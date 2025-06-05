from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from config.dependencies import get_users_email_notificator
from database import get_db, User
from database.models.movies import CommentModel, CommentReactionModel, ReactionEnum
from notifications import EmailSenderInterface
from routes.dependencies import get_current_user
from schemas.movies import CommentSchema, CommentCreate, ReactionRequest

router = APIRouter(prefix="/comments", tags=["comments"])

security = HTTPBearer()


@router.post(
    "/{comment_id}/reply/",
    response_model=CommentSchema,
    dependencies=[Depends(security)],
    status_code=status.HTTP_201_CREATED)
async def reply_to_comment(
        comment_id: int,
        comment_data: CommentCreate,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        email_sender: EmailSenderInterface = Depends(get_users_email_notificator)
):
    parent_comment = await db.get(CommentModel, comment_id)
    if not parent_comment:
        raise HTTPException(status_code=404, detail="Parent comment not found")

    new_comment = CommentModel(
        content=comment_data.content,
        user_id=current_user.id,
        movie_id=parent_comment.movie_id,
        parent_id=comment_id
    )

    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)

    if parent_comment.user_id != current_user.id:
        background_tasks.add_task(
            email_sender.send_comment_reply_notification,
            parent_comment.user.email,
            current_user.email,
            parent_comment.content,
            new_comment.content
        )

    new_comment.user_email = current_user.email
    return new_comment


@router.post(
    "/{comment_id}/reaction/",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(security)],
)
async def set_comment_reaction(
        comment_id: int,
        reaction_data: ReactionRequest,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        email_sender: EmailSenderInterface = Depends(get_users_email_notificator),
):
    comment = await db.get(CommentModel, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    existing_reaction = await db.execute(
        select(CommentReactionModel).where(
            and_(
                CommentReactionModel.user_id == current_user.id,
                CommentReactionModel.comment_id == comment_id
            )
        )
    )
    existing_reaction = existing_reaction.scalar_one_or_none()

    reaction = reaction_data.reaction

    if reaction is None:
        if existing_reaction:
            await db.delete(existing_reaction)
            await db.commit()
        return {"detail": "Reaction removed"}
    else:
        if existing_reaction:
            existing_reaction.reaction = reaction
        else:
            new_reaction = CommentReactionModel(
                user_id=current_user.id,
                comment_id=comment_id,
                reaction=reaction
            )
            db.add(new_reaction)
        await db.commit()

    if comment.user_id != current_user.id and reaction is not None:
        background_tasks.add_task(
            email_sender.send_comment_reaction_notification,
            comment.user.email,
            current_user.email,
            reaction.value,
            comment.content
        )

    return {"detail": "Reaction updated"}


@router.get(
    "/{comment_id}",
    response_model=CommentSchema,
)
@router.get(
    "/{comment_id}",
    response_model=CommentSchema,
    operation_id="get_comment_with_replies",
)
async def get_comment_with_replies(
        comment_id: int,
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CommentModel)
        .where(CommentModel.id == comment_id)
        .options(
            joinedload(CommentModel.user),
            selectinload(CommentModel.reactions)
        )
    )
    main_comment = result.scalar_one_or_none()

    if not main_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    result_all = await db.execute(
        select(CommentModel)
        .where(CommentModel.movie_id == main_comment.movie_id)
        .options(
            joinedload(CommentModel.user),
            selectinload(CommentModel.reactions)
        )
    )
    all_comments = result_all.unique().scalars().all()

    comment_dict = defaultdict(list)
    id_to_comment = {}
    for comment in all_comments:
        comment_dict[comment.parent_id].append(comment.id)
        id_to_comment[comment.id] = {
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at,
            "user_id": comment.user_id,
            "movie_id": comment.movie_id,
            "parent_id": comment.parent_id,
            "user_email": comment.user.email,
            "likes_count": sum(1 for r in comment.reactions if r.reaction == ReactionEnum.LIKE),
            "dislikes_count": sum(1 for r in comment.reactions if r.reaction == ReactionEnum.DISLIKE),
            "replies": []
        }

    def build_comment_tree(parent_id=None):
        tree = []
        for comment_id in comment_dict.get(parent_id, []):
            comment_data = id_to_comment[comment_id]
            comment_data["replies"] = build_comment_tree(comment_id)
            tree.append(comment_data)
        return tree

    main_comment_data = id_to_comment[main_comment.id]
    main_comment_data["replies"] = build_comment_tree(main_comment.id)

    return main_comment_data

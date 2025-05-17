from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config.dependencies import get_accounts_email_notificator
from database import get_db, User
from database.models.movies import CommentModel, CommentReactionModel, ReactionEnum
from notifications import EmailSenderInterface
from routes.dependencies import get_current_user
from schemas.movies import CommentSchema, CommentCreate, CommentReactionRequest

router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("/{comment_id}/reply", response_model=CommentSchema, status_code=status.HTTP_201_CREATED)
async def reply_to_comment(
        comment_id: int,
        comment_data: CommentCreate,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator)
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


@router.post("/{comment_id}/reaction", status_code=status.HTTP_200_OK)
async def set_comment_reaction(
        comment_id: int,
        reaction_data: CommentReactionRequest,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
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


@router.get("/{comment_id}", response_model=CommentSchema)
async def get_comment_with_replies(
        comment_id: int,
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CommentModel)
        .where(CommentModel.id == comment_id)
        .options(
            joinedload(CommentModel.user),
            joinedload(CommentModel.replies).joinedload(CommentModel.user),
            joinedload(CommentModel.reactions)
        )
    )
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    likes = sum(1 for r in comment.reactions if r.reaction == ReactionEnum.LIKE)
    dislikes = sum(1 for r in comment.reactions if r.reaction == ReactionEnum.DISLIKE)

    comment.likes_count = likes
    comment.dislikes_count = dislikes
    comment.user_email = comment.user.email

    def process_replies(replies):
        for reply in replies:
            reply.likes_count = sum(1 for r in reply.reactions if r.reaction == ReactionEnum.LIKE)
            reply.dislikes_count = sum(1 for r in reply.reactions if r.reaction == ReactionEnum.DISLIKE)
            reply.user_email = reply.user.email
            if reply.replies:
                process_replies(reply.replies)

    process_replies(comment.replies)

    return comment

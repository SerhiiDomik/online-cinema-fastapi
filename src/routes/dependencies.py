from fastapi import Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, DeclarativeMeta

from config.dependencies import oauth2_scheme, get_jwt_auth_manager
from database import User, UserGroupEnum
from database.models.movies import CommentModel, ReactionEnum
from database import get_db
from schemas.movies import CommentSchema
from security.interfaces import JWTAuthManagerInterface
from typing import Type, List, Optional


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        jwt_auth: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db)
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt_auth.decode_access_token(token)
        user_id: int = int(payload.get("sub"))
        if user_id is None:
            raise credentials_exception
    except (JWTError, ValueError, AttributeError):
        raise credentials_exception

    stmt = (
        select(User)
        .options(selectinload(User.group))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    return user


def parse_comment_with_replies_model(comment: CommentModel) -> CommentSchema:
    return CommentSchema(
        id=comment.id,
        content=comment.content,
        created_at=comment.created_at,
        user_id=comment.user_id,
        movie_id=comment.movie_id,
        user_email=comment.user.email,
        parent_id=comment.parent_id,
        replies=[parse_comment_with_replies_model(reply) for reply in comment.replies],
        likes_count=len([r for r in comment.reactions if r.reaction == ReactionEnum.LIKE]),
        dislikes_count=len([r for r in comment.reactions if r.reaction == ReactionEnum.DISLIKE])
    )

async def require_admin_or_moderator(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.group.name not in (UserGroupEnum.ADMIN, UserGroupEnum.MODERATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action."
        )
    return current_user

async def get_or_create_entities_by_names(
    db: AsyncSession,
    model: Type[DeclarativeMeta],
    names: List[str]
) -> List[DeclarativeMeta]:

    result = []
    for name in names:
        stmt = select(model).where(model.name == name)
        instance = (await db.execute(stmt)).scalar_one_or_none()
        if not instance:
            instance = model(name=name)
            db.add(instance)
            await db.flush()
        result.append(instance)
    return result

async def update_relation_if_present(
    db: AsyncSession,
    model: Type[DeclarativeMeta],
    names: Optional[List[str]]
) -> Optional[List[DeclarativeMeta]]:
    if names is None:
        return None
    return await get_or_create_entities_by_names(db, model, names)

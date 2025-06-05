from fastapi import Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import oauth2_scheme, get_jwt_auth_manager
from database import User
from database.models.movies import CommentModel, ReactionEnum
from database.session_postgresql import get_postgresql_db
from database.session_sqlite import get_sqlite_db
from schemas.movies import CommentSchema
from security.interfaces import JWTAuthManagerInterface


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        jwt_auth: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_sqlite_db)
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

    user = await db.get(User, user_id)
    if user is None:
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

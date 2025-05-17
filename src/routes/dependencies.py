from aiosmtplib import status
from fastapi import Depends, HTTPException
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import oauth2_scheme, get_jwt_auth_manager
from database import User
from database.session_postgresql import get_postgresql_db
from security.interfaces import JWTAuthManagerInterface


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        jwt_auth: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_postgresql_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt_auth.decode_token(token)
        user_id: int = int(payload.get("sub"))
        if user_id is None:
            raise credentials_exception
    except (JWTError, ValueError, AttributeError):
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user

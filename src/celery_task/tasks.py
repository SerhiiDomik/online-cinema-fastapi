from celery import shared_task
from datetime import datetime, timezone
from sqlalchemy import delete
from sqlalchemy.orm import Session

from database.session_postgresql import sync_postgresql_engine
from database.models.users import (
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
)


def delete_expired_tokens_sync(session: Session):
    now = datetime.now(timezone.utc)

    session.execute(
        delete(ActivationTokenModel).where(ActivationTokenModel.expires_at < now)
    )
    session.execute(
        delete(PasswordResetTokenModel).where(PasswordResetTokenModel.expires_at < now)
    )
    session.execute(delete(RefreshTokenModel).where(RefreshTokenModel.expires_at < now))
    session.commit()


@shared_task
def delete_expired_tokens():
    engine = sync_postgresql_engine
    with Session(engine) as session:
        delete_expired_tokens_sync(session)

from celery import shared_task
from datetime import datetime, timezone
from sqlalchemy import delete
from sqlalchemy.orm import Session

from database.session_postgresql import sync_postgresql_engine
from database.models.users import (
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel
)

@shared_task
def delete_expired_tokens():
    now = datetime.now(timezone.utc)
    engine = sync_postgresql_engine()

    with Session(engine) as session:
        session.execute(
            delete(ActivationTokenModel)
            .where(ActivationTokenModel.expires_at < now)
        )
        session.execute(
            delete(PasswordResetTokenModel)
            .where(PasswordResetTokenModel.expires_at < now)
        )
        session.execute(
            delete(RefreshTokenModel)
            .where(RefreshTokenModel.expires_at < now)
        )

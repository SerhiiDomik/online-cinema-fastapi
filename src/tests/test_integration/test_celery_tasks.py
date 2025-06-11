import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import insert, select

from celery_task.tasks import _delete_expired_tokens_sync
from database.models.users import (
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
)


@pytest.mark.asyncio
async def test_delete_expired_tokens(db_session):
    now = datetime.now(timezone.utc)

    expired_activation_token = ActivationTokenModel(
        user_id=1, token="expired1", expires_at=now - timedelta(days=1)
    )
    expired_password_token = PasswordResetTokenModel(
        user_id=2, token="expired2", expires_at=now - timedelta(days=1)
    )
    expired_refresh_token = RefreshTokenModel(
        user_id=3, token="expired3", expires_at=now - timedelta(days=1)
    )

    valid_token = ActivationTokenModel(
        user_id=4, token="valid", expires_at=now + timedelta(days=1)
    )

    db_session.add_all(
        [
            expired_activation_token,
            expired_password_token,
            expired_refresh_token,
            valid_token,
        ]
    )
    await db_session.commit()

    await db_session.run_sync(_delete_expired_tokens_sync)

    remaining = await db_session.execute(select(ActivationTokenModel))
    remaining_tokens = remaining.scalars().all()

    assert len(remaining_tokens) == 1
    assert remaining_tokens[0].token == "valid"

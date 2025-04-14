from logging.config import fileConfig

from alembic import context

from database.models import users  # noqa: F401
from database.models.base import Base
from sqlalchemy import create_engine
from src.config import get_settings

settings = get_settings()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    engine = create_engine(settings.SQLITE_DB_URL.replace("+aiosqlite", ""))
    connectable = engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True
        )

        with context.begin_transaction():
            context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(settings.SQLITE_DB_URL.replace("+aiosqlite", ""))
    connectable = engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

import os

from database.models.base import Base
from database.models.users import (
    User,
    UserGroup,
    UserGroupEnum,
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserProfileModel
)
from database.validators import accounts as accounts_validators

environment = os.getenv("ENVIRONMENT", "developing")

if environment == "testing":
    from database.session_sqlite import (
        get_sqlite_db_contextmanager as get_db_contextmanager,
        get_sqlite_db as get_db,
        reset_sqlite_database as reset_database,
    )
else:
    from database.session_postgresql import (
        get_postgresql_db_contextmanager as get_db_contextmanager,
        get_postgresql_db as get_db,
    )
    reset_database = None

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    BASE_DIR: Path = Path(__file__).parent.parent
    SQLITE_DB_URL: str = "sqlite+aiosqlite:///./test.db"

    PATH_TO_EMAIL_TEMPLATES_DIR: str = str(BASE_DIR / "notifications" / "templates")
    ACTIVATION_EMAIL_TEMPLATE_NAME: str = "activation_request.html"
    ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME: str = "activation_complete.html"
    PASSWORD_RESET_TEMPLATE_NAME: str = "password_reset_request.html"
    PASSWORD_RESET_COMPLETE_TEMPLATE_NAME: str = "password_reset_complete.html"
    COMMENT_REACTION_TEMPLATE: str = "comment_reaction.html"
    COMMENT_REPLY_TEMPLATE: str = "comment_reply.html"

    SECRET_KEY_ACCESS: str = os.getenv("SECRET_KEY_ACCESS", "secret_access_key")
    SECRET_KEY_REFRESH: str = os.getenv("SECRET_KEY_REFRESH", "secret_refresh_key")
    JWT_SIGNING_ALGORITHM: str = os.getenv("JWT_SIGNING_ALGORITHM", "HS256")
    LOGIN_TIME_DAYS: int = 7

    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "localhost")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", 1025))
    EMAIL_HOST_USER: str = os.getenv("EMAIL_HOST_USER", "user")
    EMAIL_HOST_PASSWORD: str = os.getenv("EMAIL_HOST_PASSWORD", "password")
    EMAIL_USE_TLS: bool = os.getenv("EMAIL_USE_TLS", "False").lower() == "true"

    S3_STORAGE_HOST: str = os.getenv("MINIO_HOST", "minio-theater")
    S3_STORAGE_PORT: int = os.getenv("MINIO_PORT", 9000)
    S3_STORAGE_ACCESS_KEY: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    S3_STORAGE_SECRET_KEY: str = os.getenv("MINIO_ROOT_PASSWORD", "some_password")
    S3_BUCKET_NAME: str = os.getenv("MINIO_STORAGE", "theater-storage")

    @property
    def S3_STORAGE_ENDPOINT(self) -> str:
        return f"http://{self.S3_STORAGE_HOST}:{self.S3_STORAGE_PORT}"

    class Config:
        env_file = ".env"


class TestingSettings(Settings):
    SQLITE_DB_URL: str = "sqlite+aiosqlite:///:memory:"

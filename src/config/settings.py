from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BASE_DIR: Path = Path(__file__).parent.parent
    SQLITE_DB_URL: str = "sqlite:///./test.db"

    SECRET_KEY_ACCESS: str = "secret-key-123"
    SECRET_KEY_REFRESH: str = "refresh-key-456"
    JWT_SIGNING_ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"

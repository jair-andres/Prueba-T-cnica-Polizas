import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Settings:
    def __init__(self) -> None:
        self.database_url: str = os.getenv("DATABASE_URL")
        self.app_port: int = int(os.getenv("APP_PORT", "8000"))
        self.app_env: str = os.getenv("APP_ENV", "development")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
        self.jwt_secret: str = os.getenv("JWT_SECRET", "cambiar_esto_en_produccion")
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRATION_MINUTES", "30"))
        self.max_login_attempts: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
        self.login_cooldown_minutes: int = int(os.getenv("LOGIN_COOLDOWN_MINUTES", "15"))


settings = Settings()

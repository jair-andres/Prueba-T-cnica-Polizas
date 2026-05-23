from pathlib import Path
from dotenv import load_dotenv
import os


# Load .env from project root if present
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Settings:
    def __init__(self) -> None:
        self.database_url: str = os.getenv("DATABASE_URL")
        self.app_port: int = int(os.getenv("APP_PORT", "8000"))
        self.app_env: str = os.getenv("APP_ENV", "development")
        self.app_tz: str = os.getenv("APP_TZ", "America/Bogota")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

        # JWT settings
        self.jwt_secret: str = os.getenv("JWT_SECRET", "cambiar_esto_en_produccion")
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRATION_MINUTES", "30"))

        # Login attempt limits
        self.max_login_attempts: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
        self.login_cooldown_minutes: int = int(os.getenv("LOGIN_COOLDOWN_MINUTES", "15"))


settings = Settings()

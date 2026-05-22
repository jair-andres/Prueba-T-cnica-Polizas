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


settings = Settings()

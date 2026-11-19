import os

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field

    class Settings(BaseSettings):
        APP_NAME: str = "CoreNest — Household Finance Tracker"
        DATABASE_URL: str = Field(
            default="postgresql+asyncpg://rentapp:rentapp_secure_password@localhost:5432/household_tracker"
        )
        DEBUG: bool = False
        SESSION_TTL_DAYS: int = 30
        COOKIE_SECURE: bool = False

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"

    settings = Settings()
except ImportError:
    class SettingsFallback:
        APP_NAME: str = os.environ.get("APP_NAME", "CoreNest — Household Finance Tracker")
        DATABASE_URL: str = os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://rentapp:rentapp_secure_password@localhost:5432/household_tracker"
        )
        DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
        SESSION_TTL_DAYS: int = int(os.environ.get("SESSION_TTL_DAYS", "30"))
        COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

    settings = SettingsFallback()

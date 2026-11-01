"""Application configuration and settings using Pydantic Settings."""

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base backend directory pointing to backend/.env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Core application settings loaded from environment variables or .env file."""

    # Application Information
    APP_NAME: str = "EventPrice Intelligence API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Server Configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    # Database Configuration (Defaults to SQLite for local development; switch to PostgreSQL via env)
    DATABASE_URL: str = "sqlite:///./eventprice.db"
    DB_ECHO_LOG: bool = False

    # Security (Loaded from environment, never hardcoded in production)
    SECRET_KEY: str = "dev-insecure-secret-key-change-in-production"

    # AI & Gemini Configuration (Stored in backend server environment only, never exposed to client)
    AI_ENABLED: bool = True
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_TIMEOUT_SECONDS: float = 20.0

    # External Data Providers Configuration (OpenWeather, OpenStreetMap, Overpass, Nominatim)
    OPENWEATHER_ENABLED: bool = True
    OPENWEATHER_API_KEY: Optional[str] = None
    OPENWEATHER_BASE_URL: str = "https://api.openweathermap.org/data/2.5"
    OPENWEATHER_TIMEOUT_SECONDS: float = 10.0

    OVERPASS_ENABLED: bool = True
    OVERPASS_BASE_URL: str = "https://overpass-api.de/api/interpreter"
    OVERPASS_TIMEOUT_SECONDS: float = 25.0

    NOMINATIM_ENABLED: bool = True
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    NOMINATIM_TIMEOUT_SECONDS: float = 10.0
    NOMINATIM_USER_AGENT: str = "EventPriceIntelligence/1.0 (contact@eventprice.local)"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Normalize PostgreSQL schemes to use the modern psycopg (v3) driver and resolve relative SQLite paths."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+psycopg://", 1)
            elif value.startswith("postgresql://"):
                return value.replace("postgresql://", "postgresql+psycopg://", 1)
            elif value.startswith("sqlite:///") and not value.startswith("sqlite:///:memory:"):
                path_part = value.replace("sqlite:///", "")
                if path_part.startswith("./"):
                    resolved = (BASE_DIR / path_part[2:]).resolve().as_posix()
                    return f"sqlite:///{resolved}"
                elif not Path(path_part).is_absolute():
                    resolved = (BASE_DIR / path_part).resolve().as_posix()
                    return f"sqlite:///{resolved}"
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        """Allow CORS_ORIGINS as either a JSON array or comma-separated string."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    return json.loads(value)
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        elif isinstance(value, list):
            return value
        return ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()


# Default singleton instance
settings = get_settings()



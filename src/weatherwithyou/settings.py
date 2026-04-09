from dataclasses import dataclass
from functools import lru_cache
import os


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default

    return float(value)


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    app_version: str
    environment: str
    debug: bool
    database_url: str
    request_timeout_seconds: float
    nominatim_base_url: str
    nominatim_user_agent: str
    open_meteo_forecast_base_url: str
    open_meteo_archive_base_url: str


@lru_cache
def get_settings() -> Settings:
    app_version = os.getenv("APP_VERSION", "0.1.0")

    return Settings(
        app_name=os.getenv("APP_NAME", "Weather With You API"),
        app_version=app_version,
        environment=os.getenv("APP_ENV", "development"),
        debug=_get_bool("DEBUG", False),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/weatherwithyou",
        ),
        request_timeout_seconds=_get_float("REQUEST_TIMEOUT_SECONDS", 10.0),
        nominatim_base_url=os.getenv(
            "NOMINATIM_BASE_URL",
            "https://nominatim.openstreetmap.org",
        ),
        nominatim_user_agent=os.getenv(
            "NOMINATIM_USER_AGENT",
            f"weatherwithyou/{app_version}",
        ),
        open_meteo_forecast_base_url=os.getenv(
            "OPEN_METEO_FORECAST_BASE_URL",
            "https://api.open-meteo.com/v1",
        ),
        open_meteo_archive_base_url=os.getenv(
            "OPEN_METEO_ARCHIVE_BASE_URL",
            "https://archive-api.open-meteo.com/v1",
        ),
    )

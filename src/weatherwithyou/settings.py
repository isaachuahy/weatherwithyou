from dataclasses import dataclass
from functools import lru_cache
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - this fallback only matters before deps are installed.
    load_dotenv = None


if load_dotenv is not None:
    # Load the repo's .env file into the process environment once so the rest of
    # the settings module can stay simple and continue using os.getenv().
    load_dotenv()


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


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    return int(value)


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
    google_maps_embed_api_key: str | None
    google_maps_embed_base_url: str
    youtube_data_api_key: str | None
    youtube_data_api_base_url: str
    youtube_max_results: int
    gemini_api_key: str | None
    gemini_model: str


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
        google_maps_embed_api_key=os.getenv("GOOGLE_MAPS_EMBED_API_KEY"),
        google_maps_embed_base_url=os.getenv(
            "GOOGLE_MAPS_EMBED_BASE_URL",
            "https://www.google.com/maps/embed/v1",
        ),
        youtube_data_api_key=os.getenv("YOUTUBE_DATA_API_KEY"),
        youtube_data_api_base_url=os.getenv(
            "YOUTUBE_DATA_API_BASE_URL",
            "https://www.googleapis.com/youtube/v3",
        ),
        youtube_max_results=_get_int("YOUTUBE_MAX_RESULTS", 3),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    )

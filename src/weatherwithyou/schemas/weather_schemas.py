from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def to_camel(string: str) -> str:
    """Convert snake_case field names to camelCase for the external API."""

    parts = string.split("_")
    return parts[0] + "".join("DateTime" if part == "datetime" else part.capitalize() for part in parts[1:])


class APIModel(BaseModel):
    """Base schema with shared API serialization settings."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
    )


class WeatherMode(StrEnum):
    """Supported weather lookup modes."""

    HISTORICAL = "historical"
    CURRENT = "current"
    FORECAST = "forecast"


class WeatherUnits(StrEnum):
    """Supported unit systems for weather lookups."""

    METRIC = "metric"
    IMPERIAL = "imperial"


class WeatherData(BaseModel):
    """Application wrapper for stored provider payloads."""

    provider: str = Field(default="open-meteo")
    payload: dict[str, Any]


def _ensure_timezone_aware(value: datetime | None, field_name: str) -> None:
    """Reject naive datetimes so the API contract stays timezone-aware."""

    if value is None:
        return

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone offset.")


class WeatherRequestBase(APIModel):
    """Shared fields for create-style weather lookup requests."""

    location_input: str = Field(min_length=1)
    mode: WeatherMode
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    units: WeatherUnits

    @model_validator(mode="after")
    def validate_datetimes(self) -> "WeatherRequestBase":
        """Apply mode-specific datetime rules before provider-specific validation runs."""

        _ensure_timezone_aware(self.start_datetime, "startDateTime")
        _ensure_timezone_aware(self.end_datetime, "endDateTime")

        if self.mode == WeatherMode.CURRENT:
            if self.start_datetime is not None or self.end_datetime is not None:
                raise ValueError("current mode does not accept startDateTime or endDateTime.")
            return self

        if self.start_datetime is None or self.end_datetime is None:
            raise ValueError("startDateTime and endDateTime are required for this mode.")

        if self.start_datetime > self.end_datetime:
            raise ValueError("startDateTime must be less than or equal to endDateTime.")
        return self


class WeatherCreateRequest(WeatherRequestBase):
    """Request body for creating a weather lookup."""

    pass


class WeatherUpdateRequest(APIModel):
    """Partial update body for an existing weather lookup."""

    location_input: str | None = Field(default=None, min_length=1)
    mode: WeatherMode | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    units: WeatherUnits | None = None

    @model_validator(mode="after")
    def validate_partial_datetimes(self) -> "WeatherUpdateRequest":
        """Apply partial mode-aware validation for weather lookup updates."""

        _ensure_timezone_aware(self.start_datetime, "startDateTime")
        _ensure_timezone_aware(self.end_datetime, "endDateTime")

        if self.mode == WeatherMode.CURRENT:
            if self.start_datetime is not None or self.end_datetime is not None:
                raise ValueError("current mode does not accept startDateTime or endDateTime.")
            return self

        if (self.start_datetime is None) ^ (self.end_datetime is None):
            raise ValueError("startDateTime and endDateTime must be provided together.")

        if (
            self.start_datetime
            and self.end_datetime
            and self.start_datetime > self.end_datetime
        ):
            raise ValueError("startDateTime must be less than or equal to endDateTime.")
        return self


class WeatherQueryResponse(APIModel):
    """Stable API response shape for saved weather lookup records."""

    id: UUID
    location_input: str
    normalized_location: str
    latitude: Decimal
    longitude: Decimal
    mode: WeatherMode
    start_datetime: datetime | None
    end_datetime: datetime | None
    units: WeatherUnits
    weather_data: WeatherData
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        # This lets us build response schemas directly from SQLAlchemy model instances.
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
    )

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def to_camel(string: str) -> str:
    """Convert snake_case field names to camelCase for the external API."""

    parts = string.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


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


class WeatherRequestBase(APIModel):
    """Shared fields for create-style weather lookup requests."""

    location_input: str = Field(min_length=1)
    mode: WeatherMode
    start_date: date
    end_date: date
    units: WeatherUnits

    @model_validator(mode="after")
    def validate_dates(self) -> "WeatherRequestBase":
        """Reject invalid date ordering before provider-specific validation runs."""

        if self.start_date > self.end_date:
            raise ValueError("startDate must be less than or equal to endDate.")
        return self


class WeatherCreateRequest(WeatherRequestBase):
    """Request body for creating a weather lookup."""

    pass


class WeatherUpdateRequest(APIModel):
    """Partial update body for an existing weather lookup."""

    location_input: str | None = Field(default=None, min_length=1)
    mode: WeatherMode | None = None
    start_date: date | None = None
    end_date: date | None = None
    units: WeatherUnits | None = None

    @model_validator(mode="after")
    def validate_partial_dates(self) -> "WeatherUpdateRequest":
        """Validate date ordering only when both partial date fields are present."""

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("startDate must be less than or equal to endDate.")
        return self


class WeatherQueryResponse(APIModel):
    """Stable API response shape for saved weather lookup records."""

    id: UUID
    location_input: str
    normalized_location: str
    latitude: Decimal
    longitude: Decimal
    mode: WeatherMode
    start_date: date
    end_date: date
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

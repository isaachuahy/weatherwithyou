from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from weatherwithyou.schemas.weather_schemas import WeatherMode, WeatherUnits
from weatherwithyou.settings import get_settings

HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]

CURRENT_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "is_day",
    "precipitation",
    "rain",
    "showers",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]


class WeatherProviderError(Exception):
    """Raised when the upstream weather provider request fails."""


class OpenMeteoClient:
    """Small Open-Meteo client for historical, current, and forecast lookups."""

    def __init__(self) -> None:
        settings = get_settings()
        self.forecast_base_url = settings.open_meteo_forecast_base_url
        self.archive_base_url = settings.open_meteo_archive_base_url
        self.timeout = settings.request_timeout_seconds

    def fetch_weather(
        self,
        *,
        latitude: Decimal,
        longitude: Decimal,
        mode: WeatherMode,
        start_datetime: datetime | None,
        end_datetime: datetime | None,
        units: WeatherUnits,
    ) -> dict[str, Any]:
        """Fetch weather data from the matching Open-Meteo endpoint for the requested mode."""

        base_url = self.archive_base_url if mode == WeatherMode.HISTORICAL else self.forecast_base_url
        params = self._build_params(
            latitude=latitude,
            longitude=longitude,
            mode=mode,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            units=units,
        )

        try:
            with httpx.Client(base_url=base_url, timeout=self.timeout) as client:
                response = client.get("/forecast" if mode != WeatherMode.HISTORICAL else "/archive", params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WeatherProviderError("Weather provider request failed.") from exc

        payload = response.json()
        if mode == WeatherMode.CURRENT:
            return payload

        return self._filter_hourly_window(
            payload=payload,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )

    def _build_params(
        self,
        *,
        latitude: Decimal,
        longitude: Decimal,
        mode: WeatherMode,
        start_datetime: datetime | None,
        end_datetime: datetime | None,
        units: WeatherUnits,
    ) -> dict[str, Any]:
        """Build provider request parameters for a weather lookup."""

        params: dict[str, Any] = {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "temperature_unit": self._temperature_unit(units),
            "wind_speed_unit": self._wind_speed_unit(units),
            "precipitation_unit": self._precipitation_unit(units),
            "timezone": "GMT",
        }

        if mode == WeatherMode.CURRENT:
            params["current"] = ",".join(CURRENT_VARIABLES)
            return params

        if start_datetime is None or end_datetime is None:
            raise ValueError("startDateTime and endDateTime are required for this mode.")

        params["hourly"] = ",".join(HOURLY_VARIABLES)

        if mode == WeatherMode.HISTORICAL:
            params["start_date"] = start_datetime.astimezone(timezone.utc).date().isoformat()
            params["end_date"] = end_datetime.astimezone(timezone.utc).date().isoformat()
            return params

        params["start_hour"] = self._to_provider_hour(start_datetime)
        params["end_hour"] = self._to_provider_hour(end_datetime)
        return params

    def _filter_hourly_window(
        self,
        *,
        payload: dict[str, Any],
        start_datetime: datetime | None,
        end_datetime: datetime | None,
    ) -> dict[str, Any]:
        """Trim hourly payloads to the exact requested datetime window."""

        if start_datetime is None or end_datetime is None:
            return payload

        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            return payload

        time_values = hourly.get("time")
        if not isinstance(time_values, list):
            return payload

        timezone_name = payload.get("timezone", "GMT")
        provider_timezone = ZoneInfo("UTC") if timezone_name == "GMT" else ZoneInfo(timezone_name)
        start_utc = start_datetime.astimezone(timezone.utc)
        end_utc = end_datetime.astimezone(timezone.utc)

        keep_indexes = [
            index
            for index, value in enumerate(time_values)
            if start_utc
            <= datetime.fromisoformat(value).replace(tzinfo=provider_timezone).astimezone(timezone.utc)
            <= end_utc
        ]

        filtered_hourly: dict[str, Any] = {}
        for key, values in hourly.items():
            if isinstance(values, list):
                filtered_hourly[key] = [values[index] for index in keep_indexes]
            else:
                filtered_hourly[key] = values

        payload["hourly"] = filtered_hourly
        return payload

    def _to_provider_hour(self, value: datetime) -> str:
        """Convert a timezone-aware datetime to the provider's UTC hour format."""

        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")

    def _temperature_unit(self, units: WeatherUnits) -> str:
        return "fahrenheit" if units == WeatherUnits.IMPERIAL else "celsius"

    def _wind_speed_unit(self, units: WeatherUnits) -> str:
        return "mph" if units == WeatherUnits.IMPERIAL else "kmh"

    def _precipitation_unit(self, units: WeatherUnits) -> str:
        return "inch" if units == WeatherUnits.IMPERIAL else "mm"

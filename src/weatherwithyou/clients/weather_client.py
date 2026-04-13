from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from weatherwithyou.schemas.weather_schemas import WeatherMode, WeatherUnits
from weatherwithyou.settings import get_settings

# We can choose to define the specific variables we want to fetch from the provider for each mode, 
# which can help optimize the request and ensure consistent data structure in our application. 
# For simplicity, we're fetching all daily variables for historical and forecast modes, but in a more complex application we might want to allow users to specify which variables they're interested in or implement some logic to determine that based on the mode and use case.
DAILY_VARIABLES = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "precipitation_hours",
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
    "sea_level_pressure",
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
        start_date: date,
        end_date: date,
        units: WeatherUnits,
    ) -> dict[str, Any]:
        """Fetch weather data from the matching Open-Meteo endpoint for the requested mode."""

        base_url = self.archive_base_url if mode == WeatherMode.HISTORICAL else self.forecast_base_url
        params = self._build_params(
            latitude=latitude,
            longitude=longitude,
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            units=units,
        )

        try:
            # Using httpx.Client here to take advantage of connection pooling and other optimizations for multiple requests to the same provider.
            with httpx.Client(base_url=base_url, timeout=self.timeout) as client:
                response = client.get("/forecast" if mode != WeatherMode.HISTORICAL else "/archive", params=params)
                # Open-Meteo returns 200 with an error message in the body for some error cases (e.g. invalid coordinates), 
                # so we need to check for that as well.
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WeatherProviderError("Weather provider request failed.") from exc

        return response.json()

    def _build_params(
        self,
        *,
        latitude: Decimal,
        longitude: Decimal,
        mode: WeatherMode,
        start_date: date,
        end_date: date,
        units: WeatherUnits,
    ) -> dict[str, Any]:
        """Helper method to build the provider request parameters for a weather lookup."""

        params: dict[str, Any] = {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "temperature_unit": self._temperature_unit(units),
            "wind_speed_unit": self._wind_speed_unit(units),
            "precipitation_unit": self._precipitation_unit(units),
            "timezone": "auto",
        }

        if mode == WeatherMode.CURRENT:
            params["current"] = ",".join(CURRENT_VARIABLES)
            return params

        params["start_date"] = start_date.isoformat() 
        params["end_date"] = end_date.isoformat()
        params["daily"] = ",".join(DAILY_VARIABLES) # Fetching all daily variables for simplicity
        return params

    def _temperature_unit(self, units: WeatherUnits) -> str:
        return "fahrenheit" if units == WeatherUnits.IMPERIAL else "celsius"

    def _wind_speed_unit(self, units: WeatherUnits) -> str:
        return "mph" if units == WeatherUnits.IMPERIAL else "kmh"

    def _precipitation_unit(self, units: WeatherUnits) -> str:
        return "inch" if units == WeatherUnits.IMPERIAL else "mm"

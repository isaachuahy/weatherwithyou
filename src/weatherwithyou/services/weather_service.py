from datetime import UTC, datetime

from sqlalchemy.orm import Session

from weatherwithyou.clients.geocoding import NominatimClient
from weatherwithyou.clients.weather_client import OpenMeteoClient
from weatherwithyou.models.weather_query import WeatherQuery
from weatherwithyou.schemas.weather_schemas import (
    WeatherCreateRequest,
    WeatherMode,
    WeatherUpdateRequest,
)


class WeatherService:
    """Coordinate geocoding, weather retrieval, and persistence for weather lookups."""

    def __init__(
        self,
        db_session: Session,
        geocoding_client: NominatimClient | None = None,
        weather_client: OpenMeteoClient | None = None,
    ) -> None:
        self.db_session = db_session
        self.geocoding_client = geocoding_client or NominatimClient()
        self.weather_client = weather_client or OpenMeteoClient()

    def _validate_mode_datetimes(
        self,
        *,
        mode: WeatherMode,
        start_datetime: datetime | None,
        end_datetime: datetime | None,
    ) -> None:
        """Validate the final merged mode/datetime state before external calls or persistence."""

        if mode == WeatherMode.CURRENT:
            if start_datetime is not None or end_datetime is not None:
                raise ValueError("current mode does not accept startDateTime or endDateTime.")
            return

        if start_datetime is None or end_datetime is None:
            raise ValueError("startDateTime and endDateTime are required for this mode.")

        if start_datetime > end_datetime:
            raise ValueError("startDateTime must be less than or equal to endDateTime.")

    def _to_utc(self, value: datetime | None) -> datetime | None:
        """Normalize timezone-aware datetimes to UTC before persistence or provider use."""

        if value is None:
            return None

        return value.astimezone(UTC)

    def create_weather_query(self, payload: WeatherCreateRequest) -> WeatherQuery:
        """Create and persist a new weather lookup record from a validated request."""

        start_datetime = self._to_utc(payload.start_datetime)
        end_datetime = self._to_utc(payload.end_datetime)

        self._validate_mode_datetimes(
            mode=payload.mode,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )

        resolved_location = self.geocoding_client.geocode(payload.location_input)
        weather_payload = self.weather_client.fetch_weather(
            latitude=resolved_location.latitude,
            longitude=resolved_location.longitude,
            mode=payload.mode,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            units=payload.units,
        )

        weather_query = WeatherQuery(
            location_input=payload.location_input,
            normalized_location=resolved_location.normalized_location,
            latitude=resolved_location.latitude,
            longitude=resolved_location.longitude,
            mode=payload.mode,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            units=payload.units,
            weather_data={
                "provider": "open-meteo",
                "payload": weather_payload,
            },
        )

        self.db_session.add(weather_query)
        self.db_session.commit()
        self.db_session.refresh(weather_query)
        return weather_query

    def update_weather_query(
        self,
        weather_query: WeatherQuery,
        payload: WeatherUpdateRequest,
    ) -> WeatherQuery:
        """Update an existing weather lookup and refresh its stored weather data."""

        provided_fields = payload.model_fields_set

        location_input = (
            payload.location_input
            if "location_input" in provided_fields
            else weather_query.location_input
        )
        mode = payload.mode if "mode" in provided_fields else weather_query.mode
        start_datetime = (
            payload.start_datetime
            if "start_datetime" in provided_fields
            else weather_query.start_datetime
        )
        end_datetime = (
            payload.end_datetime
            if "end_datetime" in provided_fields
            else weather_query.end_datetime
        )
        units = payload.units if "units" in provided_fields else weather_query.units

        start_datetime = self._to_utc(start_datetime)
        end_datetime = self._to_utc(end_datetime)

        self._validate_mode_datetimes(
            mode=mode,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )

        location_changed = location_input != weather_query.location_input
        if location_changed:
            resolved_location = self.geocoding_client.geocode(location_input)
            weather_query.normalized_location = resolved_location.normalized_location
            weather_query.latitude = resolved_location.latitude
            weather_query.longitude = resolved_location.longitude

        weather_payload = self.weather_client.fetch_weather(
            latitude=weather_query.latitude,
            longitude=weather_query.longitude,
            mode=mode,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            units=units,
        )

        weather_query.location_input = location_input
        weather_query.mode = mode
        weather_query.start_datetime = start_datetime
        weather_query.end_datetime = end_datetime
        weather_query.units = units
        weather_query.weather_data = {
            "provider": "open-meteo",
            "payload": weather_payload,
        }

        self.db_session.add(weather_query)
        self.db_session.commit()
        self.db_session.refresh(weather_query)
        return weather_query

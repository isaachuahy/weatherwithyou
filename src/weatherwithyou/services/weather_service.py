from sqlalchemy.orm import Session

from weatherwithyou.clients.geocoding import NominatimClient
from weatherwithyou.clients.weather import OpenMeteoClient
from weatherwithyou.models.weather_query import WeatherQuery
from weatherwithyou.schemas.weather import WeatherCreateRequest, WeatherUpdateRequest


class WeatherService:
    """Coordinate geocoding, weather retrieval, and persistence for weather lookups."""

    def __init__(
        self,
        db_session: Session,
        geocoding_client: NominatimClient | None = None, # Allowing clients to be injected for easier testing and future extensibility (e.g. multiple providers).
        weather_client: OpenMeteoClient | None = None, # In a more complex application, we might have provider selection logic here instead of hardcoding a single client.
    ) -> None:
        self.db_session = db_session
        self.geocoding_client = geocoding_client or NominatimClient()
        self.weather_client = weather_client or OpenMeteoClient() # For the MVP, we're directly using the Open-Meteo client, but this could be extended to support multiple providers with selection logic based on factors like availability, performance, or user preference.

    def create_weather_query(self, payload: WeatherCreateRequest) -> WeatherQuery:
        """Create and persist a new weather lookup record from a validated request."""

        resolved_location = self.geocoding_client.geocode(payload.location_input)
        weather_payload = self.weather_client.fetch_weather(
            latitude=resolved_location.latitude,
            longitude=resolved_location.longitude,
            mode=payload.mode,
            start_date=payload.start_date,
            end_date=payload.end_date,
            units=payload.units,
        )

        weather_query = WeatherQuery(
            location_input=payload.location_input,
            normalized_location=resolved_location.normalized_location,
            latitude=resolved_location.latitude,
            longitude=resolved_location.longitude,
            mode=payload.mode,
            start_date=payload.start_date,
            end_date=payload.end_date,
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

        location_input = payload.location_input or weather_query.location_input
        mode = payload.mode or weather_query.mode
        start_date = payload.start_date or weather_query.start_date
        end_date = payload.end_date or weather_query.end_date
        units = payload.units or weather_query.units

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
            start_date=start_date,
            end_date=end_date,
            units=units,
        )

        weather_query.location_input = location_input
        weather_query.mode = mode
        weather_query.start_date = start_date
        weather_query.end_date = end_date
        weather_query.units = units
        weather_query.weather_data = {
            "provider": "open-meteo",
            "payload": weather_payload,
        }

        self.db_session.add(weather_query)
        self.db_session.commit()
        self.db_session.refresh(weather_query)
        return weather_query

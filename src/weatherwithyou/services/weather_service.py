from datetime import UTC, datetime

from sqlalchemy.orm import Session

from weatherwithyou.clients.google_maps import GoogleMapsClient
from weatherwithyou.clients.geocoding import NominatimClient
from weatherwithyou.clients.pun import PunClient, PunProviderError
from weatherwithyou.clients.weather_client import OpenMeteoClient
from weatherwithyou.clients.youtube import YouTubeClient, YouTubeProviderError
from weatherwithyou.models.weather_query import WeatherQuery
from weatherwithyou.schemas.weather_schemas import (
    WeatherCreateRequest,
    WeatherEnrichment,
    WeatherEnrichmentType,
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
        google_maps_client: GoogleMapsClient | None = None,
        youtube_client: YouTubeClient | None = None,
        pun_client: PunClient | None = None,
    ) -> None:
        self.db_session = db_session
        self.geocoding_client = geocoding_client or NominatimClient()
        self.weather_client = weather_client or OpenMeteoClient()
        self.google_maps_client = google_maps_client or GoogleMapsClient()
        self.youtube_client = youtube_client or YouTubeClient()
        self.pun_client = pun_client or PunClient()

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

    def _build_enrichment(
        self,
        *,
        weather_query: WeatherQuery,
        include: list[WeatherEnrichmentType],
    ) -> WeatherEnrichment | None:
        """Assemble optional live enrichment without mutating the stored weather row."""

        if not include:
            return None

        requested = set(include)
        enrichment = WeatherEnrichment()

        if WeatherEnrichmentType.MAP in requested:
            enrichment.map = self.google_maps_client.build_place_embed(
                normalized_location=weather_query.normalized_location,
                latitude=weather_query.latitude,
                longitude=weather_query.longitude,
            )

        if WeatherEnrichmentType.YOUTUBE in requested:
            try:
                enrichment.youtube_videos = self.youtube_client.search_location_videos(
                    normalized_location=weather_query.normalized_location,
                )
            except YouTubeProviderError:
                enrichment.youtube_videos = None

        if WeatherEnrichmentType.PUN in requested:
            try:
                enrichment.pun = self.pun_client.generate_pun(
                    normalized_location=weather_query.normalized_location,
                    weather_payload=weather_query.weather_data.get("payload", {}),
                )
            except PunProviderError:
                enrichment.pun = None

        if not any(
            [
                enrichment.map,
                enrichment.youtube_videos,
                enrichment.pun,
            ]
        ):
            return None

        return enrichment

    def attach_enrichment(
        self,
        weather_query: WeatherQuery,
        include: list[WeatherEnrichmentType],
    ) -> WeatherQuery:
        """Attach live-only enrichment to a saved weather lookup for response serialization."""

        setattr(
            weather_query,
            "enrichment",
            self._build_enrichment(weather_query=weather_query, include=include),
        )
        return weather_query

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
        return self.attach_enrichment(weather_query, payload.include)

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
        return self.attach_enrichment(weather_query, payload.include or [])

from decimal import Decimal
from urllib.parse import urlencode

from weatherwithyou.schemas.weather_schemas import MapEnrichment
from weatherwithyou.settings import get_settings


class GoogleMapsClient:
    """Build Google Maps embed metadata for a resolved location."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.google_maps_embed_base_url
        self.api_key = settings.google_maps_embed_api_key

    def build_place_embed(
        self,
        *,
        normalized_location: str,
        latitude: Decimal,
        longitude: Decimal,
    ) -> MapEnrichment | None:
        """Return a map enrichment block when Google Maps is configured."""

        if not self.api_key:
            return None

        # The query string keeps the embed centered on the human-readable place,
        # while lat/lng stays available in the response for the rest of the app.
        query_string = urlencode(
            {
                "key": self.api_key,
                "q": normalized_location,
            }
        )

        return MapEnrichment(
            provider="google-maps",
            embed_url=f"{self.base_url}/place?{query_string}",
            query=normalized_location,
            latitude=latitude,
            longitude=longitude,
        )

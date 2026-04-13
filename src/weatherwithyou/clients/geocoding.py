from dataclasses import dataclass
from decimal import Decimal

import httpx

from weatherwithyou.settings import get_settings


class GeocodingError(Exception):
    """Base exception for geocoding-related failures."""

    pass


class GeocodingProviderError(GeocodingError):
    """Raised when the upstream geocoding provider request fails."""

    pass


class LocationNotFoundError(GeocodingError):
    """Raised when a location query returns no valid matches."""

    pass


@dataclass(frozen=True, slots=True)
class ResolvedLocation:
    """Normalized location data returned from the geocoding provider."""

    normalized_location: str
    latitude: Decimal
    longitude: Decimal


class NominatimClient:
    """Thin wrapper around Nominatim's search endpoint."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.nominatim_base_url
        self.timeout = settings.request_timeout_seconds
        self.user_agent = settings.nominatim_user_agent

    def geocode(self, location_input: str) -> ResolvedLocation:
        """Resolve free-form user input into a normalized location and coordinates."""

        params = {
            "q": location_input,
            "format": "jsonv2",
            # MVP behavior: take the top provider match and store that normalized result.
            "limit": 1,
        }
        headers = {
            "User-Agent": self.user_agent,
        }

        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            ) as client:
                response = client.get("/search", params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GeocodingProviderError("Geocoding provider request failed.") from exc

        results = response.json()
        if not results:
            raise LocationNotFoundError("Could not resolve the provided location.")

        match = results[0]
        return ResolvedLocation(
            # Fall back to the raw user input if the provider omits display_name.
            normalized_location=match.get("display_name", location_input),
            latitude=Decimal(match["lat"]),
            longitude=Decimal(match["lon"]),
        )

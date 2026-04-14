from typing import Any

import httpx

from weatherwithyou.schemas.weather_schemas import YouTubeVideoEnrichment
from weatherwithyou.settings import get_settings


class YouTubeProviderError(Exception):
    """Raised when the YouTube Data API request fails."""


class YouTubeClient:
    """Small YouTube client for location-based video enrichment."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.youtube_data_api_base_url
        self.api_key = settings.youtube_data_api_key
        self.max_results = settings.youtube_max_results
        self.timeout = settings.request_timeout_seconds

    def search_location_videos(self, *, normalized_location: str) -> list[YouTubeVideoEnrichment]:
        """Return a small list of YouTube videos related to the resolved location."""

        if not self.api_key:
            return []

        params = {
            "key": self.api_key,
            "part": "snippet",
            "q": normalized_location,
            "type": "video",
            "maxResults": self.max_results,
            # Keeping the payload small and location-relevant matters more than
            # exhaustive search quality for this enrichment-focused feature.
            "videoEmbeddable": "true",
            "safeSearch": "moderate",
        }

        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                response = client.get("/search", params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise YouTubeProviderError("YouTube provider request failed.") from exc

        payload = response.json()
        items = payload.get("items", [])

        return [
            self._to_video_enrichment(item)
            for item in items
            if self._is_video_result(item)
        ]

    def _is_video_result(self, item: dict[str, Any]) -> bool:
        """Guard against non-video items before shaping the response."""

        identifier = item.get("id")
        return isinstance(identifier, dict) and isinstance(identifier.get("videoId"), str)

    def _to_video_enrichment(self, item: dict[str, Any]) -> YouTubeVideoEnrichment:
        """Map a YouTube search result into the app's stable enrichment shape."""

        identifier = item["id"]
        snippet = item.get("snippet", {})
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
        video_id = identifier["videoId"]

        return YouTubeVideoEnrichment(
            provider="youtube",
            video_id=video_id,
            title=snippet.get("title", ""),
            channel_title=snippet.get("channelTitle", ""),
            thumbnail_url=thumbnail.get("url", ""),
            embed_url=f"https://www.youtube.com/embed/{video_id}",
        )

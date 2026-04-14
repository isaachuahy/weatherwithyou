from typing import Any

from google import genai

from weatherwithyou.schemas.weather_schemas import PunEnrichment
from weatherwithyou.settings import get_settings


class PunProviderError(Exception):
    """Raised when Gemini pun generation fails."""


class PunClient:
    """Generate a short weather-and-place pun using Gemini Flash."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model

    def generate_pun(
        self,
        *,
        normalized_location: str,
        weather_payload: dict[str, Any],
    ) -> PunEnrichment | None:
        """Return a short pun enrichment block when Gemini is configured."""

        if not self.api_key:
            return None

        client = genai.Client(api_key=self.api_key)
        prompt = self._build_prompt(
            normalized_location=normalized_location,
            weather_payload=weather_payload,
        )

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
        except Exception as exc:
            raise PunProviderError("Pun provider request failed.") from exc

        text = (response.text or "").strip()
        if not text:
            return None

        return PunEnrichment(
            provider="gemini-flash",
            text=text,
        )

    def _build_prompt(
        self,
        *,
        normalized_location: str,
        weather_payload: dict[str, Any],
    ) -> str:
        """Build a lightweight prompt that keeps the output short and playful."""

        # We pass a small slice of weather context rather than the entire provider
        # payload so the prompt stays cheap, focused, and easy to reason about.
        return (
            "Write exactly one short playful pun about the weather in this location. "
            "Keep it under 18 words. Avoid hashtags, emojis, bullet points, quotes, "
            "and extra explanation. "
            f"Location: {normalized_location}. "
            f"Weather context: {weather_payload!r}"
        )

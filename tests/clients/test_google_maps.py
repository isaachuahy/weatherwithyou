from decimal import Decimal

from weatherwithyou.clients.google_maps import GoogleMapsClient
from weatherwithyou.settings import get_settings


def test_build_place_embed_returns_none_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_MAPS_EMBED_API_KEY", raising=False)
    get_settings.cache_clear()

    client = GoogleMapsClient()

    result = client.build_place_embed(
        normalized_location="London, Ontario, Canada",
        latitude=Decimal("42.983675"),
        longitude=Decimal("-81.249607"),
    )

    assert result is None


def test_build_place_embed_returns_map_enrichment(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_MAPS_EMBED_API_KEY", "test-google-key")
    monkeypatch.setenv(
        "GOOGLE_MAPS_EMBED_BASE_URL",
        "https://www.google.com/maps/embed/v1",
    )
    get_settings.cache_clear()

    client = GoogleMapsClient()

    result = client.build_place_embed(
        normalized_location="London, Southwestern Ontario, Ontario, Canada",
        latitude=Decimal("42.983675"),
        longitude=Decimal("-81.249607"),
    )

    assert result is not None
    assert result.provider == "google-maps"
    assert result.query == "London, Southwestern Ontario, Ontario, Canada"
    assert result.latitude == Decimal("42.983675")
    assert result.longitude == Decimal("-81.249607")
    assert result.embed_url.startswith("https://www.google.com/maps/embed/v1/place?")
    assert "key=test-google-key" in result.embed_url
    assert "London%2C+Southwestern+Ontario%2C+Ontario%2C+Canada" in result.embed_url
    get_settings.cache_clear()

from unittest.mock import Mock, patch

from weatherwithyou.clients.pun import PunClient
from weatherwithyou.settings import get_settings


def test_generate_pun_returns_none_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()

    client = PunClient()

    result = client.generate_pun(
        normalized_location="London, Ontario, Canada",
        weather_payload={"current": {"temperature_2m": 20.0}},
    )

    assert result is None
    get_settings.cache_clear()


def test_generate_pun_returns_pun_enrichment(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    get_settings.cache_clear()

    mock_response = Mock()
    mock_response.text = "London’s forecast is looking reigneously bright."

    with patch("weatherwithyou.clients.pun.genai.Client") as client_class:
        genai_client = client_class.return_value
        genai_client.models.generate_content.return_value = mock_response

        client = PunClient()
        result = client.generate_pun(
            normalized_location="London, Southwestern Ontario, Ontario, Canada",
            weather_payload={"current": {"temperature_2m": 20.0}},
        )

    assert result is not None
    assert result.provider == "gemini-flash"
    assert result.text == "London’s forecast is looking reigneously bright."
    genai_client.models.generate_content.assert_called_once()
    get_settings.cache_clear()

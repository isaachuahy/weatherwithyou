from unittest.mock import Mock, patch

from weatherwithyou.clients.youtube import YouTubeClient
from weatherwithyou.settings import get_settings


def test_search_location_videos_returns_empty_list_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("YOUTUBE_DATA_API_KEY", raising=False)
    get_settings.cache_clear()

    client = YouTubeClient()

    result = client.search_location_videos(
        normalized_location="London, Ontario, Canada",
    )

    assert result == []


def test_search_location_videos_returns_shaped_video_results(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "test-youtube-key")
    monkeypatch.setenv("YOUTUBE_MAX_RESULTS", "2")
    get_settings.cache_clear()

    mock_response = Mock()
    mock_response.json.return_value = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "Walking around London, Ontario",
                    "channelTitle": "Example Channel",
                    "thumbnails": {
                        "high": {"url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg"}
                    },
                },
            }
        ]
    }
    mock_response.raise_for_status.return_value = None

    with patch("weatherwithyou.clients.youtube.httpx.Client") as client_class:
        httpx_client = client_class.return_value.__enter__.return_value
        httpx_client.get.return_value = mock_response

        client = YouTubeClient()
        result = client.search_location_videos(
            normalized_location="London, Southwestern Ontario, Ontario, Canada",
        )

    assert len(result) == 1
    assert result[0].provider == "youtube"
    assert result[0].video_id == "abc123"
    assert result[0].title == "Walking around London, Ontario"
    assert result[0].channel_title == "Example Channel"
    assert result[0].thumbnail_url == "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
    assert result[0].embed_url == "https://www.youtube.com/embed/abc123"
    httpx_client.get.assert_called_once()
    get_settings.cache_clear()

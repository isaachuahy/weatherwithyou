from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from weatherwithyou.clients.geocoding import ResolvedLocation
from weatherwithyou.models.weather_query import WeatherQuery
from weatherwithyou.schemas.weather_schemas import (
    WeatherCreateRequest,
    WeatherEnrichmentType,
    WeatherMode,
    WeatherUnits,
    WeatherUpdateRequest,
)
from weatherwithyou.services.weather_service import WeatherService


def test_create_weather_query_persists_expected_data() -> None:
    db_session = Mock()
    geocoding_client = Mock()
    weather_client = Mock()

    geocoding_client.geocode.return_value = ResolvedLocation(
        normalized_location="London, Ontario, Canada",
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
    )
    weather_client.fetch_weather.return_value = {
        "hourly": {"temperature_2m": [12.3]},
    }
    start_datetime = datetime(2024, 4, 1, 9, 0, tzinfo=UTC)
    end_datetime = datetime(2024, 4, 1, 18, 0, tzinfo=UTC)

    service = WeatherService(
        db_session=db_session,
        geocoding_client=geocoding_client,
        weather_client=weather_client,
    )
    payload = WeatherCreateRequest(
        locationInput="London, Ontario, Canada",
        mode=WeatherMode.HISTORICAL,
        startDateTime=start_datetime,
        endDateTime=end_datetime,
        units=WeatherUnits.METRIC,
    )

    result = service.create_weather_query(payload)

    assert isinstance(result, WeatherQuery)
    assert result.location_input == "London, Ontario, Canada"
    assert result.normalized_location == "London, Ontario, Canada"
    assert result.latitude == Decimal("42.983390")
    assert result.longitude == Decimal("-81.233040")
    assert result.mode == WeatherMode.HISTORICAL
    assert result.start_datetime == start_datetime
    assert result.end_datetime == end_datetime
    assert result.units == WeatherUnits.METRIC
    assert result.weather_data == {
        "provider": "open-meteo",
        "payload": {"hourly": {"temperature_2m": [12.3]}},
    }

    geocoding_client.geocode.assert_called_once_with("London, Ontario, Canada")
    weather_client.fetch_weather.assert_called_once_with(
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.HISTORICAL,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        units=WeatherUnits.METRIC,
    )
    db_session.add.assert_called_once_with(result)
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once_with(result)


def test_update_weather_query_reuses_existing_coordinates_when_location_is_unchanged() -> None:
    db_session = Mock()
    geocoding_client = Mock()
    weather_client = Mock()
    weather_client.fetch_weather.return_value = {
        "hourly": {"temperature_2m": [18.0]},
    }
    original_start = datetime(2024, 4, 1, 9, 0, tzinfo=UTC)
    original_end = datetime(2024, 4, 1, 18, 0, tzinfo=UTC)
    updated_start = datetime(2024, 4, 2, 9, 0, tzinfo=UTC)
    updated_end = datetime(2024, 4, 2, 18, 0, tzinfo=UTC)

    service = WeatherService(
        db_session=db_session,
        geocoding_client=geocoding_client,
        weather_client=weather_client,
    )
    weather_query = WeatherQuery(
        location_input="London, Ontario, Canada",
        normalized_location="London, Ontario, Canada",
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.HISTORICAL,
        start_datetime=original_start,
        end_datetime=original_end,
        units=WeatherUnits.METRIC,
        weather_data={"provider": "open-meteo", "payload": {}},
    )
    payload = WeatherUpdateRequest(
        startDateTime=updated_start,
        endDateTime=updated_end,
        units=WeatherUnits.IMPERIAL,
    )

    result = service.update_weather_query(weather_query, payload)

    geocoding_client.geocode.assert_not_called()
    weather_client.fetch_weather.assert_called_once_with(
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.HISTORICAL,
        start_datetime=updated_start,
        end_datetime=updated_end,
        units=WeatherUnits.IMPERIAL,
    )
    assert result.start_datetime == updated_start
    assert result.end_datetime == updated_end
    assert result.units == WeatherUnits.IMPERIAL
    assert result.weather_data == {
        "provider": "open-meteo",
        "payload": {"hourly": {"temperature_2m": [18.0]}},
    }
    db_session.add.assert_called_once_with(result)
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once_with(result)


def test_update_weather_query_re_geocodes_when_location_changes() -> None:
    db_session = Mock()
    geocoding_client = Mock()
    weather_client = Mock()

    geocoding_client.geocode.return_value = ResolvedLocation(
        normalized_location="Toronto, Ontario, Canada",
        latitude=Decimal("43.653200"),
        longitude=Decimal("-79.383200"),
    )
    weather_client.fetch_weather.return_value = {
        "current": {"temperature_2m": 21.1},
    }
    original_start = datetime(2024, 4, 1, 9, 0, tzinfo=UTC)
    original_end = datetime(2024, 4, 1, 18, 0, tzinfo=UTC)

    service = WeatherService(
        db_session=db_session,
        geocoding_client=geocoding_client,
        weather_client=weather_client,
    )
    weather_query = WeatherQuery(
        location_input="London, Ontario, Canada",
        normalized_location="London, Ontario, Canada",
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.HISTORICAL,
        start_datetime=original_start,
        end_datetime=original_end,
        units=WeatherUnits.METRIC,
        weather_data={"provider": "open-meteo", "payload": {}},
    )
    payload = WeatherUpdateRequest(
        locationInput="Toronto, Ontario, Canada",
        mode=WeatherMode.CURRENT,
        startDateTime=None,
        endDateTime=None,
    )

    result = service.update_weather_query(weather_query, payload)

    geocoding_client.geocode.assert_called_once_with("Toronto, Ontario, Canada")
    weather_client.fetch_weather.assert_called_once_with(
        latitude=Decimal("43.653200"),
        longitude=Decimal("-79.383200"),
        mode=WeatherMode.CURRENT,
        start_datetime=None,
        end_datetime=None,
        units=WeatherUnits.METRIC,
    )
    assert result.location_input == "Toronto, Ontario, Canada"
    assert result.normalized_location == "Toronto, Ontario, Canada"
    assert result.latitude == Decimal("43.653200")
    assert result.longitude == Decimal("-79.383200")
    assert result.mode == WeatherMode.CURRENT
    assert result.start_datetime is None
    assert result.end_datetime is None
    assert result.weather_data == {
        "provider": "open-meteo",
        "payload": {"current": {"temperature_2m": 21.1}},
    }
    db_session.add.assert_called_once_with(result)
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once_with(result)


def test_update_weather_query_allows_switching_to_current_with_explicit_null_dates() -> None:
    db_session = Mock()
    geocoding_client = Mock()
    weather_client = Mock()
    weather_client.fetch_weather.return_value = {
        "current": {"temperature_2m": 15.5},
    }
    original_start = datetime(2024, 4, 1, 9, 0, tzinfo=UTC)
    original_end = datetime(2024, 4, 1, 18, 0, tzinfo=UTC)

    service = WeatherService(
        db_session=db_session,
        geocoding_client=geocoding_client,
        weather_client=weather_client,
    )
    weather_query = WeatherQuery(
        location_input="London, Ontario, Canada",
        normalized_location="London, Ontario, Canada",
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.HISTORICAL,
        start_datetime=original_start,
        end_datetime=original_end,
        units=WeatherUnits.METRIC,
        weather_data={"provider": "open-meteo", "payload": {}},
    )
    payload = WeatherUpdateRequest(
        mode=WeatherMode.CURRENT,
        startDateTime=None,
        endDateTime=None,
    )

    result = service.update_weather_query(weather_query, payload)

    weather_client.fetch_weather.assert_called_once_with(
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.CURRENT,
        start_datetime=None,
        end_datetime=None,
        units=WeatherUnits.METRIC,
    )
    assert result.mode == WeatherMode.CURRENT
    assert result.start_datetime is None
    assert result.end_datetime is None
    db_session.add.assert_called_once_with(result)
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once_with(result)


def test_update_weather_query_rejects_current_mode_when_existing_dates_are_kept() -> None:
    db_session = Mock()
    geocoding_client = Mock()
    weather_client = Mock()

    service = WeatherService(
        db_session=db_session,
        geocoding_client=geocoding_client,
        weather_client=weather_client,
    )
    original_start = datetime(2024, 4, 1, 9, 0, tzinfo=UTC)
    original_end = datetime(2024, 4, 1, 18, 0, tzinfo=UTC)
    weather_query = WeatherQuery(
        location_input="London, Ontario, Canada",
        normalized_location="London, Ontario, Canada",
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.HISTORICAL,
        start_datetime=original_start,
        end_datetime=original_end,
        units=WeatherUnits.METRIC,
        weather_data={"provider": "open-meteo", "payload": {}},
    )
    payload = WeatherUpdateRequest(mode=WeatherMode.CURRENT)

    with pytest.raises(ValueError, match="current mode does not accept startDateTime or endDateTime."):
        service.update_weather_query(weather_query, payload)

    weather_client.fetch_weather.assert_not_called()
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()


def test_create_weather_query_attaches_requested_live_enrichment() -> None:
    db_session = Mock()
    geocoding_client = Mock()
    weather_client = Mock()
    google_maps_client = Mock()
    youtube_client = Mock()
    pun_client = Mock()

    geocoding_client.geocode.return_value = ResolvedLocation(
        normalized_location="London, Southwestern Ontario, Ontario, Canada",
        latitude=Decimal("42.983675"),
        longitude=Decimal("-81.249607"),
    )
    weather_client.fetch_weather.return_value = {
        "current": {"temperature_2m": 21.2},
    }
    google_maps_client.build_place_embed.return_value = {
        "provider": "google-maps",
        "embedUrl": "https://www.google.com/maps/embed/v1/place?key=test&q=London",
        "query": "London, Southwestern Ontario, Ontario, Canada",
        "latitude": Decimal("42.983675"),
        "longitude": Decimal("-81.249607"),
    }
    youtube_client.search_location_videos.return_value = [
        {
            "provider": "youtube",
            "videoId": "abc123",
            "title": "Walking around London, Ontario",
            "channelTitle": "Example Channel",
            "thumbnailUrl": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
            "embedUrl": "https://www.youtube.com/embed/abc123",
        }
    ]
    pun_client.generate_pun.return_value = {
        "provider": "gemini-flash",
        "text": "London’s forecast is looking reigneously bright.",
    }

    service = WeatherService(
        db_session=db_session,
        geocoding_client=geocoding_client,
        weather_client=weather_client,
        google_maps_client=google_maps_client,
        youtube_client=youtube_client,
        pun_client=pun_client,
    )
    payload = WeatherCreateRequest(
        locationInput="London, Ontario, Canada",
        mode=WeatherMode.CURRENT,
        units=WeatherUnits.METRIC,
        include=[
            WeatherEnrichmentType.MAP,
            WeatherEnrichmentType.YOUTUBE,
            WeatherEnrichmentType.PUN,
        ],
    )

    result = service.create_weather_query(payload)

    assert result.enrichment is not None
    assert result.enrichment.map is not None
    assert result.enrichment.youtube_videos is not None
    assert result.enrichment.pun is not None
    google_maps_client.build_place_embed.assert_called_once()
    youtube_client.search_location_videos.assert_called_once_with(
        normalized_location="London, Southwestern Ontario, Ontario, Canada",
    )
    pun_client.generate_pun.assert_called_once_with(
        normalized_location="London, Southwestern Ontario, Ontario, Canada",
        weather_payload={"current": {"temperature_2m": 21.2}},
    )

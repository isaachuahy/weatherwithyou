from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from weatherwithyou.clients.geocoding import LocationNotFoundError
from weatherwithyou.db import get_db_session
from weatherwithyou.main import app
from weatherwithyou.models.weather_query import WeatherQuery
from weatherwithyou.schemas.weather_schemas import WeatherMode, WeatherUnits


def _sample_weather_query() -> WeatherQuery:
    return WeatherQuery(
        id=uuid4(),
        location_input="London, Ontario, Canada",
        normalized_location="London, Ontario, Canada",
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.HISTORICAL,
        start_datetime=datetime(2024, 4, 1, 9, 0, tzinfo=UTC),
        end_datetime=datetime(2024, 4, 1, 18, 0, tzinfo=UTC),
        units=WeatherUnits.METRIC,
        weather_data={
            "provider": "open-meteo",
            "payload": {
                "hourly": {
                    "time": ["2024-04-01T09:00", "2024-04-01T10:00"],
                    "temperature_2m": [12.3, 13.1],
                }
            },
        },
        created_at=datetime(2024, 4, 1, 12, 0, tzinfo=UTC),
        updated_at=datetime(2024, 4, 1, 12, 0, tzinfo=UTC),
    )


def test_health_check_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_weather_lookup_returns_created_record() -> None:
    mock_session = Mock()
    app.dependency_overrides[get_db_session] = lambda: mock_session
    weather_query = _sample_weather_query()

    with patch(
        "weatherwithyou.api.routes.weather_routes.WeatherService.create_weather_query",
        return_value=weather_query,
    ) as create_weather_query:
        client = TestClient(app)
        response = client.post(
            "/weather",
            json={
                "locationInput": "London, Ontario, Canada",
                "mode": "historical",
                "startDateTime": "2024-04-01T09:00:00Z",
                "endDateTime": "2024-04-01T18:00:00Z",
                "units": "metric",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["locationInput"] == "London, Ontario, Canada"
    assert body["mode"] == "historical"
    assert body["startDateTime"] == "2024-04-01T09:00:00Z"
    assert body["endDateTime"] == "2024-04-01T18:00:00Z"
    assert body["weatherData"]["provider"] == "open-meteo"
    create_weather_query.assert_called_once()


def test_create_weather_lookup_returns_422_for_missing_location_match() -> None:
    mock_session = Mock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with patch(
        "weatherwithyou.api.routes.weather_routes.WeatherService.create_weather_query",
        side_effect=LocationNotFoundError("Could not resolve the provided location."),
    ):
        client = TestClient(app)
        response = client.post(
            "/weather",
            json={
                "locationInput": "Unknown Place",
                "mode": "historical",
                "startDateTime": "2024-04-01T09:00:00Z",
                "endDateTime": "2024-04-01T18:00:00Z",
                "units": "metric",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "error": {
                "code": "LOCATION_NOT_FOUND",
                "message": "Could not resolve the provided location.",
            }
        }
    }


def test_get_weather_lookup_returns_404_when_record_is_missing() -> None:
    mock_session = Mock()
    mock_session.get.return_value = None
    app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(app)

    response = client.get(f"/weather/{uuid4()}")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "error": {
                "code": "LOOKUP_NOT_FOUND",
                "message": "Weather lookup not found.",
            }
        }
    }


def test_delete_weather_lookup_returns_204() -> None:
    mock_session = Mock()
    weather_query = _sample_weather_query()
    mock_session.get.return_value = weather_query
    app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(app)

    response = client.delete(f"/weather/{weather_query.id}")

    app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""
    mock_session.delete.assert_called_once_with(weather_query)
    mock_session.commit.assert_called_once()


def test_update_weather_lookup_returns_422_for_invalid_merged_state() -> None:
    mock_session = Mock()
    weather_query = _sample_weather_query()
    mock_session.get.return_value = weather_query
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with patch(
        "weatherwithyou.api.routes.weather_routes.WeatherService.update_weather_query",
        side_effect=ValueError("current mode does not accept startDateTime or endDateTime."),
    ):
        client = TestClient(app)
        response = client.patch(
            f"/weather/{weather_query.id}",
            json={"mode": "current"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "error": {
                "code": "INVALID_WEATHER_LOOKUP",
                "message": "current mode does not accept startDateTime or endDateTime.",
            }
        }
    }


def test_list_weather_lookups_normalizes_datetime_filters_to_utc() -> None:
    mock_session = Mock()
    weather_query = _sample_weather_query()
    mock_session.scalars.return_value = [weather_query]
    app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(app)

    response = client.get(
        "/weather",
        params={
            "startDateTime": "2024-04-01T05:00:00-04:00",
            "endDateTime": "2024-04-01T14:00:00-04:00",
        },
    )

    app.dependency_overrides.clear()

    query = mock_session.scalars.call_args.args[0]
    filter_values = [criterion.right.value for criterion in query._where_criteria]

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(weather_query.id)
    assert datetime(2024, 4, 1, 9, 0, tzinfo=UTC) in filter_values
    assert datetime(2024, 4, 1, 18, 0, tzinfo=UTC) in filter_values


def test_export_weather_lookups_returns_json_records() -> None:
    mock_session = Mock()
    weather_query = _sample_weather_query()
    mock_session.scalars.return_value = [weather_query]
    app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(app)

    response = client.get("/weather/export")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["startDateTime"] == "2024-04-01T09:00:00Z"
    assert response.json()[0]["endDateTime"] == "2024-04-01T18:00:00Z"


def test_export_weather_lookups_returns_csv_rows() -> None:
    mock_session = Mock()
    weather_query = _sample_weather_query()
    mock_session.scalars.return_value = [weather_query]
    app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(app)

    response = client.get("/weather/export?format=csv")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=\"weather-lookups.csv\"" == response.headers["content-disposition"]
    assert "start_datetime,end_datetime" in response.text
    assert "2024-04-01 09:00:00+00:00" in response.text
    assert "weather_data_provider" in response.text
    assert "weather_data_payload_hourly_time" in response.text
    assert "weather_data_payload_hourly_temperature_2m" in response.text
    assert "open-meteo" in response.text
    assert '"[""2024-04-01T09:00"", ""2024-04-01T10:00""]"' in response.text


def test_get_weather_lookup_returns_requested_enrichment() -> None:
    mock_session = Mock()
    weather_query = _sample_weather_query()
    weather_query.enrichment = {
        "map": {
            "provider": "google-maps",
            "embedUrl": "https://www.google.com/maps/embed/v1/place?key=test&q=London",
            "query": "London, Ontario, Canada",
            "latitude": "42.983390",
            "longitude": "-81.233040",
        },
        "youtubeVideos": [
            {
                "provider": "youtube",
                "videoId": "abc123",
                "title": "Walking around London, Ontario",
                "channelTitle": "Example Channel",
                "thumbnailUrl": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
                "embedUrl": "https://www.youtube.com/embed/abc123",
            }
        ],
        "pun": {
            "provider": "gemini-flash",
            "text": "London’s forecast is looking reigneously bright.",
        },
    }
    mock_session.get.return_value = weather_query
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with patch(
        "weatherwithyou.api.routes.weather_routes.WeatherService.attach_enrichment",
        return_value=weather_query,
    ) as attach_enrichment:
        client = TestClient(app)
        response = client.get(
            f"/weather/{weather_query.id}",
            params=[("include", "map"), ("include", "youtube"), ("include", "pun")],
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["enrichment"]["map"]["provider"] == "google-maps"
    assert body["enrichment"]["youtubeVideos"][0]["videoId"] == "abc123"
    assert body["enrichment"]["pun"]["provider"] == "gemini-flash"
    attach_enrichment.assert_called_once()

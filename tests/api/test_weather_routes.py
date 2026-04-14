from datetime import date, datetime, timezone
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
        start_date=date(2024, 4, 1),
        end_date=date(2024, 4, 2),
        units=WeatherUnits.METRIC,
        weather_data={"provider": "open-meteo", "payload": {"daily": {}}},
        created_at=datetime(2024, 4, 1, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2024, 4, 1, 12, 0, tzinfo=timezone.utc),
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
                "startDate": "2024-04-01",
                "endDate": "2024-04-02",
                "units": "metric",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["locationInput"] == "London, Ontario, Canada"
    assert body["mode"] == "historical"
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
                "startDate": "2024-04-01",
                "endDate": "2024-04-02",
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

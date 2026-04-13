from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from weatherwithyou.clients.geocoding import ResolvedLocation
from weatherwithyou.models.weather_query import WeatherQuery
from weatherwithyou.schemas.weather_schemas import (
    WeatherCreateRequest,
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
        "daily": {"temperature_2m_max": [12.3]},
    }

    service = WeatherService(
        db_session=db_session,
        geocoding_client=geocoding_client,
        weather_client=weather_client,
    )
    payload = WeatherCreateRequest(
        locationInput="London, Ontario, Canada",
        mode=WeatherMode.HISTORICAL,
        startDate=date(2024, 4, 1),
        endDate=date(2024, 4, 2),
        units=WeatherUnits.METRIC,
    )

    result = service.create_weather_query(payload)

    assert isinstance(result, WeatherQuery)
    assert result.location_input == "London, Ontario, Canada"
    assert result.normalized_location == "London, Ontario, Canada"
    assert result.latitude == Decimal("42.983390")
    assert result.longitude == Decimal("-81.233040")
    assert result.mode == WeatherMode.HISTORICAL
    assert result.start_date == date(2024, 4, 1)
    assert result.end_date == date(2024, 4, 2)
    assert result.units == WeatherUnits.METRIC
    assert result.weather_data == {
        "provider": "open-meteo",
        "payload": {"daily": {"temperature_2m_max": [12.3]}},
    }

    geocoding_client.geocode.assert_called_once_with("London, Ontario, Canada")
    weather_client.fetch_weather.assert_called_once_with(
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.HISTORICAL,
        start_date=date(2024, 4, 1),
        end_date=date(2024, 4, 2),
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
        "daily": {"temperature_2m_max": [18.0]},
    }

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
        start_date=date(2024, 4, 1),
        end_date=date(2024, 4, 2),
        units=WeatherUnits.METRIC,
        weather_data={"provider": "open-meteo", "payload": {}},
    )
    payload = WeatherUpdateRequest(
        startDate=date(2024, 4, 3),
        endDate=date(2024, 4, 4),
        units=WeatherUnits.IMPERIAL,
    )

    result = service.update_weather_query(weather_query, payload)

    geocoding_client.geocode.assert_not_called()
    weather_client.fetch_weather.assert_called_once_with(
        latitude=Decimal("42.983390"),
        longitude=Decimal("-81.233040"),
        mode=WeatherMode.HISTORICAL,
        start_date=date(2024, 4, 3),
        end_date=date(2024, 4, 4),
        units=WeatherUnits.IMPERIAL,
    )
    assert result.start_date == date(2024, 4, 3)
    assert result.end_date == date(2024, 4, 4)
    assert result.units == WeatherUnits.IMPERIAL
    assert result.weather_data == {
        "provider": "open-meteo",
        "payload": {"daily": {"temperature_2m_max": [18.0]}},
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
        start_date=date(2024, 4, 1),
        end_date=date(2024, 4, 2),
        units=WeatherUnits.METRIC,
        weather_data={"provider": "open-meteo", "payload": {}},
    )
    payload = WeatherUpdateRequest(
        locationInput="Toronto, Ontario, Canada",
        mode=WeatherMode.CURRENT,
    )

    result = service.update_weather_query(weather_query, payload)

    geocoding_client.geocode.assert_called_once_with("Toronto, Ontario, Canada")
    weather_client.fetch_weather.assert_called_once_with(
        latitude=Decimal("43.653200"),
        longitude=Decimal("-79.383200"),
        mode=WeatherMode.CURRENT,
        start_date=date(2024, 4, 1),
        end_date=date(2024, 4, 2),
        units=WeatherUnits.METRIC,
    )
    assert result.location_input == "Toronto, Ontario, Canada"
    assert result.normalized_location == "Toronto, Ontario, Canada"
    assert result.latitude == Decimal("43.653200")
    assert result.longitude == Decimal("-79.383200")
    assert result.mode == WeatherMode.CURRENT
    assert result.weather_data == {
        "provider": "open-meteo",
        "payload": {"current": {"temperature_2m": 21.1}},
    }
    db_session.add.assert_called_once_with(result)
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once_with(result)

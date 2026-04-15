import csv
import json
from datetime import UTC, datetime
from io import StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from weatherwithyou.clients.geocoding import GeocodingProviderError, LocationNotFoundError
from weatherwithyou.clients.weather_client import WeatherProviderError
from weatherwithyou.db import get_db_session
from weatherwithyou.models.weather_query import WeatherQuery
from weatherwithyou.schemas.weather_schemas import (
    WeatherCreateRequest,
    WeatherEnrichmentType,
    WeatherMode,
    WeatherQueryResponse,
    WeatherUpdateRequest,
)
from weatherwithyou.services.weather_service import WeatherService


router = APIRouter(prefix="/weather", tags=["weather"]) 


def _weather_service(db_session: Session) -> WeatherService:
    """Create a request-scoped weather service."""

    return WeatherService(db_session=db_session)


def _get_weather_query_or_404(db_session: Session, weather_query_id: UUID) -> WeatherQuery:
    """Load a saved weather query or raise a 404-style API error."""

    weather_query = db_session.get(WeatherQuery, weather_query_id)
    if weather_query is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "LOOKUP_NOT_FOUND",
                    "message": "Weather lookup not found.",
                }
            },
        )
    return weather_query


def _normalize_query_datetime(value: datetime | None) -> datetime | None:
    """Normalize API datetime filters to UTC before comparing against stored rows."""

    if value is None:
        return None

    return value.astimezone(UTC)


def _raise_weather_api_error(exc: Exception) -> None:
    """Translate known service/provider failures into API-shaped HTTP errors."""

    if isinstance(exc, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": {
                    "code": "INVALID_WEATHER_LOOKUP",
                    "message": str(exc),
                }
            },
        ) from exc

    if isinstance(exc, LocationNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": {
                    "code": "LOCATION_NOT_FOUND",
                    "message": str(exc),
                }
            },
        ) from exc

    if isinstance(exc, GeocodingProviderError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "GEOCODING_PROVIDER_ERROR",
                    "message": "Failed to resolve the provided location.",
                }
            },
        ) from exc

    if isinstance(exc, WeatherProviderError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "WEATHER_PROVIDER_ERROR",
                    "message": "Failed to retrieve weather data.",
                }
            },
        ) from exc

    raise exc


def _flatten_export_value(prefix: str, value: object) -> dict[str, object]:
    """Flatten nested export data into CSV-friendly columns.

    Weather payloads can contain nested objects and arrays from upstream providers.
    Flattening them here keeps CSV export readable without changing the durable
    shape stored in the database or the JSON API contract.
    """

    if isinstance(value, dict):
        flattened: dict[str, object] = {}
        for key, nested_value in value.items():
            nested_prefix = f"{prefix}_{key}" if prefix else str(key)
            flattened.update(_flatten_export_value(nested_prefix, nested_value))
        return flattened

    if isinstance(value, list):
        return {prefix: json.dumps(value)}

    return {prefix: value}


@router.post("", response_model=WeatherQueryResponse, status_code=status.HTTP_201_CREATED)
def create_weather_lookup(
    payload: WeatherCreateRequest,
    db_session: Session = Depends(get_db_session),
) -> WeatherQuery:
    service = _weather_service(db_session)

    try:
        return service.create_weather_query(payload)
    except (
        ValueError,
        LocationNotFoundError,
        GeocodingProviderError,
        WeatherProviderError,
    ) as exc:
        _raise_weather_api_error(exc)


@router.get("", response_model=list[WeatherQueryResponse])
def list_weather_lookups(
    location: str | None = None,
    mode: WeatherMode | None = None,
    start_datetime: datetime | None = Query(default=None, alias="startDateTime"),
    end_datetime: datetime | None = Query(default=None, alias="endDateTime"),
    include: list[WeatherEnrichmentType] = Query(default_factory=list),
    db_session: Session = Depends(get_db_session),
) -> list[WeatherQuery]:
    start_datetime = _normalize_query_datetime(start_datetime)
    end_datetime = _normalize_query_datetime(end_datetime)
    service = _weather_service(db_session)

    query = select(WeatherQuery).order_by(WeatherQuery.created_at.desc())

    if location:
        query = query.where(WeatherQuery.location_input.ilike(f"%{location}%"))
    if mode:
        query = query.where(WeatherQuery.mode == mode)
    if start_datetime is not None:
        query = query.where(WeatherQuery.start_datetime == start_datetime)
    if end_datetime is not None:
        query = query.where(WeatherQuery.end_datetime == end_datetime)

    return [
        service.attach_enrichment(weather_query, include)
        for weather_query in db_session.scalars(query)
    ]


@router.get("/export", response_model=None)
def export_weather_lookups(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db_session: Session = Depends(get_db_session),
) -> Response | list[WeatherQueryResponse]:
    weather_queries = list(
        db_session.scalars(select(WeatherQuery).order_by(WeatherQuery.created_at.desc()))
    )

    if format == "json":
        return [
            WeatherQueryResponse.model_validate(weather_query)
            for weather_query in weather_queries
        ]

    csv_rows = []
    for weather_query in weather_queries:
        row = {
            "id": weather_query.id,
            "location_input": weather_query.location_input,
            "normalized_location": weather_query.normalized_location,
            "latitude": weather_query.latitude,
            "longitude": weather_query.longitude,
            "mode": weather_query.mode,
            "start_datetime": weather_query.start_datetime,
            "end_datetime": weather_query.end_datetime,
            "units": weather_query.units,
            "created_at": weather_query.created_at,
            "updated_at": weather_query.updated_at,
        }
        row.update(_flatten_export_value("weather_data", weather_query.weather_data))
        csv_rows.append(row)

    fieldnames = []
    for row in csv_rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
    )
    writer.writeheader()

    for row in csv_rows:
        writer.writerow(row)

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="weather-lookups.csv"'},
    )


@router.get("/{weather_query_id}", response_model=WeatherQueryResponse)
def get_weather_lookup(
    weather_query_id: UUID,
    include: list[WeatherEnrichmentType] = Query(default_factory=list),
    db_session: Session = Depends(get_db_session),
) -> WeatherQuery:
    service = _weather_service(db_session)
    weather_query = _get_weather_query_or_404(db_session, weather_query_id)
    return service.attach_enrichment(weather_query, include)


@router.patch("/{weather_query_id}", response_model=WeatherQueryResponse)
def update_weather_lookup(
    weather_query_id: UUID,
    payload: WeatherUpdateRequest,
    db_session: Session = Depends(get_db_session),
) -> WeatherQuery:
    weather_query = _get_weather_query_or_404(db_session, weather_query_id)
    service = _weather_service(db_session)

    try:
        return service.update_weather_query(weather_query, payload)
    except (
        ValueError,
        LocationNotFoundError,
        GeocodingProviderError,
        WeatherProviderError,
    ) as exc:
        _raise_weather_api_error(exc)


@router.delete("/{weather_query_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_weather_lookup(
    weather_query_id: UUID,
    db_session: Session = Depends(get_db_session),
) -> Response:
    weather_query = _get_weather_query_or_404(db_session, weather_query_id)
    db_session.delete(weather_query)
    db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

import csv
import json
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
    WeatherMode,
    WeatherQueryResponse,
    WeatherUpdateRequest,
)
from weatherwithyou.services.weather_service import WeatherService


router = APIRouter(prefix="/weather", tags=["weather"]) 


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


def _service_for(db_session: Session) -> WeatherService:
    """Create a request-scoped weather service."""

    return WeatherService(db_session=db_session)


@router.post("", response_model=WeatherQueryResponse, status_code=status.HTTP_201_CREATED)
def create_weather_lookup(
    payload: WeatherCreateRequest,
    db_session: Session = Depends(get_db_session),
) -> WeatherQuery:
    service = _service_for(db_session)

    try:
        return service.create_weather_query(payload)
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "LOCATION_NOT_FOUND",
                    "message": str(exc),
                }
            },
        ) from exc
    except GeocodingProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "GEOCODING_PROVIDER_ERROR",
                    "message": "Failed to resolve the provided location.",
                }
            },
        ) from exc
    except WeatherProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "WEATHER_PROVIDER_ERROR",
                    "message": "Failed to retrieve weather data.",
                }
            },
        ) from exc


@router.get("", response_model=list[WeatherQueryResponse])
def list_weather_lookups(
    location: str | None = None,
    mode: WeatherMode | None = None,
    start_date: str | None = Query(default=None, alias="startDate"),
    end_date: str | None = Query(default=None, alias="endDate"),
    db_session: Session = Depends(get_db_session),
) -> list[WeatherQuery]:
    query = select(WeatherQuery).order_by(WeatherQuery.created_at.desc())

    if location:
        query = query.where(WeatherQuery.location_input.ilike(f"%{location}%"))
    if mode:
        query = query.where(WeatherQuery.mode == mode)
    if start_date:
        query = query.where(WeatherQuery.start_date == start_date)
    if end_date:
        query = query.where(WeatherQuery.end_date == end_date)

    return list(db_session.scalars(query))


@router.get("/{weather_query_id}", response_model=WeatherQueryResponse)
def get_weather_lookup(
    weather_query_id: UUID,
    db_session: Session = Depends(get_db_session),
) -> WeatherQuery:
    return _get_weather_query_or_404(db_session, weather_query_id)


@router.patch("/{weather_query_id}", response_model=WeatherQueryResponse)
def update_weather_lookup(
    weather_query_id: UUID,
    payload: WeatherUpdateRequest,
    db_session: Session = Depends(get_db_session),
) -> WeatherQuery:
    weather_query = _get_weather_query_or_404(db_session, weather_query_id)
    service = _service_for(db_session)

    try:
        return service.update_weather_query(weather_query, payload)
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, # 422 is appropriate here since the client provided a location that doesn't exist, which is a validation issue with the input rather than a server error.
            detail={
                "error": {
                    "code": "LOCATION_NOT_FOUND",
                    "message": str(exc),
                }
            },
        ) from exc
    except GeocodingProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, # 502 is appropriate here since the error occurred while trying to communicate with an external geocoding provider, which is a server-side issue outside of the client's control.
            detail={
                "error": {
                    "code": "GEOCODING_PROVIDER_ERROR",
                    "message": "Failed to resolve the provided location.",
                }
            },
        ) from exc
    except WeatherProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "WEATHER_PROVIDER_ERROR",
                    "message": "Failed to retrieve weather data.",
                }
            },
        ) from exc

@router.delete("/{weather_query_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_weather_lookup(
    weather_query_id: UUID,
    db_session: Session = Depends(get_db_session),
) -> Response:
    weather_query = _get_weather_query_or_404(db_session, weather_query_id)
    db_session.delete(weather_query)
    db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/export")
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

    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "id",
            "location_input",
            "normalized_location",
            "latitude",
            "longitude",
            "mode",
            "start_date",
            "end_date",
            "units",
            "weather_data",
            "created_at",
            "updated_at",
        ],
    )
    writer.writeheader()

    for weather_query in weather_queries:
        writer.writerow(
            {
                "id": weather_query.id,
                "location_input": weather_query.location_input,
                "normalized_location": weather_query.normalized_location,
                "latitude": weather_query.latitude,
                "longitude": weather_query.longitude,
                "mode": weather_query.mode,
                "start_date": weather_query.start_date,
                "end_date": weather_query.end_date,
                "units": weather_query.units,
                "weather_data": json.dumps(weather_query.weather_data),
                "created_at": weather_query.created_at,
                "updated_at": weather_query.updated_at,
            }
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="weather-lookups.csv"'},
    )

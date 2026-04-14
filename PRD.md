# PRD — Weather With You

## Objective

Build a simple backend weather app that:

* accepts a user location input
* validates and resolves that location
* fetches historical, current, and forecast weather data from external APIs
* supports hourly weather lookups with datetime ranges where applicable
* stores the request and retrieved result in a database
* supports CRUD on saved weather lookups
* supports exporting saved data

## Stack

* Python 3.12
* FastAPI
* PostgreSQL
* SQLAlchemy 2.0
* Alembic
* Pydantic v2
* `httpx`

## Scope

### In scope

* location input: city, postal/ZIP code, landmark, coordinates
* geocoding with Nominatim
* weather retrieval with Open-Meteo
* support for historical, current, and forecast weather lookups
* hourly weather retrieval for historical and forecast modes
* persistence in PostgreSQL
* CRUD on saved weather lookups
* export as JSON and CSV
* clean error handling

### Out of scope

* authentication / RBAC
* frontend
* caching
* microservices
* YouTube integration for MVP

## CRUD interpretation

CRUD applies to saved weather lookup records.

* **Create**: save a new weather lookup
* **Read**: fetch saved lookups
* **Update**: modify a saved lookup and re-fetch weather
* **Delete**: remove a saved lookup from the database

## Core flow

1. User submits `locationInput`, `mode`, optional `startDateTime`, optional `endDateTime`, `units`
2. Backend validates the request
3. Backend geocodes the location using Nominatim
4. Backend fetches weather from Open-Meteo
5. Backend stores the lookup and returned weather data in PostgreSQL
6. Backend returns the saved record

## Database design

Use one table for simplicity.

### Table: `weather_queries`

* `id` UUID primary key
* `location_input` text not null
* `normalized_location` text not null
* `latitude` numeric not null
* `longitude` numeric not null
* `mode` text not null
* `start_datetime` timestamptz null
* `end_datetime` timestamptz null
* `units` text not null
* `weather_data` JSONB not null
* `created_at` timestamptz default now()
* `updated_at` timestamptz default now()

## Persistence rules

* each new lookup creates a new row
* different datetime range = different row
* update modifies an existing row and replaces stored weather data
* delete removes the row

## API endpoints

### `POST /weather`

Create a weather lookup.

Request body:

```json
{
  "locationInput": "London, Ontario, Canada",
  "mode": "historical",
  "startDateTime": "2017-04-03T09:00:00-04:00",
  "endDateTime": "2017-04-03T18:00:00-04:00",
  "units": "metric"
}
```

Behavior:

* validate input
* geocode location
* fetch weather
* save row
* return saved record

Mode rules:

* `historical` requires `startDateTime` and `endDateTime`
* `current` does not require `startDateTime` or `endDateTime`
* `forecast` requires `startDateTime` and `endDateTime`
* `historical` and `forecast` return hourly weather data within the requested datetime window

### `GET /weather`

Return all saved lookups.

Optional query params:

* `location`
* `mode`
* `startDateTime`
* `endDateTime`

Response behavior:

* return full saved records, including full `weather_data`, for MVP simplicity

### `GET /weather/{id}`

Return one saved lookup.

### `PATCH /weather/{id}`

Allowed fields:

* `locationInput`
* `mode`
* `startDateTime`
* `endDateTime`
* `units`

Behavior:

* validate updated input
* re-geocode if location changed
* re-fetch weather
* replace stored weather data

### `DELETE /weather/{id}`

Delete a saved lookup.

### `GET /weather/export?format=json|csv`

Export saved lookups.

## Validation rules

### Location

* must not be empty
* if coordinates are provided, validate numeric bounds
* geocoder must return a valid match

### Datetimes

* accept timezone-aware ISO 8601 datetime strings
* reject naive datetimes without a timezone offset
* if both datetimes are provided, `startDateTime <= endDateTime`
* `historical` requires `startDateTime` and `endDateTime`
* `current` does not require datetimes
* `forecast` requires `startDateTime` and `endDateTime`
* reject datetime ranges unsupported by the weather provider for the selected mode
* normalize stored datetimes to UTC

### Mode

Allowed values:

* `historical`
* `current`
* `forecast`

### Units

Allowed values:

* `metric`
* `imperial`

## Error handling

Do not expose raw provider/internal errors directly to the user.

Return controlled API errors like:

```json
{
  "error": {
    "code": "LOCATION_NOT_FOUND",
    "message": "Could not resolve the provided location."
  }
}
```

Examples:

* invalid input → 400
* lookup not found → 404
* location not found → 422
* external API failure → 502

## Implementation notes

* keep the app as a modular monolith
* keep weather data in `weather_data` JSONB instead of over-normalizing
* use Pydantic for request/response validation
* use FastAPI dependencies for DB session management
* use `httpx` for external API calls
* use Alembic for schema migration
* prioritize clarity and working functionality over architectural complexity
* use a stable API response wrapper while preserving relatively unprocessed provider data inside `weather_data`
* use the first valid Nominatim match for MVP and store its display name as `normalized_location`
* store hourly lookup windows as timezone-aware datetimes, not dates

## Response shape

Responses should use a stable application-level wrapper around saved lookup records.

Example shape:

```json
{
  "id": "uuid",
  "locationInput": "London, Ontario, Canada",
  "normalizedLocation": "London, Ontario, Canada",
  "latitude": 42.98339,
  "longitude": -81.23304,
  "mode": "current",
  "startDateTime": null,
  "endDateTime": null,
  "units": "metric",
  "weatherData": {
    "provider": "open-meteo",
    "payload": {}
  },
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
```

Notes:

* response fields should remain stable even if provider payloads evolve
* `weatherData` should preserve provider data with minimal transformation for MVP

## Export shape

* JSON export should return saved records in the same stable wrapper shape used by the API
* CSV export should use flat metadata columns and serialize `weather_data` as JSON text in a single column
* CSV metadata columns should use `start_datetime` and `end_datetime`

## Acceptance criteria

* user can submit a location for current lookups and a location plus datetime range for historical and forecast lookups
* backend resolves the location correctly
* backend fetches and stores weather data for each supported mode
* backend supports hourly weather windows for historical and forecast lookups
* saved records can be read, updated, and deleted
* export works in JSON and CSV
* errors are handled cleanly

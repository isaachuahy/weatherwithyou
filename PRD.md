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
* optional live response enrichment for map, YouTube videos, and a short LLM-generated pun
* clean error handling

### Out of scope

* authentication / RBAC
* frontend
* caching
* microservices
* durable storage of map, YouTube, or pun enrichment

## CRUD interpretation

CRUD applies to saved weather lookup records.

* **Create**: save a new weather lookup
* **Read**: fetch saved lookups
* **Update**: modify a saved lookup and re-fetch weather
* **Delete**: remove a saved lookup from the database

## Core flow

1. User submits `locationInput`, `mode`, optional `startDateTime`, optional `endDateTime`, `units`, and optional enrichment preferences
2. Backend validates the request
3. Backend geocodes the location using Nominatim
4. Backend fetches weather from Open-Meteo
5. Backend stores the lookup and returned weather data in PostgreSQL
6. Backend may fetch optional live enrichment tied to the resolved location
7. Backend returns the saved record

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

Optional enrichment should not be added to the durable weather table by default.

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
  "units": "metric",
  "include": ["map", "youtube", "pun"]
}
```

Behavior:

* validate input
* geocode location
* fetch weather
* save row
* optionally fetch live enrichment for the resolved location
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
* optional `include`

Response behavior:

* return full saved records, including full `weather_data`, for MVP simplicity
* if `include` is requested, enrich the response live without mutating the persisted weather row

### `GET /weather/{id}`

Return one saved lookup.

### `PATCH /weather/{id}`

Allowed fields:

* `locationInput`
* `mode`
* `startDateTime`
* `endDateTime`
* `units`
* optional `include`

Behavior:

* validate updated input
* re-geocode if location changed
* re-fetch weather
* replace stored weather data
* optionally fetch live enrichment for the updated resolved location

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

### Enrichment

Allowed values for `include`:

* `map`
* `youtube`
* `pun`

Rules:

* enrichment is optional
* enrichment should be fetched live at request time
* enrichment failures should not block weather persistence
* enrichment should not replace canonical weather fields
* enrichment should remain lightweight and weather-adjacent rather than turning the product into a city guide
* `pun` should be generated from a lightweight prompt using the resolved location and weather context

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

* invalid input → 422
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
* treat maps, YouTube videos, and puns as live response enrichment instead of durable weather data

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
  "enrichment": {
    "map": {
      "provider": "google-maps",
      "embedUrl": "https://www.google.com/maps/embed/v1/place?...",
      "query": "London, Southwestern Ontario, Ontario, Canada",
      "latitude": 42.98339,
      "longitude": -81.23304
    },
    "youtubeVideos": [
      {
        "provider": "youtube",
        "videoId": "abc123",
        "title": "Walking around London, Ontario",
        "channelTitle": "Example Channel",
        "thumbnailUrl": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
        "embedUrl": "https://www.youtube.com/embed/abc123"
      }
    ],
    "pun": {
      "provider": "gemini-flash",
      "text": "London’s forecast is so bright, it’s practically a royal-tea of sunshine."
    }
  },
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
```

Notes:

* response fields should remain stable even if provider payloads evolve
* `weatherData` should preserve provider data with minimal transformation for MVP
* `enrichment` should be optional and safe to omit
* `enrichment` should be fetched live rather than persisted by default

## Export shape

* JSON export should return saved records in the same stable wrapper shape used by the API
* CSV export should use flat metadata columns and serialize `weather_data` as JSON text in a single column
* CSV metadata columns should use `start_datetime` and `end_datetime`
* live enrichment should be excluded from exports by default

## Acceptance criteria

* user can submit a location for current lookups and a location plus datetime range for historical and forecast lookups
* backend resolves the location correctly
* backend fetches and stores weather data for each supported mode
* backend supports hourly weather windows for historical and forecast lookups
* saved records can be read, updated, and deleted
* export works in JSON and CSV
* optional map, YouTube, and pun enrichment can be returned live for a resolved location without changing the persisted weather row
* errors are handled cleanly

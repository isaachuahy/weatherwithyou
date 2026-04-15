# Weather With You

Weather app built with a FastAPI backend and a React/Vite frontend.

Single-user MVP for now. Saved lookups are durable, but there is no authentication, user ownership, or multi-user partitioning yet.

The app supports:

* current weather lookups by location
* historical and forecast weather lookups by location plus datetime window
* hourly weather data for historical and forecast modes
* optional live response enrichment for map data, YouTube videos, and a short LLM-generated pun via `include`
* CSV export and saved-data delete/clear actions from the frontend

`current` mode does not use `startDateTime` or `endDateTime`. Historical and forecast modes do.
Datetime inputs must be timezone-aware, and stored lookup windows are normalized to UTC.
Optional enrichment is live-only and is not persisted as part of the saved weather row by default.
Enrichment requires the relevant Google Maps, YouTube, and Gemini settings in `.env`.

## Quickstart

1. Create a virtual environment:

```bash
python3 -m venv .venv
```

2. Activate it:

```bash
source .venv/bin/activate
```

3. Install the project and development dependencies:

```bash
pip install -e ".[dev]"
```

4. Copy the example environment file:

```bash
cp .env.example .env
```

5. Create a PostgreSQL database named `weatherwithyou`, or update `DATABASE_URL` in `.env` to point at your database.

6. Run the initial migration:

```bash
alembic upgrade head
```

7. Start the API:

```bash
uvicorn weatherwithyou.main:app --reload
```

Docs will be available at `/docs`.

8. In a second terminal, install and run the frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://127.0.0.1:5173/`.

During local development, Vite proxies `/weather` and `/health` to the backend at `http://127.0.0.1:8000`.

## Frontend

The frontend lives in `frontend/` and is built with React + Vite.

It supports flexible location search, browser current-location lookup, current weather, a 5-day forecast, live map/video/pun enrichment, CSV export, clearing the current view, deleting displayed saved lookup rows, and clearing all saved weather rows.

## Common commands

Run tests:

```bash
pytest
```

Check the current migration revision:

```bash
alembic current
```

Create a new migration after a schema change:

```bash
alembic revision -m "describe the change"
```

Apply the latest migration:

```bash
alembic upgrade head
```

Run the frontend dev server:

```bash
cd frontend
npm run dev
```

Out of scope for this MVP: authentication, RBAC, caching, microservices, multi-user data ownership, and durable storage of enrichment data.

# Weather With You

Backend weather API built with FastAPI, SQLAlchemy, and PostgreSQL.

Single-user MVP for now. Saved lookups are durable, but there is no authentication, user ownership, or multi-user partitioning yet.

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

Out of scope for this MVP: authentication, RBAC, caching, microservices, and multi-user data ownership.

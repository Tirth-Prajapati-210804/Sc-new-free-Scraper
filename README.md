# Flight Harvester / Scraper-v4

Flight Harvester is a full-stack flight-price collection system with a FastAPI backend, a React + Vite frontend, and PostgreSQL persistence. It supports JWT authentication, scheduled collection, manual collection triggers, historical price views, logs, Excel export, round-trip groups, and multi-city groups.

## Stack

Backend: FastAPI, SQLAlchemy 2.x async, Alembic, APScheduler.
Frontend: React, TypeScript, Vite, Tailwind, React Query.
Storage: PostgreSQL.
Deployment: Render backend, Vercel frontend, Supabase Postgres.

## Repository layout

```text
flight-harvester/
|-- backend/
|   |-- app/
|   |-- alembic/
|   |-- tests/
|   |-- Dockerfile
|   `-- pyproject.toml
|-- frontend/
|   |-- src/
|   |-- e2e/
|   |-- Dockerfile
|   `-- package.json
|-- .github/workflows/ci.yml
|-- docker-compose.yml
`-- render.yaml
```

## Local setup

### Backend

```bash
cd backend
cp .env.example .env
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

The backend requires PostgreSQL before startup. For local development, either run your own Postgres instance on `localhost:5432` or start the Compose database service first:

```bash
docker compose up -d db
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend expects `VITE_API_BASE_URL` to point at the backend in local development.

## Required environment variables

### Backend

`DATABASE_URL` - must use `postgresql+asyncpg://...` and include `sslmode=require` for Supabase.

`JWT_SECRET_KEY` - at least 32 characters.

`ADMIN_EMAIL` / `ADMIN_PASSWORD` - bootstrap admin account.

`SEARCHAPI_KEY` - enables the real provider. Leave empty only for demo mode.

`DEMO_MODE` - set `true` for fake/demo data.

`CORS_ORIGINS` - explicit allowed browser origins.

`ALLOWED_HOSTS` - trusted host allow-list.

`SCHEDULER_ENABLED`, `SCHEDULER_INTERVAL_MINUTES` - collection cadence.

`SCRAPE_BATCH_SIZE`, `SCRAPE_DELAY_SECONDS`, `PROVIDER_TIMEOUT_SECONDS`, `PROVIDER_MAX_RETRIES`, `PROVIDER_CONCURRENCY_LIMIT`, `PROVIDER_MIN_DELAY_SECONDS` - collection tuning.

`LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS`, `SCRAPE_RATE_LIMIT_ATTEMPTS`, `SCRAPE_RATE_LIMIT_WINDOW_SECONDS` - rate limits.

`SENTRY_DSN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - optional monitoring hooks.

### Frontend

`VITE_API_BASE_URL` - backend base URL for local development or for the Vercel frontend, for example `https://flight-harvester-backend.onrender.com`.

## Production deployment

### Render backend

Deploy the backend as a Docker service using `render.yaml`.

Set these required Render environment variables:

- `DATABASE_URL` = your Supabase Postgres URL using the `postgresql+asyncpg://` scheme and `sslmode=require`
- `JWT_SECRET_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `SEARCHAPI_KEY`
- `CORS_ORIGINS` = your Vercel production URL plus any preview URLs you want to allow

Recommended backend values:

- `DEMO_MODE=false`
- `SCHEDULER_ENABLED=true`
- `ALLOWED_HOSTS=*.onrender.com,*.vercel.app`

### Vercel frontend

Deploy the `frontend` directory to Vercel.

Set this required Vercel environment variable:

- `VITE_API_BASE_URL` = your public Render backend URL, for example `https://flight-harvester-backend.onrender.com`

Make sure Vercel uses:

- Framework preset: `Vite`
- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`

### Supabase database

Create a Supabase Postgres project and copy the connection string into Render as `DATABASE_URL`.

Use this shape:

```text
postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require
```

After the backend is deployed, run Alembic migrations against the same database before first client use.

## Health checks

`GET /health` - overall health summary.

`GET /health/live` - liveness.

`GET /health/ready` - readiness for deployment checks.

## Client handoff notes

The API is protected with JWT bearer tokens, login and scrape trigger rate limiting, and redacted structured logging. Admins and users have the same tracker authority; only the user-management section is admin-only. The scheduler uses a PostgreSQL advisory lock to prevent duplicate collection runs, fully scraped groups are skipped automatically, and multi-city special legs are collected end to end.

## Testing

Backend unit tests:

```bash
cd backend
python -m pytest tests/test_airline_codes.py tests/test_auth_schema.py tests/test_config.py tests/test_route_group_schema.py tests/test_services
```

Frontend build:

```bash
cd frontend
npm run build
```

Full verification used for client handoff:

```bash
cd backend
python -m pytest

cd ../frontend
npm run lint
npm run test:run
npm run build
```

## Troubleshooting

If login fails, verify `JWT_SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`.

If the backend fails on startup with a PostgreSQL connection error, confirm a database is running on `localhost:5432` for host-based development, or start Docker Desktop and run `docker compose up -d db`.

If collection is disabled or provider status looks degraded, confirm `SEARCHAPI_KEY` is set and that your SearchApi.io quota is not exhausted, or use `DEMO_MODE=true`.

If the frontend cannot reach the API, verify `VITE_API_BASE_URL`, `CORS_ORIGINS`, and the deployed Render backend URL.

If Render health checks fail, confirm the backend can connect to Supabase with `sslmode=require` and that `SCHEDULER_ENABLED` is true.

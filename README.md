# Flight Harvester / Scraper-v4

Flight Harvester is a full-stack flight-price collection system with a FastAPI backend, a React + Vite frontend, and PostgreSQL persistence. It supports JWT authentication, scheduled collection, manual collection triggers, historical price views, logs, Excel export, round-trip groups, and multi-city groups.

## Stack

Backend: FastAPI, SQLAlchemy 2.x async, Alembic, APScheduler.
Frontend: React, TypeScript, Vite, Tailwind, React Query.
Storage: PostgreSQL.
Deployment: Docker and Render.

## Repository layout

```text
flight-harvester/
├─ backend/
│  ├─ app/
│  ├─ alembic/
│  ├─ tests/
│  ├─ Dockerfile
│  └─ pyproject.toml
├─ frontend/
│  ├─ src/
│  ├─ e2e/
│  ├─ Dockerfile
│  └─ package.json
├─ .github/workflows/ci.yml
├─ docker-compose.yml
└─ render.yaml
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

The backend requires PostgreSQL before startup. For local development, either
run your own Postgres instance on `localhost:5432` or start the Compose
database service first:

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

The frontend expects `VITE_API_BASE_URL` to point at the backend in local development. In same-origin production deployments, it can be left empty.

## Required environment variables

### Backend

`DATABASE_URL` — must use `postgresql+asyncpg://...` and include `?ssl=true` or `sslmode=require` for remote databases.

`JWT_SECRET_KEY` — at least 32 characters.

`ADMIN_EMAIL` / `ADMIN_PASSWORD` — bootstrap admin account.

`SEARCHAPI_KEY` — enables the real provider. Leave empty only for demo mode.

`DEMO_MODE` — set `true` for fake/demo data.

`CORS_ORIGINS` — explicit allowed browser origins.

`ALLOWED_HOSTS` — trusted host allow-list.

`SCHEDULER_ENABLED`, `SCHEDULER_INTERVAL_MINUTES` — collection cadence.

`SCRAPE_BATCH_SIZE`, `SCRAPE_DELAY_SECONDS`, `PROVIDER_TIMEOUT_SECONDS`, `PROVIDER_MAX_RETRIES`, `PROVIDER_CONCURRENCY_LIMIT`, `PROVIDER_MIN_DELAY_SECONDS` — collection tuning.

`LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS`, `SCRAPE_RATE_LIMIT_ATTEMPTS`, `SCRAPE_RATE_LIMIT_WINDOW_SECONDS` — rate limits.

`SENTRY_DSN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — optional monitoring hooks.

### Frontend

`VITE_API_BASE_URL` — backend base URL for local development or Vercel deployments. Leave blank for same-origin Docker hosting.

## Production deployment

### Render backend

Deploy the backend as a Docker service using `render.yaml`. Set the required backend environment variables in Render. For managed Postgres, point `DATABASE_URL` at the database and keep TLS enabled.

### Render frontend

Deploy the frontend as a Render static site using the same `render.yaml`. Set `VITE_API_BASE_URL` to the public backend URL, for example `https://flight-harvester-backend.onrender.com`.

### Docker

`docker compose up --build` starts PostgreSQL, the backend, and the nginx-served frontend together.

## Health checks

`GET /health` — overall health summary.

`GET /health/live` — liveness.

`GET /health/ready` — readiness for deployment checks.

## Client handoff notes

The API is protected with JWT bearer tokens, login and scrape trigger rate limiting, and redacted structured logging. Admins and users have the same tracker authority; only the user-management section is admin-only. The scheduler uses a PostgreSQL advisory lock to prevent duplicate collection runs, and fully scraped groups are skipped automatically.

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

If the backend fails on startup with a PostgreSQL connection error, confirm a
database is running on `localhost:5432` for host-based development, or start
Docker Desktop and run `docker compose up -d db`.

If collection is disabled or provider status looks degraded, confirm `SEARCHAPI_KEY` is set and that your SearchApi.io quota is not exhausted, or use `DEMO_MODE=true`.

If the frontend cannot reach the API, verify `VITE_API_BASE_URL` and browser CORS origins.

If Render health checks fail, confirm the backend can connect to PostgreSQL with TLS and that `scheduler_enabled` is true.

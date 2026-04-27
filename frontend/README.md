# Flight Data Scrapper — Frontend

React 19 + TypeScript + Tailwind CSS dashboard for the Flight Data Scrapper platform.

---

## What this is

The frontend is the visual interface for:

- Viewing collected flight prices and coverage
- Managing route groups (which airports and dates to track)
- Triggering manual collection runs and stopping them
- Downloading Excel exports
- Browsing scrape logs

It connects to the **backend API** (FastAPI) — the backend must be running before starting the frontend.

---

## Prerequisites

- **Node.js 18+** — https://nodejs.org/en/download (choose LTS)
- The **backend** must be running at http://localhost:8000

Check your versions:

```bash
node --version   # must be v18.0.0 or higher
npm --version
```

---

## Setup (local development)

### Step 1 — Install dependencies

```bash
cd frontend
npm install
```

### Step 2 — Create the environment file

```bash
cp .env.example .env
```

The default `.env` already points to localhost — no change needed for local dev:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

### Step 3 — Start the development server

```bash
npm run dev
```

Dashboard opens at **http://localhost:5173**. Changes to source files are reflected instantly.

---

## Available commands

| Command | What it does |
|---------|--------------|
| `npm run dev` | Start dev server with hot reload |
| `npm run build` | Build production bundle into `dist/` |
| `npm run preview` | Preview the production build locally at port 4173 |
| `npm run lint` | Run ESLint on all TypeScript/React files |

---

## Pages

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Overview stats, active route groups, collection status |
| Route Group Detail | `/route-groups/:id` | Coverage per date, price table, export button |
| Data Explorer | `/explorer` | Search and filter all collected prices |
| Collection Logs | `/logs` | Every individual scrape attempt with status, duration, price found |

---

## Project structure

```
frontend/
├── src/
│   ├── api/                     # Typed Axios functions (one file per resource)
│   │   ├── auth.ts              # login, getMe
│   │   ├── collection.ts        # trigger, stop, runs, logs
│   │   ├── prices.ts            # query prices
│   │   ├── routeGroups.ts       # CRUD, export
│   │   └── stats.ts             # overview stats
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx    # Sidebar + main content wrapper
│   │   │   └── Sidebar.tsx      # Nav: Dashboard, Data Explorer, Collection Logs
│   │   └── ...                  # Shared UI components
│   ├── context/
│   │   ├── AuthContext.tsx      # Login state, JWT storage, logout
│   │   └── ToastContext.tsx     # Toast notification system
│   ├── pages/
│   │   ├── DashboardPage.tsx
│   │   ├── RouteGroupDetailPage.tsx
│   │   ├── DataExplorerPage.tsx
│   │   ├── CollectionLogsPage.tsx
│   │   └── LoginPage.tsx
│   └── types/                   # TypeScript interfaces
├── .env.example
├── vite.config.ts
├── tailwind.config.ts
└── package.json
```

---

## Building for production

```bash
npm run build
```

Output goes into `dist/`. Test the production build locally:

```bash
npm run preview
# Opens at http://localhost:4173
```

---

## Docker

The frontend is included in `docker-compose.yml` and served on port 80 via nginx. When you run `docker compose up --build` from `flight-harvester/`, the frontend is built and served automatically.

You do not need to run `npm install` or `npm run build` manually when using Docker.

---

## Deploying to Vercel

1. Go to https://vercel.com → **New Project → Import Git Repository**
2. Select this repository, set **Root Directory** to `flight-harvester/frontend`
3. Add environment variable: `VITE_API_BASE_URL=https://your-backend.example.com`
4. Click Deploy — Vercel runs `npm run build` automatically

After deploying, set `CORS_ORIGINS` in your backend environment to include the Vercel URL.

---

## Environment variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Full URL of the backend API, no trailing slash | `http://localhost:8000` |

All `VITE_` variables are embedded at build time. If you change `.env`, restart `npm run dev` or rebuild.

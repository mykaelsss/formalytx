# Formalytx — F1 Telemetry Explorer

Explore Formula 1 seasons, events, sessions, driver laps, and raw car telemetry. Pick a year and event, choose a session, select drivers to compare, and plot lap times and raw telemetry channels — all in one page.

Data is sourced through [FastF1](https://docs.fastf1.dev), an open-source Python library by Philipp Schaefer and the open-source community.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript |
| Styling | Tailwind CSS v4, shadcn/ui, Radix UI |
| Charts | ECharts 6 |
| Data fetching | TanStack Query v5, Axios |
| Backend | FastAPI, Python 3.14, uv |
| F1 data | FastF1 |
| Local proxy | nginx (Docker Compose) |
| Containerization | Docker / Docker Compose |

---

## Project Structure

```
f1_telemetry/
├── client/          # Next.js frontend
│   ├── app/
│   │   ├── page.tsx          # Landing page
│   │   ├── telemetry/        # Main telemetry explorer
│   │   └── privacy/          # Privacy page
│   └── components/           # UI and feature components
└── server/          # FastAPI backend
    ├── app/
    │   ├── main.py            # App entry, middleware, error handlers
    │   ├── config.py          # Settings (env vars via pydantic-settings)
    │   ├── caching.py         # HTTP Cache-Control header policy
    │   ├── fastf1_loader.py   # In-process Session cache + per-key load locks
    │   ├── sessions/          # Session info, driver laps, telemetry
    │   │   ├── routes.py
    │   │   ├── services.py
    │   │   └── schemas.py     # Pydantic response models
    │   ├── schedule/          # Season schedule, event details, results, podium
    │   │   ├── routes.py
    │   │   ├── services.py
    │   │   └── schemas.py     # Pydantic response models
    │   └── utils.py           # Event ID parsing, FastF1 routing, KeyLockRegistry
    ├── compose.yaml
    ├── compose.override.yaml  # Dev overrides (hot-reload, exposed ports)
    ├── Dockerfile
    └── nginx/                 # Reverse proxy config
```

---

## API Endpoints

`{event_id}` is a string identifier — see [Event IDs](#event-ids) below.

**Schedule**
- `GET /schedule/{year}` — full season schedule
- `GET /schedule/{year}/{event_id}` — event summary
- `GET /schedule/{year}/{event_id}/detailed` — event with weather and lap data
- `GET /schedule/{year}/{event_id}/podium` — podium results
- `GET /schedule/{year}/{event_id}/circuit` — circuit info
- `GET /schedule/{year}/{event_id}/{identifier}/results` — session results

**Sessions**
- `GET /sessions/{year}/{event_id}/{identifier}` — session info
- `GET /sessions/{year}/{event_id}/{identifier}/laps` — driver laps
- `GET /sessions/{year}/{event_id}/{identifier}/laps/telemetry` — raw telemetry

Every route declares a Pydantic `response_model=` — see `app/sessions/schemas.py` and `app/schedule/schemas.py`. Output is validated and filtered against the schema before it leaves the server, which gives the `/docs` reference an accurate shape for each response.

FastAPI auto-generates an interactive endpoint reference at `/docs` when the server is running — treat that as the source of truth for params and response shapes.

---

## Event IDs

URLs use a string identifier instead of a raw round number:

- `r{n}` — race weekend, where `n` is the FastF1 round number (e.g. `r5`)
- `t{n}` — pre-season testing event, indexed from 1 (e.g. `t1`, `t2`)

Why: FastF1 assigns `RoundNumber = 0` to every testing event in a season, so round number alone can't disambiguate them. The schedule endpoint mints these identifiers; every other endpoint takes them and decodes via `parse_event_id` in `app/utils.py`, which routes to either `fastf1.get_event` or `fastf1.get_testing_event`.

---

## Data Flow

- F1 data is sourced entirely from FastF1 — no live API, no separate database
- Request → route → service → `resolve_session(year, event_id, identifier)` (in `app/utils.py`) → FastF1
- FastF1 sessions are loaded via `cached_locked_load` in `app/fastf1_loader.py`. A per-key lock (via `KeyLockRegistry` in `app/utils.py`) serializes concurrent loads of the same session, and the loaded `Session` is pinned in process memory (LRU 8) so repeat requests skip `session.load()` entirely
- FastF1's on-disk cache lives in `server/cache/` (mounted as a volume in Docker Compose)

---

## Caching

### HTTP Cache-Control

Set per-response in `app/caching.py`, gated on session state:

- `LIVE` (`max-age=60`) — session in progress or hasn't ended yet
- `SETTLING` (`max-age=300`) — session ended within the last 2 days; stewards may still apply penalties
- `PAST_SEASON` (`max-age=86400, stale-while-revalidate=604800`) — fully finalized

Schedule list (`/schedule/{year}`): past years get `PAST_SEASON`, current/future year gets `SETTLING` (per-event status flips over time).

Note: avoid `Cache-Control: immutable` on data endpoints. It pins responses in browser and edge caches indefinitely and bites hard when response shapes change — `stale-while-revalidate` gives long cache lifetimes with safe shape evolution.

### In-process caches

Sitting in front of the per-request work, each keyed by the parameters that determine the response. All bounded LRU, all guarded by a `KeyLockRegistry` (in `app/utils.py`) so concurrent requests for the same key serialize on the build instead of stampeding.

| Cache | Module | Key | Cap |
|---|---|---|---|
| Loaded `Session` objects | `app/fastf1_loader.py` | `(year, event_id, identifier)` | 8 |
| Driver-laps response | `app/sessions/services.py` | `(year, event_id, identifier, drivers)` | 256 |
| Per-lap telemetry dict | `app/sessions/services.py` | `(year, event_id, identifier, driver, lap_number)` | 1024 |
| Circuit response | `app/schedule/services.py` | `(year, event_id)` | 64 |

The Session cache skips re-deserializing pandas DataFrames from FastF1's pickle cache. The per-lap telemetry cache skips the `get_car_data().add_distance()` + `.tolist()` work that dominates a cold telemetry response. The laps and circuit caches memoize the full response shape — cheap reads on repeat queries.

These caches are process-local. If you ever run multiple uvicorn workers, each worker has its own; hit rate divides accordingly.

---

## Running Locally

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/)

### Backend

The `compose.override.yaml` is picked up automatically in development — it enables hot-reload and exposes the API directly on port `8000`.

```bash
cd server
docker compose up --build --watch
```

The API will be available at `http://localhost:80` (via nginx) or `http://localhost:8000` (direct).

### Frontend

```bash
cd client
pnpm install
pnpm dev
```

The app will be available at `http://localhost:3000`.

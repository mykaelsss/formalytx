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
    │   ├── fastf1_loader.py   # FastF1 fallback: small Session cache + per-key load locks
    │   ├── archive/           # Session archive on R2: models, export command, reader
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

- F1 data is sourced from FastF1, and finished sessions are exported once into the session archive (see [Session archive](#session-archive)).
- Request → route → service → the archive, through `app/archive/reader.py`.
  Each request reads only the objects it needs: the session summary, then one object per driver for laps or one per lap for telemetry, fetched in parallel.
- Sessions that aren't archived yet (live, just finished, or missing from the archive) fall back to FastF1 through `resolve_session` (in `app/utils.py`).
- FastF1 sessions are loaded via `cached_locked_load` in `app/fastf1_loader.py`.
  A per-key lock (via `KeyLockRegistry` in `app/utils.py`) serializes concurrent loads of the same session.
  The loaded `Session` is kept in process memory, but only a few of them and only while they're used, since each holds a few hundred MB.
- If the archive can't be read, requests fail with a 503 and a `Retry-After` header rather than falling back to FastF1, which would load every session into memory at once.
- FastF1's on-disk cache lives in `server/cache/` (mounted as a volume in Docker Compose).

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

Responses are cached by Cloudflare, so the server keeps only small caches.
They're process-local: with several uvicorn workers, each has its own.

| Cache | Module | Key | Cap |
|---|---|---|---|
| Archived session summaries | `app/archive/reader.py` | `(year, event_id, identifier)` | 256 |
| Archived circuits | `app/archive/reader.py` | `(year, event_id)` | 128 |
| Loaded FastF1 `Session` objects | `app/fastf1_loader.py` | `(year, event_id, identifier)` | `SESSION_CACHE_SIZE` (2) |

Every archive request needs its session summary, so those are cached; summaries whose results aren't final yet are re-read after 10 minutes.
Laps and telemetry are read from the archive on each request.
Loaded FastF1 sessions are dropped after `SESSION_CACHE_IDLE_SECONDS` (30 minutes) without use.

---

## Running Locally

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/)
- [uv](https://docs.astral.sh/uv/)
- [Infisical CLI](https://infisical.com/docs/cli/overview), logged in with `infisical login`

### Secrets

Server secrets live in Infisical, in the project linked by `server/.infisical.json`.
Run server commands through `infisical run --` from `server/` to supply them.
`server/.env.example` lists the variables the server reads.

### Backend

The `compose.override.yaml` is picked up automatically in development — it enables hot-reload and exposes the API directly on port `8000`.

```bash
cd server
infisical run -- docker compose up --build --watch
```

The API will be available at `http://localhost:80` (via nginx) or `http://localhost:8000` (direct).
Running through `infisical run` passes the R2 credentials into the container, so archived sessions are served from the dev bucket.
Without them, every session is loaded through FastF1.

### Session archive

Finished sessions are exported from FastF1 into the archive (Cloudflare R2, or a local folder):

```bash
cd server
infisical run -- uv run python -m app.archive 2025          # every finished session of 2025
infisical run -- uv run python -m app.archive 2025 r16      # every session of one event
infisical run -- uv run python -m app.archive 2025 r16 R    # one session
```

These write to Infisical's dev environment, whose bucket is only for testing.
The production bucket, which the backfill fills, is selected with `--env=prod`:

```bash
infisical run --env=prod -- uv run python -m app.archive 2025
```

Sessions already exported are skipped unless their results have since become final.
`--overwrite` exports them again, and `--force` also exports sessions that ended less than 6 hours ago.
A session FastF1 can't fully load (laps, car or position data, results or weather) isn't exported.
If that data doesn't exist upstream, `--allow-incomplete` exports it with the missing parts recorded.

### Frontend

```bash
cd client
pnpm install
pnpm dev
```

The app will be available at `http://localhost:3000`.

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
    │   ├── fastf1_loader.py   # FastF1 fallback: per-key load locks, disk cache pruning
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
- Sessions that aren't archived yet (live, just uploaded and waiting for the next export, or missing from the archive) fall back to FastF1 through `resolve_session` (in `app/utils.py`).
- FastF1 sessions are loaded via `locked_load` in `app/fastf1_loader.py`.
  A per-key lock (via `KeyLockRegistry` in `app/utils.py`) serializes concurrent loads of the same session, so only the first fetches it upstream.
  Loaded sessions aren't kept in memory, since each holds a few hundred MB: each request loads its session again from FastF1's on-disk cache.
- An event the archive has no circuit info for builds it through FastF1 from the first finished session that isn't archived and can, as the export does.
  Events without any, such as at a circuit FastF1 has no layout for, get a 404.
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
| Circuits built through FastF1 | `app/schedule/services.py` | `(year, event_id)` | 64 |

Every archive request needs its session summary, so those are cached; summaries whose results aren't final yet are re-read after 10 minutes.
Laps and telemetry are read from the archive on each request.
Circuits built through FastF1 are kept, and events without one are re-checked after 10 minutes.

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
infisical run -- uv run python -m app.archive               # every finished session of this season
infisical run -- uv run python -m app.archive 2025          # every finished session of 2025
infisical run -- uv run python -m app.archive 2025 r16      # every session of one event
infisical run -- uv run python -m app.archive 2025 r16 R    # one session
infisical run -- uv run python -m app.archive --recent      # this year's events under way or ended in the last week
```

`--recent` is what the scheduled export runs: the week covers the 2 days results take to become final, with room to catch up on missed runs.

These write to Infisical's dev environment, whose bucket is only for testing.
The production bucket, which the backfill fills, is selected with `--env=prod`:

```bash
infisical run --env=prod -- uv run python -m app.archive 2025
```

A session is exported as soon as it has ended and FastF1 can fully load it.
Until its results are final, 2 days after it ends, every run checks it again, so it picks up a partial upload being completed and later penalties.
Those checks bypass FastF1's cache, which would otherwise keep the first data it saw, and only write the objects that changed.
Sessions with final results are skipped; `--overwrite` checks them again, and `--force` also exports sessions that haven't ended.
A session FastF1 can't fully load (laps, car or position data, results or weather) isn't exported.
Within 6 hours of its end it's taken to be still uploading.
After that, a session without any laps, such as one cancelled for weather, is skipped as having no data, and any other is skipped as incomplete.
If that data doesn't exist upstream, `--allow-incomplete` exports it with the missing parts recorded.
`--allow-incomplete-when-final` does so only once the session's results are final, 2 days after it ends, since missing data rarely appears later than that.

An event's circuit info is built when its first session is exported.
If that session has no lap with car and position data, the next session exported builds it instead.
An event at a circuit FastF1 has no layout for, such as one new to MultiViewer, gets none.
`--circuit` builds only the circuit info, from the first finished session that can, for events that have none:

```bash
infisical run --env=prod -- uv run python -m app.archive 2018 r12 --circuit
```

### Scheduled export

In production, a Railway cron service runs `--recent` every 15 minutes.
Each session is exported as soon as FastF1 can fully load it, and checked again on every run until its results are final, 2 days after it ends.
A run with nothing new takes a couple of seconds and writes nothing.
A session FastF1 can't fully load is retried on every run until its results are final, then archived with what loaded (`--allow-incomplete-when-final`).
A run exits with an error only when a session failed with one, such as R2 or FastF1 being unreachable; the next run retries it.

The service is built from `server/` like the API, and its settings live in `server/railway.cron.toml`.
To set it up:

1. Add a service from this repository with the root directory `/server`.
2. Under Settings > Config-as-code, set the config file to `/server/railway.cron.toml`.
3. Give it the API's R2 variables (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` and `R2_BUCKET`) from Infisical's prod environment.

It needs no volume or domain: FastF1's cache only lasts for one run.

### Frontend

```bash
cd client
pnpm install
pnpm dev
```

The app will be available at `http://localhost:3000`.

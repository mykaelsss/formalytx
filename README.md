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
    │   ├── sessions/          # Session info, driver laps, telemetry endpoints
    │   └── schedule/          # Season schedule, round details, results, podium
    ├── compose.yaml
    ├── compose.override.yaml  # Dev overrides (hot-reload, exposed ports)
    ├── Dockerfile
    └── nginx/                 # Reverse proxy config
```

---

## API Endpoints

**Schedule**
- `GET /schedule/{year}` — full season schedule
- `GET /schedule/{year}/{round}` — round summary
- `GET /schedule/{year}/{round}/detailed` — round with weather and lap data
- `GET /schedule/{year}/{round}/podium` — podium results
- `GET /schedule/{year}/{round}/circuit` — circuit info
- `GET /schedule/{year}/{round}/{identifier}/results` — session results

**Sessions**
- `GET /sessions/{year}/{round}/{identifier}` — session info
- `GET /sessions/{year}/{round}/{identifier}/laps` — driver laps
- `GET /sessions/{year}/{round}/{identifier}/laps/telemetry` — raw telemetry

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

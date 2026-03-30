# Plan: Simplify search_ui Docker Setup

## Context

The search_ui directory has **two** docker-compose files (`docker-compose.yml` for production, `docker-compose-dev.yml` for dev) that differ by a single line (`volumes: .:/app`). Both orchestrate a single service with no inter-service dependencies. The Dockerfile is already production-ready (copies code, has CMD), but lacks a dev target. This mirrors the same pattern we just fixed in embeddings.

Additionally, the Makefile has a **duplicate `dev_run` target** (lines 15 and 36) — the second definition silently overwrites the first, so `make dev_run` runs uvicorn locally instead of via Docker.

### Key difference from embeddings
search_ui is a **long-running web server**, not batch scripts. It needs lifecycle management (`start`/`stop`/`logs`). With plain `docker run`, this maps to:
- `docker run -d --name` (detached) instead of `docker compose up -d`
- `docker stop`/`docker rm` instead of `docker compose down`
- `docker logs -f` instead of `docker compose logs`

### Networking difference
Embeddings uses `--network host`. search_ui uses explicit port mapping (`-p 8000:8000`) + `--add-host host.docker.internal:host-gateway`. I'll keep the `--add-host` approach since the app already references `host.docker.internal` in its config.

## Approach

### 1. Rewrite Dockerfile with dev/production stages

**File:** `search_ui/Dockerfile`

```dockerfile
########### BASE STAGE ###########
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

########### DEV STAGE ###########
FROM base AS dev
# App code provided via volume mount at runtime
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

########### PRODUCTION STAGE ###########
FROM base AS production
COPY app ./app
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- `dev` stage: no COPY of app code (comes via volume mount), CMD includes `--reload` for hot-reloading
- `production` stage: copies app code, no `--reload`

### 2. Delete both docker-compose files

**Files to delete:** `docker-compose.yml`, `docker-compose-dev.yml`

Compose features map to docker flags:
| docker-compose | docker equivalent |
|---|---|
| `env_file: .env` | `--env-file .env` |
| `ports: 8000:8000` | `-p 8000:8000` |
| `volumes: .:/app` | `-v $(pwd):/app` (dev only) |
| `extra_hosts: host.docker.internal:host-gateway` | `--add-host host.docker.internal:host-gateway` |

### 3. Rewrite Makefile with plain docker commands

**File:** `search_ui/Makefile`

Follow the same `dev_` prefix convention used in the updated embeddings Makefile. Fix the duplicate `dev_run` bug. Replace `docker compose` with `docker build`/`docker run`.

Key targets:
- **Dev:** `dev_build`, `dev_run` (foreground), `dev_start` (detached), `dev_stop`, `dev_down`, `dev_logs`, `dev_sh`, `dev_test`
- **Prod:** `build`, `start`, `stop`, `down`, `logs`, `sh`
- **Local (no Docker):** `dev_run_local` (renamed from the duplicate `dev_run` that runs uvicorn directly)

Container lifecycle with plain docker:
- `start`: `docker run -d --name search-ui ...`
- `stop`: `docker stop search-ui`
- `down`: `docker stop search-ui && docker rm search-ui`
- `logs`: `docker logs -f search-ui`

### 4. Update README.md

Fix to reflect new Makefile targets and removal of docker-compose.

## Files to modify
- `search_ui/Dockerfile` — add dev/production stages
- `search_ui/docker-compose.yml` — delete
- `search_ui/docker-compose-dev.yml` — delete
- `search_ui/Makefile` — plain docker commands, fix duplicate target
- `search_ui/README.md` — update docs

## Verification
1. `make dev_build && make dev_run` — dev mode with volume mount + hot-reload
2. `make build && make start && make logs` — production mode
3. `curl http://localhost:8000/health` — verify app responds
4. `make down` — clean up

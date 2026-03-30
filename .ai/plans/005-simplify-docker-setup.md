# Plan: Simplify Embeddings Docker Setup

## Context

The embeddings directory uses docker-compose to orchestrate a **single service** with no inter-service dependencies (MongoDB, Ollama, Solr all live externally). The Dockerfile is incomplete — it never copies application code, making it unusable without a volume mount. docker-compose acts purely as a convenience wrapper for `docker run` flags (`--env-file`, `-v`, `--network host`), adding indirection with no orchestration value.

The user wants to evaluate whether docker-compose is necessary and whether the volume mount pattern is appropriate for production.

## Approach: Multi-stage Dockerfile + Eliminate docker-compose

### 1. Fix dependency declarations in `pyproject.toml`
- **Add** `requests` (used in `generate_embeddings.py` but undeclared — works only via transitive dep)
- **Remove** `pysolr` (declared but never imported — `load_solr.py` uses `httpx` directly)
- Regenerate `uv.lock` with `uv lock`

### 2. Rewrite `Dockerfile` with dev/production targets
- **`base`** stage: shared layer (uv install, dependency sync) — same as current
- **`dev`** stage: empty extension of base, code comes via volume mount at runtime
- **`production`** stage: `COPY`s the Python scripts into the image for standalone execution

```dockerfile
FROM python:3.14-alpine AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/opt/venv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync

FROM base AS dev
# Code provided via volume mount

FROM base AS production
COPY generate_embeddings.py load_solr.py ./
```

### 3. Rewrite `Makefile` with plain `docker` commands
- Dev targets: `docker run --rm --network host --env-file .env -v $(pwd):/app` (volume-mounted)
- Prod targets: `docker run --rm --network host --env-file .env` (code baked in)
- Remove `down` target (no lingering containers with `--rm`)
- Add `build-prod` target

### 4. Delete `docker-compose.yml`
Every feature it provides maps to a `docker run` flag:
| docker-compose | docker run equivalent |
|---|---|
| `env_file: .env` | `--env-file .env` |
| `volumes: .:/app` | `-v $(pwd):/app` |
| `network_mode: host` | `--network host` |
| `build: context: .` | `docker build .` |

### 5. Update `.gitignore`
- Add `.env` (currently not excluded)

### 6. Update `README.md`
- Fix outdated docs (references non-existent `set_env.sh`, wrong data flow description)
- Document dev vs production workflow and Make targets

## Files to modify
- `embeddings/pyproject.toml` — fix deps
- `embeddings/Dockerfile` — multi-stage rewrite
- `embeddings/Makefile` — plain docker commands
- `embeddings/docker-compose.yml` — delete
- `embeddings/.gitignore` — add .env
- `embeddings/README.md` — update docs

## Out of scope
- Unifying `requests`/`httpx` into one HTTP library (separate concern, both work fine)
- Managing external services (MongoDB, Ollama, Solr) in docker-compose

## Verification
1. `make build && make generate_embeddings args="--dry-run --limit 1"` (dev mode)
2. `make build-prod && make generate_embeddings-prod args="--dry-run --limit 1"` (prod mode)
3. `make sh` — verify interactive shell works

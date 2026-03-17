# Plan: Dockerize Embeddings Scripts

## Context

The `embeddings/` scripts currently run directly on the host, requiring manual Python/uv setup. Isolating them in Docker provides better dependency management and consistent Python version control across environments.

## Files to Create

### 1. `embeddings/Dockerfile`

```dockerfile
########### BASE STAGE ###########
FROM python:3.13-alpine AS base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

########### DEV STAGE ###########
FROM base AS dev

COPY pyproject.toml uv.lock ./
RUN uv sync
```

Key decisions:
- Python 3.13-alpine to match `.python-version`
- `UV_PROJECT_ENVIRONMENT=/opt/venv` keeps dependencies outside `/app` so the volume mount doesn't shadow them (same pattern as `set_env.sh` on host)
- No `EXPOSE` — these are CLI scripts, not a server
- No prod stage needed for now

### 2. `embeddings/docker-compose-dev.yml`

```yaml
services:
  embeddings:
    container_name: embeddings
    build:
      context: .
      target: dev
    env_file:
      - .env
    volumes:
      - .:/app
    network_mode: host
```

Key decisions:
- `network_mode: host` — scripts connect to MongoDB/Ollama/Solr on localhost; host networking avoids URL changes (Linux-only, which matches this environment)
- `env_file` loads `.env` directly — no need for `set_env.sh` inside Docker
- Volume mount `.:/app` for live code editing during development
- No `command` — scripts are invoked via `docker compose run`

### 3. Modify `embeddings/Makefile`

Add Docker dev targets after existing local targets:

```makefile
# Docker DEV
COMPOSE_FILE_DEV=docker-compose-dev.yml

dev_build:
	@docker compose -f $(COMPOSE_FILE_DEV) build

dev_build_no_cache:
	@docker compose -f $(COMPOSE_FILE_DEV) build --no-cache

dev_generate_embeddings:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm embeddings uv run python generate_embeddings.py

dev_load_solr:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm embeddings uv run python load_solr.py

dev_sh:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm embeddings sh

dev_down:
	@docker compose -f $(COMPOSE_FILE_DEV) down
```

- Uses `docker compose run --rm` (one-shot execution with cleanup) instead of `exec` (which requires a running service)
- Preserves all existing local targets unchanged

### 4. Create `.ai/logs/2026-03-17-dockerize-embeddings.md`

Log file documenting the changes per CLAUDE.md instructions.

## Implementation Order

1. Create `embeddings/Dockerfile`
2. Create `embeddings/docker-compose-dev.yml`
3. Add Docker targets to `embeddings/Makefile`
4. Create `.ai/logs/` entry

## Verification

1. `cd embeddings && make dev_build` — should build the image successfully
2. `make dev_sh` — opens a shell inside the container; verify `uv run python -c "import pymongo; print('ok')"` works
3. `make dev_generate_embeddings` — runs the embeddings script (requires MongoDB and Ollama running on host)
4. `make dev_load_solr` — runs the Solr loader (requires MongoDB and Solr running on host)

## Notes

- If `python:3.13-alpine` causes C extension build issues, fallback to `python:3.13-slim`
- `network_mode: host` is Linux-specific; for macOS/Windows support later, switch to `extra_hosts` approach

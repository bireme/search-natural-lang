# Simplify Docker Setup for Search UI

**Date:** 2026-03-30

## Summary

Simplified the Docker configuration for the search_ui app by eliminating both docker-compose files (which orchestrated a single service differing by one volume line) and introducing a multi-stage Dockerfile with dev and production targets. Fixed duplicate Makefile target bug.

## Changes

### `search_ui/Dockerfile`
- Restructured into 3 stages: `base` (shared deps), `dev` (volume mount + `--reload`), `production` (COPY app code)
- Dev stage includes `--reload` in CMD for hot-reloading
- Production stage copies app code and omits `--reload`

### `search_ui/Makefile`
- Replaced all `docker compose` commands with plain `docker build`/`docker run`
- Fixed duplicate `dev_run` target: Docker-based run stays as `dev_run`, local uvicorn renamed to `dev_run_local`
- Extracted shared docker flags into `DOCKER_FLAGS` variable
- Added `CONTAINER_NAME` variable for lifecycle management (`stop`, `down`, `logs`)
- Dev targets use `-v $(pwd):/app` for volume-mounted code
- Production targets run without volume mount

### `search_ui/docker-compose.yml`
- Deleted

### `search_ui/docker-compose-dev.yml`
- Deleted

### `search_ui/README.md`
- Updated setup/usage sections to reflect new Makefile targets
- Preserved environment variables reference and troubleshooting sections

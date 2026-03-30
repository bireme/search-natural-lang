# Simplify Docker Setup for Embeddings

**Date:** 2026-03-30

## Summary

Simplified the Docker configuration for the embeddings scripts by eliminating docker-compose (which orchestrated a single service with no inter-service dependencies) and introducing a multi-stage Dockerfile with separate dev and production targets.

## Changes

### `embeddings/pyproject.toml`
- Added `requests>=2.32.0` (was used in `generate_embeddings.py` but undeclared)
- Removed `pysolr>=3.9.0` (declared but never imported; `load_solr.py` uses `httpx` directly)
- Regenerated `uv.lock`

### `embeddings/Dockerfile`
- Added `dev` stage: extends base, expects code via volume mount (development workflow)
- Added `production` stage: COPYs Python scripts into image for standalone execution
- Base stage unchanged (uv install + dependency sync)

### `embeddings/Makefile`
- Replaced all `docker compose` commands with plain `docker build`/`docker run`
- Dev targets (`build`, `generate_embeddings`, `load_solr`, `sh`) use `-v $(pwd):/app` for volume-mounted code
- Production targets (`build-prod`, `generate_embeddings-prod`, `load_solr-prod`) run without volume mount
- Removed `down` target (containers use `--rm`, no lingering state)

### `embeddings/docker-compose.yml`
- Deleted. All features mapped to `docker run` flags: `--env-file .env`, `-v $(pwd):/app`, `--network host`

### `embeddings/.gitignore`
- Added `.env` to exclusions

### `embeddings/README.md`
- Rewrote to reflect current data flow (MongoDB → Ollama → MongoDB → Solr)
- Documented dev vs production workflow and all CLI options
- Removed references to non-existent `set_env.sh`

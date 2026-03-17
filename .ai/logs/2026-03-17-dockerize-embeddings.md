# Dockerize Embeddings Scripts

## Summary

Added Docker support for the `embeddings/` scripts to provide consistent dependency management and Python version control across environments.

## Changes

### Created `embeddings/Dockerfile`
- Two-stage build: `base` (Python 3.13-alpine + uv) and `dev` (with dependencies installed)
- `UV_PROJECT_ENVIRONMENT=/opt/venv` keeps dependencies outside `/app` so the volume mount doesn't shadow them

### Created `embeddings/docker-compose-dev.yml`
- `network_mode: host` for accessing MongoDB/Ollama/Solr on localhost
- Volume mount `.:/app` for live code editing
- `env_file` loads `.env` directly

### Modified `embeddings/Makefile`
- Added Docker dev targets: `dev_build`, `dev_build_no_cache`, `dev_generate_embeddings`, `dev_load_solr`, `dev_sh`, `dev_down`
- All existing local targets preserved unchanged

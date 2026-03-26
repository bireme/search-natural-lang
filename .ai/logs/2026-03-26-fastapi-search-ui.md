# FastAPI Search UI Implementation

## Summary

- Added a new isolated `search_ui/` project with a FastAPI backend and static HTML, CSS, and JavaScript frontend
- Implemented `GET /health`, `GET /config`, and `POST /search`
- Added Docker packaging with `Dockerfile`, `docker-compose.yml`, and `.env.example`
- Added API tests covering validation, vector search, keyword search, empty results, and upstream failure mapping

## Endpoints

- `GET /health`
- `GET /config`
- `POST /search`

## Docker

- Single app image built from `search_ui/Dockerfile`
- Compose service exposes `8000:8000`
- Compose includes `host.docker.internal:host-gateway` for access to external Solr and Ollama services
- Added `search_ui/Makefile` with shortcuts for build, up, down, logs, shell, local sync, local run, and tests

## Assumptions

- Solr collection default is `embeddings`
- Solr vector field is `vector`
- Solr title field is `ti`
- Solr keyword query field defaults to `ti`
- Solr exposes `score` in returned documents
- Solr KNN syntax is supported through `/select` using `{!knn f=vector topK=N}[...]`
- Ollama embeddings endpoint is compatible with `/api/embed` and returns an `embeddings` array

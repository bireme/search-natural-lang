# Search UI

FastAPI web interface for Solr vector and keyword search, with Ollama-powered embeddings.

## External services

- Solr with a collection that exposes fields compatible with this app
- Ollama-compatible embeddings endpoint for vector mode

## Setup

1. Copy and configure the environment file:
```bash
cp .env.example .env
```

2. Build the Docker image:
```bash
make dev_build   # development (volume-mounted, hot-reload)
make build       # production (code baked in)
```

## Development

Run with Docker (hot-reload via volume mount):
```bash
make dev_run       # foreground
make dev_start     # detached
make dev_logs      # follow logs
make dev_stop      # stop container
make dev_down      # stop + remove container
make dev_sh        # shell into container
```

Run locally without Docker:
```bash
uv sync --dev
make dev_run_local
```

Run tests:
```bash
make dev_test
make dev_test args="-v"
```

## Production

```bash
make build
make start    # run detached
make logs     # follow logs
make stop     # stop container
make down     # stop + remove container
```

## Environment variables

Copy `.env.example` to `.env` and adjust values as needed.

### App

- `APP_HOST`
- `APP_PORT`
- `APP_DEFAULT_TOP_K`
- `APP_MAX_TOP_K`
- `APP_LOG_LEVEL`

### Solr

- `SOLR_BASE_URL`
- `SOLR_COLLECTION`
- `SOLR_VECTOR_FIELD`
- `SOLR_TITLE_FIELD`
- `SOLR_ID_FIELD`
- `SOLR_RECORD_ID_FIELD`
- `SOLR_MODEL_FIELD`
- `SOLR_KEYWORD_QF`
- `SOLR_TIMEOUT_SECONDS`

### Embeddings

- `EMBEDDINGS_API_URL`
- `EMBEDDINGS_MODEL`
- `EMBEDDINGS_VECTOR_SIZE`
- `EMBEDDINGS_TIMEOUT_SECONDS`

## Example curl requests

```bash
curl http://localhost:8000/health
curl http://localhost:8000/config
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"hypertension treatment in older adults","mode":"vector","top_k":10}'
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"hypertension treatment in older adults","mode":"keyword","top_k":10}'
```

## Troubleshooting

### Cannot reach Solr

- Verify `SOLR_BASE_URL` and `SOLR_COLLECTION`
- Confirm Solr is reachable from the container or local process
- Check that `host.docker.internal` resolves in Docker on your platform

### Cannot reach Ollama

- Verify `EMBEDDINGS_API_URL`
- Confirm the embeddings endpoint accepts Ollama-compatible `/api/embed` requests
- Vector mode depends on Ollama; keyword mode does not

### Wrong vector size

- Check `EMBEDDINGS_VECTOR_SIZE`
- Confirm the configured model matches the Solr vector field dimensionality

### Empty results

- Validate the Solr collection name and field mappings
- Check whether `SOLR_KEYWORD_QF` points to a searchable text field
- For vector mode, verify the Solr vector field contains embeddings produced by the same model family

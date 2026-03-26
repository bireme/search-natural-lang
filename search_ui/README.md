# Search UI

This app provides a small FastAPI-based browser UI for testing document retrieval from a Solr collection using either vector search or keyword search.

## External services

- Solr with a collection that exposes fields compatible with this app
- Ollama-compatible embeddings endpoint for vector mode

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

## Local run

```bash
cd search_ui
cp .env.example .env
uv sync --dev
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## Docker run

```bash
cd search_ui
cp .env.example .env
docker compose up --build
```

The container maps port `8000` and includes `host.docker.internal:host-gateway` for local host service access.

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

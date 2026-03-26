# Plan: FastAPI Search UI for Solr Vector Retrieval

## Summary

Implement a small Dockerized web application in this repo that provides a browser-based search interface for testing document retrieval from a Solr collection. The first release will support two search modes in the UI:

- `vector`
- `keyword`

The app will use FastAPI for the backend and serve a static HTML/CSS/JS frontend from the same container for simple deployment. Solr and Ollama will be treated as external services configured by environment variables. The implementation will be intentionally small, inspectable, and easy to run locally or deploy with Docker.

## Goals

- Provide a simple browser UI to test Solr retrieval behavior.
- Support natural-language vector search using the same embedding model already used in this repo.
- Support keyword search as a baseline for comparison.
- Keep deployment simple by packaging the app as a single Docker image.
- Preserve room to add hybrid search later without redesigning the API.

## Non-Goals

- No authentication.
- No database writes or persistence for search history.
- No React or frontend build pipeline.
- No production orchestration beyond Docker and a simple Compose setup.
- No hybrid result fusion in v1.
- No changes to embeddings generation or Solr loading behavior unless required for read compatibility.

## Current Repo Constraints

Existing repo facts that shape the implementation:

- Python + `uv` is already the project pattern under `embeddings/`.
- Embeddings are generated via Ollama-compatible API in [`embeddings/generate_embeddings.py`](/home/projects/search-natural-lang/embeddings/generate_embeddings.py).
- Solr documents currently loaded from Mongo to Solr include:
  - `id`
  - `record_id`
  - `ti`
  - `vector`
  - `vector_size`
  - `model`
- Docker already exists in the repo for the `embeddings/` area and uses simple patterns:
  - Python base image
  - `uv`
  - environment variables
  - host/external service connectivity

## Product Decisions Locked

- Search modes in v1: `vector` and `keyword`
- Docker scope in v1: app container only
- Frontend style: plain static HTML + CSS + vanilla JS, served by FastAPI
- Backend style: one FastAPI service exposing JSON endpoints and static assets
- Deployment model: one image for the app; Solr and Ollama remain external dependencies referenced by env vars

## Proposed Directory Layout

Create a new top-level app area so it remains separate from `embeddings/`:

- `search_ui/pyproject.toml`
- `search_ui/uv.lock`
- `search_ui/app/main.py`
- `search_ui/app/config.py`
- `search_ui/app/clients/ollama.py`
- `search_ui/app/clients/solr.py`
- `search_ui/app/models.py`
- `search_ui/app/static/index.html`
- `search_ui/app/static/app.js`
- `search_ui/app/static/styles.css`
- `search_ui/Dockerfile`
- `search_ui/docker-compose.yml`
- `search_ui/.env.example`
- `search_ui/README.md`

## Functional Specification

### User Experience

The page will contain:

- A single search input for natural-language text
- A mode selector:
  - `Vector`
  - `Keyword`
- A `Top K` selector with default `10`
- A `Search` button
- A result list
- A small debug/details section below the results

### Result List Behavior

Each result card will display:

- `title`: from Solr field `ti`
- `record_id`
- `score`
- `id`
- `model` if present

If any field is missing, the UI will show a fallback placeholder:
- title fallback: `Untitled`
- model fallback: omit line if absent

### Empty and Error States

The UI must support:

- Initial empty state before the first search
- Loading state while request is in flight
- “No results found” state
- Inline error state for backend, Solr, or embedding failures

### Debug Section

Below the results, render:

- request mode
- top_k
- response time in ms
- vector length for vector mode
- Solr request summary string
- number of results returned

This is required because the app is a retrieval test bench, not only a user-facing search page.

## Backend Specification

### Framework

Use FastAPI with Uvicorn.

### Static Asset Serving

FastAPI will serve:

- `/` -> `index.html`
- `/static/*` -> JS/CSS assets

No frontend build step is allowed in v1.

### Public Endpoints

#### `GET /health`

Purpose:
- Health check for container/deployment verification

Response:
```json
{
  "status": "ok"
}
```

#### `GET /config`

Purpose:
- Expose safe runtime config needed by the UI

Response fields:
- `default_top_k`
- `max_top_k`
- `supported_modes`

Example:
```json
{
  "default_top_k": 10,
  "max_top_k": 50,
  "supported_modes": ["vector", "keyword"]
}
```

#### `POST /search`

Request body:
```json
{
  "query": "hypertension treatment in older adults",
  "mode": "vector",
  "top_k": 10
}
```

Validation rules:
- `query` required, trimmed, non-empty
- minimum length after trim: `2`
- `mode` must be one of `vector`, `keyword`
- `top_k` integer between `1` and `50`

Response shape:
```json
{
  "query": "hypertension treatment in older adults",
  "mode": "vector",
  "top_k": 10,
  "took_ms": 123,
  "results": [
    {
      "id": "123",
      "record_id": "abc-123",
      "title": "Hypertension management",
      "score": 0.8123,
      "model": "nomic-embed-text"
    }
  ],
  "debug": {
    "solr_query": "{!knn f=vector topK=10}[...]",
    "embedding_model": "nomic-embed-text",
    "embedding_size": 768,
    "solr_rows": 10
  }
}
```

For keyword mode:
- `embedding_model` and `embedding_size` in `debug` should be `null`

## Data Flow Specification

### Vector Search Flow

1. UI sends `POST /search` with `mode=vector`
2. Backend validates input
3. Backend calls Ollama embeddings API using configured model
4. Backend validates that an embedding vector is returned and has length > 0
5. Backend formats the Solr KNN query using the `vector` field
6. Backend calls Solr select/search endpoint
7. Backend normalizes Solr docs into a stable response payload
8. Backend returns JSON to UI

### Keyword Search Flow

1. UI sends `POST /search` with `mode=keyword`
2. Backend validates input
3. Backend sends Solr text query against configured text fields
4. Backend normalizes Solr docs into the same response payload
5. Backend returns JSON to UI

## Solr Query Specification

### Vector Mode

Assume Solr is configured with a vector field named `vector`.

Query format:
- KNN local params query
- `topK` set from request
- vector serialized as compact JSON-like array without spaces

Default implementation target:
- use Solr `/select`
- send `q={!knn f=vector topK=<top_k>}<vector_literal>`
- `fl=id,record_id,ti,score,model`
- `rows=<top_k>`

### Keyword Mode

Default implementation target:
- query field set to `ti`
- request:
  - `q=ti:(<escaped user query>)`
  - `fl=id,record_id,ti,score,model`
  - `rows=<top_k>`

Preferred implementation detail:
- support a configurable text query expression via env var so the app can evolve without code changes
- default:
  - `SOLR_KEYWORD_QF=ti`

The backend should centralize this so hybrid mode can later reuse the same query builder.

## External Service Configuration

### Environment Variables

The app will read these from `.env` and Docker environment:

#### App
- `APP_HOST=0.0.0.0`
- `APP_PORT=8000`
- `APP_DEFAULT_TOP_K=10`
- `APP_MAX_TOP_K=50`
- `APP_LOG_LEVEL=INFO`

#### Solr
- `SOLR_BASE_URL=http://host.docker.internal:8983/solr`
- `SOLR_COLLECTION=embeddings`
- `SOLR_VECTOR_FIELD=vector`
- `SOLR_TITLE_FIELD=ti`
- `SOLR_ID_FIELD=id`
- `SOLR_RECORD_ID_FIELD=record_id`
- `SOLR_MODEL_FIELD=model`
- `SOLR_KEYWORD_QF=ti`
- `SOLR_TIMEOUT_SECONDS=20`

#### Embeddings / Ollama
- `EMBEDDINGS_API_URL=http://host.docker.internal:11434/api/embed`
- `EMBEDDINGS_MODEL=nomic-embed-text`
- `EMBEDDINGS_VECTOR_SIZE=768`
- `EMBEDDINGS_TIMEOUT_SECONDS=30`

### Docker Connectivity Defaults

Because the app container will call host services in common local setups, the Compose setup should include:

- `extra_hosts`
  - `host.docker.internal:host-gateway`

This is preferred over `network_mode: host` for the web app because:
- it is cleaner for a containerized HTTP service
- it is easier to map ports
- it is more deployment-friendly
- it keeps the app accessible at a stable container port

## Docker Specification

### Dockerfile

Use a small Python image with `uv`, following the repo pattern.

Requirements:
- install dependencies from `pyproject.toml` and `uv.lock`
- copy app source and static files
- expose `8000`
- run Uvicorn with the FastAPI app
- disable bytecode
- unbuffer stdout

The image should be production-lean enough for deployment, not only dev use.

### Compose File

Provide `search_ui/docker-compose.yml` with one service:

- `search-ui`
- builds from local Dockerfile
- loads `.env`
- maps `8000:8000`
- adds `host.docker.internal:host-gateway`
- restart policy `unless-stopped`

No Solr/Ollama containers in v1.

## Backend Implementation Details

### Internal Modules

#### `config.py`
Responsibilities:
- load and validate env vars
- expose typed settings object
- provide defaults

Preferred implementation:
- Pydantic settings if already acceptable in dependencies
- otherwise a minimal dataclass-based config layer

#### `models.py`
Define request/response schemas:
- `SearchRequest`
- `SearchResult`
- `SearchDebug`
- `SearchResponse`
- `ConfigResponse`
- `HealthResponse`

#### `clients/ollama.py`
Responsibilities:
- call embeddings endpoint
- parse response
- raise meaningful exceptions on:
  - timeout
  - connection failure
  - malformed response
  - empty embedding list
  - wrong vector size

#### `clients/solr.py`
Responsibilities:
- build vector query
- build keyword query
- escape keyword query text
- send request via `httpx`
- normalize docs
- return raw debug info

### Error Handling

Map errors to user-safe HTTP responses:

- invalid input -> `422`
- Solr unavailable -> `502`
- embedding service unavailable -> `502`
- malformed upstream response -> `502`
- unexpected internal failure -> `500`

Response body for handled errors:
```json
{
  "detail": "Human-readable message"
}
```

The frontend must display `detail` directly for handled failures.

## Frontend Specification

### `index.html`

Sections:
- page header with concise title
- search form
- result container
- debug container

No external JS/CSS CDNs in v1 unless strictly necessary.

### `app.js`

Responsibilities:
- load config from `/config`
- handle form submission
- disable inputs while searching
- call `/search`
- render results
- render empty/loading/error states
- render debug info

Implementation constraints:
- vanilla JS only
- no bundler
- no framework
- no local storage required in v1

### `styles.css`

Keep styling simple but intentionally clean:
- readable spacing
- clear form controls
- result cards
- responsive layout
- mobile-friendly single column
- max content width centered on page

## Acceptance Criteria

The implementation is complete when all are true:

1. `docker compose up --build` inside `search_ui/` starts the app successfully.
2. Opening `http://localhost:8000` shows the search page.
3. `GET /health` returns `{"status":"ok"}`.
4. `GET /config` returns supported modes and top-k settings.
5. Submitting a vector search triggers:
   - embedding generation
   - Solr vector query
   - rendered results or a useful empty/error state
6. Submitting a keyword search triggers:
   - Solr text query
   - rendered results or a useful empty/error state
7. Debug information is shown after each search.
8. App configuration is controlled entirely by environment variables.
9. The container can reach Solr and Ollama using configured URLs without code changes.
10. A log file is created in `.ai/logs/` documenting the implementation.

## Test Cases and Scenarios

### API Tests

At minimum, add tests for:

- `GET /health` returns 200 and expected payload
- `GET /config` returns configured defaults
- `POST /search` rejects empty query
- `POST /search` rejects unsupported mode
- `POST /search` rejects out-of-range `top_k`
- vector search success path with mocked embedding and mocked Solr response
- keyword search success path with mocked Solr response
- embedding API timeout maps to `502`
- Solr timeout maps to `502`
- embedding wrong vector size maps to `502`
- Solr returns empty docs -> response contains empty `results`

Preferred stack:
- `pytest`
- FastAPI test client
- mocked `httpx` calls

### Manual Verification

Manual scenarios to run:

1. Valid vector query with expected results
2. Valid keyword query with expected results
3. Query with no matches
4. Solr intentionally stopped
5. Ollama intentionally stopped for vector mode
6. Very short/blank query
7. `top_k=1`
8. `top_k=50`
9. Narrow browser width/mobile layout

## Documentation Changes

Add `search_ui/README.md` with:

- purpose of the app
- required external services
- env vars
- local run instructions
- Docker run instructions
- example curl requests
- troubleshooting section for:
  - cannot reach Solr
  - cannot reach Ollama
  - wrong vector size
  - empty results

## Logging / AI Audit Requirement

Per repo instruction, create a log file in `.ai/logs/` after implementation.

Required content:
- summary of added FastAPI app
- Docker packaging summary
- endpoints added
- any assumptions made about Solr fields and vector search syntax

Suggested filename:
- `.ai/logs/2026-03-26-fastapi-search-ui.md`

## Explicit Assumptions and Defaults

These assumptions will be used unless implementation discovers a hard incompatibility:

- Solr collection name default: `embeddings`
- Solr vector field name: `vector`
- Solr title/display field: `ti`
- Solr keyword field: `ti`
- Solr docs expose `score`
- Ollama embeddings endpoint is compatible with current repo usage
- expected embedding size default: `768`
- keyword mode will query only `ti` in v1
- results will display a flat list, not grouped or side-by-side comparisons
- hybrid search is out of scope for this implementation, but the backend structure must allow adding it later without breaking the `POST /search` contract

## Implementation Order

1. Create isolated `search_ui/` Python project and dependencies
2. Implement typed config and API schemas
3. Implement Ollama and Solr clients
4. Implement FastAPI routes and static asset mounting
5. Implement the HTML/CSS/JS UI
6. Add Dockerfile, Compose file, `.env.example`
7. Add automated API tests
8. Write README
9. Add `.ai/logs/` implementation record

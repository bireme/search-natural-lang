# Embedding Generator

Two-stage pipeline that generates vector embeddings from MongoDB documents and indexes them into Solr.

**Data flow:** MongoDB Source → (Ollama API) → MongoDB Embeddings → Solr

## Setup

Copy and configure the environment file:
```bash
cp .env.example .env
```

That is all — the Docker image is built automatically the first time you run a target.

## Usage

Generate embeddings from source documents:
```bash
make generate_embeddings
make generate_embeddings args="--limit 100 --dry-run"
make generate_embeddings args="--embedding-fields 'ti,ti_pt,ab'"
```

Load embeddings into Solr:
```bash
make load_solr
make load_solr args="--clear --batch-size 200"
```

Open a shell in the container:
```bash
make sh
```

The image contains only the Python runtime and the project dependencies; the working
directory is mounted into the container at run time, so every target always runs the
current code — no rebuild after editing a script. `make` rebuilds the image on its own
whenever `Dockerfile`, `pyproject.toml` or `uv.lock` changes (or the image is missing);
`make build` forces a rebuild.

### CLI Options

Both scripts support:
- `--dry-run` — run without writing data
- `--limit N` — process only N documents
- `--filter '{"key": "value"}'` — MongoDB query filter
- `--since <ObjectId>` — resume from a specific document
- `-v` — verbose (DEBUG) logging

`generate_embeddings.py` also supports:
- `--embedding-fields 'ti,ab'` — comma-separated document fields concatenated to build the embedding text (overrides the `EMBEDDING_FIELDS` env var; default: `ti,ti_pt,ti_es,ti_en`)
- `--max-retries N` — cursor re-creation attempts on CursorNotFound (default: 10)
- `--save-progress` / `--resume` — persist and resume from `.embeddings_progress.json`

`load_solr.py` also supports:
- `--batch-size N` — documents per Solr batch (default: 100)
- `--clear` — delete all Solr documents before loading

## Requirements

- MongoDB instance (source documents + embeddings storage)
- Ollama with embedding model installed (default: nomic-embed-text)
- Solr instance with a configured collection

# Embedding Generator

Two-stage pipeline that generates vector embeddings from MongoDB documents and indexes them into Solr.

**Data flow:** MongoDB Source → (Ollama API) → MongoDB Embeddings → Solr

## Setup

1. Copy and configure the environment file:
```bash
cp .env.example .env
```

2. Build the Docker image:
```bash
make dev_build
```

## Usage

Generate embeddings from source documents:
```bash
make dev_generate_embeddings
make dev_generate_embeddings args="--limit 100 --dry-run"
make dev_generate_embeddings args="--embedding-fields 'ti,ti_pt,ab'"
```

Load embeddings into Solr:
```bash
make dev_load_solr
make dev_load_solr args="--clear --batch-size 200"
```

Open a shell in the container:
```bash
make dev_sh
```

The `dev_*` targets mount the working directory into the container, so they always run
the current code. The targets without the prefix use the production image, which has the
scripts **baked in at build time** — rebuild it with `make build` after changing a script,
otherwise the container keeps running the version from when the image was built (this is
what causes `error: unrecognized arguments: --embedding-fields`).

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

## Production

Build a standalone image with scripts baked in (no volume mount needed):
```bash
make build
make generate_embeddings args="--limit 100"
make load_solr args="--clear"
```

Re-run `make build` after every change to `generate_embeddings.py` or `load_solr.py`.

## Requirements

- MongoDB instance (source documents + embeddings storage)
- Ollama with embedding model installed (default: nomic-embed-text)
- Solr instance with a configured collection

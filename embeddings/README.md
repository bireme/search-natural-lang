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
make build
```

## Usage

Generate embeddings from source documents:
```bash
make generate_embeddings
make generate_embeddings args="--limit 100 --dry-run"
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

### CLI Options

Both scripts support:
- `--dry-run` — run without writing data
- `--limit N` — process only N documents
- `--filter '{"key": "value"}'` — MongoDB query filter
- `--since <ObjectId>` — resume from a specific document
- `-v` — verbose (DEBUG) logging

`load_solr.py` also supports:
- `--batch-size N` — documents per Solr batch (default: 100)
- `--clear` — delete all Solr documents before loading

## Production

Build a standalone image with scripts baked in (no volume mount needed):
```bash
make build-prod
make generate_embeddings-prod args="--limit 100"
make load_solr-prod args="--clear"
```

## Requirements

- MongoDB instance (source documents + embeddings storage)
- Ollama with embedding model installed (default: nomic-embed-text)
- Solr instance with a configured collection

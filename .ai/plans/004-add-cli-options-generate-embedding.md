# Plan: Add CLI options and progress improvements to generate_embeddings.py

## Context
`load_solr.py` was recently enhanced with CLI arguments (argparse) and progress reporting (%, rate, ETA). `generate_embeddings.py` lacks these features — it has no CLI interface, loads all documents into memory at once, and logs every single document individually without periodic progress summaries.

## Changes to `embeddings/generate_embeddings.py`

### 1. Add argparse CLI options
Add a `parse_args()` function with the following flags (mirroring `load_solr.py`):
- `--limit N` — process only the first N documents
- `--filter '{"key": "val"}'` — MongoDB query filter as JSON string
- `--since <ObjectId>` — resume from a given MongoDB ObjectId
- `--dry-run` — generate embeddings but skip saving to MongoDB
- `-v / --verbose` — enable DEBUG-level logging

### 2. Add periodic progress reporting
- Add `PROGRESS_INTERVAL = 10` constant
- In the main loop, report progress every 10 seconds with: `Progress: X.X% (idx/total) | X.X docs/sec | ETA: Xs`
- Remove per-document `logger.info` for "Processing document..." and "Saved embedding..." — demote these to `logger.debug`

### 3. Stream documents instead of loading all into memory
- Replace `documents = list(source_collection.find(...))` with a streaming cursor
- Use `count_documents()` for total count (like `load_solr.py`)
- Respect `--limit` on both cursor and total count

### 4. Use context managers for MongoDB connections
- Replace manual `source_client.close()` / `embeddings_client.close()` with `with MongoClient(...) as client:` pattern

### 5. Add last processed document ID to summary
- Track `last_doc_id` and print it at the end (useful for `--since` resume)

### 6. Add throughput to summary
- Add `docs/sec` to the final summary (like `load_solr.py`)

### 7. Remove dead code
- Lines 81-83 in `generate_embeddings.py` are unreachable (after a `return` on line 80) — remove them

## Files to modify
- `embeddings/generate_embeddings.py` — all changes

## New imports needed
- `argparse` (stdlib)
- `bson.ObjectId` (already a dependency via pymongo)

## Verification
1. `python embeddings/generate_embeddings.py --help` — should display all CLI options
2. `python embeddings/generate_embeddings.py --dry-run --limit 5 -v` — should process 5 docs without saving, with debug output
3. `python embeddings/generate_embeddings.py --limit 10` — should show periodic progress and final summary with throughput

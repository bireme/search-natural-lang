# Plan: Improve `load_solr.py`

## Context

`load_solr.py` is a batch ETL script that reads embeddings from MongoDB and loads them into Solr. It works today but lacks operational conveniences (CLI args, progress reporting, resume support) and has a few minor bugs. The companion script `generate_embeddings.py` shares similar patterns but each script is self-contained.

## Changes

### Files to modify
- `embeddings/load_solr.py` — all improvements below
- `embeddings/.env.example` — add `SOLR_BATCH_SIZE` variable

---

### 1. Bug fix: Solr URL log inconsistency
Line 234 logs `SOLR_EMBEDDINGS_URL/solr/COLLECTION` but the actual URL pattern has no `/solr/` prefix. Fix to match reality.

### 2. Make `BATCH_SIZE` configurable via env
```python
BATCH_SIZE = int(os.getenv("SOLR_BATCH_SIZE", "100"))
```

### 3. Add CLI arguments via `argparse`
Add `parse_args()` returning a namespace with:
- `--batch-size` (int) — overrides env/default
- `--dry-run` (flag) — build docs but skip HTTP sends, log instead
- `--clear` (flag) — delete all Solr docs before loading (`{"delete": {"query": "*:*"}}`)
- `--limit N` (int) — process only first N documents
- `--filter` (JSON string) — MongoDB query filter, default `{}`
- `--since` (string) — ObjectId to resume from (`{"_id": {"$gt": ObjectId(since)}}`)
- `--verbose` / `-v` — set log level to DEBUG

Wrap dry-run check at the call site in `main()` rather than threading a flag through helper functions.

### 4. Add `clear_solr(client)` helper
Posts `{"delete": {"query": "*:*"}}` to the update endpoint and commits. Called when `--clear` is passed.

### 5. Add vector validation in `build_solr_document`
- Warn and drop `vector` field if it's not a non-empty list
- Warn if `len(vector) != vector_size` when both are present

### 6. Add periodic progress reporting
Every 10 seconds during processing, log:
```
Progress: 45.2% (4520/10000) | 312.5 docs/sec | ETA: 17s
```

### 7. Add throughput metrics to final summary
Compute and log `docs/sec` alongside the existing total time.

### 8. Log last processed document ID
At end of run, log the `_id` of the last document processed so operators can pass it to `--since` on the next run.

---

## What NOT to do
- **No async/await** — marginal gain for a batch script, adds complexity
- **No retry with backoff** — current per-document fallback is sufficient
- **No rate limiting** — batch size is the natural throttle

## Verification
1. Run `uv run python load_solr.py --dry-run --limit 10` — should log 10 docs without sending to Solr
2. Run `uv run python load_solr.py --dry-run --limit 10 --verbose` — should show DEBUG output
3. Run `uv run python load_solr.py --clear --dry-run` — should log the delete operation
4. Run against a real Solr instance with `--limit 50` to verify actual indexing
5. Verify progress reporting appears during a larger run

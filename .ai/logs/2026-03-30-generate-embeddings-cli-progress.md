# Add CLI options and progress reporting to generate_embeddings.py

**Date:** 2026-03-30

## Summary

Ported CLI and progress reporting improvements from `load_solr.py` to `generate_embeddings.py`.

## Changes made to `embeddings/generate_embeddings.py`

- **Added argparse CLI**: `--limit`, `--filter`, `--since`, `--dry-run`, `-v/--verbose`
- **Added periodic progress reporting**: logs progress %, docs/sec, and ETA every 10 seconds instead of per-document logging
- **Switched to streaming cursor**: replaced `list(collection.find(...))` with a streaming cursor and `count_documents()` to avoid loading all documents into memory
- **Added context managers**: MongoDB connections now use `with` statements for proper cleanup
- **Demoted per-document logs to DEBUG**: reduced noise at INFO level; use `--verbose` to see per-document details
- **Added throughput and last document ID to summary**: useful for monitoring and resuming with `--since`
- **Removed dead code**: unreachable lines 81-83 (after an earlier `return` statement)

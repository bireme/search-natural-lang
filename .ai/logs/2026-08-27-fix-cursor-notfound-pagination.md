# Fix CursorNotFound loop in generate_embeddings.py

**Date:** 2026-08-27

## Problem

The run in `embeddings/outs/bde_ti_mh_1.txt` hit `CursorNotFound` 7 times in 8 hours at only 15 %
of 29 869 documents. Failures landed on exact multiples of `batch_size(500)`: at 0.2 docs/sec a
500-doc batch takes ~42 min to consume, against MongoDB's 10-minute idle-cursor timeout. On top of
that, `retry_count` was never reset, so `--max-retries 10` was a lifetime budget — the run was
headed for `Max retries exceeded` at ~20 %.

## Changes

**File:** `embeddings/generate_embeddings.py`

### Keyset pagination replaces the long-lived cursor
- Each iteration fetches one page with `find(query).sort("_id", 1).limit(page_size)` and drains it
  into a list immediately, so the server-side cursor is closed before any embedding API call.
- The next page is fetched with `{"_id": {"$gt": last_doc_id}}` — the same resume mechanism as
  before, now on the happy path instead of the error path.
- Loop ends on an empty/short page or when `--limit` is reached.
- Removed `.batch_size(500)`.

### Per-incident retry budget
- `retry_count` resets to 0 after each successfully processed page, so `--max-retries` counts
  *consecutive* failures. Help text updated.
- The handler now also catches `AutoReconnect` and `OperationFailure` (previously these escaped and
  aborted the run), with exponential backoff capped at 30 s.

### New CLI option
- `--page-size N` — documents per query (default: 200), validated `>= 1` and logged at startup.

Unchanged: text assembly from `--embedding-fields`, the embedding call, the idempotent upsert on
`document_id`, progress/ETA reporting, `--save-progress` / `--resume` / `--since`.

## Verification

Against `PLN_BD.bde_teste`, all dry runs: `--limit 25 --page-size 10` → 25 docs in 3 pages;
`--limit 20 --page-size 7 --save-progress` → 20 docs in pages 7/7/6; `--resume` → correctly picked
up after the saved `_id`. No `CursorNotFound` in any run.

See `.ai/plans/008-keyset-pagination-embeddings.md` (supersedes 007).

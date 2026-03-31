# Handle CursorNotFound Error & Auto-Resume in generate_embeddings.py

**Date:** 2026-03-31

## Problem

When processing ~41k documents, the MongoDB server-side cursor times out after ~20% progress (error code 43: `CursorNotFound`), causing the script to terminate entirely.

## Changes

**File:** `embeddings/generate_embeddings.py`

### Auto-retry on CursorNotFound
- Imported `pymongo.errors.CursorNotFound` for specific error handling
- Wrapped the cursor iteration in a retry loop that catches `CursorNotFound`, re-creates the cursor from the last processed `_id`, and continues processing
- Added `--max-retries` CLI argument (default: 10) to cap re-creation attempts

### Cursor optimization
- Added `.sort("_id", 1)` for deterministic ordering (required for reliable resume)
- Added `.batch_size(500)` to reduce cursor idle time between fetches

### Progress persistence
- Added `--save-progress` flag that periodically writes last processed `_id` to `.embeddings_progress.json`
- Added `--resume` flag that reads the progress file on startup and resumes from the saved position
- Progress is also saved on each `CursorNotFound` retry before re-creating the cursor

### New CLI options
- `--max-retries N` — max cursor re-creation attempts (default: 10)
- `--save-progress` — save progress to `.embeddings_progress.json`
- `--resume` — resume from saved progress file (overrides `--since`)

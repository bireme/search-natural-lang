# Handle CursorNotFound Error & Auto-Resume in generate_embeddings.py

## Context

When processing ~41k documents at ~0.9 docs/sec, the MongoDB server-side cursor times out (error code 43: `CursorNotFound`) after ~20% progress, killing the entire script. The script already has `--since` for manual resume via ObjectId, but the user needs **automatic recovery** so the script doesn't stop on cursor timeout.

## Root Cause

MongoDB server-side cursors have a default 10-minute idle timeout. Since embedding generation is slow (~1 doc/sec), the server may close the cursor between batch fetches. The current code wraps the entire cursor loop in a single try/finally with no recovery mechanism.

## Changes — `embeddings/generate_embeddings.py`

### 1. Add `batch_size` to cursor configuration
- Set `batch_size(500)` on the cursor (matching the pattern in `load_solr.py`) to fetch smaller batches and reduce cursor idle time between fetches.

### 2. Wrap cursor iteration with auto-retry on CursorNotFound
- Instead of a single `for doc in cursor` loop, wrap it in a retry loop that catches `pymongo.errors.CursorNotFound`.
- On `CursorNotFound`, log a warning, re-create the cursor using `{"_id": {"$gt": last_doc_id}}` to resume from where it left off, and continue processing.
- Add a configurable max retry count (default 10) to prevent infinite loops. Add a `--max-retries` CLI argument.

### 3. Add `--save-progress` CLI option
- When enabled, periodically write the last processed `_id` to a progress file (`.embeddings_progress.json` in the working directory).
- On startup, if `--resume` flag is passed and the progress file exists, automatically set the `_id` filter to resume from the saved position.
- This complements `--since` (manual resume) with an automatic mechanism.

### 4. Sort cursor by `_id`
- Add `.sort("_id", 1)` to ensure deterministic ordering, which is required for reliable resume behavior.

## Implementation Details

```python
# New imports
from pymongo.errors import CursorNotFound

# New CLI args
--max-retries N    # Max cursor re-creation attempts (default: 10)
--save-progress    # Save last processed _id to progress file
--resume           # Resume from saved progress file

# Core retry logic (pseudocode)
retry_count = 0
while retry_count <= max_retries:
    query = merge(mongo_filter, {"_id": {"$gt": last_doc_id}} if last_doc_id else {})
    cursor = collection.find(query).sort("_id", 1).batch_size(500)
    try:
        for doc in cursor:
            process(doc)
            last_doc_id = doc["_id"]
        break  # completed successfully
    except CursorNotFound:
        retry_count += 1
        logger.warning("Cursor lost, resuming from %s (retry %d/%d)", last_doc_id, retry_count, max_retries)
    finally:
        cursor.close()
```

## Files to Modify

- `embeddings/generate_embeddings.py` — all changes in this single file

## Verification

1. `python generate_embeddings.py --dry-run --limit 10 -v` — confirm basic functionality still works
2. `python generate_embeddings.py --dry-run --limit 10 --save-progress` — confirm progress file is created
3. `python generate_embeddings.py --dry-run --limit 10 --resume` — confirm resume from progress file works
4. Full run against production MongoDB to verify CursorNotFound recovery

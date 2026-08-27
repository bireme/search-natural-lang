# Keyset Pagination in generate_embeddings.py (supersedes 007)

## Context

The run logged in `embeddings/outs/bde_ti_mh_1.txt` (29 869 docs, `qwen3-embedding:8b`) hit
`CursorNotFound` **7 times in 8 hours** while reaching only 15 % of the collection — on track to
exhaust the retry budget and abort around 20 %, the same symptom [007](007-handle-cursor-not-found-auto-resume.md)
set out to fix.

## Root Cause

Two problems, both in the retry loop added by 007.

### 1. `batch_size(500)` made the timeout *more* likely, not less

007 correctly identified MongoDB's 10-minute idle-cursor timeout (`cursorTimeoutMillis`), but chose
`batch_size(500)` to "fetch smaller batches and reduce cursor idle time between fetches". That is
inverted: a **larger** batch means a **longer** gap between `getMore` calls, because the script
holds the batch while it makes one slow embedding API call per document.

The log proves it — every failure lands on an exact multiple of 500:

| doc index | time | |
|---|---|---|
| 1000 | 12:50 | retry 1/10 |
| 2000 | 14:01 | retry 2/10 |
| 2500 | 14:39 | retry 3/10 |
| 3000 | 15:20 | retry 4/10 |
| 3500 | 16:02 | retry 5/10 |
| 4000 | 16:48 | retry 6/10 |
| 4500 | 19:05 | retry 7/10 |

At the observed **0.2 docs/sec**, one 500-doc batch takes ~42 minutes to consume — four times the
10-minute reap. 007 assumed ~0.9 docs/sec; the current model is ~4.5× slower, which is why the
failures became frequent enough to drain the budget.

### 2. The retry budget was global, not per-incident

`retry_count` was initialised once before the loop and never reset after successful work, so
`--max-retries 10` was a lifetime budget of 10 cursor re-creations for the whole run — regardless of
how many thousands of documents succeeded in between. The `--help` text read as if it meant
consecutive failures.

No documents were ever lost or duplicated: the `last_doc_id` + `$gt` resume was correct and the
upsert on `document_id` is idempotent. The run simply could not finish.

## Decision

Keep everything 007 introduced — `sort("_id", 1)`, `$gt` resume, the progress file,
`--since`/`--resume`, the error handler — but move the `$gt` resume from the **error path** onto the
**happy path**:

```python
page = list(source_collection.find(query).sort("_id", 1).limit(page_size))
if not page:
    break
for doc in page:      # cursor already closed — nothing alive on the server
    ...               # embed + upsert, however slow
```

Draining the page with `list(...)` closes the server-side cursor in milliseconds, *before* any
embedding call. No cursor is alive while the API round-trips happen, so the idle timeout cannot fire
no matter how slow the model gets. `batch_size(500)` is dropped — meaningless once each page is a
single short-lived query.

### Alternatives rejected

- **Lower `batch_size` to 50** — one-line change, keeps a batch under the 10-min reap at today's
  speed, but breaks again if throughput drops below ~0.08 docs/sec. Papers over the cause.
- **`no_cursor_timeout=True`** — requires an explicit session, leaks a server-side cursor if the
  script crashes, and some managed deployments disallow it.

## Changes — `embeddings/generate_embeddings.py`

- Replaced the `while retry_count <= args.max_retries` retry loop with a keyset-pagination loop.
- Added `--page-size` (default 200), validated `>= 1`, logged at startup.
- `retry_count = 0` after each successfully processed page, so `--max-retries` now means
  *consecutive* failures; `--help` updated to say so.
- The handler also catches `AutoReconnect` and `OperationFailure`, with exponential backoff capped
  at 30 s. Previously those escaped to the outer `except Exception` and aborted the run.
- The per-document body (text assembly, embedding, upsert, progress reporting, `_save_progress`) is
  unchanged.

## Verification

Run against `PLN_BD.bde_teste`:

- `--dry-run --limit 25 --page-size 10` → 25 processed, 3 pages (10/10/5), 0 errors.
- `--dry-run --limit 20 --page-size 7 --save-progress` → 20 processed, pages 7/7/6, progress file
  written at `_id` `…4636c33b`.
- `--dry-run --limit 20 --page-size 7 --resume` → resumed after `…4636c33b`, next 20 processed.
- Wire-level check: the emitted command is `{"find": …, "sort": {"_id": 1}, "limit": N}` with no
  `getMore` follow-ups.


## Final resume

**The 10 retries are global.** `retry_count` was initialised once before the loop and never reset after successful work — so `--max-retries 10` was a lifetime budget of 10 cursor re-creations for the whole run, not 10 consecutive failures. That's why the log climbed `retry 1/10` → `7/10` across 8 hours of otherwise-successful processing.

**And the cursor loss was systematic, not random.** Failures landed on exact multiples of `batch_size(500)` — 1000, 2000, 2500, 3000, 3500, 4000, 4500. At 0.2 docs/sec a 500-doc batch takes ~42 min to consume, against MongoDB's 10-min idle-cursor reap. The run was headed for `Max retries exceeded` at ~20 %.

Your instinct to check the history was right, and it paid off: `.ai/plans/007` had identified the correct root cause (the 10-minute timeout) but then picked `batch_size(500)` reasoning it would "reduce cursor idle time between fetches" — which is inverted. A larger batch means a *longer* gap between `getMore` calls. It also assumed ~0.9 docs/sec; `qwen3-embedding:8b` runs at 0.2, which is what tipped it from survivable into fatal.

## Changes — `embeddings/generate_embeddings.py`

- **Keyset pagination**: each page is `find(query).sort("_id", 1).limit(page_size)` drained into a list immediately, so no server-side cursor is alive during the API round-trips. The `$gt` resume from `1270540` is kept — just moved from the error path to the happy path. `batch_size(500)` dropped.
- **`--page-size N`** (default 200), validated and logged at startup.
- **`retry_count` resets after each successful page**, so `--max-retries` now means consecutive failures — matching what `--help` always claimed.
- The handler also catches `AutoReconnect` and `OperationFailure` (they previously escaped to the outer `except Exception` and killed the run), with backoff capped at 30 s.

Per-document logic is untouched.

## Verified against `PLN_BD.bde_teste` (all dry runs)

| test                                       | result                                       |
| ------------------------------------------ | -------------------------------------------- |
| `--limit 25 --page-size 10`                | 25 docs, 3 pages (10/10/5), 0 errors         |
| `--limit 20 --page-size 7 --save-progress` | 20 docs, pages 7/7/6, saved at `…4636c33b`   |
| `--limit 20 --page-size 7 --resume`        | resumed after `…4636c33b`, next 20 processed |

Wire-level confirmation from the pymongo command log: `{"find": …, "sort": {"_id": 1}, "limit": N}` with no `getMore` follow-ups. No `CursorNotFound` in any run.

Docs written: `.ai/plans/008-keyset-pagination-embeddings.md` (supersedes 007) and `.ai/logs/2026-08-27-fix-cursor-notfound-pagination.md`.

Two notes: I had to override `MONGODB_SOURCE_DATABASE`/`COLLECTION` for testing because `.env` now points at `FIs_transformation.02_iahx_xml_mis`, which is empty — I left `.env` untouched. And `.embeddings_progress.json` isn't in `.gitignore`; I deleted my test one, but you may want to add it. Nothing is committed.

To restart the stalled job: `--since 6a63b1e501f15c7e463776d7 --save-progress`.

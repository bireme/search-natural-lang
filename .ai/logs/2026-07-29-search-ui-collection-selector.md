# 2026-07-29 — Search UI: select the Solr collection

## Summary

`SOLR_COLLECTION` in `search_ui/.env` now accepts a comma-separated list of collections. The UI shows a collection selector and each search runs against the chosen collection.

## Changes

### `app/config.py`

- `solr_collections` property parses `SOLR_COLLECTION` on commas, trimming whitespace and dropping empty entries.
- `default_solr_collection` returns the first entry (raises if the list is empty).
- `solr_select_url` changed from a property to a method taking a collection name.

### `app/clients/solr.py`

- `SolrClient` now takes `base_url` + `default_collection` instead of a precomputed `select_url`.
- `select_url(collection=None)` builds the per-collection endpoint.
- `search_vector` / `search_keyword` accept an optional `collection`; `_send_query` posts to that collection's select URL.
- `SolrQueryResult` carries the `collection` used.

### `app/models.py`

- `ConfigResponse`: added `collections` and `default_collection`.
- `SearchRequest`: added optional `collection` (defaults to the configured default).
- `SearchResponse`: added `collection`.

### `app/main.py`

- Builds the Solr client from base URL + default collection.
- `/config` exposes the collection list and default.
- `/search` resolves the requested collection, rejects unknown values with HTTP 422 (`Unknown collection 'x'. Available: ...`), and passes it to the Solr client. The response echoes the collection used.

### Front end (`static/`)

- New `#collection` select in the field row, populated from `/config` with the default preselected.
- Disabled while a search is in flight; sent in the `/search` payload.
- Debug panel shows the collection used.
- `.field-row` grid widened from 3 to 4 columns (mobile still collapses to one).

### Docs & tests

- `.env.example` and `README.md` document the comma-separated format.
- Existing Solr stubs updated for the new `collection` argument; new tests cover single-value backward compatibility, trimming/empty-entry handling, explicit selection, default selection, unknown-collection rejection, and per-collection select URLs.

## Verification

`uv run pytest -q` in `search_ui/` — 17 passed.

## Notes

- A single value with no commas behaves exactly as before.
- Scope limited to `search_ui/`; `embeddings/` untouched.

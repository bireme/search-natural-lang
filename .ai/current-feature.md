# Current Feature: Select Solr Collection in Search UI

## Status

Completed

## Goals

- Allow `SOLR_COLLECTION` in `search_ui/.env` to hold a comma-separated list of collections (e.g. `SOLR_COLLECTION=embeddings,embeddings_v2`).
- Parse that list in `app/config.py` into an ordered list of collection names, keeping the first entry as the default.
- Expose the available collections to the UI (via template context or an API endpoint) so the front end doesn't hardcode them.
- Add a collection selector control to the search UI (`app/static/index.html` / `app.js` / `styles.css`) preselected with the default collection.
- Send the selected collection with the search request and have the backend query that collection in `app/clients/solr.py` instead of a fixed one.
- Validate the requested collection against the configured list; reject unknown values with a clear error.
- Keep backward compatibility: a single value with no commas behaves exactly as today.
- Update `.env.example`, `README.md`, and tests (`tests/test_app.py`) to cover the multi-collection behavior.

## Notes

- Inline spec (no file in `.ai/features/`): "Implement at search_ui the possibility to select the SOLR_COLLECTION to search, the list must be read from the .env SOLR_COLLECTION environment using a list separated by comma".
- Scope is limited to `search_ui/`; the `embeddings/` scripts are untouched.
- Current config reads `SOLR_COLLECTION` as a single string; `SOLR_BASE_URL` + collection form the query URL.
- Entries should be trimmed of whitespace and empty items dropped.

## History

- 2026-07-29: Starting Select Solr Collection in Search UI

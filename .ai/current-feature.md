# Current Feature: Configurable EMBEDDING_FIELDS in generate_embeddings

## Status

Completed

## Goals

- Add an `--embedding-fields` CLI argument to `embeddings/generate_embeddings.py` accepting a comma-separated list of document fields to concatenate when generating an embedding.
- Rename the module constant `TEXT_IN_FIELDS` to `EMBEDDING_FIELDS` and read it from the `EMBEDDING_FIELDS` env var, matching the other config constants; default stays `ti,ti_pt,ti_es,ti_en`.
- Parse the value into a clean list (trim whitespace, drop empty entries), with precedence CLI flag > env var > built-in default.
- Replace the module-level `TEXT_IN_FIELDS` reads in `main()` (config log line, text collection loop, and the "no content" warning) with the resolved per-run list.
- Keep the effective field list visible in the startup configuration log so runs are reproducible.
- Reject a value that resolves to an empty list with a clear error message instead of silently embedding nothing.
- Update `embeddings/README.md` and `embeddings/.env.example` to document the new argument and env var.

## Notes

- Inline spec (no file in `.ai/features/`): "Create and implement a new argument at generate_embeddings script to allow inform the TEXT_IN_FIELDS list of fields to be concatenate in the embedding generation."
- Scope is limited to `embeddings/`; `search_ui/` is untouched.
- Current state: `TEXT_IN_FIELDS` is a hardcoded module constant at `embeddings/generate_embeddings.py:42`, used at lines 205, 287, and 303.
- Existing args follow argparse conventions in `parse_args()` (`--dry-run`, `--limit`, `--filter`, `--since`, `--max-retries`, `--save-progress`, `--resume`, `-v/--verbose`).
- Backward compatibility: running without the new flag must behave exactly as today.
- Resolved during implementation: the default is env-overridable via `EMBEDDING_FIELDS`, and the constant/CLI/local variable were renamed to the `embedding_fields` wording at the user's request.
- `TEXT_OUT_FIELD` was intentionally left unrenamed.

## History

- 2026-07-29: Starting Configurable EMBEDDING_FIELDS in generate_embeddings
- 2026-07-29: Starting Select Solr Collection in Search UI
- 2026-07-29: Completed Select Solr Collection in Search UI — `SOLR_COLLECTION` now accepts a comma-separated list; the UI gained a collection selector fed by `/config`, `/search` validates and echoes the chosen collection, and the Solr client builds a per-collection select URL. Log: [2026-07-29-search-ui-collection-selector.md](.ai/logs/2026-07-29-search-ui-collection-selector.md)

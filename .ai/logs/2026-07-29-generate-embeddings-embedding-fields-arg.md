# 2026-07-29 — `--embedding-fields` argument for generate_embeddings

## Summary

Added a configurable list of document fields concatenated to build the embedding input in
`embeddings/generate_embeddings.py`, replacing the previously hardcoded `TEXT_IN_FIELDS` constant.
The list is set with the `EMBEDDING_FIELDS` env var and can be overridden per run with
`--embedding-fields`.

## Changes

### `embeddings/generate_embeddings.py`

- `TEXT_IN_FIELDS` renamed to `EMBEDDING_FIELDS` and read from the environment, matching the other
  config constants: `os.getenv("EMBEDDING_FIELDS", "ti,ti_pt,ti_es,ti_en")` (comma-separated string).
- New `--embedding-fields` argument in `parse_args()`, taking a comma-separated list; the help text
  shows the effective default.
- New `parse_embedding_fields(value)` helper: falls back to `EMBEDDING_FIELDS` when the argument is
  omitted (`None`), splits on commas, trims whitespace, drops empty entries, and raises `ValueError`
  when nothing usable remains — including an explicitly passed empty value, which must not silently
  fall back to the default.
- `main()` resolves the list once up front into `embedding_fields`, logging the error and returning
  on an empty/invalid value. The three previous `TEXT_IN_FIELDS` reads (config log line, the
  field-collection loop, and the "no content in any of the fields" warning) now use it. The config
  log line reads `Embedding Fields: [...]`.
- `TEXT_OUT_FIELD` is unchanged.

### `embeddings/.env.example`

- Added `EMBEDDING_FIELDS=ti,ti_pt,ti_es,ti_en` under the embedding model section.

### `embeddings/README.md`

- Added a usage example: `make generate_embeddings args="--embedding-fields 'ti,ti_pt,ab'"`.
- Added a `generate_embeddings.py` CLI options section documenting `--embedding-fields` alongside
  the previously undocumented `--max-retries`, `--save-progress`, and `--resume`.

## Verification

- `uv run python generate_embeddings.py --help` shows the new argument and its default.
- `parse_embedding_fields` checked directly: `None` → `['ti','ti_pt','ti_es','ti_en']`;
  `" ti , ab ,, ti_pt "` → `['ti','ab','ti_pt']`; `" , "` and `""` → `ValueError`; with
  `EMBEDDING_FIELDS` set to `"ab, ti_en"`, `None` → `['ab','ti_en']` and an explicit `"ti"` → `['ti']`.
- `uv run python generate_embeddings.py --embedding-fields " , "` exits after logging the error,
  before opening any MongoDB connection.
- The Makefile targets run the container with `--env-file .env`, so `EMBEDDING_FIELDS` reaches the
  script in Docker with no extra wiring.

## Notes

- Backward compatible: with neither the env var nor the flag set, behavior matches the previous
  hardcoded field list exactly.
- Precedence is CLI flag > `EMBEDDING_FIELDS` env var > built-in default.

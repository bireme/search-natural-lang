# 2026-08-18 — `--embedding-fields` help text + diagnosis of "unrecognized arguments"

## Reported error

```
usage: generate_embeddings.py [-h] [--dry-run] [--limit LIMIT] [--filter FILTER]
                              [--since SINCE] [--max-retries MAX_RETRIES]
                              [--save-progress] [--resume] [-v]
generate_embeddings.py: error: unrecognized arguments: --embedding-fields ti,ti_pt,...
```

## Diagnosis

The argument is **not missing from the source**. `embeddings/generate_embeddings.py` on
`main` defines `--embedding-fields` (added in `1d45de4`, 2026-07-29) and it parses
correctly — verified against the exact field list from the error report.

The `usage:` line in the error stops at `[-v]`, i.e. the process that produced it was
running the code as it existed *before* `1d45de4`. Cause: the production Makefile targets
(`make generate_embeddings` / `make load_solr`) run `embeddings:latest`, whose Dockerfile
`production` stage does `COPY generate_embeddings.py load_solr.py ./` — the scripts are
baked into the image with **no volume mount**. An image built before 2026-07-29 therefore
keeps serving the old script no matter what is on disk. The `dev_*` targets, which mount
`$(pwd)` into `/app`, are unaffected.

**Fix for the user:** run `make build` to rebuild the production image, or use
`make dev_generate_embeddings args="--embedding-fields '...'"` during development.

A contributing factor: the README documented `make build-prod`,
`make generate_embeddings-prod`, `make load_solr-prod` and `make sh` — none of which
exist in the Makefile — so the documented "rebuild" step could never have worked.

## Changes

- `embeddings/generate_embeddings.py`
  - Added an argparse `epilog` (with `RawDescriptionHelpFormatter`) showing worked
    `--embedding-fields` examples, the Makefile invocation form, and a note on how the
    fields are resolved (env override, empty fields skipped, joined with a space).
  - `--embedding-fields` now uses `metavar="FIELDS"` and its help states explicitly that
    it overrides the `EMBEDDING_FIELDS` env var.
- `embeddings/README.md`
  - Corrected all target names to the ones that actually exist (`dev_build`,
    `dev_generate_embeddings`, `dev_load_solr`, `dev_sh`, `build`).
  - Documented the dev-mount vs. production-baked-in distinction and called out the stale
    image as the cause of the `unrecognized arguments` error.
- `embeddings/Makefile`
  - Updated the stale `.PHONY` list to match the real targets.

## Verification

- `.venv/bin/python generate_embeddings.py --help` renders the new help and lists
  `--embedding-fields FIELDS`.
- Parsing `--embedding-fields ti,ti_pt,ti_es,ti_en,ab,ab_pt,ab_es,ab_en` yields the
  expected 8-element field list.

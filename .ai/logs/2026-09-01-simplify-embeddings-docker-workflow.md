# Simplify the embeddings Docker workflow

**Date:** 2026-09-01

## Problem

`embeddings/Dockerfile` had a `dev` stage (empty, code volume-mounted) and a `production`
stage that baked `generate_embeddings.py` / `load_solr.py` into the image. The Makefile
mirrored that split with two parallel target sets (`dev_*` and prod). Running the prod
targets after editing a script silently executed the stale, baked-in version — the cause of
the `error: unrecognized arguments: --embedding-fields` incident logged in
`2026-08-18-embedding-fields-help-and-stale-image-diagnosis.md`.

A self-contained image was never actually needed: the scripts are only ever run from a repo
checkout.

## Changes

- **`embeddings/Dockerfile`** — collapsed to a single stage. Removed `AS dev` / `AS production`
  and the `COPY generate_embeddings.py load_solr.py ./`. The image now carries only the
  Python runtime and dependencies. `uv sync` → `uv sync --locked` so a stale `uv.lock` fails
  the build instead of silently resolving something else (matches `search_ui/Dockerfile`).
  `UV_PROJECT_ENVIRONMENT=/opt/venv` keeps the venv outside `/app`, so the runtime mount
  cannot shadow it.

- **`embeddings/Makefile`** — one set of targets: `build`, `generate_embeddings`,
  `load_solr`, `sh`. All `dev_*` targets removed (`dev_sh` → `sh`). Every run target mounts
  `$(pwd):/app` and depends on an `image` guard that rebuilds via a `.docker-build-stamp`
  file whose prerequisites are `Dockerfile`, `pyproject.toml` and `uv.lock`; the guard also
  clears the stamp if the image itself was deleted. `build` forces a rebuild. Runs use
  `uv run --no-sync` so uv does not re-resolve against the mounted `pyproject.toml` on every
  invocation.

- **`embeddings/.dockerignore`** (new) — the build context only needs `pyproject.toml` and
  `uv.lock` now; excludes `.venv`, `__pycache__`, `.env`, `outs`, `references`, `.git`,
  `.docker-build-stamp`.

- **`embeddings/.gitignore`** — added `.docker-build-stamp`.

- **`embeddings/generate_embeddings.py`** — argparse epilog example referenced
  `make dev_generate_embeddings`; updated to `make generate_embeddings`.

- **`embeddings/README.md`** — dropped the build step from Setup, rewrote usage without the
  `dev_` prefix, and removed both the dev/prod explanation and the "Production" section
  along with the stale-image warning. Also corrected the `--max-retries` description (stale
  since the keyset-pagination change: it is consecutive page-fetch retries, not cursor
  re-creation on CursorNotFound) and documented the previously missing `--page-size`.

## Net effect

Editing a script and running `make generate_embeddings` now always runs the current code.
A rebuild happens only when dependencies or the Dockerfile change, and `make` triggers it
automatically — there is nothing left to forget.

## Verification

- Removed both images and the stamp: `make generate_embeddings args="--help"` built the
  image then ran the script.
- Added a temporary marker to the argparse help; the next run showed it with no rebuild.
- Second run went straight to the container (stamp current).
- `touch uv.lock` triggered a rebuild on the next target.
- `make dev_build` now fails with "No rule to make target".

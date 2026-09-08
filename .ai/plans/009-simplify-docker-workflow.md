# Simplify the embeddings Docker workflow

## Context

`embeddings/Dockerfile` has two stages: `dev` (empty — code arrives via `-v $(pwd):/app`)
and `production` (`COPY generate_embeddings.py load_solr.py ./`). `embeddings/Makefile`
therefore carries two parallel sets of targets (`dev_build`/`dev_generate_embeddings`/
`dev_load_solr`/`dev_sh` vs `build`/`generate_embeddings`/`load_solr`).

The production targets run code frozen at image-build time, so editing a script and running
`make generate_embeddings` silently executes the old version. This already bit us once —
`error: unrecognized arguments: --embedding-fields` (see
`.ai/logs/2026-08-18-embedding-fields-help-and-stale-image-diagnosis.md`), and the README
currently has to warn about it.

The image is only ever run from a repo checkout on this machine; a self-contained image is
not needed. So the fix is to stop baking code into the image at all: the image carries only
the Python runtime + dependencies, and the source is always mounted. One set of targets,
no `dev_` prefix, and a rebuild is needed only when dependencies change — which `make` will
detect and do on its own.

## Changes

### 1. `embeddings/Dockerfile` — collapse to a single stage

Drop both `AS dev` / `AS production` stages and the `COPY generate_embeddings.py load_solr.py ./`.
Keep everything else as-is (`python:3.14-alpine`, `UV_PROJECT_ENVIRONMENT=/opt/venv`,
`WORKDIR /app`, the `uv` binary copy).

```dockerfile
FROM python:3.14-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked
```

Two details that make the mount safe:
- `/opt/venv` lives outside `/app`, so `-v $(pwd):/app` cannot shadow the installed deps
  (this is already true today for the `dev_` targets).
- `--locked` makes the build fail loudly if `uv.lock` is stale instead of silently
  resolving something different (matches `search_ui/Dockerfile`, which uses
  `uv sync --locked --no-dev`).

### 2. `embeddings/Makefile` — one set of targets + auto-build

Delete `dev_build`, `dev_generate_embeddings`, `dev_load_solr`, `dev_sh`. Keep
`build`, `generate_embeddings`, `load_solr`, and rename `dev_sh` → `sh`. Every run target
mounts the working directory and depends on an `image` guard.

```make
#!make

.PHONY: build image generate_embeddings load_solr sh

IMAGE_NAME := embeddings
STAMP := .docker-build-stamp
DOCKER_RUN := docker run --rm --network host --env-file .env -v $$(pwd):/app $(IMAGE_NAME):latest
args ?=

# Rebuild whenever the Dockerfile or the dependency set changes.
$(STAMP): Dockerfile pyproject.toml uv.lock
	@docker build -t $(IMAGE_NAME):latest .
	@touch $@

# Guard used by every run target: also covers the image being deleted
# out from under a still-current stamp file.
image:
	@docker image inspect $(IMAGE_NAME):latest >/dev/null 2>&1 || rm -f $(STAMP)
	@$(MAKE) --no-print-directory $(STAMP)

# Force a rebuild (rarely needed — the run targets build on demand).
build:
	@rm -f $(STAMP)
	@$(MAKE) --no-print-directory $(STAMP)

generate_embeddings: image
	@$(DOCKER_RUN) uv run --no-sync python generate_embeddings.py $(args)

load_solr: image
	@$(DOCKER_RUN) uv run --no-sync python load_solr.py $(args)

sh: image
	@docker run --rm -it --network host --env-file .env -v $$(pwd):/app $(IMAGE_NAME):latest sh
```

Notes:
- `--no-sync` on `uv run` stops uv from re-resolving against the *mounted* `pyproject.toml`
  on every run (a latent slowdown in today's `dev_` targets). Dependency changes go through
  the image rebuild instead, which the stamp triggers automatically.
- The mount stays read-write: `generate_embeddings.py --save-progress` writes
  `.embeddings_progress.json` and `outs/` into the working directory.
- `sh` keeps its own `docker run` line because it needs `-it`, which `$(DOCKER_RUN)` omits.

### 3. `embeddings/.dockerignore` — new file

The build context currently ships `.venv/`, `__pycache__/`, `outs/`, `references/` and the
real `.env` to the daemon on every build. Only `pyproject.toml` and `uv.lock` are used now.

```
.venv
__pycache__
*.py[oc]
.env
outs
references
.git
.docker-build-stamp
```

### 4. `embeddings/.gitignore` — add `.docker-build-stamp`

### 5. `embeddings/README.md` — update

- Setup: drop the `make dev_build` step entirely; the first `make generate_embeddings`
  builds the image.
- Usage: rewrite the `dev_*` examples as `make generate_embeddings`, `make load_solr`,
  `make sh`.
- Delete the paragraph explaining the `dev_` vs production split and the
  `--embedding-fields` stale-image warning (lines 39–43) and the whole "Production"
  section (lines 63–72) — neither applies any more.
- Replace with a short note: the image holds only dependencies, code is mounted at runtime,
  and `make` rebuilds automatically when `pyproject.toml`/`uv.lock`/`Dockerfile` change
  (`make build` forces one).

### 6. `.ai/logs/2026-09-01-simplify-embeddings-docker-workflow.md`

Required by `AGENTS.md`/`CLAUDE.md`: summarize the change (single-stage image, dev/prod
target merge, auto-build stamp, dockerignore) and why (stale baked-in code).

## Verification

Run from `embeddings/`:

1. Clean slate — confirm auto-build works with no image present:
   ```bash
   docker image rm embeddings:dev embeddings:latest ; rm -f .docker-build-stamp
   make generate_embeddings args="--limit 1 --dry-run"
   ```
   Expect a `docker build` to run first, then the script to execute.

2. Code changes take effect with no rebuild — the actual bug being fixed:
   ```bash
   make generate_embeddings args="--help"        # note the output
   # add a temporary marker to generate_embeddings.py's argparse help, then:
   make generate_embeddings args="--help"        # marker appears, no build ran
   ```
   Revert the marker afterwards.

3. No rebuild on a second run: `make load_solr args="--limit 1 --dry-run"` should go
   straight to the container (stamp is current).

4. Dependency change triggers a rebuild: `touch uv.lock && make sh` should build first.

5. Confirm the removed targets are gone: `make dev_build` fails with
   "No rule to make target".

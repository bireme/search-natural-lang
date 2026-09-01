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
	@$(MAKE) -s --no-print-directory $(STAMP)

# Force a rebuild (rarely needed -- the run targets build on demand).
build:
	@rm -f $(STAMP)
	@$(MAKE) -s --no-print-directory $(STAMP)

generate_embeddings: image
	@$(DOCKER_RUN) uv run --no-sync python generate_embeddings.py $(args)

load_solr: image
	@$(DOCKER_RUN) uv run --no-sync python load_solr.py $(args)

sh: image
	@docker run --rm -it --network host --env-file .env -v $$(pwd):/app $(IMAGE_NAME):latest sh

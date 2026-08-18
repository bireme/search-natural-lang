#!make

.PHONY: dev_build dev_generate_embeddings dev_load_solr dev_sh build generate_embeddings load_solr

IMAGE_NAME := embeddings
args ?=

# Development build (default) -- expects volume mount
dev_build:
	@docker build --target dev -t $(IMAGE_NAME):dev .

# Development run helpers (volume-mounted code)
dev_generate_embeddings:
	@docker run --rm --network host --env-file .env -v $$(pwd):/app $(IMAGE_NAME):dev \
		uv run python generate_embeddings.py $(args)

dev_load_solr:
	@docker run --rm --network host --env-file .env -v $$(pwd):/app $(IMAGE_NAME):dev \
		uv run python load_solr.py $(args)

dev_sh:
	@docker run --rm -it --network host --env-file .env -v $$(pwd):/app $(IMAGE_NAME):dev sh

# Production run helpers (no volume mount)
build:
	@docker build --target production -t $(IMAGE_NAME):latest .

generate_embeddings:
	@docker run --rm --network host --env-file .env $(IMAGE_NAME):latest \
		uv run python generate_embeddings.py $(args)

load_solr:
	@docker run --rm --network host --env-file .env $(IMAGE_NAME):latest \
		uv run python load_solr.py $(args)

#!make

.PHONY: build build_no_cache generate_embeddings load_solr sh down

args ?=

build:
	@docker compose build

build_no_cache:
	@docker compose build --no-cache

generate_embeddings:
	@docker compose run --rm embeddings uv run python generate_embeddings.py

load_solr:
	@docker compose run --rm embeddings uv run python load_solr.py $(args)

sh:
	@docker compose run --rm embeddings sh

down:
	@docker compose down


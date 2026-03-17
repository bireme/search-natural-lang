#!make

# Docker DEV
COMPOSE_FILE_DEV=docker-compose-dev.yml

dev_build:
	@docker compose -f $(COMPOSE_FILE_DEV) build

dev_build_no_cache:
	@docker compose -f $(COMPOSE_FILE_DEV) build --no-cache

dev_generate_embeddings:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm embeddings uv run python generate_embeddings.py

dev_load_solr:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm embeddings uv run python load_solr.py

dev_sh:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm embeddings sh

dev_down:
	@docker compose -f $(COMPOSE_FILE_DEV) down


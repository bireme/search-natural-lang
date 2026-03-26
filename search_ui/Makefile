#!make

COMPOSE_FILE_DEV=docker-compose-dev.yml

.PHONY: build build_no_cache up down logs sh sync run test

args ?=

dev_build:
	@docker compose -f $(COMPOSE_FILE_DEV) build

dev_build_no_cache:
	@docker compose -f $(COMPOSE_FILE_DEV) build --no-cache

dev_run:
	@docker compose -f $(COMPOSE_FILE_DEV) up

dev_start:
	@docker compose -f $(COMPOSE_FILE_DEV) up -d

dev_down:
	@docker compose -f $(COMPOSE_FILE_DEV) down

dev_logs:
	@docker compose -f $(COMPOSE_FILE_DEV) logs -f search-ui

dev_sh:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm search-ui sh

dev_install_dev:
	@uv sync --dev

dev_install:
	@uv sync

run:
	@uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev_test:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm search-ui sh -c "uv run pytest $(args)"


build:
	@docker compose build

build_no_cache:
	@docker compose build --no-cache

start:
	@docker compose up

down:
	@docker compose down

logs:
	@docker compose logs -f search-ui

sh:
	@docker compose run --rm search-ui sh

sync_dev:
	@uv sync --dev

sync:
	@uv sync

run:
	@uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	@uv run pytest $(args)

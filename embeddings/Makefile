#!make

# app management commands
dev_deps:
	. ./set_env.sh && uv sync

dev_deps_all:
	. ./set_env.sh && uv sync --all-groups

dev_deps_upgrade:
	. ./set_env.sh && uv sync --upgrade

dev_run:
	. ./set_env.sh && uv run manage.py runserver 0.0.0.0:8000

dev_migrate:
	. ./set_env.sh && uv run manage.py migrate

dev_generate_embeddings:
	. ./set_env.sh && uv run python generate_embeddings.py


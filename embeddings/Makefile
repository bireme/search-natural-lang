#!make

# app management commands
install_deps:
	. ./set_env.sh && uv sync

install_deps_all:
	. ./set_env.sh && uv sync --all-groups

install_deps_upgrade:
	. ./set_env.sh && uv sync --upgrade

generate_embeddings:
	. ./set_env.sh && uv run python generate_embeddings.py

load_solr:
	. ./set_env.sh && uv run python load_solr.py


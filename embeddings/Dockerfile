########### BASE STAGE ###########
FROM python:3.14-alpine AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync

########### DEV STAGE ###########
FROM base AS dev
# App code provided via volume mount at runtime

########### PRODUCTION STAGE ###########
FROM base AS production
COPY generate_embeddings.py load_solr.py ./

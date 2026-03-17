########### BASE STAGE ###########
FROM python:3.13-alpine AS base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

########### DEV STAGE ###########
FROM base AS dev

COPY pyproject.toml uv.lock ./
RUN uv sync

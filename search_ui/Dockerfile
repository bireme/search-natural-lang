########### BASE STAGE ###########
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

########### DEV STAGE ###########
FROM base AS dev
# App code provided via volume mount at runtime
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

########### PRODUCTION STAGE ###########
FROM base AS production
COPY app ./app
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

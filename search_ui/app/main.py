from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.clients.ollama import (
    EmbeddingsClient,
    EmbeddingsMalformedResponseError,
    EmbeddingsUnavailableError,
)
from app.clients.solr import SolrClient, SolrMalformedResponseError, SolrUnavailableError
from app.config import Settings, get_settings
from app.models import ConfigResponse, HealthResponse, SearchDebug, SearchRequest, SearchResponse, SearchResult


STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    logging.basicConfig(level=getattr(logging, config.app_log_level.upper(), logging.INFO))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = config
        app.state.ollama_client = EmbeddingsClient(
            api_url=str(config.embeddings_api_url),
            model=config.embeddings_model,
            expected_vector_size=config.embeddings_vector_size,
            timeout_seconds=config.embeddings_timeout_seconds,
        )
        app.state.solr_client = SolrClient(
            select_url=config.solr_select_url,
            vector_field=config.solr_vector_field,
            title_field=config.solr_title_field,
            id_field=config.solr_id_field,
            record_id_field=config.solr_record_id_field,
            model_field=config.solr_model_field,
            keyword_qf=config.solr_keyword_qf,
            timeout_seconds=config.solr_timeout_seconds,
        )
        yield

    app = FastAPI(title="Solr Search UI", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        message = first_error.get("msg", "Invalid request.")
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        return JSONResponse(status_code=422, content={"detail": message})

    @app.get("/", response_class=FileResponse)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/config", response_model=ConfigResponse)
    async def get_config(request: Request) -> ConfigResponse:
        active_settings: Settings = request.app.state.settings
        return ConfigResponse(
            default_top_k=active_settings.app_default_top_k,
            max_top_k=active_settings.app_max_top_k,
            supported_modes=active_settings.supported_modes,
        )

    @app.post("/search", response_model=SearchResponse)
    async def search(payload: SearchRequest, request: Request) -> SearchResponse:
        active_settings: Settings = request.app.state.settings
        if payload.top_k > active_settings.app_max_top_k:
            raise HTTPException(
                status_code=422,
                detail=f"top_k must be between 1 and {active_settings.app_max_top_k}.",
            )

        solr_client: SolrClient = request.app.state.solr_client
        ollama_client: EmbeddingsClient = request.app.state.ollama_client

        started = time.perf_counter()
        try:
            embedding_model: str | None = None
            embedding_size: int | None = None

            if payload.mode == "vector":
                vector = await ollama_client.embed(payload.query)
                solr_result = await solr_client.search_vector(vector, payload.top_k)
                embedding_model = active_settings.embeddings_model
                embedding_size = len(vector)
            else:
                solr_result = await solr_client.search_keyword(payload.query, payload.top_k)

            results = [
                SearchResult.model_validate(solr_client.normalize_doc(doc))
                for doc in solr_result.docs
            ]
        except (EmbeddingsUnavailableError, SolrUnavailableError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except (EmbeddingsMalformedResponseError, SolrMalformedResponseError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="Unexpected internal error.") from exc

        took_ms = int((time.perf_counter() - started) * 1000)
        return SearchResponse(
            query=payload.query,
            mode=payload.mode,
            top_k=payload.top_k,
            took_ms=took_ms,
            results=results,
            debug=SearchDebug(
                solr_query=solr_result.solr_query,
                embedding_model=embedding_model,
                embedding_size=embedding_size,
                solr_rows=solr_result.rows,
            ),
        )

    return app


app = create_app()

from typing import Literal

from pydantic import BaseModel, Field, field_validator


SearchMode = Literal["vector", "keyword"]


class HealthResponse(BaseModel):
    status: str


class ConfigResponse(BaseModel):
    default_top_k: int
    max_top_k: int
    supported_modes: list[SearchMode]


class SearchRequest(BaseModel):
    query: str
    mode: SearchMode
    top_k: int = Field(default=10)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Query must contain at least 2 characters.")
        return trimmed

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, value: int) -> int:
        if not 1 <= value <= 50:
            raise ValueError("top_k must be between 1 and 50.")
        return value


class SearchResult(BaseModel):
    id: str
    record_id: str | None = None
    title: str
    score: float | None = None
    model: str | None = None


class SearchDebug(BaseModel):
    solr_query: str
    embedding_model: str | None = None
    embedding_size: int | None = None
    solr_rows: int


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    top_k: int
    took_ms: int
    results: list[SearchResult]
    debug: SearchDebug

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


SearchMode = Literal["vector", "keyword"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_default_top_k: int = Field(default=10, ge=1, le=50)
    app_max_top_k: int = Field(default=50, ge=1, le=200)
    app_log_level: str = "INFO"

    solr_base_url: AnyHttpUrl = "http://host.docker.internal:8983/solr"
    solr_collection: str = "embeddings"
    solr_vector_field: str = "vector"
    solr_title_field: str = "ti"
    solr_id_field: str = "id"
    solr_record_id_field: str = "record_id"
    solr_model_field: str = "model"
    solr_keyword_qf: str = "ti"
    solr_timeout_seconds: float = Field(default=20.0, gt=0)

    embeddings_api_url: AnyHttpUrl = "http://host.docker.internal:11434/api/embed"
    embeddings_model: str = "nomic-embed-text"
    embeddings_vector_size: int = Field(default=768, ge=1)
    embeddings_timeout_seconds: float = Field(default=30.0, gt=0)

    @property
    def supported_modes(self) -> list[SearchMode]:
        return ["vector", "keyword"]

    @property
    def solr_select_url(self) -> str:
        base_url = str(self.solr_base_url).rstrip("/")
        return f"{base_url}/{self.solr_collection}/select"


@lru_cache
def get_settings() -> Settings:
    return Settings()

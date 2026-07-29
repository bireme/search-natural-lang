from __future__ import annotations

from fastapi.testclient import TestClient

from app.clients.ollama import EmbeddingsMalformedResponseError, EmbeddingsUnavailableError
from app.clients.solr import SolrQueryResult, SolrUnavailableError
from app.config import Settings
from app.main import create_app


def build_client(solr_collection: str = "embeddings,embeddings_v2") -> TestClient:
    settings = Settings(
        app_default_top_k=7,
        app_max_top_k=50,
        solr_base_url="http://solr.test/solr",
        solr_collection=solr_collection,
        embeddings_api_url="http://ollama.test/api/embed",
    )
    app = create_app(settings)
    return TestClient(app)


def test_health_returns_ok():
    with build_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_returns_runtime_defaults():
    with build_client() as client:
        response = client.get("/config")

    assert response.status_code == 200
    assert response.json() == {
        "default_top_k": 7,
        "max_top_k": 50,
        "supported_modes": ["vector", "keyword"],
        "collections": ["embeddings", "embeddings_v2"],
        "default_collection": "embeddings",
    }


def test_config_with_single_collection_is_backward_compatible():
    with build_client(solr_collection="embeddings") as client:
        response = client.get("/config")

    body = response.json()
    assert body["collections"] == ["embeddings"]
    assert body["default_collection"] == "embeddings"


def test_collection_list_is_trimmed_and_empty_entries_dropped():
    with build_client(solr_collection=" embeddings , , embeddings_v2 ,") as client:
        response = client.get("/config")

    assert response.json()["collections"] == ["embeddings", "embeddings_v2"]


def test_search_uses_selected_collection():
    with build_client() as client:
        async def fake_search_keyword(
            query: str, top_k: int, collection: str | None = None
        ) -> SolrQueryResult:
            assert collection == "embeddings_v2"
            return SolrQueryResult(docs=[], solr_query="ti:(x)", rows=top_k, collection=collection)

        client.app.state.solr_client.search_keyword = fake_search_keyword

        response = client.post(
            "/search",
            json={"query": "heart failure", "mode": "keyword", "top_k": 5, "collection": "embeddings_v2"},
        )

    assert response.status_code == 200
    assert response.json()["collection"] == "embeddings_v2"


def test_search_defaults_to_first_collection():
    with build_client() as client:
        async def fake_search_keyword(
            query: str, top_k: int, collection: str | None = None
        ) -> SolrQueryResult:
            assert collection == "embeddings"
            return SolrQueryResult(docs=[], solr_query="ti:(x)", rows=top_k, collection=collection)

        client.app.state.solr_client.search_keyword = fake_search_keyword

        response = client.post("/search", json={"query": "heart failure", "mode": "keyword", "top_k": 5})

    assert response.status_code == 200
    assert response.json()["collection"] == "embeddings"


def test_search_rejects_unknown_collection():
    with build_client() as client:
        response = client.post(
            "/search",
            json={"query": "heart failure", "mode": "keyword", "top_k": 5, "collection": "nope"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Unknown collection 'nope'. Available: embeddings, embeddings_v2."
    )


def test_solr_client_builds_select_url_per_collection():
    with build_client() as client:
        solr_client = client.app.state.solr_client

    assert solr_client.select_url() == "http://solr.test/solr/embeddings/select"
    assert solr_client.select_url("embeddings_v2") == "http://solr.test/solr/embeddings_v2/select"


def test_search_rejects_empty_query():
    with build_client() as client:
        response = client.post("/search", json={"query": " ", "mode": "keyword", "top_k": 10})

    assert response.status_code == 422


def test_search_rejects_unsupported_mode():
    with build_client() as client:
        response = client.post("/search", json={"query": "heart failure", "mode": "hybrid", "top_k": 10})

    assert response.status_code == 422


def test_search_rejects_out_of_range_top_k():
    with build_client() as client:
        response = client.post("/search", json={"query": "heart failure", "mode": "keyword", "top_k": 99})

    assert response.status_code == 422
    assert response.json()["detail"] == "top_k must be between 1 and 50."


def test_vector_search_success():
    with build_client() as client:
        async def fake_embed(query: str) -> list[float]:
            assert query == "heart failure"
            return [0.1] * 768

        async def fake_search_vector(
            vector: list[float], top_k: int, collection: str | None = None
        ) -> SolrQueryResult:
            assert len(vector) == 768
            assert top_k == 3
            assert collection == "embeddings"
            return SolrQueryResult(
                docs=[{"id": "123", "record_id": "abc-123", "ti": "Hypertension management", "score": 0.8123, "model": "nomic-embed-text"}],
                solr_query="{!knn f=vector topK=3}[0.1,...]",
                rows=3,
            )

        client.app.state.ollama_client.embed = fake_embed
        client.app.state.solr_client.search_vector = fake_search_vector

        response = client.post("/search", json={"query": "heart failure", "mode": "vector", "top_k": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "vector"
    assert body["results"][0]["title"] == "Hypertension management"

def test_keyword_search_success():
    with build_client() as client:
        async def fake_search_keyword(
            query: str, top_k: int, collection: str | None = None
        ) -> SolrQueryResult:
            assert query == "older adults"
            assert top_k == 5
            return SolrQueryResult(
                docs=[{"id": "321", "record_id": "rec-321", "ti": "Care in older adults", "score": 4.5}],
                solr_query="ti:(older adults)",
                rows=5,
            )

        client.app.state.solr_client.search_keyword = fake_search_keyword

        response = client.post("/search", json={"query": "older adults", "mode": "keyword", "top_k": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["debug"]["embedding_model"] is None
    assert body["debug"]["embedding_size"] is None
    assert body["results"][0]["record_id"] == "rec-321"


def test_embedding_timeout_maps_to_502():
    with build_client() as client:
        async def fake_embed(query: str) -> list[float]:
            raise EmbeddingsUnavailableError("Embedding service is unavailable.")

        client.app.state.ollama_client.embed = fake_embed

        response = client.post("/search", json={"query": "heart failure", "mode": "vector", "top_k": 5})

    assert response.status_code == 502
    assert response.json() == {"detail": "Embedding service is unavailable."}


def test_solr_timeout_maps_to_502():
    with build_client() as client:
        async def fake_search_keyword(
            query: str, top_k: int, collection: str | None = None
        ) -> SolrQueryResult:
            raise SolrUnavailableError("Solr is unavailable.")

        client.app.state.solr_client.search_keyword = fake_search_keyword

        response = client.post("/search", json={"query": "heart failure", "mode": "keyword", "top_k": 5})

    assert response.status_code == 502
    assert response.json() == {"detail": "Solr is unavailable."}


def test_embedding_wrong_vector_size_maps_to_502():
    with build_client() as client:
        async def fake_embed(query: str) -> list[float]:
            raise EmbeddingsMalformedResponseError("Embedding vector size 4 does not match expected size 768.")

        client.app.state.ollama_client.embed = fake_embed

        response = client.post("/search", json={"query": "heart failure", "mode": "vector", "top_k": 5})

    assert response.status_code == 502
    assert "Embedding vector size 4" in response.json()["detail"]


def test_solr_empty_docs_returns_empty_results():
    with build_client() as client:
        async def fake_search_keyword(
            query: str, top_k: int, collection: str | None = None
        ) -> SolrQueryResult:
            return SolrQueryResult(docs=[], solr_query="ti:(none)", rows=top_k)

        client.app.state.solr_client.search_keyword = fake_search_keyword

        response = client.post("/search", json={"query": "no matches", "mode": "keyword", "top_k": 4})

    assert response.status_code == 200
    assert response.json()["results"] == []

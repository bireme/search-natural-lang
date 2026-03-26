from __future__ import annotations

import httpx


class EmbeddingsError(Exception):
    """Base embeddings client error."""


class EmbeddingsUnavailableError(EmbeddingsError):
    """Raised when the embeddings service cannot be reached."""


class EmbeddingsMalformedResponseError(EmbeddingsError):
    """Raised when the embeddings response is invalid."""


class EmbeddingsClient:
    def __init__(self, api_url: str, model: str, expected_vector_size: int, timeout_seconds: float) -> None:
        self.api_url = api_url
        self.model = model
        self.expected_vector_size = expected_vector_size
        self.timeout = timeout_seconds

    async def embed(self, query: str) -> list[float]:
        payload = {"model": self.model, "input": query}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            raise EmbeddingsUnavailableError("Embedding service is unavailable.") from exc
        except httpx.HTTPStatusError as exc:
            raise EmbeddingsUnavailableError("Embedding service returned an error.") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise EmbeddingsMalformedResponseError("Embedding service returned invalid JSON.") from exc

        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or not embeddings:
            raise EmbeddingsMalformedResponseError("Embedding service returned an empty embeddings list.")

        vector = embeddings[0]
        if not isinstance(vector, list) or not vector:
            raise EmbeddingsMalformedResponseError("Embedding service returned an invalid embedding vector.")

        if len(vector) != self.expected_vector_size:
            raise EmbeddingsMalformedResponseError(
                f"Embedding vector size {len(vector)} does not match expected size {self.expected_vector_size}."
            )

        try:
            return [float(value) for value in vector]
        except (TypeError, ValueError) as exc:
            raise EmbeddingsMalformedResponseError("Embedding vector contains invalid values.") from exc

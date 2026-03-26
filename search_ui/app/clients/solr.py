from __future__ import annotations

import re
from dataclasses import dataclass

import httpx


class SolrError(Exception):
    """Base Solr client error."""


class SolrUnavailableError(SolrError):
    """Raised when Solr cannot be reached."""


class SolrMalformedResponseError(SolrError):
    """Raised when Solr response payload is invalid."""


@dataclass
class SolrQueryResult:
    docs: list[dict]
    solr_query: str
    rows: int


class SolrClient:
    def __init__(
        self,
        *,
        select_url: str,
        vector_field: str,
        title_field: str,
        id_field: str,
        record_id_field: str,
        model_field: str,
        keyword_qf: str,
        timeout_seconds: float,
    ) -> None:
        self.select_url = select_url
        self.vector_field = vector_field
        self.title_field = title_field
        self.id_field = id_field
        self.record_id_field = record_id_field
        self.model_field = model_field
        self.keyword_qf = keyword_qf
        self.timeout = timeout_seconds

    def build_vector_query(self, vector: list[float], top_k: int) -> tuple[dict[str, str], str]:
        vector_literal = "[" + ",".join(self._format_vector_value(value) for value in vector) + "]"
        query = f"{{!knn f={self.vector_field} topK={top_k}}}{vector_literal}"
        params = {"q": query, "fl": self.field_list, "rows": str(top_k), "wt": "json"}
        return params, query

    def build_keyword_query(self, query_text: str, top_k: int) -> tuple[dict[str, str], str]:
        escaped = self.escape_keyword_query(query_text)
        query = f"{self.keyword_qf}:({escaped})"
        params = {"q": query, "fl": self.field_list, "rows": str(top_k), "wt": "json"}
        return params, query

    @property
    def field_list(self) -> str:
        return ",".join(
            [
                self.id_field,
                self.record_id_field,
                self.title_field,
                "score",
                self.model_field,
            ]
        )

    async def search_vector(self, vector: list[float], top_k: int) -> SolrQueryResult:
        params, query = self.build_vector_query(vector, top_k)
        docs = await self._send_query(params)
        return SolrQueryResult(docs=docs, solr_query=query, rows=top_k)

    async def search_keyword(self, query_text: str, top_k: int) -> SolrQueryResult:
        params, query = self.build_keyword_query(query_text, top_k)
        docs = await self._send_query(params)
        return SolrQueryResult(docs=docs, solr_query=query, rows=top_k)

    async def _send_query(self, params: dict[str, str]) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.select_url, data=params)
                response.raise_for_status()
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            raise SolrUnavailableError("Solr is unavailable.") from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500] if exc.response else "no response body"
            raise SolrUnavailableError(
                f"Solr returned HTTP {exc.response.status_code}: {detail}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise SolrMalformedResponseError("Solr returned invalid JSON.") from exc

        docs = data.get("response", {}).get("docs")
        if docs is None:
            raise SolrMalformedResponseError("Solr response is missing response.docs.")
        if not isinstance(docs, list):
            raise SolrMalformedResponseError("Solr response docs payload is invalid.")
        return docs

    def normalize_doc(self, doc: dict) -> dict:
        return {
            "id": str(doc.get(self.id_field, "")),
            "record_id": self._string_or_none(doc.get(self.record_id_field)),
            "title": self._string_or_none(doc.get(self.title_field)) or "Untitled",
            "score": self._float_or_none(doc.get("score")),
            "model": self._string_or_none(doc.get(self.model_field)),
        }

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, list):
            if not value:
                return None
            value = value[0]
        text = str(value).strip()
        return text or None

    @staticmethod
    def _float_or_none(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_vector_value(value: float) -> str:
        return format(value, ".10g")

    @staticmethod
    def escape_keyword_query(query_text: str) -> str:
        escaped = re.sub(r'([+\-!(){}\[\]^"~*?:\\/])', r"\\\1", query_text)
        escaped = re.sub(r"\b(AND|OR|NOT)\b", r"\\\1", escaped, flags=re.IGNORECASE)
        return escaped

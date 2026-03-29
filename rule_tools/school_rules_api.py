"""
School Rules Retrieval MCP Server
"""

from __future__ import annotations
import os
import json
import math
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

import requests
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv


@dataclass
class Document:
    """Represents a document."""
    id: str
    title: str
    content: str


@dataclass
class RetrievalResult:
    """Represents a retrieval result."""
    document: Document
    score: float
    rank: int


class EmbeddingProvider:
    """Provides embeddings for text using an external API."""

    def __init__(self, api_url: str, timeout: int = 30):
        """
        Args:
            api_url: URL of the embedding API.
            timeout: Request timeout in seconds.

        Raises:
            EnvironmentError: If api_url is empty.
        """
        if not api_url:
            raise EnvironmentError("請設定 EMBEDDING_API_URL")
        self.api_url = api_url
        self.timeout = timeout

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a given text.

        Args:
            text: Input text.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            ValueError: If response cannot be parsed.
        """
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        response = requests.post(
            self.api_url, headers=headers, json={"inputs": text}, timeout=self.timeout
        )
        response.raise_for_status()
        result = response.json()
        if isinstance(result, list) and result:
            return result[0] if isinstance(result[0], list) else result
        raise ValueError(f"無法解析 embedding 回應：{result}")


class DenseRetriever:
    """Dense vector-based document retriever."""

    def __init__(self, embedding_provider: EmbeddingProvider):
        """
        Args:
            embedding_provider: Instance of EmbeddingProvider.
        """
        self.embedding_provider = embedding_provider
        self.documents: List[Document] = []
        self.document_embeddings: List[List[float]] = []

    def add_documents(self, docs: List[Document]):
        """Add documents and compute embeddings.

        Args:
            docs: List of Document objects.
        """
        self.documents = docs
        self.document_embeddings = []

        for doc in docs:
            text = f"{doc.title}\n{doc.content[:1000]}"
            try:
                embedding = self.embedding_provider.get_embedding(text)
                self.document_embeddings.append(embedding)
            except Exception:
                self.document_embeddings.append([0.0] * 768)

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Retrieve top_k relevant documents for a query.

        Args:
            query: Query string.
            top_k: Number of results to return.

        Returns:
            List of RetrievalResult objects.
        """
        if not self.documents:
            return []

        query_embedding = self.embedding_provider.get_embedding(query)
        scores = [(i, self._cosine_similarity(query_embedding, doc_emb))
                  for i, doc_emb in enumerate(self.document_embeddings)]
        scores.sort(key=lambda x: x[1], reverse=True)

        return [
            RetrievalResult(document=self.documents[idx], score=score, rank=rank + 1)
            for rank, (idx, score) in enumerate(scores[:top_k])
        ]


def _load_documents(json_path: str) -> List[Document]:
    """Load documents from a JSON file.

    Args:
        json_path: Relative path from parent_dir to JSON file.

    Returns:
        List of Document objects.

    Raises:
        FileNotFoundError: If JSON file does not exist.
    """
    parent_dir = Path(__file__).parent.parent
    path = parent_dir / json_path
    if not path.exists():
        raise FileNotFoundError(f"找不到資料庫：{path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = []
    for key, value in data.items():
        content = "\n".join(str(v) for v in value.values()) if isinstance(value, dict) else str(value)
        documents.append(Document(id=str(key), title=str(key), content=content))

    return documents


# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent
load_dotenv(PARENT_DIR / ".env")

EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "")

# Load documents
DOCS = _load_documents("data/rules/school_rules.json")

# Initialize retriever
EP = EmbeddingProvider(api_url=EMBEDDING_API_URL)
RETRIEVER = DenseRetriever(EP)
RETRIEVER.add_documents(DOCS)

mcp = FastMCP("nchu_school_rules_search")


@mcp.tool()
def rule_search_by_query(query: str, top_k: int = 5) -> Dict[str, Any]:
    """Search school rules by query string.

    Args:
        query: Query string (e.g., "獎懲規定", "請假流程").
        top_k: Number of results to return (1-10).

    Returns:
        Dictionary containing retrieved documents and metadata.
    """
    top_k = max(1, min(10, top_k))
    results = RETRIEVER.retrieve(query, top_k=top_k)
    return {
        "query": query,
        "results": [
            {
                "rank": r.rank,
                "doc_id": r.document.id,
                "title": r.document.title,
                "score": round(r.score, 4),
                "content": r.document.content,
            }
            for r in results
        ],
        "total_documents": len(RETRIEVER.documents)
    }


@mcp.tool()
def rule_list_all(limit: int = 20) -> Dict[str, Any]:
    """List all available school rule documents.

    Args:
        limit: Maximum number of documents to return (1-100).

    Returns:
        Dictionary with document metadata and counts.
    """
    limit = max(1, min(100, limit))
    documents = [
        {"id": doc.id, "title": doc.title, "content_length": len(doc.content)}
        for doc in RETRIEVER.documents[:limit]
    ]
    return {
        "documents": documents,
        "total": len(RETRIEVER.documents),
        "showing": len(documents)
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")

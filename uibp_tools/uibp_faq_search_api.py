#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool for NCHU UIBP (校學士) FAQ with dense retrieval."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


@dataclass
class Document:
    """Represents a FAQ document."""

    id: str
    question: str
    answer: str


@dataclass
class RetrievalResult:
    """Represents a retrieval result."""

    document: Document
    score: float
    rank: int


class EmbeddingProvider:
    """Provides embeddings for text using an external API."""

    def __init__(self, api_url: str, timeout: int = 30):
        if not api_url:
            raise EnvironmentError("請設定 EMBEDDING_API_URL")
        self.api_url = api_url
        self.timeout = timeout

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a given text."""
        headers = {"accept": "application/json",
                   "Content-Type": "application/json"}
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
        self.embedding_provider = embedding_provider
        self.documents: List[Document] = []
        self.document_embeddings: List[List[float]] = []

    def add_documents(self, docs: List[Document]):
        """Add documents and compute embeddings."""
        self.documents = docs
        self.document_embeddings = []

        for doc in docs:
            text = doc.question
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
        """Retrieve top_k relevant documents for a query."""
        if not self.documents:
            return []

        query_embedding = self.embedding_provider.get_embedding(query)

        scores = []
        for i, (doc, doc_emb) in enumerate(
            zip(self.documents, self.document_embeddings)
        ):
            score = self._cosine_similarity(query_embedding, doc_emb)
            scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        return [
            RetrievalResult(
                document=self.documents[idx], score=score, rank=rank + 1)
            for rank, (idx, score) in enumerate(scores[:top_k])
        ]


class UIBPFAQManager:
    """Manager for NCHU UIBP (校學士) FAQ data."""

    def __init__(self, embedding_api_url: str):
        self.parent_dir = Path(__file__).parent.parent
        self.data_file_path = self.parent_dir / "data/uibp/uibp_faq.json"
        self.raw_data: Dict = {}
        self.documents: List[Document] = []

        self.embedding_provider = EmbeddingProvider(api_url=embedding_api_url)
        self.retriever = DenseRetriever(self.embedding_provider)

        self.load_data()

    def load_data(self) -> bool:
        """Load FAQ data from JSON file."""
        try:
            if self.data_file_path.exists():
                with open(self.data_file_path, "r", encoding="utf-8") as f:
                    self.raw_data = json.load(f)

                self._build_documents()

                print(f"✓ Loaded UIBP FAQ: {len(self.documents)} questions")
                return True
            else:
                print(f"✗ Data file not found: {self.data_file_path}")
                return False
        except Exception as e:
            print(f"✗ Failed to load data: {e}")
            return False

    def _build_documents(self):
        """Build document list from raw data."""
        self.documents = []
        data_list = self.raw_data.get("data", [])

        for idx, item in enumerate(data_list):
            doc = Document(
                id=str(idx),
                question=item.get("question", "").strip(),
                answer=item.get("answer", "").strip(),
            )
            self.documents.append(doc)

        self.retriever.add_documents(self.documents)

    def search_faq(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Search FAQ using dense retrieval."""
        top_k = max(1, min(10, top_k))

        results = self.retriever.retrieve(query, top_k=top_k)

        return {
            "query": query,
            "results": [
                {
                    "rank": r.rank,
                    "score": round(r.score, 4),
                    "question": r.document.question,
                    "answer": r.document.answer,
                }
                for r in results
            ],
            "total_documents": len(self.documents),
        }

    def list_all_faq(self) -> Dict[str, Any]:
        """List all FAQ items."""
        return {
            "total_questions": len(self.documents),
            "questions": [
                {
                    "question": doc.question,
                    "answer": doc.answer,
                }
                for doc in self.documents
            ],
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics of the FAQ dataset."""
        metadata = self.raw_data.get("metadata", {})
        return {
            "total_questions": len(self.documents),
            "last_updated": metadata.get("last_updated", ""),
            "data_source": metadata.get("data_source", ""),
        }


# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent
load_dotenv(PARENT_DIR / ".env")

EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "")

# Initialize manager
manager = UIBPFAQManager(embedding_api_url=EMBEDDING_API_URL)
mcp = FastMCP("nchu_uibp_faq")


@mcp.tool()
def nchu_uibp_faq_search(query: str, top_k: int = 5) -> str:
    """
    Search NCHU UIBP (校學士/校務規劃處) FAQ using semantic search.

    Uses dense retrieval to find relevant FAQ items about 校學士制度,
    including application requirements, course planning, and graduation rules.

    Args:
        query: Search query (e.g., "誰可以申請校學士", "校學士會延畢嗎")
        top_k: Number of results to return (1-10, default: 5)

    Example:
        nchu_uibp_faq_search("校學士申請資格", top_k=3)
        nchu_uibp_faq_search("教育學程學分")
    """
    try:
        result = manager.search_faq(query, top_k=top_k)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_uibp_faq_list_all() -> str:
    """
    List all UIBP (校學士) FAQ items.

    Returns all available FAQ questions and answers about 校學士制度.
    """
    try:
        result = manager.list_all_faq()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_uibp_faq_stats() -> str:
    """Get statistics of the UIBP FAQ dataset."""
    try:
        result = manager.get_stats()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")

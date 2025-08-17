"""Rerank retrieved documents using Cohere Rerank API."""

from typing import List, Dict
import os
import cohere
from .config import COHERE_API_KEY

co = cohere.Client(COHERE_API_KEY or os.getenv("COHERE_API_KEY", ""))


def rerank(query: str, docs: List[Dict], top_k: int = 5) -> List[Dict]:
    """Returns docs ordered by relevance using Cohere rerank."""
    if not docs:
        return []
    texts = [doc["text"] for doc in docs]
    response = co.rerank(query=query, documents=texts, top_k=min(top_k, len(texts)))
    ranked = [docs[result.index] for result in response.results]
    return ranked

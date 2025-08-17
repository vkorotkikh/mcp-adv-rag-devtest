"""Query Pinecone and rerank results for RAG."""

from typing import List, Dict
import pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from .config import PINECONE_API_KEY, PINECONE_ENV, PINECONE_INDEX_NAME
from .reranker import rerank


pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
index = pinecone.Index(PINECONE_INDEX_NAME)
embeddings = OpenAIEmbeddings()


def retrieve(query: str, top_k: int = 20, rerank_k: int = 5) -> List[Dict]:
    """Return top rerank_k docs relevant to query."""
    qvec = embeddings.embed_query(query)
    raw = index.query(vector=qvec, top_k=top_k, include_metadata=True)
    docs = [match["metadata"] | {"score": match["score"]} for match in raw["matches"]]
    return rerank(query, docs, top_k=rerank_k)

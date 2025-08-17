"""Ingest documents into Pinecone vector store."""

from typing import List, Dict
import uuid
import pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from .config import PINECONE_API_KEY, PINECONE_ENV, PINECONE_INDEX_NAME


pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)

# Create index if missing. Dimension is 1536 for OpenAI embeddings.
if PINECONE_INDEX_NAME not in pinecone.list_indexes():
    pinecone.create_index(PINECONE_INDEX_NAME, dimension=1536, metric="cosine")

index = pinecone.Index(PINECONE_INDEX_NAME)
embeddings = OpenAIEmbeddings()


def upsert_documents(docs: List[Dict]):
    """Takes list of {text: str, metadata: dict} and upserts into Pinecone."""
    vectors = []
    for doc in docs:
        vec = embeddings.embed_query(doc["text"])
        vectors.append((str(uuid.uuid4()), vec, doc["metadata"]))
    if vectors:
        index.upsert(vectors=vectors)

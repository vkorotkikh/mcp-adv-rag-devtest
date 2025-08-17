"""Different chunking strategies for documents."""

from typing import List
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter, CharacterTextSplitter


def paragraph_chunks(text: str, chunk_size: int = 512) -> List[str]:
    """Chunk text on paragraph boundaries keeping size under chunk_size characters."""
    paragraphs = text.split("\n\n")
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) <= chunk_size:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            current = para + "\n\n"
    if current:
        chunks.append(current.strip())
    return chunks


def recursive_chunks(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)


def semantic_chunks(text: str, embedder, threshold: float = 0.8) -> List[str]:
    """Very naive semantic chunking based on adjacent sentence similarity."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if not sentences:
        return [text]

    groups: List[str] = [sentences[0]]
    for sentence in sentences[1:]:
        prev = groups[-1]
        sim = embedder.similarity(prev, sentence)
        if sim < threshold:
            groups.append(sentence)
        else:
            groups[-1] = f"{groups[-1]} {sentence}"
    return groups

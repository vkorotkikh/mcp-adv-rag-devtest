# MCP Multi-Service Application with RAG Pipeline

This repository demonstrates a **Model Context Protocol (MCP)** setup where autonomous agents can call external tools through micro-services.  Each service is an independent FastAPI server exposing a REST interface.  A Retrieval-Augmented Generation (RAG) pipeline built on Pinecone, LangChain and Cohere ties the data together.

## Micro-services

| Service | Folder | Key Endpoints |
|---------|--------|--------------|
| Gmail   | `mcp_servers/gmail_server/` | `/search`, `/read/{message_id}` |
| GitHub  | `mcp_servers/github_server/` | `/repo/{owner}/{repo}/files`, `/repo/{owner}/{repo}/file` |
| Slack   | `mcp_servers/slack_server/` | `/channels`, `/channel/{channel_id}/history` |
| Drive   | `mcp_servers/gdrive_server/` | `/files`, `/file/{file_id}` |

Each uses a common helper in `mcp_servers/base_server.py` to ensure consistent **/health** checks.

## RAG Pipeline

Location: `rag_pipeline/`

1. **Chunking** – three strategies in `chunkers.py`:
   * Paragraph-aware
   * Recursive character
   * Semantic similarity–based
2. **Vector Store** – Pinecone index (auto-created if missing) via `indexer.py`.
3. **Retrieval** – `retriever.py` embeds the query, fetches vectors, then calls `reranker.py` (Cohere) for final ordering.

## Quick Start

```bash
# 1. Install deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Export environment variables (example)
export GOOGLE_SERVICE_ACCOUNT_JSON="/path/drive-sa.json"
export GITHUB_TOKEN="ghp_xxx"
export SLACK_BOT_TOKEN="xoxb-xxx"
export OPENAI_API_KEY="sk-..."
export PINECONE_API_KEY="..."
export COHERE_API_KEY="..."

# 3. Run a service (e.g. Gmail)
uvicorn mcp_servers.gmail_server.main:app --reload --port 8001

# 4. Ingest docs and test retrieval
python - <<'PY'
from rag_pipeline.indexer import upsert_documents
from rag_pipeline.retriever import retrieve

upsert_documents([
    {"text": "The quick brown fox jumps over the lazy dog", "metadata": {"source": "demo"}},
])
print(retrieve("What jumps over the lazy dog?"))
PY
```

## Architecture Diagram

```mermaid
graph TD
  subgraph Microservices
    GMAIL(Gmail API)
    GH(GitHub API)
    SLACK(Slack API)
    DRIVE(Drive API)
  end
  GMAIL -- REST --> Agent
  GH -- REST --> Agent
  SLACK -- REST --> Agent
  DRIVE -- REST --> Agent
  Agent -- query --> RAG[Retriever (Pinecone + Cohere)]
  RAG -- context --> Agent
```

---
MIT © 2024

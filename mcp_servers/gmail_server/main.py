from pathlib import Path
from fastapi import HTTPException

from ..base_server import create_app
from .gmail_utils import GmailClient

app = create_app("Gmail MCP Server", "0.1.0")

# Credentials location may be overridden via env var – kept flexible for deployment.
CLIENT_SECRETS_PATH = Path(__file__).parent / "credentials.json"

gmail_client = GmailClient(client_secret_file=str(CLIENT_SECRETS_PATH))


@app.get("/search")
async def search(query: str):
    """Search the user's Gmail with Gmail query syntax."""
    try:
        return gmail_client.search_messages(query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/read/{message_id}")
async def read(message_id: str):
    """Read a specific email by message ID."""
    try:
        return gmail_client.read_message(message_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

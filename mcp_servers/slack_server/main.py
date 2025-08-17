from fastapi import HTTPException

from ..base_server import create_app
from .slack_utils import SlackClient

app = create_app("Slack MCP Server", "0.1.0")

sl_client = SlackClient()


@app.get("/channels")
async def channels():
    """List Slack channels visible to the bot token."""
    try:
        return sl_client.list_channels()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/channel/{channel_id}/history")
async def history(channel_id: str, limit: int = 20):
    """Fetch message history for a channel."""
    try:
        return sl_client.channel_history(channel_id, limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

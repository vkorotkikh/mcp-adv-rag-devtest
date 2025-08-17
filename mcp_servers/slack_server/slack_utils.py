from typing import List, Dict
import os
from slack_sdk import WebClient, errors


class SlackClient:
    """Lightweight wrapper around Slack conversations.* endpoints."""

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        if self.token is None:
            raise ValueError("SLACK_BOT_TOKEN env var not set.")
        self.client = WebClient(token=self.token)

    def list_channels(self) -> List[Dict]:
        response = self.client.conversations_list(types="public_channel,private_channel")
        return response.get("channels", [])

    def channel_history(self, channel_id: str, limit: int = 20) -> List[Dict]:
        try:
            response = self.client.conversations_history(channel=channel_id, limit=limit)
            return response.get("messages", [])
        except errors.SlackApiError as exc:
            raise RuntimeError(exc.response["error"]) from exc

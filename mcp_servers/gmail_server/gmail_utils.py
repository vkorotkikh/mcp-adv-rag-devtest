from typing import List, Dict


class GmailClient:
    """Lightweight wrapper around Gmail API – implementation left as TODO."""

    def __init__(self, client_secret_file: str | None = None):
        # Placeholder for OAuth + API service initialisation.
        self.client_secret_file = client_secret_file
        # TODO: Implement OAuth flow and build gmail service.

    def search_messages(self, query: str) -> List[Dict]:
        """Search inbox using Gmail search syntax. Returns list of metadata dicts."""
        # TODO: Replace with real implementation.
        return []

    def read_message(self, message_id: str) -> Dict:
        """Return structured content for a single email."""
        # TODO: Replace with real implementation.
        return {}

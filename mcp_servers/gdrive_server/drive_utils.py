from typing import List, Dict
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class DriveClient:
    """Wrapper around Google Drive API for read-only operations."""

    def __init__(self, service_account_json: str | None = None):
        service_account_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if service_account_json is None:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON env var not set.")
        creds = service_account.Credentials.from_service_account_file(service_account_json, scopes=SCOPES)
        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_files(self, query: str = "'root' in parents") -> List[Dict]:
        results = (
            self.service.files()
            .list(q=query, fields="files(id, name, mimeType, modifiedTime, owners)")
            .execute()
        )
        return results.get("files", [])

    def get_file_metadata(self, file_id: str) -> Dict:
        return self.service.files().get(fileId=file_id, fields="id, name, mimeType, size, modifiedTime, owners").execute()

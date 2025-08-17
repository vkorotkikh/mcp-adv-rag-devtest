from fastapi import HTTPException

from ..base_server import create_app
from .drive_utils import DriveClient

app = create_app("Google Drive MCP Server", "0.1.0")

drive_client = DriveClient()


@app.get("/files")
async def list_files(query: str = "'root' in parents"):
    """List files according to Drive query syntax."""
    try:
        return drive_client.list_files(query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/file/{file_id}")
async def fetch_file(file_id: str):
    """Fetch metadata for a single file."""
    try:
        return drive_client.get_file_metadata(file_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

from fastapi import HTTPException

from ..base_server import create_app
from .github_utils import GitHubClient

app = create_app("GitHub MCP Server", "0.1.0")

gh_client = GitHubClient()


@app.get("/repo/{owner}/{repo}/files")
async def list_files(owner: str, repo: str, path: str = ""):
    """List files under a given path in a GitHub repository."""
    try:
        return gh_client.list_files(owner, repo, path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/repo/{owner}/{repo}/file")
async def read_file(owner: str, repo: str, path: str):
    """Return the content of a file."""
    try:
        content = gh_client.read_file(owner, repo, path)
        return {"path": path, "content": content}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

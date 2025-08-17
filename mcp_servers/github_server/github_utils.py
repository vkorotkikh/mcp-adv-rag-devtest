from typing import List
import os
from github import Github


class GitHubClient:
    """Wrapper around GitHub REST API using PyGithub."""

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if self.token is None:
            raise ValueError("No GitHub token provided. Set GITHUB_TOKEN env var or pass a token.")
        self.gh = Github(self.token)

    def list_files(self, owner: str, repo: str, path: str = "") -> List[str]:
        """Return a flat list of file paths at a given repo path."""
        repository = self.gh.get_repo(f"{owner}/{repo}")
        contents = repository.get_contents(path)
        files: List[str] = []
        for item in contents:
            if item.type == "file":
                files.append(item.path)
            elif item.type == "dir":
                files.extend(self.list_files(owner, repo, item.path))
        return files

    def read_file(self, owner: str, repo: str, path: str) -> str:
        """Return file content as UTF-8 string."""
        repository = self.gh.get_repo(f"{owner}/{repo}")
        file_content = repository.get_contents(path)
        return file_content.decoded_content.decode()

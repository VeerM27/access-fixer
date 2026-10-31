"""Turn the user's input into a local folder plus the GitHub repo it came from."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from pydantic import BaseModel

GITHUB_URL = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
MAX_REPO_BYTES = 50 * 1024 * 1024
MAX_REPO_FILES = 500
CLONE_TIMEOUT_SECONDS = 60


class SourceError(Exception):
    """The repo can't be used; the message is safe to show to the user."""


class Source(BaseModel):
    root: str
    owner: str | None = None
    repo: str | None = None
    base_branch: str = "main"


def parse_github_url(text: str) -> tuple[str, str] | None:
    match = GITHUB_URL.match(text.strip())
    return (match.group(1), match.group(2)) if match else None


def _repo_info(owner: str, repo: str) -> dict:
    """Ask the GitHub API for the repo's size and default branch, before cloning anything."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers={"Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except Exception as error:
        raise SourceError(f"Could not find github.com/{owner}/{repo} (is it public?)") from error


def check_folder_limits(root: Path) -> None:
    files = [p for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts]
    if len(files) > MAX_REPO_FILES:
        raise SourceError(f"Repo has {len(files)} files; the limit is {MAX_REPO_FILES}.")
    if sum(p.stat().st_size for p in files) > MAX_REPO_BYTES:
        raise SourceError("Repo is bigger than 50 MB.")


def clone_github_repo(owner: str, repo: str) -> Source:
    info = _repo_info(owner, repo)
    if info.get("size", 0) * 1024 > MAX_REPO_BYTES:  # the API reports size in KB
        raise SourceError("Repo is bigger than 50 MB.")

    dest = Path(tempfile.mkdtemp(prefix="access-fixer-clone-")) / repo
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        # A plain shallow clone: no submodules, and nothing from the repo gets executed.
        subprocess.run(
            ["git", "clone", "--depth", "1", "--no-tags", f"https://github.com/{owner}/{repo}.git",
             str(dest)],
            check=True, capture_output=True, timeout=CLONE_TIMEOUT_SECONDS, env=env,
        )
        check_folder_limits(dest)  # backstop in case the API size was out of date
    except subprocess.TimeoutExpired as error:
        shutil.rmtree(dest.parent, ignore_errors=True)
        raise SourceError("Cloning took longer than 60 seconds.") from error
    except subprocess.CalledProcessError as error:
        shutil.rmtree(dest.parent, ignore_errors=True)
        raise SourceError(f"Could not clone github.com/{owner}/{repo}.") from error
    except SourceError:
        shutil.rmtree(dest.parent, ignore_errors=True)
        raise
    return Source(
        root=str(dest), owner=owner, repo=repo, base_branch=info.get("default_branch", "main")
    )


def local_source(root: Path) -> Source:
    """Dev mode: use a local folder, and its GitHub origin remote if it has one."""
    source = Source(root=str(root))
    remote = _git(root, "remote", "get-url", "origin")
    if remote and (parsed := parse_github_url(remote)):
        source.owner, source.repo = parsed
        source.base_branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "main"
    return source


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""

"""Make a throwaway copy of the site so fixes never touch the original folder."""

import shutil
import tempfile
from pathlib import Path


def make_working_copy(root: Path) -> Path:
    """Copy `root` (minus .git) into a new temp folder and return the copy's path."""
    copy_root = Path(tempfile.mkdtemp(prefix="access-fixer-")) / "site"
    # symlinks=True copies links as links, so we never read files outside the repo.
    shutil.copytree(root, copy_root, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    return copy_root

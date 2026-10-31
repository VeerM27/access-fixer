"""Serve a folder on a free localhost port in a background thread."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def serve_folder(root: Path) -> Iterator[str]:
    """Yield the base URL of a local server for `root`. Implemented in Phase 1."""
    raise NotImplementedError
    yield ""

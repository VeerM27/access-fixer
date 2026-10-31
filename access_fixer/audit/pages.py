"""Find the HTML pages in a site folder."""

from pathlib import Path

MAX_PAGES = 500
SKIPPED_DIRS = {"node_modules"}


def _is_skipped(relative: Path) -> bool:
    return any(part.startswith(".") or part in SKIPPED_DIRS for part in relative.parts[:-1])


def find_pages(root: Path) -> list[str]:
    """Return sorted .html paths relative to `root`, ignoring files that resolve outside it."""
    real_root = root.resolve()
    pages = []
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root)
        if _is_skipped(relative) or not path.is_file():
            continue
        if not path.resolve().is_relative_to(real_root):
            continue  # a symlink pointing outside the repo
        pages.append(relative.as_posix())
        if len(pages) == MAX_PAGES:
            break
    return pages

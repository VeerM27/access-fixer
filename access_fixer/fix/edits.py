"""Apply the fixer's find/replace edits, rejecting anything unsafe or ambiguous."""

from pathlib import Path

from pydantic import BaseModel, Field

EDITABLE_SUFFIXES = {".html", ".css"}


class Edit(BaseModel):
    file: str = Field(description="Path relative to the site root, e.g. index.html")
    find: str = Field(description="Exact text copied from the file. Must appear exactly once.")
    replace: str = Field(description="Text to put in its place")
    rule_id: str = Field(description="The axe rule this edit fixes, e.g. image-alt")
    reason: str = Field(description="One short sentence on why this fixes the rule")


class EditOutcome(BaseModel):
    edit: Edit
    accepted: bool
    reason: str = ""


def _target(root: Path, file: str) -> Path | None:
    path = (root / file).resolve()
    if not path.is_relative_to(root.resolve()):
        return None
    return path


def _check(root: Path, edit: Edit, text: str | None) -> str:
    """Return why `edit` can't be applied, or "" if it can."""
    if Path(edit.file).suffix not in EDITABLE_SUFFIXES:
        return "only .html and .css files can be edited"
    if _target(root, edit.file) is None:
        return "path is outside the site"
    if text is None:
        return "file not found"
    if not edit.find:
        return "find text is empty"
    count = text.count(edit.find)
    if count == 0:
        return "find text not in file"
    if count > 1:
        return f"find text matches {count} times"
    return ""


def apply_edits(
    root: Path, edits: list[Edit]
) -> tuple[list[EditOutcome], list[EditOutcome], dict[str, str]]:
    """Apply edits in order. Returns (accepted, rejected, original text of each changed file)."""
    accepted: list[EditOutcome] = []
    rejected: list[EditOutcome] = []
    current: dict[str, str] = {}
    originals: dict[str, str] = {}

    for edit in edits:
        path = _target(root, edit.file)
        if path is not None and edit.file not in current and path.is_file():
            current[edit.file] = path.read_text()
        problem = _check(root, edit, current.get(edit.file))
        if problem:
            rejected.append(EditOutcome(edit=edit, accepted=False, reason=problem))
            continue
        originals.setdefault(edit.file, current[edit.file])
        current[edit.file] = current[edit.file].replace(edit.find, edit.replace, 1)
        accepted.append(EditOutcome(edit=edit, accepted=True))

    for file in originals:
        (root / file).write_text(current[file])
    return accepted, rejected, originals


def revert(root: Path, originals: dict[str, str], files: set[str]) -> None:
    for file in files:
        (root / file).write_text(originals[file])

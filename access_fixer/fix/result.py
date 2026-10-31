"""What the fix loop hands to the report, approval and PR steps."""

from pydantic import BaseModel

from ..audit.score import AuditSummary
from ..source import Source
from .edits import EditOutcome


class FixResult(BaseModel):
    source: Source
    copy_root: str
    before: AuditSummary
    after: AuditSummary
    rule_counts_before: dict[str, int]
    rule_counts_after: dict[str, int]
    accepted: list[EditOutcome]
    rejected: list[EditOutcome]
    manual_checks: list[str]
    changed_files: list[str]
    rounds: int

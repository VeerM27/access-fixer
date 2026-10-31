from datetime import UTC, datetime

from access_fixer.audit.score import AuditSummary
from access_fixer.fix.edits import Edit, EditOutcome
from access_fixer.fix.result import FixResult
from access_fixer.github_pr import branch_name, changed_files_payload, pr_body, pr_title
from access_fixer.source import Source


def _summary(failing: int, score: float) -> AuditSummary:
    return AuditSummary(
        score=score, failing_nodes=failing, pages=1,
        by_impact={"critical": failing, "serious": 0, "moderate": 0, "minor": 0},
        top_rules=[], advisories={}, needs_review={},
    )


def _result(tmp_path) -> FixResult:
    (tmp_path / "index.html").write_text('<img alt="Logo">')
    edit = Edit(file="index.html", find="<img>", replace='<img alt="Logo">',
                rule_id="image-alt", reason="adds alt text")
    bad = Edit(file="index.html", find="<a>", replace="", rule_id="link-name", reason="")
    return FixResult(
        source=Source(root="/x", owner="o", repo="r"), copy_root=str(tmp_path),
        before=_summary(3, 50.0), after=_summary(0, 100.0),
        rule_counts_before={"image-alt": 3}, rule_counts_after={},
        accepted=[EditOutcome(edit=edit, accepted=True)],
        rejected=[EditOutcome(edit=bad, accepted=False, reason="made link-name worse")],
        manual_checks=['index.html: suggested alt text, please check: "Logo"'],
        changed_files=["index.html"], rounds=1,
    )


def test_pr_body_has_before_after_table_and_checks(tmp_path):
    body = pr_body(_result(tmp_path))
    assert "| **Failing elements** | **3** | **0** |" in body
    assert "| Score (mean pass rate per rule) | 50.0 | 100.0 |" in body
    assert "`image-alt`: 1 edit(s)" in body
    assert "made link-name worse" in body
    assert "suggested alt text" in body
    assert "Generated" not in body


def test_title_branch_and_files(tmp_path):
    result = _result(tmp_path)
    assert pr_title(result) == "Fix 3 accessibility failures (WCAG 2.2 AA)"
    now = datetime(2026, 10, 31, 9, 5, 0, tzinfo=UTC)
    assert branch_name(now) == "access-fixer/20261031-090500"
    assert changed_files_payload(result) == [{"path": "index.html", "content": '<img alt="Logo">'}]

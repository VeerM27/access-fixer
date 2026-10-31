"""Turn axe results into a score and a summary."""

from collections import Counter

from pydantic import BaseModel

from .axe_runner import PageAudit, RuleResult

IMPACTS = ("critical", "serious", "moderate", "minor")


class AuditSummary(BaseModel):
    score: float
    failing_nodes: int
    pages: int
    by_impact: dict[str, int]
    top_rules: list[tuple[str, int]]
    advisories: dict[str, int]
    needs_review: dict[str, int]


def _count_nodes(rule_lists: list[list[RuleResult]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for rules in rule_lists:
        for rule in rules:
            counts[rule.id] += len(rule.nodes)
    return counts


def site_score(passing: Counter[str], failing: Counter[str]) -> float:
    """Mean pass rate over rules that touched at least one node, as 0-100."""
    rates = []
    for rule_id in passing.keys() | failing.keys():
        total = passing[rule_id] + failing[rule_id]
        if total:
            rates.append(passing[rule_id] / total)
    if not rates:
        return 100.0
    return round(100 * sum(rates) / len(rates), 1)


def summarize(audits: list[PageAudit]) -> AuditSummary:
    passing = _count_nodes([a.passes for a in audits])
    failing = _count_nodes([a.violations for a in audits])

    by_impact = dict.fromkeys(IMPACTS, 0)
    for audit in audits:
        for rule in audit.violations:
            by_impact[rule.impact or "minor"] += len(rule.nodes)

    return AuditSummary(
        score=site_score(passing, failing),
        failing_nodes=sum(failing.values()),
        pages=len(audits),
        by_impact=by_impact,
        top_rules=failing.most_common(5),
        advisories=dict(_count_nodes([a.advisories for a in audits])),
        needs_review=dict(_count_nodes([a.incomplete for a in audits])),
    )

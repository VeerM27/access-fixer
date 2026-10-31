from collections import Counter

from access_fixer.audit.axe_runner import AxeNode, PageAudit, RuleResult
from access_fixer.audit.score import site_score, summarize


def _rule(rule_id: str, nodes: int, impact: str | None = None) -> RuleResult:
    node = AxeNode(target=["x"], html="<x>")
    return RuleResult(id=rule_id, impact=impact, help="", help_url="", nodes=[node] * nodes)


def test_score_is_mean_pass_rate_per_rule():
    # image-alt: 1 of 4 pass (25%), label: 3 of 3 pass (100%) -> mean 62.5
    assert site_score(Counter({"image-alt": 1, "label": 3}), Counter({"image-alt": 3})) == 62.5


def test_rules_with_no_nodes_do_not_count():
    assert site_score(Counter({"label": 2, "empty": 0}), Counter()) == 100.0


def test_summary_counts_failures():
    page = PageAudit(
        path="index.html",
        violations=[_rule("image-alt", 3, "critical"), _rule("color-contrast", 2, "serious")],
        passes=[_rule("image-alt", 1)],
        incomplete=[_rule("duplicate-id-aria", 1)],
        advisories=[_rule("region", 2)],
    )
    summary = summarize([page])

    assert summary.failing_nodes == 5
    assert summary.by_impact["critical"] == 3
    assert summary.top_rules[0] == ("image-alt", 3)
    assert summary.advisories == {"region": 2}
    assert summary.needs_review == {"duplicate-id-aria": 1}
    assert summary.score == 12.5

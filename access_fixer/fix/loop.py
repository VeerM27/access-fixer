"""One fix round: apply edits, re-audit, and revert anything that made a page worse."""

import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from pydantic import BaseModel

from ..audit.axe_runner import PageAudit, audit_site
from ..audit.pages import find_pages
from .edits import Edit, EditOutcome, apply_edits, revert
from .prompt import linked_css

ALT_TEXT = re.compile(r'alt="([^"]+)"')
VAGUE_LINK_TEXT ={"click here", "here", "read more", "more", "learn more", "link"}


class RoundResult(BaseModel):
    accepted: list[EditOutcome]
    rejected: list[EditOutcome]
    audits: list[PageAudit]


def failing_counts(audits: list[PageAudit]) -> dict[str, Counter[str]]:
    return {
        audit.path: Counter({rule.id: len(rule.nodes) for rule in audit.violations})
        for audit in audits
    }


def _worse_rules(before: Counter[str], after: Counter[str]) -> list[str]:
    return [rule for rule, count in after.items() if count > before[rule]]


async def run_round(root: Path, audits: list[PageAudit], edits: list[Edit]) -> RoundResult:
    accepted, rejected, originals = apply_edits(root, edits)
    if not accepted:
        return RoundResult(accepted=[], rejected=rejected, audits=audits)

    before = failing_counts(audits)
    after = failing_counts(await audit_site(root, find_pages(root)))
    css_edited = {file for file in originals if file.endswith(".css")}

    to_revert: dict[str, str] = {}  # file -> why
    for page, counts in after.items():
        worse = _worse_rules(before.get(page, Counter()), counts)
        if not worse:
            continue
        why = f"made {', '.join(worse)} worse on {page}"
        suspects = {page} | (set(linked_css(root, page)) & css_edited)
        for file in suspects & originals.keys():
            to_revert.setdefault(file, why)

    if to_revert:
        revert(root, originals, set(to_revert))
        still_accepted = []
        for outcome in accepted:
            if outcome.edit.file in to_revert:
                reason = to_revert[outcome.edit.file]
                rejected.append(EditOutcome(edit=outcome.edit, accepted=False, reason=reason))
            else:
                still_accepted.append(outcome)
        accepted = still_accepted

    return RoundResult(
        accepted=accepted, rejected=rejected, audits=await audit_site(root, find_pages(root))
    )


class _LinkText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.text = ""
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.depth, self.text = 1, ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.depth:
            self.depth = 0
            self.links.append(" ".join(self.text.split()))

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.text += data


def manual_checks(root: Path, accepted: list[EditOutcome]) -> list[str]:
    checks = []
    for page in find_pages(root):
        parser = _LinkText()
        parser.feed((root / page).read_text())
        for text in parser.links:
            if text.lower().strip(".!") in VAGUE_LINK_TEXT:
                checks.append(f'{page}: link text "{text}" is vague, say where it goes')
    for outcome in accepted:
        if outcome.edit.rule_id == "image-alt":
            for alt in ALT_TEXT.findall(outcome.edit.replace):
                checks.append(f'{outcome.edit.file}: suggested alt text, please check: "{alt}"')
    return checks

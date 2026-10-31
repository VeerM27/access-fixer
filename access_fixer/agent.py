"""The Access Fixer workflow: read the site location, fix it on a copy, report the results."""

import json
import logging
import re
from collections import Counter
from pathlib import Path

from google.adk import Context, Event, Workflow
from google.adk.workflow import node
from google.genai import types
from pydantic import BaseModel, ValidationError

from .audit.axe_runner import audit_site
from .audit.pages import find_pages
from .audit.score import AuditSummary, summarize
from .config import load_settings
from .fix import fixer
from .fix.edits import Edit, EditOutcome
from .fix.loop import manual_checks, run_round
from .fix.prompt import build_fixer_prompt
from .fix.workspace import make_working_copy

GITHUB_URL = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+/?$")
MAX_ROUNDS = 2

log = logging.getLogger("access_fixer")


class FixResult(BaseModel):
    original_root: str
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


def _message_text(node_input: types.Content | str) -> str:
    if isinstance(node_input, str):
        return node_input.strip()
    return " ".join(part.text or "" for part in node_input.parts or []).strip()


def read_source(node_input: types.Content | str) -> Event:
    """Turn the user's message into a local folder to audit, or stop with a reason."""
    text = _message_text(node_input)
    if GITHUB_URL.match(text):
        return Event(route="stop", message="GitHub cloning arrives in Phase 3. Pass a local path.")
    if not load_settings().allow_local:
        return Event(route="stop", message="Send a GitHub HTTPS URL like https://github.com/owner/repo.")
    root = Path(text).expanduser().resolve()
    if not root.is_dir():
        return Event(route="stop", message=f"Not a folder: {text}")
    return Event(route="ok", output=str(root))


def _rule_counts(audits) -> Counter[str]:
    counts: Counter[str] = Counter()
    for audit in audits:
        for rule in audit.violations:
            counts[rule.id] += len(rule.nodes)
    return counts


def _parse_edits(raw: list | None) -> list[Edit]:
    edits = []
    for item in raw or []:
        try:
            edits.append(Edit.model_validate(item))
        except ValidationError:
            continue
    return edits


@node(rerun_on_resume=True)
async def fix_pipeline(ctx: Context, node_input: str) -> FixResult:
    original = Path(node_input)
    copy_root = make_working_copy(original)
    audits = await audit_site(copy_root, find_pages(copy_root))
    before_audits = audits
    accepted: list[EditOutcome] = []
    rejected: list[EditOutcome] = []

    rounds = 0
    while rounds < MAX_ROUNDS and _rule_counts(audits):
        rounds += 1
        usage_before = Counter(fixer.TOKEN_USAGE[ctx.invocation_id])
        raw = await ctx.run_node(fixer.fixer_agent, build_fixer_prompt(copy_root, audits))
        failing_before = sum(_rule_counts(audits).values())
        result = await run_round(copy_root, audits, _parse_edits(raw))
        audits = result.audits
        accepted += result.accepted
        rejected += result.rejected
        tokens = fixer.TOKEN_USAGE[ctx.invocation_id] - usage_before
        log.info(json.dumps({
            "event": "fix_round",
            "round": rounds,
            "model": fixer.MODEL_USED.get(ctx.invocation_id, "none"),
            "prompt_tokens": tokens["prompt_tokens"],
            "output_tokens": tokens["output_tokens"],
            "total_tokens": tokens["total_tokens"],
            "accepted": len(result.accepted),
            "rejected": len(result.rejected),
            "failing_before": failing_before,
            "failing_after": sum(_rule_counts(audits).values()),
        }))

    return FixResult(
        original_root=str(original),
        copy_root=str(copy_root),
        before=summarize(before_audits),
        after=summarize(audits),
        rule_counts_before=dict(_rule_counts(before_audits)),
        rule_counts_after=dict(_rule_counts(audits)),
        accepted=accepted,
        rejected=rejected,
        manual_checks=manual_checks(copy_root, accepted),
        changed_files=sorted({outcome.edit.file for outcome in accepted}),
        rounds=rounds,
    )


def format_report(result: FixResult) -> str:
    before, after = result.before, result.after
    drop = 100 * (before.failing_nodes - after.failing_nodes) / max(before.failing_nodes, 1)
    by_rule = Counter(outcome.edit.rule_id for outcome in result.accepted)
    worse = [
        rule for rule, count in result.rule_counts_after.items()
        if count > result.rule_counts_before.get(rule, 0)
    ]
    lines = [
        f"**Failures {before.failing_nodes} → {after.failing_nodes}** ({drop:.0f}% fewer) "
        f"in {result.rounds} round(s). Score {before.score} → {after.score}.",
        "",
        "Accepted edits by rule: "
        + (", ".join(f"`{rule}` {n}" for rule, n in by_rule.most_common()) or "none"),
        f"Rules that got worse: {', '.join(worse) or 'none'}",
        "Still failing: "
        + (", ".join(f"`{rule}` {n}" for rule, n in result.rule_counts_after.items()) or "none"),
        "",
        f"Rejected edits ({len(result.rejected)}):",
        *[f"- {o.edit.file} `{o.edit.rule_id}`: {o.reason}" for o in result.rejected],
        "",
        "Manual checks:",
        *[f"- {check}" for check in result.manual_checks or ["none"]],
        "",
        f"Changed files: {', '.join(result.changed_files) or 'none'}",
    ]
    return "\n".join(lines)


def report(node_input: FixResult) -> Event:
    return Event(
        message=format_report(node_input),
        output=node_input,
        state={
            "original_root": node_input.original_root,
            "copy_root": node_input.copy_root,
            "edits": [outcome.edit.model_dump() for outcome in node_input.accepted],
            "changed_files": node_input.changed_files,
        },
    )


root_agent = Workflow(
    name="access_fixer",
    edges=[
        ("START", read_source),
        (read_source, {"ok": fix_pipeline}),
        (fix_pipeline, report),
    ],
)

"""The Access Fixer workflow: read the site location, audit it, report the results."""

import re
from pathlib import Path

from google.adk import Event, Workflow
from google.genai import types

from .audit.axe_runner import audit_site
from .audit.pages import find_pages
from .audit.score import AuditSummary, summarize
from .config import load_settings

GITHUB_URL = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+/?$")


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


async def run_audit(node_input: str) -> Event:
    root = Path(node_input)
    pages = find_pages(root)
    summary = summarize(await audit_site(root, pages))
    return Event(output=summary, state={"site_root": str(root), "audit": summary.model_dump()})


def format_report(summary: AuditSummary) -> str:
    impacts = ", ".join(f"{name} {count}" for name, count in summary.by_impact.items() if count)
    top = "\n".join(f"- `{rule}`: {count}" for rule, count in summary.top_rules)
    advisories = ", ".join(f"`{rule}` {count}" for rule, count in summary.advisories.items())
    review = ", ".join(f"`{rule}` {count}" for rule, count in summary.needs_review.items())
    return (
        f"**{summary.failing_nodes} failing elements** across {summary.pages} pages "
        f"(WCAG 2.2 AA by axe). Score {summary.score}/100.\n\n"
        f"By impact: {impacts or 'none'}\n\nTop rules:\n{top or '- none'}\n\n"
        f"Advisories (not scored): {advisories or 'none'}\n\n"
        f"Needs review: {review or 'none'}"
    )


def report(node_input: AuditSummary) -> Event:
    return Event(message=format_report(node_input), output=node_input)


root_agent = Workflow(
    name="access_fixer",
    edges=[
        ("START", read_source),
        (read_source, {"ok": run_audit}),
        (run_audit, report),
    ],
)

"""Open the pull request by calling GitHub MCP tools directly from code, with no LLM."""

import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from google.adk import Context
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from .fix.result import FixResult

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
PR_TOOLS = ["create_branch", "push_files", "create_pull_request"]
PR_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
# The create call may only give the API URL (".../pulls/1") or the number.
PR_NUMBER = re.compile(r"/pulls?/(\d+)|\"number\":\s*(\d+)")


class PullRequestError(Exception):
    """A GitHub step failed; the message is safe to show (never contains the token)."""


def branch_name(now: datetime | None = None) -> str:
    return f"access-fixer/{(now or datetime.now(UTC)):%Y%m%d-%H%M%S}"


def pr_title(result: FixResult) -> str:
    fixed = result.before.failing_nodes - result.after.failing_nodes
    return f"Fix {fixed} accessibility failures (WCAG 2.2 AA)"


def pr_body(result: FixResult) -> str:
    before, after = result.before, result.after
    impact_rows = [
        f"| {impact.capitalize()} | {before.by_impact.get(impact, 0)} | "
        f"{after.by_impact.get(impact, 0)} |"
        for impact in before.by_impact
    ]
    by_rule = Counter(o.edit.rule_id for o in result.accepted)
    lines = [
        "Accessibility fixes for WCAG 2.2 AA, checked with axe-core 4.12.1 on every page "
        "before and after the change.",
        "",
        "| | Before | After |",
        "|---|---|---|",
        f"| **Failing elements** | **{before.failing_nodes}** | **{after.failing_nodes}** |",
        f"| Score (mean pass rate per rule) | {before.score} | {after.score} |",
        *impact_rows,
        "",
        "### Fixes",
        *[f"- `{rule}`: {n} edit(s)" for rule, n in by_rule.most_common()],
        "",
        "<details><summary>Every edit</summary>",
        "",
        *[f"- `{o.edit.file}` ({o.edit.rule_id}): {o.edit.reason}" for o in result.accepted],
        "",
        "</details>",
        "",
    ]
    if result.rejected:
        lines += [
            "### Edits that were tried and thrown out",
            *[f"- `{o.edit.file}` ({o.edit.rule_id}): {o.reason}" for o in result.rejected],
            "",
        ]
    lines += [
        "### Please check by hand",
        *[f"- {check}" for check in result.manual_checks or ["Nothing flagged."]],
        "",
        "Automated checks catch only part of WCAG. Keyboard use, screen reader output and "
        "the meaning of link text still need a person.",
    ]
    return "\n".join(lines)


def changed_files_payload(result: FixResult) -> list[dict[str, str]]:
    copy_root = Path(result.copy_root)
    return [
        {"path": file, "content": (copy_root / file).read_text()} for file in result.changed_files
    ]


def _toolset() -> McpToolset:
    token = os.environ.get("GITHUB_PAT", "")
    if not token:
        raise PullRequestError("GITHUB_PAT is not set.")
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=GITHUB_MCP_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "X-MCP-Toolsets": "repos,pull_requests",
            },
        ),
        tool_filter=PR_TOOLS,
    )


def _result_text(result: object) -> str:
    if isinstance(result, dict):
        parts = result.get("content") or []
        text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict))
        if result.get("isError") or result.get("is_error"):
            raise PullRequestError(text[:300] or "GitHub MCP tool failed.")
        return text
    return str(result)


async def open_pull_request(result: FixResult, ctx: Context) -> str:
    """Create a branch, push the changed files to it, open the PR. Returns the PR URL."""
    source = result.source
    branch = branch_name()
    toolset = _toolset()
    try:
        tools = {tool.name: tool for tool in await toolset.get_tools()}
        missing = set(PR_TOOLS) - tools.keys()
        if missing:
            raise PullRequestError(f"GitHub MCP server is missing tools: {sorted(missing)}")

        async def call(name: str, **args: object) -> str:
            return _result_text(await tools[name].run_async(args=args, tool_context=ctx))

        repo = {"owner": source.owner, "repo": source.repo}
        await call("create_branch", **repo, branch=branch, from_branch=source.base_branch)
        await call(
            "push_files", **repo, branch=branch, files=changed_files_payload(result),
            message="fix: accessibility fixes for wcag 2.2 aa",
        )
        text = await call(
            "create_pull_request", **repo, title=pr_title(result), body=pr_body(result),
            head=branch, base=source.base_branch,
        )
    finally:
        await toolset.close()

    url = pr_url(text, source.owner, source.repo)
    if url is None:
        raise PullRequestError(
            f"The pull request was created from {branch} but no link came back."
        )
    return url


def pr_url(text: str, owner: str | None, repo: str | None) -> str | None:
    if match := PR_URL.search(text):
        return match.group(0)
    if match := PR_NUMBER.search(text):
        return f"https://github.com/{owner}/{repo}/pull/{match.group(1) or match.group(2)}"
    return None

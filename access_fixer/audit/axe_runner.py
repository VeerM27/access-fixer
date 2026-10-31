"""Run axe-core in Playwright and return typed results."""

from pathlib import Path
from urllib.parse import urlsplit

from axe_playwright_python.async_playwright import Axe
from playwright.async_api import Route, async_playwright
from pydantic import BaseModel

from .serve import serve_folder

WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
ADVISORY_TAGS = ["best-practice"]

# Always pass explicit options: the library default ({"resultTypes": ["violations"]})
# trims `passes` to one node per rule, which breaks the pass-rate score.
WCAG_OPTIONS = {"runOnly": {"type": "tag", "values": WCAG_TAGS}}
ADVISORY_OPTIONS = {"runOnly": {"type": "tag", "values": ADVISORY_TAGS}}


class AxeNode(BaseModel):
    target: list[str]
    html: str
    failure_summary: str = ""


class RuleResult(BaseModel):
    id: str
    impact: str | None = None
    help: str
    help_url: str
    nodes: list[AxeNode]


class PageAudit(BaseModel):
    path: str
    violations: list[RuleResult]
    passes: list[RuleResult]
    incomplete: list[RuleResult]
    advisories: list[RuleResult]


def _rules(raw_rules: list[dict]) -> list[RuleResult]:
    return [
        RuleResult(
            id=rule["id"],
            impact=rule.get("impact"),
            help=rule["help"],
            help_url=rule["helpUrl"],
            nodes=[
                AxeNode(
                    target=[str(t) for t in node["target"]],
                    html=node["html"],
                    failure_summary=node.get("failureSummary") or "",
                )
                for node in rule["nodes"]
            ],
        )
        for rule in raw_rules
    ]


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc


async def audit_site(root: Path, pages: list[str]) -> list[PageAudit]:
    """Serve `root` locally and run the WCAG and best-practice axe passes on each page."""
    axe = Axe()
    audits = []
    with serve_folder(root) as base_url:
        local_origin = _origin(base_url)

        async def only_local(route: Route) -> None:
            # Page content is untrusted: never let it reach anything but our own server.
            if _origin(route.request.url) == local_origin:
                await route.continue_()
            else:
                await route.abort()

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            context = await browser.new_context()
            await context.route("**/*", only_local)
            page = await context.new_page()
            for path in pages:
                await page.goto(f"{base_url}/{path}", wait_until="load")
                wcag = (await axe.run(page, options=WCAG_OPTIONS)).response
                advisory = (await axe.run(page, options=ADVISORY_OPTIONS)).response
                audits.append(
                    PageAudit(
                        path=path,
                        violations=_rules(wcag["violations"]),
                        passes=_rules(wcag["passes"]),
                        incomplete=_rules(wcag["incomplete"]),
                        advisories=_rules(advisory["violations"]),
                    )
                )
            await browser.close()
    return audits

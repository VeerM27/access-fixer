from pathlib import Path

from access_fixer.audit.axe_runner import audit_site
from access_fixer.audit.pages import find_pages

FIXTURE = Path(__file__).parent / "fixtures" / "basic_site"


async def test_finds_known_fixture_failures():
    audits = await audit_site(FIXTURE, find_pages(FIXTURE))

    failing = {rule.id for audit in audits for rule in audit.violations}
    assert {"image-alt", "label", "button-name", "color-contrast", "link-name"} <= failing
    assert "html-has-lang" in failing
    assert all(audit.passes for audit in audits)

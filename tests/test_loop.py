from pathlib import Path

from access_fixer.audit.axe_runner import audit_site
from access_fixer.audit.pages import find_pages
from access_fixer.fix.edits import Edit
from access_fixer.fix.loop import failing_counts, manual_checks, run_round
from access_fixer.fix.workspace import make_working_copy

FIXTURE = Path(__file__).parent / "fixtures" / "basic_site"
IMG = '<img src="logo.svg" width="80" height="80">'


async def _start():
    root = make_working_copy(FIXTURE)
    return root, await audit_site(root, find_pages(root))


async def test_good_edit_is_kept():
    root, audits = await _start()
    alt = IMG.replace("<img", '<img alt="Fixture logo"')
    edit = Edit(file="index.html", find=IMG, replace=alt, rule_id="image-alt", reason="")

    result = await run_round(root, audits, [edit])

    assert len(result.accepted) == 1
    assert failing_counts(result.audits)["index.html"]["image-alt"] == 0
    assert any("suggested alt text" in check for check in manual_checks(root, result.accepted))


async def test_edit_that_adds_a_failure_is_reverted():
    root, audits = await _start()
    bad = Edit(
        file="index.html",
        find='<a href="about.html">About us</a>',
        replace='<a href="about.html"></a>',
        rule_id="link-name",
        reason="",
    )

    result = await run_round(root, audits, [bad])

    assert not result.accepted
    assert "made link-name worse on index.html" in result.rejected[0].reason
    assert "About us" in (root / "index.html").read_text()

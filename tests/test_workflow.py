from pathlib import Path

from google.adk.runners import InMemoryRunner

from access_fixer.agent import root_agent
from access_fixer.fix import fixer

FIXTURE = Path(__file__).parent / "fixtures" / "basic_site"


def fake_fixer(node_input: str) -> list[dict]:
    """Stands in for Gemini so CI never makes a model call."""
    return [
        {
            "file": "index.html",
            "find": '<img src="logo.svg"',
            "replace": '<img alt="Fixture logo" src="logo.svg"',
            "rule_id": "image-alt",
            "reason": "adds alt text",
        }
    ]


async def _reply_text(message: str) -> str:
    runner = InMemoryRunner(agent=root_agent, app_name="access_fixer")
    events = await runner.run_debug(message, quiet=True)
    texts = [part.text for e in events if e.content for part in e.content.parts or [] if part.text]
    return "\n".join(texts)


async def test_fixes_a_copy_of_the_local_fixture(monkeypatch):
    monkeypatch.setenv("ACCESS_FIXER_ALLOW_LOCAL", "1")
    monkeypatch.setattr(fixer, "fixer_agent", fake_fixer)
    original = (FIXTURE / "index.html").read_text()

    reply = await _reply_text(str(FIXTURE))

    assert "**Failures" in reply
    assert "`image-alt` 1" in reply
    assert "suggested alt text" in reply
    assert (FIXTURE / "index.html").read_text() == original


async def test_refuses_local_path_when_not_allowed(monkeypatch):
    monkeypatch.setenv("ACCESS_FIXER_ALLOW_LOCAL", "0")
    reply = await _reply_text(str(FIXTURE))
    assert "GitHub HTTPS URL" in reply
    assert "**Failures" not in reply

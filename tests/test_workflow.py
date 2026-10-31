from pathlib import Path

from google.adk.runners import InMemoryRunner

from access_fixer.agent import root_agent

FIXTURE = Path(__file__).parent / "fixtures" / "basic_site"


async def _reply_text(message: str) -> str:
    runner = InMemoryRunner(agent=root_agent, app_name="access_fixer")
    events = await runner.run_debug(message, quiet=True)
    texts = [part.text for e in events if e.content for part in e.content.parts or [] if part.text]
    return "\n".join(texts)


async def test_audits_local_fixture(monkeypatch):
    monkeypatch.setenv("ACCESS_FIXER_ALLOW_LOCAL", "1")
    reply = await _reply_text(str(FIXTURE))
    assert "failing elements" in reply
    assert "image-alt" in reply


async def test_refuses_local_path_when_not_allowed(monkeypatch):
    monkeypatch.setenv("ACCESS_FIXER_ALLOW_LOCAL", "0")
    reply = await _reply_text(str(FIXTURE))
    assert "GitHub HTTPS URL" in reply
    assert "failing elements" not in reply

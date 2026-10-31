from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.genai import types

from access_fixer import agent, github_pr
from access_fixer.fix import fixer
from access_fixer.source import Source

FIXTURE = Path(__file__).parent / "fixtures" / "basic_site"


def fake_fixer(node_input: str) -> list[dict]:
    return [{
        "file": "index.html",
        "find": '<img src="logo.svg"',
        "replace": '<img alt="Fixture logo" src="logo.svg"',
        "rule_id": "image-alt",
        "reason": "adds alt text",
    }]


def _texts(event) -> list[str]:
    return [p.text for p in (event.content.parts if event.content else []) if p.text]


async def _run_until_approval(monkeypatch, opened: list):
    async def fake_open_pull_request(result, ctx):
        opened.append(result)
        return "https://github.com/owner/repo/pull/7"

    monkeypatch.setenv("ACCESS_FIXER_ALLOW_LOCAL", "1")
    monkeypatch.setattr(fixer, "fixer_agent", fake_fixer)
    monkeypatch.setattr(github_pr, "open_pull_request", fake_open_pull_request)
    monkeypatch.setattr(
        agent, "local_source", lambda root: Source(root=str(root), owner="owner", repo="repo")
    )
    runner = InMemoryRunner(agent=agent.root_agent, app_name="access_fixer")
    session = await runner.session_service.create_session(app_name="access_fixer", user_id="u")
    message = types.Content(role="user", parts=[types.Part(text=str(FIXTURE))])
    request = None
    async for event in runner.run_async(user_id="u", session_id=session.id, new_message=message):
        for part in event.content.parts if event.content else []:
            if part.function_call and part.function_call.name == "adk_request_input":
                request = part.function_call
    assert request is not None, "workflow should pause for approval"
    return runner, session, request


async def _reply(runner, session, request, answer: str) -> str:
    response = types.FunctionResponse(name=request.name, id=request.id, response={"result": answer})
    message = types.Content(role="user", parts=[types.Part(function_response=response)])
    texts = []
    async for event in runner.run_async(user_id="u", session_id=session.id, new_message=message):
        texts += _texts(event)
    return "\n".join(texts)


async def test_yes_opens_the_pull_request(monkeypatch):
    opened: list = []
    runner, session, request = await _run_until_approval(monkeypatch, opened)
    assert "owner/repo" in request.args["message"]

    reply = await _reply(runner, session, request, "yes")

    assert "https://github.com/owner/repo/pull/7" in reply
    assert len(opened) == 1 and opened[0].changed_files == ["index.html"]


async def test_anything_else_leaves_github_untouched(monkeypatch):
    opened: list = []
    runner, session, request = await _run_until_approval(monkeypatch, opened)

    reply = await _reply(runner, session, request, "no thanks")

    assert "Nothing was changed on GitHub" in reply
    assert opened == []

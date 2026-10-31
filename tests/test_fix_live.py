"""Real Gemini run. Skipped unless ACCESS_FIXER_LIVE=1, so CI never calls the model."""

import os
from pathlib import Path

import pytest
from google.adk.runners import InMemoryRunner

from access_fixer.agent import FixResult, root_agent

FIXTURE = Path(__file__).parent / "fixtures" / "basic_site"

pytestmark = pytest.mark.skipif(
    os.getenv("ACCESS_FIXER_LIVE") != "1", reason="set ACCESS_FIXER_LIVE=1 to call Gemini"
)


async def test_live_fix_reduces_failures(monkeypatch):
    monkeypatch.setenv("ACCESS_FIXER_ALLOW_LOCAL", "1")
    runner = InMemoryRunner(agent=root_agent, app_name="access_fixer")
    events = await runner.run_debug(str(FIXTURE), quiet=True)

    outputs = [e.output for e in events if isinstance(e.output, FixResult | dict)]
    result = FixResult.model_validate(outputs[-1])
    assert result.after.failing_nodes < result.before.failing_nodes
    for rule, count in result.rule_counts_after.items():
        assert count <= result.rule_counts_before.get(rule, 0)

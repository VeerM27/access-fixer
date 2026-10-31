from access_fixer.agent import root_agent
from access_fixer.config import load_settings


def test_root_agent_loads():
    assert root_agent.name == "access_fixer"


def test_local_paths_are_off_by_default(monkeypatch):
    monkeypatch.delenv("ACCESS_FIXER_ALLOW_LOCAL", raising=False)
    assert load_settings().allow_local is False

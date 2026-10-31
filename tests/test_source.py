import pytest

from access_fixer import source
from access_fixer.source import SourceError, check_folder_limits, parse_github_url


def test_parses_github_urls():
    assert parse_github_url("https://github.com/VeerM27/demo-charity-site") == (
        "VeerM27",
        "demo-charity-site",
    )
    assert parse_github_url("https://github.com/a/b.git") == ("a", "b")
    assert parse_github_url("http://github.com/a/b") is None
    assert parse_github_url("https://gitlab.com/a/b") is None
    assert parse_github_url("https://github.com/a/b/tree/main") is None


def test_rejects_too_many_files(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "MAX_REPO_FILES", 2)
    for name in ("a.html", "b.html", "c.html"):
        (tmp_path / name).write_text("x")
    with pytest.raises(SourceError, match="3 files"):
        check_folder_limits(tmp_path)


def test_rejects_big_repo_before_cloning(monkeypatch):
    monkeypatch.setattr(source, "_repo_info", lambda owner, repo: {"size": 60 * 1024})
    with pytest.raises(SourceError, match="50 MB"):
        source.clone_github_repo("a", "b")

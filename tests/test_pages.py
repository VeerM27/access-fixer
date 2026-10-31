from pathlib import Path

from access_fixer.audit.pages import find_pages

FIXTURE = Path(__file__).parent / "fixtures" / "basic_site"


def test_finds_fixture_pages():
    assert find_pages(FIXTURE) == ["about.html", "index.html"]


def test_skips_symlink_outside_root(tmp_path):
    outside = tmp_path / "outside.html"
    outside.write_text("<p>secret</p>")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<p>home</p>")
    (site / "leak.html").symlink_to(outside)

    assert find_pages(site) == ["index.html"]

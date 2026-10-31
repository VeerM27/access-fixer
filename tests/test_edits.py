from pathlib import Path

from access_fixer.fix.edits import Edit, apply_edits, revert


def _site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text('<img src="a.png"><p>hi</p><p>hi</p>')
    (site / "app.js").write_text("alert(1)")
    (tmp_path / "outside.html").write_text("<p>outside</p>")
    return site


def _edit(file: str, find: str, replace: str = "x") -> Edit:
    return Edit(file=file, find=find, replace=replace, rule_id="image-alt", reason="test")


def test_applies_unique_match_and_can_revert(tmp_path):
    site = _site(tmp_path)
    accepted, rejected, originals = apply_edits(
        site, [_edit("index.html", '<img src="a.png">', '<img src="a.png" alt="A">')]
    )
    assert len(accepted) == 1 and not rejected
    assert 'alt="A"' in (site / "index.html").read_text()

    revert(site, originals, {"index.html"})
    assert 'alt="A"' not in (site / "index.html").read_text()


def test_rejects_no_match(tmp_path):
    _, rejected, _ = apply_edits(_site(tmp_path), [_edit("index.html", "<nav>")])
    assert rejected[0].reason == "find text not in file"


def test_rejects_multiple_matches(tmp_path):
    _, rejected, _ = apply_edits(_site(tmp_path), [_edit("index.html", "<p>hi</p>")])
    assert rejected[0].reason == "find text matches 2 times"


def test_rejects_path_escape(tmp_path):
    site = _site(tmp_path)
    _, rejected, _ = apply_edits(site, [_edit("../outside.html", "outside")])
    assert rejected[0].reason == "path is outside the site"
    assert "outside" in (tmp_path / "outside.html").read_text()


def test_rejects_wrong_file_type(tmp_path):
    site = _site(tmp_path)
    _, rejected, _ = apply_edits(site, [_edit("app.js", "alert(1)")])
    assert rejected[0].reason == "only .html and .css files can be edited"
    assert (site / "app.js").read_text() == "alert(1)"

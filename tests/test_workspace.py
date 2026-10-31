from pathlib import Path

from access_fixer.fix.workspace import make_working_copy

FIXTURE = Path(__file__).parent / "fixtures" / "basic_site"


def test_copy_is_separate_from_original():
    copy_root = make_working_copy(FIXTURE)
    (copy_root / "index.html").write_text("changed")

    assert copy_root != FIXTURE
    assert "Fixture home" in (FIXTURE / "index.html").read_text()

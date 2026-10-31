import urllib.request
from pathlib import Path

from access_fixer.audit.serve import serve_folder

FIXTURE = Path(__file__).parent / "fixtures" / "basic_site"


def test_serves_fixture_page():
    with serve_folder(FIXTURE) as base_url:
        with urllib.request.urlopen(f"{base_url}/index.html") as response:
            assert b"Fixture home" in response.read()

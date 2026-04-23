from __future__ import annotations

import json
from pathlib import Path

from patent_client_agents.mpep.transformers import parse_search_response, parse_section_html, parse_versions

FIXTURES = Path(__file__).parent / "data" / "mpep"


def load(name: str) -> str:
    path = FIXTURES / name
    return path.read_text()


def test_parse_search_response_extracts_hits() -> None:
    payload = json.loads(load("search_response.json"))
    resp = parse_search_response(payload, base_url="https://mpep.uspto.gov", page=1, per_page=10)
    assert resp.hits
    hit = resp.hits[0]
    assert hit.href == "d0e122292.html"
    assert hit.path == ["1200 - Appeal"]


def test_parse_section_html_returns_text_and_title() -> None:
    payload = json.loads(load("search_response.json"))
    section = parse_section_html(payload["content"], version="current", href="d0e122292.html")
    assert section.title == "1207 Appeal Brief"
    assert "Example content" in section.text


def test_parse_versions_extracts_options() -> None:
    html = load("versions.html")
    versions = parse_versions(html)
    assert len(versions) == 2
    assert versions[-1].current is True
    assert versions[-1].value == "current"

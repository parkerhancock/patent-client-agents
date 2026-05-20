"""Pytest fixtures for the PRH (Finland) connector tests.

Committed fixture JSON in ``fixtures/`` is real-API capture from
2026-05-19 — used to pin response-shape contracts without forcing a
network round-trip on every test run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def patent_search_payload() -> dict:
    return json.loads((FIXTURES_DIR / "patent-search.json").read_text())


@pytest.fixture
def patent_get_payload() -> dict:
    return json.loads((FIXTURES_DIR / "patent-get.json").read_text())


@pytest.fixture
def tm_search_payload() -> dict:
    return json.loads((FIXTURES_DIR / "tm-search.json").read_text())


@pytest.fixture
def tmr_search_payload() -> dict:
    return json.loads((FIXTURES_DIR / "tmr-search.json").read_text())


@pytest.fixture
def design_search_payload() -> dict:
    return json.loads((FIXTURES_DIR / "design-search.json").read_text())

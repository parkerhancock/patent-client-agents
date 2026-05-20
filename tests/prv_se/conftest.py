"""Pytest fixtures for the PRV (Sweden) connector tests.

The committed fixture JSON files in ``fixtures/`` are real-API
captures from 2026-05-18 — used to pin the response-shape contracts
without requiring a network round-trip on every test run.
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
def patents_search_payload() -> dict:
    return json.loads((FIXTURES_DIR / "patents-search.json").read_text())


@pytest.fixture
def patent_get_payload() -> dict:
    return json.loads((FIXTURES_DIR / "patent-get.json").read_text())


@pytest.fixture
def tm_search_payload() -> dict:
    return json.loads((FIXTURES_DIR / "tm-search.json").read_text())


@pytest.fixture
def design_search_payload() -> dict:
    return json.loads((FIXTURES_DIR / "design-search.json").read_text())


@pytest.fixture
def spc_search_payload() -> dict:
    return json.loads((FIXTURES_DIR / "spc-search.json").read_text())

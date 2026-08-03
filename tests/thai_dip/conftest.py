"""Catalogue-derived synthetic fixtures for the Thailand DIP connector."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("DIP_DATA_EXCHANGE_TOKEN", "test-token")


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"

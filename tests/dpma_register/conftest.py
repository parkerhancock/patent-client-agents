"""Mock-only DPMAconnectPlus tests.

The XML files are synthetic and based on public interface documentation. They
are not recorded API responses. Community help with sanitized real samples is
welcome.
"""

from pathlib import Path

import pytest


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"

"""Schema-derived Swiss IPI connector fixtures.

These files are synthetic. They use the published datadelivery namespaces and
request contract, but they are not recorded responses from an IPI account.
"""

from pathlib import Path

import pytest


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"

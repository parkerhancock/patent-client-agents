from __future__ import annotations

import os

import pytest

LIVE_ENV_VAR = "IP_TOOLS_LIVE_TESTS"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run tests that hit live endpoints",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: marks tests that require access to live services",
    )


@pytest.fixture
def require_live(request: pytest.FixtureRequest) -> None:
    has_flag = bool(request.config.getoption("--run-live"))
    has_env = bool(os.getenv(LIVE_ENV_VAR))
    if not (has_flag or has_env):
        pytest.skip("Live test skipped. Set IP_TOOLS_LIVE_TESTS=1 or pass --run-live to enable.")


@pytest.fixture(scope="module")
def vcr_config():
    """VCR configuration for pytest-recording."""
    return {
        "filter_headers": [
            "authorization",
            "Authorization",
            "X-API-Key",
            "Cookie",
            "Set-Cookie",
        ],
        "filter_query_parameters": [
            "apiKey",
            "api_key",
        ],
        "decode_compressed_response": True,
    }

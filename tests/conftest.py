"""Pytest configuration for patent_client_agents tests.

Supports VCR recording for HTTP interactions:
    pytest tests/                           # replay from cassettes
    pytest tests/ --vcr-record=once         # record missing cassettes
    pytest tests/ --vcr-record=all          # re-record all cassettes

Cassettes are stored in ``tests/cassettes/`` with filenames derived from the
test nodeid.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import vcr

USPTO_LIVE_ENV_VAR = "USPTO_LIVE_TESTS"
JPO_LIVE_ENV_VAR = "JPO_LIVE_TESTS"

CASSETTES_DIR = Path(__file__).parent / "cassettes"
CASSETTES_DIR.mkdir(exist_ok=True)

_record_mode = "none"


def _sanitize_cassette_name(name: str) -> str:
    """Convert test nodeid to a cassette filename."""
    sanitized = re.sub(r"[^\w\-]", "_", name)
    sanitized = re.sub(r"_+", "_", sanitized)
    return sanitized.strip("_") + ".yaml"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live-uspto",
        action="store_true",
        default=False,
        help="Run tests that hit live USPTO endpoints",
    )
    parser.addoption(
        "--run-live-jpo",
        action="store_true",
        default=False,
        help="Run tests that hit live JPO endpoints",
    )
    try:
        parser.addoption(
            "--vcr-record",
            action="store",
            default="none",
            choices=["none", "once", "new_episodes", "all"],
            help="VCR record mode: none (replay), once (record if missing), new_episodes, all",
        )
    except ValueError:
        pass


def pytest_configure(config: pytest.Config) -> None:
    global _record_mode  # noqa: PLW0603
    _record_mode = config.getoption("--vcr-record", default="none")

    for marker in (
        "live_uspto: marks tests that require access to live USPTO services",
        "live_jpo: marks tests that require access to live JPO services",
        "vcr_cassette: marks tests that use VCR cassette recording",
    ):
        config.addinivalue_line("markers", marker)


@pytest.fixture
def require_live_uspto(request: pytest.FixtureRequest) -> None:
    has_flag = bool(request.config.getoption("--run-live-uspto"))
    has_env = bool(os.getenv(USPTO_LIVE_ENV_VAR))
    if not (has_flag or has_env):
        pytest.skip(
            "Live USPTO test skipped. Set USPTO_LIVE_TESTS=1 or pass --run-live-uspto to enable."
        )


@pytest.fixture
def require_live_jpo(request: pytest.FixtureRequest) -> None:
    has_flag = bool(request.config.getoption("--run-live-jpo"))
    has_env = bool(os.getenv(JPO_LIVE_ENV_VAR))
    if not (has_flag or has_env):
        pytest.skip("Live JPO test skipped. Set JPO_LIVE_TESTS=1 or pass --run-live-jpo to enable.")


def _create_vcr() -> vcr.VCR:
    return vcr.VCR(
        cassette_library_dir=str(CASSETTES_DIR),
        record_mode=_record_mode,  # type: ignore[arg-type]
        filter_headers=[
            ("authorization", "REDACTED"),
            ("x-api-key", "REDACTED"),
        ],
        filter_query_parameters=[
            ("api_key", "REDACTED"),
            ("apiKey", "REDACTED"),
        ],
        decode_compressed_response=True,
        match_on=["method", "scheme", "host", "port", "path", "query", "body"],
    )


@pytest.fixture
def vcr_cassette(request: pytest.FixtureRequest):
    """Wrap a test in a VCR cassette keyed by its nodeid."""
    cassette_name = _sanitize_cassette_name(request.node.nodeid)
    cassette_path = CASSETTES_DIR / cassette_name

    my_vcr = _create_vcr()
    with my_vcr.use_cassette(str(cassette_path)):  # type: ignore[attr-defined]
        yield cassette_path

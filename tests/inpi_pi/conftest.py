"""Pytest fixtures for the INPI France (api-gateway.inpi.fr) connector tests.

INPI's api-gateway uses a personal ``data.inpi.fr`` account
(session-bearer + XSRF) flow — ToS / CGU posture is BYOK and we do not
currently have credentials issued. INPI Data account signup is
French-only and acquisition is blocked behind manual approval, so this
connector ships with **synthesized JSON + ST.66/ST.86 XML fixtures**
under ``tests/inpi_pi/fixtures/`` and ``httpx.MockTransport`` — no VCR
cassettes are recorded for INPI in v1.

If/when live ``INPI_USERNAME`` + ``INPI_PASSWORD`` credentials are
acquired and live cassettes get recorded, the root conftest's VCR
``filter_query_parameters`` + ``filter_headers`` lists must be
extended (or verified to already scrub) the following so the secrets
never land on disk:

* Headers: ``Authorization`` (already filtered), ``Cookie`` (already
  filtered), ``Set-Cookie`` (already filtered), ``X-XSRF-TOKEN``
  (NOT yet filtered — add before recording), ``XSRF-TOKEN`` (cookie
  name; covered by the existing ``set-cookie`` / ``cookie`` filters
  but worth a re-check).
* Query params: INPI does not use query-string credentials, but the
  login response body carries ``access_token`` / ``refresh_token``
  and must be scrubbed via a ``before_record_response`` callback
  modelled on ``_scrub_jpo_token_response`` in the root conftest.
* ``INPI_PASSWORD`` must never appear in any cassette body — the
  login request body must be redacted on record.

Provided fixtures:

* ``inpi_client`` — an async-context :class:`InpiPiClient` with a
  placeholder username/password. Suitable for tests that swap in a
  mock transport via the ``client`` kwarg on :class:`InpiPiClient`.
* ``fixture_path`` — helper resolving fixture filenames under
  ``tests/inpi_pi/fixtures/``.
* ``fixture_bytes`` — helper reading fixture files as raw bytes.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio

from patent_client_agents.inpi_pi import InpiPiClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest_asyncio.fixture
async def inpi_client() -> AsyncIterator[InpiPiClient]:
    """Yield a context-managed INPI client with placeholder credentials.

    Resolves ``username`` / ``password`` from ``INPI_USERNAME`` /
    ``INPI_PASSWORD`` (set by this conftest as placeholders); tests
    that want to assert specific request shapes inject a mock transport
    via the ``client`` kwarg on a freshly-constructed
    :class:`InpiPiClient`.
    """
    username = os.environ.get("INPI_USERNAME", "test_user")
    password = os.environ.get("INPI_PASSWORD", "test_pass")
    async with InpiPiClient(username=username, password=password) as client:
        yield client


@pytest.fixture
def fixture_path() -> Callable[..., Path]:
    """Return a helper that resolves a fixture filename to an absolute Path."""

    def _resolve(name: str) -> Path:
        return FIXTURES_DIR / name

    return _resolve


@pytest.fixture
def fixture_bytes() -> Callable[..., bytes]:
    """Return a helper that reads a fixture file as raw bytes."""

    def _read(name: str) -> bytes:
        return (FIXTURES_DIR / name).read_bytes()

    return _read

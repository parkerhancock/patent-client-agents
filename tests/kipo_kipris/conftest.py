"""Pytest fixtures for the KIPO KIPRIS Plus connector tests.

KIPRIS Plus requires a per-user ``serviceKey`` (ToS §11 BYOK — no shared
keys). We do not currently have a real key issued (acquisition is
blocked behind Korean phone / i-PIN verification per spec §6 open
items), so this connector ships with **synthesized XML fixtures**
under ``tests/kipo_kipris/fixtures/`` and ``httpx.MockTransport`` —
no VCR cassettes are recorded for KIPRIS in v1.

If/when a live ``serviceKey`` is acquired and live cassettes get
recorded, the root conftest's VCR ``filter_query_parameters`` list
must be extended with ``("serviceKey", "REDACTED")`` so the key is
scrubbed from every cassette before it lands on disk.

Provided fixtures:

* ``kipris_client`` — an async-context :class:`KiprisClient` with a
  placeholder ``serviceKey``. Suitable for tests that swap in a mock
  transport via the ``client`` kwarg.
* ``fixture_path`` — helper resolving fixture filenames under
  ``tests/kipo_kipris/fixtures/``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio

from patent_client_agents.kipo_kipris import KiprisClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest_asyncio.fixture
async def kipris_client() -> AsyncIterator[KiprisClient]:
    """Yield a context-managed KIPRIS client.

    Resolves ``service_key`` from ``KIPO_KIPRIS_API_KEY`` (set by this
    conftest as a placeholder); tests that want to assert specific
    request shapes inject a mock transport via the ``client`` kwarg
    on a freshly-constructed :class:`KiprisClient`.
    """
    service_key = os.environ.get("KIPO_KIPRIS_API_KEY", "test_kipris_servicekey")
    async with KiprisClient(service_key=service_key) as client:
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

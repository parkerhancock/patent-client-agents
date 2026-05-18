"""Tests for the module-level helpers in :mod:`patent_client_agents.inpi_pi.api`.

The helpers are thin convenience wrappers that delegate to
:class:`InpiPiClient`. We verify each helper plumbs its args through
without modification and yields the upstream return value, mocking
the client surface via ``monkeypatch.setattr``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from patent_client_agents.inpi_pi import api as api_mod
from patent_client_agents.inpi_pi.models import InpiDesignRow, InpiTrademarkRow


class _FakeClient:
    """In-memory stand-in for :class:`InpiPiClient` — records args + returns."""

    def __init__(self) -> None:
        self.search_trademarks_calls: list[dict[str, Any]] = []
        self.get_trademark_calls: list[Any] = []
        self.search_designs_calls: list[dict[str, Any]] = []
        self.get_design_calls: list[Any] = []
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> _FakeClient:
        self.entered = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self.exited = True

    async def search_trademarks(
        self,
        query: str | None = None,
        **kwargs: Any,
    ) -> tuple[list[InpiTrademarkRow], int | None]:
        self.search_trademarks_calls.append({"query": query, **kwargs})
        return [InpiTrademarkRow(application_number="A")], 1

    async def get_trademark(self, application_number: str | list[str]) -> list[InpiTrademarkRow]:
        self.get_trademark_calls.append(application_number)
        return [InpiTrademarkRow(application_number="A")]

    async def search_designs(
        self,
        query: str | None = None,
        **kwargs: Any,
    ) -> tuple[list[InpiDesignRow], int | None]:
        self.search_designs_calls.append({"query": query, **kwargs})
        return [InpiDesignRow(application_number="FR1")], 1

    async def get_design(self, application_number: str | list[str]) -> list[InpiDesignRow]:
        self.get_design_calls.append(application_number)
        return [InpiDesignRow(application_number="FR1")]


@pytest.fixture
def fake_client_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[_FakeClient]:
    """Patch ``InpiPiClient`` in ``api`` with a fresh _FakeClient per test."""
    fake = _FakeClient()

    def _factory(*args: Any, **kwargs: Any) -> _FakeClient:
        return fake

    monkeypatch.setattr(api_mod, "InpiPiClient", _factory)
    yield fake


@pytest.mark.asyncio
async def test_search_inpi_trademarks_delegates(
    fake_client_factory: _FakeClient,
) -> None:
    rows, total = await api_mod.search_inpi_trademarks(
        "Apple",
        nice_class=["9"],
        applicant="Acme",
        status="registered",
        date_from="20100101",
        date_to="20201231",
        offset=10,
        limit=50,
    )
    assert total == 1
    assert rows[0].application_number == "A"
    call = fake_client_factory.search_trademarks_calls[0]
    assert call["query"] == "Apple"
    assert call["nice_class"] == ["9"]
    assert call["applicant"] == "Acme"
    assert call["status"] == "registered"
    assert call["date_from"] == "20100101"
    assert call["date_to"] == "20201231"
    assert call["offset"] == 10
    assert call["limit"] == 50
    assert fake_client_factory.entered is True
    assert fake_client_factory.exited is True


@pytest.mark.asyncio
async def test_get_inpi_trademark_delegates(fake_client_factory: _FakeClient) -> None:
    rows = await api_mod.get_inpi_trademark("4216963")
    assert rows[0].application_number == "A"
    assert fake_client_factory.get_trademark_calls == ["4216963"]


@pytest.mark.asyncio
async def test_get_inpi_trademark_list_arg(
    fake_client_factory: _FakeClient,
) -> None:
    await api_mod.get_inpi_trademark(["X", "Y"])
    assert fake_client_factory.get_trademark_calls == [["X", "Y"]]


@pytest.mark.asyncio
async def test_search_inpi_designs_delegates(
    fake_client_factory: _FakeClient,
) -> None:
    rows, total = await api_mod.search_inpi_designs(
        "chair",
        locarno_class=["0601"],
        applicant="Acme",
        offset=5,
        limit=10,
    )
    assert total == 1
    assert rows[0].application_number == "FR1"
    call = fake_client_factory.search_designs_calls[0]
    assert call["query"] == "chair"
    assert call["locarno_class"] == ["0601"]
    assert call["applicant"] == "Acme"
    assert call["offset"] == 5
    assert call["limit"] == 10


@pytest.mark.asyncio
async def test_get_inpi_design_delegates(fake_client_factory: _FakeClient) -> None:
    rows = await api_mod.get_inpi_design("FR20140182")
    assert rows[0].application_number == "FR1"
    assert fake_client_factory.get_design_calls == ["FR20140182"]

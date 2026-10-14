"""Shared fan-out rules for list-accepting get_* tools."""

from __future__ import annotations

import asyncio

import pytest

from mcp_data_core.exceptions import AuthenticationError, NotFoundError, ValidationError
from patent_client_agents.shared.fanout import (
    LIST_CAP,
    FetchedList,
    as_id_list,
    fetch_many,
    fetched_summary,
)


def test_as_id_list_accepts_a_string_or_list_and_strips_blanks() -> None:
    assert as_id_list(" 16123456 ", noun="application number") == ["16123456"]
    assert as_id_list(["a", " ", "b "], noun="id") == ["a", "b"]


@pytest.mark.parametrize("value", [[], [" "], ""])
def test_as_id_list_rejects_empty_input(value: object) -> None:
    with pytest.raises(ValidationError, match="at least one id"):
        as_id_list(value, noun="id")  # type: ignore[arg-type]


def test_as_id_list_rejects_more_than_the_cap() -> None:
    assert len(as_id_list([str(i) for i in range(LIST_CAP)], noun="id")) == LIST_CAP
    with pytest.raises(ValidationError, match=f"limit {LIST_CAP}"):
        as_id_list([str(i) for i in range(LIST_CAP + 1)], noun="id")


async def test_fetch_many_keeps_input_order_and_collects_missing_ids() -> None:
    async def fetch(identifier: str) -> str | None:
        await asyncio.sleep(0.01 * (5 - int(identifier)))  # finish out of order
        if identifier == "2":
            raise NotFoundError("gone", 404, "")
        if identifier == "4":
            return None
        return f"record-{identifier}"

    found, missing = await fetch_many(["1", "2", "3", "4"], fetch, single=False)
    assert found == ["record-1", "record-3"]
    assert missing == ["2", "4"]


async def test_single_input_still_raises_not_found() -> None:
    async def fetch(identifier: str) -> str:
        raise NotFoundError("gone", 404, "")

    with pytest.raises(NotFoundError):
        await fetch_many(["1"], fetch, single=True)


async def test_other_errors_fail_the_whole_call() -> None:
    async def fetch(identifier: str) -> str:
        if identifier == "2":
            raise AuthenticationError("denied", 401, "")
        return identifier

    with pytest.raises(AuthenticationError):
        await fetch_many(["1", "2", "3"], fetch, single=False)


async def test_concurrency_is_bounded() -> None:
    running = peak = 0

    async def fetch(identifier: str) -> str:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return identifier

    await fetch_many([str(i) for i in range(12)], fetch, single=False, concurrency=3)
    assert peak == 3


def test_summary_and_envelope_name_missing_ids() -> None:
    assert fetched_summary(2, 3, "USPTO trademarks", ["97999999"]) == (
        "Fetched 2 of 3 USPTO trademarks. Not found: 97999999."
    )
    assert fetched_summary(3, 3, "USPTO trademarks", []) == "Fetched 3 of 3 USPTO trademarks."
    assert "not_found" in FetchedList[dict].model_json_schema()["properties"]

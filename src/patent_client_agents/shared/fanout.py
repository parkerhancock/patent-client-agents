"""Fetching several records for list-accepting ``get_*`` tools (§5.4).

Rules every list-accepting tool follows:

- A single string is a single fetch. If that record doesn't exist, the
  client's ``NotFoundError`` propagates, as it always has.
- A list returns what was found. IDs that don't exist (``NotFoundError``, or a
  ``None`` from the per-ID fetch) are left out of ``items``, named in the
  summary, and listed in ``FetchedList.not_found``.
- Any other error (auth, rate limit, an upstream failure that outlasted the
  client's retries) fails the whole call; it usually affects every ID alike.
- At most ``LIST_CAP`` IDs per call, checked before any request is made.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Generic, TypeVar

from pydantic import Field

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import NotFoundError, ValidationError

T = TypeVar("T")

LIST_CAP = 50
DEFAULT_CONCURRENCY = 5


class FetchedList(ListEnvelope[T], Generic[T]):
    """A ``ListEnvelope`` that also names the requested IDs that weren't found."""

    not_found: list[str] = Field(
        default_factory=list,
        description="Requested identifiers that the source has no record for.",
    )


def as_id_list(value: str | Sequence[str], *, noun: str, cap: int = LIST_CAP) -> list[str]:
    """Normalize a ``str | list[str]`` identifier argument.

    Strips whitespace, drops blanks, and rejects an empty list or one longer
    than ``cap`` before any request is made.
    """
    raw = [value] if isinstance(value, str) else list(value)
    ids = [item.strip() for item in raw if item and item.strip()]
    if not ids:
        raise ValidationError(f"Provide at least one {noun}.")
    if len(ids) > cap:
        raise ValidationError(
            f"Too many {noun}s: {len(ids)} (limit {cap} per call). "
            f"Split the list into batches of {cap} or fewer."
        )
    return ids


async def fetch_many(
    ids: Sequence[str],
    fetch_one: Callable[[str], Awaitable[T | None]],
    *,
    single: bool,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> tuple[list[T], list[str]]:
    """Fetch each ID with bounded concurrency, in input order.

    Returns ``(found, not_found)``. ``single`` is True when the caller passed a
    plain string; then a ``NotFoundError`` propagates instead of being collected.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def run(identifier: str) -> T | None:
        async with semaphore:
            try:
                return await fetch_one(identifier)
            except NotFoundError:
                if single:
                    raise
                return None

    results = await asyncio.gather(*(run(identifier) for identifier in ids))
    found = [result for result in results if result is not None]
    not_found = [
        identifier for identifier, result in zip(ids, results, strict=True) if result is None
    ]
    return found, not_found


def fetched_summary(found: int, requested: int, noun_plural: str, not_found: Sequence[str]) -> str:
    """``"Fetched 2 of 3 USPTO trademarks. Not found: 97999999."``"""
    summary = f"Fetched {found} of {requested} {noun_plural}."
    if not_found:
        summary += f" Not found: {', '.join(not_found)}."
    return summary

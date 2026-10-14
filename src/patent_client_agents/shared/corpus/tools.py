"""Shared bodies for the MCP search/get tools over bundled SQLite/FTS5 corpora.

Every ``mcp_local`` substantive-law module (MPEP, TMEP, EPC, the EPO
guidelines, statutes corpora, ...) exposes a ``search_*`` tool and a
list-accepting ``get_*`` tool with the same shape (CONNECTOR_STANDARDS.md
§5.5, §5.9). These helpers hold that shape; each tool module keeps its
signature, docstring, lean projection, single-record summary and source URLs.

Two rules the helpers enforce:

- Corpus status is read once per request. The same ``CorpusStatus`` feeds the
  summary text and the provenance ``corpus_*`` fields.
- The client class and status function are arguments, read by the tool body
  at call time. Tests patch them by tool-module attribute
  (``patch("...mcp.tools.ilpo.IlpoStatutesClient")``), so nothing here binds
  a connector at import.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from mcp_data_core.envelope import ListEnvelope, Provenance
from patent_client_agents.shared.envelope import dump
from patent_client_agents.shared.fanout import FetchedList, fetch_many, fetched_summary
from patent_client_agents.shared.provenance import provenance_for

StatusFn = Callable[[], Mapping[str, Any]]
"""A connector's ``get_corpus_status`` (returns ``corpus_version`` / ``corpus_synced_at``)."""


def truncate(text: str, limit: int) -> str:
    """Cap a string at ``limit`` chars, appending an ellipsis on overflow."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def corpus_provenance(
    status: Mapping[str, Any], *, source_url: str, source_name: str
) -> Provenance:
    """Provenance stamped with the corpus freshness fields from ``status`` (§4)."""
    return provenance_for(
        source_url=source_url,
        source_name=source_name,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def hits_summary(head: str, count: int, more_available: bool, tail: str = "") -> str:
    """``"{head}: 3 hits{tail} (more available)."`` — the search-tool summary line."""
    summary = f"{head}: {count} hit{'s' if count != 1 else ''}{tail}"
    return summary + (" (more available)." if more_available else ".")


async def corpus_search(
    client_cls: Callable[[], Any],
    search: Callable[[Any], Awaitable[Any]],
    *,
    corpus_status: StatusFn,
    project: Callable[[dict], dict] | None,
    summary: Callable[[Any, list[dict], str], str],
    source_url: str,
    source_name: str,
) -> ListEnvelope[dict]:
    """Run ``search(client)`` and wrap the response's ``hits`` in a ``ListEnvelope``.

    ``project`` is the lean projection (§5.5) applied to each dumped hit;
    ``None`` returns the hits as dumped (``full=True``). ``summary`` receives
    ``(response, items, corpus_version)``.
    """
    async with client_cls() as client:
        response = await search(client)

    hits = [dump(hit) for hit in response.hits]
    items = hits if project is None else [project(hit) for hit in hits]

    status = corpus_status()
    return ListEnvelope[dict](
        summary=summary(response, items, status["corpus_version"]),
        items=items,
        more_available=response.has_more,
        next_cursor=None,
        provenance=corpus_provenance(status, source_url=source_url, source_name=source_name),
    )


async def corpus_get(
    client_cls: Callable[[], Any],
    refs: Sequence[str],
    fetch_one: Callable[[Any, str], Awaitable[dict | None]],
    *,
    single: bool,
    corpus_status: StatusFn,
    summarize_one: Callable[[dict, str], str],
    missing: Callable[[str], str] | None,
    noun_plural: str | Callable[[str], str],
    source_url: str | Callable[[list[dict], str], str],
    source_name: str,
) -> FetchedList[dict]:
    """Fetch each ref with ``fetch_one(client, ref)`` and wrap them in a ``FetchedList``.

    Fan-out, ordering and not-found handling are ``shared.fanout.fetch_many``
    (§5.4). The summary is ``summarize_one(record, corpus_version)`` when one
    ref was requested and found; ``missing(ref)`` when one ref was requested
    and not found (``None`` falls through to the multi-ref form); otherwise
    ``fetched_summary``. ``noun_plural`` and ``source_url`` may depend on the
    corpus version (and ``source_url`` on the fetched items).
    """
    async with client_cls() as client:

        async def _fetch(ref: str) -> dict | None:
            return await fetch_one(client, ref)

        items, not_found = await fetch_many(refs, _fetch, single=single)

    status = corpus_status()
    version = status["corpus_version"]
    if len(refs) == 1 and items:
        summary = summarize_one(items[0], version)
    elif len(refs) == 1 and missing is not None:
        summary = missing(refs[0])
    else:
        noun = noun_plural if isinstance(noun_plural, str) else noun_plural(version)
        summary = fetched_summary(len(items), len(refs), noun, not_found)

    url = source_url if isinstance(source_url, str) else source_url(items, version)
    return FetchedList[dict](
        summary=summary,
        items=items,
        not_found=not_found,
        provenance=corpus_provenance(status, source_url=url, source_name=source_name),
    )


__all__ = [
    "StatusFn",
    "corpus_get",
    "corpus_provenance",
    "corpus_search",
    "hits_summary",
    "truncate",
]

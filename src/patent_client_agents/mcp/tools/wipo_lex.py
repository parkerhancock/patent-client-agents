"""WIPO Lex MCP tools.

Public-no-auth surface — these tools always register (no env gate).
Covers the **legislation** collection only; treaties and judgments
share the WIPO Lex URL shape and can be added as parallel tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_proxy``, ``update_strategy=live_proxy`` (per
``coverage/sources.yaml``). Live-proxy substantive-law connectors carry
the standard provenance fields only — ``corpus_synced_at`` /
``corpus_version`` are reserved for ``mcp_local`` corpora.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.wipo_lex import (
    SubjectMatter,
    TypeOfText,
    WipoLexClient,
)

wipo_lex_mcp = FastMCP("WIPO Lex")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). WIPO Lex is
# substantive law served by live proxy (§4 / coverage/sources.yaml),
# so provenance carries the standard fields only — no corpus_synced_at.
# ──────────────────────────────────────────────────────────────────────

_WIPO_LEX_BASE = "https://www.wipo.int"
_WIPO_LEX_NAME = "WIPO Lex"

_WIPO_LEX_FANOUT_CONCURRENCY = 5


def _wipo_lex_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}``."""
    return make_provenance(
        source_url=f"{_WIPO_LEX_BASE}{path}",
        source_name=_WIPO_LEX_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict (or pass through dicts).

    Every caller passes a Pydantic model from the upstream client; the
    fallback exists to be defensive if a dict slips through. Typed as
    ``dict[str, Any]`` so call sites can use ``.get(...)`` without
    per-call narrowing.
    """
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump())  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a WIPO Lex search hit (§5.5).

    The upstream ``LegislationSearchHit`` carries only id, title, and
    canonical URL; the lean view normalizes the keys an agent reads.
    Use ``get_wipo_lex_legislation`` to pull the per-record jurisdiction,
    summary line, and attachments.
    """
    return {
        "legislation_id": hit.get("legislation_id"),
        "title": hit.get("title"),
        "url": hit.get("url"),
    }


def _summarize_detail(detail: dict) -> str:
    """One-line Markdown summary of a single legislation detail record."""
    leg_id = detail.get("legislation_id") or "(no id)"
    title = detail.get("title") or "(no title)"
    jurisdiction = detail.get("jurisdiction")
    files = detail.get("files") or []
    head = f"**WIPO Lex {leg_id}** — {title}"
    parts: list[str] = []
    if jurisdiction:
        parts.append(f"Jurisdiction: {jurisdiction}")
    parts.append(f"{len(files)} attachment(s)")
    return f"{head}\n{'. '.join(parts)}."


@wipo_lex_mcp.tool(annotations=READ_ONLY)
async def search_wipo_lex_legislation(
    country_codes: Annotated[
        list[str] | None,
        "ISO 3166-1 alpha-2 country codes or regional org codes. Examples: ['CA', 'US'], ['EU'].",
    ] = None,
    subject_matter: Annotated[
        list[int] | None,
        "SubjectMatter codes: 1=Patents, 2=Utility Models, 3=Designs, "
        "4=Trademarks, 5=GIs, 9=Trade Secrets, 10=PVP, 11=Copyright, "
        "12=Enforcement.",
    ] = None,
    type_of_text: Annotated[
        list[int] | None,
        "TypeOfText codes: 205=Main IP Laws, 207=Implementing Rules, "
        "210=IP-related Laws, 213=Framework Laws, 214=Other, "
        "215=National IP Strategy.",
    ] = None,
    keywords: Annotated[str | None, "Free-text search over title + notes."] = None,
    start_date: Annotated[str | None, "Lower bound (ISO YYYY-MM-DD)."] = None,
    end_date: Annotated[str | None, "Upper bound (ISO YYYY-MM-DD)."] = None,
    include_historical: Annotated[bool, "Include superseded texts."] = False,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: "
        "legislation_id, title, url. When True, returns the upstream "
        "row shape unchanged.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search WIPO Lex (global IP legislation database) for statutes across ~200 jurisdictions.

    Filters AND together. Returns a lean stub per hit by default
    (``legislation_id``, ``title``, ``url``); pass ``full=True`` for the
    upstream row shape. Use ``get_wipo_lex_legislation`` with a hit's
    ``legislation_id`` to pull the jurisdiction, summary line, and
    downloadable PDF/DOC attachments.

    Examples:
      * Canadian patent law: country_codes=["CA"], subject_matter=[1]
      * Trade secrets statutes globally: subject_matter=[9]
      * UK IP enforcement: country_codes=["GB"], subject_matter=[12]

    Related tools: get_wipo_lex_legislation.
    """
    # Validate input codes via the IntEnum constructor (raises on bad code),
    # then cast back to list[int] for the client signature — IntEnum subclass
    # is structurally compatible but ty treats list types invariantly.
    subject_enums = (
        cast("list[int]", [SubjectMatter(c) for c in subject_matter]) if subject_matter else None
    )
    type_enums = cast("list[int]", [TypeOfText(c) for c in type_of_text]) if type_of_text else None

    async with WipoLexClient() as client:
        response = await client.search_legislation(
            country_codes=country_codes,
            subject_matter=subject_enums,
            type_of_text=type_enums,
            keywords=keywords,
            start_date=start_date,
            end_date=end_date,
            include_historical=include_historical,
        )

    dumped = _dump(response)
    hits = list(dumped.get("hits") or [])
    items = hits if full else [_stub_hit(h) for h in hits]

    query_bits: list[str] = []
    if keywords:
        query_bits.append(f"`{keywords}`")
    if country_codes:
        query_bits.append("countries=" + ",".join(country_codes))
    if subject_matter:
        query_bits.append("subjects=" + ",".join(str(c) for c in subject_matter))
    query_label = " ".join(query_bits) or "(all filters)"

    return ListEnvelope[dict](
        summary=f"WIPO Lex legislation — {query_label}: {len(items)} hits.",
        items=items,
        provenance=_wipo_lex_provenance("/wipolex/en/legislation/results"),
    )


@wipo_lex_mcp.tool(annotations=READ_ONLY)
async def get_wipo_lex_legislation(
    legislation_id: Annotated[
        str | list[str],
        "WIPO Lex internal ID, or a list of IDs for portfolio workflows. "
        "Examples: '23293' (Canadian Patent Act), ['23293', '23437'].",
    ],
) -> ListEnvelope[dict]:
    """Get one or more WIPO Lex (global IP legislation database) entries by ID.

    Returns title, jurisdiction, summary line (year, assent date, type,
    subjects), canonical URL, and the list of downloadable PDF/DOC
    attachments per entry. Accepts either a single ID or a list (§5.4);
    the response is always a ListEnvelope so the shape is stable.
    Bounded concurrent fan-out internally; order matches the input.

    Related tools: search_wipo_lex_legislation.
    """
    ids = [legislation_id] if isinstance(legislation_id, str) else list(legislation_id)
    if not ids:
        raise ValidationError("get_wipo_lex_legislation requires at least one legislation_id")

    semaphore = asyncio.Semaphore(_WIPO_LEX_FANOUT_CONCURRENCY)

    async def _fetch_one(client: WipoLexClient, lid: str) -> dict:
        async with semaphore:
            return _dump(await client.get_legislation(lid))  # type: ignore[return-value]

    async with WipoLexClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, lid) for lid in ids])

    if len(results) == 1:
        summary = _summarize_detail(results[0])
        path = f"/wipolex/en/legislation/details/{ids[0]}"
    else:
        summary = f"Fetched {len(results)} WIPO Lex legislation entries: " + ", ".join(ids)
        path = "/wipolex/en/legislation/details"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_wipo_lex_provenance(path),
    )


__all__ = ["wipo_lex_mcp"]

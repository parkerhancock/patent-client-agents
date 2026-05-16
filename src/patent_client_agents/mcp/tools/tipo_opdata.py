"""TIPO Taiwan OpenData — MCP tools.

Read-only access to the Taiwan Intellectual Property Office (TIPO /
MOEA) OpenData REST API at
``https://cloud.tipo.gov.tw/S220/opdataapi/api/``. Env-gated: tools
register only when ``TIPO_API_KEY`` is set (the ``tk`` UUID token
issued by TIPO upon request).

Coverage is biblio-only — no claims, abstracts, or figures on the
patent endpoints; TM image URLs are returned as URLs only (no
rendering). Cross-references to upstream substitutes are limited
because Taiwan is not an INPADOC contributor (no EPO bulk feed) and
is not a WIPO member (no WIPO Lex / Global Brand DB record). See
spec §3 for the full tool table.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.conditional import conditional_tool
from patent_client_agents.tipo_opdata import TipoClient

tipo_opdata_mcp = FastMCP("TIPO Taiwan — OpenData")

_TIPO_REQUIRED_ENV: list[str] = ["TIPO_API_KEY"]

# ──────────────────────────────────────────────────────────────────────
# Provenance & attribution helpers (CONNECTOR_STANDARDS.md §3, §5.9).
# Every envelope advertises the canonical attribution string per
# Taiwan OGDL v1.0 (spec §3).
# ──────────────────────────────────────────────────────────────────────

_TIPO_BASE = "https://cloud.tipo.gov.tw/S220/opdataapi/api"
_TIPO_NAME = "Intellectual Property Office, Ministry of Economic Affairs, Taiwan (TIPO/MOEA)"
_TIPO_ATTRIBUTION = (
    "Source: Intellectual Property Office, Ministry of Economic Affairs, Taiwan (TIPO/MOEA). "
    "Licence: Taiwan Open Government Data License v1.0."
)
_TIPO_FANOUT_CONCURRENCY = 5
_TIPO_DEFAULT_TOP = 100


def _tipo_provenance(path: str) -> Any:
    """Build a Provenance pointing at a TIPO OpenData endpoint.

    Provenance model fields are fixed (no ``attribution`` slot in v1);
    the canonical OGDL v1.0 attribution string is exposed via
    :data:`_TIPO_ATTRIBUTION` for callers (and the usage resource) so
    agents can surface it verbatim per spec §3.
    """
    return make_provenance(
        source_url=f"{_TIPO_BASE}{path}",
        source_name=_TIPO_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict via ``model_dump(by_alias=True)``."""
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump(by_alias=True))  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


# ──────────────────────────────────────────────────────────────────────
# Lean projection (§5.5). Drops ``xml-detail-url`` (FTPS pointer, not
# actionable per spec §6) and any null-Latin name fields. ``full=True``
# returns the full upstream-aliased dict including the dropped keys.
# ──────────────────────────────────────────────────────────────────────

_LEAN_DROP_KEYS = {"xml-detail-url"}
_LEAN_NULLISH_LATIN_KEYS = {
    "applicant-name-e",
    "applicant-addr-e",
    "applicant-name-j",
    "applicant-addr-j",
    "inventor-name-e",
    "inventor-name-j",
    "agent-name-e",
    "tmark-draft-e",
    "tmark-draft-j",
}


def _lean(row: dict[str, Any]) -> dict[str, Any]:
    """Apply lean projection rules to a TIPO row dict.

    Drops the FTPS-pointer key and any null-Latin/Japanese name
    fields. Operates recursively on nested dicts/lists so applicant
    sub-rows are pruned too.
    """
    out: dict[str, Any] = {}
    for key, value in row.items():
        if key in _LEAN_DROP_KEYS:
            continue
        if key in _LEAN_NULLISH_LATIN_KEYS and not value:
            continue
        if isinstance(value, dict):
            out[key] = _lean(value)
        elif isinstance(value, list):
            out[key] = [_lean(v) if isinstance(v, dict) else v for v in value]
        else:
            out[key] = value
    return out


def _project(rows: list[Any], *, full: bool) -> list[dict[str, Any]]:
    """Serialize + (optionally) lean a list of row models."""
    dumped = [_dump(r) for r in rows]
    if full:
        return dumped
    return [_lean(r) for r in dumped]


def _coerce_list(value: str | list[str], *, tool: str) -> list[str]:
    """Normalize a ``str | list[str]`` input to a non-empty list."""
    items = [value] if isinstance(value, str) else list(value)
    items = [s.strip() for s in items if isinstance(s, str) and s.strip()]
    if not items:
        raise ValidationError(f"{tool} requires at least one application number")
    return items


# ──────────────────────────────────────────────────────────────────────
# search_tipo_patents
# ──────────────────────────────────────────────────────────────────────


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_tipo_patents(
    q: Annotated[
        str | None,
        "Free-text query — matches applicant, title, and applicant address "
        "in the upstream filter. Example: 'TSMC'.",
    ] = None,
    applclass: Annotated[
        int | None,
        "Application class discriminator: 1 = invention patent, 2 = utility "
        "model, 3 = design. Omit to span all three.",
    ] = None,
    appl_date_from: Annotated[
        str | None,
        "Earliest application date (YYYY/MM/DD, Gregorian).",
    ] = None,
    appl_date_to: Annotated[
        str | None,
        "Latest application date (YYYY/MM/DD, Gregorian).",
    ] = None,
    applicant: Annotated[
        str | None,
        "Applicant name filter (Chinese or Latin).",
    ] = None,
    top: Annotated[int, "Page size (capped at 6000)."] = _TIPO_DEFAULT_TOP,
    skip: Annotated[int, "Offset into the result set."] = 0,
    full: Annotated[
        bool,
        "When False (default), drops xml-detail-url and null Latin/Japanese "
        "name fields per §5.5. When True, returns upstream-shaped rows.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search Taiwan patents / utility models / designs at TIPO.

    Wraps ``/PatentAppl`` — biblio-only (no claims, abstracts, or
    figures available via the API). Use ``applclass`` to scope to
    inventions (1), utility models (2), or designs (3).

    Related tools: ``get_tipo_patent`` for one application at a time;
    ``search_epo_patents`` does NOT cover TW (Taiwan is not an INPADOC
    contributor) — TIPO is the only upstream substitute.
    """
    async with TipoClient() as client:
        rows = await client.search_patent_appl(
            q=q,
            applclass=applclass,
            appl_date_from=appl_date_from,
            appl_date_to=appl_date_to,
            applicant=applicant,
            top=top,
            skip=skip,
        )
    items = _project(rows, full=full)
    summary = f"TIPO patents — {len(items)} hits"
    if q:
        summary += f" for `{q}`"
    if applclass:
        label = {1: "invention", 2: "utility model", 3: "design"}.get(
            int(applclass), str(applclass)
        )
        summary += f" ({label})"
    return ListEnvelope[dict](
        summary=f"{summary}.",
        items=items,
        more_available=len(items) == min(int(top), 6000),
        next_cursor=None,
        provenance=_tipo_provenance("/PatentAppl"),
    )


# ──────────────────────────────────────────────────────────────────────
# Generic fetch-by-appl-no helper builder
# ──────────────────────────────────────────────────────────────────────


async def _fetch_by_appl_no(
    *,
    method_name: str,
    appl_no: str | list[str],
    full: bool,
    endpoint: str,
    label: str,
    tool: str,
) -> ListEnvelope[dict]:
    """Run a TipoClient fetch method across one or more appl-no values.

    Bounded concurrency per ``_TIPO_FANOUT_CONCURRENCY``. Order in the
    response items list matches input order for list inputs.
    """
    numbers = _coerce_list(appl_no, tool=tool)
    semaphore = asyncio.Semaphore(_TIPO_FANOUT_CONCURRENCY)

    async def _fetch_one(client: TipoClient, num: str) -> list[Any]:
        async with semaphore:
            method = getattr(client, method_name)
            return await method(appl_no=num)

    async with TipoClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    rows: list[Any] = [r for batch in results for r in batch]
    items = _project(rows, full=full)
    summary = (
        f"TIPO {label} — {len(items)} rows for "
        f"{len(numbers)} application{'s' if len(numbers) != 1 else ''}: "
        f"{', '.join(numbers[:5])}{' …' if len(numbers) > 5 else ''}."
    )
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_tipo_provenance(endpoint),
    )


# ──────────────────────────────────────────────────────────────────────
# Patent fetch tools
# ──────────────────────────────────────────────────────────────────────


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_patent(
    appl_no: Annotated[
        str | list[str],
        "TW patent / UM / design application number, or a list for "
        "portfolio fan-outs. Each list element is fetched concurrently.",
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch one or more Taiwan patent application biblio records.

    Wraps ``/PatentAppl?appl-no=...``. Returns the application-side
    bibliographic record (filing no, filing date, IPC + Locarno
    classifications). For grant status, use
    ``get_tipo_patent_rights``.

    Related tools: ``search_tipo_patents``; no upstream substitute
    available (Taiwan is not in INPADOC, so ``get_epo_biblio`` does
    not cover TW).
    """
    return await _fetch_by_appl_no(
        method_name="search_patent_appl",
        appl_no=appl_no,
        full=full,
        endpoint="/PatentAppl",
        label="patent applications",
        tool="get_tipo_patent",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_patent_publication(
    appl_no: Annotated[
        str | list[str],
        "TW patent / UM / design application number, or a list.",
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan patent publication records (KOKAI + KOKOKU).

    Wraps ``/PatentPub``. Carries the publication reference, the
    application reference, title, parties, and IPC classifications.

    Related tools: ``get_tipo_patent`` for the application-side
    record; no upstream substitute (TW not in INPADOC).
    """
    return await _fetch_by_appl_no(
        method_name="get_patent_pub",
        appl_no=appl_no,
        full=full,
        endpoint="/PatentPub",
        label="patent publications",
        tool="get_tipo_patent_publication",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_patent_rights(
    appl_no: Annotated[
        str | list[str],
        "TW patent / UM / design application number, or a list.",
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan patent grant + status records (with ``twins-flag``).

    Wraps ``/PatentRights``. Carries the grant status, registration
    info, and the TW-specific ``twins-flag`` on ``application-
    reference`` flagging Article 32 dual-track invention / UM pairs.

    Related tools: ``get_tipo_patent_twins`` for the explicit pair
    list; ``get_tipo_patent_annuity`` for maintenance status.
    """
    return await _fetch_by_appl_no(
        method_name="get_patent_rights",
        appl_no=appl_no,
        full=full,
        endpoint="/PatentRights",
        label="patent rights",
        tool="get_tipo_patent_rights",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_patent_priority(
    appl_no: Annotated[
        str | list[str],
        "TW patent / UM / design application number, or a list.",
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan Paris priority claim records for a patent.

    Wraps ``/PatentPriority``. One row per application; the
    ``prioritys`` list carries each claimed priority.

    Related tools: ``get_tipo_patent`` (application biblio includes
    no priority); no upstream substitute (TW not in INPADOC).
    """
    return await _fetch_by_appl_no(
        method_name="get_patent_priority",
        appl_no=appl_no,
        full=full,
        endpoint="/PatentPriority",
        label="patent priority",
        tool="get_tipo_patent_priority",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_patent_annuity(
    appl_no: Annotated[
        str | list[str],
        "TW patent / UM / design application number, or a list.",
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan annuity payment schedule for a patent.

    Wraps ``/PatentAnnuity``. Carries paid-through dates and per-year
    charges — useful for "still in force" / lapse-risk screening.

    Related tools: ``get_tipo_patent_rights`` for grant status; no
    upstream substitute.
    """
    return await _fetch_by_appl_no(
        method_name="get_patent_annuity",
        appl_no=appl_no,
        full=full,
        endpoint="/PatentAnnuity",
        label="patent annuity",
        tool="get_tipo_patent_annuity",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_patent_twins(
    appl_no: Annotated[
        str | list[str],
        "TW patent application number, or a list.",
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan Article 32 invention / UM "twin" pair records.

    Wraps ``/PatentTwins``. TW Patent Act Article 32 permits dual
    invention + utility-model filings on the same disclosure;
    inventors must elect one within the granting decision window.
    This endpoint surfaces the twin pairs.

    Related tools: ``get_tipo_patent_rights`` (the ``twins-flag``
    field on ``application-reference``); no upstream substitute (this
    is a TW-specific dual-track regime).
    """
    return await _fetch_by_appl_no(
        method_name="get_patent_twins",
        appl_no=appl_no,
        full=full,
        endpoint="/PatentTwins",
        label="patent twins",
        tool="get_tipo_patent_twins",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_patent_events(
    appl_no: Annotated[
        str | list[str],
        "TW patent / UM / design application number, or a list.",
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan patent post-filing events (alterations, changes, divides).

    Combined surface per spec §3, §5.6: merges
    ``/PatentAlteration`` (applicant / inventor / agent edits),
    ``/PatentChange`` (appl-no / appl-class structural changes), and
    ``/PatentDivide`` (divisional links) into one envelope. Each
    item carries an ``event_type`` discriminator
    (``"alteration"``, ``"change"``, ``"divide"``).

    Related tools: ``get_tipo_patent`` (application biblio);
    ``get_tipo_patent_rights`` (grant status); no upstream substitute.
    """
    numbers = _coerce_list(appl_no, tool="get_tipo_patent_events")
    semaphore = asyncio.Semaphore(_TIPO_FANOUT_CONCURRENCY)

    async def _fetch_one_kind(
        client: TipoClient, method_name: str, num: str
    ) -> list[Any]:
        async with semaphore:
            method = getattr(client, method_name)
            return await method(appl_no=num)

    async with TipoClient() as client:
        coroutines = []
        for num in numbers:
            coroutines.extend(
                [
                    _fetch_one_kind(client, "get_patent_alteration", num),
                    _fetch_one_kind(client, "get_patent_change", num),
                    _fetch_one_kind(client, "get_patent_divide", num),
                ]
            )
        results = await asyncio.gather(*coroutines)

    # Triplets of (alteration, change, divide) per appl_no, in order.
    items: list[dict[str, Any]] = []
    for idx, num in enumerate(numbers):
        alt_rows, chg_rows, div_rows = results[idx * 3 : idx * 3 + 3]
        for tag, batch in (
            ("alteration", alt_rows),
            ("change", chg_rows),
            ("divide", div_rows),
        ):
            for row in batch:
                dumped = _dump(row)
                projected = dumped if full else _lean(dumped)
                projected = {"event_type": tag, "appl_no": num, **projected}
                items.append(projected)

    summary = (
        f"TIPO patent events — {len(items)} events across "
        f"{len(numbers)} application{'s' if len(numbers) != 1 else ''}: "
        f"{', '.join(numbers[:5])}{' …' if len(numbers) > 5 else ''}."
    )
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_tipo_provenance("/PatentAlteration+Change+Divide"),
    )


# ──────────────────────────────────────────────────────────────────────
# search_tipo_trademarks
# ──────────────────────────────────────────────────────────────────────


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_tipo_trademarks(
    q: Annotated[
        str | None,
        "Free-text query — matches mark text, applicant, and description.",
    ] = None,
    tmark_class: Annotated[
        int | str | None,
        "Nice classification class (1-45).",
    ] = None,
    appl_date_from: Annotated[
        str | None, "Earliest application date (YYYY/MM/DD)."
    ] = None,
    appl_date_to: Annotated[
        str | None, "Latest application date (YYYY/MM/DD)."
    ] = None,
    applicant: Annotated[
        str | None, "Applicant name filter (Chinese or Latin)."
    ] = None,
    top: Annotated[int, "Page size (capped at 6000)."] = _TIPO_DEFAULT_TOP,
    skip: Annotated[int, "Offset into the result set."] = 0,
    full: Annotated[
        bool, "Lean (default) vs upstream-shaped rows per §5.5."
    ] = False,
) -> ListEnvelope[dict]:
    """Search Taiwan trademarks at TIPO.

    Wraps ``/TmarkAppl``. Returns biblio + Nice class + image URLs.
    Note: Taiwan is not a WIPO member, so no WIPO Global Brand DB
    equivalent — TIPO is the only upstream substitute.
    """
    async with TipoClient() as client:
        rows = await client.search_tmark_appl(
            q=q,
            tmark_class=tmark_class,
            appl_date_from=appl_date_from,
            appl_date_to=appl_date_to,
            applicant=applicant,
            top=top,
            skip=skip,
        )
    items = _project(rows, full=full)
    summary = f"TIPO trademarks — {len(items)} hits"
    if q:
        summary += f" for `{q}`"
    if tmark_class:
        summary += f" (class {tmark_class})"
    return ListEnvelope[dict](
        summary=f"{summary}.",
        items=items,
        more_available=len(items) == min(int(top), 6000),
        next_cursor=None,
        provenance=_tipo_provenance("/TmarkAppl"),
    )


# ──────────────────────────────────────────────────────────────────────
# Trademark fetch tools
# ──────────────────────────────────────────────────────────────────────


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_trademark(
    appl_no: Annotated[
        str | list[str], "TW trademark application number, or a list."
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch one or more Taiwan trademark application records.

    Wraps ``/TmarkAppl?appl-no=...``. Returns biblio + Nice class +
    image URLs.

    Related tools: ``search_tipo_trademarks``;
    ``get_tipo_trademark_rights`` for registration status.
    """
    return await _fetch_by_appl_no(
        method_name="search_tmark_appl",
        appl_no=appl_no,
        full=full,
        endpoint="/TmarkAppl",
        label="trademark applications",
        tool="get_tipo_trademark",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_trademark_rights(
    appl_no: Annotated[
        str | list[str], "TW trademark application number, or a list."
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan trademark registration + status records.

    Wraps ``/TmarkRights``. Carries the full status grid
    (opposition, exam, nullity, transfer, extended ...) plus the
    registration number + dates.

    Related tools: ``get_tipo_trademark`` for the application-side
    record; ``get_tipo_trademark_events`` for post-filing edits.
    """
    return await _fetch_by_appl_no(
        method_name="get_tmark_rights",
        appl_no=appl_no,
        full=full,
        endpoint="/TmarkRights",
        label="trademark rights",
        tool="get_tipo_trademark_rights",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_trademark_priority(
    appl_no: Annotated[
        str | list[str], "TW trademark application number, or a list."
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan trademark Paris priority claim records.

    Wraps ``/TmarkPriority``.

    Related tools: ``get_tipo_trademark``; ``get_tipo_trademark_rights``.
    """
    return await _fetch_by_appl_no(
        method_name="get_tmark_priority",
        appl_no=appl_no,
        full=full,
        endpoint="/TmarkPriority",
        label="trademark priority",
        tool="get_tipo_trademark_priority",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_trademark_image_urls(
    appl_no: Annotated[
        str | list[str], "TW trademark application number, or a list."
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan trademark image URLs.

    Wraps ``/TmarkPics``. Returns image URLs only — Pillow rendering
    is out of scope for v1. Sound marks include an audio filename
    among the URL list.

    Related tools: ``get_tipo_trademark`` (the ``tmark-image-url``
    array is also present on the application record).
    """
    return await _fetch_by_appl_no(
        method_name="get_tmark_pics",
        appl_no=appl_no,
        full=full,
        endpoint="/TmarkPics",
        label="trademark images",
        tool="get_tipo_trademark_image_urls",
    )


@conditional_tool(tipo_opdata_mcp, requires_env=_TIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_tipo_trademark_events(
    appl_no: Annotated[
        str | list[str], "TW trademark application number, or a list."
    ],
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Fetch Taiwan trademark post-filing events (changes, divisions).

    Combined surface per spec §3, §5.6: merges ``/TmarkChange``
    (transfer / name-change events) and ``/TmarkDivide`` (TM
    application divisions) into one envelope. Each item carries an
    ``event_type`` discriminator (``"change"`` or ``"divide"``).

    Related tools: ``get_tipo_trademark_rights`` for current status.
    """
    numbers = _coerce_list(appl_no, tool="get_tipo_trademark_events")
    semaphore = asyncio.Semaphore(_TIPO_FANOUT_CONCURRENCY)

    async def _fetch_one_kind(
        client: TipoClient, method_name: str, num: str
    ) -> list[Any]:
        async with semaphore:
            method = getattr(client, method_name)
            return await method(appl_no=num)

    async with TipoClient() as client:
        coroutines = []
        for num in numbers:
            coroutines.extend(
                [
                    _fetch_one_kind(client, "get_tmark_change", num),
                    _fetch_one_kind(client, "get_tmark_divide", num),
                ]
            )
        results = await asyncio.gather(*coroutines)

    items: list[dict[str, Any]] = []
    for idx, num in enumerate(numbers):
        chg_rows, div_rows = results[idx * 2 : idx * 2 + 2]
        for tag, batch in (("change", chg_rows), ("divide", div_rows)):
            for row in batch:
                dumped = _dump(row)
                projected = dumped if full else _lean(dumped)
                projected = {"event_type": tag, "appl_no": num, **projected}
                items.append(projected)

    summary = (
        f"TIPO trademark events — {len(items)} events across "
        f"{len(numbers)} application{'s' if len(numbers) != 1 else ''}: "
        f"{', '.join(numbers[:5])}{' …' if len(numbers) > 5 else ''}."
    )
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_tipo_provenance("/TmarkChange+Divide"),
    )


__all__ = ["tipo_opdata_mcp"]

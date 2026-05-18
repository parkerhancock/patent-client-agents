"""INPI France MCP tools — Trademark + Design (no patents).

Read-only access to French national trademarks (WIPO ST.66 v1.0) and
designs (WIPO ST.86 v1.0) via ``api-gateway.inpi.fr``. Env-gated: tools
register only when both ``INPI_USERNAME`` and ``INPI_PASSWORD`` are
set (BYOK posture — production deployers must register their own
personal ``data.inpi.fr`` account).

Patents — deliberately absent
-----------------------------
**No patent tools are exposed by this module.** For FR patent coverage,
use ``patent_client_agents.epo_ops`` (country code ``FR``); INPADOC
covers EP-routed FR designations and FR national-route filings with
adequate fidelity. Per ``CONNECTOR_STANDARDS.md`` §6 "single source of
truth", we do not duplicate the same bibliographic dataset across
connectors.

Provenance: every envelope carries an ``attribution`` line —
``"Source: Institut National de la Propriété Industrielle (INPI).
Réutilisation des données INPI — licence INPI."`` Stored in the
:class:`Provenance.source_name` slot since the envelope has no
dedicated attribution field; ``coverage/sources.yaml`` carries the
``licence_url`` per §3 standards.
"""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.conditional import conditional_tool
from patent_client_agents.inpi_pi import InpiPiClient
from patent_client_agents.inpi_pi.models import InpiDesignRow, InpiTrademarkRow

inpi_pi_mcp = FastMCP("INPI-PI")

_INPI_REQUIRED_ENV: list[str] = ["INPI_USERNAME", "INPI_PASSWORD"]

# Provenance is built per-call to capture the canonical upstream URL.
# ``Provenance`` has no ``attribution`` field, so we fold the INPI legal
# attribution into ``source_name`` per the chunk-3 fallback used by
# TIPO / KIPO. ``coverage/sources.yaml`` carries the formal
# ``licence_url`` per CONNECTOR_STANDARDS §3.
_INPI_ATTRIBUTION = (
    "Institut National de la Propriété Industrielle (INPI) — "
    "Réutilisation des données INPI — licence INPI."
)
_INPI_BASE = "https://api-gateway.inpi.fr"


def _inpi_provenance(path: str) -> Any:
    """Build a Provenance pointing at the canonical INPI gateway path."""
    return make_provenance(
        source_url=f"{_INPI_BASE}{path}",
        source_name=_INPI_ATTRIBUTION,
    )


def _dump(model: Any) -> dict[str, Any]:
    """Serialize a Pydantic row to dict with INPI's ST.66/ST.86 aliases."""
    if hasattr(model, "model_dump"):
        return cast("dict[str, Any]", model.model_dump(by_alias=True))
    if isinstance(model, dict):
        return cast("dict[str, Any]", model)
    raise TypeError(f"_dump expected Pydantic model or dict, got {type(model).__name__}")


# Lean-vs-full projection (§5.5). Lean drops raw ST.66/ST.86 XML notice,
# Director-General decision references, and prior-rights arrays. The
# row models don't currently carry raw_notice/dg_decisions/prior_rights
# fields — they will land in a follow-up once cassette validation
# stabilizes (spec §6 open issue) — but the lean shape is wired so the
# follow-up is a pure projection change.
_LEAN_TM_FIELDS: tuple[str, ...] = (
    "ApplicationNumber",
    "Mark",
    "ApplicantName",
    "HolderName",
    "MarkCurrentStatusCode",
    "ApplicationDate",
    "RegistrationDate",
    "ClassNumber",
)
_LEAN_DESIGN_FIELDS: tuple[str, ...] = (
    "DesignApplicationNumber",
    "DesignReference",
    "DesignTitle",
    "ApplicantName",
    "HolderName",
    "DesignCurrentStatusCode",
    "DesignApplicationDate",
    "RegistrationDate",
    "ClassNumber",
)


def _project_lean(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Project a record to only the fields in the lean field-set."""
    return {key: record.get(key) for key in fields}


def _summarize_tm(record: dict[str, Any]) -> str:
    appno = record.get("ApplicationNumber") or "(no appno)"
    mark = record.get("Mark") or "(no verbal element)"
    applicants = record.get("ApplicantName") or []
    owner = applicants[0] if applicants else "(no applicant)"
    status = record.get("MarkCurrentStatusCode") or "(unknown status)"
    filing = record.get("ApplicationDate") or "?"
    head = f"**INPI TM {appno}** — {mark} (applicant: {owner})"
    return f"{head}\nStatus: {status}. Filed {filing}."


def _summarize_design(record: dict[str, Any]) -> str:
    appno = record.get("DesignApplicationNumber") or "(no appno)"
    ref = record.get("DesignReference")
    appno_full = f"{appno}-{ref}" if ref else appno
    title = record.get("DesignTitle") or "(no title)"
    applicants = record.get("ApplicantName") or []
    owner = applicants[0] if applicants else "(no applicant)"
    status = record.get("DesignCurrentStatusCode") or "(unknown status)"
    filing = record.get("DesignApplicationDate") or "?"
    head = f"**INPI Design {appno_full}** — {title} (applicant: {owner})"
    return f"{head}\nStatus: {status}. Filed {filing}."


# ---------------------------------------------------------------------------
# Trademarks
# ---------------------------------------------------------------------------


@conditional_tool(inpi_pi_mcp, requires_env=_INPI_REQUIRED_ENV, annotations=READ_ONLY)
async def search_inpi_trademarks(
    query: Annotated[
        str | None,
        (
            "SolR Lucene query expression against INPI's marques index. "
            "Example: 'Mark:Apple AND MarkCurrentStatusCode:registered'. "
            "Leave blank to combine only the structured filter args."
        ),
    ] = None,
    nice_class: Annotated[
        list[str] | None,
        "Nice classes to OR together, e.g. ['9', '38']. Maps to ClassNumber.",
    ] = None,
    applicant: Annotated[str | None, "Applicant name term — matches DEPOSANT index"] = None,
    status: Annotated[str | None, "Mark current status (e.g. 'registered', 'filed')"] = None,
    date_from: Annotated[str | None, "Filing date lower bound, YYYYMMDD"] = None,
    date_to: Annotated[str | None, "Filing date upper bound, YYYYMMDD"] = None,
    offset: Annotated[int, "0-indexed offset; INPI caps at 500"] = 0,
    limit: Annotated[int, "Page size, 1..100"] = 25,
    full: Annotated[
        bool,
        (
            "When False (default), each hit is a lean stub: application "
            "number, verbal element, applicant, holder, status, filing/"
            "registration dates, Nice classes. When True, every hit "
            "carries the full ST.66 row. Use ``get_inpi_trademark`` for "
            "single-record depth."
        ),
    ] = False,
) -> ListEnvelope[dict]:
    """Search French national trademarks (FR national, ST.66 v1.0).

    Related: ``search_euipo_trademarks`` — for EUTMs designating FR,
    which represent the majority of FR-relevant TM coverage.
    ``search_inpi_trademarks`` is for FR-national-only filings
    (~190k active). Cross-link to ``get_inpi_trademark`` for one
    record at full ST.66 depth.
    """
    async with InpiPiClient() as client:
        rows, total = await client.search_trademarks(
            query,
            nice_class=nice_class,
            applicant=applicant,
            status=status,
            date_from=date_from,
            date_to=date_to,
            offset=offset,
            limit=limit,
        )

    dumped = [_dump(row) for row in rows]
    items = dumped if full else [_project_lean(r, _LEAN_TM_FIELDS) for r in dumped]
    more = total is not None and (offset + len(items)) < total
    query_label = f"`{query}`" if query else "(structured)"
    summary_total = f"{len(items)} of {total} hits" if total is not None else f"{len(items)} hits"
    return ListEnvelope[dict](
        summary=f"INPI trademarks — {query_label}: {summary_total} (offset {offset}).",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_inpi_provenance("/services/apidiffusion/api/marques/search"),
    )


@conditional_tool(inpi_pi_mcp, requires_env=_INPI_REQUIRED_ENV, annotations=READ_ONLY)
async def get_inpi_trademark(
    application_number: Annotated[
        str | list[str],
        (
            "INPI national trademark application number (e.g. '4216963'). "
            "Pass a list (max 50) for portfolio workflows; the response "
            "shape stays a ListEnvelope. Iterated serially to respect "
            "the 10 req/min INPI throttle."
        ),
    ],
    full: Annotated[
        bool,
        (
            "When True, returns the full ST.66 v1.0 record including any "
            "raw notice envelope. When False (default) returns the lean "
            "projection."
        ),
    ] = False,
) -> ListEnvelope[dict]:
    """Fetch full FR national trademark record(s) by application number.

    ST.66 v1.0 bibliographic record. List-accept per §5.4 (cap 50).
    Related: ``search_inpi_trademarks``, ``get_euipo_trademark`` for
    EUTM coverage of FR-designated marks.
    """
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_inpi_trademark requires at least one application_number")

    async with InpiPiClient() as client:
        rows = await client.get_trademark(numbers)

    dumped = [_dump(row) for row in rows]
    items = dumped if full else [_project_lean(r, _LEAN_TM_FIELDS) for r in dumped]

    if len(items) == 1:
        summary = _summarize_tm(dumped[0])
        path = f"/services/apidiffusion/api/marques/{numbers[0]}"
    else:
        summary = f"Fetched {len(items)} INPI trademarks: {', '.join(numbers)}."
        path = "/services/apidiffusion/api/marques"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_inpi_provenance(path),
    )


# ---------------------------------------------------------------------------
# Designs (dessins et modèles)
# ---------------------------------------------------------------------------


@conditional_tool(inpi_pi_mcp, requires_env=_INPI_REQUIRED_ENV, annotations=READ_ONLY)
async def search_inpi_designs(
    query: Annotated[
        str | None,
        (
            "SolR Lucene query against INPI's dessins index. Example: "
            "'DesignTitle:chair AND ClassNumber:0601'."
        ),
    ] = None,
    locarno_class: Annotated[
        list[str] | None,
        "Locarno classes to OR together (e.g. ['0601', '0602']).",
    ] = None,
    applicant: Annotated[str | None, "Applicant term — matches DEPOSANT"] = None,
    status: Annotated[str | None, "Design current status"] = None,
    date_from: Annotated[str | None, "Filing date lower bound, YYYYMMDD"] = None,
    date_to: Annotated[str | None, "Filing date upper bound, YYYYMMDD"] = None,
    offset: Annotated[int, "0-indexed offset; INPI caps at 500"] = 0,
    limit: Annotated[int, "Page size, 1..100"] = 25,
    full: Annotated[
        bool,
        (
            "When False (default), each hit is a lean stub: application "
            "number, design reference, title, applicant, holder, status, "
            "filing/registration dates, Locarno classes. When True, "
            "every hit carries the full ST.86 row."
        ),
    ] = False,
) -> ListEnvelope[dict]:
    """Search French national designs (FR national, ST.86 v1.0).

    Related: ``search_euipo_designs`` — for Registered Community Designs
    (RCDs), which represent the majority of FR-relevant design
    coverage. ``search_inpi_designs`` is for FR-national-only filings.
    Hague international registrations designating FR are handled by
    WIPO Hague (separate connector).
    """
    async with InpiPiClient() as client:
        rows, total = await client.search_designs(
            query,
            locarno_class=locarno_class,
            applicant=applicant,
            status=status,
            date_from=date_from,
            date_to=date_to,
            offset=offset,
            limit=limit,
        )

    dumped = [_dump(row) for row in rows]
    items = dumped if full else [_project_lean(r, _LEAN_DESIGN_FIELDS) for r in dumped]
    more = total is not None and (offset + len(items)) < total
    query_label = f"`{query}`" if query else "(structured)"
    summary_total = f"{len(items)} of {total} hits" if total is not None else f"{len(items)} hits"
    return ListEnvelope[dict](
        summary=f"INPI designs — {query_label}: {summary_total} (offset {offset}).",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_inpi_provenance("/services/apidiffusion/api/dessins/search"),
    )


@conditional_tool(inpi_pi_mcp, requires_env=_INPI_REQUIRED_ENV, annotations=READ_ONLY)
async def get_inpi_design(
    application_number: Annotated[
        str | list[str],
        (
            "INPI national design application number (e.g. 'FR20140182'). "
            "Pass a list (max 50) for portfolio workflows."
        ),
    ],
    full: Annotated[
        bool,
        "When True, return the full ST.86 v1.0 record; default lean projection.",
    ] = False,
) -> ListEnvelope[dict]:
    """Fetch full FR national design record(s) by application number.

    ST.86 v1.0 bibliographic record. List-accept per §5.4 (cap 50).
    Related: ``search_inpi_designs``, ``get_euipo_design`` for RCD
    coverage of FR-relevant designs.
    """
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_inpi_design requires at least one application_number")

    async with InpiPiClient() as client:
        rows = await client.get_design(numbers)

    dumped = [_dump(row) for row in rows]
    items = dumped if full else [_project_lean(r, _LEAN_DESIGN_FIELDS) for r in dumped]

    if len(items) == 1:
        summary = _summarize_design(dumped[0])
        path = f"/services/apidiffusion/api/dessins/{numbers[0]}"
    else:
        summary = f"Fetched {len(items)} INPI designs: {', '.join(numbers)}."
        path = "/services/apidiffusion/api/dessins"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_inpi_provenance(path),
    )


# Re-export for tests that want to verify model objects directly.
_MODELS = (InpiTrademarkRow, InpiDesignRow)


__all__ = ["inpi_pi_mcp"]

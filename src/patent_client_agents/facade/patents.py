"""Consolidated cross-jurisdiction patent search/retrieval facade (public toolset).

Thin dispatchers over the per-source patent tool functions in
``patent_client_agents.mcp.tools.{publications,epo_ops,uspto,kipo_kipris,office_actions}``.
No business logic lives here beyond jurisdiction routing: each branch forwards
to an existing function that already returns the §5.9 envelope (or its native
dict), so the §5.15 per-module helpers and the canonical templates stay
untouched.

**Path A — Google Patents removed.** The hosted public connector must not touch
Google Patents (scraped, non-public-domain). Every branch that previously routed
to Google now routes to a clean source:

- ``search_patents`` — US → USPTO PPUBS full-text search; EP/WO → EPO OPS CQL;
  KR → KIPRIS (when ``KIPO_KIPRIS_API_KEY`` is set); CN/JP/other → an actionable
  "search not available for this jurisdiction; retrieve a known number via
  get_patent" message (never a silent empty result).
- ``get_patent`` (view enum):
    - ``biblio``  → PPUBS (US) / KIPRIS (KR) / EPO OPS biblio (everything else).
    - ``claims``  → clean ODP→EPO cascade (``get_patent_claims_clean``).
    - ``family``  → USPTO ODP (was never Google).
    - ``figures`` → PPUBS/EPO page images; Google's ML callout bounding boxes are
      dropped (response notes "callouts unavailable from clean sources").
    - ``citations`` → US: USPTO office-action examiner-cited references (honest,
      degraded — true forward citations have no clean public source); non-US: a
      clear "forward citations not available for this jurisdiction" message.

``resolve_patent_number`` and ``patent_client_status`` never touched Google.

The source ``get_patent`` is not imported (Google-backed); the dispatcher owns
the routing. KR routing is env-gated at call time so the single ``search_patents``
/ ``get_patent`` tool surface stays stable whether or not the KIPRIS key is set.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Literal

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, ResponseEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents import __version__
from patent_client_agents.mcp.tools.epo_ops import (
    convert_epo_number,
    get_epo_biblio,
    get_epo_cql_help,
    search_epo,
)
from patent_client_agents.mcp.tools.office_actions import search_office_actions
from patent_client_agents.mcp.tools.patents import get_patent_figures_clean
from patent_client_agents.mcp.tools.publications import (
    get_patent_publication,
    resolve_publication_number,
    search_patent_publications,
)
from patent_client_agents.mcp.tools.uspto import get_patent_family
from patent_client_agents.unified import get_patent_claims_clean

patents_facade_mcp = FastMCP("Patent search")

#: Env var that gates the Korean (KIPRIS) routing. Per ToS §11 BYOK.
_KIPO_ENV = "KIPO_KIPRIS_API_KEY"

#: Country codes routed to EPO OPS for biblio/search (EPO indexes these well).
_EPO_SEARCH_COUNTRIES = {"EP", "WO"}


def _kipo_configured() -> bool:
    """True when the KIPRIS API key is present (KR routing is live)."""
    return bool(os.environ.get(_KIPO_ENV))


def _country_of(identifier: str) -> str | None:
    """Two-letter country prefix of a publication number, or None."""
    head = (identifier or "").strip()[:2]
    if len(head) == 2 and head.isalpha():
        return head.upper()
    return None


def _digits(identifier: str) -> str:
    """Strip a publication number down to digits (KIPRIS wants digits-only)."""
    return "".join(ch for ch in identifier if ch.isdigit())


# ──────────────────────────────────────────────────────────────────────
# search_patents — jurisdiction-routed full-text / biblio search
# ──────────────────────────────────────────────────────────────────────


@patents_facade_mcp.tool(
    annotations=READ_ONLY,
    title="Search Patents (US / EP / WO / KR)",
)
async def search_patents(
    query: Annotated[
        str,
        "Search query. For US (jurisdiction='us') this is PPUBS full-text "
        "syntax (Boolean + field codes like CLM/SPEC/AB/TI). For EP/WO "
        "(jurisdiction='ep_wo') this is EPO CQL (e.g. 'ta=CRISPR and pa=Broad'). "
        "For KR (jurisdiction='kr') this is KIPRIS free text.",
    ],
    jurisdiction: Annotated[
        Literal["us", "ep_wo", "kr"],
        "Which clean source to search. 'us' = USPTO Public Search (PPUBS) "
        "full text (claims + specification + abstract). 'ep_wo' = EPO OPS "
        "worldwide CQL search (best for EP/WO; biblio across many offices). "
        "'kr' = KIPO KIPRIS (requires the deployment to carry a KIPRIS key). "
        "Note: CN and JP full-text search have no clean public source — "
        "retrieve a known CN/JP number via get_patent instead.",
    ] = "us",
    limit: Annotated[int, "Maximum results to return (1-20 for US PPUBS)."] = 20,
    full: Annotated[
        bool,
        "False (default) = lean stub per hit. True = full upstream row "
        "(large; prefer get_patent for one record).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search patents by jurisdiction using clean public sources (no Google).

    Routes to the right official source by ``jurisdiction``:
    US → USPTO PPUBS full text; EP/WO → EPO OPS CQL; KR → KIPRIS.
    Returns a §5.9 ``ListEnvelope`` of hits (lean stubs by default).

    Full-text search of CN and JP body text has no clean public source. To
    look at a known CN/JP publication, pass its number to ``get_patent``.

    Related tools: get_patent, resolve_patent_number.
    """
    if jurisdiction == "us":
        return await search_patent_publications(query=query, limit=limit, full=full)
    if jurisdiction == "ep_wo":
        return await search_epo(cql_query=query, range_begin=1, range_end=limit, full=full)
    # jurisdiction == "kr"
    if not _kipo_configured():
        raise ValidationError(
            "Korean (KR) patent search is not enabled on this server "
            f"({_KIPO_ENV} is not configured). Use jurisdiction='us' (USPTO "
            "PPUBS) or 'ep_wo' (EPO OPS) for clean full-text/biblio search, "
            "or retrieve a known KR number with get_patent."
        )
    from patent_client_agents.mcp.tools.kipo_kipris import search_kipo_patents

    return await search_kipo_patents(query=query, num_of_rows=limit, full=full)


# ──────────────────────────────────────────────────────────────────────
# get_patent — view dispatch over clean retrieval sources
# ──────────────────────────────────────────────────────────────────────


@patents_facade_mcp.tool(
    annotations=READ_ONLY,
    title="Get Patent (biblio / claims / family / figures / citations)",
)
async def get_patent(
    view: Annotated[
        Literal["biblio", "claims", "family", "figures", "citations"],
        "Which slice of a patent to fetch. 'biblio' = bibliographic record "
        "(title, abstract, applicants, classifications, dates) — US via PPUBS, "
        "KR via KIPRIS, everything else via EPO OPS. 'claims' = structured "
        "claims (US ODP grant XML, EPO OPS full-text fallback). 'family' = "
        "patent family relationships via USPTO ODP. 'figures' = figure page "
        "images (PPUBS/EPO; callout bounding boxes are not available from "
        "clean sources). 'citations' = US examiner-cited prior-art references "
        "(true forward citations have no clean public source; non-US "
        "unavailable).",
    ],
    identifier: Annotated[
        str | list[str],
        "Patent or publication number with country and kind code. Examples: "
        "'US10123456B2', 'US20230012345A1', 'EP3456789A1', 'KR1020230012345'. "
        "view='biblio' accepts a list for portfolio fan-out; the other views "
        "take a single number.",
    ],
) -> Any:
    """Fetch one slice of a patent by view, using clean public sources only.

    Routes by ``view`` and (for biblio) by jurisdiction: US → PPUBS, KR →
    KIPRIS (when configured), other → EPO OPS. No Google Patents is touched.

    Find numbers with ``search_patents``; normalize with
    ``resolve_patent_number``.

    Related tools: search_patents, resolve_patent_number.
    """
    if view == "biblio":
        return await _get_biblio(identifier)
    if view == "claims":
        return await get_patent_claims_clean(_as_single(identifier, "claims"))
    if view == "family":
        return await get_patent_family(_as_single(identifier, "family"), identifier_type="patent")
    if view == "figures":
        return await get_patent_figures_clean(_as_single(identifier, "figures"))
    # view == "citations"
    return await _citations(_as_single(identifier, "citations"))


def _as_single(identifier: str | list[str], view: str) -> str:
    """Coerce to a single number; the non-biblio views are single-number only."""
    if isinstance(identifier, list):
        if len(identifier) != 1:
            raise ValidationError(
                f"get_patent(view='{view}') takes a single number, not a list. "
                "Only view='biblio' accepts a list."
            )
        return identifier[0]
    return identifier


async def _get_biblio(identifier: str | list[str]) -> ListEnvelope[dict]:
    """Bibliographic fetch routed by jurisdiction (US→PPUBS, KR→KIPRIS, else EPO)."""
    numbers = [identifier] if isinstance(identifier, str) else list(identifier)
    if not numbers:
        raise ValidationError("get_patent(view='biblio') requires at least one number")

    countries = {_country_of(n) for n in numbers}
    # Homogeneous jurisdiction → route to the single best clean source.
    if countries == {"US"}:
        return await get_patent_publication(publication_number=numbers)
    if countries == {"KR"}:
        if not _kipo_configured():
            raise ValidationError(
                "Korean (KR) bibliographic retrieval is not enabled on this "
                f"server ({_KIPO_ENV} is not configured). EPO OPS biblio may "
                "still cover this KR publication — re-try without forcing KR, "
                "or contact the operator to enable KIPRIS."
            )
        from patent_client_agents.mcp.tools.kipo_kipris import get_kipo_patent

        return await get_kipo_patent(application_number=[_digits(n) for n in numbers])
    # Mixed or non-US/KR → EPO OPS (indexes worldwide biblio incl. CN/JP/KR).
    return await get_epo_biblio(patent_number=numbers)


async def _citations(identifier: str) -> ResponseEnvelope[dict]:
    """Forward-citation request answered honestly from clean sources.

    True forward citations (patents that cite this one) have no clean public
    source — they were a Google Patents enrichment. For US patents we instead
    return the USPTO examiner-cited prior-art references for the application
    (clean, but a different relation: references this patent cited, not
    patents citing it). For non-US we return an explicit unavailable message
    rather than a silent empty result.
    """
    country = _country_of(identifier)
    if country == "US":
        # USPTO office-action citations are keyed by application number. We
        # forward the patent/application number as-is on the application-number
        # field; PPUBS/ODP numbers resolve there. This surfaces examiner-cited
        # references, clearly labeled as NOT forward citations.
        app_no = _digits(identifier)
        result = await search_office_actions(
            criteria=f"patentApplicationNumber:{app_no}",
            result_type="citations",
            rows=100,
        )
        note = (
            "NOTE: True forward citations (patents that cite this one) are not "
            "available from clean public sources. The references below are the "
            "USPTO examiner-/applicant-cited prior-art references from this "
            "patent's own prosecution — a different relation."
        )
        return ResponseEnvelope[dict](
            summary=f"{note} {result.summary}",
            details={"examiner_cited_references": list(result.items), "note": note},
            provenance=result.provenance,
        )
    return ResponseEnvelope[dict](
        summary=(
            f"Forward citations are not available for {country or 'this'} "
            "publications from clean public sources. Google Patents (the only "
            "worldwide forward-citation source) is intentionally not used by "
            "this server. For US patents, get_patent(view='citations') returns "
            "USPTO examiner-cited references instead."
        ),
        details={
            "available": False,
            "jurisdiction": country,
            "reason": "no_clean_forward_citation_source",
        },
        provenance=make_provenance(
            source_url="https://mcp.patentclient.com/",
            source_name="patent-client-agents (no clean forward-citation source)",
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# resolve_patent_number — mode dispatch (never touched Google)
# ──────────────────────────────────────────────────────────────────────


@patents_facade_mcp.tool(
    annotations=READ_ONLY,
    title="Resolve / Convert Patent Number",
)
async def resolve_patent_number(
    mode: Annotated[
        Literal["resolve", "convert_epo", "cql_help"],
        "What to do. 'resolve' = normalize a publication number to canonical "
        "form and confirm it exists in USPTO Public Search (PPUBS). "
        "'convert_epo' = convert a number between EPO formats "
        "(original ↔ docdb ↔ epodoc). 'cql_help' = show the EPO CQL search "
        "syntax accepted by EPO search (no identifier needed).",
    ] = "resolve",
    number: Annotated[
        str | None,
        "The number to act on. Required for 'resolve' and 'convert_epo'; "
        "ignored for 'cql_help'. resolve: 'US20230012345A1', '10123456', etc. "
        "convert_epo: 'EP1234567A1', 'EP.1234567.A1', 'EP1234567'.",
    ] = None,
    input_format: Annotated[
        str, "convert_epo only: input format — 'original', 'docdb', or 'epodoc'."
    ] = "original",
    output_format: Annotated[
        str, "convert_epo only: output format — 'docdb' or 'epodoc'."
    ] = "docdb",
) -> ResponseEnvelope[dict]:
    """Normalize or convert a patent number, or show EPO search syntax.

    'resolve' confirms a publication number against PPUBS and returns its
    canonical form. 'convert_epo' translates between EPO normalization formats.
    'cql_help' returns the EPO CQL field codes and operators for building EPO
    queries. All three return a §5.9 ``ResponseEnvelope``.

    Related tools: search_patents, get_patent.
    """
    if mode == "convert_epo":
        return await convert_epo_number(
            number=number, input_format=input_format, output_format=output_format
        )
    if mode == "cql_help":
        return await get_epo_cql_help()
    if number is None:
        raise ValidationError("resolve_patent_number(mode='resolve') requires number")
    return await resolve_publication_number(publication_number=number)


# Env vars that gate each connector family. Presence (non-empty) means the
# family is configured for live calls; absence means it falls back / is off.
_CONNECTOR_ENV = {
    "uspto": ["USPTO_ODP_API_KEY"],
    "epo": ["EPO_OPS_API_KEY", "EPO_OPS_API_SECRET"],
    "jpo": ["JPO_API_USERNAME", "JPO_API_PASSWORD"],
    "euipo": ["EUIPO_CLIENT_ID"],
    "ip_australia": ["IPAUSTRALIA_CLIENT_ID"],
    "kipo": ["KIPO_KIPRIS_API_KEY"],
    "tipo": ["TIPO_API_KEY"],
    "inpi": ["INPI_USERNAME"],
    "canlii": ["CANLII_API_KEY"],
}


@patents_facade_mcp.tool(
    annotations=READ_ONLY,
    title="Patent Client Status",
)
async def patent_client_status() -> dict:
    """Report package version and which env-gated connector families are configured.

    No network calls — reports the installed ``patent-client-agents`` version
    and, per connector family, whether its required environment variables are
    present. The USPTO/EPO clean sources and bundled SQLite corpora are the
    always-available backbone; KR (KIPRIS) search/retrieval activates only when
    ``KIPO_KIPRIS_API_KEY`` is configured.

    Related tools: search_patents, get_patent.
    """
    configured = {
        family: all(os.environ.get(var) for var in env_vars)
        for family, env_vars in _CONNECTOR_ENV.items()
    }
    return {
        "version": __version__,
        "configured_families": configured,
        "always_available": ["uspto_ppubs", "epo_ops", "bundled_corpora"],
    }

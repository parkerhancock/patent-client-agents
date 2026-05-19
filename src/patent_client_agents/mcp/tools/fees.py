"""IP-office fee schedules — MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_proxy``, ``update_strategy=live_proxy``,
``update_cadence=annual``. The connector live-fetches each office's
schedule (USPTO HTML page; EPO undocumented BFF JSON; EUIPO HTML +
Next.js SSR stream) with a 7-day hishel TTL. Provenance carries
``corpus_synced_at`` = the schedule's effective date so agents can
quote freshness in the same shape as the bundled-corpus connectors.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, ResponseEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.fees import (
    FeesClient,
    RightType,
    UnknownJurisdictionError,
)
from patent_client_agents.fees.client import resolve_jurisdiction
from patent_client_agents.fees.models import EntityTier, FeeSchedule
from patent_client_agents.fees.registry import OFFICES, get_scraper

fees_mcp = FastMCP("IP fee schedules")


_SOURCE_NAME = "IP-office fee schedules"


def _fees_provenance(schedule: FeeSchedule | None, fallback_url: str) -> Any:
    """Build Provenance for a fees response.

    ``corpus_synced_at`` is the schedule's ``retrieved_at`` (when our cache
    last successfully read upstream); ``corpus_version`` is a
    ``snapshot-<effective_date>`` label so agents can cite the figures by
    revision date.
    """
    if schedule is None:
        return make_provenance(
            source_url=fallback_url,
            source_name=_SOURCE_NAME,
            corpus_synced_at=None,
            corpus_version="unknown",
        )
    return make_provenance(
        source_url=schedule.source_url,
        source_name=f"{_SOURCE_NAME} — {schedule.office_code}",
        corpus_synced_at=datetime(
            schedule.retrieved_at.year,
            schedule.retrieved_at.month,
            schedule.retrieved_at.day,
            tzinfo=UTC,
        ),
        corpus_version=f"snapshot-{schedule.effective_date.isoformat()}",
    )


def _summarize_schedule(s: FeeSchedule) -> str:
    return (
        f"**{s.office_code} {s.right.value} fee schedule** "
        f"({s.jurisdiction}) — effective {s.effective_date.isoformat()}, "
        f"{len(s.fees)} fees in {s.currency}. "
        f"Source: {s.source_url}"
    )


def _resolve_right(right: str) -> RightType:
    try:
        return RightType(right.lower())
    except ValueError as exc:
        raise ValidationError(
            f"unknown right {right!r}; supported: {[r.value for r in RightType]}"
        ) from exc


# ──────────────────────────────────────────────────────────────────────
# get_fee_schedule
# ──────────────────────────────────────────────────────────────────────


@fees_mcp.tool(annotations=READ_ONLY)
async def get_fee_schedule(
    jurisdiction: Annotated[
        str,
        "Office or jurisdiction. Accepts 'USPTO', 'US', 'EPO', 'EUIPO', or "
        "'EP' (which routes to EPO for patents and EUIPO for trademarks/designs).",
    ],
    right: Annotated[
        str,
        "Which IP right's schedule: 'patent' (default), 'trademark', or "
        "'design'. EPO has only patents; EUIPO has only trademarks + designs.",
    ] = "patent",
) -> ResponseEnvelope[dict]:
    """Fetch the full fee schedule for an IP office.

    Returns every line item the office publishes for the requested
    right, with amounts in the office's native currency, entity-tier
    where applicable (USPTO large/small/micro), and a ``year`` field on
    renewal/maintenance rows. The schedule's ``effective_date`` is the
    most-recent revision date the office surfaces; ``retrieved_at`` is
    when our cache last refreshed from upstream.

    Examples:
      * USPTO utility patents:   jurisdiction='USPTO'
      * USPTO trademarks:        jurisdiction='USPTO', right='trademark'
      * EPO patents:             jurisdiction='EPO'
      * EUIPO design (REUD):     jurisdiction='EUIPO', right='design'

    Related tools: list_fee_jurisdictions, lookup_fee.
    """
    right_enum = _resolve_right(right)
    try:
        _, office_code = resolve_jurisdiction(jurisdiction, right_enum)
    except UnknownJurisdictionError as exc:
        raise ValidationError(str(exc)) from exc

    scraper = get_scraper(office_code, right_enum)
    schedule = await scraper()
    summary = _summarize_schedule(schedule)

    return ResponseEnvelope[dict](
        summary=summary,
        details=schedule.model_dump(mode="json"),
        provenance=_fees_provenance(schedule, schedule.source_url),
    )


# ──────────────────────────────────────────────────────────────────────
# list_fee_jurisdictions
# ──────────────────────────────────────────────────────────────────────


@fees_mcp.tool(annotations=READ_ONLY)
async def list_fee_jurisdictions() -> ListEnvelope[dict]:
    """Return one row per supported (jurisdiction, right) fee schedule.

    Lean cross-office summary — issuing body, currency, effective date,
    fee count, days since last upstream refresh. Use this to discover
    what schedules are available before calling :func:`get_fee_schedule`.

    Related tools: get_fee_schedule, lookup_fee.
    """
    async with FeesClient() as client:
        rows = await client.list_schedules()
    items = [r.model_dump(mode="json") for r in rows]
    summary = f"{len(rows)} fee schedules across {len(OFFICES)} offices ({', '.join(OFFICES)})."
    # Use a stable canonical landing-page URL for the provenance source.
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_fees_provenance(None, "https://patentclient.com/atlas"),
    )


# ──────────────────────────────────────────────────────────────────────
# lookup_fee
# ──────────────────────────────────────────────────────────────────────


@fees_mcp.tool(annotations=READ_ONLY)
async def lookup_fee(
    jurisdiction: Annotated[
        str,
        "Office or jurisdiction (see get_fee_schedule).",
    ],
    category: Annotated[
        str | None,
        "Filter to one fee category. Common values: 'filing', 'search', "
        "'examination', 'grant', 'renewal', 'maintenance', 'excess_claims', "
        "'extension', 'appeal', 'petition', 'opposition'. Pass None to "
        "match every category.",
    ] = None,
    tier: Annotated[
        str,
        "Entity-tier filter for offices with discounts (USPTO patents + "
        "designs). 'large' (default), 'small', or 'micro'. Silently "
        "ignored on schedules with no tier dimension (EPO, EUIPO, USPTO TM).",
    ] = "large",
    year: Annotated[
        int | None,
        "Required when filtering renewal/maintenance fees — pass the year "
        "you want (USPTO maintenance: 4, 8, or 12; EPO renewals: 2-20; "
        "EUIPO design renewals: 5, 10, 15, 20; TM renewals: 10). When "
        "None, renewal/maintenance rows are excluded from the result.",
    ] = None,
    right: Annotated[
        str,
        "'patent' (default), 'trademark', or 'design'.",
    ] = "patent",
) -> ListEnvelope[dict]:
    """Filter a fee schedule down to matching line items.

    Returns a list (possibly empty) of fees matching ALL provided
    filters. Filters interact:

    * ``year=None`` (default) excludes renewal/maintenance rows.
    * ``tier`` only narrows on USPTO patents/designs; ignored elsewhere.
    * ``category=None`` returns every category that matches the other filters.

    Examples:
      * USPTO 3.5-year maintenance fee:
          jurisdiction='USPTO', category='maintenance', year=4
      * EPO 10th-year renewal:
          jurisdiction='EPO', category='renewal', year=10
      * EUIPO design 4th-period renewal:
          jurisdiction='EUIPO', right='design', category='renewal', year=20

    Related tools: get_fee_schedule, list_fee_jurisdictions.
    """
    right_enum = _resolve_right(right)
    try:
        tier_enum = EntityTier(tier.lower())
    except ValueError as exc:
        raise ValidationError(
            f"unknown tier {tier!r}; supported: {[t.value for t in EntityTier]}"
        ) from exc

    async with FeesClient() as client:
        try:
            fees = await client.lookup_fee(
                jurisdiction,
                category=category,
                tier=tier_enum,
                year=year,
                right=right_enum,
            )
            # Reach into the same scraper to lift a schedule for provenance.
            schedule = await client.get_schedule(jurisdiction, right_enum)
        except UnknownJurisdictionError as exc:
            raise ValidationError(str(exc)) from exc

    items = [f.model_dump(mode="json") for f in fees]
    cat_part = f" category={category!r}" if category else ""
    year_part = f" year={year}" if year is not None else ""
    summary = (
        f"{schedule.office_code} {right_enum.value}{cat_part}{year_part}: "
        f"{len(items)} fee{'s' if len(items) != 1 else ''} "
        f"(schedule effective {schedule.effective_date.isoformat()})."
    )

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_fees_provenance(schedule, schedule.source_url),
    )


__all__ = ["fees_mcp", "get_fee_schedule", "list_fee_jurisdictions", "lookup_fee"]

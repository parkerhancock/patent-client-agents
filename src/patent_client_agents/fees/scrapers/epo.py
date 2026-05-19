"""EPO fee-schedule scraper.

The EPO publishes its schedule through a React SPA at
https://fees.apps.epo.org/prod/ui/ that is backed by an undocumented
but stable JSON BFF (backend-for-frontend) at
https://fees.apps.epo.org/prod/bff/api/fees. We hit the BFF directly —
the SPA is a thin wrapper around it.

Endpoint: ``GET /prod/bff/api/fees?language=EN&currency=EUR``

Response shape (truncated)::

    [
      {
        "key": 1,
        "data": {"feeCode": "001", "feeDescription": "Filing fee - EP direct", "amount": null},
        "children": [
          {"data": {"feeCode": null, "feeDescription": "not online", "amount": "285,00"}},
          {"data": {"feeCode": null, "feeDescription": "online", "amount": "135,00"}}
        ]
      },
      ...
    ]

Notes:

* Amounts are European-formatted strings: ``"1.595,00"`` → ``Decimal("1595.00")``.
* Parents with children carry no amount; the children are the priced rows.
* Parents without children are themselves the priced rows.
* EPO does not publish a single "effective_date" alongside the API
  payload; we capture today as ``retrieved_at`` and rely on EPO's
  cadence (revisions every 1-2 years per Administrative Council decision).

Statutory basis: Rules relating to Fees, EPC Implementing Regulations.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Any

from law_tools_core import BaseAsyncClient
from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeCondition,
    FeeItem,
    FeeSchedule,
    RightType,
)

logger = logging.getLogger(__name__)

EPO_FEES_API = "https://fees.apps.epo.org/prod/bff/api/fees"
EPO_FEES_UI = "https://fees.apps.epo.org/prod/ui/?lang=EN&currency=EUR"
EPO_FEES_OFFICIAL_PAGE = "https://www.epo.org/en/applying/fees"


class EPOFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the EPO fees BFF."""

    DEFAULT_BASE_URL = "https://fees.apps.epo.org"
    CACHE_NAME = "epo_fees"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("ttl_seconds", self.DEFAULT_TTL_SECONDS)
        kwargs.setdefault(
            "headers",
            {
                "User-Agent": "patent-client-agents (https://patentclient.com)",
                "Accept": "application/json",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_fees(self) -> list[dict[str, Any]]:
        return await self._request_json(
            "GET",
            "/prod/bff/api/fees",
            params={"language": "EN", "currency": "EUR"},
            context="epo_fees_bff",
        )  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────────────────
# Parsing
# ──────────────────────────────────────────────────────────────────────

_RENEWAL_YEAR_RE = re.compile(r"(\d+)(?:st|nd|rd|th)\s*year", re.IGNORECASE)
_CLAIMS_OVER_RE = re.compile(r"(?:from the\s*)?(\d+)(?:st|nd|rd|th)\s+claim", re.IGNORECASE)
_PAGES_OVER_RE = re.compile(r"35\s*pages?|over 35", re.IGNORECASE)


def _parse_eu_money(raw: str | None) -> Decimal | None:
    """'1.595,00' → Decimal('1595.00'); '0,00' → Decimal('0'). None → None."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    # European convention: '.' is thousands separator, ',' is decimal point
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        logger.warning("EPO fees: could not parse amount %r", raw)
        return None


def _categorize(description: str, parent_desc: str | None = None) -> FeeCategory:
    """Map EPO fee description → closed FeeCategory vocab."""
    d = description.lower()
    p = (parent_desc or "").lower()
    combined = f"{p} {d}".strip()

    if "renewal fee" in combined and "additional" not in combined and "add." not in combined:
        return FeeCategory.renewal
    if ("additional fee" in combined or "add. fee" in combined) and "renewal" in combined:
        return FeeCategory.late_fee
    if "filing fee" in combined:
        return FeeCategory.filing
    if "search fee" in combined or "search" == combined.strip():
        return FeeCategory.search
    if "examination fee" in combined or "exam fee" in combined:
        return FeeCategory.examination
    if "designation" in combined:
        return FeeCategory.designation
    if "grant" in combined or "printing" in combined or "publication" in combined:
        return FeeCategory.grant
    if "claims fee" in combined or "claim fee" in combined:
        return FeeCategory.excess_claims
    if "page fee" in combined or ("pages" in combined and "over" in combined):
        return FeeCategory.excess_pages
    if "appeal" in combined:
        return FeeCategory.appeal
    if "opposition" in combined:
        return FeeCategory.opposition
    if "petition" in combined or "re-establishment" in combined or "reinstatement" in combined:
        return FeeCategory.petition
    if "translation" in combined:
        return FeeCategory.translation
    if "transfer" in combined or "registration" in combined:
        return FeeCategory.transfer
    if "fee for further processing" in combined or "further processing" in combined:
        return FeeCategory.late_fee
    return FeeCategory.other


def _extract_year(description: str) -> int | None:
    m = _RENEWAL_YEAR_RE.search(description)
    if not m:
        return None
    return int(m.group(1))


def _detect_condition(description: str) -> FeeCondition | None:
    d = description.lower()
    if "claims fee" in d or "claim fee" in d:
        m = _CLAIMS_OVER_RE.search(d)
        if "16th" in d or "from the 16th" in d:
            return FeeCondition(
                trigger="claims_over",  # type: ignore[arg-type]
                threshold=15,
                per_unit=True,
                description="EPO charges per claim from the 16th onwards.",
            )
        if "51st" in d or "from the 51st" in d:
            return FeeCondition(
                trigger="claims_over",  # type: ignore[arg-type]
                threshold=50,
                per_unit=True,
                description="EPO higher-tier per-claim fee from the 51st onwards.",
            )
        # Fallback if threshold not yet identifiable
        threshold = int(m.group(1)) - 1 if m else 15
        return FeeCondition(
            trigger="claims_over",  # type: ignore[arg-type]
            threshold=threshold,
            per_unit=True,
        )
    if "page fee" in d or ("pages" in d and "over" in d):
        return FeeCondition(
            trigger="pages_over",  # type: ignore[arg-type]
            threshold=35,
            per_unit=True,
            description="Per page over 35.",
        )
    return None


def _label_with_parent(parent_desc: str | None, child_desc: str) -> str:
    if parent_desc:
        return f"{parent_desc} — {child_desc}"
    return child_desc


def _walk(
    nodes: list[dict[str, Any]],
    parent_desc: str | None = None,
    parent_code: str | None = None,
) -> list[FeeItem]:
    """Flatten the EPO fee tree into FeeItems.

    For each node: if it has a numeric amount, emit a FeeItem. If it has
    children, recurse (children typically carry the priced rows for
    multi-option fees like online/paper filing).
    """
    items: list[FeeItem] = []
    for node in nodes:
        data = node.get("data") or {}
        children = node.get("children") or []
        code = data.get("feeCode") or parent_code
        description = (data.get("feeDescription") or "").strip()
        amount = _parse_eu_money(data.get("amount"))

        if amount is not None and code is not None:
            label = _label_with_parent(parent_desc, description) if parent_desc else description
            category = _categorize(description, parent_desc)
            year = (
                _extract_year(label)
                if category in (FeeCategory.renewal, FeeCategory.late_fee)
                else None
            )
            # If a row matched 'renewal' on keyword but isn't actually year-indexed
            # (e.g., 'Reimbursement of reduction of renewal fees'), downgrade to
            # `other` so the year-required validator doesn't reject it.
            if category == FeeCategory.renewal and year is None:
                category = FeeCategory.other
            condition = _detect_condition(label)
            items.append(
                FeeItem(
                    code=str(code),
                    label=label,
                    category=category,
                    rights=[RightType.patent],
                    amount=amount,
                    currency="EUR",
                    tier=EntityTier.none,
                    year=year,
                    condition=condition,
                    source_url=EPO_FEES_OFFICIAL_PAGE,
                )
            )

        if children:
            items.extend(_walk(children, parent_desc=description, parent_code=code))
    return items


async def scrape_epo_patents() -> FeeSchedule:
    """Fetch the EPO patent fee schedule from the BFF and project into FeeItems."""
    async with EPOFeesClient() as client:
        raw = await client.fetch_fees()
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(
            "EPO fees BFF returned unexpected payload; API contract may have changed"
        )

    fees = _walk(raw)

    # Late-fee rows for renewals need year too — they map to a renewal year.
    # Our schema enforces year only for category=renewal|maintenance. Late fees
    # don't strictly need year, but storing it improves downstream lookups.
    # If our walk missed it for any late_fee row, the row still validates fine.

    if not fees:
        raise RuntimeError("EPO scraper parsed zero fees from BFF response")

    return FeeSchedule(
        jurisdiction="EP",
        issuing_body="European Patent Office",
        office_code="EPO",
        right=RightType.patent,
        currency="EUR",
        # EPO doesn't surface a single "effective_date" alongside the API
        # payload; we stamp today as a conservative effective date and let
        # callers consult the source_url for the canonical revision history.
        effective_date=date.today(),
        source_url=EPO_FEES_OFFICIAL_PAGE,
        statutory_basis=(
            "Rules relating to Fees, EPC Implementing Regulations; "
            "set by EPO Administrative Council (CA/D decisions)."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Sourced from the EPO Schedule-of-Fees SPA's backing BFF "
            "(https://fees.apps.epo.org/prod/bff/api/fees). The BFF is "
            "undocumented but stable. Renewal years 2-20 covered by codes "
            "732-750; the parallel 752-770 series is the 'additional fee' "
            "(late-payment surcharge) for the same year. Codes 100-110 are "
            "additional fees for the IP5 sharing renewal calculation. "
            "Amounts converted from European notation ('1.595,00' → 1595.00)."
        ),
    )


__all__ = [
    "EPO_FEES_API",
    "EPO_FEES_UI",
    "EPO_FEES_OFFICIAL_PAGE",
    "EPOFeesClient",
    "scrape_epo_patents",
]

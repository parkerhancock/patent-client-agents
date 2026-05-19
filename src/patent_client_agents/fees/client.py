"""Dispatching client for the fees connectors.

The client itself does no HTTP — it just resolves the
``(jurisdiction, right)`` lookup to an office-specific scraper and
hands off. Each scraper owns its own :class:`BaseAsyncClient` instance
(with its own hishel cache, TTL, base URL) and is responsible for
cleanup. This client is cheap; constructing one never opens a socket.

Caching lives in each scraper, not here. That keeps office-specific
TTL knobs local (e.g., EUIPO may need a shorter TTL during the REUD
reform period than USPTO does).
"""

from __future__ import annotations

from datetime import date

from .models import (
    EntityTier,
    FeeItem,
    FeeSchedule,
    JurisdictionMeta,
    RightType,
)
from .registry import OFFICES, get_scraper

# ──────────────────────────────────────────────────────────────────────
# Jurisdiction resolver
# ──────────────────────────────────────────────────────────────────────
# Practitioners use a grab bag of names for the same office. The vocab
# is intentionally narrow: each alias maps to exactly one office. For
# "EP" the right disambiguates: patent → EPO, trademark/design → EUIPO.

_OFFICE_ALIASES: dict[str, tuple[str, str]] = {
    # USPTO
    "USPTO": ("US", "USPTO"),
    "US": ("US", "USPTO"),
    "U.S.": ("US", "USPTO"),
    "UNITED STATES": ("US", "USPTO"),
    # EPO
    "EPO": ("EP", "EPO"),
    "EUROPEAN PATENT OFFICE": ("EP", "EPO"),
    # EUIPO
    "EUIPO": ("EP", "EUIPO"),
    "EU INTELLECTUAL PROPERTY OFFICE": ("EP", "EUIPO"),
    "EUTM": ("EP", "EUIPO"),
    "EU IPO": ("EP", "EUIPO"),
    # CNIPA
    "CNIPA": ("CN", "CNIPA"),
    "CN": ("CN", "CNIPA"),
    "CHINA": ("CN", "CNIPA"),
    "CHINA NATIONAL INTELLECTUAL PROPERTY ADMINISTRATION": ("CN", "CNIPA"),
    # CIPO
    "CIPO": ("CA", "CIPO"),
    "CA": ("CA", "CIPO"),
    "CANADA": ("CA", "CIPO"),
    "CANADIAN INTELLECTUAL PROPERTY OFFICE": ("CA", "CIPO"),
    # DPMA
    "DPMA": ("DE", "DPMA"),
    "DE": ("DE", "DPMA"),
    "GERMANY": ("DE", "DPMA"),
    "DEUTSCHES PATENT- UND MARKENAMT": ("DE", "DPMA"),
    # KIPO
    "KIPO": ("KR", "KIPO"),
    "KR": ("KR", "KIPO"),
    "KOREA": ("KR", "KIPO"),
    "SOUTH KOREA": ("KR", "KIPO"),
    "KOREAN INTELLECTUAL PROPERTY OFFICE": ("KR", "KIPO"),
    # IP Australia
    "IPAU": ("AU", "IPAU"),
    "IP AUSTRALIA": ("AU", "IPAU"),
    "AU": ("AU", "IPAU"),
    "AUSTRALIA": ("AU", "IPAU"),
    # UKIPO
    "UKIPO": ("GB", "UKIPO"),
    "UK IPO": ("GB", "UKIPO"),
    "UK INTELLECTUAL PROPERTY OFFICE": ("GB", "UKIPO"),
    "GB": ("GB", "UKIPO"),
    "UK": ("GB", "UKIPO"),
    "UNITED KINGDOM": ("GB", "UKIPO"),
    "BRITAIN": ("GB", "UKIPO"),
    # JPO
    "JPO": ("JP", "JPO"),
    "JP": ("JP", "JPO"),
    "JAPAN": ("JP", "JPO"),
    "JAPAN PATENT OFFICE": ("JP", "JPO"),
}


class UnknownJurisdictionError(ValueError):
    """Raised when a jurisdiction/office input can't be resolved."""


def resolve_jurisdiction(value: str, right: RightType) -> tuple[str, str]:
    """Resolve a free-text jurisdiction or office name to ``(jurisdiction, office_code)``.

    The ``right`` parameter disambiguates regional codes — passing
    ``"EP"`` with ``right=patent`` returns ``("EP", "EPO")`` while
    ``right=trademark`` returns ``("EP", "EUIPO")`` because EPO has no
    trademark schedule.

    Raises :class:`UnknownJurisdictionError` if the value cannot be
    mapped to any office, or if the right is incompatible with the
    resolved office (e.g. ``EPO`` + ``trademark``).
    """
    key = value.strip().upper()
    if key == "EP":
        if right in (RightType.trademark, RightType.design):
            return "EP", "EUIPO"
        return "EP", "EPO"
    if key not in _OFFICE_ALIASES:
        raise UnknownJurisdictionError(
            f"Unknown jurisdiction or office {value!r}. "
            f"Accepted: {sorted(set(_OFFICE_ALIASES) | {'EP'})!r}."
        )
    juris, office = _OFFICE_ALIASES[key]
    if office == "EPO" and right in (RightType.trademark, RightType.design):
        raise UnknownJurisdictionError(
            f"EPO does not have a {right.value} schedule. EU-wide "
            f"{right.value}s are administered by EUIPO — pass 'EUIPO' "
            "as the jurisdiction."
        )
    if office == "EUIPO" and right == RightType.patent:
        raise UnknownJurisdictionError(
            "EUIPO does not have a patent schedule. EU-region patents "
            "are handled by EPO — pass 'EPO' as the jurisdiction."
        )
    return juris, office


class FeesClient:
    """Dispatching client for the bundled set of fee scrapers.

    The client itself is a thin facade. Real network work happens
    inside the per-office scraper modules, each of which owns its own
    cached HTTP client. Constructing this client is cheap.
    """

    async def __aenter__(self) -> FeesClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    # ──────────────────────────────────────────────────────────────────
    # Single schedule
    # ──────────────────────────────────────────────────────────────────

    async def get_schedule(
        self,
        jurisdiction: str,
        right: RightType | str = RightType.patent,
    ) -> FeeSchedule:
        """Fetch the full schedule for ``(jurisdiction, right)``."""
        right_enum = right if isinstance(right, RightType) else RightType(right)
        _, office = resolve_jurisdiction(jurisdiction, right_enum)
        scraper = get_scraper(office, right_enum)
        return await scraper()

    # ──────────────────────────────────────────────────────────────────
    # Cross-office listing
    # ──────────────────────────────────────────────────────────────────

    async def list_schedules(self) -> list[JurisdictionMeta]:
        """Return one ``JurisdictionMeta`` per supported ``(office, right)`` route.

        Calls each scraper once — they share cache, so subsequent calls
        are cheap. Returns rows in registry order.
        """
        from .registry import _DISPATCH  # local import; intentional

        rows: list[JurisdictionMeta] = []
        for (_office, _right), scraper in _DISPATCH.items():
            schedule = await scraper()
            rows.append(_to_meta(schedule))
        return rows

    # ──────────────────────────────────────────────────────────────────
    # Narrowed fee lookup
    # ──────────────────────────────────────────────────────────────────

    async def lookup_fee(
        self,
        jurisdiction: str,
        *,
        category: str | None = None,
        tier: EntityTier | str = EntityTier.large,
        year: int | None = None,
        right: RightType | str = RightType.patent,
    ) -> list[FeeItem]:
        """Return fees matching the given filters.

        Returns a list because some filters match multiple line items
        (e.g. ``category='excess_claims'`` on USPTO matches one row per
        tier). Empty list is a legitimate answer — not an error.

        Filter semantics:

        * ``category=None`` matches every category.
        * ``tier`` is silently ignored on schedules with no tier
          dimension (TM, EPO). On tiered schedules, only rows whose
          ``tier`` matches are returned.
        * ``year=None`` excludes renewal/maintenance rows (caller
          didn't ask for them). Pass an integer to filter to one year.
        """
        right_enum = right if isinstance(right, RightType) else RightType(right)
        tier_enum = tier if isinstance(tier, EntityTier) else EntityTier(tier)
        schedule = await self.get_schedule(jurisdiction, right_enum)

        def _match(fee: FeeItem) -> bool:
            if category is not None and fee.category.value != category:
                return False
            if fee.tier != EntityTier.none and fee.tier != tier_enum:
                return False
            if year is not None and fee.year != year:
                return False
            if year is None and fee.year is not None:
                return False
            return True

        return [f for f in schedule.fees if _match(f)]


def _to_meta(s: FeeSchedule) -> JurisdictionMeta:
    today = date.today()
    return JurisdictionMeta(
        jurisdiction=s.jurisdiction,
        office_code=s.office_code,
        issuing_body=s.issuing_body,
        right=s.right,
        currency=s.currency,
        effective_date=s.effective_date,
        retrieved_at=s.retrieved_at,
        source_url=s.source_url,
        fee_count=len(s.fees),
        days_since_retrieval=max(0, (today - s.retrieved_at).days),
    )


__all__ = [
    "FeesClient",
    "UnknownJurisdictionError",
    "resolve_jurisdiction",
    "OFFICES",
]

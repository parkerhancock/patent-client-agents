"""Fees-category envelope-compliance tests.

Per CONNECTOR_STANDARDS.md §3a (Provenance for fees), every response
from a ``category: fees`` source MUST carry ``effective_date`` in the
envelope's Provenance. This is win #1 of the four-category schema
rollout (2026-05-21) — the CI contract that prevents quoting stale
fees to clients.

Two layers of enforcement:

1.  **Schema audit** — walk ``coverage/sources.yaml``, confirm every
    ``category: fees`` entry routes through ``patent_client_agents.fees``.
    The helper ``_fees_provenance`` is the single chokepoint, so verifying
    it once covers all 25 fee entries.

2.  **Behavioral test** — invoke ``get_fee_schedule`` and ``lookup_fee``
    against a patched dispatcher returning a synthetic schedule with a
    known ``effective_date``. Assert the Provenance on the returned
    envelope carries that date.

The schema layer fails fast if a new fees connector ever bypasses the
shared helper. The behavioral layer fails fast if the helper itself
ever stops setting ``effective_date``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from mcp_data_core.envelope import ListEnvelope, Provenance, ResponseEnvelope
from patent_client_agents.fees import RightType, registry
from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeItem,
    FeeSchedule,
)
from patent_client_agents.mcp.tools.fees import (
    _fees_provenance,
    get_fee_schedule,
    lookup_fee,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCES_YAML = ROOT / "coverage" / "sources.yaml"

KNOWN_EFFECTIVE_DATE = date(2026, 5, 1)


def _load_fees_entries() -> list[dict]:
    text = SOURCES_YAML.read_text()
    data = yaml.safe_load(text)
    return [s for s in data["sources"] if s.get("category") == "fees"]


# ──────────────────────────────────────────────────────────────────────
# Schema layer — every fees entry routes through the shared connector
# ──────────────────────────────────────────────────────────────────────


def test_at_least_one_fees_entry_exists() -> None:
    """Sanity check — guards against accidentally deleting every fees row."""
    entries = _load_fees_entries()
    assert len(entries) >= 20, (
        f"expected ≥20 fees-category entries in coverage/sources.yaml, "
        f"found {len(entries)}. Did the four-category rollout regress?"
    )


def test_every_fees_entry_uses_shared_connector_module() -> None:
    """Every fees entry must route through ``patent_client_agents.fees``.

    The shared module is the single chokepoint where ``_fees_provenance``
    stamps ``effective_date`` on the envelope. If a new fees connector
    lands under a different module, that connector needs its own
    envelope-compliance test — fail loud here so we don't silently lose
    the contract.
    """
    entries = _load_fees_entries()
    offenders = [
        e["id"]
        for e in entries
        if (e.get("connector") or {}).get("module") != "patent_client_agents.fees"
    ]
    assert not offenders, (
        f"fees-category entries not routing through patent_client_agents.fees: "
        f"{offenders}. Either move them onto the shared connector or add a "
        f"dedicated envelope-compliance test asserting Provenance.effective_date "
        f"is set on every response."
    )


# ──────────────────────────────────────────────────────────────────────
# Behavioral layer — the shared helper stamps effective_date
# ──────────────────────────────────────────────────────────────────────


def _synthetic_schedule() -> FeeSchedule:
    return FeeSchedule(
        jurisdiction="US",
        issuing_body="U.S. Patent and Trademark Office",
        office_code="USPTO",
        right=RightType.patent,
        currency="USD",
        effective_date=KNOWN_EFFECTIVE_DATE,
        source_url="https://www.uspto.gov/fees",
        retrieved_at=date(2026, 5, 20),
        fees=[
            FeeItem(
                code="1011",
                label="Basic filing fee - Utility",
                category=FeeCategory.filing,
                rights=[RightType.patent],
                amount=Decimal("350"),
                currency="USD",
                tier=EntityTier.large,
            ),
        ],
    )


@pytest.fixture
def patched_uspto_dispatch():
    """Replace the live USPTO scraper with one returning the synthetic schedule."""

    async def _fake_scraper() -> FeeSchedule:
        return _synthetic_schedule()

    with patch.dict(
        registry._DISPATCH,
        {("USPTO", RightType.patent): _fake_scraper},
    ):
        yield


def test_fees_provenance_helper_stamps_effective_date() -> None:
    """Direct unit test on the chokepoint."""
    schedule = _synthetic_schedule()
    prov: Provenance = _fees_provenance(schedule, schedule.source_url)

    assert prov.effective_date == KNOWN_EFFECTIVE_DATE, (
        f"Provenance.effective_date must be the schedule's effective_date "
        f"(got {prov.effective_date!r}). CONNECTOR_STANDARDS.md §3a contract."
    )
    # The legacy corpus_version="snapshot-..." hack is gone — fees aren't
    # a corpus. Guard against it sneaking back in.
    assert prov.corpus_version is None, (
        f"fees Provenance must not set corpus_version (legacy hack); "
        f"got {prov.corpus_version!r}. Use effective_date instead."
    )
    assert prov.corpus_synced_at is None, (
        f"fees Provenance must not set corpus_synced_at (fees aren't a "
        f"bundled corpus); got {prov.corpus_synced_at!r}."
    )


@pytest.mark.asyncio
async def test_get_fee_schedule_returns_envelope_with_effective_date(
    patched_uspto_dispatch,
) -> None:
    """End-to-end MCP-tool test — the user-facing surface carries the date."""
    envelope = await get_fee_schedule(jurisdiction="USPTO", right="patent")

    assert isinstance(envelope, ResponseEnvelope)
    assert envelope.provenance.effective_date == KNOWN_EFFECTIVE_DATE


@pytest.mark.asyncio
async def test_lookup_fee_returns_envelope_with_effective_date(
    patched_uspto_dispatch,
) -> None:
    """Same contract on the lookup surface."""
    envelope = await lookup_fee(jurisdiction="USPTO", category="filing", right="patent")

    assert isinstance(envelope, ListEnvelope)
    assert envelope.provenance.effective_date == KNOWN_EFFECTIVE_DATE

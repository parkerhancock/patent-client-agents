"""Representative provenance-contract tests by connector category.

The full MCP surface is too large to hit every tool in one test, so this
file pins the category-specific fields at the helper layer:

* registered_ip: standard provenance only
* adjudicative_records: ``as_of_status``
* substantive_law: ``corpus_synced_at`` + ``corpus_version``
* fees: covered in ``tests/fees/test_envelope_compliance.py``
"""

from __future__ import annotations

from datetime import UTC, datetime

from mcp_data_core.envelope import Provenance
from patent_client_agents.mcp.tools import epc as epc_tools
from patent_client_agents.mcp.tools.publications import _ppubs_provenance
from patent_client_agents.mcp.tools.usitc import _usitc_provenance


def test_registered_ip_provenance_has_standard_fields_only() -> None:
    """Registered-IP live proxies should not look like corpora or fees."""
    provenance: Provenance = _ppubs_provenance("/api/searches/searchWithBeFamily")

    assert provenance.source_name == "USPTO Patent Public Search (PPUBS)"
    assert provenance.source_url.endswith("/api/searches/searchWithBeFamily")
    assert provenance.connector_version != "unknown"
    assert provenance.corpus_synced_at is None
    assert provenance.corpus_version is None
    assert provenance.effective_date is None
    assert provenance.as_of_status is None


def test_adjudicative_records_provenance_carries_as_of_status() -> None:
    """Live docket/proceeding records need snapshot-status provenance."""
    provenance: Provenance = _usitc_provenance(
        "/data/investigation/337-1234",
        as_of_status="Active",
    )

    assert provenance.source_name == "U.S. International Trade Commission (USITC)"
    assert provenance.source_url.endswith("/data/investigation/337-1234")
    assert provenance.as_of_status == "Active"
    assert provenance.corpus_synced_at is None
    assert provenance.corpus_version is None
    assert provenance.effective_date is None


def test_substantive_law_provenance_carries_corpus_fields(monkeypatch) -> None:
    """Local law/guideline corpora need sync/version provenance."""
    synced_at = datetime(2026, 5, 1, tzinfo=UTC)

    monkeypatch.setattr(
        epc_tools,
        "get_corpus_status",
        lambda: {"corpus_synced_at": synced_at, "corpus_version": "2026"},
    )

    provenance: Provenance = epc_tools._epc_provenance("/en/legal/epc")

    assert provenance.source_name == "European Patent Convention"
    assert provenance.source_url.endswith("/en/legal/epc")
    assert provenance.corpus_synced_at == synced_at
    assert provenance.corpus_version == "2026"
    assert provenance.effective_date is None
    assert provenance.as_of_status is None

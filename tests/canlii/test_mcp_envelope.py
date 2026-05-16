"""Envelope-shape tests for the migrated CanLII MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + full opt-in), §5.6
(cross-references), and §5.8 (browse_* → search_* renames).

Mocks ``CanLIIClient`` at the boundary — we're testing envelope shape,
not the upstream REST API. Fakes are plain Python classes with a
``model_dump`` shim (matching the IP Australia envelope-test pattern,
which keeps ``ty`` quiet about ``populate_by_name``-driven alias
parameters that Pydantic exposes at runtime but not at the type
level).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.canlii import (
    get_canlii_case,
    get_canlii_cited_cases,
    get_canlii_cited_legislations,
    get_canlii_citing_cases,
    get_canlii_legislation,
    list_canlii_case_databases,
    list_canlii_ip_statutes,
    list_canlii_legislation_databases,
    search_canlii_cases,
    search_canlii_ip_cases,
    search_canlii_legislation,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — plain Python ``model_dump`` shim, mirroring the IP Australia
# envelope-test pattern. Pydantic ``populate_by_name`` aliases confuse
# ``ty`` (the dataclass-style signature only knows the alias name), so
# we keep these fakes outside Pydantic entirely.
# ──────────────────────────────────────────────────────────────────────


class _FakeModel:
    """Round-trip arbitrary fields via ``model_dump`` (alias-agnostic).

    Also exposes every kwarg as a regular attribute so production code
    that iterates ``response.case_databases`` or ``response.legislations``
    works against the fake without further plumbing.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._payload = kwargs
        for key, value in kwargs.items():
            # ``__setattr__`` is fine — we want both ``model_dump`` and
            # attribute access to work for the same value.
            object.__setattr__(self, key, value)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self._payload)


def _make_case_ref(case_id: str, title: str = "Acme v. Bob", db: str = "fct") -> dict[str, Any]:
    return {
        "database_id": db,
        "case_id": {"en": case_id, "fr": None},
        "title": title,
        "citation": f"2024 FC {case_id[-3:]} (CanLII)",
    }


def _make_case_list(rows: list[dict[str, Any]]) -> _FakeModel:
    return _FakeModel(cases=rows)


def _make_case_metadata(case_id: str, title: str = "Acme v. Bob") -> _FakeModel:
    return _FakeModel(
        database_id="csc-scc",
        case_id=case_id,
        url=f"http://canlii.ca/t/{case_id}",
        title=title,
        citation=f"2024 SCC {case_id[-3:]} (CanLII)",
        language="en",
        decision_date="2024-03-07",
        keywords="patent infringement",
    )


def _make_legislation_ref(lid: str, title: str = "Patent Act") -> dict[str, Any]:
    return {
        "database_id": "cas",
        "legislation_id": lid,
        "title": title,
        "citation": f"R.S.C., 1985, c. {lid[-3:].upper()}",
        "type": "STATUTE",
    }


def _make_legislation_metadata(
    lid: str, title: str = "Patent Act", repealed: str | None = None
) -> _FakeModel:
    return _FakeModel(
        legislation_id=lid,
        url=f"http://canlii.ca/t/{lid}",
        title=title,
        citation=f"R.S.C., 1985, c. {lid[-3:].upper()}",
        type="STATUTE",
        language="en",
        repealed=repealed,
        start_date="1985-01-01",
        end_date=None,
        content=[],
    )


# ──────────────────────────────────────────────────────────────────────
# §5.8 rename — browse_canlii_* deleted; search_canlii_* exposed
# ──────────────────────────────────────────────────────────────────────


def test_browse_canlii_names_were_renamed_to_search():
    """The §5.8 violations should no longer be importable."""
    from patent_client_agents.mcp.tools import canlii as canlii_module

    assert not hasattr(canlii_module, "browse_canlii_cases")
    assert not hasattr(canlii_module, "browse_canlii_legislation")
    assert hasattr(canlii_module, "search_canlii_cases")
    assert hasattr(canlii_module, "search_canlii_legislation")


def test_no_batch_tool_present():
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import canlii as canlii_module

    assert not hasattr(canlii_module, "batch_canlii_case")
    assert not hasattr(canlii_module, "batch_get_canlii_case")


# ──────────────────────────────────────────────────────────────────────
# list_canlii_case_databases / list_canlii_legislation_databases — §5.9
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_case_databases_returns_list_envelope():
    # The production code iterates ``response.case_databases`` and calls
    # ``model_dump()`` on each entry — give it both as ``_FakeModel`` instances.
    response = _FakeModel(
        case_databases=[
            _FakeModel(database_id="fct", jurisdiction="ca", name="Federal Court"),
            _FakeModel(database_id="csc-scc", jurisdiction="ca", name="Supreme Court"),
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_case_databases = AsyncMock(return_value=response)

        result = await list_canlii_case_databases()

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/caseBrowse/en/" in result.provenance.source_url
    assert len(result.items) == 2
    assert "2 courts" in result.summary or "2 " in result.summary


@pytest.mark.asyncio
async def test_list_legislation_databases_returns_list_envelope():
    response = _FakeModel(
        legislation_databases=[
            _FakeModel(
                database_id="cas",
                type="STATUTE",
                jurisdiction="ca",
                name="Federal Statutes",
            ),
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_legislation_databases = AsyncMock(return_value=response)

        result = await list_canlii_legislation_databases()

    assert isinstance(result, ListEnvelope)
    assert "/v1/legislationBrowse/en/" in result.provenance.source_url
    assert len(result.items) == 1


# ──────────────────────────────────────────────────────────────────────
# search_canlii_cases — §5.9, §5.5 lean default
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_canlii_cases_returns_lean_list_envelope_by_default():
    response = _make_case_list(
        [
            _make_case_ref("2024fc100", title="Patent Co. v. Crown"),
            _make_case_ref("2024fc101", title="Trademark Co. v. Acme"),
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(return_value=response)

        result = await search_canlii_cases(database_id="fct")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/caseBrowse/en/fct/" in result.provenance.source_url
    assert len(result.items) == 2
    # Lean projection: exactly these keys.
    assert set(result.items[0].keys()) == {"case_id", "citation", "title", "database_id"}
    assert result.items[0]["case_id"] == "2024fc100"
    assert "fct" in result.summary


@pytest.mark.asyncio
async def test_search_canlii_cases_full_true_returns_upstream_shape():
    response = _make_case_list([_make_case_ref("2024fc100")])
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(return_value=response)

        result = await search_canlii_cases(database_id="fct", full=True)

    # Full mode preserves the upstream nested case_id object.
    assert isinstance(result.items[0]["case_id"], dict)
    assert result.items[0]["case_id"]["en"] == "2024fc100"


@pytest.mark.asyncio
async def test_search_canlii_cases_more_available_when_page_full():
    # When the upstream returns exactly result_count rows, more_available=True.
    response = _make_case_list([_make_case_ref(f"2024fc{i:03d}") for i in range(3)])
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(return_value=response)

        result = await search_canlii_cases(database_id="fct", result_count=3)

    assert result.more_available is True


# ──────────────────────────────────────────────────────────────────────
# get_canlii_case — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_canlii_case_single_returns_list_envelope():
    record = _make_case_metadata("2008scc9", title="Dunsmuir v. New Brunswick")
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_case = AsyncMock(return_value=record)

        result = await get_canlii_case(database_id="csc-scc", case_id="2008scc9")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/caseBrowse/en/csc-scc/2008scc9/" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["case_id"] == "2008scc9"
    assert "2008scc9" in result.summary
    assert "Dunsmuir" in result.summary


@pytest.mark.asyncio
async def test_get_canlii_case_list_preserves_order():
    ids = ["2008scc9", "2020fca100", "2024fc77"]
    records = [_make_case_metadata(cid, title=f"Case {cid}") for cid in ids]
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_case = AsyncMock(side_effect=records)

        result = await get_canlii_case(database_id="csc-scc", case_id=ids)

    assert isinstance(result, ListEnvelope)
    assert [r["case_id"] for r in result.items] == ids
    # Multi-record summary lists the IDs.
    assert "Fetched 3" in result.summary
    for cid in ids:
        assert cid in result.summary
    # Multi-record path is the database root, not a specific case.
    assert result.provenance.source_url.endswith("/v1/caseBrowse/en/csc-scc/")


@pytest.mark.asyncio
async def test_get_canlii_case_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one case_id"):
        await get_canlii_case(database_id="csc-scc", case_id=[])


# ──────────────────────────────────────────────────────────────────────
# Citator tools — §5.9, §5.6 cross-refs
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_canlii_cited_cases_returns_list_envelope():
    response = _FakeModel(cited_cases=[_make_case_ref("2020fc1"), _make_case_ref("2021fc2")])
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_cited_cases = AsyncMock(return_value=response)

        result = await get_canlii_cited_cases(database_id="csc-scc", case_id="2008scc9")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/caseCitator/en/csc-scc/2008scc9/citedCases" in result.provenance.source_url
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {"case_id", "citation", "title", "database_id"}
    assert "2008scc9" in result.summary
    assert "cites 2 case" in result.summary


@pytest.mark.asyncio
async def test_get_canlii_citing_cases_returns_list_envelope():
    response = _FakeModel(citing_cases=[_make_case_ref("2024fc1")])
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_citing_cases = AsyncMock(return_value=response)

        result = await get_canlii_citing_cases(database_id="csc-scc", case_id="2008scc9")

    assert isinstance(result, ListEnvelope)
    assert "/citingCases" in result.provenance.source_url
    assert len(result.items) == 1
    assert "cite case `2008scc9`" in result.summary


@pytest.mark.asyncio
async def test_get_canlii_cited_legislations_returns_list_envelope():
    response = _FakeModel(
        cited_legislations=[
            {
                "database_id": "cas",
                "legislation_id": "rsc-1985-c-p-4",
                "title": "Patent Act",
                "citation": "R.S.C., 1985, c. P-4",
                "type": "STATUTE",
            },
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_cited_legislations = AsyncMock(return_value=response)

        result = await get_canlii_cited_legislations(database_id="csc-scc", case_id="2008scc9")

    assert isinstance(result, ListEnvelope)
    assert "/citedLegislations" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["legislation_id"] == "rsc-1985-c-p-4"
    # Lean projection on legislation references.
    assert set(result.items[0].keys()) == {
        "legislation_id",
        "title",
        "citation",
        "type",
        "database_id",
    }


# ──────────────────────────────────────────────────────────────────────
# search_canlii_legislation — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_canlii_legislation_returns_lean_list_envelope_by_default():
    response = _FakeModel(
        legislations=[
            _make_legislation_ref("rsc-1985-c-p-4", title="Patent Act"),
            _make_legislation_ref("rsc-1985-c-t-13", title="Trade-marks Act"),
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_legislation = AsyncMock(return_value=response)

        result = await search_canlii_legislation(database_id="cas")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/legislationBrowse/en/cas/" in result.provenance.source_url
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {
        "legislation_id",
        "title",
        "citation",
        "type",
        "database_id",
    }
    assert result.items[0]["legislation_id"] == "rsc-1985-c-p-4"


# ──────────────────────────────────────────────────────────────────────
# get_canlii_legislation — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_canlii_legislation_single_returns_list_envelope():
    record = _make_legislation_metadata("rsc-1985-c-p-4", title="Patent Act")
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_legislation = AsyncMock(return_value=record)

        result = await get_canlii_legislation(database_id="cas", legislation_id="rsc-1985-c-p-4")

    assert isinstance(result, ListEnvelope)
    assert "/v1/legislationBrowse/en/cas/rsc-1985-c-p-4/" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["legislation_id"] == "rsc-1985-c-p-4"
    assert "rsc-1985-c-p-4" in result.summary
    assert "Patent Act" in result.summary


@pytest.mark.asyncio
async def test_get_canlii_legislation_list_preserves_order():
    ids = ["rsc-1985-c-p-4", "rsc-1985-c-t-13", "rsc-1985-c-c-42"]
    records = [_make_legislation_metadata(lid, title=f"Act {lid}") for lid in ids]
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_legislation = AsyncMock(side_effect=records)

        result = await get_canlii_legislation(database_id="cas", legislation_id=ids)

    assert isinstance(result, ListEnvelope)
    assert [r["legislation_id"] for r in result.items] == ids
    assert "Fetched 3" in result.summary
    for lid in ids:
        assert lid in result.summary
    assert result.provenance.source_url.endswith("/v1/legislationBrowse/en/cas/")


@pytest.mark.asyncio
async def test_get_canlii_legislation_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one legislation_id"):
        await get_canlii_legislation(database_id="cas", legislation_id=[])


# ──────────────────────────────────────────────────────────────────────
# search_canlii_ip_cases — IP-filtered convenience tool
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_canlii_ip_cases_filters_general_courts_by_keywords():
    """FC / FCA / SCC rows must mention an IP-rights keyword in the title.

    Mock the upstream so each database returns three rows; only the IP-
    titled rows survive the post-filter for general courts. Tribunal
    databases pass everything through.
    """

    def _per_db_rows(db: str) -> list[dict]:
        # Each db returns a "patent" hit, a "trademark" hit, and a non-IP hit.
        return [
            _make_case_ref(f"{db}1", title="Acme v. Crown re: patent of invention"),
            _make_case_ref(f"{db}2", title="Trademark Co. v. Foo (Trade-mark dispute)"),
            _make_case_ref(f"{db}3", title="Smith v. Crown (Tax Court appeal)"),
        ]

    call_dbs: list[str] = []

    async def _fake_browse(**kwargs: Any) -> _FakeModel:
        db = kwargs["database_id"]
        call_dbs.append(db)
        return _make_case_list(_per_db_rows(db))

    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(side_effect=_fake_browse)

        result = await search_canlii_ip_cases(rights=["patent", "trademark"])

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    # All 5 default databases queried.
    assert sorted(call_dbs) == sorted(["tmob-comc", "cab-cab", "fct", "fca", "csc-scc"])
    # Each general court (3) → 2 IP-titled rows; each tribunal (2) → 3
    # rows (tribunals pass everything through). Total = 3*2 + 2*3 = 12.
    assert len(result.items) == 12
    # Every surviving hit carries a ``rights`` tag.
    for hit in result.items:
        assert hit["rights"]
        assert set(hit["rights"]).issubset({"patent", "trademark"})


@pytest.mark.asyncio
async def test_search_canlii_ip_cases_tribunal_only_when_in_scope():
    """When ``rights=['copyright']``, both tribunals should drop out.

    TMOB defaults to ``trademark``; PAB defaults to ``patent``. Neither
    intersects ``['copyright']``, so the tribunal rows should all be
    skipped. General courts contribute zero "copyright"-titled rows in
    this fixture, so total is 0.
    """

    async def _fake_browse(**kwargs: Any) -> _FakeModel:
        return _make_case_list([_make_case_ref("x1", title="Acme v. Crown (Tax Court appeal)")])

    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(side_effect=_fake_browse)

        result = await search_canlii_ip_cases(rights=["copyright"])

    assert len(result.items) == 0


@pytest.mark.asyncio
async def test_search_canlii_ip_cases_custom_databases_and_french():
    """Caller-supplied ``databases`` and ``language='fr'`` round-trip."""

    async def _fake_browse(**kwargs: Any) -> _FakeModel:
        assert kwargs["language"] == "fr"
        return _make_case_list(
            [
                _make_case_ref(
                    "fc1",
                    title="Acme c. Couronne en matière de brevet d'invention",
                )
            ]
        )

    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(side_effect=_fake_browse)

        result = await search_canlii_ip_cases(rights=["patent"], databases=["fct"], language="fr")

    assert len(result.items) == 1
    # FR keyword 'brevet' must have matched.
    assert "patent" in result.items[0]["rights"]
    assert "/v1/caseBrowse/fr/" in result.provenance.source_url


@pytest.mark.asyncio
async def test_search_canlii_ip_cases_rejects_unknown_right():
    with pytest.raises(ValidationError, match="unknown IP right"):
        await search_canlii_ip_cases(rights=["telephone"])


@pytest.mark.asyncio
async def test_search_canlii_ip_cases_rejects_bad_result_count():
    with pytest.raises(ValidationError, match="result_count"):
        await search_canlii_ip_cases(result_count=0)
    with pytest.raises(ValidationError, match="result_count"):
        await search_canlii_ip_cases(result_count=10_001)


@pytest.mark.asyncio
async def test_search_canlii_ip_cases_pab_tagged_as_patent_when_only_patent_requested():
    """Bare PAB titles (no keywords) should fall back to the tribunal's intrinsic right."""

    async def _fake_browse(**kwargs: Any) -> _FakeModel:
        if kwargs["database_id"] == "cab-cab":
            return _make_case_list([_make_case_ref("pab1", title="In Re Application No. 2019-001")])
        # All other dbs return nothing IP-flavored.
        return _make_case_list([])

    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(side_effect=_fake_browse)

        result = await search_canlii_ip_cases(rights=["patent"])

    assert len(result.items) == 1
    assert result.items[0]["rights"] == ["patent"]


# ──────────────────────────────────────────────────────────────────────
# list_canlii_ip_statutes — closed-vocabulary IP statute catalog
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_canlii_ip_statutes_returns_four_acts():
    result = await list_canlii_ip_statutes()

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/legislationBrowse/en/cas/" in result.provenance.source_url
    rights = {item["right"] for item in result.items}
    assert rights == {"patent_act", "trademarks_act", "industrial_design_act", "copyright_act"}
    legislation_ids = {item["legislation_id"] for item in result.items}
    assert legislation_ids == {
        "rsc-1985-c-p-4",
        "rsc-1985-c-t-13",
        "rsc-1985-c-i-9",
        "rsc-1985-c-c-42",
    }
    # Every entry routes through the federal-statutes database.
    assert {item["database_id"] for item in result.items} == {"cas"}


@pytest.mark.asyncio
async def test_list_canlii_ip_statutes_threads_french_language():
    result = await list_canlii_ip_statutes(language="fr")
    assert "/v1/legislationBrowse/fr/cas/" in result.provenance.source_url
    for item in result.items:
        assert item["language"] == "fr"


# ──────────────────────────────────────────────────────────────────────
# Module-level constants — IP database curation
# ──────────────────────────────────────────────────────────────────────


def test_module_exposes_ip_database_constants():
    from patent_client_agents.mcp.tools import canlii as canlii_module

    assert canlii_module.CANLII_IP_TRIBUNALS == ("tmob-comc", "cab-cab")
    assert canlii_module.CANLII_IP_REVIEWING_COURTS == ("fct", "fca", "csc-scc")
    assert set(canlii_module.CANLII_IP_DATABASES) == {
        "tmob-comc",
        "cab-cab",
        "fct",
        "fca",
        "csc-scc",
    }
    assert canlii_module.CANLII_IP_STATUTES["patent_act"] == "rsc-1985-c-p-4"
    assert canlii_module.CANLII_IP_STATUTES["industrial_design_act"] == "rsc-1985-c-i-9"
    assert canlii_module.CANLII_IP_STATUTES["copyright_act"] == "rsc-1985-c-c-42"


def test_matches_ip_rights_helper_substring_logic():
    """The keyword filter is substring-match against the lowercased title."""
    from patent_client_agents.mcp.tools.canlii import _matches_ip_rights

    assert _matches_ip_rights("Acme v. Crown re Patent of Invention", ("patent",))
    assert _matches_ip_rights("Trade-mark opposition", ("trademark",))
    assert _matches_ip_rights("Trademark Co. v. Acme", ("trademark",))
    assert _matches_ip_rights("Droit d'auteur opposition", ("copyright",))
    assert _matches_ip_rights("Dessin industriel - opposition", ("design",))
    assert not _matches_ip_rights("Tax appeal — capital gains", ("patent",))
    assert not _matches_ip_rights(None, ("patent",))
    assert not _matches_ip_rights("", ("patent",))

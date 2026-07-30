"""Unit tests for ``patent_client_agents.canlii.client``.

Uses ``httpx.MockTransport`` rather than VCR cassettes because the CanLII
API requires a personal API key, which makes recording brittle for
contributors who don't have one yet. The tests assert on URL shape, query
parameter injection, and model parsing against canonical response bodies
that mirror the ones in the upstream CanLII README.

When we obtain a key and want live coverage, port these to VCR cassettes
following the pattern in ``tests/cpc/`` or ``tests/mpep/``.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from mcp_data_core.exceptions import ApiError, ConfigurationError
from patent_client_agents.canlii import (
    CanLIIClient,
    GetCaseInput,
    GetCitatorInput,
    GetLegislationInput,
    LegislationType,
)

CASE_DATABASES_PAYLOAD = {
    "caseDatabases": [
        {"databaseId": "oncicb", "jurisdiction": "on", "name": "Criminal Injuries"},
        {"databaseId": "tmob-comc", "jurisdiction": "ca", "name": "TMOB"},
    ],
}

BROWSE_CASES_PAYLOAD = {
    "cases": [
        {
            "databaseId": "fct",
            "caseId": {"en": "2024fc123"},
            "title": "Acme v. Bob",
            "citation": "2024 FC 123 (CanLII)",
        },
    ],
}

DUNSMUIR_PAYLOAD = {
    "databaseId": "csc-scc",
    "caseId": "2008scc9",
    "url": "http://canlii.ca/t/1vxsm",
    "title": "Dunsmuir v. New Brunswick",
    "citation": "[2008] 1 SCR 190, 2008 SCC 9 (CanLII)",
    "language": "en",
    "docketNumber": "31459",
    "decisionDate": "2008-03-07",
    "keywords": "adjudicator — review",
    "concatenatedId": "2008csc-scc9",
}

CITED_CASES_PAYLOAD = {
    "citedCases": [
        {
            "databaseId": "onca",
            "caseId": {"en": "1998canlii2237"},
            "title": "Alper Dev v. Harrowston",
            "citation": "1998 CanLII 2237 (ON CA)",
        },
    ],
}

LEGISLATION_DATABASES_PAYLOAD = {
    "legislationDatabases": [
        {"databaseId": "cas", "type": "STATUTE", "jurisdiction": "ca", "name": "Federal Statutes"},
        {"databaseId": "car", "type": "REGULATION", "jurisdiction": "ca", "name": "Federal Regs"},
    ],
}

BROWSE_LEGISLATION_PAYLOAD = {
    "legislations": [
        {
            "databaseId": "cas",
            "legislationId": "rsc-1985-c-p-4",
            "title": "Patent Act",
            "citation": "RSC 1985, c P-4",
            "type": "STATUTE",
        },
    ],
}

LEGISLATION_METADATA_PAYLOAD = {
    "legislationId": "rsc-1985-c-p-4",
    "url": "http://canlii.ca/t/52z3z",
    "title": "Patent Act",
    "citation": "RSC 1985, c P-4",
    "type": "STATUTE",
    "language": "en",
    "dateScheme": "ENTRY_INTO_FORCE",
    "startDate": "1985-12-31",
    "endDate": None,
    "repealed": "NO",
    "content": [{"partId": "1", "partName": "Main"}],
}


def _mock_client(handler) -> CanLIIClient:
    """Build a ``CanLIIClient`` wired to a ``MockTransport`` handler."""
    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return CanLIIClient(api_key="test-key", client=transport_client)


class TestConfiguration:
    def test_missing_api_key_raises_configuration_error(self, monkeypatch) -> None:
        monkeypatch.delenv("CANLII_API_KEY", raising=False)
        with pytest.raises(ConfigurationError):
            CanLIIClient()

    def test_env_var_is_picked_up(self, monkeypatch) -> None:
        monkeypatch.setenv("CANLII_API_KEY", "from-env")
        client = CanLIIClient()
        assert client._api_key == "from-env"


class TestCases:
    @pytest.mark.asyncio
    async def test_list_case_databases(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=CASE_DATABASES_PAYLOAD)

        async with _mock_client(handler) as client:
            result = await client.list_case_databases()

        assert len(captured) == 1
        assert captured[0].url.path.endswith("/caseBrowse/en/")
        assert captured[0].url.params["api_key"] == "test-key"
        assert [db.database_id for db in result.case_databases] == ["oncicb", "tmob-comc"]

    @pytest.mark.asyncio
    async def test_browse_cases_injects_date_filters(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=BROWSE_CASES_PAYLOAD)

        async with _mock_client(handler) as client:
            result = await client.browse_cases(
                database_id="fct",
                offset=0,
                result_count=20,
                published_after="2024-01-01",
            )

        req = captured[0]
        assert req.url.path == "/v1/caseBrowse/en/fct/"
        params = req.url.params
        assert params["offset"] == "0"
        assert params["resultCount"] == "20"
        assert params["publishedAfter"] == "2024-01-01"
        # Unspecified filters must NOT be present (None values stripped).
        assert "publishedBefore" not in params
        assert result.cases[0].case_id.en == "2024fc123"

    @pytest.mark.asyncio
    async def test_browse_cases_rejects_oversized_page(self) -> None:
        async with _mock_client(lambda r: httpx.Response(200, json={"cases": []})) as client:
            with pytest.raises(ValueError, match="result_count"):
                await client.browse_cases(database_id="fct", result_count=10_001)

    @pytest.mark.asyncio
    async def test_get_case_parses_dunsmuir(self) -> None:
        async with _mock_client(lambda r: httpx.Response(200, json=DUNSMUIR_PAYLOAD)) as client:
            case = await client.get_case(database_id="csc-scc", case_id="2008scc9")

        assert case.case_id == "2008scc9"
        assert case.decision_date == date(2008, 3, 7)
        assert case.docket_number == "31459"
        assert case.concatenated_id == "2008csc-scc9"


class TestCitator:
    @pytest.mark.asyncio
    async def test_get_cited_cases_uses_english_path(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=CITED_CASES_PAYLOAD)

        async with _mock_client(handler) as client:
            result = await client.get_cited_cases(database_id="onca", case_id="1999canlii1527")

        assert captured[0].url.path == "/v1/caseCitator/en/onca/1999canlii1527/citedCases"
        assert result.cited_cases[0].case_id.en == "1998canlii2237"


class TestLegislation:
    @pytest.mark.asyncio
    async def test_list_legislation_databases(self) -> None:
        async with _mock_client(
            lambda r: httpx.Response(200, json=LEGISLATION_DATABASES_PAYLOAD)
        ) as client:
            result = await client.list_legislation_databases()

        types = [db.type for db in result.legislation_databases]
        assert LegislationType.STATUTE in types
        assert LegislationType.REGULATION in types

    @pytest.mark.asyncio
    async def test_browse_legislation(self) -> None:
        async with _mock_client(
            lambda r: httpx.Response(200, json=BROWSE_LEGISLATION_PAYLOAD)
        ) as client:
            result = await client.browse_legislation(database_id="cas")
        assert result.legislations[0].legislation_id == "rsc-1985-c-p-4"
        assert result.legislations[0].type == LegislationType.STATUTE

    @pytest.mark.asyncio
    async def test_get_legislation_parses_dates_and_parts(self) -> None:
        async with _mock_client(
            lambda r: httpx.Response(200, json=LEGISLATION_METADATA_PAYLOAD)
        ) as client:
            leg = await client.get_legislation(
                database_id="cas",
                legislation_id="rsc-1985-c-p-4",
            )

        assert leg.title == "Patent Act"
        assert leg.start_date == date(1985, 12, 31)
        assert leg.repealed == "NO"
        assert leg.content[0].part_name == "Main"


class TestTooLongEnvelope:
    @pytest.mark.asyncio
    async def test_too_long_response_raises_api_error(self) -> None:
        too_long_body = {
            "contentLength": 36771905,
            "error": "TOO_LONG",
            "message": "This content is larger than 10MB.",
        }

        async with _mock_client(lambda r: httpx.Response(200, json=too_long_body)) as client:
            with pytest.raises(ApiError) as exc_info:
                await client.list_case_databases()
        assert exc_info.value.status_code == 413


class TestModuleLevelApi:
    """Smoke-test that the module-level coroutines wire up correctly."""

    @staticmethod
    def _install_factory(monkeypatch, payload: dict) -> None:
        """Install a CanLIIClient factory that returns ``payload`` for every call."""
        from patent_client_agents.canlii import api as canlii_api

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        def _factory(*args, **kwargs):
            transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            return CanLIIClient(api_key="test-key", client=transport_client)

        monkeypatch.setattr(canlii_api, "CanLIIClient", _factory)

    @pytest.mark.asyncio
    async def test_module_api_returns_models(self, monkeypatch) -> None:
        """Patch CanLIIClient inside api.py so the auto-managed lifecycle uses MockTransport."""
        from patent_client_agents.canlii import api as canlii_api

        self._install_factory(monkeypatch, DUNSMUIR_PAYLOAD)

        case = await canlii_api.get_case(GetCaseInput(database_id="csc-scc", case_id="2008scc9"))
        assert case.title == "Dunsmuir v. New Brunswick"

    @pytest.mark.asyncio
    async def test_get_citator_input_threads_through(self, monkeypatch) -> None:
        from patent_client_agents.canlii import api as canlii_api

        self._install_factory(monkeypatch, CITED_CASES_PAYLOAD)

        result = await canlii_api.get_cited_cases(
            GetCitatorInput(database_id="onca", case_id="1999canlii1527")
        )
        assert len(result.cited_cases) == 1

    @pytest.mark.asyncio
    async def test_get_legislation_input_threads_through(self, monkeypatch) -> None:
        from patent_client_agents.canlii import api as canlii_api

        self._install_factory(monkeypatch, LEGISLATION_METADATA_PAYLOAD)

        leg = await canlii_api.get_legislation(
            GetLegislationInput(database_id="cas", legislation_id="rsc-1985-c-p-4")
        )
        assert leg.title == "Patent Act"

    # ------------------------------------------------------------------
    # Coverage for the remaining module-level coroutines. Each is a thin
    # wrapper around an upstream method already validated by TestCases /
    # TestCitator / TestLegislation; the assertions here are intentionally
    # minimal — we just need to execute the factory + dispatch path.
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_case_databases_module_api(self, monkeypatch) -> None:
        from patent_client_agents.canlii import api as canlii_api

        self._install_factory(monkeypatch, CASE_DATABASES_PAYLOAD)
        result = await canlii_api.list_case_databases()
        assert len(result.case_databases) == 2

    @pytest.mark.asyncio
    async def test_browse_cases_module_api(self, monkeypatch) -> None:
        from patent_client_agents.canlii import api as canlii_api
        from patent_client_agents.canlii.api import BrowseCasesInput

        self._install_factory(monkeypatch, BROWSE_CASES_PAYLOAD)
        result = await canlii_api.browse_cases(BrowseCasesInput(database_id="fct", result_count=10))
        assert len(result.cases) == 1

    @pytest.mark.asyncio
    async def test_get_citing_cases_module_api(self, monkeypatch) -> None:
        from patent_client_agents.canlii import api as canlii_api

        self._install_factory(monkeypatch, {"citingCases": CITED_CASES_PAYLOAD["citedCases"]})
        result = await canlii_api.get_citing_cases(
            GetCitatorInput(database_id="onca", case_id="1999canlii1527")
        )
        assert len(result.citing_cases) == 1

    @pytest.mark.asyncio
    async def test_get_cited_legislations_module_api(self, monkeypatch) -> None:
        from patent_client_agents.canlii import api as canlii_api

        cited_legs_payload = {
            "citedLegislations": [
                {
                    "databaseId": "cas",
                    "legislationId": "rsc-1985-c-p-4",
                    "title": "Patent Act",
                    "citation": "R.S.C., 1985, c. P-4",
                    "type": "STATUTE",
                }
            ]
        }
        self._install_factory(monkeypatch, cited_legs_payload)
        result = await canlii_api.get_cited_legislations(
            GetCitatorInput(database_id="onca", case_id="1999canlii1527")
        )
        assert len(result.cited_legislations) == 1

    @pytest.mark.asyncio
    async def test_list_legislation_databases_module_api(self, monkeypatch) -> None:
        from patent_client_agents.canlii import api as canlii_api

        self._install_factory(monkeypatch, LEGISLATION_DATABASES_PAYLOAD)
        result = await canlii_api.list_legislation_databases()
        assert len(result.legislation_databases) == 2

    @pytest.mark.asyncio
    async def test_browse_legislation_module_api(self, monkeypatch) -> None:
        from patent_client_agents.canlii import api as canlii_api
        from patent_client_agents.canlii.api import BrowseLegislationInput

        self._install_factory(monkeypatch, BROWSE_LEGISLATION_PAYLOAD)
        result = await canlii_api.browse_legislation(BrowseLegislationInput(database_id="cas"))
        assert result.legislations[0].legislation_id == "rsc-1985-c-p-4"

    def test_get_client_returns_canlii_client(self, monkeypatch) -> None:
        from patent_client_agents.canlii import api as canlii_api

        monkeypatch.setenv("CANLII_API_KEY", "k")
        client = canlii_api.get_client()
        assert isinstance(client, CanLIIClient)

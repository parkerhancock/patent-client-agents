"""Offline request-contract tests for the Federal Court connector."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from patent_client_agents.canada_federal_court import CanadaFederalCourtClient


def _case_row(*, court_number: str = "T-2962-24", nature: str = "Patent Infringement") -> dict:
    return {
        "COURT_NO": court_number,
        "COURT_SEQ": "2024302962",
        "STYLE_OF_CAUSE": "PFIZER CANADA ULC v. TARO PHARMACEUTICALS INC.",
        "NATURE_CD": "C22",
        "ENGLISH_NATURE_DESC": nature,
        "FRENCH_NATURE_DESC": "Brevet - Contrefaçon" if "Patent" in nature else "Amirauté",
        "DIVISION": "T",
        "FILE_DT": "/Date(1730406718000)/",
        "OFF_CD": "TOR",
        "ENGLISH_CITY_NAME": "Toronto",
        "FRENCH_CITY_NAME": "Toronto",
        "PRCDG_TYPE": "T",
        "ENGLISH_PROCEEDING_TYPE": "Federal Court",
        "FRENCH_PROCEEDING_TYPE": "Cour fédérale",
        "PROCEEDING_CLASS_ID": 2.0,
        "ENGLISH_PROCEEDING_CLASS": "Ordinary",
        "FRENCH_PROCEEDING_CLASS": "Ordinaire",
        "LANG_CD": "E",
        "ENGLISH_LANGUAGE_NAME": "English",
        "FRENCH_LANGUAGE_NAME": "Anglais",
        "Party": ["PFIZER CANADA ULC", "TARO PHARMACEUTICALS INC"],
        "Ships": [None, None],
    }


def _docket_row(*, entry_number: int = 10, summary: str = "Defence filed") -> dict:
    return {
        "Division": "T",
        "COURT_NO": "T-2962-24",
        "STYLE_OF_CAUSE": "PFIZER CANADA ULC v. TARO PHARMACEUTICALS INC.",
        "FILING_DATE": "/Date(1730406718000)/",
        "NATURE_CD": "C22",
        "ENGLISH_NATURE_DESC": "Patent Infringement",
        "FRENCH_NATURE_DESC": "Brevet - Contrefaçon",
        "ENGLISH_TRACK_NAME": "Actions",
        "FRENCH_TRACK_NAME": "Actions",
        "ENGLISH_PROCEEDING_CLASS": "Ordinary",
        "FRENCH_PROCEEDING_CLASS": "Ordinaire",
        "ENGLISH_OFFICE_NAME": "Toronto",
        "FRENCH_OFFICE_NAME": "Toronto",
        "DOCNO": 1,
        "RE_NO": entry_number,
        "FOREMOST_NUMBER": "8645719",
        "RECORDED_ENTRY": summary,
        "DOC_DT": "2024-11-21T00:00:00",
        "CAN_PUBLISH_DOCUMENT": "Y",
        "RE_LANG_CD": "E",
        "IS_CONFIDENTIAL": "N",
        "REGISTRY_NOTES_EXTERNAL": None,
        "COMMAND_PHRASE_EN": None,
        "COMMAND_PHRASE_FR": None,
    }


def _mock_client(handler) -> CanadaFederalCourtClient:
    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return CanadaFederalCourtClient(client=transport_client)


@pytest.mark.asyncio
async def test_party_search_uses_official_endpoint_and_filters_patent_cases() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "Count": 2,
                "data": [_case_row(), _case_row(court_number="T-1-24", nature="Admiralty")],
            },
        )

    async with _mock_client(handler) as client:
        result = await client.search_party_cases("Pfizer", patent_only=True)

    assert captured[0].url.path.endswith("/ProceedingsQueriesPartyInfo")
    assert captured[0].url.params["division"] == "t"
    assert captured[0].url.params["name"] == "Pfizer"
    assert result.upstream_count == 2
    assert result.filtered_count == 1
    assert result.cases[0].court_number == "T-2962-24"
    assert result.cases[0].filed_date == date(2024, 10, 31)


@pytest.mark.asyncio
async def test_party_search_with_dates_uses_date_endpoint() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"Count": 0, "data": []})

    async with _mock_client(handler) as client:
        await client.search_party_cases(
            "Acme",
            filed_from=date(2024, 1, 1),
            filed_to=date(2024, 12, 31),
        )

    request = captured[0]
    assert request.url.path.endswith("/ProceedingsQueriesPartyInfoDates")
    assert request.url.params["from"] == "01-01-2024"
    assert request.url.params["to"] == "12-31-2024"


@pytest.mark.asyncio
async def test_get_case_fans_out_to_metadata_parties_ip_and_related_cases() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("proceedingQueriesAddInfo"):
            return httpx.Response(200, json={"Count": 1, "data": [_case_row()]})
        if request.url.path.endswith("PublicPartiesListInfo"):
            return httpx.Response(
                200,
                json={
                    "Count": 1,
                    "data": [
                        {
                            "PARTY_NAME": "PFIZER CANADA ULC",
                            "SOLCTR_FIRM": "Norton Rose Fulbright Canada",
                            "SOLCTR_CONTACT": "COUNSEL, TEST",
                        }
                    ],
                },
            )
        if request.url.path.endswith("PartyInfoIntlProp"):
            return httpx.Response(
                200,
                json={
                    "Count": 1,
                    "data": [{"INT_PROPERTY_TITLE": "BOSULIF", "INT_PROPERTY_NUMBER": 2688467.0}],
                },
            )
        return httpx.Response(200, json={"Count": 0, "data": []})

    async with _mock_client(handler) as client:
        result = await client.get_case("t-2962-24")

    assert len(paths) == 4
    assert result.case.court_number == "T-2962-24"
    assert result.parties[0].solicitor_firm == "Norton Rose Fulbright Canada"
    assert result.intellectual_property[0].number == "2688467"


@pytest.mark.asyncio
async def test_docket_entries_include_download_url_and_inferred_status() -> None:
    rows = [
        _docket_row(entry_number=11, summary="Notice of Discontinuance filed"),
        _docket_row(entry_number=10),
    ]

    async with _mock_client(
        lambda request: httpx.Response(200, json={"Count": len(rows), "data": rows})
    ) as client:
        result = await client.list_docket_entries("T-2962-24")

    assert result.status.assessment == "likely_closed"
    assert result.status.inferred is True
    assert result.total_count == 2
    assert result.entries[0].entry_number == 11
    assert "downloadFileFromAlfresco" in (result.entries[0].download_url or "")


@pytest.mark.asyncio
async def test_search_rejects_one_sided_date_range() -> None:
    async with _mock_client(
        lambda request: httpx.Response(200, json={"Count": 0, "data": []})
    ) as client:
        with pytest.raises(ValueError, match="supplied together"):
            await client.search_party_cases("Acme", filed_from=date(2024, 1, 1))

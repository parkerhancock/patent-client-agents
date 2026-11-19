"""MCP tools for the ODP release 5.0/5.1 endpoints.

The tools run against a real ``UsptoOdpClient`` over an ``httpx2.MockTransport``
that answers by request path, so each test covers the tool's request, the
client's parsing, and the envelope the caller sees. Payloads are trimmed
copies of live responses recorded 2026-11-19.
"""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from mcp_data_core.exceptions import NotFoundError
from patent_client_agents.mcp.tools import office_actions as oa_tools
from patent_client_agents.mcp.tools import uspto as uspto_tools
from patent_client_agents.uspto_odp import UsptoOdpClient

API = "/api/v1"
NOT_FOUND = httpx2.Response(404, json={"code": 404, "error": "Not Found"})

OFFICE_ACTION = {
    "officeActionRecordIdentifier": "59a95b2cc615208718119d84c780952b",
    "applicationNumberText": "16123456",
    "patentNumber": "10902286",
    "inventionTitle": "LEARNING ASSISTANCE DEVICE",
    "documentCode": "CTNF",
    "documentCodeDescriptionText": "Non-Final Rejection",
    "submissionDate": "2020-03-27",
    "groupArtUnitNumber": 2641,
    "rejectionTypeBag": ["102", "DoublePatent"],
}

EXPUNGEMENT = {
    "documentIdentifier": "053f05b8",
    "decisionProceedingCategory": "ExpungReexam",
    "proceedingTypeCategory": "EXPUNGEMENT",
    "documentTypeDescriptionText": "NOTICE OF INSTITUTION / OFFICE ACTION ISSUED - EXPUNGEMENT",
    "decisionActionDate": "2026-11-17",
    "serialNumber": 79295732,
    "registrationNumber": 6458316,
    "markLiteralText": "NEOWISE",
    "registrantName": "Shanghai Flexiv Robotics Technology Co., Ltd.",
    "petitionerName": "Tutunjian & Bitetto, P.C.",
    "documentURI": "https://tsdr.uspto.gov/#caseNumber=79295732",
    "ocrSearchText": "Petition for Expungement or Reexamination form ...",
}

SHOW_CAUSE = {
    "documentIdentifier": "66371dda",
    "decisionProceedingCategory": "Administrative",
    "documentTypeDescriptionText": "Show-cause",
    "decisionActionDate": "2026-11-18",
    "partyName": "In re Patent and Trademark Office, LLC et al.",
    "fileName": "Show Cause Order.pdf",
    "fileDownloadURI": (
        "https://api.uspto.gov/api/v1/trademark/decision-proceeding/file/"
        "proceedings-decisions/66371dda.pdf"
    ),
    "ocrSearchText": "To: Patent & Trademark Office, LLC ...",
}


class FakeOdp:
    """Routes requests by path suffix to canned replies and records them."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        reply = self.routes.get(request.url.path.removeprefix(API), NOT_FOUND)
        if isinstance(reply, httpx2.Response):
            return reply
        if isinstance(reply, bytes):
            return httpx2.Response(200, content=reply)
        return httpx2.Response(200, json=reply)

    def body(self, index: int = -1) -> dict[str, Any]:
        return json.loads(self.requests[index].content)

    def client(self) -> UsptoOdpClient:
        http = httpx2.AsyncClient(transport=httpx2.MockTransport(self.handle))
        return UsptoOdpClient(api_key="test-key", client=http)


@pytest.fixture
def odp(monkeypatch: pytest.MonkeyPatch) -> FakeOdp:
    fake = FakeOdp({})
    monkeypatch.setattr(uspto_tools, "UsptoOdpClient", fake.client)
    monkeypatch.setattr(oa_tools, "UsptoOdpClient", fake.client)
    return fake


# ─────────────────────────── office action full text ──────────────────────


async def test_search_office_action_full_text_returns_lean_stubs(odp: FakeOdp) -> None:
    odp.routes["/patent/office-action/search"] = {
        "count": 4584,
        "officeActionDataBag": [OFFICE_ACTION],
    }

    result = await oa_tools.search_office_action_full_text(
        query='officeActionText:"abstract idea"', limit=1, offset=10
    )

    sent = odp.body()
    assert sent["q"] == 'officeActionText:"abstract idea"'
    assert sent["pagination"] == {"offset": 10, "limit": 1}
    assert "officeActionText" not in sent["fields"]  # stubs must not pull body text
    assert result.items == [
        {
            "document_identifier": "59a95b2cc615208718119d84c780952b",
            "application_number": "16123456",
            "patent_number": "10902286",
            "mail_date": "2020-03-27",
            "document_code": "CTNF",
            "document_description": "Non-Final Rejection",
            "rejection_types": ["102", "DoublePatent"],
            "invention_title": "LEARNING ASSISTANCE DEVICE",
            "art_unit": "2641",
        }
    ]
    assert result.more_available is True
    assert "1 of 4584 hits" in result.summary


async def test_search_office_action_full_text_full_returns_body_text(odp: FakeOdp) -> None:
    record = {**OFFICE_ACTION, "officeActionText": "Claims 1-10 are rejected ..."}
    odp.routes["/patent/office-action/search"] = {"count": 1, "officeActionDataBag": [record]}

    result = await oa_tools.search_office_action_full_text(query="x", full=True)

    assert "fields" not in odp.body()
    assert result.items[0]["officeActionText"] == "Claims 1-10 are rejected ..."
    assert result.more_available is False


class _LegacyMiss:
    """Stand-in for the legacy office-action client that finds nothing."""

    async def __aenter__(self) -> _LegacyMiss:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def search_office_action_text(self, query: str, **kwargs: Any) -> dict[str, Any]:
        return {"num_found": 0, "results": []}


async def test_get_office_action_falls_back_to_the_search_api_identifier(
    odp: FakeOdp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(oa_tools, "OfficeActionClient", _LegacyMiss)
    doc_id = OFFICE_ACTION["officeActionRecordIdentifier"]
    record = {**OFFICE_ACTION, "officeActionText": "Claims 1-10 are rej"}  # ODP's excerpt
    whole = "Claims 1-10 are rejected under 35 U.S.C. 102 ... Conclusion ..."
    odp.routes[f"/patent/office-action/{doc_id}"] = {"count": 1, "officeActionDataBag": [record]}
    odp.routes[f"/patent/office-action/{doc_id}/download/officeActionText"] = whole.encode()

    result = await oa_tools.get_office_action(doc_id)

    assert result.items[0]["officeActionText"] == whole
    assert "application 16123456, type CTNF" in result.summary
    assert "Mailed 2020-03-27; art unit 2641" in result.summary


async def test_get_office_action_unknown_to_both_apis_is_not_found(
    odp: FakeOdp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(oa_tools, "OfficeActionClient", _LegacyMiss)

    with pytest.raises(NotFoundError, match="search_office_action_full_text"):
        await oa_tools.get_office_action("nope")


# ─────────────────────────── trademark decisions ──────────────────────────


async def test_search_trademark_decisions_returns_lean_stubs(odp: FakeOdp) -> None:
    odp.routes["/trademark/decision-proceeding/search"] = {
        "count": 7,
        "trademarkDecisionsDataBag": [EXPUNGEMENT, SHOW_CAUSE],
    }

    result = await uspto_tools.search_trademark_decisions(query="registrationNumber:6458316")

    assert odp.body() == {
        "q": "registrationNumber:6458316",
        "pagination": {"offset": 0, "limit": 25},
    }
    expungement, order = result.items
    assert expungement == {
        "document_identifier": "053f05b8",
        "category": "ExpungReexam",
        "proceeding_type": "EXPUNGEMENT",
        "document_type": "NOTICE OF INSTITUTION / OFFICE ACTION ISSUED - EXPUNGEMENT",
        "decision_date": "2026-11-17",
        "mark": "NEOWISE",
        "serial_number": "79295732",
        "registration_number": "6458316",
        "party": "Shanghai Flexiv Robotics Technology Co., Ltd.",
        "petitioner": "Tutunjian & Bitetto, P.C.",
        "petition_number": None,
        "proceeding_number": None,
        "precedential": None,
        "tsdr_url": "https://tsdr.uspto.gov/#caseNumber=79295732",
        "pdf_available": False,
    }
    assert (order["party"], order["pdf_available"]) == (SHOW_CAUSE["partyName"], True)
    assert result.more_available is True


async def test_trademark_decision_records_never_expose_the_key_gated_url(odp: FakeOdp) -> None:
    odp.routes["/trademark/decision-proceeding/search"] = {
        "count": 1,
        "trademarkDecisionsDataBag": [SHOW_CAUSE],
    }
    odp.routes["/trademark/decision-proceeding/search/66371dda"] = {
        "count": 1,
        "trademarkDecisionsDataBag": SHOW_CAUSE,
    }

    searched = await uspto_tools.search_trademark_decisions(query="sanctions", full=True)
    fetched = await uspto_tools.get_trademark_decision("66371dda")

    for record in (searched.items[0], fetched.items[0]):
        assert "fileDownloadURI" not in record
        assert record["pdf_available"] is True
        assert record["ocrSearchText"].startswith("To: Patent & Trademark Office")
    assert "Show-cause" in fetched.summary


async def test_get_trademark_decision_list_reports_missing(odp: FakeOdp) -> None:
    odp.routes["/trademark/decision-proceeding/search/053f05b8"] = {
        "count": 1,
        "trademarkDecisionsDataBag": EXPUNGEMENT,
    }

    result = await uspto_tools.get_trademark_decision(["053f05b8", "missing"])

    assert [r["markLiteralText"] for r in result.items] == ["NEOWISE"]
    assert result.not_found == ["missing"]


async def test_download_trademark_decision_fetches_the_pdf(odp: FakeOdp) -> None:
    odp.routes["/trademark/decision-proceeding/search/66371dda"] = {
        "count": 1,
        "trademarkDecisionsDataBag": SHOW_CAUSE,
    }
    odp.routes["/trademark/decision-proceeding/file/proceedings-decisions/66371dda.pdf"] = (
        b"%PDF-1.7 order"
    )

    content, filename = await uspto_tools._fetch_trademark_decision_document("66371dda")

    assert (content, filename) == (b"%PDF-1.7 order", "Show Cause Order.pdf")


async def test_download_trademark_decision_without_a_pdf_points_to_tsdr(odp: FakeOdp) -> None:
    odp.routes["/trademark/decision-proceeding/search/053f05b8"] = {
        "count": 1,
        "trademarkDecisionsDataBag": EXPUNGEMENT,
    }

    with pytest.raises(NotFoundError, match=r"no PDF.*tsdr\.uspto\.gov"):
        await uspto_tools.download_trademark_decision("053f05b8")


# ───────────────────── status codes and application sections ──────────────


async def test_search_application_status_codes(odp: FakeOdp) -> None:
    odp.routes["/patent/status-codes"] = {
        "count": 2,
        "statusCodeBag": [
            {"applicationStatusCode": 150, "applicationStatusDescriptionText": "Patented Case"}
        ],
    }

    result = await uspto_tools.search_application_status_codes(query="Patented", limit=1)

    assert result.items == [{"status_code": 150, "description": "Patented Case"}]
    assert result.more_available is True


async def test_get_application_section_fetches_only_that_section(odp: FakeOdp) -> None:
    events = [{"eventCode": "MN/=.", "eventDate": "2021-01-06"}]
    odp.routes["/patent/applications/16123456/transactions"] = {
        "count": 1,
        "patentFileWrapperDataBag": [{"applicationNumberText": "16123456", "eventDataBag": events}],
    }

    result = await uspto_tools.get_application("16/123,456", section="transactions")

    (request,) = odp.requests
    assert request.url.path == f"{API}/patent/applications/16123456/transactions"
    assert result.items[0]["patentBag"][0]["eventDataBag"] == events

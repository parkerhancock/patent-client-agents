"""ODP release 5.0/5.1 compatibility: petition changes and newly covered endpoints.

Each test drives a real ``UsptoOdpClient`` over an ``httpx2.MockTransport``.
The payloads are trimmed copies of live responses recorded 2026-11-19, so they
keep the shapes that differ from the published docs: numeric codes sent as
numbers on one endpoint and strings on another, download endpoints with their
own record keys, and the trademark get-by-identifier bag sent as one object.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from patent_client_agents.mcp.tools.uspto import _stub_petition, _summarize_petition
from patent_client_agents.uspto_odp import UsptoOdpClient

API = "https://api.uspto.gov/api/v1"

PETITION = {
    "petitionDecisionRecordIdentifier": "f21dc3e1-5583-56cd-9154-99ed746a162c",
    "applicationNumberText": "17654321",
    "decisionPetitionTypeCode": "652",
    "decisionPetitionTypeCodeDescriptionText": "Petition to withdraw holding of abandonment",
    "prosecutionStatusCode": 652,
    "prosecutionStatusCodeDescriptionText": "Abandoned",
    "decidedPetitionTypeCode": "C",
    "decidedPetitionTypeCodeDescriptionText": "DENIED",
    "decisionDate": "2026-11-17",
    "decisionMailDate": "2026-11-17",
    "finalPetitionDecisionIndicator": False,
    "applicationStatusDescriptionText": "Abandoned  --  Failure to Respond to an Office Action",
    "groupArtUnitNumber": "2641",
}

OFFICE_ACTION = {
    "officeActionRecordIdentifier": "7e0f21f01fe3bf91fc98254d4d211a51",
    "applicationNumberText": "16123456",
    "patentNumber": "10902286",
    "documentCode": "NOA",
    "documentCodeDescriptionText": "NOA",
    "submissionDate": "2020-09-23",
    "groupArtUnitNumber": 2641,
    "officeActionText": "Notice of Pre-AIA or AIA Status ...",
    "publicStatusIndicator": True,
}

TRADEMARK_DECISION = {
    "documentIdentifier": "053f05b84f8c26eb29047fd6962e637fd29dbc18a0b0cb6a589b285dcd53f5d8",
    "decisionProceedingCategory": "ExpungReexam",
    "proceedingTypeCategory": "EXPUNGEMENT",
    "serialNumber": 79295732,
    "registrationNumber": 6458316,
    "petitionNumber": "2026-105807E",
    "markLiteralText": "NEOWISE",
    "decisionActionDate": "2026-11-17",
    "fileSize": 21914,
    "precedentialIndicator": False,
}

NOT_FOUND = {"code": 404, "error": "Not Found", "errorDetails": "No records found"}


class FakeOdp:
    """Answers every request with ``reply`` and records what was asked."""

    def __init__(self, reply: Any, *, status: int = 200) -> None:
        self.reply = reply
        self.status = status
        self.requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if isinstance(self.reply, (bytes, str)):
            return httpx2.Response(self.status, text=str(self.reply))
        return httpx2.Response(self.status, json=self.reply)

    @property
    def request(self) -> httpx2.Request:
        (only,) = self.requests
        return only

    @property
    def sent(self) -> tuple[str, str, Any]:
        request = self.request
        body = json.loads(request.content) if request.content else None
        return request.method, str(request.url).removeprefix(API), body

    def client(self) -> UsptoOdpClient:
        http = httpx2.AsyncClient(transport=httpx2.MockTransport(self.handle))
        return UsptoOdpClient(api_key="test-key", client=http)


# ─────────────────────────────── petitions ───────────────────────────────


async def test_petition_search_accepts_mixed_code_types_and_new_outcome_fields() -> None:
    odp = FakeOdp({"count": 1, "petitionDecisionDataBag": [PETITION]})
    async with odp.client() as client:
        result = await client.search_petitions(q="decidedPetitionTypeCodeDescriptionText:DENIED")

    (decision,) = result.petitionDecisionDataBag
    assert (decision.prosecutionStatusCode, decision.decisionPetitionTypeCode) == ("652", 652)
    assert decision.decidedPetitionTypeCodeDescriptionText == "DENIED"
    assert decision.finalPetitionDecisionIndicator is False


async def test_petition_download_reads_the_download_record_key() -> None:
    odp = FakeOdp({"petitionDecisionData": [PETITION, PETITION]})
    async with odp.client() as client:
        result = await client.download_petitions(q="x", file_format="json")

    assert result.count == 2
    assert result.petitionDecisionDataBag[0].applicationNumberText == "17654321"


def test_petition_stub_and_summary_report_the_relocated_outcome() -> None:
    record = {**PETITION, "decisionTypeCode": None}

    assert _stub_petition(record)["decision_type_code"] == "DENIED"
    assert "Decision: DENIED on 2026-11-17" in _summarize_petition(record)


# ──────────────────────────── office action search ────────────────────────


async def test_search_office_actions() -> None:
    facets = {"documentCode": [{"value": "CTNF", "count": 6763150}]}
    odp = FakeOdp({"count": 7, "officeActionDataBag": [OFFICE_ACTION], "facets": facets})
    async with odp.client() as client:
        result = await client.search_office_actions(
            q="obviousness",
            filters=[{"name": "documentCode", "value": ["CTNF"]}],
            facets=["documentCode"],
            limit=1,
        )

    assert odp.sent == (
        "POST",
        "/patent/office-action/search",
        {
            "q": "obviousness",
            "filters": [{"name": "documentCode", "value": ["CTNF"]}],
            "facets": ["documentCode"],
            "pagination": {"offset": 0, "limit": 1},
        },
    )
    (action,) = result.officeActionDataBag
    assert (result.count, action.groupArtUnitNumber, action.documentCode) == (7, "2641", "NOA")
    assert result.facets == facets


async def test_download_office_actions_reads_the_download_record_key() -> None:
    odp = FakeOdp({"officeActionsData": [OFFICE_ACTION]})
    async with odp.client() as client:
        result = await client.download_office_actions(q="applicationNumberText:16123456")

    assert odp.sent == (
        "POST",
        "/patent/office-action/search/download",
        {"q": "applicationNumberText:16123456", "format": "json"},
    )
    assert (result.count, result.officeActionDataBag[0].patentNumber) == (1, "10902286")


async def test_get_office_action() -> None:
    odp = FakeOdp({"count": 1, "officeActionDataBag": [OFFICE_ACTION]})
    async with odp.client() as client:
        result = await client.get_office_action(" 7e0f21f01fe3bf91fc98254d4d211a51 ")

    assert odp.sent[:2] == ("GET", "/patent/office-action/7e0f21f01fe3bf91fc98254d4d211a51")
    assert result.officeActionDataBag[0].submissionDate == "2020-09-23"


@pytest.mark.parametrize(
    "reply",
    ["EXAMINER'S AMENDMENT ...", {"officeActionText": "EXAMINER'S AMENDMENT ..."}],
    ids=["plain-text-as-served", "json-as-documented"],
)
async def test_get_office_action_text(reply: Any) -> None:
    odp = FakeOdp(reply)
    async with odp.client() as client:
        text = await client.get_office_action_text("abc")

    assert odp.sent[:2] == ("GET", "/patent/office-action/abc/download/officeActionText")
    assert text == "EXAMINER'S AMENDMENT ..."


# ──────────────────────────── trademark decisions ─────────────────────────


async def test_search_trademark_decisions() -> None:
    odp = FakeOdp({"count": 11883, "trademarkDecisionsDataBag": [TRADEMARK_DECISION]})
    async with odp.client() as client:
        result = await client.search_trademark_decisions(
            q="expungement",
            filters=[{"name": "decisionProceedingCategory", "value": ["ExpungReexam"]}],
            limit=1,
        )

    assert odp.sent == (
        "POST",
        "/trademark/decision-proceeding/search",
        {
            "q": "expungement",
            "filters": [{"name": "decisionProceedingCategory", "value": ["ExpungReexam"]}],
            "pagination": {"offset": 0, "limit": 1},
        },
    )
    (decision,) = result.trademarkDecisionsDataBag
    assert (result.count, decision.serialNumber, decision.registrationNumber) == (
        11883,
        "79295732",
        "6458316",
    )


async def test_search_trademark_decisions_treats_404_as_no_results() -> None:
    odp = FakeOdp(NOT_FOUND, status=404)
    async with odp.client() as client:
        result = await client.search_trademark_decisions(q="zzzzqqqqxxxx")

    assert (result.count, result.trademarkDecisionsDataBag) == (0, [])


async def test_get_trademark_decision_wraps_the_single_object_bag() -> None:
    odp = FakeOdp({"count": 1, "trademarkDecisionsDataBag": TRADEMARK_DECISION})
    async with odp.client() as client:
        result = await client.get_trademark_decision(TRADEMARK_DECISION["documentIdentifier"])

    assert odp.sent[:2] == (
        "GET",
        f"/trademark/decision-proceeding/search/{TRADEMARK_DECISION['documentIdentifier']}",
    )
    assert [d.markLiteralText for d in result.trademarkDecisionsDataBag] == ["NEOWISE"]


async def test_download_trademark_decisions() -> None:
    odp = FakeOdp({"count": 1, "trademarkDecisionsDataBag": [TRADEMARK_DECISION]})
    async with odp.client() as client:
        result = await client.download_trademark_decisions(limit=1)

    assert odp.sent == (
        "POST",
        "/trademark/decision-proceeding/search/download",
        {"pagination": {"limit": 1}, "format": "json"},
    )
    assert result.trademarkDecisionsDataBag[0].petitionNumber == "2026-105807E"


async def test_download_trademark_decision_pdf(tmp_path: Path) -> None:
    uri = f"{API}/trademark/decision-proceeding/file/proceedings-decisions/abc.pdf"
    odp = FakeOdp("%PDF-1.7")
    async with odp.client() as client:
        content = await client.download_trademark_decision_pdf(
            uri, output_path=tmp_path / "out" / "abc.pdf"
        )

    assert str(odp.request.url) == uri
    assert content == (tmp_path / "out" / "abc.pdf").read_bytes() == b"%PDF-1.7"


# ───────────────── application sections, downloads, status codes ───────────


@pytest.mark.parametrize(
    ("section", "key"),
    [
        ("meta-data", "applicationMetaData"),
        ("adjustment", "patentTermAdjustmentData"),
        ("attorney", "recordAttorney"),
        ("continuity", "childContinuityBag"),
        ("foreign-priority", "foreignPriorityBag"),
        ("transactions", "eventDataBag"),
        ("associated-documents", "grantDocumentMetaData"),
    ],
)
async def test_get_application_section(section: Any, key: str) -> None:
    record = {"applicationNumberText": "16123456", key: {"marker": section}}
    odp = FakeOdp({"count": 1, "patentFileWrapperDataBag": [record]})
    async with odp.client() as client:
        result = await client.get_application_section("16/123,456", section)

    assert odp.sent[:2] == ("GET", f"/patent/applications/16123456/{section}")
    (record,) = result.patentBag
    assert record["applicationNumberText"] == "16123456"
    # Normalization may flatten or nest the section; its content must survive.
    assert f'"marker": "{section}"' in json.dumps(record)


async def test_download_applications_reads_the_download_record_key() -> None:
    record = {"applicationMetaData": {"inventionTitle": "LEARNING ASSISTANCE DEVICE"}}
    odp = FakeOdp({"patentdata": [record]})
    async with odp.client() as client:
        result = await client.download_applications(
            query="applicationNumberText:16123456",
            range_filters=[{"field": "applicationMetaData.filingDate", "valueFrom": "2018-01-01"}],
        )

    method, path, body = odp.sent
    assert (method, path) == ("POST", "/patent/applications/search/download")
    assert (body["q"], body["format"]) == ("applicationNumberText:16123456", "json")
    assert body["rangeFilters"][0]["valueTo"]  # the open bound ODP requires is filled in
    assert (result.count, result.patentBag[0]["inventionTitle"]) == (
        1,
        "LEARNING ASSISTANCE DEVICE",
    )


async def test_search_status_codes() -> None:
    bag = [{"applicationStatusCode": 150, "applicationStatusDescriptionText": "Patented Case"}]
    odp = FakeOdp({"count": 1, "statusCodeBag": bag})
    async with odp.client() as client:
        result = await client.search_status_codes(query="applicationStatusCode:150", limit=1)

    assert odp.sent == (
        "POST",
        "/patent/status-codes",
        {"q": "applicationStatusCode:150", "pagination": {"offset": 0, "limit": 1}},
    )
    assert result.statusCodeBag[0].applicationStatusDescriptionText == "Patented Case"


# ───────────────────────────── bulk file download ─────────────────────────


async def test_download_bulk_dataset_file_streams_to_disk(tmp_path: Path) -> None:
    odp = FakeOdp("zip-bytes")
    async with odp.client() as client:
        written = await client.download_bulk_dataset_file(
            "PTFWPRE", "2011-2020.zip", tmp_path / "bulk" / "2011-2020.zip"
        )

    assert odp.sent[:2] == ("GET", "/datasets/products/files/PTFWPRE/2011-2020.zip")
    assert written.read_bytes() == b"zip-bytes"


async def test_download_bulk_dataset_file_raises_on_error(tmp_path: Path) -> None:
    from mcp_data_core.exceptions import NotFoundError

    odp = FakeOdp(NOT_FOUND, status=404)
    async with odp.client() as client:
        with pytest.raises(NotFoundError):
            await client.download_bulk_dataset_file("PTFWPRE", "nope.zip", tmp_path / "nope.zip")


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_office_action("  "),
        lambda c: c.get_office_action_text(""),
        lambda c: c.get_trademark_decision(" "),
        lambda c: c.download_trademark_decision_pdf(""),
        lambda c: c.download_bulk_dataset_file("PTFWPRE", " ", "x.zip"),
    ],
)
async def test_blank_identifiers_are_rejected_before_any_request(
    call: Callable[[UsptoOdpClient], Any],
) -> None:
    from mcp_data_core.exceptions import ValidationError

    odp = FakeOdp({})
    async with odp.client() as client:
        with pytest.raises(ValidationError):
            await call(client)

    assert odp.requests == []

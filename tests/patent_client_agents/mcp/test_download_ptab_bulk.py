"""Tests for the four PTAB bulk download tools."""

from __future__ import annotations

import asyncio
import zipfile
from types import SimpleNamespace

import pytest

from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp import downloads
from patent_client_agents.mcp.tools import uspto as uspto_tools


@pytest.fixture(autouse=True)
def _reset_sources():
    saved = dict(downloads._SOURCES)
    downloads._SOURCES.clear()
    yield
    downloads._SOURCES.clear()
    downloads._SOURCES.update(saved)


@pytest.fixture
def _stdio_mode(monkeypatch):
    monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
    monkeypatch.delenv("LAW_TOOLS_PUBLIC_URL", raising=False)


@pytest.fixture
def _isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))


def _run(coro):
    """Run the coroutine and unwrap ``ToolResult.structured_content``.

    PTAB bulk tools now return ``ToolResult`` (per-item ResourceLinks
    alongside the existing dict payload). These tests assert on the
    dict shape, so we unwrap here.
    """
    result = asyncio.run(coro)
    if hasattr(result, "structured_content"):
        return result.structured_content
    return result


def _stub_pdf_downloader(monkeypatch, content_by_uri: dict[str, bytes]) -> dict[str, int]:
    """Replace _ptab_download_pdf so tests don't need a real HTTP client."""
    calls: dict[str, int] = {}

    async def fake_download(uri: str) -> bytes:
        calls[uri] = calls.get(uri, 0) + 1
        if uri not in content_by_uri:
            raise RuntimeError(f"no canned content for {uri!r}")
        return content_by_uri[uri]

    monkeypatch.setattr(uspto_tools, "_ptab_download_pdf", fake_download)
    return calls


def _trial_doc_entry(*, doc_id: str, uri: str, filing_date: str, code: str = "PET"):
    return SimpleNamespace(
        documentData=SimpleNamespace(
            documentIdentifier=doc_id,
            fileDownloadURI=uri,
            downloadURI=None,
            documentFilingDate=filing_date,
            documentTitleText=f"Title {doc_id}",
            documentName=None,
            documentTypeDescriptionText=code,
            documentNumber=None,
            filingPartyCategory="PETITIONER",
        ),
        decisionData=None,
    )


def _trial_decision_entry(*, doc_id: str, uri: str, issue_date: str, code: str = "INST"):
    return SimpleNamespace(
        documentData=SimpleNamespace(
            documentIdentifier=doc_id,
            fileDownloadURI=uri,
            downloadURI=None,
            documentFilingDate=issue_date,
            documentTitleText=None,
            documentName=f"Decision {doc_id}",
            documentTypeDescriptionText="Decision",
            documentNumber=None,
            filingPartyCategory="BOARD",
        ),
        decisionData=SimpleNamespace(
            decisionTypeCategory=code,
            decisionIssueDate=issue_date,
            trialOutcomeCategory=None,
        ),
    )


def _appeal_entry(*, doc_id: str, uri: str, issue_date: str, code: str = "AFFIRMED"):
    return SimpleNamespace(
        documentData=SimpleNamespace(
            documentIdentifier=doc_id,
            fileDownloadURI=uri,
            downloadURI=None,
            documentFilingDate=issue_date,
            documentName=f"Appeal {doc_id}",
            documentTypeDescriptionText="Decision on Appeal",
        ),
        decisionData=SimpleNamespace(
            decisionTypeCategory=code,
            decisionIssueDate=issue_date,
            appealOutcomeCategory=code,
        ),
    )


def _interference_entry(*, doc_id: str, uri: str, issue_date: str):
    return SimpleNamespace(
        documentData=None,
        decisionDocumentData=SimpleNamespace(
            documentIdentifier=doc_id,
            fileDownloadURI=uri,
            decisionIssueDate=issue_date,
            decisionTypeCategory="FINAL",
            interferenceOutcomeCategory="AFFIRMED",
            documentTitleText=None,
            documentName=f"Interference {doc_id}",
        ),
    )


class _FakeOdpClient:
    """Stand-in for UsptoOdpClient that returns canned by-trial / by-number bags."""

    def __init__(
        self,
        *,
        trial_documents: list | None = None,
        trial_decisions: list | None = None,
        appeal_decisions: list | None = None,
        interference_decisions: list | None = None,
    ) -> None:
        self._trial_documents = trial_documents or []
        self._trial_decisions = trial_decisions or []
        self._appeal_decisions = appeal_decisions or []
        self._interference_decisions = interference_decisions or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return None

    async def get_trial_documents_by_trial(self, _tn):
        return SimpleNamespace(patentTrialDocumentDataBag=self._trial_documents)

    async def get_trial_decisions_by_trial(self, _tn):
        return SimpleNamespace(patentTrialDocumentDataBag=self._trial_decisions)

    async def get_appeal_decisions_by_number(self, _an):
        return SimpleNamespace(patentAppealDataBag=self._appeal_decisions)

    async def get_interference_decisions_by_number(self, _in):
        return SimpleNamespace(patentInterferenceDataBag=self._interference_decisions)


def _patch_client(monkeypatch, client: _FakeOdpClient) -> None:
    monkeypatch.setattr(uspto_tools, "UsptoOdpClient", lambda: client)


class TestTrialDocuments:
    def test_bulk_with_all_docs(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(
            monkeypatch,
            _FakeOdpClient(
                trial_documents=[
                    _trial_doc_entry(doc_id="A", uri="/p/A.pdf", filing_date="2024-01-15"),
                    _trial_doc_entry(doc_id="B", uri="/p/B.pdf", filing_date="2024-02-01"),
                    _trial_doc_entry(doc_id="C", uri="/p/C.pdf", filing_date="2024-03-01"),
                ]
            ),
        )
        _stub_pdf_downloader(monkeypatch, {"/p/A.pdf": b"a", "/p/B.pdf": b"b", "/p/C.pdf": b"c"})

        result = _run(uspto_tools.download_ptab_trial_documents("IPR2024-00001"))
        assert result["ok_count"] == 3
        assert result["container"] == "IPR2024-00001"
        assert result["trial_number"] == "IPR2024-00001"
        assert result["filename"] == "IPR2024-00001_trial_documents.zip"
        with zipfile.ZipFile(result["file_path"]) as zf:
            names = sorted(zf.namelist())
            assert len(names) == 3
            assert all(n.startswith(("A/", "B/", "C/")) for n in names)

    def test_item_ids_filter(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(
            monkeypatch,
            _FakeOdpClient(
                trial_documents=[
                    _trial_doc_entry(doc_id=f"D{n}", uri=f"/p/D{n}.pdf", filing_date="2024-01-15")
                    for n in range(4)
                ]
            ),
        )
        _stub_pdf_downloader(monkeypatch, {"/p/D0.pdf": b"0", "/p/D2.pdf": b"2"})

        result = _run(
            uspto_tools.download_ptab_trial_documents("IPR2024-00001", item_ids=["D0", "D2"])
        )
        ids = sorted(m["item_id"] for m in result["manifest"])
        assert ids == ["D0", "D2"]

    def test_date_filter(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(
            monkeypatch,
            _FakeOdpClient(
                trial_documents=[
                    _trial_doc_entry(doc_id="early", uri="/p/e.pdf", filing_date="2023-12-01"),
                    _trial_doc_entry(doc_id="mid1", uri="/p/m1.pdf", filing_date="2024-02-15"),
                    _trial_doc_entry(doc_id="mid2", uri="/p/m2.pdf", filing_date="2024-02-20"),
                    _trial_doc_entry(doc_id="late", uri="/p/l.pdf", filing_date="2024-06-01"),
                ]
            ),
        )
        _stub_pdf_downloader(monkeypatch, {"/p/m1.pdf": b"m1", "/p/m2.pdf": b"m2"})

        result = _run(
            uspto_tools.download_ptab_trial_documents(
                "IPR2024-00001", after="2024-01-01", before="2024-03-01"
            )
        )
        ids = sorted(m["item_id"] for m in result["manifest"])
        assert ids == ["mid1", "mid2"]

    def test_cap_exceeded(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        # cap is 100.
        docs = [
            _trial_doc_entry(doc_id=f"D{n}", uri=f"/p/D{n}.pdf", filing_date="2024-01-01")
            for n in range(101)
        ]
        _patch_client(monkeypatch, _FakeOdpClient(trial_documents=docs))

        with pytest.raises(ValidationError, match="max 100 per call"):
            _run(uspto_tools.download_ptab_trial_documents("IPR2024-00001"))

    def test_no_match_raises(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(monkeypatch, _FakeOdpClient(trial_documents=[]))

        with pytest.raises(ValidationError, match="No PTAB trial documents"):
            _run(uspto_tools.download_ptab_trial_documents("IPR2024-00001"))


class TestTrialDecisions:
    def test_uses_separate_cache_prefix(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(
            monkeypatch,
            _FakeOdpClient(
                trial_decisions=[
                    _trial_decision_entry(doc_id="D1", uri="/p/D1.pdf", issue_date="2024-06-15"),
                ]
            ),
        )
        _stub_pdf_downloader(monkeypatch, {"/p/D1.pdf": b"decision"})

        result = _run(uspto_tools.download_ptab_trial_decisions("IPR2024-00001"))
        # n=1 short-circuits; confirm it uses the new trial-decisions cache prefix
        # (not ptab/documents).
        from mcp_data_core.mcp.downloads import _cache_get

        assert _cache_get("ptab/trial-decisions/D1") is not None
        assert _cache_get("ptab/documents/D1") is None
        assert result["filename"].endswith("D1.pdf")

    def test_cap_50(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        decisions = [
            _trial_decision_entry(doc_id=f"X{n}", uri=f"/p/X{n}.pdf", issue_date="2024-06-15")
            for n in range(51)
        ]
        _patch_client(monkeypatch, _FakeOdpClient(trial_decisions=decisions))

        with pytest.raises(ValidationError, match="max 50 per call"):
            _run(uspto_tools.download_ptab_trial_decisions("IPR2024-00001"))


class TestAppealDecisions:
    def test_bulk_download(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(
            monkeypatch,
            _FakeOdpClient(
                appeal_decisions=[
                    _appeal_entry(doc_id="A1", uri="/p/A1.pdf", issue_date="2024-01-15"),
                    _appeal_entry(doc_id="A2", uri="/p/A2.pdf", issue_date="2024-02-01"),
                ]
            ),
        )
        _stub_pdf_downloader(monkeypatch, {"/p/A1.pdf": b"a1", "/p/A2.pdf": b"a2"})

        result = _run(uspto_tools.download_ptab_appeal_decisions("16123456"))
        assert result["ok_count"] == 2
        assert result["application_number"] == "16123456"

    def test_date_filter_uses_issue_date(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(
            monkeypatch,
            _FakeOdpClient(
                appeal_decisions=[
                    _appeal_entry(doc_id="early", uri="/p/e.pdf", issue_date="2023-06-01"),
                    _appeal_entry(doc_id="mid1", uri="/p/m1.pdf", issue_date="2024-03-01"),
                    _appeal_entry(doc_id="mid2", uri="/p/m2.pdf", issue_date="2024-04-15"),
                    _appeal_entry(doc_id="late", uri="/p/l.pdf", issue_date="2025-01-01"),
                ]
            ),
        )
        _stub_pdf_downloader(monkeypatch, {"/p/m1.pdf": b"m1", "/p/m2.pdf": b"m2"})

        result = _run(
            uspto_tools.download_ptab_appeal_decisions(
                "16123456", after="2024-01-01", before="2024-12-31"
            )
        )
        ids = sorted(m["item_id"] for m in result["manifest"])
        assert ids == ["mid1", "mid2"]


class TestInterferenceDecisions:
    def test_bulk_download(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(
            monkeypatch,
            _FakeOdpClient(
                interference_decisions=[
                    _interference_entry(doc_id="I1", uri="/p/I1.pdf", issue_date="2010-06-15"),
                    _interference_entry(doc_id="I2", uri="/p/I2.pdf", issue_date="2011-01-01"),
                ]
            ),
        )
        _stub_pdf_downloader(monkeypatch, {"/p/I1.pdf": b"i1", "/p/I2.pdf": b"i2"})

        result = _run(uspto_tools.download_ptab_interference_decisions("105,123"))
        assert result["ok_count"] == 2
        assert result["interference_number"] == "105,123"


class TestInvalidInput:
    def test_bad_date_raises(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(monkeypatch, _FakeOdpClient(trial_documents=[]))
        with pytest.raises(ValidationError, match="ISO date"):
            _run(uspto_tools.download_ptab_trial_documents("IPR2024-00001", after="bogus"))

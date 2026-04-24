"""Tests for PatentsView client and models."""

import json
from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest
from ip_tools.patentsview import (
    Assignee,
    Citation,
    CitationsResponse,
    Claim,
    ClaimsResponse,
    CpcClassification,
    Examiner,
    Inventor,
    Patent,
    PatentsResponse,
    PatentsViewClient,
    PatentWithDetails,
)
from ip_tools.patentsview.client import _normalize_patent_number, _parse_patent


class TestModels:
    """Tests for Pydantic models."""

    def test_patent_model(self):
        """Basic Patent model."""
        patent = Patent(
            patent_id="abc123",
            patent_number="10000000",
            patent_title="Test Patent",
            patent_date=date(2020, 1, 15),
            patent_type="utility",
            patent_num_claims=20,
            patent_num_cited_by_us_patents=50,
        )
        assert patent.patent_id == "abc123"
        assert patent.patent_number == "10000000"
        assert patent.patent_date == date(2020, 1, 15)
        assert patent.patent_num_cited_by_us_patents == 50

    def test_inventor_full_name(self):
        """Inventor full_name property."""
        inv = Inventor(
            inventor_id="inv1",
            inventor_first_name="John",
            inventor_last_name="Doe",
        )
        assert inv.full_name == "John Doe"

        # Partial name
        inv2 = Inventor(inventor_id="inv2", inventor_last_name="Smith")
        assert inv2.full_name == "Smith"

    def test_examiner_full_name(self):
        """Examiner full_name property."""
        ex = Examiner(
            examiner_id="ex1",
            examiner_first_name="Jane",
            examiner_last_name="Wilson",
            examiner_group="2100",
        )
        assert ex.full_name == "Jane Wilson"
        assert ex.examiner_group == "2100"

    def test_cpc_full_code(self):
        """CpcClassification full_code property."""
        cpc = CpcClassification(
            cpc_section_id="H",
            cpc_group_id="H04L",
            cpc_subgroup_id="H04L63/00",
        )
        assert cpc.full_code == "H04L63/00"

        # Partial
        cpc2 = CpcClassification(cpc_group_id="G06F")
        assert cpc2.full_code == "G06F"

    def test_claim_properties(self):
        """Claim is_independent and word_count properties."""
        # Independent claim
        claim1 = Claim(
            patent_id="abc",
            claim_number=1,
            claim_text="A method comprising steps of processing data",
            claim_sequence=1,
            dependent=None,
        )
        assert claim1.is_independent is True
        assert claim1.word_count == 7

        # Dependent claim
        claim2 = Claim(
            patent_id="abc",
            claim_number=2,
            claim_text="The method of claim 1 further comprising storing",
            claim_sequence=2,
            dependent=1,
        )
        assert claim2.is_independent is False
        assert claim2.word_count == 8

    def test_patent_with_details(self):
        """PatentWithDetails with nested entities."""
        patent = PatentWithDetails(
            patent_id="abc123",
            patent_number="10000000",
            patent_title="Test Patent",
            inventors=[
                Inventor(inventor_id="inv1", inventor_first_name="John", inventor_last_name="Doe")
            ],
            assignees=[Assignee(assignee_id="asg1", assignee_organization="Test Corp")],
            cpcs=[CpcClassification(cpc_group_id="H04L")],
            examiners=[Examiner(examiner_id="ex1", examiner_group="2100")],
        )
        assert len(patent.inventors) == 1
        assert patent.inventors[0].full_name == "John Doe"
        assert patent.assignees[0].assignee_organization == "Test Corp"


class TestNormalizePatentNumber:
    """Tests for patent number normalization."""

    def test_already_normalized(self):
        """Already normalized number."""
        assert _normalize_patent_number("10000000") == "10000000"

    def test_with_us_prefix(self):
        """Remove US prefix."""
        assert _normalize_patent_number("US10000000") == "10000000"
        assert _normalize_patent_number("us10000000") == "10000000"

    def test_with_kind_code(self):
        """Remove kind code."""
        assert _normalize_patent_number("US10000000B2") == "10000000"
        assert _normalize_patent_number("US10000000A1") == "10000000"
        assert _normalize_patent_number("10000000B1") == "10000000"

    def test_with_spaces(self):
        """Handle whitespace."""
        assert _normalize_patent_number("  US10000000B2  ") == "10000000"

    def test_ep_prefix(self):
        """Handle EP prefix."""
        assert _normalize_patent_number("EP1234567B1") == "1234567"


class TestParsePatent:
    """Tests for _parse_patent helper."""

    def test_parse_basic(self):
        """Parse basic patent data."""
        data = {
            "patent_id": "abc123",
            "patent_number": "10000000",
            "patent_title": "Test Patent",
            "patent_date": "2020-01-15",
            "patent_type": "utility",
            "patent_num_claims": 20,
            "patent_num_cited_by_us_patents": 50,
        }
        patent = _parse_patent(data)
        assert patent.patent_id == "abc123"
        assert patent.patent_date == date(2020, 1, 15)
        assert patent.patent_num_cited_by_us_patents == 50

    def test_parse_with_inventors(self):
        """Parse patent with inventors."""
        data = {
            "patent_id": "abc123",
            "patent_number": "10000000",
            "patent_title": "Test",
            "inventors": [
                {
                    "inventor_id": "inv1",
                    "inventor_first_name": "John",
                    "inventor_last_name": "Doe",
                },
                {
                    "inventor_id": "inv2",
                    "inventor_first_name": "Jane",
                    "inventor_last_name": "Smith",
                },
            ],
        }
        patent = _parse_patent(data)
        assert len(patent.inventors) == 2
        assert patent.inventors[0].full_name == "John Doe"

    def test_parse_with_null_nested(self):
        """Handle null nested entities."""
        data = {
            "patent_id": "abc123",
            "patent_number": "10000000",
            "patent_title": "Test",
            "inventors": None,
            "assignees": None,
        }
        patent = _parse_patent(data)
        assert patent.inventors == []
        assert patent.assignees == []

    def test_parse_invalid_date(self):
        """Handle invalid date gracefully."""
        data = {
            "patent_id": "abc123",
            "patent_number": "10000000",
            "patent_title": "Test",
            "patent_date": "invalid-date",
        }
        patent = _parse_patent(data)
        assert patent.patent_date is None


class TestPatentsViewClient:
    """Tests for PatentsViewClient."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Client works as context manager."""
        async with PatentsViewClient(use_cache=False) as client:
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_search_patents_builds_request(self, monkeypatch):
        """search_patents builds correct request body."""
        captured_request = {}

        async def mock_request(self, method, url, **kwargs):
            captured_request["method"] = method
            captured_request["url"] = url
            captured_request["json"] = kwargs.get("json")
            response = MagicMock(spec=httpx.Response)
            response.is_success = True
            response.json.return_value = {
                "patents": [
                    {
                        "patent_id": "abc",
                        "patent_number": "10000000",
                        "patent_title": "Test",
                    }
                ],
                "total_patent_count": 1,
                "count": 1,
            }
            return response

        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with PatentsViewClient(use_cache=False) as client:
            result = await client.search_patents(
                query={"cpc_group_id": "H04L63"},
                fields=["patent_id", "patent_title"],
                sort=[{"patent_date": "desc"}],
                per_page=50,
                page=2,
            )

        assert captured_request["method"] == "POST"
        assert "patent/" in captured_request["url"]
        body = captured_request["json"]
        assert body["q"] == {"cpc_current.cpc_group_id": "H04L63"}
        assert body["f"] == ["patent_id", "patent_title"]
        assert body["s"] == [{"patent_date": "desc"}]
        assert body["o"] == {"per_page": 50, "page": 2}
        assert len(result.patents) == 1

    @pytest.mark.asyncio
    async def test_get_patent_normalizes_number(self, monkeypatch):
        """get_patent normalizes patent number."""
        captured_query = {}

        async def mock_search(self, query, **kwargs):
            captured_query.update(query)
            return PatentsResponse(patents=[], total_patent_count=0, count=0)

        monkeypatch.setattr(PatentsViewClient, "search_patents", mock_search)

        async with PatentsViewClient(use_cache=False) as client:
            await client.get_patent("US10000000B2")

        assert captured_query == {"patent_id": "10000000"}

    @pytest.mark.asyncio
    async def test_get_citations_direction(self, monkeypatch):
        """get_citations uses correct query for direction."""
        captured_requests = []

        async def mock_request(self, method, url, **kwargs):
            captured_requests.append(kwargs.get("json"))
            response = MagicMock(spec=httpx.Response)
            response.is_success = True
            response.json.return_value = {"us_patent_citations": [], "total_hits": 0}
            return response

        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with PatentsViewClient(use_cache=False) as client:
            # Citing direction
            await client.get_citations("abc123", direction="citing")
            # Cited direction
            await client.get_citations("abc123", direction="cited")

        # First call: citing (find patents that cite this one)
        assert captured_requests[0]["q"] == {"citation_patent_id": "abc123"}
        # Second call: cited (find patents cited by this one)
        assert captured_requests[1]["q"] == {"patent_id": "abc123"}

    @pytest.mark.asyncio
    async def test_get_claims_sorted(self, monkeypatch):
        """get_claims requests sorted by claim_sequence."""
        captured_request = {}

        async def mock_request(self, method, url, **kwargs):
            captured_request["method"] = method
            captured_request["url"] = url
            captured_request["params"] = kwargs.get("params", {})
            response = MagicMock(spec=httpx.Response)
            response.is_success = True
            response.json.return_value = {"g_claims": [], "total_hits": 0}
            return response

        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with PatentsViewClient(use_cache=False) as client:
            await client.get_claims("abc123")

        assert captured_request["method"] == "GET"
        assert "g_claim" in captured_request["url"]
        assert json.loads(captured_request["params"]["s"]) == [{"claim_sequence": "asc"}]

    @pytest.mark.asyncio
    async def test_per_page_capped_at_1000(self, monkeypatch):
        """per_page is capped at 1000."""
        captured_request = {}

        async def mock_request(self, method, url, **kwargs):
            captured_request.update(kwargs.get("json", {}))
            response = MagicMock(spec=httpx.Response)
            response.is_success = True
            response.json.return_value = {"patents": [], "total_hits": 0}
            return response

        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with PatentsViewClient(use_cache=False) as client:
            await client.search_patents(
                query={"patent_type": "utility"},
                per_page=5000,  # Way over limit
            )

        assert captured_request["o"]["per_page"] == 1000


class TestResponseModels:
    """Tests for response model structures."""

    def test_patents_response(self):
        """PatentsResponse structure."""
        resp = PatentsResponse(
            patents=[
                PatentWithDetails(
                    patent_id="abc",
                    patent_number="10000000",
                    patent_title="Test",
                )
            ],
            total_patent_count=100,
            count=1,
        )
        assert len(resp.patents) == 1
        assert resp.total_patent_count == 100

    def test_citations_response(self):
        """CitationsResponse structure."""
        resp = CitationsResponse(
            citations=[
                Citation(
                    citation_patent_id="abc",
                    cited_patent_id="def",
                    citation_category="examiner",
                )
            ],
            total_citation_count=50,
            count=1,
        )
        assert len(resp.citations) == 1
        assert resp.citations[0].citation_category == "examiner"

    def test_claims_response(self):
        """ClaimsResponse structure."""
        resp = ClaimsResponse(
            claims=[
                Claim(
                    patent_id="abc",
                    claim_number=1,
                    claim_text="A method",
                    claim_sequence=1,
                )
            ],
            total_claim_count=20,
            count=1,
        )
        assert len(resp.claims) == 1
        assert resp.claims[0].is_independent

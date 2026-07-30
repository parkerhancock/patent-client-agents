"""Structured citation, equivalents, and European Patent Register tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope
from patent_client_agents.epo_ops.client import EpoOpsClient
from patent_client_agents.epo_ops.models import (
    CitationResponse,
    DocumentId,
    EquivalentsResponse,
    RegisterEvent,
    RegisterEventsResponse,
    RegisterProceduralStep,
    RegisterProceduralStepsResponse,
)
from patent_client_agents.epo_ops.parsing import (
    parse_citations,
    parse_equivalents,
    parse_register_events,
    parse_register_procedural_steps,
)
from patent_client_agents.mcp.tools.epo_ops import (
    get_epo_citations,
    get_epo_equivalents,
    get_epo_procedural_steps,
    get_epo_register_events,
)

_CITATIONS_XML = """\
<ops:world-patent-data xmlns:ops="http://ops.epo.org"
                       xmlns="http://www.epo.org/exchange">
  <exchange-document>
    <bibliographic-data>
      <references-cited>
        <citation cited-phase="national-search-report" cited-by="examiner" sequence="1">
          <patcit dnum-type="publication number" num="1">
            <document-id document-id-type="epodoc">
              <doc-number>EP0680812</doc-number>
            </document-id>
            <document-id document-id-type="docdb">
              <country>EP</country>
              <doc-number>0680812</doc-number>
              <kind>A1</kind>
              <name>BOER BEHEER NIJMEGEN BV DE [NL]</name>
              <date>19951108</date>
            </document-id>
          </patcit>
          <category>X</category>
          <rel-claims>1,10,11</rel-claims>
          <rel-passage><passage>column 3, lines 4-18</passage></rel-passage>
        </citation>
        <citation cited-phase="international-search-report" sequence="2">
          <nplcit num="2"><text>Example Journal 12 (1998), 1-5</text></nplcit>
          <category>A</category>
        </citation>
      </references-cited>
    </bibliographic-data>
  </exchange-document>
</ops:world-patent-data>
"""

_EQUIVALENTS_XML = """\
<ops:world-patent-data xmlns:ops="http://ops.epo.org"
                       xmlns="http://www.epo.org/exchange">
  <ops:equivalents-inquiry>
    <ops:publication-reference>
      <document-id document-id-type="epodoc"><doc-number>EP1000000</doc-number></document-id>
    </ops:publication-reference>
    <ops:inquiry-result>
      <publication-reference>
        <document-id document-id-type="epodoc"><doc-number>US6093011</doc-number></document-id>
        <document-id document-id-type="docdb">
          <country>US</country><doc-number>6093011</doc-number><kind>A</kind>
        </document-id>
      </publication-reference>
    </ops:inquiry-result>
  </ops:equivalents-inquiry>
</ops:world-patent-data>
"""

_REGISTER_EVENTS_XML = """\
<ops:world-patent-data xmlns:ops="http://ops.epo.org"
                       xmlns:reg="http://www.epo.org/register">
  <ops:register-search total-result-count="1">
    <reg:register-documents>
      <reg:register-document status="active" produced-by="RO"
          lang="en" dtd-version="1.0" date-produced="20260730">
        <reg:events-data>
          <reg:dossier-event event-type="new" id="EVT_82">
            <reg:event-date><reg:date>20000331</reg:date></reg:event-date>
            <reg:event-code>0009012</reg:event-code>
            <reg:event-text event-text-type="DESCRIPTION">Publication in section I.1</reg:event-text>
            <reg:event-text event-text-type="DETAIL">Search report published</reg:event-text>
            <reg:gazette-reference>
              <reg:gazette-num>2000/20</reg:gazette-num>
              <reg:date>20000517</reg:date>
            </reg:gazette-reference>
          </reg:dossier-event>
        </reg:events-data>
      </reg:register-document>
    </reg:register-documents>
  </ops:register-search>
</ops:world-patent-data>
"""

_REGISTER_STEPS_XML = """\
<ops:world-patent-data xmlns:ops="http://ops.epo.org"
                       xmlns:reg="http://www.epo.org/register">
  <ops:register-search total-result-count="1">
    <reg:register-documents>
      <reg:register-document status="active" date-produced="20260730">
        <reg:procedural-data>
          <reg:procedural-step procedure-step-phase="fees" id="RENEWAL_5">
            <reg:procedural-step-code>RFEE</reg:procedural-step-code>
            <reg:procedural-step-text step-texttype="STEP_DESCRIPTION">Renewal fee payment</reg:procedural-step-text>
            <reg:procedural-step-text step-text-type="YEAR">03</reg:procedural-step-text>
            <reg:procedural-step-date step-date-type="DATE_OF_PAYMENT">
              <reg:date>20011128</reg:date>
            </reg:procedural-step-date>
          </reg:procedural-step>
        </reg:procedural-data>
      </reg:register-document>
    </reg:register-documents>
  </ops:register-search>
</ops:world-patent-data>
"""


def test_parse_citations_preserves_prosecution_metadata() -> None:
    result = parse_citations(_CITATIONS_XML, publication_number="EP1000000A1")

    assert result.publication_number == "EP1000000A1"
    assert len(result.citations) == 2
    patent = result.citations[0]
    assert patent.sequence == 1
    assert patent.cited_by == "examiner"
    assert patent.cited_phase == "national-search-report"
    assert patent.categories == ["X"]
    assert patent.relevant_claims == ["1,10,11"]
    assert patent.passages == ["column 3, lines 4-18"]
    assert patent.patent_document == DocumentId(
        country="EP",
        number="0680812",
        kind="A1",
        name="BOER BEHEER NIJMEGEN BV DE [NL]",
        date="19951108",
        format="docdb",
        id_type="docdb",
        doc_type="document-id",
    )
    assert result.citations[1].non_patent_literature == "Example Journal 12 (1998), 1-5"


def test_parse_equivalents_chooses_one_canonical_identifier_per_publication() -> None:
    result = parse_equivalents(_EQUIVALENTS_XML)

    assert len(result.equivalents) == 1
    assert result.equivalents[0].country == "US"
    assert result.equivalents[0].doc_number == "6093011"
    assert result.equivalents[0].kind == "A"
    assert result.equivalents[0].format == "docdb"


def test_structured_parsers_handle_records_without_results() -> None:
    empty = """\
    <ops:world-patent-data xmlns:ops="http://ops.epo.org"
        xmlns="http://www.epo.org/exchange"
        xmlns:reg="http://www.epo.org/register">
      <ops:equivalents-inquiry/>
      <reg:register-documents><reg:register-document/></reg:register-documents>
    </ops:world-patent-data>
    """

    assert parse_citations(empty, publication_number="EP1").citations == []
    assert parse_equivalents(empty).equivalents == []
    assert parse_register_events(empty, epo_number="EP1").events == []
    assert (
        parse_register_procedural_steps(empty, epo_number="EP1").procedural_steps
        == []
    )


def test_parse_register_events_preserves_typed_text_and_gazette() -> None:
    result = parse_register_events(_REGISTER_EVENTS_XML, epo_number="EP1000000")

    assert result.status == "active"
    assert result.date_produced == "20260730"
    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_code == "0009012"
    assert event.description == "Publication in section I.1"
    assert [item.text_type for item in event.texts] == ["DESCRIPTION", "DETAIL"]
    assert event.gazette_reference is not None
    assert event.gazette_reference.number == "2000/20"


def test_parse_register_steps_preserves_typed_text_and_dates() -> None:
    result = parse_register_procedural_steps(_REGISTER_STEPS_XML, epo_number="EP1000000")

    assert len(result.procedural_steps) == 1
    step = result.procedural_steps[0]
    assert step.phase == "fees"
    assert step.step_code == "RFEE"
    assert step.description == "Renewal fee payment"
    assert step.texts[1].text_type == "YEAR"
    assert step.dates[0].date_type == "DATE_OF_PAYMENT"
    assert step.dates[0].date == "20011128"


@pytest.mark.asyncio
async def test_client_uses_exact_citation_and_equivalents_paths() -> None:
    client = object.__new__(EpoOpsClient)
    client._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            SimpleNamespace(text=_CITATIONS_XML),
            SimpleNamespace(text=_EQUIVALENTS_XML),
        ]
    )

    await client.fetch_citations(number=" ep 1000000 a1 ")
    await client.fetch_equivalents(number=" ep 1000000 a1 ")

    assert client._request.await_args_list[0].args == (  # type: ignore[attr-defined]
        "GET",
        "/rest-services/published-data/publication/docdb/EP1000000A1/biblio",
    )
    assert client._request.await_args_list[1].args == (  # type: ignore[attr-defined]
        "GET",
        "/rest-services/published-data/publication/docdb/EP1000000A1/equivalents",
    )


@pytest.mark.asyncio
async def test_client_register_helpers_delegate_to_supported_sub_endpoints() -> None:
    client = object.__new__(EpoOpsClient)
    client.fetch_register = AsyncMock(  # type: ignore[method-assign]
        side_effect=[_REGISTER_EVENTS_XML, _REGISTER_STEPS_XML]
    )

    events = await client.fetch_register_events(number="ep1000000")
    steps = await client.fetch_register_procedural_steps(number="ep1000000")

    assert events.events[0].event_code == "0009012"
    assert steps.procedural_steps[0].step_code == "RFEE"
    assert client.fetch_register.await_args_list[0].kwargs["sub"] == "events"  # type: ignore[attr-defined]
    assert client.fetch_register.await_args_list[1].kwargs["sub"] == "procedural-steps"  # type: ignore[attr-defined]


def _patch_client(mock_client: MagicMock) -> Any:
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=mock_client)
    context.__aexit__ = AsyncMock(return_value=None)
    return patch("patent_client_agents.mcp.tools.epo_ops.client_from_env", return_value=context)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "method", "response", "number", "source_suffix"),
    [
        (
            get_epo_citations,
            "fetch_citations",
            CitationResponse(publication_number="EP1A1"),
            "EP1A1",
            "/published-data/publication/docdb/EP1A1/biblio",
        ),
        (
            get_epo_equivalents,
            "fetch_equivalents",
            EquivalentsResponse(equivalents=[]),
            "EP1A1",
            "/published-data/publication/docdb/EP1A1/equivalents",
        ),
        (
            get_epo_register_events,
            "fetch_register_events",
            RegisterEventsResponse(
                epo_number="EP1000000",
                events=[RegisterEvent(event_code="0009012")],
            ),
            "EP1000000",
            "/register/publication/epodoc/EP1000000/events",
        ),
        (
            get_epo_procedural_steps,
            "fetch_register_procedural_steps",
            RegisterProceduralStepsResponse(
                epo_number="EP1000000",
                procedural_steps=[RegisterProceduralStep(step_code="RFEE")],
            ),
            "EP1000000",
            "/register/publication/epodoc/EP1000000/procedural-steps",
        ),
    ],
)
async def test_new_mcp_views_preserve_envelope_and_exact_provenance(
    tool,
    method,
    response,
    number,
    source_suffix,
) -> None:
    client = MagicMock()
    setattr(client, method, AsyncMock(return_value=response))

    with _patch_client(client):
        result = await tool(number)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.provenance.source_url.endswith(source_suffix)
    getattr(client, method).assert_awaited_once_with(number=number)


@pytest.mark.asyncio
async def test_citation_mcp_view_preserves_list_order() -> None:
    responses = {
        "EP1A1": CitationResponse(publication_number="EP1A1"),
        "EP2A1": CitationResponse(publication_number="EP2A1"),
    }
    client = MagicMock()
    client.fetch_citations = AsyncMock(
        side_effect=lambda *, number: responses[number]
    )

    with _patch_client(client):
        result = await get_epo_citations(["EP1A1", "EP2A1"])

    assert [item["publication_number"] for item in result.items] == [
        "EP1A1",
        "EP2A1",
    ]

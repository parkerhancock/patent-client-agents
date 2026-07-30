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
    RegisterBiblioResponse,
    RegisterEvent,
    RegisterEventsResponse,
    RegisterProceduralStep,
    RegisterProceduralStepsResponse,
)
from patent_client_agents.epo_ops.parsing import (
    parse_citations,
    parse_equivalents,
    parse_register_biblio,
    parse_register_events,
    parse_register_procedural_steps,
)
from patent_client_agents.mcp.tools.epo_ops import (
    get_epo_citations,
    get_epo_equivalents,
    get_epo_procedural_steps,
    get_epo_register_biblio,
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

_REGISTER_BIBLIO_XML = """\
<ops:world-patent-data xmlns:ops="http://ops.epo.org"
                       xmlns:reg="http://www.epo.org/register">
  <ops:register-search total-result-count="1">
    <reg:register-documents produced-by="RO">
        <reg:register-document status="NO OPPOSITION FILED WITHIN TIMELIMIT"
          produced-by="RO" lang="en" dtd-version="1.0" date-produced="20260730">
        <reg:ep-patent-statuses>
          <reg:ep-patent-status change-date="20030212" status-code="8">Patent granted</reg:ep-patent-status>
        </reg:ep-patent-statuses>
        <reg:bibliographic-data status="NO OPPOSITION FILED WITHIN TIMELIMIT"
            lang="en" id="EP99203729P" country="EP">
          <reg:publication-reference change-date="20000517" change-gazette-num="2000/20"
              value-valid-for-publications="A1 B1" id="EP1000000A1">
            <reg:document-id lang="en">
              <reg:country>EP</reg:country><reg:doc-number>1000000</reg:doc-number>
              <reg:kind>A1</reg:kind><reg:date>20000517</reg:date>
            </reg:document-id>
          </reg:publication-reference>
          <reg:publication-reference change-date="20030212" change-gazette-num="2003/07"
              value-valid-for-publications="B1" id="EP1000000B1">
            <reg:document-id lang="de">
              <reg:country>EP</reg:country><reg:doc-number>1000000</reg:doc-number>
              <reg:kind>B1</reg:kind><reg:date>20030212</reg:date>
            </reg:document-id>
          </reg:publication-reference>
          <reg:classifications-ipcr change-date="20030212" change-gazette-num="2003/07">
            <reg:classification-ipcr><reg:text>B28B5/02, B28B7/00</reg:text></reg:classification-ipcr>
          </reg:classifications-ipcr>
          <reg:application-reference appl-type="regional" change-date="19991108">
            <reg:document-id>
              <reg:country>EP</reg:country><reg:doc-number>99203729</reg:doc-number>
              <reg:date>19991108</reg:date>
            </reg:document-id>
          </reg:application-reference>
          <reg:language-of-filing change-date="19991108" change-gazette-num="1999/45">nl</reg:language-of-filing>
          <reg:language-of-publication change-date="20000517">en</reg:language-of-publication>
          <reg:priority-claims change-date="19991108" change-gazette-num="1999/45">
            <reg:priority-claim sequence="1" kind="national">
              <reg:country>NL</reg:country><reg:doc-number>19981010536</reg:doc-number>
              <reg:date>19981112</reg:date>
              <reg:office-of-filing><reg:country>NL</reg:country></reg:office-of-filing>
            </reg:priority-claim>
          </reg:priority-claims>
          <reg:priority-claims change-date="20000114" change-gazette-num="2000/03"/>
          <reg:parties>
            <reg:applicants transfer-of-rights="no" change-date="19991108"
                change-gazette-num="1999/45">
              <reg:applicant app-type="applicant" designation="all" sequence="1">
                <reg:addressbook>
                  <reg:name>Example Applicant BV</reg:name>
                  <reg:address>
                    <reg:address-1>Example Street 1</reg:address-1>
                    <reg:country>NL</reg:country>
                  </reg:address>
                </reg:addressbook>
              </reg:applicant>
            </reg:applicants>
            <reg:applicants transfer-of-rights="yes" change-date="20030212"
                change-gazette-num="2003/07">
              <reg:applicant app-type="proprietor" designation="as-indicated" sequence="1">
                <reg:addressbook>
                  <reg:name>New Owner NV</reg:name>
                  <reg:address><reg:country>BE</reg:country></reg:address>
                </reg:addressbook>
                <reg:designated-states><reg:country>DE</reg:country></reg:designated-states>
              </reg:applicant>
            </reg:applicants>
            <reg:inventors change-date="19991108">
              <reg:inventor sequence="1" wishes-to-be-published="yes">
                <reg:addressbook><reg:first-name>Ada</reg:first-name><reg:last-name>Lovelace</reg:last-name></reg:addressbook>
              </reg:inventor>
            </reg:inventors>
            <reg:agents change-date="19991108">
              <reg:agent rep-type="attorney" sequence="1" et-al="yes">
                <reg:addressbook>
                  <reg:name>Example Patent Firm</reg:name><reg:registered-number>12345</reg:registered-number>
                </reg:addressbook>
              </reg:agent>
            </reg:agents>
          </reg:parties>
          <reg:designation-of-states change-date="20000517" change-gazette-num="2000/20">
            <reg:designation-pct>
              <reg:regional>
                <reg:region><reg:country>EP</reg:country></reg:region>
                <reg:country>AT</reg:country><reg:country>DE</reg:country>
              </reg:regional>
              <reg:national><reg:country>GB</reg:country></reg:national>
            </reg:designation-pct>
            <reg:exclusion-from-designation>
              <reg:regional>
                <reg:region><reg:country>EP</reg:country></reg:region>
                <reg:country>TR</reg:country>
              </reg:regional>
            </reg:exclusion-from-designation>
          </reg:designation-of-states>
          <reg:invention-title lang="en" change-date="20000517"
              change-gazette-num="2000/20">Apparatus for manufacturing green bricks</reg:invention-title>
          <reg:term-of-grant change-date="20030212" change-gazette-num="2003/07">
            <reg:lapsed-in-country><reg:country>AT</reg:country><reg:date>20030212</reg:date></reg:lapsed-in-country>
          </reg:term-of-grant>
          <reg:term-of-grant change-date="20030625" change-gazette-num="2003/26">
            <reg:lapsed-in-country><reg:country>AT</reg:country><reg:date>20030212</reg:date></reg:lapsed-in-country>
            <reg:lapsed-in-country><reg:country>SE</reg:country><reg:date>20030625</reg:date></reg:lapsed-in-country>
          </reg:term-of-grant>
        </reg:bibliographic-data>
      </reg:register-document>
    </reg:register-documents>
  </ops:register-search>
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
    assert parse_register_biblio(empty, epo_number="EP1").publication_references == []
    assert parse_register_events(empty, epo_number="EP1").events == []
    assert parse_register_procedural_steps(empty, epo_number="EP1").procedural_steps == []


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


def test_parse_register_biblio_preserves_status_parties_and_state_scope() -> None:
    result = parse_register_biblio(_REGISTER_BIBLIO_XML, epo_number="EP1000000")

    assert result.bibliographic_status == "NO OPPOSITION FILED WITHIN TIMELIMIT"
    assert result.bibliographic_language == "en"
    assert result.application_id == "EP99203729P"
    assert [reference.documents[0].kind for reference in result.publication_references] == [
        "A1",
        "B1",
    ]
    assert result.publication_references[0].change_gazette_number == "2000/20"
    assert result.publication_references[0].valid_for_publications == ["A1", "B1"]
    assert result.publication_references[1].documents[0].language == "de"
    assert result.application_references[0].documents[0].doc_number == "99203729"
    assert result.application_references[0].application_type == "regional"
    assert len(result.priority_claim_sets) == 2
    assert result.priority_claim_sets[0].claims[0].country == "NL"
    assert result.priority_claim_sets[0].claims[0].office_of_filing == "NL"
    assert result.priority_claim_sets[1].claims == []
    assert result.patent_statuses[0].text == "Patent granted"
    assert result.patent_statuses[0].status_code == "8"
    assert result.titles[0].text == "Apparatus for manufacturing green bricks"
    assert result.titles[0].change_gazette_number == "2000/20"
    assert result.filing_languages[0].text == "nl"
    assert result.filing_languages[0].change_gazette_number == "1999/45"
    assert [party_set.role for party_set in result.party_sets] == [
        "applicant",
        "applicant",
        "inventor",
        "representative",
    ]
    assert result.party_sets[0].parties[0].name == "Example Applicant BV"
    assert result.party_sets[0].parties[0].address_country == "NL"
    assert result.party_sets[1].transfer_of_rights == "yes"
    assert result.party_sets[1].parties[0].party_type == "proprietor"
    assert result.party_sets[1].parties[0].designation == "as-indicated"
    assert result.party_sets[1].parties[0].designated_states == ["DE"]
    assert result.party_sets[2].parties[0].wishes_to_be_published is True
    assert result.party_sets[3].parties[0].registered_number == "12345"
    assert result.party_sets[3].parties[0].et_al is True
    assert result.classification_sets[0].classifications == ["B28B5/02, B28B7/00"]
    assert [
        (designation.scope, designation.country, designation.excluded)
        for designation in result.state_designation_sets[0].designations
    ] == [
        ("regional", "AT", False),
        ("regional", "DE", False),
        ("national", "GB", False),
        ("regional", "TR", True),
    ]
    assert result.state_designation_sets[0].change_gazette_number == "2000/20"
    assert [lapse.country for lapse in result.term_of_grant_snapshots[0].lapses] == ["AT"]
    assert [lapse.country for lapse in result.term_of_grant_snapshots[1].lapses] == ["AT", "SE"]


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
async def test_client_uses_exact_structured_record_paths() -> None:
    client = object.__new__(EpoOpsClient)
    client._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            SimpleNamespace(text=_CITATIONS_XML),
            SimpleNamespace(text=_EQUIVALENTS_XML),
            SimpleNamespace(text=_REGISTER_BIBLIO_XML),
        ]
    )

    await client.fetch_citations(number=" ep 1000000 a1 ")
    await client.fetch_equivalents(number=" ep 1000000 a1 ")
    await client.fetch_register_biblio(number=" ep 1000000 ")

    assert client._request.await_args_list[0].args == (  # type: ignore[attr-defined]
        "GET",
        "/rest-services/published-data/publication/docdb/EP1000000A1/biblio",
    )
    assert client._request.await_args_list[1].args == (  # type: ignore[attr-defined]
        "GET",
        "/rest-services/published-data/publication/docdb/EP1000000A1/equivalents",
    )
    assert client._request.await_args_list[2].args == (  # type: ignore[attr-defined]
        "GET",
        "/rest-services/register/publication/epodoc/EP1000000/biblio",
    )


@pytest.mark.asyncio
async def test_client_register_helpers_delegate_to_supported_sub_endpoints() -> None:
    client = object.__new__(EpoOpsClient)
    client.fetch_register = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            _REGISTER_BIBLIO_XML,
            _REGISTER_EVENTS_XML,
            _REGISTER_STEPS_XML,
        ]
    )

    biblio = await client.fetch_register_biblio(number="ep1000000")
    events = await client.fetch_register_events(number="ep1000000")
    steps = await client.fetch_register_procedural_steps(number="ep1000000")

    assert biblio.publication_references[0].documents[0].kind == "A1"
    assert events.events[0].event_code == "0009012"
    assert steps.procedural_steps[0].step_code == "RFEE"
    assert client.fetch_register.await_args_list[0].kwargs["sub"] == "biblio"  # type: ignore[attr-defined]
    assert client.fetch_register.await_args_list[1].kwargs["sub"] == "events"  # type: ignore[attr-defined]
    assert client.fetch_register.await_args_list[2].kwargs["sub"] == "procedural-steps"  # type: ignore[attr-defined]


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
            get_epo_register_biblio,
            "fetch_register_biblio",
            RegisterBiblioResponse(epo_number="EP1000000"),
            "EP1000000",
            "/register/publication/epodoc/EP1000000/biblio",
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
    client.fetch_citations = AsyncMock(side_effect=lambda *, number: responses[number])

    with _patch_client(client):
        result = await get_epo_citations(["EP1A1", "EP2A1"])

    assert [item["publication_number"] for item in result.items] == [
        "EP1A1",
        "EP2A1",
    ]

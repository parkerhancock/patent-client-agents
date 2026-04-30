"""Tests for Google Patents Pydantic models."""

from __future__ import annotations

from patent_client_agents.google_patents.client import (
    ChemicalCompound,
    ChildApplication,
    Concept,
    CountryFiling,
    CpcClassification,
    Definition,
    DetailedNpl,
    ExternalLink,
    FamilyMember,
    Landscape,
    LegalEvent,
    NonPatentLiterature,
    PatentCitation,
    PriorityApplication,
    _resolve_expiration_date,
)


class TestCpcClassification:
    """Tests for CpcClassification model."""

    def test_creates_with_code_and_description(self) -> None:
        cpc = CpcClassification(code="H04L9/32", description="Key management")
        assert cpc.code == "H04L9/32"
        assert cpc.description == "Key management"

    def test_description_defaults_empty(self) -> None:
        cpc = CpcClassification(code="G06F21/00")
        assert cpc.code == "G06F21/00"
        assert cpc.description == ""


class TestPatentCitation:
    """Tests for PatentCitation model."""

    def test_creates_full_citation(self) -> None:
        citation = PatentCitation(
            publication_number="US7654321B2",
            publication_date="2010-02-02",
            assignee="Example Corp",
            title="Security Method",
            examiner_cited=True,
        )
        assert citation.publication_number == "US7654321B2"
        assert citation.examiner_cited is True

    def test_defaults(self) -> None:
        citation = PatentCitation(publication_number="US1234567A")
        assert citation.publication_date is None
        assert citation.assignee is None
        assert citation.title is None
        assert citation.examiner_cited is False


class TestFamilyMember:
    """Tests for FamilyMember model."""

    def test_creates_full_member(self) -> None:
        member = FamilyMember(
            application_number="US15123456",
            publication_number="US10123456B2",
            status="Active",
            priority_date="2018-01-01",
            filing_date="2018-06-15",
            title="Test Patent",
        )
        assert member.application_number == "US15123456"
        assert member.status == "Active"

    def test_defaults(self) -> None:
        member = FamilyMember(application_number="US15123456")
        assert member.publication_number is None
        assert member.status is None
        assert member.priority_date is None


class TestCountryFiling:
    """Tests for CountryFiling model."""

    def test_creates_full_filing(self) -> None:
        filing = CountryFiling(
            country_code="JP",
            count=3,
            representative_publication="JP2020123456A",
        )
        assert filing.country_code == "JP"
        assert filing.count == 3

    def test_defaults(self) -> None:
        filing = CountryFiling(country_code="US")
        assert filing.count == 1
        assert filing.representative_publication is None


class TestPriorityApplication:
    """Tests for PriorityApplication model."""

    def test_creates_full_priority(self) -> None:
        priority = PriorityApplication(
            application_number="US62123456",
            publication_number="US2020123456A1",
            priority_date="2019-01-15",
            filing_date="2020-01-14",
            title="Provisional Title",
        )
        assert priority.application_number == "US62123456"
        assert priority.priority_date == "2019-01-15"

    def test_defaults(self) -> None:
        priority = PriorityApplication(application_number="US62123456")
        assert priority.publication_number is None
        assert priority.priority_date is None


class TestLegalEvent:
    """Tests for LegalEvent model."""

    def test_creates_full_event(self) -> None:
        event = LegalEvent(
            date="2021-05-15",
            title="Assignment",
            assignee="New Owner Inc",
            assignor="Old Owner Corp",
            status="Recorded",
        )
        assert event.date == "2021-05-15"
        assert event.title == "Assignment"
        assert event.assignee == "New Owner Inc"

    def test_defaults(self) -> None:
        event = LegalEvent()
        assert event.date is None
        assert event.title is None
        assert event.assignee is None


class TestNonPatentLiterature:
    """Tests for NonPatentLiterature model."""

    def test_creates_full_npl(self) -> None:
        npl = NonPatentLiterature(
            citation="Smith et al., Journal of Example, 2020",
            examiner_cited=True,
        )
        assert npl.citation == "Smith et al., Journal of Example, 2020"
        assert npl.examiner_cited is True

    def test_defaults(self) -> None:
        npl = NonPatentLiterature(citation="Test citation")
        assert npl.examiner_cited is False


class TestConcept:
    """Tests for Concept model."""

    def test_creates_full_concept(self) -> None:
        concept = Concept(name="Machine Learning", image_url="https://example.com/img.png")
        assert concept.name == "Machine Learning"
        assert concept.image_url == "https://example.com/img.png"

    def test_defaults(self) -> None:
        concept = Concept(name="Neural Network")
        assert concept.image_url is None


class TestLandscape:
    """Tests for Landscape model."""

    def test_creates_full_landscape(self) -> None:
        landscape = Landscape(name="Artificial Intelligence", type="technology")
        assert landscape.name == "Artificial Intelligence"
        assert landscape.type == "technology"

    def test_defaults(self) -> None:
        landscape = Landscape(name="Cryptography")
        assert landscape.type == ""


class TestDefinition:
    """Tests for Definition model."""

    def test_creates_full_definition(self) -> None:
        definition = Definition(
            term="processor",
            definition="A computing device that executes instructions",
            paragraph="[0015]",
        )
        assert definition.term == "processor"
        assert definition.definition == "A computing device that executes instructions"
        assert definition.paragraph == "[0015]"

    def test_defaults(self) -> None:
        definition = Definition(term="memory", definition="A storage device")
        assert definition.paragraph == ""


class TestChildApplication:
    """Tests for ChildApplication model."""

    def test_creates_full_child(self) -> None:
        child = ChildApplication(
            application_number="US16234567",
            relation_type="continuation",
            publication_number="US11234567B2",
            priority_date="2018-01-01",
            filing_date="2020-03-15",
            title="Child Patent",
        )
        assert child.application_number == "US16234567"
        assert child.relation_type == "continuation"

    def test_defaults(self) -> None:
        child = ChildApplication(application_number="US16234567")
        assert child.relation_type is None
        assert child.publication_number is None


class TestDetailedNpl:
    """Tests for DetailedNpl model."""

    def test_creates_full_npl(self) -> None:
        npl = DetailedNpl(
            title="Deep Learning for Patents",
            url="https://example.com/paper.pdf",
        )
        assert npl.title == "Deep Learning for Patents"
        assert npl.url == "https://example.com/paper.pdf"

    def test_defaults(self) -> None:
        npl = DetailedNpl(title="Research Paper")
        assert npl.url is None


class TestChemicalCompound:
    """Tests for ChemicalCompound model."""

    def test_creates_full_compound(self) -> None:
        compound = ChemicalCompound(
            id="CID12345",
            name="Example Compound",
            smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
            inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            domain="pharmaceutical",
            similarity="0.95",
        )
        assert compound.id == "CID12345"
        assert compound.smiles == "CC(=O)OC1=CC=CC=C1C(=O)O"
        assert compound.inchi_key == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"

    def test_defaults(self) -> None:
        compound = ChemicalCompound()
        assert compound.id is None
        assert compound.name is None
        assert compound.smiles is None


class TestExternalLink:
    """Tests for ExternalLink model."""

    def test_creates_full_link(self) -> None:
        link = ExternalLink(
            url="https://patents.google.com/patent/US10123456",
            id="google-patents",
            name="Google Patents",
        )
        assert link.url == "https://patents.google.com/patent/US10123456"
        assert link.id == "google-patents"
        assert link.name == "Google Patents"

    def test_defaults(self) -> None:
        link = ExternalLink(url="https://example.com")
        assert link.id is None
        assert link.name is None


class TestResolveExpirationDate:
    """Tests for _resolve_expiration_date — priority+20y fallback when GP is empty."""

    def test_uses_gp_value_when_present(self) -> None:
        result, estimated = _resolve_expiration_date("2038-03-15", "2018-03-15")
        assert result == "2038-03-15"
        assert estimated is False

    def test_falls_back_to_priority_plus_20_when_gp_empty(self) -> None:
        result, estimated = _resolve_expiration_date("", "2013-03-15")
        assert result == "2033-03-15"
        assert estimated is True

    def test_returns_empty_when_neither_available(self) -> None:
        result, estimated = _resolve_expiration_date("", None)
        assert result == ""
        assert estimated is False

    def test_returns_empty_when_priority_unparseable(self) -> None:
        result, estimated = _resolve_expiration_date("", "not-a-date")
        assert result == ""
        assert estimated is False

    def test_handles_leap_day_priority_in_non_leap_target(self) -> None:
        # 1880-02-29 + 20y → 1900-02-29 doesn't exist (1900 is not a leap year),
        # so the helper clamps to Feb 28.
        result, estimated = _resolve_expiration_date("", "1880-02-29")
        assert result == "1900-02-28"
        assert estimated is True

    def test_priority_with_whitespace_is_stripped(self) -> None:
        result, estimated = _resolve_expiration_date("", "  2010-06-01  ")
        assert result == "2030-06-01"
        assert estimated is True

    def test_empty_priority_string_treated_as_missing(self) -> None:
        result, estimated = _resolve_expiration_date("", "")
        assert result == ""
        assert estimated is False

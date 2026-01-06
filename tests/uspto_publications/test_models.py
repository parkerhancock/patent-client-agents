"""Tests for USPTO Publications Pydantic models."""

import datetime as dt

from ip_tools.uspto_publications.models import (
    Applicant,
    Assignee,
    Claim,
    CpcCode,
    Document,
    DocumentStructure,
    ForeignPriorityApplication,
    ForeignReference,
    IntlCode,
    Inventor,
    NplReference,
    PublicSearchBiblio,
    PublicSearchBiblioPage,
    PublicSearchDocument,
    RelatedApplication,
    UsReference,
)


class TestClaim:
    """Tests for Claim model."""

    def test_basic_claim(self):
        """Test creating a basic claim."""
        claim = Claim(number=1, limitations=["A method comprising step A."])
        assert claim.number == 1
        assert "step A" in claim.limitations[0]

    def test_claim_text_property(self):
        """Test the text property."""
        claim = Claim(number=1, limitations=["First limitation", "Second limitation"])
        text = claim.text
        assert text.startswith("1.")
        assert "First limitation" in text
        assert "Second limitation" in text

    def test_independent_property(self):
        """Test independent claim detection."""
        independent = Claim(number=1, limitations=["A method."])
        dependent = Claim(number=2, limitations=["The method."], depends_on=[1])

        assert independent.independent is True
        assert dependent.independent is False

    def test_dependent_property(self):
        """Test dependent claim detection."""
        independent = Claim(number=1, limitations=["A method."])
        dependent = Claim(number=2, limitations=["The method."], depends_on=[1])

        assert independent.dependent is False
        assert dependent.dependent is True


class TestDocument:
    """Tests for Document model."""

    def test_basic_document(self):
        """Test creating a basic document."""
        doc = Document(
            abstract_html="<p>An abstract</p>",
            claim_statement="What is claimed:",
        )
        assert doc.abstract_html == "<p>An abstract</p>"
        assert doc.claim_statement == "What is claimed:"

    def test_default_claims_list(self):
        """Test claims default to empty list."""
        doc = Document()
        assert doc.claims == []


class TestDocumentStructure:
    """Tests for DocumentStructure model."""

    def test_basic_structure(self):
        """Test creating a basic structure."""
        structure = DocumentStructure(
            number_of_claims=20,
            number_of_drawing_sheets=5,
            page_count=15,
        )
        assert structure.number_of_claims == 20
        assert structure.number_of_drawing_sheets == 5
        assert structure.page_count == 15

    def test_page_ranges(self):
        """Test page range fields."""
        structure = DocumentStructure(
            claims_start=10,
            claims_end=15,
            description_start=3,
            description_end=9,
        )
        assert structure.claims_start == 10
        assert structure.claims_end == 15


class TestUsReference:
    """Tests for UsReference model."""

    def test_basic_reference(self):
        """Test creating a US reference."""
        ref = UsReference(
            publication_number="US8830957B2",
            patentee_name="John Doe",
            cited_by_examiner=True,
        )
        assert ref.publication_number == "US8830957B2"
        assert ref.cited_by_examiner is True


class TestForeignReference:
    """Tests for ForeignReference model."""

    def test_basic_reference(self):
        """Test creating a foreign reference."""
        ref = ForeignReference(
            country_code="EP",
            patent_number="1234567",
            cited_by_examiner=False,
        )
        assert ref.country_code == "EP"
        assert ref.patent_number == "1234567"


class TestNplReference:
    """Tests for NplReference model."""

    def test_basic_reference(self):
        """Test creating an NPL reference."""
        ref = NplReference(
            citation="Smith et al., 'Machine Learning', 2020",
            cited_by_examiner=True,
        )
        assert "Smith" in ref.citation
        assert ref.cited_by_examiner is True


class TestRelatedApplication:
    """Tests for RelatedApplication model."""

    def test_basic_related_app(self):
        """Test creating a related application."""
        app = RelatedApplication(
            country_code="US",
            number="16/123456",
            filing_date=dt.date(2020, 1, 15),
            parent_status_code="CON",
        )
        assert app.country_code == "US"
        assert app.number == "16/123456"
        assert app.parent_status_code == "CON"


class TestForeignPriorityApplication:
    """Tests for ForeignPriorityApplication model."""

    def test_basic_priority(self):
        """Test creating a foreign priority application."""
        priority = ForeignPriorityApplication(
            country="JP",
            app_number="2020-123456",
            app_filing_date=dt.date(2020, 6, 15),
        )
        assert priority.country == "JP"
        assert priority.app_number == "2020-123456"


class TestInventor:
    """Tests for Inventor model."""

    def test_basic_inventor(self):
        """Test creating an inventor."""
        inventor = Inventor(
            name="John Doe",
            city="San Francisco",
            state="CA",
            country="US",
        )
        assert inventor.name == "John Doe"
        assert inventor.city == "San Francisco"


class TestApplicant:
    """Tests for Applicant model."""

    def test_basic_applicant(self):
        """Test creating an applicant."""
        applicant = Applicant(
            name="Tech Corporation",
            city="Seattle",
            state="WA",
            country="US",
            authority_type="assignee",
        )
        assert applicant.name == "Tech Corporation"
        assert applicant.authority_type == "assignee"


class TestAssignee:
    """Tests for Assignee model."""

    def test_basic_assignee(self):
        """Test creating an assignee."""
        assignee = Assignee(
            name="Big Tech Inc",
            city="Mountain View",
            state="CA",
            country="US",
            type_code="02",
        )
        assert assignee.name == "Big Tech Inc"
        assert assignee.type_code == "02"


class TestCpcCode:
    """Tests for CpcCode model."""

    def test_basic_cpc(self):
        """Test creating a CPC code."""
        cpc = CpcCode(
            cpc_class="H04L",
            cpc_subclass="9/32",
            version=dt.date(2023, 1, 1),
        )
        assert cpc.cpc_class == "H04L"
        assert cpc.cpc_subclass == "9/32"


class TestIntlCode:
    """Tests for IntlCode model."""

    def test_basic_intl(self):
        """Test creating an international class code."""
        intl = IntlCode(
            intl_class="G06F",
            intl_subclass="21/00",
            version=dt.date(2023, 1, 1),
        )
        assert intl.intl_class == "G06F"
        assert intl.intl_subclass == "21/00"


class TestPublicSearchDocument:
    """Tests for PublicSearchDocument model."""

    def test_basic_document(self):
        """Test creating a basic search document."""
        doc = PublicSearchDocument(
            guid="doc-123",
            publication_number="US8830957B2",
            publication_date=dt.date(2014, 9, 9),
            patent_title="Test Invention",
        )
        assert doc.guid == "doc-123"
        assert doc.publication_number == "US8830957B2"
        assert doc.patent_title == "Test Invention"

    def test_default_lists(self):
        """Test list fields default to empty."""
        doc = PublicSearchDocument()
        assert doc.inventors == []
        assert doc.applicants == []
        assert doc.assignees == []
        assert doc.us_references == []
        assert doc.foreign_references == []
        assert doc.npl_references == []

    def test_application_number_normalization(self):
        """Test application number is normalized (slashes and spaces removed)."""
        doc = PublicSearchDocument(appl_id="16/123456")
        assert doc.appl_id == "16123456"

    def test_design_application_normalization(self):
        """Test design application numbers are converted."""
        doc = PublicSearchDocument(appl_id="D123456")
        assert doc.appl_id == "29123456"


class TestPublicSearchBiblio:
    """Tests for PublicSearchBiblio model."""

    def test_basic_biblio(self):
        """Test creating a basic biblio record."""
        biblio = PublicSearchBiblio(
            guid="biblio-123",
            publication_number="US8830957B2",
            publication_date=dt.date(2014, 9, 9),
            patent_title="Test Patent",
            type="B2",
        )
        assert biblio.publication_number == "US8830957B2"
        assert biblio.type == "B2"

    def test_default_lists(self):
        """Test list fields default to empty."""
        biblio = PublicSearchBiblio()
        assert biblio.applicant_names == []
        assert biblio.assignee_names == []
        assert biblio.ipc_code == []


class TestPublicSearchBiblioPage:
    """Tests for PublicSearchBiblioPage model."""

    def test_empty_page(self):
        """Test empty search results page."""
        page = PublicSearchBiblioPage(
            num_found=0,
            per_page=25,
            page=1,
            docs=[],
        )
        assert page.num_found == 0
        assert len(page.docs) == 0

    def test_page_with_results(self):
        """Test page with results."""
        doc = PublicSearchBiblio(publication_number="US8830957B2")
        page = PublicSearchBiblioPage(
            num_found=1,
            per_page=25,
            page=1,
            docs=[doc],
        )
        assert page.num_found == 1
        assert len(page.docs) == 1
        assert page.docs[0].publication_number == "US8830957B2"

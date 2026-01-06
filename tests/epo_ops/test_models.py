"""Tests for EPO OPS Pydantic models."""

from ip_tools.epo_ops.models import (
    BiblioRecord,
    Claim,
    CpcClassificationItem,
    CpcSearchResult,
    DesignatedState,
    DocumentId,
    FamilyMember,
    LegalEvent,
    NumberConversionResponse,
    OppositionData,
    OppositionParty,
    ProceduralStep,
    RegisterBiblioResponse,
    RegisterEvent,
    RegisterSearchResult,
    SearchResponse,
    SearchResult,
    UnitaryPatentData,
)


class TestDocumentId:
    """Tests for DocumentId model."""

    def test_basic_creation(self):
        """Test creating a basic document ID."""
        doc = DocumentId(country="US", doc_number="10123456", kind="B2")
        assert doc.country == "US"
        assert doc.doc_number == "10123456"
        assert doc.kind == "B2"

    def test_optional_fields(self):
        """Test that all fields are optional."""
        doc = DocumentId()
        assert doc.country is None
        assert doc.doc_number is None
        assert doc.kind is None

    def test_alias_number(self):
        """Test the 'number' alias for doc_number."""
        doc = DocumentId(country="EP", number="1234567", kind="A1")
        assert doc.doc_number == "1234567"


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_basic_creation(self):
        """Test creating a search result."""
        result = SearchResult(
            docdb_number="EP1234567A1",
            country="EP",
            doc_number="1234567",
            kind="A1",
            publication_date="20200101",
            family_id="12345",
        )
        assert result.docdb_number == "EP1234567A1"
        assert result.country == "EP"
        assert result.family_id == "12345"


class TestSearchResponse:
    """Tests for SearchResponse model."""

    def test_empty_results(self):
        """Test response with no results."""
        response = SearchResponse(
            query="ta=test",
            total_results=0,
            range_begin=1,
            range_end=0,
            results=[],
        )
        assert response.total_results == 0
        assert len(response.results) == 0

    def test_with_results(self):
        """Test response with results."""
        results = [
            SearchResult(country="US", doc_number="123"),
            SearchResult(country="EP", doc_number="456"),
        ]
        response = SearchResponse(
            query="ta=robot",
            total_results=2,
            results=results,
        )
        assert response.total_results == 2
        assert len(response.results) == 2


class TestBiblioRecord:
    """Tests for BiblioRecord model."""

    def test_full_record(self):
        """Test creating a full bibliographic record."""
        record = BiblioRecord(
            docdb_number="EP1234567A1",
            family_id="12345",
            title="Test Invention",
            abstract="This is an abstract.",
            applicants=["ACME Corp", "XYZ Inc"],
            inventors=["John Doe", "Jane Smith"],
            ipc_classes=["H04L 9/32", "G06F 21/00"],
            cpc_classes=["H04L 9/3247"],
        )
        assert record.title == "Test Invention"
        assert len(record.applicants) == 2
        assert len(record.inventors) == 2
        assert len(record.ipc_classes) == 2

    def test_default_lists(self):
        """Test that list fields default to empty."""
        record = BiblioRecord()
        assert record.applicants == []
        assert record.inventors == []
        assert record.ipc_classes == []


class TestClaim:
    """Tests for Claim model."""

    def test_basic_claim(self):
        """Test creating a claim."""
        claim = Claim(
            number=1,
            text="A method for doing something.",
            depends_on=[],
            dependent_claims=[2, 3],
        )
        assert claim.number == 1
        assert "method" in claim.text
        assert len(claim.dependent_claims) == 2

    def test_dependent_claim(self):
        """Test a dependent claim."""
        claim = Claim(
            number=2,
            text="The method of claim 1, further comprising...",
            depends_on=[1],
        )
        assert claim.depends_on == [1]


class TestFamilyMember:
    """Tests for FamilyMember model."""

    def test_basic_member(self):
        """Test creating a family member."""
        member = FamilyMember(
            family_id="12345",
            publication_number="EP1234567A1",
            application_number="EP20200001",
        )
        assert member.family_id == "12345"
        assert member.publication_number == "EP1234567A1"


class TestLegalEvent:
    """Tests for LegalEvent model."""

    def test_basic_event(self):
        """Test creating a legal event."""
        event = LegalEvent(
            event_code="GRANT",
            event_date="20210615",
            event_country="EP",
            free_text="Patent granted",
        )
        assert event.event_code == "GRANT"
        assert event.event_date == "20210615"


class TestNumberConversionResponse:
    """Tests for NumberConversionResponse model."""

    def test_conversion(self):
        """Test number conversion response."""
        response = NumberConversionResponse(
            input_document=DocumentId(country="US", doc_number="2020123456", kind="A1"),
            output_document=DocumentId(country="US", doc_number="10123456", kind="B2"),
            service_version="1.0",
        )
        assert response.input_document.country == "US"
        assert response.output_document.doc_number == "10123456"


class TestRegisterModels:
    """Tests for EP Register models."""

    def test_designated_state(self):
        """Test DesignatedState model."""
        state = DesignatedState(
            country_code="DE",
            status="validated",
            effective_date="20210101",
        )
        assert state.country_code == "DE"
        assert state.status == "validated"

    def test_procedural_step(self):
        """Test ProceduralStep model."""
        step = ProceduralStep(
            phase="examination",
            step_code="RFEE",
            step_description="Request for examination",
            step_date="20200601",
            office="EPO",
        )
        assert step.phase == "examination"
        assert step.step_code == "RFEE"

    def test_register_event(self):
        """Test RegisterEvent model."""
        event = RegisterEvent(
            event_code="A1",
            event_date="20200315",
            event_description="Publication of application",
            bulletin_number="2020/12",
        )
        assert event.event_code == "A1"
        assert event.bulletin_number == "2020/12"

    def test_opposition_data(self):
        """Test OppositionData model."""
        opposition = OppositionData(
            opposition_date="20210901",
            status="pending",
            parties=[
                OppositionParty(name="Opponent Corp", country="DE", role="opponent"),
                OppositionParty(name="Patent Owner", country="US", role="patent_owner"),
            ],
        )
        assert opposition.status == "pending"
        assert len(opposition.parties) == 2

    def test_unitary_patent_data(self):
        """Test UnitaryPatentData model."""
        upp = UnitaryPatentData(
            upp_status="registered",
            registration_date="20230601",
            participating_states=["DE", "FR", "IT", "NL"],
        )
        assert upp.upp_status == "registered"
        assert len(upp.participating_states) == 4

    def test_register_search_result(self):
        """Test RegisterSearchResult model."""
        result = RegisterSearchResult(
            application_number="EP20200001",
            publication_number="EP1234567A1",
            title="Test Patent",
            applicants=["Test Corp"],
            status="granted",
        )
        assert result.application_number == "EP20200001"
        assert result.status == "granted"

    def test_register_biblio_response(self):
        """Test RegisterBiblioResponse model."""
        response = RegisterBiblioResponse(
            application_number="EP20200001",
            publication_number="EP1234567B1",
            grant_date="20220101",
            title="Test Patent",
            applicants=["Test Corp"],
            inventors=["Inventor One"],
            representatives=["Patent Attorney"],
            designated_states=[
                DesignatedState(country_code="DE"),
                DesignatedState(country_code="FR"),
            ],
            status="granted",
        )
        assert response.grant_date == "20220101"
        assert len(response.designated_states) == 2


class TestCpcModels:
    """Tests for CPC classification models."""

    def test_cpc_classification_item(self):
        """Test CpcClassificationItem model."""
        item = CpcClassificationItem(
            symbol="H04L 9/32",
            level=5,
            title="Authentication",
            not_allocatable=False,
        )
        assert item.symbol == "H04L 9/32"
        assert item.level == 5

    def test_cpc_search_result(self):
        """Test CpcSearchResult model."""
        result = CpcSearchResult(
            classification_symbol="G06F 21/00",
            percentage=85.5,
            title="Security arrangements",
        )
        assert result.classification_symbol == "G06F 21/00"
        assert result.percentage == 85.5

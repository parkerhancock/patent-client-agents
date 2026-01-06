"""Tests for USPTO ODP Pydantic models."""

from ip_tools.uspto_odp.models import (
    Address,
    Applicant,
    ApplicationRecord,
    Assignee,
    Assignment,
    Assignor,
    Attorney,
    BulkDataFile,
    BulkDataProduct,
    ChildContinuity,
    ContinuityBag,
    ForeignPriority,
    Inventor,
    ParentContinuity,
    PatentTermAdjustmentData,
    PtabTrialProceeding,
    SearchResponse,
)


class TestAddress:
    """Tests for Address model."""

    def test_basic_address(self):
        """Test basic address with camelCase fields."""
        addr = Address(
            cityName="San Francisco",
            geographicRegionCode="CA",
            countryCode="US",
            postalCode="94102",
        )
        assert addr.cityName == "San Francisco"
        assert addr.countryCode == "US"


class TestInventor:
    """Tests for Inventor model."""

    def test_basic_inventor(self):
        """Test basic inventor."""
        inventor = Inventor(
            inventorNameText="John Doe",
            firstName="John",
            lastName="Doe",
            countryCode="US",
        )
        assert inventor.inventorNameText == "John Doe"
        assert inventor.firstName == "John"


class TestApplicant:
    """Tests for Applicant model."""

    def test_basic_applicant(self):
        """Test basic applicant."""
        applicant = Applicant(
            applicantNameText="ACME Corporation",
            countryCode="US",
        )
        assert applicant.applicantNameText == "ACME Corporation"


class TestAssignee:
    """Tests for Assignee model."""

    def test_basic_assignee(self):
        """Test basic assignee."""
        assignee = Assignee(
            assigneeNameText="Tech Corp Inc",
            assigneeCity="Seattle",
            assigneeGeographicRegionCode="WA",
            assigneeCountryCode="US",
        )
        assert assignee.assigneeNameText == "Tech Corp Inc"


class TestContinuityModels:
    """Tests for continuity models."""

    def test_parent_continuity(self):
        """Test ParentContinuity model - flexible model accepts any fields."""
        parent = ParentContinuity()
        assert parent is not None

    def test_child_continuity(self):
        """Test ChildContinuity model - flexible model accepts any fields."""
        child = ChildContinuity()
        assert child is not None

    def test_continuity_bag(self):
        """Test ContinuityBag model."""
        bag = ContinuityBag()
        assert bag is not None


class TestForeignPriority:
    """Tests for ForeignPriority model."""

    def test_basic_priority(self):
        """Test basic foreign priority - flexible model."""
        priority = ForeignPriority()
        assert priority is not None


class TestAttorney:
    """Tests for Attorney model."""

    def test_basic_attorney(self):
        """Test attorney record."""
        attorney = Attorney(
            registrationNumber="12345",
            firstName="Patent",
            lastName="Attorney",
        )
        assert attorney.registrationNumber == "12345"


class TestPatentTermAdjustmentData:
    """Tests for PatentTermAdjustmentData model."""

    def test_pta_data(self):
        """Test PTA data - flexible model."""
        pta = PatentTermAdjustmentData()
        assert pta is not None


class TestApplicationRecord:
    """Tests for ApplicationRecord model."""

    def test_basic_record(self):
        """Test basic application record."""
        record = ApplicationRecord(
            applicationNumberText="17/123456",
            filingDate="2021-01-15",
            inventionTitle="Test Invention",
        )
        assert record.applicationNumberText == "17/123456"
        assert record.inventionTitle == "Test Invention"


class TestSearchResponse:
    """Tests for SearchResponse model."""

    def test_empty_response(self):
        """Test empty search response."""
        response = SearchResponse(count=0, data=[])
        assert response.count == 0
        assert len(response.data) == 0


class TestAssignmentModels:
    """Tests for assignment models."""

    def test_assignor(self):
        """Test Assignor model - flexible model."""
        assignor = Assignor()
        assert assignor is not None

    def test_assignment(self):
        """Test Assignment model - flexible model."""
        assignment = Assignment()
        assert assignment is not None


class TestBulkDataModels:
    """Tests for bulk data models."""

    def test_bulk_data_file(self):
        """Test BulkDataFile model."""
        file = BulkDataFile(
            fileName="grants_2024_01.zip",
            fileSize=1024000,
        )
        assert file.fileName == "grants_2024_01.zip"

    def test_bulk_data_product(self):
        """Test BulkDataProduct model."""
        product = BulkDataProduct(
            productIdentifier="GRANT_FULL_TEXT",
            productShortName="Patent Grant Full Text",
            productDesc="Weekly patent grants in XML format",
        )
        assert product.productIdentifier == "GRANT_FULL_TEXT"


class TestPtabModels:
    """Tests for PTAB models."""

    def test_ptab_trial_proceeding(self):
        """Test PtabTrialProceeding model."""
        trial = PtabTrialProceeding(
            proceedingNumber="IPR2023-00001",
            proceedingTypeCategory="IPR",
            proceedingStatusCategory="Instituted",
        )
        assert trial.proceedingNumber == "IPR2023-00001"
        assert trial.proceedingTypeCategory == "IPR"

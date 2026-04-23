"""Tests for JPO models."""

from __future__ import annotations

from patent_client_agents.jpo.models import (
    ApiResult,
    ApplicantAttorney,
    ApplicantAttorneyClass,
    ApplicantCodeResponse,
    ApplicantNameResponse,
    ApplicationDocumentsData,
    CitedDocumentInfo,
    DesignProgressData,
    DivisionalApplicationInfo,
    DocumentContent,
    DocumentType,
    FiClassification,
    FTermClassification,
    IpcClassification,
    JplatpatFixedAddress,
    JplatpatUrlResponse,
    NumberReference,
    NumberReferenceResponse,
    NumberType,
    PatentProgressData,
    PatentProgressResponse,
    PctNationalPhaseData,
    PriorityInfo,
    ProcedureInfo,
    RefusalReasonInfo,
    RegistrationInfo,
    SimplifiedPatentProgressData,
    SimplifiedPatentProgressResponse,
    StatusCode,
    TrademarkProgressData,
)


class TestStatusCode:
    """Tests for StatusCode enum."""

    def test_success_value(self) -> None:
        assert StatusCode.SUCCESS.value == "100"

    def test_no_data_value(self) -> None:
        assert StatusCode.NO_DATA.value == "107"

    def test_daily_limit_value(self) -> None:
        assert StatusCode.DAILY_LIMIT_EXCEEDED.value == "203"

    def test_invalid_token_value(self) -> None:
        assert StatusCode.INVALID_TOKEN.value == "210"

    def test_all_codes_are_strings(self) -> None:
        for code in StatusCode:
            assert isinstance(code.value, str)


class TestNumberType:
    """Tests for NumberType enum."""

    def test_application_value(self) -> None:
        assert NumberType.APPLICATION.value == "01"

    def test_publication_value(self) -> None:
        assert NumberType.PUBLICATION.value == "02"

    def test_registration_value(self) -> None:
        assert NumberType.REGISTRATION.value == "06"

    def test_pct_application_value(self) -> None:
        assert NumberType.PCT_APPLICATION.value == "10"


class TestApplicantAttorneyClass:
    """Tests for ApplicantAttorneyClass enum."""

    def test_applicant_value(self) -> None:
        assert ApplicantAttorneyClass.APPLICANT.value == "1"

    def test_attorney_value(self) -> None:
        assert ApplicantAttorneyClass.ATTORNEY.value == "2"


class TestDocumentType:
    """Tests for DocumentType enum."""

    def test_biblio_value(self) -> None:
        assert DocumentType.BIBLIO.value == "S"

    def test_claims_value(self) -> None:
        assert DocumentType.CLAIMS.value == "L"

    def test_drawings_value(self) -> None:
        assert DocumentType.DRAWINGS.value == "Z"


class TestApiResult:
    """Tests for ApiResult model."""

    def test_creates_from_alias(self) -> None:
        result = ApiResult(
            statusCode="100",
            errorMessage="",
            remainAccessCount="50",
            data={"key": "value"},
        )
        assert result.status_code == "100"
        assert result.remain_access_count == "50"

    def test_creates_from_field_name(self) -> None:
        result = ApiResult.model_validate(
            {
                "statusCode": "100",
                "errorMessage": "",
                "remainAccessCount": "50",
            }
        )
        assert result.status_code == "100"

    def test_is_success_true(self) -> None:
        result = ApiResult(statusCode="100")
        assert result.is_success is True

    def test_is_success_false(self) -> None:
        result = ApiResult(statusCode="107")
        assert result.is_success is False

    def test_has_data_true(self) -> None:
        result = ApiResult(statusCode="100")
        assert result.has_data is True

    def test_has_data_false_no_data(self) -> None:
        result = ApiResult(statusCode="107")
        assert result.has_data is False

    def test_has_data_false_no_document(self) -> None:
        result = ApiResult(statusCode="108")
        assert result.has_data is False

    def test_defaults(self) -> None:
        result = ApiResult(statusCode="100")
        assert result.error_message == ""
        assert result.remain_access_count == ""
        assert result.data is None


class TestApplicantAttorney:
    """Tests for ApplicantAttorney model."""

    def test_creates_from_alias(self) -> None:
        applicant = ApplicantAttorney(
            applicantAttorneyCd="123456789",
            repeatNumber="01",
            name="Test Company",
            applicantAttorneyClass="1",
        )
        assert applicant.applicant_attorney_cd == "123456789"
        assert applicant.name == "Test Company"

    def test_defaults(self) -> None:
        applicant = ApplicantAttorney()
        assert applicant.applicant_attorney_cd == ""
        assert applicant.name == ""


class TestPriorityInfo:
    """Tests for PriorityInfo model."""

    def test_creates_from_alias(self) -> None:
        priority = PriorityInfo(
            priorityNumber="US12345",
            priorityDate="2020-01-01",
            priorityCountryCd="US",
        )
        assert priority.priority_number == "US12345"
        assert priority.priority_country_cd == "US"


class TestDivisionalApplicationInfo:
    """Tests for DivisionalApplicationInfo model."""

    def test_creates_from_alias(self) -> None:
        div = DivisionalApplicationInfo(
            applicationNumber="2020123456",
            filingDate="2020-05-01",
            relationship="child",
        )
        assert div.application_number == "2020123456"
        assert div.relationship == "child"


class TestClassificationModels:
    """Tests for classification models."""

    def test_ipc_classification(self) -> None:
        ipc = IpcClassification(ipcCode="H01L21/00", ipcVersion="2020.01")
        assert ipc.ipc_code == "H01L21/00"
        assert ipc.ipc_version == "2020.01"

    def test_fi_classification(self) -> None:
        fi = FiClassification(fiCode="5F110AA01")
        assert fi.fi_code == "5F110AA01"

    def test_fterm_classification(self) -> None:
        fterm = FTermClassification(fTermTheme="5B035", fTerm="AA01")
        assert fterm.f_term_theme == "5B035"
        assert fterm.f_term == "AA01"


class TestProcedureInfo:
    """Tests for ProcedureInfo model."""

    def test_creates_from_alias(self) -> None:
        proc = ProcedureInfo(
            documentCd="A00",
            documentName="Request for Examination",
            receiptDate="2020-06-01",
            sendingDate="",
            documentNumber="12345",
        )
        assert proc.document_cd == "A00"
        assert proc.document_name == "Request for Examination"


class TestRefusalReasonInfo:
    """Tests for RefusalReasonInfo model."""

    def test_creates_from_alias(self) -> None:
        reason = RefusalReasonInfo(
            documentNumber="12345",
            sendingDate="2021-01-15",
            refusalReasonCd="29-1",
        )
        assert reason.refusal_reason_cd == "29-1"


class TestCitedDocumentInfo:
    """Tests for CitedDocumentInfo model."""

    def test_creates_from_alias(self) -> None:
        cite = CitedDocumentInfo(
            documentNumber="12345",
            citationCategory="X",
            citationDocument="JP2019-123456A",
        )
        assert cite.citation_category == "X"
        assert cite.citation_document == "JP2019-123456A"


class TestRegistrationInfo:
    """Tests for RegistrationInfo model."""

    def test_creates_from_alias(self) -> None:
        reg = RegistrationInfo(
            registrationNumber="7000001",
            registrationDate="2022-01-01",
            expirationDate="2042-01-01",
        )
        assert reg.registration_number == "7000001"
        assert reg.expiration_date == "2042-01-01"


class TestPatentProgressData:
    """Tests for PatentProgressData model."""

    def test_creates_full_model(self) -> None:
        data = PatentProgressData(
            applicationNumber="2020123456",
            inventionTitle="Test Invention",
            filingDate="2020-01-15",
            publicationNumber="2021-123456",
            publicationDate="2021-07-15",
            registrationNumber="7000001",
            registrationDate="2022-03-01",
        )
        assert data.application_number == "2020123456"
        assert data.invention_title == "Test Invention"

    def test_nested_lists_default_empty(self) -> None:
        data = PatentProgressData(applicationNumber="2020123456")
        assert data.applicant_attorney == []
        assert data.priority_info == []
        assert data.ipc_classification == []
        assert data.procedure_info == []

    def test_with_nested_objects(self) -> None:
        data = PatentProgressData.model_validate(
            {
                "applicationNumber": "2020123456",
                "inventionTitle": "Test",
                "applicantAttorney": [{"applicantAttorneyCd": "123", "name": "Test Corp"}],
                "ipcClassification": [{"ipcCode": "H01L21/00", "ipcVersion": "2020"}],
            }
        )
        assert len(data.applicant_attorney) == 1
        assert data.applicant_attorney[0].name == "Test Corp"
        assert len(data.ipc_classification) == 1


class TestSimplifiedPatentProgressData:
    """Tests for SimplifiedPatentProgressData model."""

    def test_creates_model(self) -> None:
        data = SimplifiedPatentProgressData(
            applicationNumber="2020123456",
            inventionTitle="Test Invention",
        )
        assert data.application_number == "2020123456"

    def test_has_procedure_info(self) -> None:
        data = SimplifiedPatentProgressData.model_validate(
            {
                "applicationNumber": "2020123456",
                "procedureInfo": [{"documentCd": "A00", "documentName": "Test"}],
            }
        )
        assert len(data.procedure_info) == 1


class TestNumberReference:
    """Tests for NumberReference model."""

    def test_creates_from_alias(self) -> None:
        ref = NumberReference(
            applicationNumber="2020123456",
            publicationNumber="2021-123456",
            registrationNumber="7000001",
        )
        assert ref.application_number == "2020123456"
        assert ref.publication_number == "2021-123456"


class TestDocumentContent:
    """Tests for DocumentContent model."""

    def test_creates_from_alias(self) -> None:
        doc = DocumentContent(
            documentCd="A00",
            documentName="Application",
            receiptDate="2020-01-15",
            documentNumber="12345",
            documentType="S",
            contentUrl="https://example.com/doc",
            fileSize="12345",
        )
        assert doc.document_type == "S"
        assert doc.content_url == "https://example.com/doc"


class TestApplicationDocumentsData:
    """Tests for ApplicationDocumentsData model."""

    def test_creates_model(self) -> None:
        data = ApplicationDocumentsData.model_validate(
            {
                "applicationNumber": "2020123456",
                "documents": [{"documentCd": "A00", "documentName": "Test"}],
                "zipUrl": "https://example.com/docs.zip",
            }
        )
        assert data.application_number == "2020123456"
        assert len(data.documents) == 1
        assert data.zip_url == "https://example.com/docs.zip"


class TestJplatpatFixedAddress:
    """Tests for JplatpatFixedAddress model."""

    def test_creates_from_alias(self) -> None:
        addr = JplatpatFixedAddress(
            applicationNumber="2020123456",
            jplatpatUrl="https://www.j-platpat.inpit.go.jp/c1801/...",
        )
        assert addr.jplatpat_url.startswith("https://")


class TestPctNationalPhaseData:
    """Tests for PctNationalPhaseData model."""

    def test_creates_from_alias(self) -> None:
        data = PctNationalPhaseData(
            internationalApplicationNumber="PCT/JP2020/001234",
            internationalPublicationNumber="WO2020/123456",
            nationalApplicationNumber="2021-550001",
        )
        assert data.international_application_number == "PCT/JP2020/001234"
        assert data.national_application_number == "2021-550001"


class TestDesignProgressData:
    """Tests for DesignProgressData model."""

    def test_creates_model(self) -> None:
        data = DesignProgressData(
            applicationNumber="2020012345",
            designTitle="Electronic Device",
            filingDate="2020-03-01",
        )
        assert data.application_number == "2020012345"
        assert data.design_title == "Electronic Device"


class TestTrademarkProgressData:
    """Tests for TrademarkProgressData model."""

    def test_creates_model(self) -> None:
        data = TrademarkProgressData(
            applicationNumber="2020054321",
            trademarkName="TEST MARK",
            filingDate="2020-04-01",
            goodsServices=["Class 9: Computers", "Class 42: Software services"],
        )
        assert data.application_number == "2020054321"
        assert data.trademark_name == "TEST MARK"
        assert len(data.goods_services) == 2


class TestPatentProgressResponse:
    """Tests for PatentProgressResponse wrapper."""

    def test_data_property_with_data(self) -> None:
        response = PatentProgressResponse(
            result=ApiResult(
                statusCode="100",
                data={
                    "applicationNumber": "2020123456",
                    "inventionTitle": "Test",
                },
            )
        )
        assert response.data is not None
        assert response.data.application_number == "2020123456"

    def test_data_property_without_data(self) -> None:
        response = PatentProgressResponse(result=ApiResult(statusCode="107", data=None))
        assert response.data is None


class TestSimplifiedPatentProgressResponse:
    """Tests for SimplifiedPatentProgressResponse wrapper."""

    def test_data_property_with_data(self) -> None:
        response = SimplifiedPatentProgressResponse(
            result=ApiResult(
                statusCode="100",
                data={"applicationNumber": "2020123456"},
            )
        )
        assert response.data is not None

    def test_data_property_without_data(self) -> None:
        response = SimplifiedPatentProgressResponse(result=ApiResult(statusCode="107"))
        assert response.data is None


class TestApplicantNameResponse:
    """Tests for ApplicantNameResponse wrapper."""

    def test_applicants_property_with_data(self) -> None:
        response = ApplicantNameResponse(
            result=ApiResult(
                statusCode="100",
                data={"applicantAttorney": [{"applicantAttorneyCd": "123", "name": "Test"}]},
            )
        )
        assert len(response.applicants) == 1
        assert response.applicants[0].name == "Test"

    def test_applicants_property_empty(self) -> None:
        response = ApplicantNameResponse(result=ApiResult(statusCode="107"))
        assert response.applicants == []


class TestApplicantCodeResponse:
    """Tests for ApplicantCodeResponse wrapper."""

    def test_applicants_property_with_data(self) -> None:
        response = ApplicantCodeResponse(
            result=ApiResult(
                statusCode="100",
                data={"applicantAttorney": [{"applicantAttorneyCd": "123456789", "name": "Test"}]},
            )
        )
        assert len(response.applicants) == 1


class TestNumberReferenceResponse:
    """Tests for NumberReferenceResponse wrapper."""

    def test_references_property_with_data(self) -> None:
        response = NumberReferenceResponse(
            result=ApiResult(
                statusCode="100",
                data={
                    "caseNumberReference": [
                        {
                            "applicationNumber": "2020123456",
                            "publicationNumber": "2021-123456",
                        }
                    ]
                },
            )
        )
        assert len(response.references) == 1
        assert response.references[0].application_number == "2020123456"

    def test_references_property_empty(self) -> None:
        response = NumberReferenceResponse(result=ApiResult(statusCode="107"))
        assert response.references == []


class TestJplatpatUrlResponse:
    """Tests for JplatpatUrlResponse wrapper."""

    def test_url_property_with_data(self) -> None:
        response = JplatpatUrlResponse(
            result=ApiResult(
                statusCode="100",
                data={"jplatpatUrl": "https://www.j-platpat.inpit.go.jp/..."},
            )
        )
        assert response.url == "https://www.j-platpat.inpit.go.jp/..."

    def test_url_property_without_data(self) -> None:
        response = JplatpatUrlResponse(result=ApiResult(statusCode="107"))
        assert response.url is None

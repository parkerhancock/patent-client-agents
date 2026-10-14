"""Tests for JPO models — built from real production payloads (2026-05-07)."""

from __future__ import annotations

from patent_client_agents.jpo.models import (
    ApiResult,
    DocumentBundleResult,
    PatentProgressData,
    PctNationalPhaseData,
    RegistrationInfo,
    TrademarkProgressData,
)

# =============================================================================
# Enum tests
# =============================================================================


# =============================================================================
# ApiResult
# =============================================================================


class TestApiResult:
    def test_is_success_true(self) -> None:
        assert ApiResult(statusCode="100").is_success is True

    def test_is_success_false(self) -> None:
        assert ApiResult(statusCode="107").is_success is False


# =============================================================================
# Component models
# =============================================================================


# =============================================================================
# Patent progress
# =============================================================================


class TestPatentProgressData:
    def test_with_real_priority_payload(self) -> None:
        data = PatentProgressData.model_validate(
            {
                "applicationNumber": "2020123456",
                "inventionTitle": "立体配線構造体の製造方法",
                "applicantAttorney": [
                    {
                        "applicantAttorneyCd": "000114400",
                        "name": "メイショウ株式会社",
                        "applicantAttorneyClass": "1",
                    }
                ],
                "priorityRightInformation": [
                    {
                        "nationalPriorityLawCd": "1",
                        "nationalPriorityApplicationNumber": "2019210418",
                        "nationalPriorityDate": "20191121",
                    }
                ],
                "bibliographyInformation": [
                    {
                        "numberType": "01",
                        "number": "2020123456",
                        "documentList": [],
                    }
                ],
                "parentApplicationInformation": {},
                "divisionalApplicationInformation": [],
            }
        )
        assert len(data.applicant_attorney) == 1
        assert data.applicant_attorney[0].name == "メイショウ株式会社"
        assert len(data.priority_right_information) == 1
        assert (
            data.priority_right_information[0].national_priority_application_number == "2019210418"
        )
        assert len(data.bibliography_information) == 1
        # Empty parentApplicationInformation object materialises to a stub
        # ParentApplicationInfo (not None) — that's acceptable.
        assert data.parent_application_information is not None
        assert data.parent_application_information.parent_application_number == ""


# =============================================================================
# Divisional info (top-level wrapper)
# =============================================================================


# =============================================================================
# Number reference
# =============================================================================


# =============================================================================
# Citations
# =============================================================================


# =============================================================================
# Registration
# =============================================================================


class TestRegistrationInfo:
    def test_patent_shape(self) -> None:
        reg = RegistrationInfo.model_validate(
            {
                "applicationNumber": "2020123456",
                "filingDate": "20200720",
                "registrationNumber": "7533889",
                "registrationDate": "20240805",
                "decisionDate": "20240704",
                "rightPersonInformation": [
                    {"rightPersonCd": "000114400", "rightPersonName": "メイショウ株式会社"}
                ],
                "inventionTitle": "立体配線構造体の製造方法",
                "numberOfClaims": "005",
                "expireDate": "20400720",
                "nextPensionPaymentDate": "20270805",
                "lastPaymentYearly": "03",
                "erasureIdentifier": "00",
                "updateDate": "20240821",
            }
        )
        assert reg.registration_number == "7533889"
        assert reg.number_of_claims == "005"
        assert len(reg.right_person_information) == 1
        assert reg.right_person_information[0].right_person_name == "メイショウ株式会社"


# =============================================================================
# PCT national phase
# =============================================================================


class TestPctNationalPhaseData:
    def test_minimal(self) -> None:
        data = PctNationalPhaseData(applicationNumber="2021550001")
        assert data.application_number == "2021550001"
        # Backwards-compat alias.
        assert data.national_application_number == "2021550001"


# =============================================================================
# Document bundle
# =============================================================================


class TestDocumentBundleResult:
    def test_inline_zip(self) -> None:
        bundle = DocumentBundleResult(
            application_number="2020123456",
            zip_bytes=b"PK\x03\x04...",
            content_type="application/zip",
        )
        assert bundle.zip_bytes is not None
        assert bundle.is_empty is False

    def test_oversize_redirect(self) -> None:
        bundle = DocumentBundleResult(
            application_number="2020123456",
            download_url="https://example.com/big.zip",
            content_type="application/json",
        )
        assert bundle.zip_bytes is None
        assert bundle.download_url == "https://example.com/big.zip"
        assert bundle.is_empty is False

    def test_empty(self) -> None:
        bundle = DocumentBundleResult(application_number="2020123456")
        assert bundle.is_empty is True


# =============================================================================
# Design / trademark
# =============================================================================


class TestTrademarkProgressData:
    def test_real_payload(self) -> None:
        data = TrademarkProgressData.model_validate(
            {
                "applicationNumber": "2024123456",
                "trademarkForDisplay": "メタンレス和牛",
                "transliteration": {"0": "メタンレス", "1": "メタンレスワギュー"},
                "viennaClass": {},
                "goodsServiceInformation": [
                    {
                        "goodsServiceClass": "29",
                        "goodsServiceName": "牛肉",
                        "similarCode": "32A01",
                    }
                ],
                "filingDate": "20241118",
            }
        )
        assert data.trademark_for_display == "メタンレス和牛"
        # Backwards-compat alias.
        assert data.trademark_name == "メタンレス和牛"
        assert data.transliteration == {"0": "メタンレス", "1": "メタンレスワギュー"}
        assert len(data.goods_service_information) == 1
        # Flat backwards-compat list.
        assert data.goods_services == ["牛肉"]

"""Pydantic models for JPO Patent Information Retrieval API responses.

These models are based on the official JPO API OpenAPI specification.
All fields use Japanese descriptions from the spec for reference.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Enums and Code Definitions
# =============================================================================


class StatusCode(str, Enum):
    """API status codes returned in responses.

    See: https://ip-data.jpo.go.jp/pages/api_status.html
    """

    SUCCESS = "100"  # 正常終了 - Successful completion
    NO_DATA = "107"  # 該当するデータがありません - No applicable data
    NO_DOCUMENT = "108"  # 該当する書類実体がありません - No substantial documents
    UNAVAILABLE_NUMBER = "111"  # 提供対象外の案件番号 - Unavailable registration number
    DAILY_LIMIT_EXCEEDED = "203"  # 1日のアクセス上限を超過 - Daily access limit exceeded
    INVALID_PARAMETER = "204"  # パラメーターの入力された値に問題 - Inappropriate parameter value
    INVALID_CHARACTERS = "208"  # タブ文字、,、;、|は利用できません - Invalid characters
    INVALID_TOKEN = "210"  # 無効なトークン - Invalid token
    INVALID_AUTH = "212"  # 無効な認証情報 - Invalid authentication
    URL_NOT_FOUND = "301"  # 指定されたURLは存在しません - URL does not exist
    TIMEOUT = "302"  # タイムアウト - Timeout
    CONCENTRATED_ACCESS = "303"  # アクセスが集中 - Concentrated access
    INVALID_REQUEST = "400"  # 無効なリクエスト - Invalid request
    UNEXPECTED_ERROR = "999"  # 想定外のエラー - Unexpected error


class NumberType(str, Enum):
    """Number types for reference APIs.

    See: https://ip-data.jpo.go.jp/pages/api_code_definition.html
    """

    APPLICATION = "01"  # 出願番号
    PUBLICATION = "02"  # 公開番号
    PCT_PUBLICATION_JP = "03"  # 公表番号
    REPUBLICATION = "04"  # 再公表番号
    EXAMINED_PUBLICATION = "05"  # 公告番号
    REGISTRATION = "06"  # 登録番号
    APPEAL = "07"  # 審判番号
    ACTION = "08"  # 出訴事件番号
    PRIORITY = "09"  # 優先権主張国・番号
    PCT_APPLICATION = "10"  # 国際出願番号
    PCT_PUBLICATION = "11"  # 国際公開番号
    INTERNATIONAL_REGISTRATION = "12"  # 国際登録番号
    CONTROL = "90"  # 庁内整理番号


class ApplicantAttorneyClass(str, Enum):
    """Applicant/Attorney identifier."""

    APPLICANT = "1"  # 出願人
    ATTORNEY = "2"  # 代理人


class DocumentType(str, Enum):
    """Document types in file wrappers."""

    NONE = " "  # 書類実体なし - No document
    BIBLIO = "S"  # 書誌 - Bibliographic data
    CLAIMS = "L"  # 請求の範囲 - Claims
    DESCRIPTION = "M"  # 明細書 - Description
    SEQUENCE = "H"  # 配列表 - Sequence listings
    DRAWINGS = "Z"  # 図面 - Drawings
    ABSTRACT = "Y"  # 要約書 - Abstract
    ATTACHMENT = "T"  # 添付書類 - Attached document
    ORIGINAL = "G"  # 原データ - Original data
    DRAFT = "K"  # 起案書 - Office action draft
    INTERNAL = "C"  # 庁内書類 - Internal JPO document
    UNSTRUCTURED = "N"  # 非構造化書類 - Unstructured document


# =============================================================================
# Base Response Models
# =============================================================================


class ApiResult(BaseModel):
    """Base result wrapper for all API responses."""

    status_code: str = Field(alias="statusCode", description="ステータスコード")
    error_message: str = Field(default="", alias="errorMessage", description="エラーメッセージ")
    remain_access_count: str = Field(
        default="", alias="remainAccessCount", description="残アクセス数"
    )
    data: dict[str, Any] | None = Field(default=None, description="詳細情報データ")

    model_config = {"populate_by_name": True}

    @property
    def is_success(self) -> bool:
        """Check if the request was successful."""
        return self.status_code == StatusCode.SUCCESS.value

    @property
    def has_data(self) -> bool:
        """Check if the response contains data."""
        return self.status_code not in (
            StatusCode.NO_DATA.value,
            StatusCode.NO_DOCUMENT.value,
        )


# =============================================================================
# Applicant/Attorney Models
# =============================================================================


class ApplicantAttorney(BaseModel):
    """申請人（出願人・代理人）- Applicant or Attorney information."""

    applicant_attorney_cd: str = Field(
        default="", alias="applicantAttorneyCd", description="申請人コード"
    )
    repeat_number: str = Field(default="", alias="repeatNumber", description="繰返番号")
    name: str = Field(default="", description="申請人氏名・名称")
    applicant_attorney_class: str = Field(
        default="", alias="applicantAttorneyClass", description="出願人・代理人識別"
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Priority/Related Application Models
# =============================================================================


class PriorityInfo(BaseModel):
    """優先権情報 - Priority claim information."""

    priority_number: str = Field(default="", alias="priorityNumber", description="優先権番号")
    priority_date: str = Field(default="", alias="priorityDate", description="優先日")
    priority_country_cd: str = Field(
        default="", alias="priorityCountryCd", description="優先権主張国コード"
    )

    model_config = {"populate_by_name": True}


class DivisionalApplicationInfo(BaseModel):
    """分割出願情報 - Divisional application information."""

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    relationship: str = Field(default="", description="関係 (parent/child)")

    model_config = {"populate_by_name": True}


# =============================================================================
# Classification Models
# =============================================================================


class IpcClassification(BaseModel):
    """IPC分類 - International Patent Classification."""

    ipc_code: str = Field(default="", alias="ipcCode", description="IPC分類")
    ipc_version: str = Field(default="", alias="ipcVersion", description="IPCバージョン")

    model_config = {"populate_by_name": True}


class FiClassification(BaseModel):
    """FI分類 - Japanese File Index classification."""

    fi_code: str = Field(default="", alias="fiCode", description="FI分類")

    model_config = {"populate_by_name": True}


class FTermClassification(BaseModel):
    """Fターム - Japanese F-term classification."""

    f_term_theme: str = Field(default="", alias="fTermTheme", description="Fタームテーマ")
    f_term: str = Field(default="", alias="fTerm", description="Fターム")

    model_config = {"populate_by_name": True}


# =============================================================================
# Procedure/Action Models
# =============================================================================


class ProcedureInfo(BaseModel):
    """手続情報 - Procedure/action information."""

    document_cd: str = Field(default="", alias="documentCd", description="書類コード")
    document_name: str = Field(default="", alias="documentName", description="書類名")
    receipt_date: str = Field(default="", alias="receiptDate", description="受付日/起案日")
    sending_date: str = Field(default="", alias="sendingDate", description="発送日")
    document_number: str = Field(default="", alias="documentNumber", description="書類番号")

    model_config = {"populate_by_name": True}


class RefusalReasonInfo(BaseModel):
    """拒絶理由情報 - Refusal reason information."""

    document_number: str = Field(default="", alias="documentNumber", description="書類番号")
    sending_date: str = Field(default="", alias="sendingDate", description="発送日")
    refusal_reason_cd: str = Field(
        default="", alias="refusalReasonCd", description="拒絶理由コード"
    )

    model_config = {"populate_by_name": True}


class CitedDocumentInfo(BaseModel):
    """引用文献情報 - Cited document information."""

    document_number: str = Field(default="", alias="documentNumber", description="書類番号")
    citation_category: str = Field(default="", alias="citationCategory", description="引用区分")
    citation_document: str = Field(default="", alias="citationDocument", description="引用文献")

    model_config = {"populate_by_name": True}


# =============================================================================
# Registration Models
# =============================================================================


class RegistrationInfo(BaseModel):
    """登録情報 - Registration information."""

    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    registration_date: str = Field(default="", alias="registrationDate", description="登録日")
    expiration_date: str = Field(default="", alias="expirationDate", description="存続期間満了日")

    model_config = {"populate_by_name": True}


# =============================================================================
# Patent Progress (Status) Models
# =============================================================================


class PatentProgressData(BaseModel):
    """特許出願経過情報 - Patent application progress/status data.

    This is the main response model for the Patent Progress Information API.
    """

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    invention_title: str = Field(default="", alias="inventionTitle", description="発明の名称")
    applicant_attorney: list[ApplicantAttorney] = Field(
        default_factory=list, alias="applicantAttorney", description="申請人"
    )
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    publication_number: str = Field(default="", alias="publicationNumber", description="公開番号")
    publication_date: str = Field(default="", alias="publicationDate", description="公開日")
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    registration_date: str = Field(default="", alias="registrationDate", description="登録日")

    # Priority information
    priority_info: list[PriorityInfo] = Field(
        default_factory=list, alias="priorityInfo", description="優先権情報"
    )

    # Classification
    ipc_classification: list[IpcClassification] = Field(
        default_factory=list, alias="ipcClassification", description="IPC分類"
    )
    fi_classification: list[FiClassification] = Field(
        default_factory=list, alias="fiClassification", description="FI分類"
    )
    f_term_classification: list[FTermClassification] = Field(
        default_factory=list, alias="fTermClassification", description="Fターム"
    )

    # Procedures
    procedure_info: list[ProcedureInfo] = Field(
        default_factory=list, alias="procedureInfo", description="手続情報"
    )

    # Additional fields
    international_application_number: str = Field(
        default="", alias="internationalApplicationNumber", description="国際出願番号"
    )
    international_publication_number: str = Field(
        default="", alias="internationalPublicationNumber", description="国際公開番号"
    )
    ib_flag: str = Field(default="", alias="ibFlag", description="IB書類フラグ")

    model_config = {"populate_by_name": True}


class SimplifiedPatentProgressData(BaseModel):
    """簡易特許出願経過情報 - Simplified patent progress data.

    This is a lighter version without priority and classification information.
    """

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    invention_title: str = Field(default="", alias="inventionTitle", description="発明の名称")
    applicant_attorney: list[ApplicantAttorney] = Field(
        default_factory=list, alias="applicantAttorney", description="申請人"
    )
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    publication_number: str = Field(default="", alias="publicationNumber", description="公開番号")
    publication_date: str = Field(default="", alias="publicationDate", description="公開日")
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    registration_date: str = Field(default="", alias="registrationDate", description="登録日")
    procedure_info: list[ProcedureInfo] = Field(
        default_factory=list, alias="procedureInfo", description="手続情報"
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Number Reference Models
# =============================================================================


class NumberReference(BaseModel):
    """番号照会結果 - Number reference result."""

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    publication_number: str = Field(default="", alias="publicationNumber", description="公開番号")
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")

    model_config = {"populate_by_name": True}


# =============================================================================
# Document Models
# =============================================================================


class DocumentContent(BaseModel):
    """書類内容 - Document content information."""

    document_cd: str = Field(default="", alias="documentCd", description="書類コード")
    document_name: str = Field(default="", alias="documentName", description="書類名")
    receipt_date: str = Field(default="", alias="receiptDate", description="受付日")
    document_number: str = Field(default="", alias="documentNumber", description="書類番号")
    document_type: str = Field(default="", alias="documentType", description="書類識別")
    content_url: str = Field(default="", alias="contentUrl", description="コンテンツURL")
    file_size: str = Field(default="", alias="fileSize", description="ファイルサイズ")

    model_config = {"populate_by_name": True}


class ApplicationDocumentsData(BaseModel):
    """出願書類情報 - Application documents data."""

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    documents: list[DocumentContent] = Field(default_factory=list, description="書類一覧")
    zip_url: str = Field(default="", alias="zipUrl", description="ZIPダウンロードURL")

    model_config = {"populate_by_name": True}


# =============================================================================
# J-PlatPat URL Model
# =============================================================================


class JplatpatFixedAddress(BaseModel):
    """J-PlatPat固定アドレス - J-PlatPat fixed URL."""

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    jplatpat_url: str = Field(default="", alias="jplatpatUrl", description="J-PlatPat URL")

    model_config = {"populate_by_name": True}


# =============================================================================
# PCT National Phase Model
# =============================================================================


class PctNationalPhaseData(BaseModel):
    """PCT国内移行番号情報 - PCT national phase application number."""

    international_application_number: str = Field(
        default="", alias="internationalApplicationNumber", description="国際出願番号"
    )
    international_publication_number: str = Field(
        default="", alias="internationalPublicationNumber", description="国際公開番号"
    )
    national_application_number: str = Field(
        default="", alias="nationalApplicationNumber", description="国内出願番号"
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Design-Specific Models
# =============================================================================


class DesignProgressData(BaseModel):
    """意匠出願経過情報 - Design application progress data."""

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    design_title: str = Field(default="", alias="designTitle", description="意匠に係る物品")
    applicant_attorney: list[ApplicantAttorney] = Field(
        default_factory=list, alias="applicantAttorney", description="申請人"
    )
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    registration_date: str = Field(default="", alias="registrationDate", description="登録日")
    priority_info: list[PriorityInfo] = Field(
        default_factory=list, alias="priorityInfo", description="優先権情報"
    )
    procedure_info: list[ProcedureInfo] = Field(
        default_factory=list, alias="procedureInfo", description="手続情報"
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Trademark-Specific Models
# =============================================================================


class TrademarkProgressData(BaseModel):
    """商標出願経過情報 - Trademark application progress data."""

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    trademark_name: str = Field(default="", alias="trademarkName", description="商標の名称")
    applicant_attorney: list[ApplicantAttorney] = Field(
        default_factory=list, alias="applicantAttorney", description="申請人"
    )
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    registration_date: str = Field(default="", alias="registrationDate", description="登録日")
    priority_info: list[PriorityInfo] = Field(
        default_factory=list, alias="priorityInfo", description="優先権情報"
    )
    procedure_info: list[ProcedureInfo] = Field(
        default_factory=list, alias="procedureInfo", description="手続情報"
    )
    goods_services: list[str] = Field(
        default_factory=list, alias="goodsServices", description="指定商品・役務"
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Response Wrappers
# =============================================================================


class PatentProgressResponse(BaseModel):
    """Response wrapper for Patent Progress API."""

    result: ApiResult

    @property
    def data(self) -> PatentProgressData | None:
        """Parse and return the progress data."""
        if self.result.data:
            return PatentProgressData.model_validate(self.result.data)
        return None


class SimplifiedPatentProgressResponse(BaseModel):
    """Response wrapper for Simplified Patent Progress API."""

    result: ApiResult

    @property
    def data(self) -> SimplifiedPatentProgressData | None:
        """Parse and return the progress data."""
        if self.result.data:
            return SimplifiedPatentProgressData.model_validate(self.result.data)
        return None


class ApplicantNameResponse(BaseModel):
    """Response for Applicant Name lookup by code."""

    result: ApiResult

    @property
    def applicants(self) -> list[ApplicantAttorney]:
        """Parse and return the applicant list."""
        if self.result.data and "applicantAttorney" in self.result.data:
            return [
                ApplicantAttorney.model_validate(item)
                for item in self.result.data["applicantAttorney"]
            ]
        return []


class ApplicantCodeResponse(BaseModel):
    """Response for Applicant Code lookup by name."""

    result: ApiResult

    @property
    def applicants(self) -> list[ApplicantAttorney]:
        """Parse and return the applicant list."""
        if self.result.data and "applicantAttorney" in self.result.data:
            return [
                ApplicantAttorney.model_validate(item)
                for item in self.result.data["applicantAttorney"]
            ]
        return []


class NumberReferenceResponse(BaseModel):
    """Response for Number Reference API."""

    result: ApiResult

    @property
    def references(self) -> list[NumberReference]:
        """Parse and return the number references."""
        if self.result.data and "caseNumberReference" in self.result.data:
            return [
                NumberReference.model_validate(item)
                for item in self.result.data["caseNumberReference"]
            ]
        return []


class JplatpatUrlResponse(BaseModel):
    """Response for J-PlatPat Fixed Address API."""

    result: ApiResult

    @property
    def url(self) -> str | None:
        """Get the J-PlatPat URL."""
        if self.result.data and "jplatpatUrl" in self.result.data:
            return self.result.data["jplatpatUrl"]
        return None


__all__ = [
    # Enums
    "StatusCode",
    "NumberType",
    "ApplicantAttorneyClass",
    "DocumentType",
    # Base
    "ApiResult",
    # Common models
    "ApplicantAttorney",
    "PriorityInfo",
    "DivisionalApplicationInfo",
    "IpcClassification",
    "FiClassification",
    "FTermClassification",
    "ProcedureInfo",
    "RefusalReasonInfo",
    "CitedDocumentInfo",
    "RegistrationInfo",
    "NumberReference",
    "DocumentContent",
    "ApplicationDocumentsData",
    "JplatpatFixedAddress",
    "PctNationalPhaseData",
    # Patent models
    "PatentProgressData",
    "SimplifiedPatentProgressData",
    # Design models
    "DesignProgressData",
    # Trademark models
    "TrademarkProgressData",
    # Response wrappers
    "PatentProgressResponse",
    "SimplifiedPatentProgressResponse",
    "ApplicantNameResponse",
    "ApplicantCodeResponse",
    "NumberReferenceResponse",
    "JplatpatUrlResponse",
]

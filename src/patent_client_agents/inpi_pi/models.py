"""Pydantic models for JPO Patent Information Retrieval API responses.

These models track the *actual* JSON returned by the live JPO Patent
Information Retrieval API (handbook v14, validated against production
2026-05-07). The OpenAPI spec at ``resources/jpo/jpo_api_openapi.json``
is *not* always accurate (it sometimes describes objects where the API
returns arrays, and uses different status-code keys); when the spec and
the API disagree, the live API wins.

Field aliases preserve the camelCase keys returned by JPO. Japanese
descriptions (from the handbook) are kept on each ``Field`` for
reference. Pydantic ``populate_by_name`` is enabled so callers can
construct models with snake_case kwargs in tests.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Enums and code definitions
# =============================================================================


class StatusCode(StrEnum):
    """API status codes returned in the ``result.statusCode`` field.

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
    CONCENTRATED_ACCESS = "303"  # アクセスが集中 - Concentrated access (transient)
    INVALID_REQUEST = "400"  # 無効なリクエスト - Invalid request
    UNEXPECTED_ERROR = "999"  # 想定外のエラー - Unexpected error


# Status codes that mean "no result" but are not errors.
EMPTY_STATUS_CODES = frozenset(
    {
        StatusCode.NO_DATA.value,
        StatusCode.NO_DOCUMENT.value,
        StatusCode.UNAVAILABLE_NUMBER.value,
    }
)


class CaseNumberKind(StrEnum):
    """Kind values for ``case_number_reference`` endpoints.

    These are descriptive strings (not numeric codes). The JPO ``NumberType``
    numeric codes (01-12) used elsewhere do **not** apply here.
    """

    APPLICATION = "application"
    PUBLICATION = "publication"
    REGISTRATION = "registration"


class PctKind(StrEnum):
    """Kind values for ``pct_national_phase_application_number`` endpoint."""

    INTERNATIONAL_APPLICATION = "international_application"
    INTERNATIONAL_PUBLICATION = "international_publication"


class NumberType(StrEnum):
    """Numeric number-type codes used in the bibliographyInformation arrays.

    See: https://ip-data.jpo.go.jp/pages/api_code_definition.html (table 03020).

    These are the codes that appear in the ``numberType`` field of
    ``bibliographyInformation`` entries. They are *not* the right values
    for ``case_number_reference`` or PCT national-phase endpoints — those
    use the descriptive strings on :class:`CaseNumberKind` /
    :class:`PctKind`.
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


class ApplicantAttorneyClass(StrEnum):
    """Applicant/attorney role flag (``applicantAttorneyClass``)."""

    APPLICANT = "1"  # 出願人
    ATTORNEY = "2"  # 代理人


class DocumentSeparator(StrEnum):
    """Document body classifier (``documentSeparator``).

    See handbook code-table 03050.
    """

    NONE = " "  # 書類実体なし - No document body
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


# Backwards compatibility alias — older callers imported ``DocumentType``.
DocumentType = DocumentSeparator


# =============================================================================
# Result wrapper
# =============================================================================


class ApiResult(BaseModel):
    """The ``result`` envelope every JSON response is wrapped in."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    status_code: str = Field(alias="statusCode", description="ステータスコード")
    error_message: str = Field(default="", alias="errorMessage", description="エラーメッセージ")
    remain_access_count: str = Field(
        default="", alias="remainAccessCount", description="残アクセス数"
    )
    data: dict[str, Any] | None = Field(default=None, description="詳細情報データ")

    @property
    def is_success(self) -> bool:
        """``True`` if the request returned data successfully (status 100)."""
        return self.status_code == StatusCode.SUCCESS.value

    @property
    def has_data(self) -> bool:
        """``True`` unless the API explicitly says there's no data."""
        return self.status_code not in EMPTY_STATUS_CODES


# =============================================================================
# Shared component models
# =============================================================================


class ApplicantAttorney(BaseModel):
    """申請人 (出願人・代理人) — Applicant or attorney row."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    applicant_attorney_cd: str = Field(
        default="", alias="applicantAttorneyCd", description="申請人コード"
    )
    repeat_number: str = Field(default="", alias="repeatNumber", description="繰返番号")
    name: str = Field(default="", description="申請人氏名・名称")
    applicant_attorney_class: str = Field(
        default="", alias="applicantAttorneyClass", description="出願人・代理人識別"
    )


class PriorityInfo(BaseModel):
    """優先権情報 — single row of priority/basic-application data.

    The *real* response uses the ``priorityRightInformation`` array key
    (not ``priorityInfo`` — that field name does not exist in production).
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    paris_priority_application_number: str = Field(
        default="",
        alias="parisPriorityApplicationNumber",
        description="パリ条約に基づく優先権出願番号",
    )
    paris_priority_date: str = Field(
        default="", alias="parisPriorityDate", description="パリ条約に基づく優先権主張日"
    )
    paris_priority_country_cd: str = Field(
        default="", alias="parisPriorityCountryCd", description="パリ条約に基づく優先権国コード"
    )
    national_priority_law_cd: str = Field(
        default="", alias="nationalPriorityLawCd", description="国内優先権四法コード"
    )
    national_priority_application_number: str = Field(
        default="",
        alias="nationalPriorityApplicationNumber",
        description="国内優先権出願番号",
    )
    national_priority_international_application_number: str = Field(
        default="",
        alias="nationalPriorityInternationalApplicationNumber",
        description="国内優先権国際出願番号",
    )
    national_priority_date: str = Field(
        default="", alias="nationalPriorityDate", description="国内優先権主張日"
    )


class ParentApplicationInfo(BaseModel):
    """原出願情報 — parent (pre-divisional) application reference.

    Patent responses include just ``parentApplicationNumber`` + ``filingDate``.
    Design and trademark responses also include ``parentApplicationCategory``
    and ``parentApplicationLawCode``.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    parent_application_number: str = Field(
        default="", alias="parentApplicationNumber", description="原出願番号"
    )
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    parent_application_category: str = Field(
        default="", alias="parentApplicationCategory", description="原出願種別"
    )
    parent_application_law_code: str = Field(
        default="", alias="parentApplicationLawCode", description="原出願四法コード"
    )


class DivisionalApplicationInfo(BaseModel):
    """分割出願情報 — divisional-application descendant row.

    Field set is from the live patent ``app_progress`` response. The OpenAPI
    spec listed only ``applicationNumber``/``filingDate``/``relationship``
    which is wrong — the real schema is much richer.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    publication_number: str = Field(default="", alias="publicationNumber", description="公開番号")
    ad_publication_number: str = Field(
        default="", alias="ADPublicationNumber", description="公開番号（西暦変換）"
    )
    national_publication_number: str = Field(
        default="", alias="nationalPublicationNumber", description="公表番号"
    )
    ad_national_publication_number: str = Field(
        default="", alias="ADNationalPublicationNumber", description="公表番号（西暦変換）"
    )
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    international_application_number: str = Field(
        default="", alias="internationalApplicationNumber", description="国際出願番号"
    )
    international_publication_number: str = Field(
        default="", alias="internationalPublicationNumber", description="国際公開番号"
    )
    erasure_identifier: str = Field(default="", alias="erasureIdentifier", description="抹消識別")
    expire_date: str = Field(default="", alias="expireDate", description="存続期間満了年月日")
    disappearance_date: str = Field(
        default="", alias="disappearanceDate", description="本権利消滅日"
    )
    divisional_generation: str = Field(
        default="", alias="divisionalGeneration", description="分割出願の世代"
    )


class BibliographyDocument(BaseModel):
    """書類一覧 entry — a single document inside ``bibliographyInformation``."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    legal_date: str = Field(default="", alias="legalDate", description="受付日・発送日・作成日")
    irir_flg: str = Field(default="", alias="irirFlg", description="IB書類フラグ")
    availability_flag: str = Field(default="", alias="availabilityFlag", description="書類実体有無")
    document_code: str = Field(default="", alias="documentCode", description="中間書類コード")
    document_description: str = Field(default="", alias="documentDescription", description="書類名")
    document_number: str = Field(default="", alias="documentNumber", description="書類番号")
    version_number: str = Field(default="", alias="versionNumber", description="バージョン番号")
    document_separator: str = Field(default="", alias="documentSeparator", description="書類識別")
    number_of_pages: str = Field(default="", alias="numberOfPages", description="ページ数")
    size_of_document: str = Field(
        default="", alias="sizeOfDocument", description="ドキュメントサイズ"
    )


class BibliographyInformation(BaseModel):
    """書類一覧（書誌） — file-wrapper bibliography group keyed by number.

    The ``app_progress*`` endpoints return one of these per number type
    (application / publication / registration), each containing a list
    of documents.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    number_type: str = Field(default="", alias="numberType", description="番号種別")
    number: str = Field(default="", description="番号")
    document_list: list[BibliographyDocument] = Field(
        default_factory=list, alias="documentList", description="書類一覧"
    )


class RightPersonInfo(BaseModel):
    """権利者情報 — current rights-holder row in registration responses."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    right_person_cd: str = Field(default="", alias="rightPersonCd", description="権利者コード")
    right_person_name: str = Field(default="", alias="rightPersonName", description="権利者名")


class GoodsServiceInformation(BaseModel):
    """商品区分情報 — Nice-class designation row in trademark responses."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    goods_service_class: str = Field(
        default="", alias="goodsServiceClass", description="指定商品又は指定役務の区分"
    )
    goods_service_name: str = Field(
        default="", alias="goodsServiceName", description="指定商品又は指定役務名"
    )
    similar_code: str = Field(default="", alias="similarCode", description="類似群コード")


# =============================================================================
# Patent — application progress
# =============================================================================


class PatentProgressData(BaseModel):
    """特許出願経過情報 — full patent progress response data.

    Field set matches the live ``/patent/v1/app_progress/{n}`` response.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    invention_title: str = Field(default="", alias="inventionTitle", description="発明の名称")
    applicant_attorney: list[ApplicantAttorney] = Field(
        default_factory=list, alias="applicantAttorney", description="申請人"
    )
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    publication_number: str = Field(default="", alias="publicationNumber", description="公開番号")
    ad_publication_number: str = Field(
        default="", alias="ADPublicationNumber", description="公開番号（西暦変換）"
    )
    national_publication_number: str = Field(
        default="", alias="nationalPublicationNumber", description="公表番号"
    )
    ad_national_publication_number: str = Field(
        default="", alias="ADNationalPublicationNumber", description="公表番号（西暦変換）"
    )
    publication_date: str = Field(default="", alias="publicationDate", description="公開日")
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    registration_date: str = Field(default="", alias="registrationDate", description="登録日")
    international_application_number: str = Field(
        default="", alias="internationalApplicationNumber", description="国際出願番号"
    )
    international_publication_number: str = Field(
        default="", alias="internationalPublicationNumber", description="国際公開番号"
    )
    international_publication_date: str = Field(
        default="", alias="internationalPublicationDate", description="国際公開日"
    )
    erasure_identifier: str = Field(default="", alias="erasureIdentifier", description="抹消識別")
    expire_date: str = Field(default="", alias="expireDate", description="存続期間満了年月日")
    disappearance_date: str = Field(
        default="", alias="disappearanceDate", description="本権利消滅日"
    )
    priority_right_information: list[PriorityInfo] = Field(
        default_factory=list, alias="priorityRightInformation", description="優先権基礎情報"
    )
    parent_application_information: ParentApplicationInfo | None = Field(
        default=None, alias="parentApplicationInformation", description="原出願情報"
    )
    divisional_application_information: list[DivisionalApplicationInfo] = Field(
        default_factory=list,
        alias="divisionalApplicationInformation",
        description="分割出願群情報",
    )
    bibliography_information: list[BibliographyInformation] = Field(
        default_factory=list, alias="bibliographyInformation", description="書類一覧（書誌）"
    )


# Simple progress shares the same shape minus priority/parent/divisional.
# The PatentProgressData model already makes those fields optional/empty by
# default, so SimplifiedPatentProgressData is a thin alias kept for type
# clarity at the API surface.
class SimplifiedPatentProgressData(PatentProgressData):
    """簡易特許出願経過情報 — same fields as PatentProgressData, minus
    ``priorityRightInformation``, ``parentApplicationInformation``, and
    ``divisionalApplicationInformation``. The simple endpoint just doesn't
    populate those, so the parent model's defaults handle it cleanly.
    """


# =============================================================================
# Patent — divisional information (single endpoint)
# =============================================================================


class DivisionalAppInfoData(BaseModel):
    """Top-level data for ``/patent/v1/divisional_app_info``.

    Wraps the parent reference and the list of divisional descendants.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    parent_application_information: ParentApplicationInfo | None = Field(
        default=None, alias="parentApplicationInformation", description="原出願情報"
    )
    divisional_application_information: list[DivisionalApplicationInfo] = Field(
        default_factory=list,
        alias="divisionalApplicationInformation",
        description="分割出願群情報",
    )


# =============================================================================
# Number reference (case_number_reference)
# =============================================================================


class NumberReference(BaseModel):
    """番号照会結果 — single cross-reference row.

    Note: the live API returns a *single object* (not a list), e.g.::

        {
          "applicationNumber": "2020123456",
          "publicationNumber": "2021090037",
          "registrationNumber": "7533889",
          ...
        }
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    publication_number: str = Field(
        default="", alias="publicationNumber", description="公開番号（西暦）"
    )
    national_publication_number: str = Field(
        default="", alias="nationalPublicationNumber", description="公表番号（西暦）"
    )
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    international_publication_number: str = Field(
        default="", alias="internationalPublicationNumber", description="国際公開番号"
    )
    # Design-only fields
    international_registration_number: str = Field(
        default="", alias="internationalRegistrationNumber", description="国際登録番号"
    )
    design_number: str = Field(default="", alias="designNumber", description="意匠番号")


# =============================================================================
# Citations
# =============================================================================


class PatentCitedDocument(BaseModel):
    """特許文献情報データ — patent citation row inside ``cite_doc_info``."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    draft_date: str = Field(default="", alias="draftDate", description="起案日")
    citation_type: str = Field(default="", alias="citationType", description="種別 (code 07010)")
    citation_order: str = Field(default="", alias="citationOrder", description="引用順番")
    document_number: str = Field(
        default="", alias="documentNumber", description="文献番号 (code 07020)"
    )


class NonPatentCitedDocument(BaseModel):
    """非特許文献情報データ — non-patent citation row inside ``cite_doc_info``."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    draft_date: str = Field(default="", alias="draftDate", description="起案日")
    citation_type: str = Field(default="", alias="citationType", description="種別 (code 07010)")
    citation_order: str = Field(default="", alias="citationOrder", description="引用順番")
    document_type: str = Field(
        default="", alias="documentType", description="文献分類 (code 07060)"
    )
    author_name: str = Field(default="", alias="authorName", description="著者/翻訳者名")
    paper_title: str = Field(default="", alias="paperTitle", description="論文名/タイトル")
    publication_name: str = Field(default="", alias="publicationName", description="刊行物名")
    issue_country_cd: str = Field(
        default="", alias="issueCountryCd", description="発行国コード (code 07070)"
    )
    publisher: str = Field(default="", description="発行所／発行者")
    issue_date: str = Field(default="", alias="issueDate", description="発行／受入年月日")
    issue_date_type: str = Field(
        default="", alias="issueDateType", description="年月日フラグ (code 07080)"
    )
    issue_number: str = Field(default="", alias="issueNumber", description="版数／巻／号数")
    citation_pages: str = Field(default="", alias="citationPages", description="引用頁")


class CitedDocumentsData(BaseModel):
    """``cite_doc_info`` data wrapper — patent + non-patent citations.

    The OpenAPI spec describes ``patentDoc`` and ``nonPatentDoc`` as
    objects, but the live API returns arrays. This model accepts arrays.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    patent_doc: list[PatentCitedDocument] = Field(
        default_factory=list, alias="patentDoc", description="特許文献情報データ"
    )
    non_patent_doc: list[NonPatentCitedDocument] = Field(
        default_factory=list, alias="nonPatentDoc", description="非特許文献情報データ"
    )


# Backwards-compatible alias (older callers used CitedDocumentInfo for the
# combined wrapper, which conflated patent + non-patent into one shape).
class CitedDocumentInfo(BaseModel):
    """Legacy flat citation row, retained for callers that built records
    with ``citationDocument``/``citationCategory``. New code should use
    :class:`CitedDocumentsData`."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    document_number: str = Field(default="", alias="documentNumber", description="文献番号")
    citation_category: str = Field(default="", alias="citationCategory", description="引用区分")
    citation_document: str = Field(default="", alias="citationDocument", description="引用文献")


# =============================================================================
# Registration info
# =============================================================================


class RegistrationInfo(BaseModel):
    """登録情報 — patent/design/trademark registration response.

    All three flavours share most fields plus a few type-specific ones
    (e.g. ``inventionTitle``, ``numberOfClaims`` for patents;
    ``designArticle`` for designs; ``trademarkForDisplay`` etc. for
    trademarks). All fields are optional/defaulted so the same model
    serves all three.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    registration_date: str = Field(default="", alias="registrationDate", description="登録日")
    decision_date: str = Field(default="", alias="decisionDate", description="査定日")
    appeal_trial_decision_date: str = Field(
        default="", alias="appealTrialDecisiondDate", description="審決日"
    )
    right_person_information: list[RightPersonInfo] = Field(
        default_factory=list, alias="rightPersonInformation", description="権利者情報"
    )
    invention_title: str = Field(default="", alias="inventionTitle", description="発明の名称")
    number_of_claims: str = Field(default="", alias="numberOfClaims", description="請求項の数")
    expire_date: str = Field(default="", alias="expireDate", description="存続期間満了年月日")
    next_pension_payment_date: str = Field(
        default="", alias="nextPensionPaymentDate", description="次期年金納付期限"
    )
    last_payment_yearly: str = Field(
        default="", alias="lastPaymentYearly", description="最終納付年分"
    )
    erasure_identifier: str = Field(
        default="", alias="erasureIdentifier", description="本権利抹消識別"
    )
    disappearance_date: str = Field(
        default="", alias="disappearanceDate", description="本権利抹消日"
    )
    update_date: str = Field(default="", alias="updateDate", description="更新日付")
    # Design-specific
    design_article: str = Field(
        default="", alias="designArticle", description="意匠に係る物品の名称"
    )
    # Trademark-specific
    trademark_for_display: str = Field(
        default="", alias="trademarkForDisplay", description="表示用商標"
    )
    transliteration: dict[str, Any] = Field(default_factory=dict, description="称呼")
    vienna_class: dict[str, Any] = Field(
        default_factory=dict, alias="viennaClass", description="ウィーン図形分類"
    )
    goods_service_information: list[GoodsServiceInformation] = Field(
        default_factory=list, alias="goodsServiceInformation", description="商品区分情報"
    )


# =============================================================================
# PCT national-phase data
# =============================================================================


class PctNationalPhaseData(BaseModel):
    """``/patent/v1/pct_national_phase_application_number`` data.

    The live API returns just ``applicationNumber`` — the JP national-phase
    application that corresponds to the queried PCT international number.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    # Echo fields kept for backwards compatibility with older callers.
    international_application_number: str = Field(
        default="", alias="internationalApplicationNumber", description="国際出願番号"
    )
    international_publication_number: str = Field(
        default="", alias="internationalPublicationNumber", description="国際公開番号"
    )

    @property
    def national_application_number(self) -> str:
        """Backwards-compat alias — same value as ``application_number``."""
        return self.application_number


# =============================================================================
# Document downloads (zip / oversize URL)
# =============================================================================


class DocumentBundleResult(BaseModel):
    """Result of a document-download endpoint (``app_doc_cont_*``).

    These endpoints return either:

    * the ZIP archive bytes directly (Content-Type ``application/zip``,
      ``zip_bytes`` populated, ``download_url`` empty); or
    * a JSON envelope pointing at a hosted ZIP (``download_url`` populated,
      ``zip_bytes`` empty) when the archive exceeds the 10 MB inline cap.

    When neither is present (e.g. status 107 / 108), the bundle is empty.
    Both paths leave the consumer responsible for unzipping and parsing
    the JPO XML inside.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", description="Application number queried")
    zip_bytes: bytes | None = Field(default=None, description="Inline ZIP bytes (<10 MB)")
    download_url: str = Field(default="", description="Hosted ZIP URL when >10 MB")
    content_type: str = Field(default="", description="HTTP Content-Type header")

    @property
    def is_empty(self) -> bool:
        """True if the API found no documents for this number."""
        return self.zip_bytes is None and not self.download_url


# =============================================================================
# Design / trademark progress
# =============================================================================


class DesignProgressData(BaseModel):
    """意匠出願経過情報 — design application progress response."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    design_article: str = Field(
        default="", alias="designArticle", description="意匠に係る物品の名称"
    )
    design_class: str = Field(default="", alias="designClass", description="意匠分類")
    applicant_attorney: list[ApplicantAttorney] = Field(
        default_factory=list, alias="applicantAttorney", description="申請人"
    )
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    publication_date: str = Field(default="", alias="publicationDate", description="公開日")
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    registration_date: str = Field(default="", alias="registrationDate", description="登録日")
    principal_design_application_number: str = Field(
        default="", alias="principalDesignApplicationNumber", description="本意匠番号"
    )
    erasure_identifier: str = Field(default="", alias="erasureIdentifier", description="抹消識別")
    expire_date: str = Field(default="", alias="expireDate", description="存続期間満了年月日")
    disappearance_date: str = Field(
        default="", alias="disappearanceDate", description="本権利消滅日"
    )
    priority_right_information: list[PriorityInfo] = Field(
        default_factory=list, alias="priorityRightInformation", description="優先権基礎情報"
    )
    parent_application_information: ParentApplicationInfo | None = Field(
        default=None, alias="parentApplicationInformation", description="原出願情報"
    )
    bibliography_information: list[BibliographyInformation] = Field(
        default_factory=list, alias="bibliographyInformation", description="書類一覧"
    )

    # Backwards-compat aliases for the earlier (now-incorrect) field names.
    @property
    def design_title(self) -> str:
        """Deprecated alias — use ``design_article``."""
        return self.design_article


class TrademarkProgressData(BaseModel):
    """商標出願経過情報 — trademark application progress response."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    application_number: str = Field(default="", alias="applicationNumber", description="出願番号")
    applicant_attorney: list[ApplicantAttorney] = Field(
        default_factory=list, alias="applicantAttorney", description="申請人"
    )
    filing_date: str = Field(default="", alias="filingDate", description="出願日")
    publication_date: str = Field(default="", alias="publicationDate", description="公開日")
    registration_number: str = Field(default="", alias="registrationNumber", description="登録番号")
    registration_date: str = Field(default="", alias="registrationDate", description="登録日")
    erasure_identifier: str = Field(default="", alias="erasureIdentifier", description="抹消識別")
    expire_date: str = Field(default="", alias="expireDate", description="存続期間満了年月日")
    disappearance_date: str = Field(
        default="", alias="disappearanceDate", description="本権利消滅日"
    )
    trademark_for_display: str = Field(
        default="", alias="trademarkForDisplay", description="表示用商標"
    )
    transliteration: dict[str, Any] = Field(default_factory=dict, description="称呼")
    vienna_class: dict[str, Any] = Field(
        default_factory=dict, alias="viennaClass", description="ウィーン図形分類"
    )
    goods_service_information: list[GoodsServiceInformation] = Field(
        default_factory=list, alias="goodsServiceInformation", description="商品区分情報"
    )
    priority_right_information: list[PriorityInfo] = Field(
        default_factory=list, alias="priorityRightInformation", description="優先権基礎情報"
    )
    parent_application_information: ParentApplicationInfo | None = Field(
        default=None, alias="parentApplicationInformation", description="原出願情報"
    )
    bibliography_information: list[BibliographyInformation] = Field(
        default_factory=list, alias="bibliographyInformation", description="書類一覧"
    )

    # Backwards-compat alias.
    @property
    def trademark_name(self) -> str:
        """Deprecated alias — use ``trademark_for_display``."""
        return self.trademark_for_display

    @property
    def goods_services(self) -> list[str]:
        """Backwards-compat: flat list of goods/service descriptions."""
        return [g.goods_service_name for g in self.goods_service_information]


# =============================================================================
# Public re-exports
# =============================================================================


__all__ = [
    # Enums
    "StatusCode",
    "EMPTY_STATUS_CODES",
    "NumberType",
    "CaseNumberKind",
    "PctKind",
    "ApplicantAttorneyClass",
    "DocumentSeparator",
    "DocumentType",
    # Wrappers
    "ApiResult",
    # Common components
    "ApplicantAttorney",
    "PriorityInfo",
    "ParentApplicationInfo",
    "DivisionalApplicationInfo",
    "BibliographyDocument",
    "BibliographyInformation",
    "RightPersonInfo",
    "GoodsServiceInformation",
    # Patent
    "PatentProgressData",
    "SimplifiedPatentProgressData",
    "DivisionalAppInfoData",
    "PatentCitedDocument",
    "NonPatentCitedDocument",
    "CitedDocumentsData",
    "CitedDocumentInfo",  # legacy
    # Reference / PCT
    "NumberReference",
    "PctNationalPhaseData",
    # Documents
    "DocumentBundleResult",
    # Registration
    "RegistrationInfo",
    # Design / trademark
    "DesignProgressData",
    "TrademarkProgressData",
]

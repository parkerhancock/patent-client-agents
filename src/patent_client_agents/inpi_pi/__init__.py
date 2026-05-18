"""Async INPI France national TM + Design connector (BYOK).

Wraps ``api-gateway.inpi.fr`` for French national trademarks (ST.66 v1.0) and
designs (ST.86 v1.0). Authentication is a session-bearer + XSRF flow bound to
a personal ``data.inpi.fr`` account (NOT PISTE); the XSRF + bearer + refresh
lifecycle is implemented in chunk 3. **TM + design only — patents covered via
EPO OPS** (FR designations + national-route filings).

Environment Variables:
    INPI_USERNAME: personal data.inpi.fr account username
    INPI_PASSWORD: personal data.inpi.fr account password
"""

from .api import (  # noqa: F401
    # Models
    ApplicantAttorney,
    CaseNumberKind,
    CitedDocumentsData,
    DesignProgressData,
    DivisionalAppInfoData,
    DocumentBundleResult,
    # Client
    InpiPiClient,
    NumberReference,
    # Enums
    NumberType,
    ParentApplicationInfo,
    PatentProgressData,
    PctKind,
    PctNationalPhaseData,
    PriorityInfo,
    RegistrationInfo,
    SimplifiedPatentProgressData,
    StatusCode,
    TrademarkProgressData,
    get_design_applicant_by_code,
    get_design_applicant_by_name,
    # Design functions
    get_design_application_documents,
    get_design_jplatpat_url,
    get_design_mailed_documents,
    get_design_number_reference,
    get_design_priority_info,
    get_design_progress,
    get_design_progress_simple,
    get_design_refusal_notices,
    get_design_registration_info,
    get_patent_applicant_by_code,
    get_patent_applicant_by_name,
    # Patent functions
    get_patent_application_documents,
    get_patent_cited_documents,
    get_patent_divisional_info,
    get_patent_jplatpat_url,
    get_patent_mailed_documents,
    get_patent_number_reference,
    get_patent_pct_national_number,
    get_patent_priority_info,
    get_patent_progress,
    get_patent_progress_simple,
    get_patent_refusal_notices,
    get_patent_registration_info,
    get_trademark_applicant_by_code,
    get_trademark_applicant_by_name,
    # Trademark functions
    get_trademark_application_documents,
    get_trademark_jplatpat_url,
    get_trademark_mailed_documents,
    get_trademark_number_reference,
    get_trademark_priority_info,
    get_trademark_progress,
    get_trademark_progress_simple,
    get_trademark_refusal_notices,
    get_trademark_registration_info,
)
from .documents import parse_document_bundle  # noqa: F401
from .models_documents import (  # noqa: F401
    DocumentBundle,
    DocumentEntry,
    DocumentKind,
    IpType,
)

__all__ = [
    # Client
    "InpiPiClient",
    # Enums
    "StatusCode",
    "NumberType",
    "CaseNumberKind",
    "PctKind",
    # Models
    "PatentProgressData",
    "SimplifiedPatentProgressData",
    "DesignProgressData",
    "TrademarkProgressData",
    "ApplicantAttorney",
    "PriorityInfo",
    "ParentApplicationInfo",
    "DivisionalAppInfoData",
    "NumberReference",
    "DocumentBundleResult",
    "CitedDocumentsData",
    "RegistrationInfo",
    "PctNationalPhaseData",
    # Document parsing
    "DocumentBundle",
    "DocumentEntry",
    "DocumentKind",
    "IpType",
    "parse_document_bundle",
    # Patent functions
    "get_patent_progress",
    "get_patent_progress_simple",
    "get_patent_divisional_info",
    "get_patent_priority_info",
    "get_patent_applicant_by_code",
    "get_patent_applicant_by_name",
    "get_patent_number_reference",
    "get_patent_application_documents",
    "get_patent_mailed_documents",
    "get_patent_refusal_notices",
    "get_patent_cited_documents",
    "get_patent_registration_info",
    "get_patent_jplatpat_url",
    "get_patent_pct_national_number",
    # Design functions
    "get_design_progress",
    "get_design_progress_simple",
    "get_design_priority_info",
    "get_design_applicant_by_code",
    "get_design_applicant_by_name",
    "get_design_number_reference",
    "get_design_application_documents",
    "get_design_mailed_documents",
    "get_design_refusal_notices",
    "get_design_registration_info",
    "get_design_jplatpat_url",
    # Trademark functions
    "get_trademark_progress",
    "get_trademark_progress_simple",
    "get_trademark_priority_info",
    "get_trademark_applicant_by_code",
    "get_trademark_applicant_by_name",
    "get_trademark_number_reference",
    "get_trademark_application_documents",
    "get_trademark_mailed_documents",
    "get_trademark_refusal_notices",
    "get_trademark_registration_info",
    "get_trademark_jplatpat_url",
]

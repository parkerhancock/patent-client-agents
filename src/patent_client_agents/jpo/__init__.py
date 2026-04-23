"""Async JPO Patent Information Retrieval API (MCP-free) plus client re-exports.

This module provides access to the Japan Patent Office (JPO) Patent Information
Retrieval APIs for patents, designs, and trademarks.

Usage:
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        progress = await client.get_patent_progress("2020123456")

Environment Variables:
    JPO_API_USERNAME: JPO-issued username/ID
    JPO_API_PASSWORD: JPO-issued password

Note: This API requires user registration with JPO. See:
    https://www.jpo.go.jp/e/system/laws/koho/internet/api-patent_info.html
"""

from .api import (  # noqa: F401
    # Models
    ApplicantAttorney,
    ApplicationDocumentsData,
    CitedDocumentInfo,
    DesignProgressData,
    DivisionalApplicationInfo,
    # Client
    JpoClient,
    NumberReference,
    # Enums
    NumberType,
    PatentProgressData,
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

__all__ = [
    # Client
    "JpoClient",
    # Enums
    "StatusCode",
    "NumberType",
    # Models
    "PatentProgressData",
    "SimplifiedPatentProgressData",
    "DesignProgressData",
    "TrademarkProgressData",
    "ApplicantAttorney",
    "PriorityInfo",
    "DivisionalApplicationInfo",
    "NumberReference",
    "ApplicationDocumentsData",
    "CitedDocumentInfo",
    "RegistrationInfo",
    "PctNationalPhaseData",
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

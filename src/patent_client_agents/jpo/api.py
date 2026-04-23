"""High-level async API for JPO Patent Information Retrieval.

Usage
-----
Preferred: use the client as a context manager::

    async with JpoClient(username="...", password="...") as client:
        progress = await client.get_patent_progress("2020123456")

One-shot convenience functions (create client automatically)::

    progress = await get_patent_progress("2020123456")

Note: One-shot functions require JPO_API_USERNAME and JPO_API_PASSWORD
environment variables to be set.
"""

from __future__ import annotations

from .client import JpoClient
from .models import (
    ApplicantAttorney,
    ApplicationDocumentsData,
    CitedDocumentInfo,
    DesignProgressData,
    DivisionalApplicationInfo,
    NumberReference,
    NumberType,
    PatentProgressData,
    PctNationalPhaseData,
    PriorityInfo,
    RegistrationInfo,
    SimplifiedPatentProgressData,
    StatusCode,
    TrademarkProgressData,
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
    # Functions
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


# =============================================================================
# Patent API Functions
# =============================================================================


async def get_patent_progress(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> PatentProgressData | None:
    """Get full patent progress/status information.

    Args:
        application_number: 10-digit application number (e.g., "2020123456").
        username: JPO username (falls back to JPO_API_USERNAME env var).
        password: JPO password (falls back to JPO_API_PASSWORD env var).

    Returns:
        Patent progress data or None if not found.
    """
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_progress(application_number)


async def get_patent_progress_simple(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> SimplifiedPatentProgressData | None:
    """Get simplified patent progress information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_progress_simple(application_number)


async def get_patent_divisional_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[DivisionalApplicationInfo]:
    """Get divisional application information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_divisional_info(application_number)


async def get_patent_priority_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[PriorityInfo]:
    """Get priority claim information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_priority_info(application_number)


async def get_patent_applicant_by_code(
    applicant_code: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get applicant name by code."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_applicant_by_code(applicant_code)


async def get_patent_applicant_by_name(
    applicant_name: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get applicant code by name."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_applicant_by_name(applicant_name)


async def get_patent_number_reference(
    kind: NumberType | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[NumberReference]:
    """Get cross-reference of application, publication, and registration numbers."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_number_reference(kind, number)


async def get_patent_application_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> ApplicationDocumentsData | None:
    """Get patent application documents."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_application_documents(application_number)


async def get_patent_mailed_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> ApplicationDocumentsData | None:
    """Get mailed patent documents (office actions)."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_mailed_documents(application_number)


async def get_patent_refusal_notices(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> ApplicationDocumentsData | None:
    """Get notices of reasons for refusal."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_refusal_notices(application_number)


async def get_patent_cited_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[CitedDocumentInfo]:
    """Get cited documents information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_cited_documents(application_number)


async def get_patent_registration_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> RegistrationInfo | None:
    """Get patent registration information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_registration_info(application_number)


async def get_patent_jplatpat_url(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get J-PlatPat URL for a patent application."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_jplatpat_url(application_number)


async def get_patent_pct_national_number(
    kind: NumberType | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> PctNationalPhaseData | None:
    """Get national phase application number from PCT number."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_patent_pct_national_number(kind, number)


# =============================================================================
# Design API Functions
# =============================================================================


async def get_design_progress(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DesignProgressData | None:
    """Get design application progress information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_progress(application_number)


async def get_design_progress_simple(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DesignProgressData | None:
    """Get simplified design progress information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_progress_simple(application_number)


async def get_design_priority_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[PriorityInfo]:
    """Get design priority information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_priority_info(application_number)


async def get_design_applicant_by_code(
    applicant_code: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get design applicant name by code."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_applicant_by_code(applicant_code)


async def get_design_applicant_by_name(
    applicant_name: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get design applicant code by name."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_applicant_by_name(applicant_name)


async def get_design_number_reference(
    kind: NumberType | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[NumberReference]:
    """Get design number cross-reference."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_number_reference(kind, number)


async def get_design_application_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> ApplicationDocumentsData | None:
    """Get design application documents."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_application_documents(application_number)


async def get_design_mailed_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> ApplicationDocumentsData | None:
    """Get mailed design documents."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_mailed_documents(application_number)


async def get_design_refusal_notices(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> ApplicationDocumentsData | None:
    """Get design refusal notices."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_refusal_notices(application_number)


async def get_design_registration_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> RegistrationInfo | None:
    """Get design registration information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_registration_info(application_number)


async def get_design_jplatpat_url(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get J-PlatPat URL for a design application."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_design_jplatpat_url(application_number)


# =============================================================================
# Trademark API Functions
# =============================================================================


async def get_trademark_progress(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> TrademarkProgressData | None:
    """Get trademark application progress information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_progress(application_number)


async def get_trademark_progress_simple(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> TrademarkProgressData | None:
    """Get simplified trademark progress information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_progress_simple(application_number)


async def get_trademark_priority_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[PriorityInfo]:
    """Get trademark priority information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_priority_info(application_number)


async def get_trademark_applicant_by_code(
    applicant_code: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get trademark applicant name by code."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_applicant_by_code(applicant_code)


async def get_trademark_applicant_by_name(
    applicant_name: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get trademark applicant code by name."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_applicant_by_name(applicant_name)


async def get_trademark_number_reference(
    kind: NumberType | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[NumberReference]:
    """Get trademark number cross-reference."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_number_reference(kind, number)


async def get_trademark_application_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> ApplicationDocumentsData | None:
    """Get trademark application documents."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_application_documents(application_number)


async def get_trademark_mailed_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> ApplicationDocumentsData | None:
    """Get mailed trademark documents."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_mailed_documents(application_number)


async def get_trademark_refusal_notices(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> ApplicationDocumentsData | None:
    """Get trademark refusal notices."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_refusal_notices(application_number)


async def get_trademark_registration_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> RegistrationInfo | None:
    """Get trademark registration information."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_registration_info(application_number)


async def get_trademark_jplatpat_url(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get J-PlatPat URL for a trademark application."""
    async with JpoClient(username=username, password=password) as client:
        return await client.get_trademark_jplatpat_url(application_number)

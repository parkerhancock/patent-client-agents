"""High-level async API for JPO Patent Information Retrieval.

Usage
-----
Preferred: use the client as a context manager::

    async with InpiPiClient(username="...", password="...") as client:
        progress = await client.get_patent_progress("2020123456")

One-shot convenience functions (create client automatically)::

    progress = await get_patent_progress("2020123456")

Note: One-shot functions require ``INPI_USERNAME`` and ``INPI_PASSWORD``
environment variables to be set.
"""

from __future__ import annotations

from .client import InpiPiClient
from .models import (
    ApplicantAttorney,
    CaseNumberKind,
    CitedDocumentsData,
    DesignProgressData,
    DivisionalAppInfoData,
    DocumentBundleResult,
    NumberReference,
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
        username: JPO username (falls back to ``INPI_USERNAME`` env var).
        password: JPO password (falls back to ``INPI_PASSWORD`` env var).

    Returns:
        Patent progress data or ``None`` if not found.
    """
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_progress(application_number)


async def get_patent_progress_simple(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> SimplifiedPatentProgressData | None:
    """Get simplified patent progress information."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_progress_simple(application_number)


async def get_patent_divisional_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DivisionalAppInfoData | None:
    """Get divisional application family (parent + descendants)."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_divisional_info(application_number)


async def get_patent_priority_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[PriorityInfo]:
    """Get priority claim information."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_priority_info(application_number)


async def get_patent_applicant_by_code(
    applicant_code: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get applicant name from a 9-digit applicant code."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_applicant_by_code(applicant_code)


async def get_patent_applicant_by_name(
    applicant_name: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get applicant code(s) for an exact applicant name."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_applicant_by_name(applicant_name)


async def get_patent_number_reference(
    kind: CaseNumberKind | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> NumberReference | None:
    """Cross-reference application/publication/registration numbers."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_number_reference(kind, number)


async def get_patent_application_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get applicant-filed documents (opinions/amendments) as a ZIP bundle."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_application_documents(application_number)


async def get_patent_mailed_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get JPO-mailed documents (rejections + decisions) as a ZIP bundle."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_mailed_documents(application_number)


async def get_patent_refusal_notices(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get notices of reasons for refusal as a ZIP bundle."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_refusal_notices(application_number)


async def get_patent_cited_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> CitedDocumentsData | None:
    """Get patent + non-patent cited documents."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_cited_documents(application_number)


async def get_patent_registration_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> RegistrationInfo | None:
    """Get patent registration record."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_registration_info(application_number)


async def get_patent_jplatpat_url(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get J-PlatPat fixed-address URL for a patent application."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_patent_jplatpat_url(application_number)


async def get_patent_pct_national_number(
    kind: PctKind | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> PctNationalPhaseData | None:
    """Get the JP national-phase application number for a PCT number."""
    async with InpiPiClient(username=username, password=password) as client:
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
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_progress(application_number)


async def get_design_progress_simple(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DesignProgressData | None:
    """Get simplified design progress information."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_progress_simple(application_number)


async def get_design_priority_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[PriorityInfo]:
    """Get design priority information."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_priority_info(application_number)


async def get_design_applicant_by_code(
    applicant_code: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get design applicant name from code."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_applicant_by_code(applicant_code)


async def get_design_applicant_by_name(
    applicant_name: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get design applicant code by exact name."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_applicant_by_name(applicant_name)


async def get_design_number_reference(
    kind: CaseNumberKind | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> NumberReference | None:
    """Get design number cross-reference."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_number_reference(kind, number)


async def get_design_application_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get design application documents."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_application_documents(application_number)


async def get_design_mailed_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get mailed design documents."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_mailed_documents(application_number)


async def get_design_refusal_notices(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get design refusal notices."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_refusal_notices(application_number)


async def get_design_registration_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> RegistrationInfo | None:
    """Get design registration information."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design_registration_info(application_number)


async def get_design_jplatpat_url(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get J-PlatPat URL for a design application."""
    async with InpiPiClient(username=username, password=password) as client:
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
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_progress(application_number)


async def get_trademark_progress_simple(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> TrademarkProgressData | None:
    """Get simplified trademark progress information."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_progress_simple(application_number)


async def get_trademark_priority_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[PriorityInfo]:
    """Get trademark priority information."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_priority_info(application_number)


async def get_trademark_applicant_by_code(
    applicant_code: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get trademark applicant name from code."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_applicant_by_code(applicant_code)


async def get_trademark_applicant_by_name(
    applicant_name: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get trademark applicant code by exact name."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_applicant_by_name(applicant_name)


async def get_trademark_number_reference(
    kind: CaseNumberKind | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> NumberReference | None:
    """Get trademark number cross-reference."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_number_reference(kind, number)


async def get_trademark_application_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get trademark application documents."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_application_documents(application_number)


async def get_trademark_mailed_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get mailed trademark documents."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_mailed_documents(application_number)


async def get_trademark_refusal_notices(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get trademark refusal notices."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_refusal_notices(application_number)


async def get_trademark_registration_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> RegistrationInfo | None:
    """Get trademark registration information."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_registration_info(application_number)


async def get_trademark_jplatpat_url(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get J-PlatPat URL for a trademark application."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark_jplatpat_url(application_number)

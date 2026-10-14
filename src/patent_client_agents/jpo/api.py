"""High-level async API for JPO Patent Information Retrieval.

Usage
-----
Preferred: use the client as a context manager::

    async with JpoClient(username="...", password="...") as client:
        progress = await client.get_patent_progress("2020123456")

One-shot convenience functions (create client automatically)::

    progress = await get_patent_progress("2020123456")

Note: One-shot functions require ``JPO_API_USERNAME`` and ``JPO_API_PASSWORD``
environment variables to be set.
"""

from __future__ import annotations

from patent_client_agents.shared.api import one_shot

from .client import JpoClient
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
    "JpoClient",
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


_CREDENTIALS = ("username", "password")


def _new_client(*, username: str | None = None, password: str | None = None) -> JpoClient:
    return JpoClient(username=username, password=password)


# =============================================================================
# Patent API Functions
# =============================================================================


@one_shot(_new_client, JpoClient.get_patent_progress, factory_args=_CREDENTIALS)
async def get_patent_progress(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> PatentProgressData | None:
    """Get full patent progress/status information.

    Args:
        application_number: 10-digit application number (e.g., "2020123456").
        username: JPO username (falls back to ``JPO_API_USERNAME`` env var).
        password: JPO password (falls back to ``JPO_API_PASSWORD`` env var).

    Returns:
        Patent progress data or ``None`` if not found.
    """


@one_shot(_new_client, JpoClient.get_patent_progress_simple, factory_args=_CREDENTIALS)
async def get_patent_progress_simple(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> SimplifiedPatentProgressData | None:
    """Get simplified patent progress information."""


@one_shot(_new_client, JpoClient.get_patent_divisional_info, factory_args=_CREDENTIALS)
async def get_patent_divisional_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DivisionalAppInfoData | None:
    """Get divisional application family (parent + descendants)."""


@one_shot(_new_client, JpoClient.get_patent_priority_info, factory_args=_CREDENTIALS)
async def get_patent_priority_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[PriorityInfo]:
    """Get priority claim information."""


@one_shot(_new_client, JpoClient.get_patent_applicant_by_code, factory_args=_CREDENTIALS)
async def get_patent_applicant_by_code(
    applicant_code: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get applicant name from a 9-digit applicant code."""


@one_shot(_new_client, JpoClient.get_patent_applicant_by_name, factory_args=_CREDENTIALS)
async def get_patent_applicant_by_name(
    applicant_name: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get applicant code(s) for an exact applicant name."""


@one_shot(_new_client, JpoClient.get_patent_number_reference, factory_args=_CREDENTIALS)
async def get_patent_number_reference(
    kind: CaseNumberKind | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> NumberReference | None:
    """Cross-reference application/publication/registration numbers."""


@one_shot(_new_client, JpoClient.get_patent_application_documents, factory_args=_CREDENTIALS)
async def get_patent_application_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get applicant-filed documents (opinions/amendments) as a ZIP bundle."""


@one_shot(_new_client, JpoClient.get_patent_mailed_documents, factory_args=_CREDENTIALS)
async def get_patent_mailed_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get JPO-mailed documents (rejections + decisions) as a ZIP bundle."""


@one_shot(_new_client, JpoClient.get_patent_refusal_notices, factory_args=_CREDENTIALS)
async def get_patent_refusal_notices(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get notices of reasons for refusal as a ZIP bundle."""


@one_shot(_new_client, JpoClient.get_patent_cited_documents, factory_args=_CREDENTIALS)
async def get_patent_cited_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> CitedDocumentsData | None:
    """Get patent + non-patent cited documents."""


@one_shot(_new_client, JpoClient.get_patent_registration_info, factory_args=_CREDENTIALS)
async def get_patent_registration_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> RegistrationInfo | None:
    """Get patent registration record."""


@one_shot(_new_client, JpoClient.get_patent_jplatpat_url, factory_args=_CREDENTIALS)
async def get_patent_jplatpat_url(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get J-PlatPat fixed-address URL for a patent application."""


@one_shot(_new_client, JpoClient.get_patent_pct_national_number, factory_args=_CREDENTIALS)
async def get_patent_pct_national_number(
    kind: PctKind | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> PctNationalPhaseData | None:
    """Get the JP national-phase application number for a PCT number."""


# =============================================================================
# Design API Functions
# =============================================================================


@one_shot(_new_client, JpoClient.get_design_progress, factory_args=_CREDENTIALS)
async def get_design_progress(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DesignProgressData | None:
    """Get design application progress information."""


@one_shot(_new_client, JpoClient.get_design_progress_simple, factory_args=_CREDENTIALS)
async def get_design_progress_simple(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DesignProgressData | None:
    """Get simplified design progress information."""


@one_shot(_new_client, JpoClient.get_design_priority_info, factory_args=_CREDENTIALS)
async def get_design_priority_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[PriorityInfo]:
    """Get design priority information."""


@one_shot(_new_client, JpoClient.get_design_applicant_by_code, factory_args=_CREDENTIALS)
async def get_design_applicant_by_code(
    applicant_code: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get design applicant name from code."""


@one_shot(_new_client, JpoClient.get_design_applicant_by_name, factory_args=_CREDENTIALS)
async def get_design_applicant_by_name(
    applicant_name: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get design applicant code by exact name."""


@one_shot(_new_client, JpoClient.get_design_number_reference, factory_args=_CREDENTIALS)
async def get_design_number_reference(
    kind: CaseNumberKind | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> NumberReference | None:
    """Get design number cross-reference."""


@one_shot(_new_client, JpoClient.get_design_application_documents, factory_args=_CREDENTIALS)
async def get_design_application_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get design application documents."""


@one_shot(_new_client, JpoClient.get_design_mailed_documents, factory_args=_CREDENTIALS)
async def get_design_mailed_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get mailed design documents."""


@one_shot(_new_client, JpoClient.get_design_refusal_notices, factory_args=_CREDENTIALS)
async def get_design_refusal_notices(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get design refusal notices."""


@one_shot(_new_client, JpoClient.get_design_registration_info, factory_args=_CREDENTIALS)
async def get_design_registration_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> RegistrationInfo | None:
    """Get design registration information."""


@one_shot(_new_client, JpoClient.get_design_jplatpat_url, factory_args=_CREDENTIALS)
async def get_design_jplatpat_url(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get J-PlatPat URL for a design application."""


# =============================================================================
# Trademark API Functions
# =============================================================================


@one_shot(_new_client, JpoClient.get_trademark_progress, factory_args=_CREDENTIALS)
async def get_trademark_progress(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> TrademarkProgressData | None:
    """Get trademark application progress information."""


@one_shot(_new_client, JpoClient.get_trademark_progress_simple, factory_args=_CREDENTIALS)
async def get_trademark_progress_simple(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> TrademarkProgressData | None:
    """Get simplified trademark progress information."""


@one_shot(_new_client, JpoClient.get_trademark_priority_info, factory_args=_CREDENTIALS)
async def get_trademark_priority_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[PriorityInfo]:
    """Get trademark priority information."""


@one_shot(_new_client, JpoClient.get_trademark_applicant_by_code, factory_args=_CREDENTIALS)
async def get_trademark_applicant_by_code(
    applicant_code: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get trademark applicant name from code."""


@one_shot(_new_client, JpoClient.get_trademark_applicant_by_name, factory_args=_CREDENTIALS)
async def get_trademark_applicant_by_name(
    applicant_name: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[ApplicantAttorney]:
    """Get trademark applicant code by exact name."""


@one_shot(_new_client, JpoClient.get_trademark_number_reference, factory_args=_CREDENTIALS)
async def get_trademark_number_reference(
    kind: CaseNumberKind | str,
    number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> NumberReference | None:
    """Get trademark number cross-reference."""


@one_shot(_new_client, JpoClient.get_trademark_application_documents, factory_args=_CREDENTIALS)
async def get_trademark_application_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get trademark application documents."""


@one_shot(_new_client, JpoClient.get_trademark_mailed_documents, factory_args=_CREDENTIALS)
async def get_trademark_mailed_documents(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get mailed trademark documents."""


@one_shot(_new_client, JpoClient.get_trademark_refusal_notices, factory_args=_CREDENTIALS)
async def get_trademark_refusal_notices(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> DocumentBundleResult:
    """Get trademark refusal notices."""


@one_shot(_new_client, JpoClient.get_trademark_registration_info, factory_args=_CREDENTIALS)
async def get_trademark_registration_info(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> RegistrationInfo | None:
    """Get trademark registration information."""


@one_shot(_new_client, JpoClient.get_trademark_jplatpat_url, factory_args=_CREDENTIALS)
async def get_trademark_jplatpat_url(
    application_number: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Get J-PlatPat URL for a trademark application."""

"""Async API for USPTO ODP patent applications and PTAB data.

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with UsptoOdpClient() as client:
        results = await client.search_applications(query="machine learning")
        app = await client.get_application("16123456")

One-shot convenience functions (create and close client automatically)::

    results = await search_applications(q="machine learning")

Legacy: passing client= parameter (deprecated, will be removed in v1.0)::

    client = get_client()
    results = await search_applications(q="machine learning", client=client)
    await client.close()  # Manual cleanup required
"""

from __future__ import annotations

import warnings

from ip_tools.uspto_odp import UsptoOdpClient
from ip_tools.uspto_odp.models import (
    ApplicationResponse,
    DocumentsResponse,
    FamilyGraphResponse,
    # PTAB Appeals
    PtabAppealResponse,
    # PTAB Interferences
    PtabInterferenceResponse,
    PtabTrialDecisionResponse,
    PtabTrialDocumentResponse,
    # PTAB Trials
    PtabTrialProceedingResponse,
    SearchResponse,
)

__all__ = [
    "UsptoOdpClient",
    # Application responses
    "SearchResponse",
    "ApplicationResponse",
    "DocumentsResponse",
    "FamilyGraphResponse",
    # PTAB responses
    "PtabTrialProceedingResponse",
    "PtabTrialDecisionResponse",
    "PtabTrialDocumentResponse",
    "PtabAppealResponse",
    "PtabInterferenceResponse",
    # Application functions
    "get_client",
    "search_applications",
    "get_application",
    "list_documents",
    "get_family",
    # PTAB Trial functions
    "search_trial_proceedings",
    "get_trial_proceeding",
    "search_trial_decisions",
    "get_trial_decisions_by_trial",
    "search_trial_documents",
    "get_trial_documents_by_trial",
    # PTAB Appeal functions
    "search_appeal_decisions",
    "get_appeal_decisions_by_number",
    # PTAB Interference functions
    "search_interference_decisions",
    "get_interference_decisions_by_number",
]


def get_client(api_key: str | None = None) -> UsptoOdpClient:
    """Instantiate a USPTO ODP client, defaulting to env var `USPTO_ODP_API_KEY`.

    Prefer using the client as a context manager::

        async with UsptoOdpClient() as client:
            ...

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return UsptoOdpClient(api_key=api_key)


def _warn_client_deprecated() -> None:
    warnings.warn(
        "Passing client= is deprecated and will be removed in v1.0. "
        "Use 'async with UsptoOdpClient() as client:' instead.",
        DeprecationWarning,
        stacklevel=3,
    )


async def search_applications(
    *,
    q: str | None = None,
    fields: list[str] | None = None,
    facets: list[str] | None = None,
    filters: list[str] | None = None,
    range_filters: list[str] | None = None,
    sort: str | None = None,
    limit: int = 25,
    offset: int = 0,
    raw_payload: dict[str, object] | None = None,
    client: UsptoOdpClient | None = None,
) -> SearchResponse:
    """Search USPTO patent applications.

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "query": q,
        "fields": fields,
        "facets": facets,
        "filters": filters,
        "range_filters": range_filters,
        "sort": sort,
        "limit": limit,
        "offset": offset,
        "raw_payload": raw_payload,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_applications(**kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.search_applications(**kwargs)


async def get_application(
    application_number: str,
    *,
    client: UsptoOdpClient | None = None,
) -> ApplicationResponse:
    """Get a patent application by number.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_application(application_number)

    async with UsptoOdpClient() as cl:
        return await cl.get_application(application_number)


async def list_documents(
    application_number: str,
    *,
    include_associated: bool = True,
    client: UsptoOdpClient | None = None,
) -> DocumentsResponse:
    """List documents for a patent application.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_documents(
            application_number,
            include_associated=include_associated,
        )

    async with UsptoOdpClient() as cl:
        return await cl.get_documents(
            application_number,
            include_associated=include_associated,
        )


async def get_family(
    identifier: str,
    *,
    client: UsptoOdpClient | None = None,
) -> FamilyGraphResponse:
    """Get patent family data.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_family(identifier)

    async with UsptoOdpClient() as cl:
        return await cl.get_family(identifier)


# ---------------------------------------------------------------------------
# PTAB Trial Proceedings
# ---------------------------------------------------------------------------


async def search_trial_proceedings(
    *,
    query: str | None = None,
    fields: list[str] | None = None,
    facets: list[str] | None = None,
    filters: list[str] | None = None,
    range_filters: list[str] | None = None,
    sort: str | None = None,
    limit: int = 25,
    offset: int = 0,
    client: UsptoOdpClient | None = None,
) -> PtabTrialProceedingResponse:
    """Search PTAB trial proceedings (IPR, PGR, CBM, DER).

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "query": query,
        "fields": fields,
        "facets": facets,
        "filters": filters,
        "range_filters": range_filters,
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_trial_proceedings(**kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.search_trial_proceedings(**kwargs)


async def get_trial_proceeding(
    trial_number: str,
    *,
    client: UsptoOdpClient | None = None,
) -> PtabTrialProceedingResponse:
    """Get a single PTAB trial proceeding by trial number (e.g., IPR2024-00001).

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_trial_proceeding(trial_number)

    async with UsptoOdpClient() as cl:
        return await cl.get_trial_proceeding(trial_number)


# ---------------------------------------------------------------------------
# PTAB Trial Decisions
# ---------------------------------------------------------------------------


async def search_trial_decisions(
    *,
    query: str | None = None,
    fields: list[str] | None = None,
    facets: list[str] | None = None,
    filters: list[str] | None = None,
    range_filters: list[str] | None = None,
    sort: str | None = None,
    limit: int = 25,
    offset: int = 0,
    client: UsptoOdpClient | None = None,
) -> PtabTrialDecisionResponse:
    """Search PTAB trial decisions.

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "query": query,
        "fields": fields,
        "facets": facets,
        "filters": filters,
        "range_filters": range_filters,
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_trial_decisions(**kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.search_trial_decisions(**kwargs)


async def get_trial_decisions_by_trial(
    trial_number: str,
    *,
    client: UsptoOdpClient | None = None,
) -> PtabTrialDecisionResponse:
    """Get decisions for a specific PTAB trial.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_trial_decisions_by_trial(trial_number)

    async with UsptoOdpClient() as cl:
        return await cl.get_trial_decisions_by_trial(trial_number)


# ---------------------------------------------------------------------------
# PTAB Trial Documents
# ---------------------------------------------------------------------------


async def search_trial_documents(
    *,
    query: str | None = None,
    fields: list[str] | None = None,
    facets: list[str] | None = None,
    filters: list[str] | None = None,
    range_filters: list[str] | None = None,
    sort: str | None = None,
    limit: int = 25,
    offset: int = 0,
    client: UsptoOdpClient | None = None,
) -> PtabTrialDocumentResponse:
    """Search PTAB trial documents.

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "query": query,
        "fields": fields,
        "facets": facets,
        "filters": filters,
        "range_filters": range_filters,
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_trial_documents(**kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.search_trial_documents(**kwargs)


async def get_trial_documents_by_trial(
    trial_number: str,
    *,
    client: UsptoOdpClient | None = None,
) -> PtabTrialDocumentResponse:
    """Get documents for a specific PTAB trial.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_trial_documents_by_trial(trial_number)

    async with UsptoOdpClient() as cl:
        return await cl.get_trial_documents_by_trial(trial_number)


# ---------------------------------------------------------------------------
# PTAB Appeals
# ---------------------------------------------------------------------------


async def search_appeal_decisions(
    *,
    query: str | None = None,
    fields: list[str] | None = None,
    facets: list[str] | None = None,
    filters: list[str] | None = None,
    range_filters: list[str] | None = None,
    sort: str | None = None,
    limit: int = 25,
    offset: int = 0,
    client: UsptoOdpClient | None = None,
) -> PtabAppealResponse:
    """Search PTAB ex parte appeal decisions.

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "query": query,
        "fields": fields,
        "facets": facets,
        "filters": filters,
        "range_filters": range_filters,
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_appeal_decisions(**kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.search_appeal_decisions(**kwargs)


async def get_appeal_decisions_by_number(
    appeal_number: str,
    *,
    client: UsptoOdpClient | None = None,
) -> PtabAppealResponse:
    """Get decisions for a specific PTAB appeal.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_appeal_decisions_by_number(appeal_number)

    async with UsptoOdpClient() as cl:
        return await cl.get_appeal_decisions_by_number(appeal_number)


# ---------------------------------------------------------------------------
# PTAB Interferences
# ---------------------------------------------------------------------------


async def search_interference_decisions(
    *,
    query: str | None = None,
    fields: list[str] | None = None,
    facets: list[str] | None = None,
    filters: list[str] | None = None,
    range_filters: list[str] | None = None,
    sort: str | None = None,
    limit: int = 25,
    offset: int = 0,
    client: UsptoOdpClient | None = None,
) -> PtabInterferenceResponse:
    """Search PTAB interference decisions.

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "query": query,
        "fields": fields,
        "facets": facets,
        "filters": filters,
        "range_filters": range_filters,
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_interference_decisions(**kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.search_interference_decisions(**kwargs)


async def get_interference_decisions_by_number(
    interference_number: str,
    *,
    client: UsptoOdpClient | None = None,
) -> PtabInterferenceResponse:
    """Get decisions for a specific PTAB interference.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_interference_decisions_by_number(interference_number)

    async with UsptoOdpClient() as cl:
        return await cl.get_interference_decisions_by_number(interference_number)

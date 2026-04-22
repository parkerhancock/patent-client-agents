"""PatentsView API client and Pydantic models."""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from law_tools_core import BaseAsyncClient
from law_tools_core.exceptions import ApiError, NotFoundError

logger = logging.getLogger(__name__)

# Default fields to request when not specified
DEFAULT_PATENT_FIELDS = [
    "patent_id",
    "patent_number",
    "patent_title",
    "patent_date",
    "patent_type",
    "patent_num_claims",
    "patent_num_cited_by_us_patents",
]

DEFAULT_PATENT_DETAIL_FIELDS = [
    *DEFAULT_PATENT_FIELDS,
    "patent_abstract",
    "inventors.inventor_id",
    "inventors.inventor_first_name",
    "inventors.inventor_last_name",
    "inventors.inventor_city",
    "inventors.inventor_state",
    "inventors.inventor_country",
    "assignees.assignee_id",
    "assignees.assignee_organization",
    "assignees.assignee_type",
    "cpcs.cpc_section_id",
    "cpcs.cpc_group_id",
    "cpcs.cpc_subgroup_id",
    "examiners.examiner_id",
    "examiners.examiner_first_name",
    "examiners.examiner_last_name",
    "examiners.examiner_group",
]

DEFAULT_CITATION_FIELDS = [
    "patent_id",
    "citation_patent_id",
    "citation_date",
]

DEFAULT_CLAIM_FIELDS = [
    "document_number",
    "claim_number",
    "claim_text",
    "claim_sequence",
    "claim_dependent",
]


FIELD_ALIASES = {
    "patent_number": "patent_id",
    "patent_num_cited_by_us_patents": "patent_num_times_cited_by_us_patents",
    "cpc_group_id": "cpc_current.cpc_group_id",
    "cpc_subgroup_id": "cpc_current.cpc_subgroup_id",
    "assignee_organization": "assignees.assignee_organization",
    "inventor_first_name": "inventors.inventor_name_first",
    "inventor_last_name": "inventors.inventor_name_last",
    "inventors.inventor_first_name": "inventors.inventor_name_first",
    "inventors.inventor_last_name": "inventors.inventor_name_last",
    "cpcs.cpc_section_id": "cpc_current.cpc_class_id",
    "cpcs.cpc_group_id": "cpc_current.cpc_group_id",
    "cpcs.cpc_subgroup_id": "cpc_current.cpc_subgroup_id",
    "examiners.examiner_first_name": "examiners.examiner_name_first",
    "examiners.examiner_last_name": "examiners.examiner_name_last",
    "examiners.examiner_group": "examiners.examiner_art_unit",
}


# -----------------------------------------------------------------------------
# Pydantic Models
# -----------------------------------------------------------------------------


class Patent(BaseModel):
    """Core patent data from PatentsView."""

    patent_id: str
    patent_number: str
    patent_title: str
    patent_date: date | None = None
    patent_type: str | None = None
    patent_num_claims: int | None = None
    patent_num_cited_by_us_patents: int | None = None
    patent_abstract: str | None = None


class Inventor(BaseModel):
    """Inventor information."""

    inventor_id: str
    inventor_first_name: str | None = None
    inventor_last_name: str | None = None
    inventor_city: str | None = None
    inventor_state: str | None = None
    inventor_country: str | None = None

    @property
    def full_name(self) -> str:
        """Return full name as 'First Last'."""
        parts = [self.inventor_first_name, self.inventor_last_name]
        return " ".join(p for p in parts if p)


class Assignee(BaseModel):
    """Assignee/owner information."""

    assignee_id: str
    assignee_organization: str | None = None
    assignee_type: str | None = None


class Examiner(BaseModel):
    """Patent examiner information."""

    examiner_id: str
    examiner_first_name: str | None = None
    examiner_last_name: str | None = None
    examiner_group: str | None = None  # Art unit

    @property
    def full_name(self) -> str:
        """Return full name as 'First Last'."""
        parts = [self.examiner_first_name, self.examiner_last_name]
        return " ".join(p for p in parts if p)


class CpcClassification(BaseModel):
    """CPC classification code."""

    cpc_section_id: str | None = None
    cpc_group_id: str | None = None
    cpc_subgroup_id: str | None = None

    @property
    def full_code(self) -> str:
        """Return full CPC code."""
        return self.cpc_subgroup_id or self.cpc_group_id or self.cpc_section_id or ""


class Citation(BaseModel):
    """Patent citation relationship."""

    citation_patent_id: str
    cited_patent_id: str
    citation_category: str | None = None  # examiner, applicant, other
    citation_sequence: int | None = None


class Claim(BaseModel):
    """Patent claim text and metadata."""

    patent_id: str
    claim_number: int
    claim_text: str
    claim_sequence: int | None = None
    dependent: int | None = None  # None = independent claim

    @property
    def is_independent(self) -> bool:
        """Check if this is an independent claim."""
        return self.dependent is None

    @property
    def word_count(self) -> int:
        """Count words in claim text."""
        return len(self.claim_text.split())


class PatentWithDetails(Patent):
    """Patent with related entities (inventors, assignees, etc.)."""

    inventors: list[Inventor] = Field(default_factory=list)
    assignees: list[Assignee] = Field(default_factory=list)
    cpcs: list[CpcClassification] = Field(default_factory=list)
    examiners: list[Examiner] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Response Models
# -----------------------------------------------------------------------------


class PatentsResponse(BaseModel):
    """Response from patents endpoint."""

    patents: list[PatentWithDetails] = Field(default_factory=list)
    total_patent_count: int = 0
    count: int = 0


class CitationsResponse(BaseModel):
    """Response from citations endpoint."""

    citations: list[Citation] = Field(default_factory=list)
    total_citation_count: int = 0
    count: int = 0


class ClaimsResponse(BaseModel):
    """Response from claims endpoint."""

    claims: list[Claim] = Field(default_factory=list)
    total_claim_count: int = 0
    count: int = 0


# -----------------------------------------------------------------------------
# Client
# -----------------------------------------------------------------------------


def _parse_patent(data: dict[str, Any]) -> PatentWithDetails:
    """Parse a patent dict into PatentWithDetails model."""

    def parse_inventor(inv: dict[str, Any]) -> Inventor:
        return Inventor(
            inventor_id=str(inv.get("inventor_id", "")),
            inventor_first_name=inv.get("inventor_first_name") or inv.get("inventor_name_first"),
            inventor_last_name=inv.get("inventor_last_name") or inv.get("inventor_name_last"),
            inventor_city=inv.get("inventor_city"),
            inventor_state=inv.get("inventor_state"),
            inventor_country=inv.get("inventor_country"),
        )

    def parse_assignee(asg: dict[str, Any]) -> Assignee:
        return Assignee(
            assignee_id=str(asg.get("assignee_id", "")),
            assignee_organization=asg.get("assignee_organization"),
            assignee_type=asg.get("assignee_type"),
        )

    def parse_cpc(cpc: dict[str, Any]) -> CpcClassification:
        return CpcClassification(
            cpc_section_id=cpc.get("cpc_section_id") or cpc.get("cpc_class_id"),
            cpc_group_id=cpc.get("cpc_group_id"),
            cpc_subgroup_id=cpc.get("cpc_subgroup_id") or cpc.get("cpc_group_id"),
        )

    def parse_examiner(ex: dict[str, Any]) -> Examiner:
        return Examiner(
            examiner_id=str(ex.get("examiner_id", "")),
            examiner_first_name=ex.get("examiner_first_name") or ex.get("examiner_name_first"),
            examiner_last_name=ex.get("examiner_last_name") or ex.get("examiner_name_last"),
            examiner_group=ex.get("examiner_group") or ex.get("art_group"),
        )

    inventors = [parse_inventor(inv) for inv in data.get("inventors", []) or []]
    assignees = [parse_assignee(asg) for asg in data.get("assignees", []) or []]
    cpc_rows = data.get("cpcs", []) or data.get("cpc_current", []) or []
    cpcs = [parse_cpc(cpc) for cpc in cpc_rows]
    examiners = [parse_examiner(ex) for ex in data.get("examiners", []) or []]

    # Parse date
    patent_date = None
    if data.get("patent_date"):
        try:
            patent_date = date.fromisoformat(data["patent_date"])
        except ValueError:
            logger.warning("Invalid patent_date format: %s", data["patent_date"])

    return PatentWithDetails(
        patent_id=data.get("patent_id", ""),
        patent_number=data.get("patent_number", "") or data.get("patent_id", ""),
        patent_title=data.get("patent_title", ""),
        patent_date=patent_date,
        patent_type=data.get("patent_type"),
        patent_num_claims=data.get("patent_num_claims"),
        patent_num_cited_by_us_patents=data.get("patent_num_cited_by_us_patents")
        or data.get("patent_num_times_cited_by_us_patents"),
        patent_abstract=data.get("patent_abstract"),
        inventors=inventors,
        assignees=assignees,
        cpcs=cpcs,
        examiners=examiners,
    )


def _translate_field(field: str) -> str:
    """Map legacy PatentsView field names to the current PatentSearch API."""
    return FIELD_ALIASES.get(field, field)


def _translate_fields(fields: list[str] | None) -> list[str]:
    """Translate and de-duplicate requested fields."""
    translated: list[str] = []
    seen: set[str] = set()
    for field in fields or DEFAULT_PATENT_DETAIL_FIELDS:
        mapped = _translate_field(field)
        if mapped not in seen:
            translated.append(mapped)
            seen.add(mapped)
    return translated


def _translate_query(query: Any) -> Any:
    """Translate legacy PatentsView query keys to the current API."""
    if isinstance(query, list):
        return [_translate_query(item) for item in query]
    if not isinstance(query, dict):
        return query

    translated: dict[str, Any] = {}
    for key, value in query.items():
        if key in {"_and", "_or"} and isinstance(value, list):
            translated[key] = [_translate_query(item) for item in value]
            continue
        if key == "_not":
            translated[key] = _translate_query(value)
            continue
        if key in {
            "_gte",
            "_lte",
            "_gt",
            "_lt",
            "_eq",
            "_neq",
            "_begins",
            "_contains",
            "_text_any",
            "_text_all",
            "_text_phrase",
        } and isinstance(value, dict):
            translated[key] = {
                _translate_field(inner_key): _translate_query(inner_value)
                for inner_key, inner_value in value.items()
            }
            continue
        translated[_translate_field(key)] = _translate_query(value)
    return translated


def _coerce_int(value: Any) -> int | None:
    """Convert common API integer payloads to ints."""
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_claim(data: dict[str, Any]) -> Claim:
    """Parse a claim dict into the public Claim model."""
    return Claim(
        patent_id=str(data.get("patent_id") or data.get("document_number") or ""),
        claim_number=_coerce_int(data.get("claim_number")) or 0,
        claim_text=data.get("claim_text", ""),
        claim_sequence=_coerce_int(data.get("claim_sequence")),
        dependent=_coerce_int(data.get("dependent") or data.get("claim_dependent")),
    )


def _normalize_patent_number(patent_number: str) -> str:
    """Normalize patent number for PatentsView lookup.

    PatentsView uses numbers without country prefix or kind codes.
    Example: "US10123456B2" -> "10123456"
    """
    normalized = patent_number.upper().strip()

    # Remove country prefix (US, EP, WO, etc.)
    if normalized[:2].isalpha():
        normalized = normalized[2:]

    # Remove kind code at end (A1, B1, B2, etc.)
    if len(normalized) > 2 and normalized[-2].isalpha():
        normalized = normalized[:-2]
    elif len(normalized) > 1 and normalized[-1].isalpha():
        normalized = normalized[:-1]

    return normalized


class PatentsViewClient(BaseAsyncClient):
    """Async client for PatentsView API.

    Usage::

        async with PatentsViewClient() as client:
            results = await client.search_patents(
                query={"cpc_group_id": "H04L63"},
                fields=["patent_id", "patent_title"],
            )

    The client provides access to patent data including:
    - Patent bibliographic data with citation counts
    - Inventor, assignee, and examiner information
    - CPC classifications
    - Citation relationships
    - Claim text
    """

    DEFAULT_BASE_URL = "https://search.patentsview.org/api/v1"
    CACHE_NAME = "patentsview"
    DEFAULT_TIMEOUT = 30.0

    def __init__(self, *, use_cache: bool = True, api_key: str | None = None) -> None:
        headers = {"Accept": "application/json"}
        resolved_api_key = api_key or os.getenv("PATENTSVIEW_API_KEY")
        if resolved_api_key:
            headers["X-Api-Key"] = resolved_api_key
        super().__init__(use_cache=use_cache, headers=headers)

    async def search_patents(
        self,
        query: dict[str, Any],
        fields: list[str] | None = None,
        sort: list[dict[str, str]] | None = None,
        per_page: int = 25,
        page: int = 1,
    ) -> PatentsResponse:
        """Search patents using PatentsView query language.

        Args:
            query: Query dict (use PatentsViewQuery builder or raw dict)
            fields: Fields to return (defaults to common fields)
            sort: Sort specification, e.g., [{"patent_date": "desc"}]
            per_page: Results per page (max 1000)
            page: Page number (1-indexed)

        Returns:
            PatentsResponse with matching patents and counts
        """
        request_body: dict[str, Any] = {"q": _translate_query(query)}
        request_body["f"] = _translate_fields(fields)
        request_body["o"] = {"per_page": min(per_page, 1000), "page": page}
        if sort:
            request_body["s"] = [
                {_translate_field(key): value for key, value in item.items()} for item in sort
            ]

        data = await self._request_json(
            "POST",
            "/patent/",
            json=request_body,
            context="Patent search",
        )

        patents_data = data.get("patents") or []
        patents = [_parse_patent(p) for p in patents_data]

        return PatentsResponse(
            patents=patents,
            total_patent_count=data.get("total_hits", data.get("total_patent_count", len(patents))),
            count=data.get("count", len(patents)),
        )

    async def get_patent(
        self,
        patent_number: str,
        fields: list[str] | None = None,
    ) -> PatentWithDetails | None:
        """Get a single patent by number.

        Args:
            patent_number: Patent number (e.g., "US10123456B2" or "10123456")
            fields: Fields to return (defaults to detailed fields)

        Returns:
            PatentWithDetails or None if not found
        """
        normalized = _normalize_patent_number(patent_number)
        query = {"patent_id": normalized}

        try:
            result = await self.search_patents(
                query=query,
                fields=fields or DEFAULT_PATENT_DETAIL_FIELDS,
                per_page=1,
            )
            if result.patents:
                return result.patents[0]
            return None
        except NotFoundError:
            return None

    async def get_citations(
        self,
        patent_id: str,
        *,
        direction: str = "citing",
        per_page: int = 100,
        page: int = 1,
    ) -> CitationsResponse:
        """Get citation relationships for a patent.

        Args:
            patent_id: PatentsView patent_id (not patent_number)
            direction: "citing" (patents that cite this one) or
                      "cited" (patents cited by this one)
            per_page: Results per page (max 1000)
            page: Page number (1-indexed)

        Returns:
            CitationsResponse with citation relationships
        """
        if direction == "citing":
            query = {"citation_patent_id": patent_id}
        else:
            query = {"patent_id": patent_id}

        request_body: dict[str, Any] = {
            "q": query,
            "f": DEFAULT_CITATION_FIELDS,
            "o": {"per_page": min(per_page, 1000), "page": page},
        }

        data = await self._request_json(
            "POST",
            "/patent/us_patent_citation/",
            json=request_body,
            context="Citations query",
        )

        citations_data = data.get("us_patent_citations") or data.get("citations") or []
        citations = [
            Citation(
                citation_patent_id=str(c.get("patent_id", "")),
                cited_patent_id=str(c.get("citation_patent_id", "")),
                citation_category=c.get("citation_category"),
                citation_sequence=_coerce_int(c.get("citation_sequence")),
            )
            for c in citations_data
        ]

        return CitationsResponse(
            citations=citations,
            total_citation_count=data.get(
                "total_hits", data.get("total_citation_count", len(citations))
            ),
            count=data.get("count", len(citations)),
        )

    async def get_claims(
        self,
        patent_id: str,
        *,
        per_page: int = 100,
        page: int = 1,
    ) -> ClaimsResponse:
        """Get claims for a patent.

        Args:
            patent_id: PatentsView patent_id (not patent_number)
            per_page: Results per page (max 1000)
            page: Page number (1-indexed)

        Returns:
            ClaimsResponse with claim text and metadata
        """
        params = {
            "q": json.dumps({"document_number": patent_id}),
            "f": json.dumps(DEFAULT_CLAIM_FIELDS),
            "o": json.dumps({"per_page": min(per_page, 1000), "page": page}),
            "s": json.dumps([{"claim_sequence": "asc"}]),
        }
        try:
            data = await self._request_json(
                "GET",
                "/g_claim/",
                params=params,
                context="Claims query",
            )
        except (ApiError, NotFoundError) as exc:
            logger.warning("PatentsView claims endpoint unavailable for %s: %s", patent_id, exc)
            return ClaimsResponse()

        claims_data = data.get("g_claims") or data.get("claims") or []
        claims = [_parse_claim(c) for c in claims_data]

        return ClaimsResponse(
            claims=claims,
            total_claim_count=data.get("total_hits", data.get("total_claim_count", len(claims))),
            count=data.get("count", len(claims)),
        )


__all__ = [
    # Client
    "PatentsViewClient",
    # Models
    "Patent",
    "PatentWithDetails",
    "Inventor",
    "Assignee",
    "Examiner",
    "CpcClassification",
    "Citation",
    "Claim",
    # Response models
    "PatentsResponse",
    "CitationsResponse",
    "ClaimsResponse",
    # Field defaults
    "DEFAULT_PATENT_FIELDS",
    "DEFAULT_PATENT_DETAIL_FIELDS",
    "DEFAULT_CITATION_FIELDS",
    "DEFAULT_CLAIM_FIELDS",
]

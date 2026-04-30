"""Client utilities for interacting with Google Patents."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import time
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from lxml import html
from markitdown import MarkItDown
from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

from law_tools_core.resilience import default_retryer

from .cache import build_cached_http_client
from .parsers import extract_claims, extract_figures, extract_metadata

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limiter — Google Patents returns 503 after ~3 rapid requests and
# requires a multi-minute cooldown. This limits to 1 request per
# _MIN_INTERVAL seconds and backs off on 503s.
# ---------------------------------------------------------------------------

_MIN_INTERVAL = 4.0  # seconds between requests
_COOLDOWN_SECONDS = 90.0  # wait after a 503 before retrying

_rate_lock = asyncio.Lock()
_last_request_time: float = 0.0
_cooldown_until: float = 0.0


async def _rate_limit() -> None:
    """Wait until we are allowed to make the next Google Patents request."""
    global _last_request_time
    async with _rate_lock:
        now = time.monotonic()
        # If we are in a cooldown period from a 503, wait it out
        if now < _cooldown_until:
            wait = _cooldown_until - now
            logger.info("Google Patents cooldown: waiting %.0fs", wait)
            await asyncio.sleep(wait)
            now = time.monotonic()
        # Enforce minimum interval between requests
        elapsed = now - _last_request_time
        if elapsed < _MIN_INTERVAL:
            await asyncio.sleep(_MIN_INTERVAL - elapsed)
        _last_request_time = time.monotonic()


def _trigger_cooldown() -> None:
    """Start a cooldown period after a 503 response."""
    global _cooldown_until
    _cooldown_until = time.monotonic() + _COOLDOWN_SECONDS
    logger.warning(
        "Google Patents rate limited (503) — cooling down for %.0fs",
        _COOLDOWN_SECONDS,
    )


def _build_http_client(*, use_cache: bool):
    """Build an HTTP client with optional caching for Google Patents."""
    return build_cached_http_client(
        use_cache=use_cache,
        cache_name="google_patents",
        headers={"Accept-Language": "en-US,en;q=0.9"},
        follow_redirects=True,
    )


_PARA_NUM_RE = re.compile(r'<para-num\s+num="(\[\d+\])"\s*>\s*</para-num>')
# Hidden spans that contain duplicate paragraph numbers scattered throughout text
_HIDDEN_PARA_SPAN_RE = re.compile(
    r'<span\s+style="display:\s*none"\s*>\s*\[\d+\]\s*</span>',
    re.IGNORECASE,
)


def _preprocess_patent_html(html_string: str) -> str:
    """Preprocess Google Patents HTML to preserve paragraph numbers.

    Google Patents uses two representations of paragraph markers:
    1. <para-num num="[0001]"></para-num> at paragraph starts (good)
    2. <span style="display: none">[0001]</span> scattered mid-text (bad)

    This function:
    - Converts <para-num> tags to visible [0001] text at paragraph starts
    - Removes hidden spans that would otherwise pollute the text
    """
    # First remove hidden spans with paragraph numbers (they appear mid-sentence)
    result = _HIDDEN_PARA_SPAN_RE.sub("", html_string)
    # Then convert para-num tags to visible text at paragraph starts
    result = _PARA_NUM_RE.sub(r"\1 ", result)
    return result


def _html_to_markdown(html_string: str | None) -> str | None:
    """Convert HTML string to markdown using MarkItDown."""
    if not html_string:
        return None
    try:
        # Preprocess to preserve paragraph numbers
        preprocessed = _preprocess_patent_html(html_string)
        md = MarkItDown(enable_plugins=False)
        stream = io.BytesIO(preprocessed.encode("utf-8"))
        result = md.convert_stream(stream, file_extension=".html")
        return result.text_content
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to convert HTML to markdown: %s", exc)
        return None


class CpcClassification(BaseModel):
    """CPC classification code with description."""

    code: str
    description: str = ""


class PatentCitation(BaseModel):
    """A patent citation (cited or citing)."""

    publication_number: str
    publication_date: str | None = None
    assignee: str | None = None
    title: str | None = None
    examiner_cited: bool = False


class FamilyMember(BaseModel):
    """A member of the patent family."""

    application_number: str
    publication_number: str | None = None
    status: str | None = None
    priority_date: str | None = None
    filing_date: str | None = None
    title: str | None = None


class CountryFiling(BaseModel):
    """A country filing in the patent family."""

    country_code: str
    count: int = 1
    representative_publication: str | None = None


class PriorityApplication(BaseModel):
    """A priority application claim."""

    application_number: str
    publication_number: str | None = None
    priority_date: str | None = None
    filing_date: str | None = None
    title: str | None = None


class LegalEvent(BaseModel):
    """A legal event in the patent's history."""

    date: str | None = None
    title: str | None = None
    assignee: str | None = None
    assignor: str | None = None
    status: str | None = None


class NonPatentLiterature(BaseModel):
    """A non-patent literature citation."""

    citation: str
    examiner_cited: bool = False


class Concept(BaseModel):
    """A Google-extracted concept from the patent."""

    name: str
    image_url: str | None = None


class Landscape(BaseModel):
    """A technology area classification."""

    name: str
    type: str = ""


class Definition(BaseModel):
    """A term definition extracted from the patent text."""

    term: str
    definition: str
    paragraph: str = ""


class ChildApplication(BaseModel):
    """A child application (continuation, divisional)."""

    application_number: str
    relation_type: str | None = None
    publication_number: str | None = None
    priority_date: str | None = None
    filing_date: str | None = None
    title: str | None = None


class DetailedNpl(BaseModel):
    """Detailed non-patent literature with title and link."""

    title: str
    url: str | None = None


class ChemicalCompound(BaseModel):
    """Chemical compound data from a patent."""

    id: str | None = None
    name: str | None = None
    smiles: str | None = None
    inchi_key: str | None = None
    domain: str | None = None
    similarity: str | None = None


class ExternalLink(BaseModel):
    """An external link to USPTO, Espacenet, Global Dossier, etc."""

    url: str
    id: str | None = None
    name: str | None = None


def _build_citations(
    citations: list[dict[str, str | None | bool]],
) -> list[PatentCitation]:
    """Build PatentCitation objects from raw dict data (with examiner_cited)."""
    result: list[PatentCitation] = []
    for c in citations:
        pub_num = c.get("publication_number")
        if pub_num and isinstance(pub_num, str):
            pub_date = c.get("publication_date")
            assignee = c.get("assignee")
            title = c.get("title")
            examiner_cited = c.get("examiner_cited")
            result.append(
                PatentCitation(
                    publication_number=pub_num,
                    publication_date=pub_date if isinstance(pub_date, str) else None,
                    assignee=assignee if isinstance(assignee, str) else None,
                    title=title if isinstance(title, str) else None,
                    examiner_cited=bool(examiner_cited),
                )
            )
    return result


def _build_citations_simple(
    citations: list[dict[str, str | None]],
) -> list[PatentCitation]:
    """Build PatentCitation objects from raw dict data (without examiner_cited)."""
    result: list[PatentCitation] = []
    for c in citations:
        pub_num = c.get("publication_number")
        if pub_num:
            result.append(
                PatentCitation(
                    publication_number=pub_num,
                    publication_date=c.get("publication_date"),
                    assignee=c.get("assignee"),
                    title=c.get("title"),
                    examiner_cited=False,
                )
            )
    return result


def _build_family_members(
    members: list[dict[str, str | None]],
) -> list[FamilyMember]:
    """Build FamilyMember objects from raw dict data."""
    result: list[FamilyMember] = []
    for m in members:
        app_num = m.get("application_number")
        if app_num:
            result.append(
                FamilyMember(
                    application_number=app_num,
                    publication_number=m.get("publication_number"),
                    status=m.get("status"),
                    priority_date=m.get("priority_date"),
                    filing_date=m.get("filing_date"),
                    title=m.get("title"),
                )
            )
    return result


def _build_country_filings(
    filings: list[dict[str, str | int | None]],
) -> list[CountryFiling]:
    """Build CountryFiling objects from raw dict data."""
    result: list[CountryFiling] = []
    for f in filings:
        country = f.get("country_code")
        if country:
            count_val = f.get("count")
            result.append(
                CountryFiling(
                    country_code=str(country),
                    count=int(count_val) if count_val is not None else 1,
                    representative_publication=(
                        str(f["representative_publication"])
                        if f.get("representative_publication") is not None
                        else None
                    ),
                )
            )
    return result


def _build_priority_applications(
    priorities: list[dict[str, str | None]],
) -> list[PriorityApplication]:
    """Build PriorityApplication objects from raw dict data."""
    result: list[PriorityApplication] = []
    for p in priorities:
        app_num = p.get("application_number")
        if app_num:
            result.append(
                PriorityApplication(
                    application_number=app_num,
                    publication_number=p.get("publication_number"),
                    priority_date=p.get("priority_date"),
                    filing_date=p.get("filing_date"),
                    title=p.get("title"),
                )
            )
    return result


def _build_legal_events(
    events: list[dict[str, str | None]],
) -> list[LegalEvent]:
    """Build LegalEvent objects from raw dict data."""
    result: list[LegalEvent] = []
    for e in events:
        # Include event if it has at least a title or date
        if e.get("title") or e.get("date"):
            result.append(
                LegalEvent(
                    date=e.get("date"),
                    title=e.get("title"),
                    assignee=e.get("assignee"),
                    assignor=e.get("assignor"),
                    status=e.get("status"),
                )
            )
    return result


def _build_non_patent_literature(
    npl: list[dict[str, str | None]],
) -> list[NonPatentLiterature]:
    """Build NonPatentLiterature objects from raw dict data."""
    result: list[NonPatentLiterature] = []
    for n in npl:
        citation = n.get("citation")
        if citation:
            examiner_cited = n.get("examiner_cited") == "true"
            result.append(
                NonPatentLiterature(
                    citation=citation,
                    examiner_cited=examiner_cited,
                )
            )
    return result


def _build_concepts(
    concepts: list[dict[str, str | None]],
) -> list[Concept]:
    """Build Concept objects from raw dict data."""
    result: list[Concept] = []
    for c in concepts:
        name = c.get("name")
        if name:
            result.append(
                Concept(
                    name=name,
                    image_url=c.get("image_url"),
                )
            )
    return result


def _build_landscapes(
    landscapes: list[dict[str, str]],
) -> list[Landscape]:
    """Build Landscape objects from raw dict data."""
    result: list[Landscape] = []
    for ls in landscapes:
        name = ls.get("name")
        if name:
            result.append(
                Landscape(
                    name=name,
                    type=ls.get("type", ""),
                )
            )
    return result


def _build_definitions(
    definitions: list[dict[str, str]],
) -> list[Definition]:
    """Build Definition objects from raw dict data."""
    result: list[Definition] = []
    for d in definitions:
        term = d.get("term")
        definition = d.get("definition")
        if term and definition:
            result.append(
                Definition(
                    term=term,
                    definition=definition,
                    paragraph=d.get("paragraph", ""),
                )
            )
    return result


def _build_child_applications(
    children: list[dict[str, str | None]],
) -> list[ChildApplication]:
    """Build ChildApplication objects from raw dict data."""
    result: list[ChildApplication] = []
    for c in children:
        app_num = c.get("application_number")
        if app_num:
            result.append(
                ChildApplication(
                    application_number=app_num,
                    relation_type=c.get("relation_type"),
                    publication_number=c.get("publication_number"),
                    priority_date=c.get("priority_date"),
                    filing_date=c.get("filing_date"),
                    title=c.get("title"),
                )
            )
    return result


def _build_detailed_npl(
    npl: list[dict[str, str | None]],
) -> list[DetailedNpl]:
    """Build DetailedNpl objects from raw dict data."""
    result: list[DetailedNpl] = []
    for n in npl:
        title = n.get("title")
        if title:
            result.append(
                DetailedNpl(
                    title=title,
                    url=n.get("url"),
                )
            )
    return result


def _build_chemical_data(
    compounds: list[dict[str, str | None]],
) -> list[ChemicalCompound]:
    """Build ChemicalCompound objects from raw dict data."""
    result: list[ChemicalCompound] = []
    for c in compounds:
        # Only include if there's actual chemical data
        if c.get("smiles") or c.get("inchi_key"):
            result.append(
                ChemicalCompound(
                    id=c.get("id"),
                    name=c.get("name"),
                    smiles=c.get("smiles"),
                    inchi_key=c.get("inchi_key"),
                    domain=c.get("domain"),
                    similarity=c.get("similarity"),
                )
            )
    return result


def _build_external_links(
    links: list[dict[str, str]],
) -> list[ExternalLink]:
    """Build ExternalLink objects from raw dict data."""
    result: list[ExternalLink] = []
    for link in links:
        url = link.get("url")
        if url:
            result.append(
                ExternalLink(
                    url=url,
                    id=link.get("id"),
                    name=link.get("name"),
                )
            )
    return result


class PatentData(BaseModel):
    """Patent data fetched from Google Patents."""

    patent_number: str
    application_number: str | None = None
    title: str
    abstract: str
    status: str
    current_assignee: str
    original_assignee: str | None = None
    inventors: list[str] = Field(default_factory=list)
    filing_date: str
    grant_date: str
    publication_date: str | None = None
    expiration_date: str = Field(
        default="",
        description=(
            "Anticipated expiration as YYYY-MM-DD, or empty string if unknown. "
            "When ``expiration_estimated`` is True, this value came from the "
            "priority_date + 20y fallback (Google Patents had no structured "
            "expiration data for this patent, typical of newly-granted utilities). "
            "An estimate computed this way may be wrong by months — refine via "
            "USPTO ODP (applicationFilingDate + 20y + "
            "patentTermAdjustmentData.adjustmentTotalQuantity days, with a "
            "continuity-chain walk for the earliest non-provisional filing) "
            "before relying on it for legally-significant work."
        ),
    )
    expiration_estimated: bool = Field(
        default=False,
        description=(
            "True iff ``expiration_date`` came from the priority+20y fallback "
            "because Google Patents had no structured expiration data. "
            "**Refine via USPTO ODP for accurate patent term.**"
        ),
    )
    priority_date: str | None = None
    claims: list[dict[str, str | None]]
    description: str
    description_html: str | None = None
    description_markdown: str | None = None
    pdf_url: str | None
    structured_limitations: dict[str, list[str]] = Field(default_factory=dict)
    # Original language fields (for non-English patents)
    source_language: str | None = None  # ISO 639-1 code (e.g., "ja", "de", "zh")
    original_title: str | None = None
    original_abstract: str | None = None
    original_limitations: dict[str, list[str]] = Field(default_factory=dict)
    # Publication metadata
    kind_code: str | None = None
    publication_description: str | None = None
    legal_status_category: str | None = None
    # Family and classification fields
    family_id: str | None = None
    cpc_classifications: list[CpcClassification] = Field(default_factory=list)
    landscapes: list[Landscape] = Field(default_factory=list)
    cited_patents: list[PatentCitation] = Field(default_factory=list)
    citing_patents: list[PatentCitation] = Field(default_factory=list)
    cited_patents_family: list[PatentCitation] = Field(default_factory=list)
    citing_patents_family: list[PatentCitation] = Field(default_factory=list)
    family_members: list[FamilyMember] = Field(default_factory=list)
    country_filings: list[CountryFiling] = Field(default_factory=list)
    similar_patents: list[str] = Field(default_factory=list)
    priority_applications: list[PriorityApplication] = Field(default_factory=list)
    child_applications: list[ChildApplication] = Field(default_factory=list)
    apps_claiming_priority: list[PriorityApplication] = Field(default_factory=list)
    # Legal events and literature fields
    legal_events: list[LegalEvent] = Field(default_factory=list)
    non_patent_literature: list[NonPatentLiterature] = Field(default_factory=list)
    detailed_non_patent_literature: list[DetailedNpl] = Field(default_factory=list)
    prior_art_keywords: list[str] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    definitions: list[Definition] = Field(default_factory=list)
    chemical_data: list[ChemicalCompound] = Field(default_factory=list)
    # External resources
    external_links: list[ExternalLink] = Field(default_factory=list)
    raw_html: str | None = None


class GooglePatentsSearchResult(BaseModel):
    """Lightweight entry returned from the Google Patents search API."""

    result_type: str = Field(description="`patent`, `scholar`, or `web` result type")
    id: str
    rank: int
    title: str | None = None
    snippet: str | None = None
    publication_number: str | None = None
    language: str | None = None
    priority_date: str | None = None
    filing_date: str | None = None
    grant_date: str | None = None
    publication_date: str | None = None
    inventor: str | None = None
    assignee: str | None = None
    pdf_url: str | None = None
    thumbnail_url: str | None = None
    detail_url: str | None = None
    family_country_status: list[dict[str, Any]] = Field(default_factory=list)


class GooglePatentsSearchResponse(BaseModel):
    """Structured payload for google_patents.search."""

    query_url: str
    total_results: int
    total_pages: int
    page: int
    page_size: int
    has_more: bool
    results: list[GooglePatentsSearchResult]


_SEARCH_ENDPOINT = "https://patents.google.com/xhr/query"
_PDF_BASE = "https://patentimages.storage.googleapis.com/"


def _custom_encode(value: str) -> str:
    """Mirror the custom encoder used by the Google Patents front-end."""

    replacements = "&?/,=+%#"
    encoded_chars: list[str] = []
    for char in value:
        if char in replacements:
            encoded_chars.append("%" + format(ord(char), "x"))
        elif char == " ":
            encoded_chars.append("+")
        else:
            encoded_chars.append(char)
    return "".join(encoded_chars)


def _clean_list(values: Sequence[str] | None) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    for value in values:
        stripped = value.strip()
        if stripped:
            cleaned.append(stripped)
    return cleaned


def _normalize_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("Dates must be provided as YYYY-MM-DD") from exc
    return parsed.strftime("%Y-%m-%d")


def _resolve_expiration_date(
    gp_expiration: str,
    priority_date: str | None,
) -> tuple[str, bool]:
    """Resolve ``expiration_date`` with a priority+20y fallback.

    Google Patents doesn't populate ``expiration_date`` for newly-granted
    patents (typical for grants in the last ~6 months) — its structured
    data lacks the field until backfill. As an unblock for callers who
    need *some* answer, we compute ``priority_date + 20 years`` as a
    rough estimate.

    **The estimate is approximate.** It assumes the recorded priority
    date represents the term-controlling effective filing date, which
    holds for most US utility patents but underestimates term where only
    foreign or provisional priority is claimed (since the US filing
    comes later). Estimates should be refined via USPTO ODP — see the
    field docstrings on :class:`PatentData` for the recommended
    computation.

    Args:
        gp_expiration: The expiration date as extracted from Google Patents.
        priority_date: The patent's priority date (ISO YYYY-MM-DD) if known.

    Returns:
        ``(expiration_date, estimated)`` where:

        * Google Patents had a value → ``(gp_expiration, False)``
        * GP empty but priority parseable → ``(priority+20y, True)``
        * Neither available → ``("", False)``
    """
    if gp_expiration:
        return gp_expiration, False

    if not priority_date:
        return "", False

    try:
        parsed = datetime.strptime(priority_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        logger.debug("Unable to parse priority_date %r for expiration estimate", priority_date)
        return "", False

    try:
        estimate = parsed.replace(year=parsed.year + 20)
    except ValueError:
        # Feb 29 in priority year, target year isn't a leap year — clamp to Feb 28.
        estimate = parsed.replace(year=parsed.year + 20, day=28)
    return estimate.isoformat(), True


def _join_encoded(values: Iterable[str]) -> str:
    return ",".join(_custom_encode(value) for value in values)


def _build_detail_url(result_id: str | None) -> str | None:
    if not result_id:
        return None
    return f"https://patents.google.com/{result_id}"


def _build_pdf_url(pdf_path: str | None) -> str | None:
    if not pdf_path:
        return None
    return f"{_PDF_BASE}{pdf_path}"


def _build_thumbnail_url(thumbnail_path: str | None) -> str | None:
    if not thumbnail_path:
        return None
    return f"{_PDF_BASE}{thumbnail_path}"


def _build_query_url(
    *,
    keywords: Sequence[str] | None = None,
    cpc_codes: Sequence[str] | None = None,
    inventors: Sequence[str] | None = None,
    assignees: Sequence[str] | None = None,
    countries: Sequence[str] | None = None,
    languages: Sequence[str] | None = None,
    date_type: str | None = None,
    filed_after: str | None = None,
    filed_before: str | None = None,
    status: str | None = None,
    patent_type: str | None = None,
    litigation: str | None = None,
    include_patents: bool = True,
    include_npl: bool = False,
    sort: str | None = None,
    dups: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    cluster_results: bool | None = None,
    local: str | None = None,
) -> str:
    parts: list[str] = []

    keyword_values = _clean_list(keywords)
    for term in keyword_values:
        parts.append(f"q={_custom_encode(term)}")

    cpc_values = _clean_list(cpc_codes)
    if cpc_values:
        parts.append(f"cpc={_join_encoded(cpc_values)}")

    inventor_values = _clean_list(inventors)
    if inventor_values:
        parts.append(f"inventor={_join_encoded(inventor_values)}")

    assignee_values = _clean_list(assignees)
    if assignee_values:
        parts.append(f"assignee={_join_encoded(assignee_values)}")

    country_values = [value.strip().upper() for value in countries or [] if value.strip()]
    if country_values:
        parts.append(f"country={','.join(country_values)}")

    language_values = [value.strip().lower() for value in languages or [] if value.strip()]
    if language_values:
        parts.append(f"language={','.join(language_values)}")

    target_date_type = date_type or "priority"
    if filed_after:
        parts.append(f"after={target_date_type}:{_normalize_date(filed_after)}")
    if filed_before:
        parts.append(f"before={target_date_type}:{_normalize_date(filed_before)}")

    if status:
        parts.append(f"status={_custom_encode(status)}")
    if patent_type:
        parts.append(f"type={_custom_encode(patent_type)}")
    if litigation:
        parts.append(f"litigation={_custom_encode(litigation)}")

    if page_size and page_size != 10:
        parts.append(f"num={page_size}")

    if not include_patents:
        parts.append("patents=false")
    if include_npl:
        parts.append("scholar")

    if sort:
        sort_value = sort.lower()
        if sort_value not in {"new", "old"}:
            raise ValueError("sort must be 'new' or 'old'")
        parts.append(f"sort={sort_value}")

    if dups:
        parts.append(f"dups={_custom_encode(dups)}")

    if page is not None and page > 1:
        parts.append(f"page={page - 1}")

    if cluster_results:
        parts.append("clustered=true")
    if local:
        parts.append(f"local={_custom_encode(local)}")

    if not parts:
        raise ValueError(
            "Provide at least one search term (keyword, CPC, inventor, assignee, country, "
            "or language)."
        )

    return "&".join(parts)


def _parse_search_results(payload: dict[str, Any], query_url: str) -> GooglePatentsSearchResponse:
    results_payload = payload.get("results", {})
    clusters = results_payload.get("cluster", []) or []
    flattened: list[GooglePatentsSearchResult] = []

    for cluster in clusters:
        for entry in cluster.get("result", []) or []:
            result_id = entry.get("id")
            rank = entry.get("rank", 0)
            patent_data = entry.get("patent")
            scholar_data = entry.get("scholar")
            web_data = entry.get("webdoc")

            if patent_data:
                result_type = "patent"
                data = patent_data
            elif scholar_data:
                result_type = "scholar"
                data = scholar_data
            elif web_data:
                result_type = "web"
                data = web_data
            else:
                continue

            flattened.append(
                GooglePatentsSearchResult(
                    result_type=result_type,
                    id=result_id or "",
                    rank=rank,
                    title=data.get("title"),
                    snippet=data.get("snippet"),
                    publication_number=data.get("publication_number") or data.get("number"),
                    language=data.get("language"),
                    priority_date=data.get("priority_date"),
                    filing_date=data.get("filing_date"),
                    grant_date=data.get("grant_date"),
                    publication_date=data.get("publication_date"),
                    inventor=data.get("inventor"),
                    assignee=data.get("assignee"),
                    pdf_url=_build_pdf_url(data.get("pdf")),
                    thumbnail_url=_build_thumbnail_url(data.get("thumbnail")),
                    detail_url=_build_detail_url(result_id),
                    family_country_status=(
                        data.get("family_metadata", {})
                        .get("aggregated", {})
                        .get("country_status", [])
                    ),
                )
            )

    total_results = results_payload.get("total_num_results", len(flattened))
    total_pages = results_payload.get("total_num_pages", 1)
    current_page = results_payload.get("num_page", 0)
    page_size = len(flattened)
    has_more = current_page + 1 < total_pages

    return GooglePatentsSearchResponse(
        query_url=query_url,
        total_results=total_results,
        total_pages=total_pages,
        page=current_page + 1,
        page_size=page_size,
        has_more=has_more,
        results=flattened,
    )


def _normalize_patent_number(patent_number: str) -> str:
    normalized = patent_number.upper().strip()

    if normalized and normalized[0].isdigit():
        normalized = f"US{normalized}"

    if re.match(r"^US\d{4}\d{6}A1$", normalized) and len(normalized) == 14:
        normalized = f"{normalized[:6]}0{normalized[6:]}"

    if re.match(r"^WO\d{2}[0-9]+[A-Z][0-9]*$", normalized) and len(normalized) <= 12:
        year_part = normalized[2:4]
        century = "19" if int(year_part) >= 80 else "20"
        suffix = normalized[4:]
        normalized = (
            f"WO{century}{year_part}0{suffix}"
            if len(suffix) >= 5
            else f"WO{century}{normalized[2:]}"
        )

    return normalized


async def fetch_patent_from_google_patents(
    patent_number: str,
    use_cache: bool = True,
) -> PatentData:
    """Fetch Google Patents metadata, claims, and structured limitations parsed from HTML.

    Retrieves comprehensive patent data including:
    - Basic metadata (title, abstract, status, assignee, inventors)
    - Dates (filing, grant, publication, expiration, priority)
    - Claims and full specification (text, HTML, and markdown)
    - Structured claim limitations parsed by claim number
    - Patent family data and country filings
    - Citations (cited/citing patents, non-patent literature)
    - CPC classifications and technology landscapes
    - Legal events and status changes
    - Concepts, definitions, and chemical data
    - Links to external resources (USPTO, Espacenet, etc.)

    Args:
        patent_number: Patent publication number (e.g., 'US8206789B2', 'EP3123456B1')
        use_cache: Whether to use cached responses (default: True)

    Returns:
        PatentData with 50+ fields of patent information parsed from Google Patents HTML
    """

    normalized = _normalize_patent_number(patent_number)
    logger.debug("Fetching patent data for %s", normalized)
    url = f"https://patents.google.com/patent/{normalized}/en"

    await _rate_limit()
    async with _build_http_client(use_cache=use_cache) as client:
        try:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            if response.status_code == 503:
                _trigger_cooldown()
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network failures
            logger.error("Error fetching patent %s: %s", normalized, exc)
            raise

        if "Sorry, we couldn't find this patent" in response.text:
            logger.warning("Patent %s not found in Google Patents", normalized)
            raise FileNotFoundError(f"Patent {normalized} not found on Google Patents")

        document = html.fromstring(response.text)
        metadata = extract_metadata(document, response.text, patent_number=normalized)
        description = metadata["description"]
        description_html = metadata["description_html"]
        description_markdown = _html_to_markdown(description_html)
        claims, structured_limitations, original_limitations = extract_claims(document)

        # Detect source language from patent number prefix and original text presence
        source_language: str | None = None
        original_title: str | None = None
        original_abstract: str | None = None

        # Check if we have original text in claims (indicates non-English patent)
        has_original = any(c.get("original_text") for c in claims)
        if has_original:
            # Detect language from patent number country code
            country_code = normalized[:2].upper()
            language_map = {
                "JP": "ja",  # Japanese
                "CN": "zh",  # Chinese
                "KR": "ko",  # Korean
                "DE": "de",  # German
                "FR": "fr",  # French
                "ES": "es",  # Spanish
                "IT": "it",  # Italian
                "RU": "ru",  # Russian
                "BR": "pt",  # Portuguese (Brazil)
            }
            source_language = language_map.get(country_code)

            # Extract original title and abstract from metadata
            original_title = metadata.get("original_title")
            original_abstract = metadata.get("original_abstract")

        status_value = metadata["status"] or "Unknown"
        title_value = metadata["title"]

        logger.debug("Successfully fetched patent %s: %s", normalized, title_value)

        publication_date = metadata["publication_date"] or None
        priority_date = metadata["priority_date"] or None

        expiration_date, expiration_estimated = _resolve_expiration_date(
            metadata["expiration_date"], priority_date
        )

        return PatentData(
            patent_number=normalized,
            application_number=metadata["application_number"],
            title=title_value,
            abstract=metadata["abstract"],
            status=status_value or "Unknown",
            current_assignee=metadata["current_assignee"],
            original_assignee=metadata["original_assignee"],
            inventors=list(metadata["inventors"]),
            filing_date=metadata["filing_date"],
            grant_date=metadata["grant_date"],
            publication_date=publication_date,
            expiration_date=expiration_date,
            expiration_estimated=expiration_estimated,
            priority_date=priority_date,
            claims=claims,
            description=description,
            description_html=description_html,
            description_markdown=description_markdown,
            pdf_url=metadata["pdf_url"],
            structured_limitations=structured_limitations,
            # Original language fields
            source_language=source_language,
            original_title=original_title,
            original_abstract=original_abstract,
            original_limitations=original_limitations,
            # Publication metadata
            kind_code=metadata["kind_code"],
            publication_description=metadata["publication_description"],
            legal_status_category=metadata["legal_status_category"],
            # Family and classification fields
            family_id=metadata["family_id"],
            cpc_classifications=[CpcClassification(**c) for c in metadata["cpc_classifications"]],
            landscapes=_build_landscapes(metadata["landscapes"]),
            cited_patents=_build_citations(metadata["cited_patents"]),
            citing_patents=_build_citations(metadata["citing_patents"]),
            cited_patents_family=_build_citations_simple(metadata["cited_patents_family"]),
            citing_patents_family=_build_citations_simple(metadata["citing_patents_family"]),
            family_members=_build_family_members(metadata["family_members"]),
            country_filings=_build_country_filings(metadata["country_filings"]),
            similar_patents=metadata["similar_patents"],
            priority_applications=_build_priority_applications(metadata["priority_applications"]),
            child_applications=_build_child_applications(metadata["child_applications"]),
            apps_claiming_priority=_build_priority_applications(metadata["apps_claiming_priority"]),
            # Legal events and literature fields
            legal_events=_build_legal_events(metadata["legal_events"]),
            non_patent_literature=_build_non_patent_literature(metadata["non_patent_literature"]),
            detailed_non_patent_literature=_build_detailed_npl(
                metadata["detailed_non_patent_literature"]
            ),
            prior_art_keywords=metadata["prior_art_keywords"],
            concepts=_build_concepts(metadata["concepts"]),
            definitions=_build_definitions(metadata["definitions"]),
            chemical_data=_build_chemical_data(metadata["chemical_data"]),
            # External resources
            external_links=_build_external_links(metadata["external_links"]),
            raw_html=response.text,
        )


class GooglePatentsClient:
    """Client wrapper that proxies requests through the Google Patents fetcher.

    Can be used as a context manager for consistency with other clients::

        async with GooglePatentsClient() as client:
            patent = await client.get_patent_data("US7654321B2")

    Note: This client is stateless and creates HTTP connections per-request,
    so the context manager is optional but recommended for API consistency.
    """

    def __init__(self, *, use_cache: bool = True) -> None:
        self._use_cache = use_cache

    async def __aenter__(self) -> GooglePatentsClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        # Stateless client - no cleanup needed
        pass

    async def _fetch_with_retry(self, patent_number: str) -> PatentData:
        normalized = _normalize_patent_number(patent_number)
        async for attempt in default_retryer(max_attempts=4):
            with attempt:
                return await fetch_patent_from_google_patents(normalized, use_cache=self._use_cache)
        raise RuntimeError(f"Unable to fetch patent data for {normalized} after retries")

    async def _get_patent_data(self, patent_number: str) -> PatentData:
        return await self._fetch_with_retry(patent_number)

    async def get_patent_data(self, patent_number: str) -> PatentData | None:
        try:
            return await self._fetch_with_retry(patent_number)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error retrieving patent data for %s: %s", patent_number, exc)
            return None

    async def get_patent_details(self, patent_number: str) -> dict[str, object] | None:
        try:
            patent = await self._get_patent_data(patent_number)
        except Exception as exc:  # pragma: no cover
            logger.error("Error getting patent details for %s: %s", patent_number, exc)
            return None

        def _parse_date(value: str | None) -> date | None:
            if not value:
                return None
            stripped = value.strip()
            for fmt in ("%b %d, %Y", "%Y-%m-%d", "%d %b %Y"):
                try:
                    return datetime.strptime(stripped, fmt).date()
                except ValueError:
                    continue
            return None

        filing_date = _parse_date(patent.filing_date)
        issue_date = _parse_date(patent.grant_date)

        return {
            "patent_number": patent.patent_number,
            "application_number": patent.application_number,
            "title": patent.title,
            "filing_date": filing_date,
            "issue_date": issue_date,
            "claim_count": len(patent.claims),
            "status": patent.status,
            "abstract": patent.abstract,
            "inventors": patent.inventors,
        }

    async def search_patents(
        self,
        *,
        keywords: Sequence[str] | None = None,
        cpc_codes: Sequence[str] | None = None,
        inventors: Sequence[str] | None = None,
        assignees: Sequence[str] | None = None,
        countries: Sequence[str] | None = None,
        languages: Sequence[str] | None = None,
        date_type: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        status: str | None = None,
        patent_type: str | None = None,
        litigation: str | None = None,
        include_patents: bool = True,
        include_npl: bool = False,
        sort: str | None = None,
        dups: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        cluster_results: bool | None = None,
        local: str | None = None,
    ) -> GooglePatentsSearchResponse:
        query_url = _build_query_url(
            keywords=keywords,
            cpc_codes=cpc_codes,
            inventors=inventors,
            assignees=assignees,
            countries=countries,
            languages=languages,
            date_type=date_type,
            filed_after=filed_after,
            filed_before=filed_before,
            status=status,
            patent_type=patent_type,
            litigation=litigation,
            include_patents=include_patents,
            include_npl=include_npl,
            sort=sort,
            dups=dups,
            page=page,
            page_size=page_size,
            cluster_results=cluster_results,
            local=local,
        )

        params = {"url": query_url}

        await _rate_limit()
        async with _build_http_client(use_cache=False) as client:
            response = await client.get(
                _SEARCH_ENDPOINT,
                params=params,
                headers={"Accept": "application/json"},
                timeout=30.0,
            )

        text = response.text.strip()
        if text.startswith("<") or response.status_code == 503:
            _trigger_cooldown()
            raise RuntimeError(
                "Google Patents rate limited. The request will be retried "
                "automatically after a cooldown period."
            )

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise RuntimeError("Unable to parse Google Patents search response") from exc

        return _parse_search_results(payload, query_url)

    async def get_patent_claims(self, patent_number: str) -> list[dict[str, object]] | None:
        try:
            patent = await self._get_patent_data(patent_number)
        except Exception as exc:  # pragma: no cover
            logger.error("Error getting patent claims for %s: %s", patent_number, exc)
            return None

        claims_payload: list[dict[str, object]] = []
        for claim in patent.claims:
            number = claim.get("number")
            claims_payload.append(
                {
                    "claim_number": int(number)
                    if isinstance(number, str) and number.isdigit()
                    else number,
                    "claim_text": claim.get("text"),
                    "claim_type": claim.get("type"),
                    "depends_on": claim.get("depends_on"),
                }
            )
        return claims_payload

    async def get_structured_claim_limitations(
        self, patent_number: str
    ) -> dict[str, list[str]] | None:
        try:
            patent = await self._get_patent_data(patent_number)
        except Exception as exc:  # pragma: no cover
            logger.error(
                "Error getting structured claim limitations for %s: %s", patent_number, exc
            )
            return None

        return patent.structured_limitations

    async def get_patent_pdf_url(self, patent_number: str) -> str | None:
        try:
            patent = await self._get_patent_data(patent_number)
        except Exception as exc:  # pragma: no cover
            logger.error("Error getting patent PDF URL for %s: %s", patent_number, exc)
            return None

        return patent.pdf_url

    async def get_patent_figures(self, patent_number: str) -> list[dict[str, Any]] | None:
        try:
            patent = await self._get_patent_data(patent_number)
        except Exception as exc:  # pragma: no cover
            logger.error("Error getting patent figures for %s: %s", patent_number, exc)
            return None

        html_payload = patent.raw_html
        if not html_payload:
            try:
                refreshed = await fetch_patent_from_google_patents(
                    patent_number, use_cache=self._use_cache
                )
            except Exception as exc:  # pragma: no cover
                logger.error("Error refetching patent %s for figures: %s", patent_number, exc)
                return None
            patent = refreshed
            html_payload = refreshed.raw_html
        if not html_payload:
            logger.warning("Patent %s missing raw HTML for figure parsing", patent_number)
            return None

        document = html.fromstring(html_payload)
        return extract_figures(document)

    async def download_patent_pdf(
        self,
        patent_number: str,
        *,
        use_cache: bool = True,
    ) -> bytes:
        patent = await self.get_patent_data(patent_number)
        if not patent or not patent.pdf_url:
            raise ValueError(f"No PDF URL available for {patent_number}")

        pdf_url = patent.pdf_url
        if pdf_url.startswith("//"):
            pdf_url = f"https:{pdf_url}"
        elif pdf_url.startswith("/"):
            pdf_url = f"https://patents.google.com{pdf_url}"

        async with _build_http_client(use_cache=use_cache) as client:
            response = await client.get(pdf_url, timeout=45.0, follow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" not in content_type:
                reported_type = content_type or "unknown"
                raise ValueError(
                    f"Expected PDF content for {patent_number}, received {reported_type}"
                )
            return response.content


__all__ = [
    "PatentData",
    "GooglePatentsClient",
    "fetch_patent_from_google_patents",
]

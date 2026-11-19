"""Consolidated USPTO facade tools (public toolset).

Thin dispatchers over the per-source USPTO tool functions in
``patent_client_agents.mcp.tools.{uspto,publications,office_actions}``. No
business logic lives here: each branch forwards to an existing function
that already returns the §5.9 envelope, so the §5.15 per-module helpers and
the canonical templates stay untouched.

Design note — only homogeneous-signature searches fold into ``search_uspto``
(applications, publications, petitions, office-action full text, trademark
decisions, status codes: ``query``/``limit``/``full``). The legacy office
action datasets (``result_type`` + ``criteria``/``start``/``rows``) and assignments
(``by`` axis + date filters) keep their own facade tools; folding their
distinct query languages would reintroduce the argument-shape ambiguity this
consolidation exists to remove. The ``get_*`` side is uniform (single
identifier in, ``ListEnvelope`` out), so ``get_uspto`` folds all six.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.mcp.tools.office_actions import (
    get_office_action,
    search_office_action_full_text,
    search_office_actions,
)
from patent_client_agents.mcp.tools.patent_assignments import search_patent_assignments
from patent_client_agents.mcp.tools.publications import (
    get_patent_publication,
    search_patent_publications,
)
from patent_client_agents.mcp.tools.uspto import (
    download_file_history,
    get_application,
    get_file_history_item,
    get_patent_assignment,
    get_petition,
    get_trademark_decision,
    list_file_history,
    search_application_status_codes,
    search_applications,
    search_petitions,
    search_trademark_decisions,
)
from patent_client_agents.uspto_odp.clients.applications import ApplicationSection

uspto_facade_mcp = FastMCP("USPTO")


@uspto_facade_mcp.tool(annotations=READ_ONLY)
async def search_uspto(
    dataset: Annotated[
        Literal[
            "applications",
            "publications",
            "petitions",
            "office_actions",
            "trademark_decisions",
            "status_codes",
        ],
        "Which USPTO index to search. 'applications' = ODP application "
        "metadata (title, CPC, dates, status — NOT claim/spec text). "
        "'publications' = Public Search (PPUBS) full text (claims, "
        "specification, abstract). 'petitions' = decided patent petition "
        "records. 'office_actions' = full text of examiner office actions "
        "(rejections, allowances, restrictions; applications filed 2001+). "
        "'trademark_decisions' = trademark expungement/reexamination "
        "proceedings, petitions to the Director, and administrative "
        "sanctions orders. 'status_codes' = what a numeric application "
        "status code means.",
    ],
    query: Annotated[
        str,
        "Search query. Publications: PPUBS syntax with field codes "
        "(CLM/SPEC/AB/TI/IN/AS). Every other dataset: free text plus "
        "Lucene field:value terms (AND/OR, quoted phrases, [a TO b] ranges). "
        "Fields by dataset — applications: applicationMetaData.inventionTitle, "
        ".filingDate, .cpcClassificationBag, .examinerNameText. petitions: "
        "decidedPetitionTypeCodeDescriptionText (GRANTED | DENIED | "
        "DISMISSED), decisionPetitionTypeCodeDescriptionText, "
        "applicationNumberText, decisionDate, finalDecidingOfficeName. "
        "office_actions: officeActionText, applicationNumberText, "
        "documentCode (CTNF | CTFR | NOA | CTRS), rejectionTypeBag (101 | "
        "102 | 103 | 112 | DoublePatent), groupArtUnitNumber, "
        "submissionDate. trademark_decisions: decisionProceedingCategory "
        "(ExpungReexam | PetitionsToDirector | Administrative), "
        "serialNumber, registrationNumber, markLiteralText, registrantName, "
        "decisionActionDate, precedentialIndicator. status_codes: "
        "applicationStatusCode, applicationStatusDescriptionText. "
        "Example (applications): 'applicationMetaData.inventionTitle:\"neural\"'. "
        "Example (publications): '\"machine learning\" AND neural.CLM.'. "
        'Example (office_actions): \'officeActionText:"abstract idea" AND '
        "documentCode:CTFR AND groupArtUnitNumber:3689'. "
        "Example (trademark_decisions): 'registrationNumber:6458316'.",
    ],
    limit: Annotated[int, "Maximum results to return (1-20 for publications)."] = 20,
    offset: Annotated[
        int,
        "Result offset for pagination. PPUBS publications paginate by limit only (offset ignored).",
    ] = 0,
    full: Annotated[
        bool,
        "False (default) = lean stub per hit (small). True = full record per "
        "hit (large; prefer get_uspto for a single record). Ignored for "
        "status_codes.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search USPTO records — applications, publications, petitions, office actions, trademark decisions.

    Routes to the right USPTO index by ``dataset``. NOTE: 'applications'
    searches metadata only; for claim/specification text use
    'publications'. 'office_actions' searches what examiners wrote; for
    structured per-claim rejection flags or the prior art cited in an action
    use the dedicated ``search_office_actions``. For one record by identifier
    use ``get_uspto``; for prosecution documents use ``get_file_history``;
    for assignments use ``search_patent_assignments``; for trademark
    register records use ``search_trademarks``.

    Related tools: get_uspto, get_file_history, search_office_actions,
    search_patent_assignments, search_trademarks.
    """
    if dataset == "applications":
        return await search_applications(query=query, limit=limit, offset=offset, full=full)
    if dataset == "publications":
        return await search_patent_publications(query=query, limit=limit, full=full)
    if dataset == "office_actions":
        return await search_office_action_full_text(
            query=query, limit=limit, offset=offset, full=full
        )
    if dataset == "trademark_decisions":
        return await search_trademark_decisions(query=query, limit=limit, offset=offset, full=full)
    if dataset == "status_codes":
        return await search_application_status_codes(query=query, limit=limit, offset=offset)
    return await search_petitions(query=query, limit=limit, offset=offset, full=full)


def _looks_like_application_number(value: str) -> bool:
    """True if ``value`` is a bare USPTO application serial (digits + separators)."""
    return value.strip().replace("/", "").replace(",", "").replace(" ", "").isdigit()


def _require_application_numbers(dataset: str, identifier: str | list[str]) -> None:
    """Reject patent/publication-number-shaped ids for application/assignment lookups.

    The ODP application and assignment endpoints key on a numeric application
    number (8+ digits, e.g. '16123456'). Passing a patent or publication number
    (e.g. 'US10123456B2') here just 404s at USPTO — catch it locally with a
    pointer to the right dataset instead of burning a round-trip per id.
    """
    ids = [identifier] if isinstance(identifier, str) else list(identifier)
    bad = [i for i in ids if not _looks_like_application_number(i)]
    if not bad:
        return
    shown = ", ".join(bad[:5]) + ("…" if len(bad) > 5 else "")
    raise ValidationError(
        f"get_uspto(dataset='{dataset}') needs a numeric USPTO application "
        f"number (8+ digits, e.g. '16123456'), but got {len(bad)} "
        f"patent/publication-style identifier(s): {shown}. For a patent or "
        f"publication number, use dataset='publication'. To look up the "
        f"application from a patent number, find it first with "
        f"search_uspto(dataset='applications')."
    )


@uspto_facade_mcp.tool(annotations=READ_ONLY)
async def get_uspto(
    dataset: Annotated[
        Literal[
            "application",
            "publication",
            "petition",
            "office_action",
            "assignment",
            "trademark_decision",
        ],
        "What kind of record the identifier names. 'application' = ODP "
        "application metadata. 'publication' = PPUBS patent text. 'petition' "
        "= petition decision record. 'office_action' = office-action "
        "document with its complete body text. 'assignment' = recorded assignments "
        "for an application. 'trademark_decision' = trademark decision or "
        "proceeding record (text excerpt, TSDR link, whether a PDF exists).",
    ],
    identifier: Annotated[
        str | list[str],
        "The record identifier, or a list for portfolio workflows. By "
        "dataset: application/assignment → application number (8+ digits, "
        "e.g. '16123456'); publication → publication or patent number (e.g. "
        "'US20230012345A1', 'US10123456B2'); petition → petition record id "
        "(from search); office_action → document_identifier from "
        "search_uspto(dataset='office_actions') or search_office_actions; "
        "trademark_decision → document_identifier from "
        "search_uspto(dataset='trademark_decisions').",
    ],
    section: Annotated[
        ApplicationSection | None,
        "dataset='application' only: return one part of the file wrapper "
        "instead of the full record. 'meta-data' = bibliographic data; "
        "'adjustment' = patent term adjustment and its history; 'attorney' = "
        "correspondence address and attorneys of record; 'continuity' = "
        "parent/child applications; 'foreign-priority' = priority claims; "
        "'transactions' = dated prosecution events; 'associated-documents' = "
        "PGPub and grant XML file metadata.",
    ] = None,
) -> ListEnvelope[dict]:
    """Fetch USPTO records by identifier — application, publication, petition, office action, assignment, trademark decision.

    Always returns a ``ListEnvelope`` (stable shape whether you pass one id
    or many). For status/dates use dataset='application'; for claim/spec
    text use dataset='publication'. Find identifiers with ``search_uspto``
    (or ``search_office_actions`` / ``search_patent_assignments``).

    Related tools: search_uspto, get_file_history.
    """
    if section is not None and dataset != "application":
        raise ValidationError(
            f"get_uspto(section={section!r}) applies only to dataset='application', "
            f"not dataset={dataset!r}."
        )
    if dataset == "application":
        _require_application_numbers(dataset, identifier)
        if section is None:
            return await get_application(identifier)
        return await get_application(identifier, section=section)
    if dataset == "trademark_decision":
        return await get_trademark_decision(identifier)
    if dataset == "publication":
        return await get_patent_publication(publication_number=identifier)
    if dataset == "petition":
        return await get_petition(identifier)
    if dataset == "office_action":
        return await get_office_action(identifier)
    _require_application_numbers(dataset, identifier)
    return await get_patent_assignment(identifier)


@uspto_facade_mcp.tool(annotations=READ_ONLY)
async def get_file_history(
    application_number: Annotated[
        str, "USPTO application number (8+ digits). Example: '16123456'."
    ],
    mode: Annotated[
        Literal["list", "item", "download"],
        "'list' (default) = enumerate file-history documents with codes and "
        "dates. 'item' = download one document in an exact format (needs "
        "document_identifier). 'download' = bulk-download matching PDFs.",
    ] = "list",
    document_identifier: Annotated[
        str | None,
        "Required when mode='item'. A document_identifier from mode='list'.",
    ] = None,
    format: Annotated[
        Literal["pdf", "xml", "docx"],
        "mode='item' artifact format: 'pdf' (default), 'xml', or 'docx'. "
        "The item is returned without OCR or text extraction.",
    ] = "pdf",
    item_ids: Annotated[
        list[str] | None,
        "mode='download': specific document_identifier values. None = all "
        "documents matching the other filters.",
    ] = None,
    document_codes: Annotated[
        list[str] | None,
        "mode='download': filter to USPTO document codes (e.g. ['CTNF', 'NOA']).",
    ] = None,
    after: Annotated[
        str | None, "mode='download': include docs on/after this date (YYYY-MM-DD)."
    ] = None,
    before: Annotated[
        str | None, "mode='download': include docs on/before this date (YYYY-MM-DD)."
    ] = None,
) -> Any:
    """Work with a USPTO application's prosecution file history — list, read one, or bulk-download.

    Return shape varies by mode. 'list' returns a ``ListEnvelope`` of document
    descriptors. 'item' returns one signed PDF, XML, or DOCX download.
    'download' returns ``ResourceLink``s plus a zip manifest. Discover document
    ids, codes, and available formats with mode='list' first.

    Related tools: search_uspto, get_uspto.
    """
    if mode == "item":
        if not document_identifier:
            raise ValidationError(
                "get_file_history(mode='item') requires document_identifier "
                "(get one from mode='list')."
            )
        return await get_file_history_item(application_number, document_identifier, format=format)
    if mode == "download":
        return await download_file_history(
            application_number,
            item_ids=item_ids,
            document_codes=document_codes,
            after=after,
            before=before,
        )
    return await list_file_history(application_number)


# Heterogeneous-signature searches kept standalone (see module docstring): their
# own internal enums (office actions: result_type; assignments: by-axis + date
# filters) don't fold into search_uspto without a fat optional-param bag that
# hurts routing. Re-expose them verbatim on the facade — full schema preserved.
uspto_facade_mcp.tool(annotations=READ_ONLY)(search_office_actions)
uspto_facade_mcp.tool(annotations=READ_ONLY)(search_patent_assignments)

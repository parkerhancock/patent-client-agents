"""Consolidated EPO facade tools (public toolset).

Thin dispatchers over the per-source EPO Open Patent Services tool functions
in ``patent_client_agents.mcp.tools.epo_ops``. No business logic lives here:
each branch forwards to an existing function that already returns the §5.9
envelope, so the §5.15 per-module helpers and the canonical templates stay
untouched.

Design note — the EPO ``get_*`` retrievals fold into ``get_epo`` because
they are uniform at the call surface (one identifier in, an envelope out).
``family_intelligence`` and ``unitary_status`` take one publication number;
the other views also accept lists. The dispatcher forwards the identifier
unchanged and returns the underlying envelope as-is, so each view's native
shape and provenance survive the dispatch (return type is ``Any`` to cover
both envelope kinds).

``search_epo`` is already well-shaped (a single EPO OPS CQL search with its
own ``group_by`` / pagination cursor surface), so it is re-exposed verbatim —
full schema preserved, no re-declaration.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP

from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.mcp.tools.epo_ops import (
    get_epo_biblio,
    get_epo_citations,
    get_epo_equivalents,
    get_epo_family,
    get_epo_family_intelligence,
    get_epo_fulltext,
    get_epo_legal_events,
    get_epo_procedural_steps,
    get_epo_register_biblio,
    get_epo_register_events,
    get_epo_unitary_patent_status,
    search_epo,
)

epo_facade_mcp = FastMCP("EPO")


@epo_facade_mcp.tool(annotations=READ_ONLY)
async def get_epo(
    view: Annotated[
        Literal[
            "biblio",
            "citations",
            "equivalents",
            "family",
            "family_intelligence",
            "fulltext",
            "legal_events",
            "procedural_steps",
            "register_biblio",
            "register_events",
            "unitary_status",
        ],
        "Which EPO record to fetch for the patent. 'biblio' = bibliographic "
        "data (title, applicants, inventors, IPC/CPC, priority). 'family' = "
        "INPADOC family members (priority-linked publications across "
        "jurisdictions). 'family_intelligence' = source-separated family, "
        "backward-citation, legal-event, and EP Register evidence for one "
        "publication, without a family-wide legal-status conclusion. "
        "'fulltext' = claims + description. 'legal_events' = "
        "legal-status timeline (filing, publication, grant, lapse). "
        "'citations' = structured backward patent and non-patent citations. "
        "'equivalents' = simple-family equivalent publications. "
        "'register_biblio' = correction-aware European Patent Register "
        "bibliographic data for one or more EP publications. "
        "'register_events' = European Patent Register dossier events. "
        "'procedural_steps' = European Patent Register dossier chronology. "
        "'unitary_status' = EPO Register Unitary Patent (UP) record (single EP "
        "number only).",
    ],
    identifier: Annotated[
        str | list[str],
        "Patent document number, or a list for portfolio workflows. Examples: "
        "'EP1234567A1', ['EP1234567A1', 'US10123456B2']. EPO OPS accepts "
        "country-prefixed publication numbers across all jurisdictions it "
        "indexes. NOTE: views 'family_intelligence' and 'unitary_status' take "
        "a single publication number. Pass the granted B1 when known for "
        "unitary_status.",
    ],
) -> Any:
    """Fetch one structured EPO OPS or European Patent Register view.

    Family intelligence and unitary status take one publication number; the
    other views also accept lists. Find identifiers with ``search_epo``;
    convert number formats with ``resolve_patent_number``.

    Related tools: search_epo, resolve_patent_number.
    """
    if view == "biblio":
        return await get_epo_biblio(identifier)
    if view == "family":
        return await get_epo_family(identifier)
    if view == "family_intelligence":
        if isinstance(identifier, list):
            raise ValidationError("view='family_intelligence' requires a single publication number")
        return await get_epo_family_intelligence(identifier)
    if view == "fulltext":
        return await get_epo_fulltext(identifier)
    if view == "legal_events":
        return await get_epo_legal_events(identifier)
    if view == "citations":
        return await get_epo_citations(identifier)
    if view == "equivalents":
        return await get_epo_equivalents(identifier)
    if view == "register_biblio":
        return await get_epo_register_biblio(identifier)
    if view == "register_events":
        return await get_epo_register_events(identifier)
    if view == "procedural_steps":
        return await get_epo_procedural_steps(identifier)
    if isinstance(identifier, list):
        raise ValidationError("view='unitary_status' requires a single EP publication number")
    return await get_epo_unitary_patent_status(identifier)


# search_epo is already well-shaped — a single EPO OPS CQL search with its own
# group_by axis and opaque pagination cursor. Re-expose it verbatim on the
# facade; the full schema is preserved with no re-declaration.
epo_facade_mcp.tool(annotations=READ_ONLY)(search_epo)

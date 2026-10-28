"""Consolidated legal-reference facade tools (public toolset).

Thin dispatchers over the per-corpus substantive-law tool functions in
``patent_client_agents.mcp.tools.*``. No business logic lives here: each
branch forwards to an existing function that already returns the §5.9
envelope (with §4 ``corpus_synced_at`` / ``corpus_version`` provenance for
``substantive_law`` corpora), so the §5.15 per-module helpers and the
canonical templates stay untouched.

This pair collapses 28 corpus tools → 2 — the single biggest consolidation
win — because the 12 bundled SQLite/FTS5 corpora share one
search-then-fetch-section interface. The 14-value corpus enum is the
primary eval risk, so the enum values are stable, mnemonic, and grouped by
office in the docstrings; all folded corpora share one schema.

Design note — divergence handling (DOCUMENTED, eval-risk tool):

* 12 corpora fold cleanly. Their search side is the uniform
  ``(query, limit, offset, syntax, sort, full)`` shape; ``dpma`` and
  ``india_statutes`` add one optional ``statute`` Act-filter, surfaced here
  as the optional ``statute`` param (forwarded only for those two). The get
  side is uniform single-identifier in / ``ListEnvelope`` out — the
  underlying param is named ``section`` for examination-manual corpora and
  ``citation`` for statute corpora; the dispatch passes the facade's
  ``identifier`` positionally so the name difference is absorbed.
* ``upc`` and ``wipo_lex`` do NOT fold. UPC search keys off
  ``instrument`` + ``language`` (no plain ``query``/``syntax`` axis; no
  per-section get — get takes an instrument key), and WIPO Lex search keys
  off ``country_codes`` / ``subject_matter`` / ``type_of_text`` filters
  (no plain ``query``) with a ``legislation_id`` get. Folding either into
  the uniform shape would reintroduce the argument-shape ambiguity this
  consolidation removes, so both keep their full schemas via verbatim
  re-expose at the bottom of this module. They are intentionally absent
  from the corpus enum (the enum lists only what these dispatchers handle);
  the docstrings point to the dedicated tools for discovery.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.mcp.tools.dpma_statutes import (
    get_dpma_section,
    search_dpma_statutes,
)
from patent_client_agents.mcp.tools.epc import get_epc_section, search_epc
from patent_client_agents.mcp.tools.epo_case_law import (
    get_epo_case_law_section,
    search_epo_case_law,
)
from patent_client_agents.mcp.tools.epo_guidelines import (
    get_epo_guidelines_section,
    search_epo_guidelines,
)
from patent_client_agents.mcp.tools.epo_pct_guidelines import (
    get_epo_pct_guidelines_section,
    search_epo_pct_guidelines,
)
from patent_client_agents.mcp.tools.epo_up_guidelines import (
    get_epo_up_guidelines_section,
    search_epo_up_guidelines,
)
from patent_client_agents.mcp.tools.ipo_in_mppp import (
    get_ipo_in_mppp_section,
    search_ipo_in_mppp,
)
from patent_client_agents.mcp.tools.ipo_in_statutes import (
    get_ipo_in_section,
    search_ipo_in_statutes,
)
from patent_client_agents.mcp.tools.mpep import get_mpep_section, search_mpep
from patent_client_agents.mcp.tools.trademarks import get_tmep_section, search_tmep
from patent_client_agents.mcp.tools.tw_trade_secrets import (
    get_tw_trade_secrets_section,
    search_tw_trade_secrets,
)
from patent_client_agents.mcp.tools.ukipo_mopp import get_mopp_section, search_mopp
from patent_client_agents.mcp.tools.upc import get_upc_section, search_upc_statutes
from patent_client_agents.mcp.tools.wipo_lex import (
    get_wipo_lex_legislation,
    search_wipo_lex_legislation,
)

legal_reference_facade_mcp = FastMCP("Legal references")

# Corpus enum — the 12 corpora whose search+get pairs fold cleanly. The enum
# lists ONLY what these dispatchers actually handle (no advertise-then-redirect):
# ``upc`` and ``wipo_lex`` have divergent signatures and live as their own
# standalone tools (search_upc_statutes / search_wipo_lex_legislation, re-exposed
# verbatim below).
Corpus = Literal[
    "uspto_mpep",
    "uspto_tmep",
    "epo_guidelines",
    "epo_pct_guidelines",
    "epo_up_guidelines",
    "epo_case_law",
    "epc",
    "dpma",
    "ukipo_mopp",
    "india_statutes",
    "india_mppp",
    "tw_trade_secrets",
]

# corpus enum value -> (search_fn, get_fn) for the 12 cleanly-folding corpora.
# ``upc`` / ``wipo_lex`` are intentionally absent: their pairs diverge and are
# re-exposed verbatim instead (see module docstring). The dispatch re-resolves
# each pair through this module's namespace by ``__name__`` at call time (see
# ``_resolve``) so the patch seam tests rely on — patching
# ``...facade.legal_reference.<fn>`` — works, matching the USPTO facade.
_ROUTES = {
    "uspto_mpep": (search_mpep, get_mpep_section),
    "uspto_tmep": (search_tmep, get_tmep_section),
    "epo_guidelines": (search_epo_guidelines, get_epo_guidelines_section),
    "epo_pct_guidelines": (search_epo_pct_guidelines, get_epo_pct_guidelines_section),
    "epo_up_guidelines": (search_epo_up_guidelines, get_epo_up_guidelines_section),
    "epo_case_law": (search_epo_case_law, get_epo_case_law_section),
    "epc": (search_epc, get_epc_section),
    "dpma": (search_dpma_statutes, get_dpma_section),
    "ukipo_mopp": (search_mopp, get_mopp_section),
    "india_statutes": (search_ipo_in_statutes, get_ipo_in_section),
    "india_mppp": (search_ipo_in_mppp, get_ipo_in_mppp_section),
    "tw_trade_secrets": (search_tw_trade_secrets, get_tw_trade_secrets_section),
}


def _resolve(fn):
    """Return the current module attribute named ``fn.__name__``.

    Lets ``unittest.mock.patch`` swap the target by attribute name while the
    canonical reference still lives in ``_ROUTES`` (keeping the imports live).
    """
    return globals().get(fn.__name__, fn)


# Corpora whose search side accepts the optional ``statute`` Act-filter.
_STATUTE_FILTER_CORPORA = {"dpma", "india_statutes"}


@legal_reference_facade_mcp.tool(annotations=READ_ONLY)
async def search_legal_reference(
    corpus: Annotated[
        Corpus,
        "Which legal-reference corpus to search. US: 'uspto_mpep' "
        "(patent examiner manual), 'uspto_tmep' (trademark examiner manual). "
        "EPO: 'epo_guidelines', 'epo_pct_guidelines', 'epo_up_guidelines' "
        "(unitary patent), 'epo_case_law' (Boards of Appeal), 'epc' (the "
        "Convention). National statutes/manuals: 'dpma' (Germany), "
        "'ukipo_mopp' (UK), 'india_statutes', 'india_mppp' (India patent "
        "practice), 'tw_trade_secrets' (Taiwan). For UPC or WIPO Lex law use "
        "the dedicated search_upc_statutes / search_wipo_lex_legislation.",
    ],
    query: Annotated[
        str,
        "Search query. Examples: 'subject matter eligibility', 'inventive "
        "step', 'restriction requirement'. Default treats terms as a phrase "
        "(or all-terms for statute corpora); set syntax to widen.",
    ],
    limit: Annotated[int, "Maximum hits to return (1-100)."] = 25,
    offset: Annotated[int, "Result offset for pagination."] = 0,
    syntax: Annotated[
        str,
        "Query syntax: 'adj' (phrase), 'and' (all terms), 'or' (any term), "
        "'exact'. Per-corpus default differs (manuals='adj', statutes='and').",
    ] = "adj",
    sort: Annotated[
        str,
        "'relevance' (BM25, default) or 'outline' (section/citation order).",
    ] = "relevance",
    statute: Annotated[
        str | None,
        "Act filter — corpus='dpma': 'PatG'/'MarkenG'/'GebrMG'/'DesignG'/"
        "'UrhG'/'GeschGehG'; corpus='india_statutes': 'Patents Act'/"
        "'Patent Rules'/'Designs Act'/'Trade Marks Act'/'Copyright Act'. "
        "Ignored for other corpora. Omit to search across all Acts.",
    ] = None,
    full: Annotated[
        bool,
        "False (default) = lean stub per hit. True = full upstream row.",
    ] = False,
    version: Annotated[
        str, "MPEP installed release selector; other corpora support current only."
    ] = "current",
) -> ListEnvelope[dict]:
    """Search a legal-reference corpus — statutes, examination manuals, or guidelines.

    Routes to one of 12 bundled substantive-law corpora by ``corpus`` and
    returns relevance-ranked snippet hits. Find a provision, then call
    ``get_legal_reference`` with the same ``corpus`` and the hit's
    section/citation identifier for the full text. The ``statute`` filter
    applies only to corpus='dpma' and 'india_statutes'. For corpus='upc' or
    'wipo_lex' use ``search_upc_statutes`` / ``search_wipo_lex_legislation``.

    Related tools: get_legal_reference, search_upc_statutes, search_wipo_lex_legislation.
    """
    search_fn = _resolve(_ROUTES[corpus][0])
    if corpus == "uspto_mpep":
        return await search_fn(
            query=query,
            limit=limit,
            offset=offset,
            syntax=syntax,
            sort=sort,
            full=full,
            version=version,
        )
    if version != "current":
        raise ValueError("Explicit version selection is supported only for uspto_mpep")
    if corpus in _STATUTE_FILTER_CORPORA:
        return await search_fn(
            query=query,
            statute=statute,
            limit=limit,
            offset=offset,
            syntax=syntax,
            sort=sort,
            full=full,
        )
    return await search_fn(
        query=query,
        limit=limit,
        offset=offset,
        syntax=syntax,
        sort=sort,
        full=full,
    )


@legal_reference_facade_mcp.tool(annotations=READ_ONLY)
async def get_legal_reference(
    corpus: Annotated[
        Corpus,
        "Which legal-reference corpus the identifier belongs to (same enum as "
        "search_legal_reference). US: 'uspto_mpep', 'uspto_tmep'. EPO: "
        "'epo_guidelines', 'epo_pct_guidelines', 'epo_up_guidelines', "
        "'epo_case_law', 'epc'. National: 'dpma', 'ukipo_mopp', "
        "'india_statutes', 'india_mppp', 'tw_trade_secrets'. For 'upc' or "
        "'wipo_lex' use get_upc_section / get_wipo_lex_legislation — their "
        "identifiers (instrument key / legislation id) differ.",
    ],
    identifier: Annotated[
        str,
        "Section number or statute citation, from a search_legal_reference "
        "hit. Examples: '2106' (MPEP), 'Article 54' (EPC), '§ 4 PatG' "
        "(dpma), 'Section 3 Patents Act' (india_statutes).",
    ],
    version: Annotated[
        str, "MPEP installed release selector; other corpora support current only."
    ] = "current",
) -> ListEnvelope[dict]:
    """Fetch the full text of one legal-reference section by identifier.

    Always returns a ``ListEnvelope`` (stable shape). Route by ``corpus``;
    the identifier is a section number for examination manuals/guidelines or
    a statute citation for statute corpora — discover it with
    ``search_legal_reference``. For corpus='upc' or 'wipo_lex' use
    ``get_upc_section`` / ``get_wipo_lex_legislation`` instead.

    Related tools: search_legal_reference, get_upc_section, get_wipo_lex_legislation.
    """
    get_fn = _resolve(_ROUTES[corpus][1])
    if corpus == "uspto_mpep":
        return await get_fn(identifier, version=version)
    if version != "current":
        raise ValueError("Explicit version selection is supported only for uspto_mpep")
    # Underlying get fns name the single identifier ``section`` (manuals) or
    # ``citation`` (statutes); pass positionally to absorb the difference.
    return await get_fn(identifier)


# UPC and WIPO Lex pairs diverge from the uniform corpus interface (see module
# docstring): UPC keys off instrument+language with no per-section get; WIPO Lex
# keys off country/subject/type filters with a legislation_id get. Re-expose
# them verbatim on the facade — full schemas preserved, no lossy folding.
legal_reference_facade_mcp.tool(annotations=READ_ONLY)(search_upc_statutes)
legal_reference_facade_mcp.tool(annotations=READ_ONLY)(get_upc_section)
legal_reference_facade_mcp.tool(annotations=READ_ONLY)(search_wipo_lex_legislation)
legal_reference_facade_mcp.tool(annotations=READ_ONLY)(get_wipo_lex_legislation)

"""Corpus-backed EPO Guidelines for Examination client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-guidelines-corpus`` and located via
``GUIDELINES_CORPUS_PATH`` or ``~/.cache/patent_client_agents/guidelines.db``.

The corpus is scraped from ``www.epo.org/en/legal/guidelines-epc/<year>/...``.
EPO publishes the Guidelines section-by-section as HTML pages in an
8-part hierarchy (Part A through Part H, plus a "General Part"). Each
section has a stable slug like ``g_ii_3_1`` which encodes Part-Chapter-
Section-Subsection as ``<letter>_<roman>_<num>_<num>``.

Citation forms accepted by ``get_section``:

- URL slug — ``g_ii_3_1`` or ``g_ii_3_1.html``
- Canonical citation — ``G-II, 3.1`` or ``G-II 3.1`` or ``G.II.3.1``
- Path only — ``G-II`` (whole chapter) or ``A`` (whole part)

Public surface mirrors :class:`patent_client_agents.mpep.MpepClient`:
``search``, ``get_section``, ``resolve_section_href``, ``list_versions``.
"""

from __future__ import annotations

import os

from patent_client_agents.shared.corpus.epo_legal import (
    GUIDELINES_CITATION_PATTERN as _CITATION_PATTERN,
)
from patent_client_agents.shared.corpus.epo_legal import (
    GUIDELINES_SLUG_PATTERN as _SLUG_PATTERN,
)
from patent_client_agents.shared.corpus.epo_legal import (
    EpoGuidelinesClient,
)
from patent_client_agents.shared.corpus.epo_legal import (
    guidelines_citation_to_slug as _citation_to_slug,
)

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import (
    GuidelinesSearchHit,
    GuidelinesSearchResponse,
    GuidelinesSection,
    GuidelinesVersion,
)


class GuidelinesClient(
    EpoGuidelinesClient[GuidelinesSearchResponse, GuidelinesSection, GuidelinesVersion]
):
    """Corpus-backed EPO Guidelines for Examination client."""

    DEFAULT_BASE_URL: str = os.getenv("GUIDELINES_BASE_URL", "https://www.epo.org")
    CACHE_NAME: str = "guidelines"
    DEFAULT_VERSION: str = os.getenv("GUIDELINES_VERSION", "2024")

    CORPUS_DB = CorpusDB
    HIT_MODEL = GuidelinesSearchHit
    RESPONSE_MODEL = GuidelinesSearchResponse
    SECTION_MODEL = GuidelinesSection
    VERSION_MODEL = GuidelinesVersion
    NOT_FOUND_LABEL = "EPO Guidelines"
    BOOK = "guidelines-epc"


__all__ = [
    "GuidelinesClient",
    "_CITATION_PATTERN",
    "_SLUG_PATTERN",
    "_citation_to_slug",
    "CorpusUnavailable",
]

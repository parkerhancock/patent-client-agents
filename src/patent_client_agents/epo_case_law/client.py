"""Corpus-backed EPO Case Law of the Boards of Appeal client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-caselaw-corpus`` and located via
``CASELAW_CORPUS_PATH`` or ``~/.cache/patent_client_agents/caselaw.db``.

The corpus is scraped from
``www.epo.org/en/legal/case-law/<year>/...``. EPO publishes the
canonical "white book" compilation of Boards of Appeal case law
every 2-3 years (2019, 2022, ...). Each section has a slug like
``clr_i_a_1`` encoding Part-Subpart-Subsubpart-Section.

Citation forms accepted by ``get_section``:

- Canonical citation: ``I.A.1`` / ``I-A-1`` / ``I A 1``
- URL slug: ``clr_i_a_1`` / ``clr_i_a_1.html``
- Full URL: ``https://www.epo.org/en/legal/case-law/2022/clr_i_a_1.html``
"""

from __future__ import annotations

import os
import re

from patent_client_agents.shared.corpus.epo_legal import EpoLegalClient

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import CaseLawSearchHit, CaseLawSearchResponse, CaseLawSection, CaseLawVersion

_CITATION_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<part>[IVX]+)                    # Roman-numeral Part
    (?:
        [-_\s.,]+
        (?P<subpart>[A-Z])              # Letter sub-part
        (?:
            [-_\s.,]+
            (?P<chain>[\dA-Z]+(?:[-_\s.,]+[\dA-Z]+)*)
        )?
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_SLUG_PATTERN = re.compile(r"^clr_[a-z0-9_]+$", re.IGNORECASE)


def _citation_to_slug(text: str) -> str | None:
    m = _CITATION_PATTERN.match(text)
    if not m:
        return None
    part = m.group("part").lower()
    subpart = m.group("subpart")
    chain = m.group("chain")
    slug = f"clr_{part}"
    if subpart:
        slug += f"_{subpart.lower()}"
    if chain:
        normalized = re.sub(r"[-\s.,]+", "_", chain).lower()
        slug += f"_{normalized}"
    return slug


class CaseLawClient(EpoLegalClient[CaseLawSearchResponse, CaseLawSection, CaseLawVersion]):
    """Corpus-backed EPO Case Law of the Boards of Appeal client."""

    DEFAULT_BASE_URL: str = os.getenv("CASELAW_BASE_URL", "https://www.epo.org")
    CACHE_NAME: str = "caselaw"
    DEFAULT_VERSION: str = os.getenv("CASELAW_VERSION", "2022")

    CORPUS_DB = CorpusDB
    HIT_MODEL = CaseLawSearchHit
    RESPONSE_MODEL = CaseLawSearchResponse
    SECTION_MODEL = CaseLawSection
    VERSION_MODEL = CaseLawVersion
    NOT_FOUND_LABEL = "Case Law"
    BOOK = "case-law"
    EDITION_META_KEY = "caselaw_year"
    CHAPTER_LABEL = "{}"
    VERSION_LABEL = "Case Law {edition} edition (snapshot {snapshot})"

    def _citation_to_slug(self, section: str) -> str | None:
        return _citation_to_slug(section)


__all__ = [
    "CaseLawClient",
    "_CITATION_PATTERN",
    "_SLUG_PATTERN",
    "_citation_to_slug",
    "CorpusUnavailable",
]

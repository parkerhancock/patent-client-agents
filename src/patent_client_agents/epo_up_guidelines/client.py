"""Corpus-backed EPO Unitary Patent (UP) Guidelines client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-up-guidelines-corpus`` and located via
``UP_GUIDELINES_CORPUS_PATH`` or ``~/.cache/patent_client_agents/up_guidelines.db``.

The corpus is scraped from ``www.epo.org/en/legal/guidelines-up/<year>/...``.
Unlike the EPC Guidelines (Parts A-H), UP Guidelines use a flat
``section_N_M_P`` slug matching the ``N.M.P`` numbering used in the
text. The 2026 edition has ~140 leaf sections.

Citation forms accepted by ``get_section``:

- Canonical citation — ``1.2.1`` / ``1-2-1`` / ``Section 1.2.1`` / ``§ 1.2.1``
- URL slug — ``section_1_2_1``
- Full URL — ``https://www.epo.org/en/legal/guidelines-up/2026/section_1_2_1``

Public surface mirrors :class:`patent_client_agents.mpep.MpepClient`:
``search``, ``get_section``, ``resolve_section_href``, ``list_versions``.
"""

from __future__ import annotations

import os
import re

from patent_client_agents.shared.corpus.epo_legal import EpoLegalClient

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import (
    UpGuidelinesSearchHit,
    UpGuidelinesSearchResponse,
    UpGuidelinesSection,
    UpGuidelinesVersion,
)

# UP Guidelines use a flat ``N.M.P`` numbering matching slug
# ``section_N_M_P``. Citation forms we recognize:
#   1.2.1
#   1-2-1
#   1 2 1
#   Section 1.2.1
#   § 1.2.1
_CITATION_PATTERN = re.compile(
    r"""
    ^\s*
    (?:section\s+|§\s*)?            # optional "Section " or "§" prefix
    (?P<chain>\d+(?:[._\s-]\d+)*)   # dotted/spaced/hyphenated number chain
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Bare slugs like ``section_1_2_1``:
_SLUG_PATTERN = re.compile(r"^section(?:_\d+)+$", re.IGNORECASE)


def _citation_to_slug(text: str) -> str | None:
    """Map ``1.2.1`` (or variants) → ``section_1_2_1``."""
    m = _CITATION_PATTERN.match(text)
    if not m:
        return None
    chain = re.sub(r"[._\s-]+", "_", m.group("chain"))
    return f"section_{chain}"


class UpGuidelinesClient(
    EpoLegalClient[UpGuidelinesSearchResponse, UpGuidelinesSection, UpGuidelinesVersion]
):
    """Corpus-backed EPO Unitary Patent (UP) Guidelines client."""

    DEFAULT_BASE_URL: str = os.getenv("UP_GUIDELINES_BASE_URL", "https://www.epo.org")
    CACHE_NAME: str = "up_guidelines"
    DEFAULT_VERSION: str = os.getenv("UP_GUIDELINES_VERSION", "2026")

    CORPUS_DB = CorpusDB
    HIT_MODEL = UpGuidelinesSearchHit
    RESPONSE_MODEL = UpGuidelinesSearchResponse
    SECTION_MODEL = UpGuidelinesSection
    VERSION_MODEL = UpGuidelinesVersion
    NOT_FOUND_LABEL = "UP Guidelines"
    BOOK = "guidelines-up"
    # UP pages have no ``.html`` suffix.
    RESULT_SUFFIX = ""
    EDITION_META_KEY = "up_guidelines_year"

    def _citation_to_slug(self, section: str) -> str | None:
        return _citation_to_slug(section)

    def _section_number_for_slug(self, slug: str) -> str | None:
        # Maybe the corpus indexed the slug as a section_number too.
        return slug


__all__ = [
    "UpGuidelinesClient",
    "_CITATION_PATTERN",
    "_SLUG_PATTERN",
    "_citation_to_slug",
    "CorpusUnavailable",
]

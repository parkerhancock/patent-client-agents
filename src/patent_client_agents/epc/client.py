"""Corpus-backed European Patent Convention (EPC) client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-epc-corpus`` and located via
``EPC_CORPUS_PATH`` or ``~/.cache/patent_client_agents/epc.db``.

The corpus covers both Articles of the Convention and Rules of the
Implementing Regulations. Slugs follow the EPO's URL convention:
``a1`` (Article 1), ``a10a`` (Article 10a), ``r1`` (Rule 1), etc.

Citation forms accepted by ``get_section``:

- ``Article 14``, ``Art. 14``, ``Art 14``, ``a14``
- ``Rule 71``, ``R. 71``, ``R 71``, ``r71``
- URL slug ``a14`` / ``r71`` / ``a14.html``
- Full URL ``https://www.epo.org/en/legal/epc/2020/a14.html``

Public surface mirrors :class:`patent_client_agents.mpep.MpepClient`:
``search``, ``get_section``, ``resolve_section_href``, ``list_versions``.
"""

from __future__ import annotations

import os
import re

from patent_client_agents.shared.corpus.epo_legal import EpoLegalClient

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import EpcSearchHit, EpcSearchResponse, EpcSection, EpcVersion

# Citation forms to slug:
#   "Article 14" / "Art. 14" / "Art 14" → "a14"
#   "Rule 71" / "R. 71" / "R 71" → "r71"
_CITATION_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<kind>article|art\.?|a|rule|r\.?)         # Article / Rule / abbreviation
    \s*
    (?P<num>\d+[a-z]?)                            # Number, optionally with suffix letter
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_SLUG_PATTERN = re.compile(r"^[ar]\d+[a-z]?$", re.IGNORECASE)


def _citation_to_slug(text: str) -> str | None:
    m = _CITATION_PATTERN.match(text)
    if not m:
        return None
    kind = m.group("kind").lower().rstrip(".")
    prefix = "a" if kind in {"article", "art", "a"} else "r"
    return f"{prefix}{m.group('num').lower()}"


def _section_number_from_slug(slug: str) -> str | None:
    m = re.match(r"^([ar])(\d+[a-z]?)$", slug, re.IGNORECASE)
    if not m:
        return None
    prefix, num = m.groups()
    label = "Article" if prefix.lower() == "a" else "Rule"
    return f"{label} {num}"


class EpcClient(EpoLegalClient[EpcSearchResponse, EpcSection, EpcVersion]):
    """Corpus-backed EPC + Implementing Regulations client."""

    DEFAULT_BASE_URL: str = os.getenv("EPC_BASE_URL", "https://www.epo.org")
    CACHE_NAME: str = "epc"
    DEFAULT_VERSION: str = os.getenv("EPC_VERSION", "2020")

    CORPUS_DB = CorpusDB
    HIT_MODEL = EpcSearchHit
    RESPONSE_MODEL = EpcSearchResponse
    SECTION_MODEL = EpcSection
    VERSION_MODEL = EpcVersion
    NOT_FOUND_LABEL = "EPC"
    BOOK = "epc"
    EDITION_META_KEY = "epc_year"
    CHAPTER_LABEL = "{}"
    VERSION_LABEL = "EPC {edition} edition (snapshot {snapshot})"

    def _citation_to_slug(self, section: str) -> str | None:
        return _citation_to_slug(section)

    def _section_number_for_slug(self, slug: str) -> str | None:
        # Callers sometimes pass "Article 14", which is how the corpus
        # stores section_number.
        return _section_number_from_slug(slug)


__all__ = [
    "EpcClient",
    "_CITATION_PATTERN",
    "_SLUG_PATTERN",
    "_citation_to_slug",
    "CorpusUnavailable",
]

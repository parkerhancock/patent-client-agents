"""Corpus-backed UKIPO Manual of Patent Practice (MoPP) client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-mopp-corpus`` and located via
``MOPP_CORPUS_PATH`` or ``~/.cache/patent_client_agents/mopp.db`` (see
:mod:`patent_client_agents.ukipo_mopp.corpus.db`).

The corpus is scraped from
``www.gov.uk/guidance/manual-of-patent-practice-mopp`` — UKIPO publishes
the Manual section-by-section as gov.uk guidance pages, one HTML page
per PA 1977 section (~190 pages including appendices). Quarterly refresh.

Public surface mirrors :class:`patent_client_agents.mpep.MpepClient`:
``search``, ``get_section``, ``resolve_section_href``, ``list_versions``.
"""

from __future__ import annotations

import os
import re

from patent_client_agents.shared.corpus.outline import OutlineCorpusClient

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import MoppSearchHit, MoppSearchResponse, MoppSection, MoppVersion

# Pattern to detect if input looks like a section number vs an href.
# Section numbers: 2106, 2106.04, 2106.04(a), 706.03(a)(1)
# Hrefs: d0e197244.html, ch2100_d29a1b_13a9e_2dc.html
SECTION_NUMBER_PATTERN = re.compile(
    r"^\d+[a-z]?(\.\d+)?(\.\d+)?(\([a-z]\))?(\(\d+\))?$", re.IGNORECASE
)


def _normalize_href(value: str) -> str:
    """Accept hrefs in the forms callers commonly produce.

    MoPP hrefs in the corpus are gov.uk slugs (no .html suffix).
    Accept three input forms and normalize to the bare slug:

    - bare slug: ``section-1-patentability`` (passthrough)
    - relative path: ``/guidance/manual-of-patent-practice-mopp/section-1-patentability``
    - absolute URL: ``https://www.gov.uk/guidance/.../section-1-patentability``
    """
    h = value.strip()
    if h.startswith("http"):
        h = h.split("://", 1)[1].split("/", 1)[1]
    h = h.lstrip("/")
    prefix = "guidance/manual-of-patent-practice-mopp/"
    if h.startswith(prefix):
        h = h[len(prefix) :]
    h = h.removesuffix(".html")
    return h


class MoppClient(OutlineCorpusClient[MoppSearchResponse, MoppSection, MoppVersion]):
    """Corpus-backed eMOPP client.

    The corpus is opened lazily on first use so consumers can still
    construct clients in environments where the database hasn't been
    materialized yet (it'll raise ``CorpusUnavailable`` on the first
    actual call instead).
    """

    DEFAULT_BASE_URL: str = os.getenv("MOPP_BASE_URL", "https://www.gov.uk")
    CACHE_NAME: str = "mopp"

    CORPUS_DB = CorpusDB
    HIT_MODEL = MoppSearchHit
    RESPONSE_MODEL = MoppSearchResponse
    SECTION_MODEL = MoppSection
    VERSION_MODEL = MoppVersion
    NOT_FOUND_LABEL = "MOPP"
    SECTION_NUMBER_PATTERN = SECTION_NUMBER_PATTERN

    def _normalize_href(self, value: str) -> str:
        return _normalize_href(value)

    def _result_url(self, href: str, edition: str | None) -> str:
        return (
            f"{self.base_url}/guidance/manual-of-patent-practice-mopp/{href.removesuffix('.html')}"
        )


__all__ = ["MoppClient", "SECTION_NUMBER_PATTERN", "CorpusUnavailable"]

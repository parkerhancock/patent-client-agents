"""Corpus-backed MPEP client.

Replaces the previous HTTP client against ``mpep.uspto.gov`` — USPTO's
``/RDMS/MPEP/search`` endpoint has been intermittently broken since
2026-05-13, and even when healthy, search round-trips are slow. The
runtime now reads exclusively from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-mpep-corpus`` and located via
``MPEP_CORPUS_PATH`` or ``~/.cache/patent_client_agents/mpep.db`` (see
:mod:`patent_client_agents.mpep.corpus.db`).

The public surface here is preserved exactly so callers don't change:
``search``, ``get_section``, ``resolve_section_href``, ``list_versions``.
"""

from __future__ import annotations

import hashlib
import os
import re
from urllib.parse import urlencode

from mcp_data_core.corpus_db import OutlineCorpusSection
from patent_client_agents.shared.corpus.outline import OutlineCorpusClient

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import MpepSearchHit, MpepSearchResponse, MpepSection, MpepVersion

# Pattern to detect if input looks like a section number vs an href.
# Section numbers: 2106, 2106.04, 2106.04(a), 706.03(a)(1)
# Hrefs: d0e197244.html, ch2100_d29a1b_13a9e_2dc.html
SECTION_NUMBER_PATTERN = re.compile(r"^\d+(\.\d+)?(\([a-z]\))?(\(\d+\))?$", re.IGNORECASE)

_CORPUS_METADATA_KEYS = (
    "source_version",
    "edition",
    "revision",
    "publication_date",
    "substantive_cutoff_date",
    "build_id",
    "synced_at",
    "snapshot_date",
    "interim_updates_coverage",
)


def _normalize_href(value: str) -> str:
    """Accept hrefs in any of the forms callers commonly produce."""
    h = value.strip().lstrip("/")
    h = h.removeprefix("current/")
    if not h.endswith(".html"):
        h = f"{h}.html"
    return h


class MpepClient(OutlineCorpusClient[MpepSearchResponse, MpepSection, MpepVersion]):
    """Corpus-backed eMPEP client.

    The corpus is opened lazily on first use so consumers can still
    construct clients in environments where the database hasn't been
    materialized yet (it'll raise ``CorpusUnavailable`` on the first
    actual call instead).

    Unlike the other outline clients, ``version`` is checked against the
    installed snapshot, and sections carry release metadata.
    """

    DEFAULT_BASE_URL: str = os.getenv("MPEP_BASE_URL", "https://mpep.uspto.gov")
    CACHE_NAME: str = "mpep"

    CORPUS_DB = CorpusDB
    HIT_MODEL = MpepSearchHit
    RESPONSE_MODEL = MpepSearchResponse
    SECTION_MODEL = MpepSection
    VERSION_MODEL = MpepVersion
    NOT_FOUND_LABEL = "MPEP"
    SECTION_NUMBER_PATTERN = SECTION_NUMBER_PATTERN

    def _normalize_href(self, value: str) -> str:
        return _normalize_href(value)

    def _result_url(self, href: str, edition: str | None) -> str:
        return f"{self.base_url}/RDMS/MPEP/result?href={href}"

    def _check_version(self, version: str) -> dict[str, str]:
        meta = self._open().meta()
        installed = meta.get("source_version", "unknown")
        if version != "current" and (installed in {"current", "unknown"} or version != installed):
            raise ValueError(
                f"MPEP version {version!r} is unavailable; only the installed snapshot "
                f"({installed}) is retained. 'current' selects that snapshot, not a live release."
            )
        return meta

    def _to_section(
        self, row: OutlineCorpusSection, version: str, meta: dict[str, str] | None
    ) -> MpepSection:
        meta = meta or {}
        source_version = meta.get("source_version")
        return MpepSection(
            href=row.href,
            html=row.html,
            text=row.text,
            version=(source_version if source_version != "current" else None) or "unknown",
            title=row.title,
            source_url=f"{self.base_url}/RDMS/MPEP/result?"
            + urlencode(
                {
                    "href": row.href,
                    "version": source_version
                    if source_version not in {None, "unknown"}
                    else "current",
                }
            ),
            content_sha256=hashlib.sha256(row.html.encode()).hexdigest(),
            section_revision=(
                match.group(0)
                if (match := re.search(r"\[R-[^\]]+\]", row.title or row.text[:500]))
                else None
            ),
            corpus_metadata={key: meta.get(key) for key in _CORPUS_METADATA_KEYS},
        )

    async def list_versions(self) -> list[MpepVersion]:
        """Single-entry list reflecting the loaded corpus snapshot.

        The corpus only ships one MPEP version (the snapshot recorded
        when ``patent-client-agents-build-mpep-corpus`` last ran);
        return its recorded identifier when known. ``current`` remains an
        alias for the installed snapshot, never a claim of source freshness.
        """
        meta = self._open().meta()
        snapshot = meta.get("snapshot_date", "unknown")
        return [
            MpepVersion(
                label=f"{meta.get('source_version', 'unknown')} (installed snapshot {snapshot})",
                value=meta.get("source_version", "current")
                if meta.get("source_version") not in {None, "unknown"}
                else "current",
                current=True,
            )
        ]


__all__ = ["MpepClient", "SECTION_NUMBER_PATTERN", "CorpusUnavailable"]

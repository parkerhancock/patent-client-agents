"""Client base for the outline corpora.

Every outline package (MPEP, TMEP, EPC, the EPO books, MoPP) exposes the same
async client surface over an :class:`~mcp_data_core.corpus_db.OutlineCorpusDB`:
``search``, ``get_section``, ``resolve_section_href``, and ``list_versions``.
:class:`OutlineCorpusClient` implements it once. A package subclass declares
its corpus, result models, and labels as class attributes, and overrides the
few hooks where its source really differs:

- ``_normalize_href`` and ``_result_url`` (always): how a caller's reference
  maps to a stored href, and the upstream URL for a hit.
- ``_lookups`` (optional): the ``(column, value)`` lookups ``get_section``
  tries in order. The default looks up ``section_number`` when
  ``SECTION_NUMBER_PATTERN`` matches and the normalized href otherwise.
- ``_check_version``, ``_to_section``, ``list_versions`` (optional): MPEP
  validates ``version`` against the installed snapshot and returns extra
  section metadata; the others ignore ``version`` and echo it back.

The corpus opens lazily on first use, so a client can be constructed where the
database is missing and raises ``CorpusUnavailable`` only on the first call.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from typing import Any, Generic, Self, TypeVar

from mcp_data_core.corpus_db import OutlineCorpusDB, OutlineCorpusSection
from patent_client_agents.shared.corpus.fts_query import translate_fts_query
from patent_client_agents.shared.errors import SectionNotFoundError

from .models import OutlineSearchHit, OutlineSearchResponse, OutlineSection, OutlineVersion

ResponseT = TypeVar("ResponseT", bound=OutlineSearchResponse)
SectionT = TypeVar("SectionT", bound=OutlineSection)
VersionT = TypeVar("VersionT", bound=OutlineVersion)


class OutlineCorpusClient(Generic[ResponseT, SectionT, VersionT]):
    """Corpus-backed client for one outline corpus. Subclass and configure."""

    # -- Required configuration ------------------------------------------------
    CORPUS_DB: type[OutlineCorpusDB]
    HIT_MODEL: type[OutlineSearchHit]
    RESPONSE_MODEL: type[ResponseT]
    SECTION_MODEL: type[SectionT]
    VERSION_MODEL: type[VersionT]
    DEFAULT_BASE_URL: str
    CACHE_NAME: str
    # Names the source in ``SectionNotFoundError`` messages.
    NOT_FOUND_LABEL: str

    # -- Optional configuration ------------------------------------------------
    # Inputs that look like a section number ("2106.04(a)") are looked up by
    # ``section_number``; everything else is treated as an href.
    SECTION_NUMBER_PATTERN: re.Pattern[str] | None = None
    # Formats a hit's chapter as the first ``path`` entry.
    CHAPTER_LABEL: str = "Chapter {}"
    # ``list_versions`` label; ``{edition}`` reads ``EDITION_META_KEY``.
    VERSION_LABEL: str = "current (snapshot {snapshot})"
    EDITION_META_KEY: str | None = None

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._db: OutlineCorpusDB | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    @property
    def base_url(self) -> str:
        return self._base_url

    def _open(self) -> OutlineCorpusDB:
        if self._db is None:
            self._db = self.CORPUS_DB.open(self._corpus_path)
        return self._db

    # -- Hooks -----------------------------------------------------------------

    def _check_version(self, version: str) -> dict[str, str] | None:
        """Validate ``version``; return corpus meta when the check read it.

        Single-snapshot corpora accept any ``version`` and echo it back.
        """
        del version
        return None

    def _normalize_href(self, value: str) -> str:
        raise NotImplementedError

    def _result_url(self, href: str, edition: str | None) -> str:
        raise NotImplementedError

    def _edition(self, db: OutlineCorpusDB) -> str | None:
        """The edition that hit URLs embed; ``None`` when they embed none."""
        del db
        return None

    def _lookups(self, section: str) -> Iterator[tuple[str, str]]:
        pattern = self.SECTION_NUMBER_PATTERN
        if pattern is not None and pattern.match(section):
            yield "section_number", section
        else:
            yield "href", self._normalize_href(section)

    def _not_found_message(self, section: str) -> str:
        pattern = self.SECTION_NUMBER_PATTERN
        kind = "href" if pattern is not None and not pattern.match(section) else "section"
        return f"Could not find {self.NOT_FOUND_LABEL} {kind} '{section}'"

    def _to_section(
        self, row: OutlineCorpusSection, version: str, meta: dict[str, str] | None
    ) -> SectionT:
        del meta
        return self.SECTION_MODEL(
            href=row.href, html=row.html, text=row.text, version=version, title=row.title
        )

    def _hit_to_model(self, hit: Any, edition: str | None) -> OutlineSearchHit:
        title = (
            f"{hit.section_number} - {hit.title}"
            if hit.section_number and hit.title
            else hit.title or hit.section_number or ""
        )
        path: list[str] = []
        if hit.chapter:
            path.append(self.CHAPTER_LABEL.format(hit.chapter))
        if hit.section_number:
            path.append(hit.section_number)
        return self.HIT_MODEL(
            title=title, href=hit.href, path=path, result_url=self._result_url(hit.href, edition)
        )

    # -- Public surface --------------------------------------------------------

    async def resolve_section_href(
        self,
        section_number: str,
        *,
        version: str = "current",
    ) -> str | None:
        self._check_version(version)
        row = self._open().get_section(section_number=section_number)
        return row.href if row else None

    async def search(
        self,
        query: str,
        *,
        version: str = "current",
        include_content: bool = True,
        include_index: bool = False,
        include_notes: bool = False,
        include_form_paragraphs: bool = False,
        syntax: str = "adj",
        snippet: str = "compact",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
        offset: int | None = None,
    ) -> ResponseT:
        # The corpus indexes all body text together, so the content / index /
        # notes / form-paragraph flags are accepted for API parity only.
        self._check_version(version)
        del include_content, include_index, include_notes, include_form_paragraphs, snippet
        db = self._open()
        fts_query = translate_fts_query(query, syntax)
        if not fts_query:
            return self.RESPONSE_MODEL(hits=[], page=page, per_page=per_page, has_more=False)
        # A row ``offset`` takes precedence over ``page`` when given.
        if offset is None:
            offset = max(0, (page - 1) * per_page)
        # Fetch one extra row to detect whether more pages exist.
        rows = db.search(fts_query, limit=per_page + 1, offset=offset, sort=sort)
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        edition = self._edition(db)
        hits = [self._hit_to_model(r, edition) for r in rows]
        return self.RESPONSE_MODEL(hits=hits, page=page, per_page=per_page, has_more=has_more)

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
        highlight_query: str | None = None,
    ) -> SectionT:
        # The corpus stores the canonical HTML; there is no highlighted view.
        del highlight_query
        meta = self._check_version(version)
        db = self._open()
        for column, value in self._lookups(section):
            if column == "href":
                row = db.get_section(href=value)
            else:
                row = db.get_section(section_number=value)
            if row is not None:
                return self._to_section(row, version, meta)
        raise SectionNotFoundError(self._not_found_message(section))

    async def list_versions(self) -> list[VersionT]:
        """A single entry for the installed snapshot, with value ``current``."""
        meta = self._open().meta()
        snapshot = meta.get("snapshot_date", "unknown")
        edition = meta.get(self.EDITION_META_KEY, "unknown") if self.EDITION_META_KEY else None
        return [
            self.VERSION_MODEL(
                label=self.VERSION_LABEL.format(snapshot=snapshot, edition=edition),
                value="current",
                current=True,
            )
        ]


__all__ = ["OutlineCorpusClient"]

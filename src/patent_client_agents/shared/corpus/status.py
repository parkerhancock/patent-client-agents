"""``get_corpus_status()`` for the bundled SQLite/FTS5 corpora (§4).

Every ``mcp_local`` substantive-law package exposes a module-level
``get_corpus_status()`` that reads freshness metadata from the corpus
``meta`` table without an upstream call. ``scripts/build_coverage.py`` uses
it to detect drift, and the MCP tools stamp ``Provenance.corpus_synced_at`` /
``Provenance.corpus_version`` from it. Each package builds its callable with
:func:`make_corpus_status`, naming the meta keys its build writes::

    get_corpus_status = make_corpus_status(
        CorpusDB, CorpusUnavailable, label="EPC", version_keys=("epc_year",)
    )

A missing or unreadable corpus reports ``corpus_version="unknown"`` and
``corpus_synced_at=None``; the callable never raises.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime
from typing import Protocol, TypedDict

_logger = logging.getLogger(__name__)

UNKNOWN_VERSION = "unknown"

# Labels a build may record that name a moving target rather than a version.
MOVING_LABELS: tuple[str, ...] = ("current",)


class CorpusStatus(TypedDict):
    """Return shape of ``get_corpus_status()``.

    ``corpus_synced_at`` is the UTC datetime the corpus was last refreshed
    from upstream, or ``None`` when that isn't recorded. ``corpus_version`` is
    the vendor's version label, or ``"unknown"``. Values are never fabricated.
    """

    corpus_synced_at: datetime | None
    corpus_version: str


class _MetaReader(Protocol):
    def meta(self) -> Mapping[str, str]: ...


class _CorpusOpener(Protocol):
    @classmethod
    def open(cls) -> AbstractContextManager[_MetaReader]: ...


def parse_snapshot_date(value: str | None) -> datetime | None:
    """Parse a ``YYYY-MM-DD`` snapshot date or an ISO build timestamp into UTC.

    A bare date becomes UTC midnight; a naive timestamp is taken as UTC.
    Returns ``None`` for an empty or malformed value.
    """
    if not value:
        return None
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value)
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        parsed_date = date.fromisoformat(value)
    except ValueError:
        _logger.debug("corpus snapshot date %r is not ISO", value)
        return None
    return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=UTC)


def corpus_status_from_meta(
    meta: Mapping[str, str],
    *,
    version_keys: Sequence[str] = ("source_version",),
    synced_at_keys: Sequence[str] = ("snapshot_date",),
    snapshot_label: str | None = None,
    moving_labels: Sequence[str] = MOVING_LABELS,
) -> CorpusStatus:
    """Derive a :class:`CorpusStatus` from a corpus ``meta`` mapping.

    The version is the first non-empty value among ``version_keys`` that
    isn't a moving label such as ``"current"``. Failing that, and when
    ``snapshot_label`` is given (a format string such as ``"snapshot-{}"``),
    the snapshot date fills it in. Otherwise the version is ``"unknown"``.
    The sync time comes from the first non-empty value among
    ``synced_at_keys``.
    """
    snapshot_raw = next((meta[key] for key in synced_at_keys if meta.get(key)), None)
    version = next(
        (meta[key] for key in version_keys if meta.get(key) and meta[key] not in moving_labels),
        None,
    )
    if version is None:
        if snapshot_label is not None and snapshot_raw:
            version = snapshot_label.format(snapshot_raw)
        else:
            version = UNKNOWN_VERSION
    return CorpusStatus(
        corpus_synced_at=parse_snapshot_date(snapshot_raw),
        corpus_version=version,
    )


def make_corpus_status(
    db_cls: type[_CorpusOpener],
    unavailable: type[Exception],
    *,
    label: str,
    version_keys: Sequence[str] = ("source_version",),
    synced_at_keys: Sequence[str] = ("snapshot_date",),
    snapshot_label: str | None = None,
    moving_labels: Sequence[str] = MOVING_LABELS,
) -> Callable[[], CorpusStatus]:
    """Build a package's module-level ``get_corpus_status()``.

    ``db_cls.open()`` locates the corpus (its env var, then the local cache)
    each time the callable runs. ``unavailable`` is the package's
    "no corpus here" exception, logged at debug level; any other error is
    logged as a warning. Both report an unknown status. ``label`` names the
    corpus in log messages. The remaining arguments are as for
    :func:`corpus_status_from_meta`.
    """

    def get_corpus_status() -> CorpusStatus:
        try:
            with db_cls.open() as db:
                meta = db.meta()
        except unavailable as exc:
            _logger.debug("%s corpus unavailable for get_corpus_status: %s", label, exc)
            return CorpusStatus(corpus_synced_at=None, corpus_version=UNKNOWN_VERSION)
        except Exception as exc:  # never crash the caller
            _logger.warning(
                "%s get_corpus_status: unexpected error reading corpus meta: %r", label, exc
            )
            return CorpusStatus(corpus_synced_at=None, corpus_version=UNKNOWN_VERSION)
        return corpus_status_from_meta(
            meta,
            version_keys=version_keys,
            synced_at_keys=synced_at_keys,
            snapshot_label=snapshot_label,
            moving_labels=moving_labels,
        )

    get_corpus_status.__doc__ = (
        f"Return {label} corpus freshness metadata (CONNECTOR_STANDARDS.md §4).\n\n"
        "Reads the bundled corpus ``meta`` table; never calls upstream and never raises.\n"
        "A missing or unreadable corpus reports ``corpus_version='unknown'`` and\n"
        "``corpus_synced_at=None``."
    )
    return get_corpus_status

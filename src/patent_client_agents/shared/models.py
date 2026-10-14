"""Reusable Pydantic v2 pieces for connector models.

Upstream registers send dates in a handful of string shapes, empty XML
elements as ``""``, and camelCase JSON keys. The parsers here are the
lenient coercers several connectors share; each returns ``None`` for input
it can't read instead of raising, so one bad field doesn't fail a record.

The date parsers are not interchangeable. They differ in which strings they
accept and in how they treat a ``datetime`` object, so a connector picks the
one whose semantics it already had:

- :func:`parse_iso_date` / :data:`IsoDate`: ``date.fromisoformat`` plus
  ``YYYYMMDD``; ``"00000000"`` means unknown; full timestamps are rejected.
- :func:`parse_iso_timestamp_date` / :data:`IsoTimestampDate`: also accepts
  full ISO timestamps (including a trailing ``Z``) and keeps the date part.
- :func:`lenient_date`: ``strptime`` against an explicit, ordered tuple of
  formats. Format order matters (``%d/%m/%Y`` vs ``%m/%d/%Y``), so each
  connector names its own.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict
from pydantic.alias_generators import to_camel

__all__ = [
    "ApiModel",
    "EmptyStrNone",
    "IsoDate",
    "IsoTimestampDate",
    "YmdDate",
    "empty_str_to_none",
    "lenient_date",
    "parse_iso_date",
    "parse_iso_timestamp_date",
    "parse_ymd_date",
]


def parse_iso_date(value: Any) -> date | None:
    """Coerce an ISO 8601 date or ``YYYYMMDD`` string to ``date``.

    ``date`` passes through and ``datetime`` is truncated to its date.
    ``None``, blank strings, the ``"00000000"`` unknown-date sentinel,
    timestamps, non-strings, and anything else unparseable return ``None``.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or cleaned == "00000000":
        return None
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass
    if len(cleaned) == 8 and cleaned.isdigit():
        try:
            return datetime.strptime(cleaned, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def parse_iso_timestamp_date(value: Any) -> date | None:
    """Coerce an ISO 8601 date or timestamp, or ``YYYYMMDD``, to ``date``.

    Timestamps keep their date part as written (no timezone conversion); a
    trailing ``Z`` is accepted. ``date`` passes through, ``datetime`` is
    truncated, and blank, non-string, or unparseable input returns ``None``.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None


def lenient_date(*formats: str, keep_datetime: bool = False) -> Callable[[Any], Any]:
    """Build a parser that tries each ``strptime`` format in order.

    The returned callable strips whitespace and returns the first successful
    parse as a ``date``; blank, non-string, or unparseable input returns
    ``None``. A ``date`` passes through unchanged. A ``datetime`` is
    truncated to its date unless ``keep_datetime`` is set, in which case it is
    returned as is and Pydantic's own ``date`` validation decides (it accepts
    midnight and rejects any other time).
    """

    def parse(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime) and not keep_datetime:
            return value.date()
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            return None
        text = value.strip()
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    return parse


parse_ymd_date = lenient_date("%Y-%m-%d", keep_datetime=True)
"""Strict ``YYYY-MM-DD`` parser; anything else returns ``None``."""


def empty_str_to_none(value: Any) -> Any:
    """Return ``None`` for empty or whitespace-only strings; pass anything else."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


IsoDate = Annotated[date | None, BeforeValidator(parse_iso_date)]
IsoTimestampDate = Annotated[date | None, BeforeValidator(parse_iso_timestamp_date)]
YmdDate = Annotated[date | None, BeforeValidator(parse_ymd_date)]
EmptyStrNone = Annotated[str | None, BeforeValidator(empty_str_to_none)]


class ApiModel(BaseModel):
    """Base for models whose wire keys are the camelCase form of the field names.

    Fields accept either the camelCase key or the Python name. A field whose
    wire key isn't plain camelCase still declares ``Field(alias=...)``, which
    overrides the generated alias. ``extra`` is left to each model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

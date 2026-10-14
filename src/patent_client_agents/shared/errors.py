"""Exceptions shared by the bundled-corpus clients."""

from __future__ import annotations

from mcp_data_core.exceptions import NotFoundError


class SectionNotFoundError(NotFoundError, ValueError):
    """A citation parsed, but the bundled corpus has no such section.

    A ``NotFoundError`` so list-accepting tools report it in ``not_found``
    (see ``shared.fanout``), and a ``ValueError`` because the corpus clients
    raised ``ValueError`` for this before and callers may still catch that.
    """

    __str__ = Exception.__str__

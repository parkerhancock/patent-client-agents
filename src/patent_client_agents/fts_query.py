"""Translate user search text into an SQLite FTS5 MATCH expression.

Shared by the bundled-corpus clients. Every token is quoted, so punctuation
in legal citations (``Art. 54``, ``1207.01(a)``, ``L. 611-10``) and words that
FTS5 treats as operators (``AND``, ``NOT``, ``NEAR``) are matched as text
instead of being parsed as query syntax.
"""

from __future__ import annotations

import re


def _quote(text: str) -> str:
    return '"' + text.replace('"', '""') + '"'


def translate_fts_query(query: str, syntax: str = "and") -> str:
    """Return an FTS5 MATCH expression for ``query``.

    - ``adj`` / ``exact``: the whole query as one phrase.
    - ``or``: any of the whitespace-separated terms.
    - ``and`` / anything else: all of the terms.
    """
    cleaned = query.strip()
    if not cleaned:
        return ""
    if syntax in ("adj", "exact"):
        return _quote(cleaned)
    tokens = [_quote(t) for t in re.split(r"\s+", cleaned) if t]
    if syntax == "or":
        return " OR ".join(tokens)
    return " ".join(tokens)

"""Async KIPO KIPRIS Plus connector (Korean Intellectual Property Office).

Built in 4 chunks: (1) scaffold from the JPO package, (2) XML row
models for ``patUtliInfoSearchService`` / ``trademarkInfoSearchService``
/ ``designInfoSearchService``, (3) ``KiprisClient`` + module-level
helpers + MCP tool surface (this commit), (4) tests. See
``research/specs/kr-kipo-connector-spec.md`` for the full contract.

Auth is BYOK per ToS §11: a single per-user ``serviceKey`` exposed via
the ``KIPO_KIPRIS_API_KEY`` environment variable.
"""

from .client import KiprisClient
from .models import DesignRow, PatentUtilityRow, TrademarkRow

__all__ = [
    "DesignRow",
    "KiprisClient",
    "PatentUtilityRow",
    "TrademarkRow",
]

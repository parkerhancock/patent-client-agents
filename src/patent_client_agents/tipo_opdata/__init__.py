"""Async client for the TIPO OpenData REST API (Taiwan).

The Taiwan Intellectual Property Office (TIPO / 智慧財產局) publishes a
15-endpoint OpenData REST surface at
``https://cloud.tipo.gov.tw/S220/opdataapi/api/`` covering patent,
utility-model, design, and trademark bibliographic + status records.

This is a scaffold (chunk 1 of 4); models, client behaviour, and MCP
tools are written in subsequent chunks per
``research/specs/tw-tipo-connector-spec.md``.

See :class:`TipoClient` for the auth + environment contract.
"""

from .client import TipoClient
from .models import Patent, PatentSearchHit, PatentSearchResult

__all__ = [
    "Patent",
    "PatentSearchHit",
    "PatentSearchResult",
    "TipoClient",
]

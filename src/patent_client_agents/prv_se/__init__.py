"""Async client for the Swedish Patent and Registration Office (PRV).

PRV (Patent- och registreringsverket) runs three undocumented but
unauthenticated REST/JSON APIs behind the [`search.prv.se`](https://search.prv.se/)
beta UI:

* ``patents-search-api.prv.se`` — national patent simple search
* ``dv-search-api.prv.se`` — trademark + design simple search
* ``api.prv.se`` — per-record patent fetch

No API key, no signed ToU. Parallel bulk feeds on ``data.prv.se`` are
licensed CC0 1.0 / CC BY 4.0 under Sweden's Open Data Act
(SFS 2022:818); the live APIs share that governance umbrella.

See :class:`PrvClient` for the connection contract and
``research/national/se-prv.md`` for the full source survey.
"""

from .client import PrvClient
from .models import (
    DesignSearchResponse,
    DesignSearchRow,
    Party,
    PatentGetRecord,
    PatentSearchResponse,
    PatentSearchRow,
    Publication,
    PublicationStatus,
    RegistryEntry,
    SpcSearchResponse,
    SpcSearchRow,
    TrademarkSearchResponse,
    TrademarkSearchRow,
)

__all__ = [
    "PrvClient",
    "PatentSearchResponse",
    "PatentSearchRow",
    "PatentGetRecord",
    "TrademarkSearchResponse",
    "TrademarkSearchRow",
    "DesignSearchResponse",
    "DesignSearchRow",
    "SpcSearchResponse",
    "SpcSearchRow",
    "Party",
    "Publication",
    "PublicationStatus",
    "RegistryEntry",
]

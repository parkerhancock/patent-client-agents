"""Async client for the Finnish Patent and Registration Office (PRH).

PRH (Patentti- ja rekisterihallitus) runs three undocumented but
unauthenticated JSON APIs behind modern React SPAs:

* ``patenttitietopalvelu.prh.fi/nis-api-gateway-pat/`` — patent / UM /
  SPC / EP-FI corpus.
* ``tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/`` — national
  trademarks + well-known trademarks register (TMR).
* ``mallioikeustietopalvelu.prh.fi/nis-api-gateway/`` — national designs.

No API key, no signed ToU. The patent-search payload is a 30-field
form-state body decoded from the React bundle — three list-valued
slots are **inclusion** filters whose defaults this client supplies
automatically.

See :class:`PrhClient` for the connection contract and
``research/national/fi-prh.md`` for the full source survey.
"""

from .client import (
    DEFAULT_PATENT_STATUSES,
    DEFAULT_PATENT_TYPES,
    DEFAULT_PUBLICATION_TYPES,
    DEFAULT_USER_AGENT,
    DESIGN_HOST,
    DESIGN_PATH,
    PATENT_HOST,
    PATENT_PATH,
    SERVER_RESULT_CAP,
    TMR_PATH,
    TRADEMARK_HOST,
    TRADEMARK_PATH,
    PrhClient,
    build_design_search_body,
    build_patent_search_body,
    build_trademark_search_body,
)
from .models import (
    AbstractTranslation,
    Classification,
    DesignEmbodiment,
    DossierPriority,
    DossierSearchResponse,
    DossierSearchRow,
    Examiner,
    GoodsAndServicesClass,
    LocarnoClass,
    Party,
    PatentGetRecord,
    PatentPublication,
    PatentSearchResponse,
    PatentSearchRow,
    PriorityClaim,
    TitleTranslation,
)

__all__ = [
    "PrhClient",
    "DossierSearchRow",
    "DossierSearchResponse",
    "PatentSearchRow",
    "PatentSearchResponse",
    "PatentGetRecord",
    "Party",
    "GoodsAndServicesClass",
    "LocarnoClass",
    "DesignEmbodiment",
    "TitleTranslation",
    "AbstractTranslation",
    "Classification",
    "PatentPublication",
    "PriorityClaim",
    "Examiner",
    "DossierPriority",
    "build_patent_search_body",
    "build_trademark_search_body",
    "build_design_search_body",
    "DEFAULT_PATENT_TYPES",
    "DEFAULT_PATENT_STATUSES",
    "DEFAULT_PUBLICATION_TYPES",
    "DEFAULT_USER_AGENT",
    "SERVER_RESULT_CAP",
    "PATENT_HOST",
    "TRADEMARK_HOST",
    "DESIGN_HOST",
    "PATENT_PATH",
    "TRADEMARK_PATH",
    "TMR_PATH",
    "DESIGN_PATH",
]

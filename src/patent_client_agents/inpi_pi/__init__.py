"""Async INPI France national TM + Design connector (BYOK).

Wraps ``api-gateway.inpi.fr`` for French national trademarks (WIPO ST.66
v1.0) and designs (WIPO ST.86 v1.0). Authentication is a session-bearer
+ XSRF flow bound to a personal ``data.inpi.fr`` account (NOT PISTE);
see :mod:`patent_client_agents.inpi_pi.session` for the lifecycle
(XSRF bootstrap → login → bearer + refresh-on-401).

**TM + design only — patents covered via EPO OPS.** For FR patent
coverage, use ``patent_client_agents.epo_ops`` (country code ``FR``);
INPADOC covers EP-routed FR designations and FR national-route filings
with adequate fidelity. The INPI national patents API exists, but its
bibliographic coverage duplicates EPO INPADOC for the same filings and
adds no signal worth the second auth surface.

Environment Variables:
    INPI_USERNAME: personal data.inpi.fr account username
    INPI_PASSWORD: personal data.inpi.fr account password
"""

from .api import (
    get_inpi_design,
    get_inpi_trademark,
    search_inpi_designs,
    search_inpi_trademarks,
)
from .client import InpiPiClient
from .models import InpiDesignRow, InpiTrademarkRow
from .session import InpiSession

__all__ = [
    "InpiPiClient",
    "InpiTrademarkRow",
    "InpiDesignRow",
    "InpiSession",
    "search_inpi_trademarks",
    "get_inpi_trademark",
    "search_inpi_designs",
    "get_inpi_design",
]

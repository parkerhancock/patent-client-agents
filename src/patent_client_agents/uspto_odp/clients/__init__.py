"""Domain-specific USPTO ODP clients."""

from .applications import ApplicationsClient
from .bulkdata import BulkDataClient
from .office_action_search import OfficeActionSearchClient
from .petitions import PetitionsClient
from .ptab_appeals import PtabAppealsClient
from .ptab_interferences import PtabInterferencesClient
from .ptab_trials import PtabTrialsClient
from .trademark_decisions import TrademarkDecisionsClient

__all__ = [
    "ApplicationsClient",
    "BulkDataClient",
    "OfficeActionSearchClient",
    "PetitionsClient",
    "PtabTrialsClient",
    "PtabAppealsClient",
    "PtabInterferencesClient",
    "TrademarkDecisionsClient",
]

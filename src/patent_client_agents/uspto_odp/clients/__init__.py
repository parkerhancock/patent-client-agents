"""Domain-specific USPTO ODP clients."""

from .applications import ApplicationsClient
from .bulkdata import BulkDataClient
from .petitions import PetitionsClient
from .ptab_appeals import PtabAppealsClient
from .ptab_interferences import PtabInterferencesClient
from .ptab_trials import PtabTrialsClient

__all__ = [
    "ApplicationsClient",
    "BulkDataClient",
    "PetitionsClient",
    "PtabTrialsClient",
    "PtabAppealsClient",
    "PtabInterferencesClient",
]

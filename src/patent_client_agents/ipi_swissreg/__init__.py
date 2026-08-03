"""Swiss IPI Swissreg datadelivery connector.

This connector is schema-tested only. Live account validation is welcome.
"""

from .api import (
    get_ipi_patent,
    get_ipi_spc,
    get_ipi_trademark,
    search_ipi_patent_publications,
    search_ipi_patents,
    search_ipi_spc_publications,
    search_ipi_spcs,
    search_ipi_trademarks,
)
from .client import IpiSwissregClient
from .models import (
    IpiPatentRecord,
    IpiPublicationRecord,
    IpiSearchMeta,
    IpiSpcRecord,
    IpiTrademarkRecord,
)

__all__ = [
    "IpiPatentRecord",
    "IpiPublicationRecord",
    "IpiSearchMeta",
    "IpiSpcRecord",
    "IpiSwissregClient",
    "IpiTrademarkRecord",
    "get_ipi_patent",
    "get_ipi_spc",
    "get_ipi_trademark",
    "search_ipi_patent_publications",
    "search_ipi_patents",
    "search_ipi_spc_publications",
    "search_ipi_spcs",
    "search_ipi_trademarks",
]

"""Spain OEPM CEO connector.

This connector is WSDL-tested only. Live account validation is welcome.
"""

from .api import get_oepm_design, get_oepm_patent, get_oepm_trademark
from .client import OepmSpainClient
from .models import OepmDesignRecord, OepmPatentRecord, OepmTrademarkRecord

__all__ = [
    "OepmDesignRecord",
    "OepmPatentRecord",
    "OepmSpainClient",
    "OepmTrademarkRecord",
    "get_oepm_design",
    "get_oepm_patent",
    "get_oepm_trademark",
]

"""New Zealand IPONZ v5 API connector."""

from .client import IponzClient
from .models import (
    IponzDesignRecord,
    IponzPatentRecord,
    IponzRegisterSummary,
    IponzTrademarkRecord,
)

__all__ = [
    "IponzClient",
    "IponzDesignRecord",
    "IponzPatentRecord",
    "IponzRegisterSummary",
    "IponzTrademarkRecord",
]

"""USPTO Trademark Assignment Center API client."""

from .client import TrademarkAssignmentClient
from .models import (
    Assignor,
    SearchCriterion,
    TrademarkAssignmentRecord,
    TrademarkAssignmentSearchResponse,
    TrademarkProperty,
)

__all__ = [
    "TrademarkAssignmentClient",
    "Assignor",
    "TrademarkProperty",
    "TrademarkAssignmentRecord",
    "SearchCriterion",
    "TrademarkAssignmentSearchResponse",
]

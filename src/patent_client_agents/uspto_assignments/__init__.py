"""USPTO Assignment Center API client.

Async access to USPTO patent assignment recordations via the Assignment
Center's reverse-engineered JSON API. A single :meth:`search` method
covers every indexed axis (assignee, assignor, correspondent, application,
patent, publication, reel/frame, PCT, international registration) with
conveyance-type populated, optional execution-date and conveyance-text
filters, and pagination.

Example:
    from datetime import date
    from patent_client_agents.uspto_assignments import AssignmentCenterClient

    async with AssignmentCenterClient() as client:
        result = await client.search(
            query="Apple Inc",
            by="assignee",
            executed_between=(date(2024, 1, 1), date(2024, 12, 31)),
            limit=100,
        )
        for record in result:
            print(record.reel_frame, record.conveyance, record.assignees)
        if result.truncated:
            print(f"USPTO capped this query at {len(result)} of {result.total}+")
"""

from .client import AssignmentCenterClient, SearchAxis
from .models import (
    AssignmentRecord,
    Assignor,
    Property,
    SearchResults,
)

__all__ = [
    "AssignmentCenterClient",
    "AssignmentRecord",
    "Assignor",
    "Property",
    "SearchAxis",
    "SearchResults",
]

"""Fluent query builder for PatentsView JSON query language."""

from __future__ import annotations

from typing import Any, Self


class PatentsViewQuery:
    """Fluent builder for PatentsView API JSON query language.

    PatentsView uses a JSON-based query syntax with operators like _and, _or,
    _gte, _lte, _text_any, etc. This builder provides a Pythonic interface.

    Example::

        query = (PatentsViewQuery()
            .cpc("H04L63")
            .assignee("Google")
            .since("2020-01-01")
            .build())

        # Produces:
        # {"_and": [
        #     {"_text_any": {"cpc_group_id": "H04L63"}},
        #     {"_text_any": {"assignee_organization": "Google"}},
        #     {"_gte": {"patent_date": "2020-01-01"}}
        # ]}
    """

    def __init__(self) -> None:
        self._conditions: list[dict[str, Any]] = []

    def equals(self, field: str, value: str) -> Self:
        """Add exact match condition."""
        self._conditions.append({field: value})
        return self

    def gte(self, field: str, value: str) -> Self:
        """Add greater-than-or-equal condition."""
        self._conditions.append({"_gte": {field: value}})
        return self

    def lte(self, field: str, value: str) -> Self:
        """Add less-than-or-equal condition."""
        self._conditions.append({"_lte": {field: value}})
        return self

    def gt(self, field: str, value: str) -> Self:
        """Add greater-than condition."""
        self._conditions.append({"_gt": {field: value}})
        return self

    def lt(self, field: str, value: str) -> Self:
        """Add less-than condition."""
        self._conditions.append({"_lt": {field: value}})
        return self

    def text_any(self, field: str, value: str) -> Self:
        """Add text search matching any word."""
        self._conditions.append({"_text_any": {field: value}})
        return self

    def text_all(self, field: str, value: str) -> Self:
        """Add text search matching all words."""
        self._conditions.append({"_text_all": {field: value}})
        return self

    def text_phrase(self, field: str, value: str) -> Self:
        """Add exact phrase text search."""
        self._conditions.append({"_text_phrase": {field: value}})
        return self

    def begins(self, field: str, value: str) -> Self:
        """Add prefix match condition."""
        self._conditions.append({"_begins": {field: value}})
        return self

    def contains(self, field: str, value: str) -> Self:
        """Add substring match condition."""
        self._conditions.append({"_contains": {field: value}})
        return self

    # Convenience methods for common fields

    def patent_number(self, number: str) -> Self:
        """Filter by exact patent number."""
        return self.equals("patent_number", number)

    def patent_id(self, patent_id: str) -> Self:
        """Filter by exact patent ID."""
        return self.equals("patent_id", patent_id)

    def cpc(self, group: str) -> Self:
        """Filter by CPC group (e.g., 'H04L63')."""
        return self.text_any("cpc_group_id", group)

    def cpc_subgroup(self, subgroup: str) -> Self:
        """Filter by CPC subgroup (e.g., 'H04L63/0428')."""
        return self.text_any("cpc_subgroup_id", subgroup)

    def assignee(self, org: str) -> Self:
        """Filter by assignee organization name."""
        return self.text_any("assignee_organization", org)

    def inventor(self, name: str) -> Self:
        """Filter by inventor name (first or last)."""
        return self.text_any("inventor_last_name", name)

    def title(self, keywords: str) -> Self:
        """Filter by patent title keywords."""
        return self.text_any("patent_title", keywords)

    def abstract(self, keywords: str) -> Self:
        """Filter by patent abstract keywords."""
        return self.text_any("patent_abstract", keywords)

    def since(self, date: str) -> Self:
        """Filter patents granted on or after date (YYYY-MM-DD)."""
        return self.gte("patent_date", date)

    def until(self, date: str) -> Self:
        """Filter patents granted on or before date (YYYY-MM-DD)."""
        return self.lte("patent_date", date)

    def patent_type(self, type_name: str) -> Self:
        """Filter by patent type (utility, design, plant, reissue)."""
        return self.equals("patent_type", type_name)

    def build(self) -> dict[str, Any]:
        """Build the final query dict.

        Returns an empty dict if no conditions added.
        Returns the single condition if only one.
        Wraps multiple conditions in _and.
        """
        if len(self._conditions) == 0:
            return {}
        if len(self._conditions) == 1:
            return self._conditions[0]
        return {"_and": self._conditions}

    @staticmethod
    def and_(*queries: dict[str, Any]) -> dict[str, Any]:
        """Combine multiple query dicts with AND."""
        non_empty = [q for q in queries if q]
        if len(non_empty) == 0:
            return {}
        if len(non_empty) == 1:
            return non_empty[0]
        return {"_and": list(non_empty)}

    @staticmethod
    def or_(*queries: dict[str, Any]) -> dict[str, Any]:
        """Combine multiple query dicts with OR."""
        non_empty = [q for q in queries if q]
        if len(non_empty) == 0:
            return {}
        if len(non_empty) == 1:
            return non_empty[0]
        return {"_or": list(non_empty)}

    @staticmethod
    def not_(query: dict[str, Any]) -> dict[str, Any]:
        """Negate a query."""
        if not query:
            return {}
        return {"_not": query}


__all__ = ["PatentsViewQuery"]

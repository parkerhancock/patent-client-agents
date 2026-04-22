"""Static resources for USPTO Bulk Data MCP server."""

from __future__ import annotations

from importlib import resources

BULKDATA_PRODUCT_GUIDE_RESOURCE_URI = "resource://uspto-bulkdata/product-guide-2025"
BULKDATA_RESPONSE_SCHEMA_RESOURCE_URI = "resource://uspto-bulkdata/bulkdata-response-schema"
PATENT_DATA_SCHEMA_RESOURCE_URI = "resource://uspto-bulkdata/patent-data-schema"
PETITION_DECISION_SCHEMA_RESOURCE_URI = "resource://uspto-bulkdata/petition-decision-schema"


def _read_text(filename: str) -> str:
    return (
        resources.files("ip_tools.uspto_bulkdata.data")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )


def get_product_guide() -> str:
    """Return the 2025 bulk data product guide markdown."""
    return _read_text("2025_bulkdata_product_guide.md")


def get_bulkdata_response_schema() -> str:
    return _read_text("bulkdata-response-schema.json")


def get_patent_data_schema() -> str:
    return _read_text("patent-data-schema.json")


def get_petition_decision_schema() -> str:
    return _read_text("petition-decision-schema.json")

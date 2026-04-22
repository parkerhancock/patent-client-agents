"""Async API for USPTO BDSS/ODP bulk data (MCP-free)."""

from .api import (  # noqa: F401
    BulkDataProductResponse,
    BulkDataSearchResponse,
    UsptoOdpClient,
    get_client,
    get_product,
    search_products,
)
from .resources import (  # noqa: F401
    BULKDATA_PRODUCT_GUIDE_RESOURCE_URI,
    BULKDATA_RESPONSE_SCHEMA_RESOURCE_URI,
    PATENT_DATA_SCHEMA_RESOURCE_URI,
    PETITION_DECISION_SCHEMA_RESOURCE_URI,
    get_bulkdata_response_schema,
    get_patent_data_schema,
    get_petition_decision_schema,
    get_product_guide,
)

__all__ = [
    "UsptoOdpClient",
    "BulkDataSearchResponse",
    "BulkDataProductResponse",
    "get_client",
    "search_products",
    "get_product",
    "BULKDATA_PRODUCT_GUIDE_RESOURCE_URI",
    "BULKDATA_RESPONSE_SCHEMA_RESOURCE_URI",
    "PATENT_DATA_SCHEMA_RESOURCE_URI",
    "PETITION_DECISION_SCHEMA_RESOURCE_URI",
    "get_product_guide",
    "get_bulkdata_response_schema",
    "get_patent_data_schema",
    "get_petition_decision_schema",
]

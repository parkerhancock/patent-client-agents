"""INPI Brazil — RPI XML weekly bulk catalog client (dados.gov.br).

Lightweight CKAN-style catalog + download surface for the *Revista da
Propriedade Industrial* (RPI) — Brazil's weekly official IP bulletin
covering patents, trademarks, designs, GIs, IC topographies, software
programs, technology-transfer contracts, and INPI communications. No
auth — published under Decreto 8.777/2016 open license.

This connector intentionally ships a minimal v1 surface (catalog +
download) per CONNECTOR_STANDARDS.md §7.2 Shape E. Full RPI XML
ingestion (eight sections × per-issue layouts) is deferred to a
follow-up so this PR ships independently.
"""

from .client import CKAN_HOST, INPI_BR_RPI_DATASET_ID, InpiBrBulkClient
from .models import BulkDataset, BulkResource

__all__ = [
    "CKAN_HOST",
    "INPI_BR_RPI_DATASET_ID",
    "BulkDataset",
    "BulkResource",
    "InpiBrBulkClient",
]

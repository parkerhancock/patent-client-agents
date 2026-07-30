"""ILPO Israel trade mark feed client (data.gov.il, CKAN).

Lightweight CKAN catalog + download surface for the data.gov.il
trade-mark dataset published by the Israel Ministry of Justice / ILPO.
No auth — the dataset is publicly licensed.

This connector intentionally ships a minimal v1 surface (catalog +
download) per CONNECTOR_STANDARDS.md §7.2 Shape E. The CSV / JSON
resources behind the dataset are downloadable directly from data.gov.il
using the URL surfaced by ``list_ilpo_tm_releases``.
"""

from .client import CKAN_HOST, IlpoTmClient
from .models import IlpoTmDataset, IlpoTmResource

__all__ = [
    "CKAN_HOST",
    "IlpoTmClient",
    "IlpoTmDataset",
    "IlpoTmResource",
]

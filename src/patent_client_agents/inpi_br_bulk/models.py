"""Pydantic models for the INPI Brazil RPI bulk data catalog.

The *Revista da Propriedade Industrial* (RPI) is INPI Brazil's weekly
official bulletin. Every administrative act (filings, office actions,
allowances, registrations, oppositions, appeals, GI grants, IC topography
registrations, technology-transfer contract registrations) publishes
here. Eight sections — Patentes, Marcas, Desenhos Industriais, Indicações
Geográficas, Programas de Computador, Topografia de Circuitos Integrados,
Contratos de Tecnologia, Comunicados.

Distributed via the Brazilian Open Data Portal (dados.gov.br) under
Decreto 8.777/2016's open license — no auth. The catalog uses the
CKAN-compatible ``package_show`` action; the returned ``resources`` list
carries the per-section / per-file metadata we surface through
:class:`BulkResource`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


class BulkResource(BaseModel):
    """One downloadable resource within an INPI dados.gov.br dataset.

    Mirrors the CKAN ``resource`` shape, projected to the fields a
    consumer needs to identify and fetch the file (id, name, mimetype,
    size, download URL, last-modified timestamp).
    """

    id: str
    name: str | None = None
    description: str | None = None
    format: str | None = None
    mimetype: str | None = None
    size: int | None = None
    url: str | None = None
    last_modified: str | None = Field(default=None, alias="last_modified")

    model_config = _BASE_CONFIG


class BulkDataset(BaseModel):
    """An INPI dados.gov.br package (the RPI feed by default).

    ``resources`` is the list of downloadable files. For the canonical
    ``revista-da-propriedade-industrial-rpi`` dataset, these are the
    weekly XML / TXT / PDF artifacts (one per section per issue, since
    2017-01-31).
    """

    id: str
    name: str
    title: str | None = None
    notes: str | None = None
    license_id: str | None = None
    license_title: str | None = None
    metadata_modified: str | None = None
    organization: dict[str, Any] | None = None
    resources: list[BulkResource] = Field(default_factory=list)

    model_config = _BASE_CONFIG


__all__ = ["BulkDataset", "BulkResource"]

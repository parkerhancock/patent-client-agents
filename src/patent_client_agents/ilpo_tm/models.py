"""Pydantic models for the data.gov.il ILPO trade mark feed (CKAN).

The Israeli Ministry of Justice (ILPO) publishes the national trade
mark register to ``data.gov.il`` on a refresh cadence that varies by
dataset (typically weekly for the live register). The portal speaks
the standard CKAN action API, so :class:`IlpoTmDataset` mirrors a CKAN
``package`` and :class:`IlpoTmResource` mirrors a CKAN ``resource``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


class IlpoTmResource(BaseModel):
    """One downloadable resource within a data.gov.il TM dataset.

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


class IlpoTmDataset(BaseModel):
    """The data.gov.il TM dataset as reported by CKAN ``package_show``.

    ``resources`` is the list of downloadable files (CSV, JSON,
    dictionary PDF, etc., depending on the dataset).
    """

    id: str
    name: str
    title: str | None = None
    notes: str | None = None
    license_id: str | None = None
    license_title: str | None = None
    metadata_modified: str | None = None
    organization: dict[str, Any] | None = None
    resources: list[IlpoTmResource] = Field(default_factory=list)

    model_config = _BASE_CONFIG


__all__ = ["IlpoTmDataset", "IlpoTmResource"]

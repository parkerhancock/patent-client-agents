"""Base model configuration for USPTO ODP models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base model that ignores unknown fields.

    Use this for production models where we want type safety but also
    resilience against API changes that add new fields.
    """

    model_config = ConfigDict(extra="ignore")


class FlexibleModel(BaseModel):
    """Base model that allows unknown fields.

    Use this for models where we need to pass through unknown fields
    for backward compatibility or when the schema is not fully known.
    """

    model_config = ConfigDict(extra="allow")


__all__ = ["StrictModel", "FlexibleModel"]

"""Public re-exports for the TIPO OpenData connector.

Stub created in chunk 1 of 4; final tool surface (15 endpoints over
``cloud.tipo.gov.tw/S220/opdataapi/api/``) is written in chunk 3 per
``research/specs/tw-tipo-connector-spec.md``.
"""

from .client import TipoClient

__all__ = ["TipoClient"]

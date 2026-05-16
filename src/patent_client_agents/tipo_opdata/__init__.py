"""Async client for the TIPO OpenData REST API (Taiwan).

The Taiwan Intellectual Property Office (TIPO / 智慧財產局) publishes a
15-endpoint OpenData REST surface at
``https://cloud.tipo.gov.tw/S220/opdataapi/api/`` covering patent,
utility-model, design, and trademark bibliographic + status records.

Coverage is biblio-only: no claims, abstracts, or figures via the API.
Auth is a single ``tk`` UUID token (``TIPO_API_KEY`` env var) issued
by TIPO upon emailing a Word-form application to
``ipoid@tipo.gov.tw``.

See :class:`TipoClient` for the connection contract and the
``research/specs/tw-tipo-connector-spec.md`` for the full tool
surface.
"""

from .client import TipoClient
from .models import (
    PatentAlterationRow,
    PatentAnnuityRow,
    PatentApplRow,
    PatentChangeRow,
    PatentDivideRow,
    PatentPriorityRow,
    PatentPubRow,
    PatentRightsRow,
    PatentTwinsRow,
    TmarkApplRow,
    TmarkChangeRow,
    TmarkDivideRow,
    TmarkPicsRow,
    TmarkPriorityRow,
    TmarkRightsRow,
)

__all__ = [
    "TipoClient",
    "PatentApplRow",
    "PatentPubRow",
    "PatentRightsRow",
    "PatentPriorityRow",
    "PatentAnnuityRow",
    "PatentTwinsRow",
    "PatentAlterationRow",
    "PatentChangeRow",
    "PatentDivideRow",
    "TmarkApplRow",
    "TmarkRightsRow",
    "TmarkPriorityRow",
    "TmarkPicsRow",
    "TmarkChangeRow",
    "TmarkDivideRow",
]

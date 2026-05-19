"""Dispatch table mapping ``(office_code, right)`` → scraper coroutine.

Kept as an explicit dict (no decorator registry) because v1 has six
routes and a flat table is easier to read than dynamic registration.
New offices add one line per route here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .models import FeeSchedule, RightType
from .scrapers import cipo as _cipo
from .scrapers import cnipa as _cnipa
from .scrapers import dpma as _dpma
from .scrapers import epo as _epo
from .scrapers import euipo as _euipo
from .scrapers import ipaustralia as _ipau
from .scrapers import kipo as _kipo
from .scrapers import ukipo as _ukipo
from .scrapers import uspto as _uspto

# Each scraper takes no arguments; it owns its own BaseAsyncClient and
# closes it on exit. Returning a fully-validated FeeSchedule is the
# only contract.
Scraper = Callable[[], Awaitable[FeeSchedule]]


_DISPATCH: dict[tuple[str, RightType], Scraper] = {
    ("USPTO", RightType.patent): _uspto.scrape_uspto_patents,
    ("USPTO", RightType.trademark): _uspto.scrape_uspto_trademarks,
    ("USPTO", RightType.design): _uspto.scrape_uspto_designs,
    ("EPO", RightType.patent): _epo.scrape_epo_patents,
    ("EUIPO", RightType.trademark): _euipo.scrape_euipo_trademarks,
    ("EUIPO", RightType.design): _euipo.scrape_euipo_designs,
    ("CNIPA", RightType.patent): _cnipa.scrape_cnipa_patents,
    ("CIPO", RightType.patent): _cipo.scrape_cipo_patents,
    ("DPMA", RightType.patent): _dpma.scrape_dpma_patents,
    ("KIPO", RightType.patent): _kipo.scrape_kipo_patents,
    ("IPAU", RightType.patent): _ipau.scrape_ipaustralia_patents,
    ("UKIPO", RightType.patent): _ukipo.scrape_ukipo_patents,
    ("UKIPO", RightType.trademark): _ukipo.scrape_ukipo_trademarks,
}


OFFICES: tuple[str, ...] = (
    "USPTO",
    "EPO",
    "EUIPO",
    "CNIPA",
    "CIPO",
    "DPMA",
    "KIPO",
    "IPAU",
    "UKIPO",
)
"""Office codes covered in v1, in stable order for tool docstrings + listings."""


class UnsupportedRouteError(ValueError):
    """Raised when ``(office, right)`` has no registered scraper."""


def get_scraper(office_code: str, right: RightType) -> Scraper:
    """Look up the scraper for ``(office_code, right)``."""
    key = (office_code.upper(), right)
    try:
        return _DISPATCH[key]
    except KeyError as exc:
        raise UnsupportedRouteError(
            f"No fee scraper registered for office={office_code!r} "
            f"right={right.value!r}. Supported: {list_supported_routes()}."
        ) from exc


def list_supported_routes() -> list[tuple[str, str]]:
    """Return every ``(office_code, right_value)`` pair we can scrape."""
    return [(office, right.value) for (office, right) in _DISPATCH]


__all__ = [
    "OFFICES",
    "Scraper",
    "UnsupportedRouteError",
    "get_scraper",
    "list_supported_routes",
]

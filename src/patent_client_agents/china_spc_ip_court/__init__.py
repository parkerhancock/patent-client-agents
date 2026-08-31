"""China Supreme People's Court Intellectual Property Court connector."""

from .api import get_hearing_notice, list_hearing_index, search_site
from .client import (
    HEARING_INDEX_URL,
    ChinaSpcIpCourtClient,
    parse_hearing_index,
    parse_hearing_notice,
    parse_site_search,
)
from .models import (
    ChinaSpcIpHearingIndexItem,
    ChinaSpcIpHearingIndexResponse,
    ChinaSpcIpHearingNotice,
    ChinaSpcIpParty,
    ChinaSpcIpSiteSearchHit,
    ChinaSpcIpSiteSearchResponse,
)

__all__ = [
    "HEARING_INDEX_URL",
    "ChinaSpcIpCourtClient",
    "ChinaSpcIpHearingIndexItem",
    "ChinaSpcIpHearingIndexResponse",
    "ChinaSpcIpHearingNotice",
    "ChinaSpcIpParty",
    "ChinaSpcIpSiteSearchHit",
    "ChinaSpcIpSiteSearchResponse",
    "get_hearing_notice",
    "list_hearing_index",
    "parse_hearing_index",
    "parse_hearing_notice",
    "parse_site_search",
    "search_site",
]

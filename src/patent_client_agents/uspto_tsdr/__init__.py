"""USPTO TSDR (Trademark Status & Document Retrieval) client.

Access trademark status, documents, and images from the USPTO TSDR API.

Requires an API key. Sign in to the USPTO API Key Manager
(https://account.uspto.gov/api-manager/) with a free MyUSPTO account,
select the TSDR API product, and click "Request API key" — the key is
emailed and stored under your account. Lost keys can be recovered by
signing back in. Support: APIhelp@uspto.gov.

Example:
    async with TsdrClient() as client:
        # Get trademark status
        status = await client.get_status("97123456")
        print(f"{status.mark_text}: {status.status_description}")

        # Download mark image
        image_data = await client.get_image("97123456")

        # List documents
        docs = await client.get_documents("97123456")

Environment Variables:
    USPTO_TSDR_API_KEY: API key for TSDR access
"""

from .client import TsdrClient
from .models import (
    GoodsServices,
    LastUpdateInfo,
    MultiCaseStatus,
    Owner,
    ProsecutionEvent,
    TrademarkStatus,
    TsdrDocument,
)

__all__ = [
    "TsdrClient",
    "TrademarkStatus",
    "TsdrDocument",
    "LastUpdateInfo",
    "MultiCaseStatus",
    "Owner",
    "GoodsServices",
    "ProsecutionEvent",
]

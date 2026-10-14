"""Base class for this package's HTTP connector clients."""

from __future__ import annotations

from typing import Any

import httpx

from mcp_data_core.base_client import BaseAsyncClient

from .provenance import record_response


def install_fetch_recording(client: httpx.AsyncClient) -> None:
    """Add the provenance response hook to ``client`` once."""
    hooks = client.event_hooks.setdefault("response", [])
    if record_response not in hooks:
        hooks.append(record_response)


class ConnectorClient(BaseAsyncClient):
    """``BaseAsyncClient`` that records cache hits for ``shared.provenance``."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        install_fetch_recording(self._client)

"""Process-wide auth and rate-limit state for connector clients.

MCP tools build a new client per call, so tokens, sessions and rate limiters
kept on a client instance were thrown away after every call: each call
fetched a fresh token and per-office request caps never applied across calls.
State registered here lives for the process and is shared by every client
with the same key.
"""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

from mcp_data_core.oauth2 import OAuth2ClientCredentialsAuth

T = TypeVar("T")

_registry: dict[Hashable, Any] = {}


def process_shared(key: Hashable, factory: Callable[[], T]) -> T:
    """Return the process-wide object for ``key``, creating it on first use."""
    try:
        return _registry[key]
    except KeyError:
        _registry[key] = value = factory()
        return value


def reset_process_shared() -> None:
    """Forget all shared state (tests use this to isolate cases)."""
    _registry.clear()


class LoopLock:
    """An ``asyncio.Lock`` per running event loop.

    asyncio locks bind to the loop that first waits on them, so a lock kept for
    the whole process would fail under a second loop (as in tests).
    """

    def __init__(self) -> None:
        self._locks: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = (
            weakref.WeakKeyDictionary()
        )

    def _lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        lock = self._locks.get(loop)
        if lock is None:
            self._locks[loop] = lock = asyncio.Lock()
        return lock

    async def __aenter__(self) -> None:
        await self._lock().acquire()

    async def __aexit__(self, *exc_info: object) -> None:
        self._lock().release()


def shared_oauth2(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    scope: str | None = None,
    credentials_in_body: bool = False,
    extra_token_params: dict[str, str] | None = None,
) -> OAuth2ClientCredentialsAuth:
    """An ``OAuth2ClientCredentialsAuth`` shared by every client with these settings."""
    key = (
        "oauth2",
        token_url,
        client_id,
        client_secret,
        scope,
        credentials_in_body,
        tuple(sorted((extra_token_params or {}).items())),
    )
    return process_shared(
        key,
        lambda: OAuth2ClientCredentialsAuth(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            credentials_in_body=credentials_in_body,
            extra_token_params=extra_token_params,
        ),
    )

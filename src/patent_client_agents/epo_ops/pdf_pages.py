"""Pacing and page storage for assembling EPO OPS PDFs one page at a time.

OPS serves a publication's images one page per request and limits the
``images`` service to a per-minute request count that it reports on every
response in ``X-Throttling-Control`` (for example
``busy (images=green:100, ...)``). A client that ignores the header trips the
limit within a minute and OPS then blocks the service (``images=black:0``)
for everyone on the account. Large PCT pamphlets run to hundreds of pages, so
a full download can take longer than one MCP tool call should, and progress
must survive between calls and across autoscaled instances.
"""

from __future__ import annotations

import asyncio
import re
import time
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from mcp_data_core.mcp.downloads import BlobStore

#: ``images=green:50`` inside ``X-Throttling-Control``.
_SERVICE_RE = re.compile(r"(\w+)=(green|yellow|red|black):(\d+)")

#: Requests per minute assumed until OPS reports a figure (its documented
#: anonymous images allowance, and what it reports when ``overloaded``).
DEFAULT_IMAGES_PER_MINUTE = 50

#: Wait after OPS blocks the images service, when it gives no Retry-After.
#: OPS throttles per minute, so a block clears within one.
DEFAULT_BLOCK_SECONDS = 60.0

#: Margin over OPS's stated rate, so clock skew doesn't trip the limit.
_SAFETY = 1.1


def parse_throttle(header: str | None, service: str = "images") -> tuple[str, int] | None:
    """Return ``(color, requests_per_minute)`` for ``service``, or ``None``."""
    if not header:
        return None
    for name, color, count in _SERVICE_RE.findall(header):
        if name == service:
            return color, int(count)
    return None


class ImagesPacer:
    """Space OPS image requests to the rate OPS currently allows.

    One instance is shared by the process, because the OPS limit applies to
    the account rather than to a client object. Callers queue on a per-loop
    lock and each reserves the next slot before its request goes out.
    """

    def __init__(self, per_minute: int = DEFAULT_IMAGES_PER_MINUTE) -> None:
        self._interval = 60.0 / per_minute * _SAFETY
        self._next = 0.0
        self._locks: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = (
            weakref.WeakKeyDictionary()
        )

    @property
    def interval(self) -> float:
        return self._interval

    def _lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        lock = self._locks.get(loop)
        if lock is None:
            lock = self._locks[loop] = asyncio.Lock()
        return lock

    def seconds_until_ready(self) -> float:
        return max(0.0, self._next - time.monotonic())

    async def wait(self) -> None:
        """Sleep until this caller's slot, then reserve the following one."""
        async with self._lock():
            delay = self._next - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next = time.monotonic() + self._interval

    def observe(self, header: str | None) -> None:
        """Adopt the rate from an ``X-Throttling-Control`` header."""
        parsed = parse_throttle(header)
        if parsed is None:
            return
        color, per_minute = parsed
        if color == "black" or per_minute <= 0:
            self.block(DEFAULT_BLOCK_SECONDS)
            return
        interval = 60.0 / per_minute * _SAFETY
        # OPS reports red when the account is close to the limit; back off
        # further rather than ride the edge.
        if color == "red":
            interval *= 2
        self._interval = interval

    def block(self, seconds: float) -> None:
        """Hold every request until ``seconds`` from now."""
        self._next = max(self._next, time.monotonic() + seconds)


images_pacer = ImagesPacer()


class PageStore(Protocol):
    """Where fetched pages wait until the whole document is assembled."""

    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, content: bytes) -> None: ...


class LocalPageStore:
    """Pages on local disk (stdio and VM deployments)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        return self._root / key

    async def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None

    async def put(self, key: str, content: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(content)
        tmp.replace(path)


class BlobPageStore:
    """Pages in the deployment's durable blob store (Cloud Run).

    Autoscaled instances don't share local disk, so a follow-up call that
    lands on another instance would otherwise start over.
    """

    def __init__(self, store: BlobStore) -> None:
        self._store = store

    async def get(self, key: str) -> bytes | None:
        return await self._store.read_object(key)

    async def put(self, key: str, content: bytes) -> None:
        await self._store.put(
            key, content, content_type="application/pdf", filename=key.rsplit("/", 1)[-1]
        )


def default_page_store(local_root: Path) -> PageStore:
    """Blob store when the deployment injected one with reads, else local disk."""
    from mcp_data_core.mcp.downloads import get_blob_store

    store = get_blob_store()
    if store is not None and getattr(store, "read_object", None) is not None:
        return BlobPageStore(store)
    return LocalPageStore(local_root)


def page_key(publication: str, page: int) -> str:
    return f"epo/pdf-pages/{publication}/{page:05d}.pdf"


class PdfDownloadIncomplete(Exception):
    """The time budget ran out before every page was fetched.

    Fetched pages are saved, so calling again continues where this call
    stopped. Deliberately not a ``RuntimeError`` or ``ValueError``: the PDF
    cascade treats those as "this source has no PDF" and would move on.
    """

    def __init__(
        self,
        publication_number: str,
        *,
        pages_fetched: int,
        total_pages: int,
        seconds_per_page: float,
    ) -> None:
        self.publication_number = publication_number
        self.pages_fetched = pages_fetched
        self.total_pages = total_pages
        self.seconds_per_page = seconds_per_page
        super().__init__(
            f"Fetched {pages_fetched} of {total_pages} pages of {publication_number} "
            "from EPO OPS before this call's time budget ran out; progress is saved."
        )

    @property
    def remaining_pages(self) -> int:
        return self.total_pages - self.pages_fetched

    @property
    def estimated_seconds_remaining(self) -> int:
        return int(self.remaining_pages * self.seconds_per_page) + 1


class _BudgetExhausted(Exception):
    """Internal: waiting out a throttle block would pass the deadline."""


__all__ = [
    "BlobPageStore",
    "ImagesPacer",
    "LocalPageStore",
    "PageStore",
    "PdfDownloadIncomplete",
    "default_page_store",
    "images_pacer",
    "page_key",
    "parse_throttle",
]

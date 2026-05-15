"""Download registry with HMAC-signed resource URIs.

Search/list tools return signed download URLs on records that have
downloadable content (PDFs, filings, attachments). Example::

    https://mcp.example.com/downloads/uspto/applications/16123456/documents/XYZ?key=<hmac>

When a client hits the URL, the server verifies the HMAC, fetches the
document via a connector-registered fetcher (with disk caching), and
streams it back.

Resource paths are designed to map to future MCP resource templates::

    patent-client-agents://uspto/applications/{app_number}/documents/{doc_id}

Two rules govern how tool responses handle URLs:

    1. MASK INACCESSIBLE URLs. Any URL in a tool response that requires
       auth the agent doesn't have (API keys, tokens in our .env) must
       be removed.
    2. ADD DOWNLOAD URLs. When a search/list result has downloadable
       content, add a ``download_url`` field using
       ``build_download_url()``. Register a fetch function via
       ``register_source()``, and remove the dedicated download_* tool.

Env vars (all accept a ``LAW_TOOLS_*`` legacy alias)::

    LAW_TOOLS_CORE_PUBLIC_URL        base URL for download links
    LAW_TOOLS_CORE_API_KEY           secret for HMAC signing
    LAW_TOOLS_CORE_DOWNLOAD_CACHE    on-disk cache dir (default: ~/.cache/law_tools_core/downloads)
    LAW_TOOLS_CORE_DOWNLOAD_TTL_SECONDS  HMAC rotation bucket (default 86400)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import io
import logging
import tempfile
import time
import uuid
import zipfile
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from fastmcp.resources import ResourceContent
from fastmcp.tools.tool import ToolResult  # ty: ignore[unresolved-import]
from mcp.types import Annotations, ResourceLink
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from ..exceptions import BulkDownloadError
from . import _env

logger = logging.getLogger(__name__)


# URI scheme for MCP resources backed by this download registry. The shared
# scheme lets every download artifact be addressable as
# ``pca://{resource_path}`` regardless of whether the bytes ride out through
# the HTTP /downloads route or through MCP's resources/read.
RESOURCE_SCHEME = "pca"


def _public_url() -> str:
    return _env.get("PUBLIC_URL", "").rstrip("/")


def _secret() -> str:
    return _env.get("API_KEY", "")


def _cache_dir() -> Path:
    custom = _env.get("DOWNLOAD_CACHE")
    if custom:
        return Path(custom)
    return Path.home() / ".cache" / "law_tools_core" / "downloads"


def _bulk_zip_dir() -> Path:
    """Tempfile dir for assembled bulk-download zips. Sibling of the per-doc cache."""
    return _cache_dir().parent / "bulk_zips"


# Bulk zips are deleted on successful delivery; this is the backstop for
# zips that were assembled but never fully streamed (client disconnected,
# agent retried instead of consuming, etc.).
_BULK_ZIP_TTL_SECONDS = 3600

# Throttle for opportunistic sweeping inside handle_download — at most
# once every 10 minutes so a busy server doesn't reap on every request.
_BULK_ZIP_REAP_INTERVAL_SECONDS = 600
_last_bulk_zip_reap: float = 0.0


def _key_rotation_seconds() -> int:
    return int(_env.get("DOWNLOAD_TTL_SECONDS", "86400"))


_PERMANENT_BUCKET = "permanent"  # sentinel for non-expiring URLs


# ---------------------------------------------------------------------------
# HMAC signing
# ---------------------------------------------------------------------------


def _current_bucket() -> int:
    """Wall-clock bucket index for the current rotation window."""
    return int(time.time()) // _key_rotation_seconds()


def _bucket_expiry_epoch(bucket: int) -> int:
    """Unix epoch at which a URL signed with ``bucket`` definitively expires.

    A URL is valid while either ``current_bucket`` or ``current_bucket - 1``
    matches the signed bucket — so the latest moment a ``bucket``-signed
    URL still works is the end of the bucket immediately following it.
    """
    return (bucket + 2) * _key_rotation_seconds()


def sign_path(path: str, *, bucket: int | str | None = None) -> str:
    """HMAC-SHA256 of ``{path}|{bucket}``, truncated to 12 URL-safe base64 chars.

    ``bucket`` defaults to the current rotation bucket — so the same
    path mints a different signature each rotation window. Pass an
    explicit integer for testing, or the string ``"permanent"`` for a
    URL that never expires (the sentinel is also accepted by
    ``verify_path``).
    """
    if bucket is None:
        bucket = _current_bucket()
    payload = f"{path}|{bucket}".encode()
    sig = hmac.new(_secret().encode(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig[:9]).rstrip(b"=").decode()  # 9 bytes → 12 chars


def verify_path(path: str, signature: str) -> bool:
    """Constant-time HMAC verification.

    A URL is valid if its signature matches the current rotation bucket,
    the previous bucket (grace window for URLs minted near a boundary),
    or the special ``"permanent"`` bucket. There is no ``exp`` query
    parameter — the time dimension lives inside the HMAC. The agent
    reads ``expires_at`` from the tool response to know when to re-call.
    """
    if not _secret():
        return True  # no secret configured (local/stdio mode)
    current = _current_bucket()
    candidate_buckets: tuple[int | str, ...] = (current, current - 1, _PERMANENT_BUCKET)
    for bucket in candidate_buckets:
        expected = sign_path(path, bucket=bucket)
        if hmac.compare_digest(expected, signature):
            return True
    return False


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------


def _cache_key(resource_path: str) -> Path:
    digest = hashlib.sha256(resource_path.encode()).hexdigest()[:16]
    return _cache_dir() / digest


def _cache_get(resource_path: str) -> tuple[bytes, str | None] | None:
    """Return ``(content, filename)`` if cached, else ``None``.

    Filename is read from a ``.name`` sidecar written by ``_cache_put``
    and is used to set Content-Disposition when streaming cached
    content.
    """
    path = _cache_key(resource_path)
    if not path.exists():
        return None
    name_path = path.with_suffix(".name")
    filename = name_path.read_text() if name_path.exists() else None
    return path.read_bytes(), filename


def _cache_put(resource_path: str, content: bytes, filename: str | None = None) -> None:
    _cache_dir().mkdir(parents=True, exist_ok=True)
    key = _cache_key(resource_path)
    key.write_bytes(content)
    if filename:
        key.with_suffix(".name").write_text(filename)


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------


@dataclass
class DownloadSource:
    """A registered download source."""

    fetch: Callable[..., Awaitable[tuple[bytes, str]]]  # (content, filename)
    mime_type: str = "application/pdf"
    path_prefix: str = ""


# Maps path prefixes to sources. Matched by longest prefix.
_SOURCES: dict[str, DownloadSource] = {}


def register_source(
    path_prefix: str,
    fetch: Callable[..., Awaitable[tuple[bytes, str]]],
    mime_type: str = "application/pdf",
) -> None:
    """Register a download source for a path prefix.

    Connectors call this at module import to make their content
    retrievable through the shared ``/downloads/{resource_path}`` route.
    Idempotent — re-registering the same prefix replaces the entry.
    """
    _SOURCES[path_prefix] = DownloadSource(
        fetch=fetch, mime_type=mime_type, path_prefix=path_prefix
    )


def _match_source(resource_path: str) -> tuple[DownloadSource, str] | None:
    """Find the source matching a resource path.

    Returns ``(source, remaining_path)`` or ``None`` if unknown.
    Longest-prefix match.
    """
    # Explicit `.keys()` + lambda keeps ty's element-type inference on str
    # rather than the more general `Sized` it infers from `key=len`.
    for prefix in sorted(_SOURCES.keys(), key=lambda p: len(p), reverse=True):
        if resource_path.startswith(prefix + "/") or resource_path == prefix:
            remainder = resource_path[len(prefix) :].lstrip("/")
            return _SOURCES[prefix], remainder
    return None


# ---------------------------------------------------------------------------
# URL builder (called by tools)
# ---------------------------------------------------------------------------


def build_resource_uri(resource_path: str) -> str:
    """Canonical MCP resource URI for a registered download.

    Mirrors :func:`build_download_url` but produces a scheme-rooted URI
    (``pca://{path}``) that resolves through ``resources/read`` rather
    than the HTTP ``/downloads`` route. The URI is permanent — it does
    not carry an HMAC signature and never expires, even when the HTTP
    URL is rotating.
    """
    return f"{RESOURCE_SCHEME}://{resource_path.strip('/')}"


def build_download_url(
    resource_path: str,
    *,
    label: str = "",
    permanent: bool = False,
) -> str:
    """Build a signed download URL (remote) or resource-path stub (local).

    The URL is signed against the current rotation bucket and is valid
    for at least ``LAW_TOOLS_CORE_DOWNLOAD_TTL_SECONDS`` (default 24h),
    up to ~2× that depending on minting time relative to the bucket
    boundary. No ``exp`` query parameter — the time dimension is bound
    inside the HMAC, so the URL is just ``?key={sig}``.

    Args:
        resource_path: Resource path (e.g. ``"uspto/applications/16123456/documents/XYZ"``)
        label: Human-readable description for the return message
        permanent: Mint a URL that never expires. Use sparingly —
            leaks are valid until ``LAW_TOOLS_CORE_API_KEY`` rotates.
    """
    resource_path = resource_path.strip("/")
    public = _public_url()

    if public:
        bucket: int | str | None = _PERMANENT_BUCKET if permanent else None
        sig = sign_path(resource_path, bucket=bucket)
        url = f"{public}/downloads/{resource_path}?key={sig}"
        if label:
            return f"{label}\n\nDownload: {url}"
        return url

    # Local/stdio fallback: tools handle their own tempfiles
    return f"(local mode) Resource: {resource_path}"


async def build_download_url_or_fetch(
    resource_path: str,
    *,
    label: str = "",
) -> str:
    """Build a signed URL, or fetch + save to tempfile for local mode.

    Async version that actually fetches in local mode.
    """
    resource_path = resource_path.strip("/")
    public = _public_url()

    if public:
        sig = sign_path(resource_path)
        url = f"{public}/downloads/{resource_path}?key={sig}"
        if label:
            return f"{label}\n\nDownload: {url}"
        return url

    match = _match_source(resource_path)
    if match is None:
        raise ValueError(f"Unknown download source for path: {resource_path}")

    source, remainder = match
    content, filename = await source.fetch(remainder)

    suffix = Path(filename).suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix="law_tools_core_")
    tmp.write(content)
    tmp.close()

    size_str = f"{len(content):,} bytes"
    if label:
        return f"Downloaded {label} ({size_str}). Saved to {tmp.name}"
    return f"Downloaded file ({size_str}). Saved to {tmp.name}"


async def download_response(
    resource_path: str,
    content: bytes,
    *,
    filename: str,
    content_type: str = "application/pdf",
    permanent: bool = False,
    **extras: object,
) -> dict:
    """Standard return shape for MCP download tools.

    Caches ``content`` so the URL hit serves from disk, then returns the
    canonical payload: ``download_url``, ``expires_at``, ``filename``,
    ``content_type``, ``size_bytes``, plus any ``extras`` (e.g.
    ``patent_number``).

    ``expires_at`` is an ISO 8601 UTC timestamp telling the agent the
    *guaranteed* deadline — the URL is good through that moment and
    refused afterward. (The actual upper bound can be the same instant
    or up to one rotation window later, depending on when in the bucket
    cycle the URL was minted; the response always reports the latest
    moment the URL is *guaranteed* to still work.)

    Pass ``permanent=True`` to mint a non-expiring URL (omits
    ``expires_at``); use sparingly because leaks become permanent until
    ``LAW_TOOLS_CORE_API_KEY`` rotates.

    In remote/HTTP mode (``LAW_TOOLS_CORE_PUBLIC_URL`` set) the response
    carries a signed ``download_url``. In local/stdio mode the bytes
    are written to a tempfile and ``file_path`` is returned instead —
    tempfiles do not expire. No base64 in either case.
    """
    payload: dict = {
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "resource_uri": build_resource_uri(resource_path),
        **extras,
    }
    # Cache the bytes in both transport modes — the MCP resources/read
    # handler reads from the same per-doc cache as the HTTP route, so
    # we want them warm regardless of which path a client picks.
    _cache_put(resource_path, content, filename=filename)
    if _public_url():
        payload["download_url"] = build_download_url(resource_path, permanent=permanent)
        if not permanent:
            expiry = _bucket_expiry_epoch(_current_bucket())
            payload["expires_at"] = datetime.fromtimestamp(expiry, tz=UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
    else:
        suffix = Path(filename).suffix or ".bin"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix="law_tools_core_")
        tmp.write(content)
        tmp.close()
        payload["file_path"] = tmp.name
    return payload


def _make_resource_link(
    *,
    uri: str,
    name: str,
    mime_type: str,
    size: int | None = None,
    description: str | None = None,
    last_modified: str | None = None,
) -> ResourceLink:
    """Build a ``ResourceLink`` content block.

    Centralized so every tool that surfaces a downloadable artifact
    produces the same shape: ``type="resource_link"`` (required by the
    spec), populated ``size`` when known so clients can decide whether
    to attempt ``resources/read``, ``annotations.lastModified`` when the
    source carries that metadata.
    """
    # MCP's Annotations + ResourceLink are Pydantic models whose camelCase
    # aliases are the only construction names ty sees. Using model_validate
    # avoids kwarg checking and keeps the wire-format names.
    annotations = (
        Annotations.model_validate({"audience": ["user"], "lastModified": last_modified})
        if last_modified
        else Annotations.model_validate({"audience": ["user"]})
    )
    return ResourceLink.model_validate(
        {
            "type": "resource_link",
            "uri": uri,
            "name": name,
            "mimeType": mime_type,
            "size": size,
            "description": description,
            "annotations": annotations,
        }
    )


async def download_tool_result(
    resource_path: str,
    content: bytes,
    *,
    filename: str,
    content_type: str = "application/pdf",
    permanent: bool = False,
    description: str | None = None,
    last_modified: str | None = None,
    **extras: object,
) -> ToolResult:
    """Build a dual-transport ``ToolResult`` for a downloadable artifact.

    Returns a ``ToolResult`` carrying:

    - ``content``: a ``ResourceLink`` content block pointing at
      ``pca://{resource_path}``. Resource-aware MCP clients (e.g. Claude
      CoWork) follow this via ``resources/read`` over the existing MCP
      session — no separate HTTP fetch, no domain allowlist.
    - ``structured_content``: the same dict returned by
      :func:`download_response`, with ``download_url`` (when
      ``LAW_TOOLS_CORE_PUBLIC_URL`` is set), ``resource_uri``,
      ``expires_at`` (rotating URLs), ``filename``, ``content_type``,
      ``size_bytes``, plus any ``extras``.

    Callers that need to mutate the payload before returning (e.g. add a
    ``source`` field) can pass it via ``**extras`` or skip this wrapper
    and use :func:`download_response` directly.
    """
    payload = await download_response(
        resource_path,
        content,
        filename=filename,
        content_type=content_type,
        permanent=permanent,
        **extras,
    )
    link = _make_resource_link(
        uri=payload["resource_uri"],
        name=filename,
        mime_type=content_type,
        size=len(content),
        description=description,
        last_modified=last_modified,
    )
    return ToolResult(content=[link], structured_content=payload)


async def read_resource(resource_path: str) -> list[ResourceContent]:
    """Resolve a ``pca://{resource_path}`` resource to MCP content.

    The body of every connector's ``@sub_mcp.resource(...)`` handler.
    Loads bytes through :func:`fetch_with_cache` (hot from cache,
    fetched from the registered source on miss) and wraps them in a
    ``ResourceContent`` with the source's declared MIME type. The MCP
    layer base64-encodes bytes into ``BlobResourceContents`` on the
    way out.

    Bulk-zip resources are intentionally not served here — they live
    behind the HTTP ``/downloads/bulk_zips/{uuid}`` route only.
    Resource-aware clients should prefer the per-doc URIs surfaced in
    the bulk tool's manifest.
    """
    resource_path = resource_path.strip("/")
    if resource_path.startswith("bulk_zips/"):
        raise ValueError(
            "Bulk-zip resources are HTTP-only — fetch via download_url, or "
            "follow the per-document resource URIs in the bulk tool's manifest."
        )
    match = _match_source(resource_path)
    mime = match[0].mime_type if match else "application/octet-stream"
    content, _filename = await fetch_with_cache(resource_path)
    return [ResourceContent(content, mime_type=mime)]


async def fetch_with_cache(
    resource_path: str,
    *,
    fetcher: Callable[[], Awaitable[tuple[bytes, str]]] | None = None,
) -> tuple[bytes, str]:
    """Fetch a resource via the per-doc cache, falling back to a fetcher on miss.

    Standard ``download_response`` only writes the cache; ``handle_download``
    only reads it. This helper closes the loop so callers (notably bulk
    download tools) get cache-hit speed on repeat fetches without going
    through the HTTP route.

    On cache miss, uses ``fetcher`` if provided, else falls back to the
    fetcher registered with :func:`register_source` for this path. The
    result is always written back to the cache before returning. Raises
    ``ValueError`` if neither is available.
    """
    resource_path = resource_path.strip("/")
    cached = _cache_get(resource_path)
    if cached is not None:
        content, cached_filename = cached
        if cached_filename:
            return content, cached_filename
    if fetcher is not None:
        content, filename = await fetcher()
    else:
        match = _match_source(resource_path)
        if match is None:
            raise ValueError(
                f"No registered fetcher for resource path {resource_path!r} "
                "and no inline fetcher was provided."
            )
        source, remainder = match
        content, filename = await source.fetch(remainder)
    _cache_put(resource_path, content, filename=filename)
    return content, filename


# ---------------------------------------------------------------------------
# Bulk downloads
# ---------------------------------------------------------------------------


@dataclass
class BulkItem:
    """One unit of a bulk download request.

    Attributes:
        item_id: Stable, user-meaningful identifier. Becomes the manifest
            key and the directory prefix inside the zip archive
            (``{item_id}/{filename}``).
        resource_path: Cache key for this item's bytes — must match the
            registered fetcher's path format. Reused by the n=1
            short-circuit so per-doc cache stays hot across calls.
        metadata: Extra fields surfaced in the manifest entry (date,
            doc_type, anything source-specific).
    """

    item_id: str
    resource_path: str
    metadata: dict = field(default_factory=dict)


def _build_zip_bytes(items_in_order: list[tuple[str, bytes, str]]) -> bytes:
    """Build a zip archive in memory. CPU-bound; call via ``asyncio.to_thread``."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item_id, content, filename in items_in_order:
            zf.writestr(f"{item_id}/{filename}", content)
    return buf.getvalue()


async def download_bulk_response(
    items: list[BulkItem],
    fetcher: Callable[[BulkItem], Awaitable[tuple[bytes, str]]],
    *,
    container_label: str,
    container_metadata: dict | None = None,
    content_type_single: str = "application/pdf",
    max_concurrency: int = 5,
) -> dict:
    """Fetch a list of items concurrently and return a download payload.

    n=1: short-circuits to :func:`download_response` (raw file, no zip
    ceremony). The lone item's ``resource_path`` is reused as the cache
    key so re-fetches share the per-doc cache.

    n>1: fans out the fetch with bounded concurrency, zips successes
    into a tempfile under ``~/.cache/law_tools_core/bulk_zips/{uuid}.zip``,
    and returns a signed one-shot URL plus a manifest. Per-item failures
    do not fail the call — they go in the manifest with
    ``status='error'``. If *all* items fail, raises
    :class:`BulkDownloadError`.

    Args:
        items: The items to fetch. Empty list raises ``BulkDownloadError``.
        fetcher: Async callable that takes a ``BulkItem`` and returns
            ``(content, filename)``. Typically delegates to the source's
            registered per-doc fetcher.
        container_label: Used as the zip filename (``{label}.zip``) and
            surfaced as ``container`` in the response if not overridden.
        container_metadata: Extra top-level fields for the response (e.g.
            ``{"container": "16123456"}``). Item-level metadata wins on
            key collisions.
        content_type_single: MIME type for the n=1 short-circuit. Ignored
            for n>1 (zip is always ``application/zip``).
        max_concurrency: Cap on concurrent fetcher calls. Default 5;
            polite-source bulks can pass lower (e.g. PACER → 3).

    Returns:
        A dict matching :func:`download_response`'s shape, plus
        ``manifest``, ``item_count``, ``ok_count``, and ``error_count``
        for the n>1 case.
    """
    if not items:
        raise BulkDownloadError("download_bulk_response called with no items")

    container_meta = dict(container_metadata or {})

    if len(items) == 1:
        only = items[0]
        content, filename = await fetcher(only)
        extras: dict = {**container_meta, "item_id": only.item_id, **only.metadata}
        return await download_response(
            only.resource_path,
            content,
            filename=filename,
            content_type=content_type_single,
            **extras,
        )

    sem = asyncio.Semaphore(max_concurrency)
    results: dict[str, tuple[bytes, str]] = {}
    manifest_entries: dict[str, dict] = {}
    manifest_lock = asyncio.Lock()

    async def _fetch_one(item: BulkItem) -> None:
        entry: dict = {"item_id": item.item_id, **item.metadata}
        async with sem:
            try:
                content, filename = await fetcher(item)
            except Exception as exc:  # noqa: BLE001 — record per-item, don't fail bulk
                entry["status"] = "error"
                entry["error"] = str(exc) or exc.__class__.__name__
                async with manifest_lock:
                    manifest_entries[item.item_id] = entry
                return
        results[item.item_id] = (content, filename)
        entry["status"] = "ok"
        entry["filename"] = f"{item.item_id}/{filename}"
        entry["size_bytes"] = len(content)
        # Only advertise a resource_uri / per-item download_url for items
        # whose resource_path maps to a registered source. Bulk callers
        # sometimes mint ad-hoc paths (e.g. ``ptab/trial-decisions/{id}``)
        # that are used only as cache keys — exposing those as MCP URIs
        # would dangle because resources/read has no fetcher to call.
        if _match_source(item.resource_path) is not None:
            entry["resource_uri"] = build_resource_uri(item.resource_path)
            if _public_url():
                entry["download_url"] = build_download_url(item.resource_path)
        async with manifest_lock:
            manifest_entries[item.item_id] = entry

    await asyncio.gather(*(_fetch_one(item) for item in items))

    # Manifest order matches input order so callers can rely on it.
    manifest = [
        manifest_entries[item.item_id] for item in items if item.item_id in manifest_entries
    ]
    ok_count = len(results)
    error_count = len(items) - ok_count

    if ok_count == 0:
        first_err = next(
            (e.get("error") for e in manifest if e.get("status") == "error"),
            "unknown",
        )
        raise BulkDownloadError(
            f"All {len(items)} items failed to fetch (first error: {first_err})."
        )

    items_in_order = [
        (item.item_id, *results[item.item_id]) for item in items if item.item_id in results
    ]
    zip_bytes = await asyncio.to_thread(_build_zip_bytes, items_in_order)
    zip_filename = f"{container_label}.zip"

    payload: dict = {
        **container_meta,
        "filename": zip_filename,
        "content_type": "application/zip",
        "size_bytes": len(zip_bytes),
        "item_count": len(items),
        "ok_count": ok_count,
        "error_count": error_count,
        "manifest": manifest,
    }

    if _public_url():
        bulk_id = uuid.uuid4().hex
        bulk_dir = _bulk_zip_dir()
        await asyncio.to_thread(bulk_dir.mkdir, parents=True, exist_ok=True)
        bulk_path = bulk_dir / f"{bulk_id}.zip"
        await asyncio.to_thread(bulk_path.write_bytes, zip_bytes)
        # Sidecar with the user-facing filename for Content-Disposition.
        await asyncio.to_thread(bulk_path.with_suffix(".name").write_text, zip_filename)

        resource_path = f"bulk_zips/{bulk_id}"
        payload["download_url"] = build_download_url(resource_path)
        expiry = _bucket_expiry_epoch(_current_bucket())
        payload["expires_at"] = datetime.fromtimestamp(expiry, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    else:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".zip", delete=False, prefix="law_tools_core_bulk_"
        )
        tmp.write(zip_bytes)
        tmp.close()
        payload["file_path"] = tmp.name

    return payload


async def download_bulk_tool_result(
    items: list[BulkItem],
    fetcher: Callable[[BulkItem], Awaitable[tuple[bytes, str]]],
    *,
    container_label: str,
    container_metadata: dict | None = None,
    content_type_single: str = "application/pdf",
    max_concurrency: int = 5,
) -> ToolResult:
    """Bulk-download companion to :func:`download_tool_result`.

    Wraps :func:`download_bulk_response` and returns a ``ToolResult`` whose:

    - ``content`` carries per-item ``ResourceLink`` blocks, one per
      successfully fetched item. Resource-aware clients follow these
      via ``resources/read`` over MCP — the per-doc transport path
      that bypasses the bulk-zip cap problem (large archives can blow
      past JSON-RPC message limits on common clients).
    - ``structured_content`` carries the same dict
      :func:`download_bulk_response` returns: ``download_url`` (the zip,
      for URL-comfortable clients), ``manifest`` (with per-item
      ``resource_uri`` and ``download_url`` echoes), and the counts.

    n=1 short-circuits to a single-doc ``ToolResult`` (same shape as
    :func:`download_tool_result`).
    """
    payload = await download_bulk_response(
        items,
        fetcher,
        container_label=container_label,
        container_metadata=container_metadata,
        content_type_single=content_type_single,
        max_concurrency=max_concurrency,
    )
    blocks: list[ResourceLink] = []
    manifest = payload.get("manifest")
    if manifest is None:
        # n=1 short-circuit — payload is a single-doc download_response
        # dict. Build a single ResourceLink for it.
        if payload.get("resource_uri"):
            blocks.append(
                _make_resource_link(
                    uri=payload["resource_uri"],
                    name=payload["filename"],
                    mime_type=payload.get("content_type", "application/octet-stream"),
                    size=payload.get("size_bytes"),
                )
            )
    else:
        for entry in manifest:
            if entry.get("status") != "ok":
                continue
            uri = entry.get("resource_uri")
            if not uri:
                continue
            # The manifest filename is prefixed with the item_id directory
            # (e.g. "ABC123/spec.pdf"); strip for the link display name.
            display_name = entry["filename"].split("/", 1)[-1]
            blocks.append(
                _make_resource_link(
                    uri=uri,
                    name=display_name,
                    mime_type=content_type_single,
                    size=entry.get("size_bytes"),
                    description=entry.get("description") or entry.get("document_title"),
                )
            )
    return ToolResult(content=blocks, structured_content=payload)


class _DeleteOnSuccess:
    """Async stream that unlinks the underlying file only after delivery.

    Bulk-zip route uses this to enforce one-shot-on-success delivery: if
    the entire byte stream is consumed (``bytes_sent == file_size``),
    the zip is deleted. If reading is interrupted (client disconnect,
    error), the file is left in place so the agent can retry — the 1h
    TTL sweeper acts as the backstop.
    """

    def __init__(self, path: Path, expected_size: int, chunk_size: int = 65536) -> None:
        self._path = path
        self._expected_size = expected_size
        self._chunk_size = chunk_size

    async def __aiter__(self) -> AsyncIterator[bytes]:
        bytes_sent = 0
        try:
            with self._path.open("rb") as fh:
                while True:
                    chunk = await asyncio.to_thread(fh.read, self._chunk_size)
                    if not chunk:
                        break
                    bytes_sent += len(chunk)
                    yield chunk
        finally:
            if bytes_sent == self._expected_size:
                try:
                    self._path.unlink()
                    self._path.with_suffix(".name").unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning(
                        "bulk zip delivered but failed to unlink %s: %s", self._path, exc
                    )


def reap_stale_bulk_zips(*, ttl_seconds: int = _BULK_ZIP_TTL_SECONDS) -> int:
    """Delete bulk-zip tempfiles older than ``ttl_seconds``.

    Backstop for zips that were never successfully delivered (so
    ``_DeleteOnSuccess`` never reaped them). Safe to call from a
    background task or at server startup. Returns the number of files
    deleted.
    """
    bulk_dir = _bulk_zip_dir()
    if not bulk_dir.exists():
        return 0
    cutoff = time.time() - ttl_seconds
    deleted = 0
    for path in bulk_dir.iterdir():
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                deleted += 1
        except OSError as exc:
            logger.warning("failed to reap stale bulk zip %s: %s", path, exc)
    return deleted


# ---------------------------------------------------------------------------
# Route handler (registered in server_factory.build_server)
# ---------------------------------------------------------------------------


def _maybe_reap_bulk_zips() -> None:
    """Run the bulk-zip sweeper if we haven't recently.

    Called opportunistically from ``handle_download``. Cheap when
    throttled — just a clock comparison.
    """
    global _last_bulk_zip_reap
    now = time.time()
    if now - _last_bulk_zip_reap < _BULK_ZIP_REAP_INTERVAL_SECONDS:
        return
    _last_bulk_zip_reap = now
    try:
        reap_stale_bulk_zips()
    except Exception as exc:  # noqa: BLE001 — sweeper failure must never fail a download
        logger.warning("bulk zip sweeper failed: %s", exc)


async def _serve_bulk_zip(uuid_hex: str) -> Response:
    """Stream a bulk zip from the tempfile dir and unlink on full delivery."""
    bulk_path = _bulk_zip_dir() / f"{uuid_hex}.zip"
    if not bulk_path.exists():
        return Response(
            f"Bulk download {uuid_hex} is no longer available "
            "(already delivered or expired). Re-call the bulk tool to regenerate.",
            status_code=404,
        )
    size = bulk_path.stat().st_size
    name_sidecar = bulk_path.with_suffix(".name")
    filename = name_sidecar.read_text() if name_sidecar.exists() else f"{uuid_hex}.zip"
    return StreamingResponse(
        _DeleteOnSuccess(bulk_path, expected_size=size),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(size),
            "Cache-Control": "no-store",
        },
    )


async def handle_download(request: Request) -> Response:
    """Handle GET ``/downloads/{resource_path}?key={hmac_signature}``."""
    resource_path: str = request.path_params.get("path", "")
    if not resource_path:
        return Response("Missing resource path", status_code=400)

    # Verify HMAC. Time/expiry is bound inside the HMAC (rotating-key
    # scheme), so there's no separate `exp` query parameter — an
    # expired URL simply fails to verify.
    signature = request.query_params.get("key", "")
    if not verify_path(resource_path, signature):
        return Response(
            "Invalid signature, or URL has expired (URLs rotate every "
            f"{_key_rotation_seconds()}s; re-call the tool to mint a fresh one).",
            status_code=403,
        )

    # Opportunistic backstop reap so stale bulk zips don't pile up on
    # long-running servers. Throttled to once per 10 minutes.
    _maybe_reap_bulk_zips()

    # Bulk zips live outside the per-doc cache and the source registry —
    # they're transient tempfiles produced by `download_bulk_response`.
    if resource_path.startswith("bulk_zips/"):
        uuid_hex = resource_path[len("bulk_zips/") :]
        if "/" in uuid_hex or not uuid_hex:
            return Response(f"Invalid bulk-zip path: {resource_path}", status_code=400)
        return await _serve_bulk_zip(uuid_hex)

    cached = _cache_get(resource_path)
    if cached is not None:
        content, cached_filename = cached
        source_match = _match_source(resource_path)
        mime = source_match[0].mime_type if source_match else "application/octet-stream"
        disposition = (
            f'attachment; filename="{cached_filename}"' if cached_filename else "attachment"
        )
        return Response(
            content=content,
            media_type=mime,
            headers={
                "Content-Disposition": disposition,
                "Cache-Control": "private, max-age=3600",
            },
        )

    match = _match_source(resource_path)
    if match is None:
        return Response(f"Unknown resource: {resource_path}", status_code=404)

    source, remainder = match
    try:
        content, filename = await source.fetch(remainder)
    except PermissionError as exc:
        return Response(str(exc), status_code=410)
    except Exception as exc:
        return Response(f"Fetch error: {exc}", status_code=502)

    _cache_put(resource_path, content, filename=filename)

    return Response(
        content=content,
        media_type=source.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )

"""Rewrite key-gated USPTO ODP download URLs to the signed download proxy.

The proxy host and signing secret come from the environment, so they stay a
deployment concern. USPTO ODP bulk-file URLs
(``fileDownloadURI``) require the server's ``X-API-KEY`` and are useless to an
agent as-is. When ``USPTO_ODP_PROXY_URL`` is set, each such URL is rewritten
host-swap style (``api.uspto.gov`` → the proxy host, native path preserved)
with an HMAC ``?sig=`` over the path. The deployment's download
proxy (a Cloudflare Worker) verifies the
signature, injects the API key, follows USPTO's 302 to CloudFront, and streams
the bytes — so agents download with no key. When no proxy is configured the
URL is stripped instead (a key-gated URL the agent can't use is worse than its
absence).
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from mcp_data_core.mcp.downloads import sign_path

# USPTO ODP URL fields that require the server's X-API-KEY.
_AUTH_URL_FIELDS = {"fileDownloadURI", "downloadURI", "downloadUrl", "fileLocationURI"}

# Upstream host whose download URLs the proxy reverse-proxies.
_PROXY_UPSTREAM_HOST = "api.uspto.gov"

# Only these api.uspto.gov path prefixes are rewritten — bulk-data file
# downloads only; every other auth URL keeps being stripped. MUST stay in sync
# with the download proxy's ALLOWED_PATH_PREFIXES.
_PROXY_PATH_PREFIXES = ("api/v1/datasets/products/files/",)


def proxy_base() -> str:
    """Configured download-proxy base URL, or '' when unset.

    Set ``USPTO_ODP_PROXY_URL`` (e.g. ``https://downloads.patentclient.com``)
    to a host that reverse-proxies ``api.uspto.gov`` and injects the API key.
    """
    return os.environ.get("USPTO_ODP_PROXY_URL", "").rstrip("/")


def _rewrite_download_url(url: str, proxy_base_url: str) -> str | None:
    """Rewrite an ``api.uspto.gov`` download URL to the signed proxy, or ``None``.

    Returns ``None`` when ``url`` is not a proxyable USPTO download URL (wrong
    host, or a path outside ``_PROXY_PATH_PREFIXES``); the caller then strips
    the field.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or parts.netloc != _PROXY_UPSTREAM_HOST:
        return None
    path = parts.path.lstrip("/")
    if not path.startswith(_PROXY_PATH_PREFIXES):
        return None
    sig = sign_path(path)
    query = f"{parts.query}&sig={sig}" if parts.query else f"sig={sig}"
    proxy = urlsplit(proxy_base_url)
    return urlunsplit((proxy.scheme, proxy.netloc, "/" + path, query, ""))


def rewrite_auth_urls(data: Any) -> None:
    """Recursively rewrite (or strip) auth-required URL fields in place.

    For each ``_AUTH_URL_FIELDS`` entry: when a download proxy is configured
    and the URL is a proxyable bulk-file URL, rewrite it to the signed proxy
    URL (keyless for the agent). Otherwise delete the field. Walks JSON-shaped
    data of arbitrary depth.
    """
    proxy_base_url = proxy_base()
    if isinstance(data, dict):
        for key in _AUTH_URL_FIELDS & data.keys():
            value = data[key]
            rewritten = (
                _rewrite_download_url(value, proxy_base_url)
                if proxy_base_url and isinstance(value, str)
                else None
            )
            if rewritten is not None:
                data[key] = rewritten
            else:
                del data[key]
        for v in data.values():
            rewrite_auth_urls(v)
    elif isinstance(data, list):
        for item in data:
            rewrite_auth_urls(item)

"""Unit tests for the USPTO bulk-data download proxy URL rewriting.

Pure logic — no HTTP, no cassettes. Covers ``_rewrite_download_url`` /
``_rewrite_auth_urls`` in ``patent_client_agents.mcp.tools.uspto`` and pins
the HMAC signature scheme against a shared vector that the Cloudflare Worker
(patent-client-agents-deploy) must reproduce.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_data_core.mcp.downloads import sign_path, verify_path
from patent_client_agents.mcp.tools import uspto

_PROXY = "https://downloads.patentclient.com"
_SECRET = "test-shared-hmac-secret-v1"
_BULK_URL = (
    "https://api.uspto.gov/api/v1/datasets/products/files/PTFWPRE/"
    "2011-2020-patent-filewrapper-full-json-20260607.zip"
)
_BULK_PATH = (
    "api/v1/datasets/products/files/PTFWPRE/2011-2020-patent-filewrapper-full-json-20260607.zip"
)
# A USPTO download URL outside the proxy allowlist (application doc download).
_NON_BULK_URL = "https://api.uspto.gov/api/v1/download/applications/16123456/ABC.pdf"

_VECTORS = json.loads(
    (Path(__file__).parent / "fixtures" / "hmac_download_proxy_vectors.json").read_text()
)


@pytest.fixture
def proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a proxy host and the shared HMAC secret."""
    monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", _SECRET)
    monkeypatch.setenv("USPTO_ODP_PROXY_URL", _PROXY)


def test_rewrite_bulk_url_swaps_host_and_signs(proxy_env: None) -> None:
    rewritten = uspto._rewrite_download_url(_BULK_URL, _PROXY)
    assert rewritten is not None
    parts = urlsplit(rewritten)
    assert parts.scheme == "https"
    assert parts.netloc == "downloads.patentclient.com"
    # Upstream path preserved verbatim.
    assert parts.path == "/" + _BULK_PATH
    sig = parse_qs(parts.query)["sig"][0]
    # The signature verifies under the shared scheme (current rotation bucket).
    assert verify_path(_BULK_PATH, sig) is True


def test_rewrite_preserves_existing_query(proxy_env: None) -> None:
    rewritten = uspto._rewrite_download_url(_BULK_URL + "?foo=bar", _PROXY)
    assert rewritten is not None
    q = parse_qs(urlsplit(rewritten).query)
    assert q["foo"] == ["bar"]
    assert "sig" in q


def test_non_bulk_url_not_rewritten(proxy_env: None) -> None:
    # Outside the allowlist → None (caller strips it).
    assert uspto._rewrite_download_url(_NON_BULK_URL, _PROXY) is None


def test_foreign_host_not_rewritten(proxy_env: None) -> None:
    assert uspto._rewrite_download_url("https://evil.example.com/api/v1/x", _PROXY) is None


def test_rewrite_auth_urls_rewrites_bulk_strips_others(proxy_env: None) -> None:
    data = {
        "productFileBag": {
            "fileDataBag": [
                {"fileName": "a.zip", "fileDownloadURI": _BULK_URL},
                {"fileName": "doc.pdf", "fileDownloadURI": _NON_BULK_URL},
            ]
        }
    }
    uspto._rewrite_auth_urls(data)
    files = data["productFileBag"]["fileDataBag"]
    # Bulk file: rewritten to the proxy host.
    assert files[0]["fileDownloadURI"].startswith(_PROXY + "/" + _BULK_PATH)
    # Non-bulk file: field removed entirely.
    assert "fileDownloadURI" not in files[1]


def test_no_proxy_configured_strips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USPTO_ODP_PROXY_URL", raising=False)
    data = {"fileDownloadURI": _BULK_URL, "fileName": "a.zip"}
    uspto._rewrite_auth_urls(data)
    assert "fileDownloadURI" not in data
    assert data["fileName"] == "a.zip"


def test_shared_hmac_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the signature scheme so the Worker's Web Crypto port can't drift."""
    monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", _VECTORS["secret"])
    for case in _VECTORS["cases"]:
        assert sign_path(case["path"], bucket=case["bucket"]) == case["sig"]

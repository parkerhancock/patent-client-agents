"""WAF token manager for USPTO Trademark Search.

Handles acquisition, caching, and refresh of the AWS WAF token required
to access the USPTO TESS API at tmsearch.uspto.gov.

Token acquisition requires Playwright (install via ``pip install
patent-client-agents[tmsearch]`` plus ``playwright install chromium``)
but the token lasts ~4 days. Once cached, all subsequent API calls use
curl_cffi with no browser needed.

For headless/server deployments, the recommended pattern is to mint
tokens out of band (e.g. a Cloud Run Job running Playwright on a
schedule) and feed the JSON via ``PCA_WAF_TOKEN_JSON`` env var or
``PCA_WAF_TOKEN_PATH`` on-disk path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from law_tools_core.exceptions import ConfigurationError

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default cache lives under the PCA cache root rather than the legacy
# ~/.law-tools/ path. The legacy path is still honored as a read-only
# fallback for one release (see ``_legacy_cache_path``).
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "patent_client_agents"
_LEGACY_CACHE_DIR = Path.home() / ".law-tools"

_TMSEARCH_URL = "https://tmsearch.uspto.gov"
_EXPIRY_MARGIN_HOURS = 6

# AWS WAF binds the token to the User-Agent that solved the challenge.
# Subsequent API calls (in TmsearchClient._post) MUST send the same UA
# string or USPTO returns non-200 and the token looks broken.
WAF_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _env_token_path() -> str | None:
    """Resolve token path env var with legacy fallback."""
    return os.environ.get("PCA_WAF_TOKEN_PATH") or os.environ.get("WAF_TOKEN_PATH")


def _env_token_json() -> str | None:
    """Resolve inline JSON token env var with legacy fallback."""
    return os.environ.get("PCA_WAF_TOKEN_JSON") or os.environ.get("LAW_TOOLS_WAF_TOKEN_JSON")


class WafTokenManager:
    """Manage the AWS WAF token for USPTO trademark search.

    The token is acquired by loading tmsearch.uspto.gov in a headless
    browser (Playwright), which triggers the AWS WAF challenge.js to
    set an ``aws-waf-token`` cookie. The token is then cached to disk
    and reused until it expires.

    If Playwright is not installed, the manager serves tokens from cache
    only. This supports server deployments where a cron job refreshes
    the token and the application itself has no browser.

    Args:
        token_path: Path to the token cache file. Defaults to the
            ``PCA_WAF_TOKEN_PATH`` env var (legacy ``WAF_TOKEN_PATH``)
            or ``~/.cache/patent_client_agents/waf_token.json``.
    """

    def __init__(self, token_path: str | Path | None = None) -> None:
        # Tracks whether the cache path is the default vs. explicit. The
        # legacy fallback at ``~/.law-tools/waf_token.json`` only applies
        # when the caller is on the default — passing an explicit path
        # (test fixtures, custom deployments) must be honored exactly.
        self._using_default_path: bool
        if token_path is not None:
            self._cache_path = Path(token_path)
            self._using_default_path = False
        else:
            env_path = _env_token_path()
            if env_path:
                self._cache_path = Path(env_path)
                self._using_default_path = False
            else:
                self._cache_path = _DEFAULT_CACHE_DIR / "waf_token.json"
                self._using_default_path = True
        self._legacy_cache_path = _LEGACY_CACHE_DIR / "waf_token.json"
        self._lock = asyncio.Lock()

    async def get_token(self, *, force_refresh: bool = False) -> str:
        """Get a valid WAF token, acquiring a new one if needed.

        Args:
            force_refresh: Acquire a new token even if the cache is valid.

        Returns:
            The WAF token string.

        Raises:
            ConfigurationError: If no valid token is available and
                Playwright is not installed.
        """
        async with self._lock:
            if not force_refresh:
                cached = self._read_cache()
                if cached is not None:
                    return cached

            if not PLAYWRIGHT_AVAILABLE:
                raise ConfigurationError(
                    "No valid WAF token cached and Playwright is not installed. "
                    "Either install with the [tmsearch] extra "
                    "(pip install 'patent-client-agents[tmsearch]' && "
                    "playwright install chromium) or provide a cached "
                    f"token at {self._cache_path} (override with "
                    "PCA_WAF_TOKEN_PATH / PCA_WAF_TOKEN_JSON)."
                )

            token, expires = await self._acquire_token()
            self._write_cache(token, expires)
            return token

    def _read_cache(self) -> str | None:
        """Read and validate the cached token. Returns None if expired.

        Sources, in order of consideration:
        - ``PCA_WAF_TOKEN_JSON`` env var (or legacy ``LAW_TOOLS_WAF_TOKEN_JSON``;
          a Secret Manager mount on Cloud Run typically writes here).
        - On-disk cache file at the resolved path.
        - Legacy on-disk cache at ``~/.law-tools/waf_token.json`` (one-release shim).

        When multiple exist, the one with the freshest ``acquired``
        timestamp wins. This matters on Cloud Run: Secret Manager binds
        env at instance start, so the env token is frozen for the life
        of the instance. When the in-process retry mints a fresh token
        (because the env token has been WAF-rejected), the new token is
        written to disk — and on subsequent calls we want to prefer the
        fresh disk copy over the stale env copy without paying another
        mint.
        """
        env_payload = _env_token_json()
        disk_payload: str | None = None
        # Only walk the legacy path when we're on the default location;
        # an explicit token_path/env override should be honored exactly.
        candidate_paths = [self._cache_path]
        if self._using_default_path:
            candidate_paths.append(self._legacy_cache_path)
        for path in candidate_paths:
            if path.exists():
                try:
                    disk_payload = path.read_text()
                    break
                except OSError as exc:
                    logger.warning("Failed to read WAF token cache at %s: %s", path, exc)

        candidates: list[tuple[str, str, str]] = []
        if env_payload:
            parsed = self._parse_for_freshest(env_payload, source="env")
            if parsed is not None:
                candidates.append(parsed)
        if disk_payload:
            parsed = self._parse_for_freshest(disk_payload, source=str(self._cache_path))
            if parsed is not None:
                candidates.append(parsed)

        if not candidates:
            return None
        candidates.sort(key=lambda c: c[0], reverse=True)
        acquired, token, source = candidates[0]
        logger.debug("Using freshest WAF token from %s (acquired %s)", source, acquired)
        return token

    @classmethod
    def _parse_for_freshest(cls, raw: str, *, source: str) -> tuple[str, str, str] | None:
        """Parse a payload and return (acquired, token, source) if valid."""
        token = cls._parse_payload(raw, source=source)
        if token is None:
            return None
        try:
            acquired = json.loads(raw).get("acquired", "")
        except (json.JSONDecodeError, TypeError):
            acquired = ""
        return acquired, token, source

    @staticmethod
    def _parse_payload(raw: str, *, source: str) -> str | None:
        try:
            data = json.loads(raw)
            token = data["token"]
            expires = data["expires"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse WAF token payload from %s: %s", source, exc)
            return None
        expires_dt = datetime.fromtimestamp(expires, tz=UTC)
        margin = _EXPIRY_MARGIN_HOURS * 3600
        if datetime.now(UTC).timestamp() + margin >= expires:
            logger.info("WAF token from %s expired or expiring soon", source)
            return None
        logger.debug("Using WAF token from %s (expires %s)", source, expires_dt.isoformat())
        return token  # type: ignore[no-any-return]

    def _write_cache(self, token: str, expires: float) -> None:
        """Write token to cache file."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "token": token,
            "expires": expires,
            "acquired": datetime.now(UTC).isoformat(),
        }
        self._cache_path.write_text(json.dumps(data, indent=2))
        logger.info("WAF token cached to %s", self._cache_path)

    @staticmethod
    async def _acquire_token() -> tuple[str, float]:
        """Acquire a fresh WAF token via Playwright.

        Returns:
            Tuple of (token_value, expiry_timestamp).
        """
        assert async_playwright is not None
        logger.info("Acquiring WAF token via Playwright...")

        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                ],
            )
            ctx = await browser.new_context(user_agent=WAF_USER_AGENT)
            page = await ctx.new_page()
            await page.goto(_TMSEARCH_URL)
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(5000)

            cookies = await ctx.cookies()
            waf_cookies = [c for c in cookies if c.get("name") == "aws-waf-token"]
            if not waf_cookies:
                raise ConfigurationError(
                    "Playwright loaded tmsearch.uspto.gov but no aws-waf-token "
                    "cookie was set. The WAF challenge may have changed."
                )

            token: str = waf_cookies[0].get("value", "")
            expires: float = waf_cookies[0].get("expires", 0.0)
            hours_left = (expires - datetime.now(UTC).timestamp()) / 3600
            logger.info("WAF token acquired (expires in ~%.0f hours)", hours_left)

            await browser.close()
        finally:
            await pw.stop()

        return token, expires

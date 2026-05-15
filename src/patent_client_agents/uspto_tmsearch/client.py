"""USPTO Trademark Search client.

Uses curl_cffi (Chrome TLS impersonation) for API calls and a cached
AWS WAF token for authentication. The WAF token is acquired via Playwright
when needed and lasts ~4 days. See ``token_manager.py`` for details.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from law_tools_core.exceptions import AuthenticationError, ConfigurationError

from .models import TrademarkSearchResponse, TrademarkSearchResult
from .token_manager import WAF_USER_AGENT, WafTokenManager

# curl_cffi is imported lazily so the import-time path doesn't pull in
# its native deps for callers that never use the trademark search.
try:
    from curl_cffi.requests import AsyncSession

    CURL_CFFI_AVAILABLE = True
except ImportError:
    AsyncSession = None  # type: ignore[assignment,misc]  # ty: ignore[invalid-assignment]
    CURL_CFFI_AVAILABLE = False


# AWS WAF binds the token to (UA + cookie). The headers below mirror
# what tmsearch.uspto.gov's web UI sends on a real Chrome request.
_BROWSER_HEADERS = {
    "User-Agent": WAF_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://tmsearch.uspto.gov",
    "Referer": "https://tmsearch.uspto.gov/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


class TmsearchClient:
    """Async client for USPTO Trademark Search (TESS).

    Uses curl_cffi with Chrome TLS fingerprinting to call the TESS
    Elasticsearch API. Authentication is handled by a cached AWS WAF
    token, acquired automatically via Playwright when needed.

    If Playwright is not installed, the client works as long as a valid
    cached token exists (e.g. refreshed by a cron job on the server).

    Example:
        async with TmsearchClient() as client:
            results = await client.search_wordmark("APPLE")
            for tm in results.results:
                print(f"{tm.serial_number}: {tm.wordmark}")
    """

    API_URL = "https://tmsearch.uspto.gov/prod-stage-v1-0-0/tmsearch"

    def __init__(self, token_path: str | Path | None = None) -> None:
        """Initialize the client.

        Args:
            token_path: Path to the WAF token cache file. Defaults to
                ``PCA_WAF_TOKEN_PATH`` env var (legacy ``WAF_TOKEN_PATH``)
                or ``~/.cache/patent_client_agents/waf_token.json``.
        """
        if not CURL_CFFI_AVAILABLE:
            raise ConfigurationError(
                "TmsearchClient requires curl_cffi for AWS WAF TLS impersonation. "
                "Install with: pip install 'patent-client-agents[tmsearch]'"
            )
        self._token_manager = WafTokenManager(token_path=token_path)
        self._session: Any = None
        self._token: str | None = None

    async def __aenter__(self) -> TmsearchClient:
        await self._init_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _init_session(self) -> None:
        """Initialize curl_cffi session with WAF token."""
        self._token = await self._token_manager.get_token()
        self._session = AsyncSession(impersonate="chrome120")

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._token = None

    async def _search(
        self,
        query: dict[str, Any],
        *,
        size: int = 100,
        from_: int = 0,
    ) -> TrademarkSearchResponse:
        """Execute a search query against the USPTO API."""
        if self._session is None:
            await self._init_session()
        assert self._session is not None

        payload = {
            "query": query,
            "size": min(size, 500),
            "from": from_,
        }

        result = await self._post(payload)

        hits = result.get("hits", {})
        total = hits.get("totalValue", 0)
        took = result.get("took", 0)

        results = []
        for hit in hits.get("hits", []):
            source = hit.get("source", {})
            if "serialNumber" not in source:
                source["serialNumber"] = hit.get("id", "")
            results.append(TrademarkSearchResult.model_validate(source))

        return TrademarkSearchResponse(
            total=total,
            results=results,
            query_time_ms=took,
        )

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to the API, retrying once with a fresh token on 403."""
        assert self._session is not None

        response = await self._session.post(
            self.API_URL,
            json=payload,
            cookies={"aws-waf-token": self._token or ""},
            headers=_BROWSER_HEADERS,
        )

        if response.status_code != 200:
            # Non-200 (403, 202 WAF challenge, etc.) — refresh token and retry
            original_status = response.status_code
            try:
                self._token = await self._token_manager.get_token(force_refresh=True)
            except ConfigurationError as exc:
                # Playwright unavailable in this environment (e.g. Cloud Run
                # service image). Re-raise as AuthenticationError carrying
                # the upstream status so the symptom isn't misclassified as
                # a misconfiguration. Out-of-band refresh (Cloud Run Job)
                # is the recovery path; this caller can't help in-process.
                raise AuthenticationError(
                    f"USPTO trademark search returned {original_status} and "
                    "the cached WAF token cannot be refreshed in-process "
                    f"(Playwright unavailable). {exc}"
                ) from exc
            response = await self._session.post(
                self.API_URL,
                json=payload,
                cookies={"aws-waf-token": self._token},
                headers=_BROWSER_HEADERS,
            )
            if response.status_code != 200:
                raise AuthenticationError(
                    f"USPTO trademark search returned {response.status_code} "
                    "after token refresh. The WAF challenge may have changed."
                )

        return response.json()

    async def search_wordmark(
        self,
        wordmark: str,
        *,
        live_only: bool = False,
        size: int = 100,
        from_: int = 0,
    ) -> TrademarkSearchResponse:
        """Search trademarks by wordmark text."""
        must_clauses: list[dict[str, Any]] = [{"match": {"wordmark": wordmark}}]
        if live_only:
            must_clauses.append({"term": {"alive": True}})
        query = {"bool": {"must": must_clauses}}
        return await self._search(query, size=size, from_=from_)

    async def search_owner(
        self,
        owner_name: str,
        *,
        live_only: bool = False,
        size: int = 100,
        from_: int = 0,
    ) -> TrademarkSearchResponse:
        """Search trademarks by owner name."""
        must_clauses: list[dict[str, Any]] = [{"match": {"ownerName": owner_name}}]
        if live_only:
            must_clauses.append({"term": {"alive": True}})
        query = {"bool": {"must": must_clauses}}
        return await self._search(query, size=size, from_=from_)

    async def search_goods_services(
        self,
        terms: str,
        *,
        live_only: bool = False,
        size: int = 100,
        from_: int = 0,
    ) -> TrademarkSearchResponse:
        """Search trademarks by goods and services description."""
        must_clauses: list[dict[str, Any]] = [{"match": {"goodsAndServices": terms}}]
        if live_only:
            must_clauses.append({"term": {"alive": True}})
        query = {"bool": {"must": must_clauses}}
        return await self._search(query, size=size, from_=from_)

    async def get_by_serial(self, serial_number: str) -> TrademarkSearchResult | None:
        """Get a trademark by its serial number."""
        query = {"term": {"serialNumber": serial_number}}
        response = await self._search(query, size=1)
        if response.results:
            return response.results[0]
        return None

    async def get_by_registration(self, registration_number: str) -> TrademarkSearchResult | None:
        """Get a trademark by its registration number."""
        query = {"term": {"registrationNumber": registration_number}}
        response = await self._search(query, size=1)
        if response.results:
            return response.results[0]
        return None

    async def search(
        self,
        *,
        wordmark: str | None = None,
        owner: str | None = None,
        goods_services: str | None = None,
        serial_number: str | None = None,
        registration_number: str | None = None,
        live_only: bool = False,
        status: Literal["live", "dead", "all"] = "all",
        size: int = 100,
        from_: int = 0,
    ) -> TrademarkSearchResponse:
        """Search trademarks with multiple criteria.

        At least one search criterion must be provided.

        Raises:
            ValueError: If no search criteria provided.
        """
        must_clauses: list[dict[str, Any]] = []
        should_clauses: list[dict[str, Any]] = []

        if wordmark:
            should_clauses.append({"match": {"wordmark": wordmark}})
        if owner:
            should_clauses.append({"match": {"ownerName": owner}})
        if goods_services:
            should_clauses.append({"match": {"goodsAndServices": goods_services}})
        if serial_number:
            must_clauses.append({"term": {"serialNumber": serial_number}})
        if registration_number:
            must_clauses.append({"term": {"registrationNumber": registration_number}})

        if should_clauses:
            must_clauses.append({"bool": {"should": should_clauses, "minimum_should_match": 1}})

        if not must_clauses:
            raise ValueError("At least one search criterion must be provided")

        if live_only or status == "live":
            must_clauses.append({"term": {"alive": True}})
        elif status == "dead":
            must_clauses.append({"term": {"alive": False}})

        query = {"bool": {"must": must_clauses}}
        return await self._search(query, size=size, from_=from_)

    async def search_all(
        self,
        *,
        wordmark: str | None = None,
        owner: str | None = None,
        live_only: bool = False,
        batch_size: int = 500,
        max_results: int | None = None,
    ) -> list[TrademarkSearchResult]:
        """Search and paginate through all matching trademarks."""
        all_results: list[TrademarkSearchResult] = []
        from_ = 0
        batch_size = min(batch_size, 500)

        while True:
            response = await self.search(
                wordmark=wordmark,
                owner=owner,
                live_only=live_only,
                size=batch_size,
                from_=from_,
            )

            if not response.results:
                break

            all_results.extend(response.results)

            if max_results and len(all_results) >= max_results:
                all_results = all_results[:max_results]
                break

            if len(response.results) < batch_size:
                break

            from_ += batch_size

            if from_ > 10000:
                break

        return all_results


__all__ = ["TmsearchClient"]

"""Fake EUIPO network shared by the Trademark Search and Design Search suites.

The fake sits below each client's own OAuth handler, so the real token fetch,
header injection, retries and error mapping all run.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx2

TOKEN_PATH_SUFFIX = "/oidc/accessToken"
TOKEN = "euipo-tok-1"


def is_token_request(request: httpx2.Request) -> bool:
    return request.url.path.endswith(TOKEN_PATH_SUFFIX)


def euipo_transport(
    handler: Callable[[httpx2.Request], httpx2.Response],
    seen: list[httpx2.Request] | None = None,
) -> httpx2.MockTransport:
    """Answer the OAuth token endpoint and hand API requests to ``handler``.

    Every request (token and API) is appended to ``seen`` when given.
    """

    def route(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        if is_token_request(request):
            return httpx2.Response(
                200, json={"access_token": TOKEN, "token_type": "Bearer", "expires_in": 3600}
            )
        return handler(request)

    return httpx2.MockTransport(route)


def api_requests(seen: list[httpx2.Request]) -> list[httpx2.Request]:
    return [r for r in seen if not is_token_request(r)]

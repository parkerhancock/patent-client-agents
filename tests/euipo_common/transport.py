"""Fake EUIPO network shared by the Trademark Search and Design Search suites.

The fake sits below each client's own OAuth handler, so the real token fetch,
header injection, retries and error mapping all run.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

TOKEN_PATH_SUFFIX = "/oidc/accessToken"
TOKEN = "euipo-tok-1"


def is_token_request(request: httpx.Request) -> bool:
    return request.url.path.endswith(TOKEN_PATH_SUFFIX)


def euipo_transport(
    handler: Callable[[httpx.Request], httpx.Response],
    seen: list[httpx.Request] | None = None,
) -> httpx.MockTransport:
    """Answer the OAuth token endpoint and hand API requests to ``handler``.

    Every request (token and API) is appended to ``seen`` when given.
    """

    def route(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if is_token_request(request):
            return httpx.Response(
                200, json={"access_token": TOKEN, "token_type": "Bearer", "expires_in": 3600}
            )
        return handler(request)

    return httpx.MockTransport(route)


def api_requests(seen: list[httpx.Request]) -> list[httpx.Request]:
    return [r for r in seen if not is_token_request(r)]

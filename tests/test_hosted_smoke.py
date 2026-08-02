from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "hosted_smoke.py"
SPEC = importlib.util.spec_from_file_location("hosted_smoke", SCRIPT)
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


@pytest.mark.asyncio
async def test_check_availability_accepts_oauth_challenge():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/-/health":
            return httpx.Response(200, json={"status": "ok"})
        if ".well-known" in str(request.url):
            return httpx.Response(200, json={"resource": "https://example.test/mcp"})
        return httpx.Response(401)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await smoke.check_availability(
            "https://example.test/mcp", attempts=1, client=client
        )

    assert report == {
        "health_status": 200,
        "metadata_status": 200,
        "endpoint_status": 401,
        "attempts": 1,
    }


@pytest.mark.asyncio
async def test_check_availability_rejects_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/-/health":
            return httpx.Response(200, json={"status": "ok"})
        if ".well-known" in str(request.url):
            return httpx.Response(200, json={})
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(smoke.SmokeFailure, match="MCP endpoint returned HTTP 503"):
            await smoke.check_availability("https://example.test/mcp", attempts=1, client=client)


@pytest.mark.asyncio
async def test_check_availability_rejects_bad_health_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/-/health":
            return httpx.Response(200, json={"status": "starting"})
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(smoke.SmokeFailure, match="health response did not report ok"):
            await smoke.check_availability("https://example.test/mcp", attempts=1, client=client)


def test_protected_resource_url_preserves_mcp_path():
    assert (
        smoke.protected_resource_url("https://example.test/mcp")
        == "https://example.test/.well-known/oauth-protected-resource/mcp"
    )


def test_health_url_uses_host_root():
    assert smoke.health_url("https://example.test/mcp") == "https://example.test/-/health"

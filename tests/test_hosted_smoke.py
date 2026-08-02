from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

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
        if ".well-known" in str(request.url):
            return httpx.Response(200, json={"resource": "https://example.test/mcp"})
        return httpx.Response(401)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await smoke.check_availability(
            "https://example.test/mcp", attempts=1, client=client
        )

    assert report == {"metadata_status": 200, "endpoint_status": 401, "attempts": 1}


@pytest.mark.asyncio
async def test_check_availability_rejects_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if ".well-known" in str(request.url):
            return httpx.Response(200, json={})
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(smoke.SmokeFailure, match="MCP endpoint returned HTTP 503"):
            await smoke.check_availability("https://example.test/mcp", attempts=1, client=client)


class _FakeMcpClient:
    def __init__(self, _url: str, **_kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def list_tools(self):
        names = smoke.REQUIRED_TOOLS | {f"extra_{index}" for index in range(3)}
        return [SimpleNamespace(name=name) for name in names]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return SimpleNamespace(isError=False)

    async def list_resource_templates(self):
        return [SimpleNamespace(uriTemplate="pca://downloads/{path}")]


@pytest.mark.asyncio
async def test_check_functional_covers_representative_surfaces():
    report = await smoke.check_functional(
        "https://example.test/mcp",
        "token",
        min_tools=6,
        client_factory=_FakeMcpClient,
    )

    assert report == {
        "tool_count": 6,
        "tool_checks": ["fees", "registered_ip", "substantive_law"],
        "resource_template_count": 1,
    }


def test_protected_resource_url_preserves_mcp_path():
    assert (
        smoke.protected_resource_url("https://example.test/mcp")
        == "https://example.test/.well-known/oauth-protected-resource/mcp"
    )

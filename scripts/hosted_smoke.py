#!/usr/bin/env python3
"""Check hosted MCP availability and, with a token, core tool workflows."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import httpx

DEFAULT_URL = "https://mcp.patentclient.com/mcp"
REQUIRED_TOOLS = {
    "list_fee_jurisdictions",
    "search_mpep",
    "search_patents_global",
}


class SmokeFailure(RuntimeError):
    """A hosted smoke check failed."""


def protected_resource_url(server_url: str) -> str:
    """Return the RFC 9728 metadata URL for an MCP endpoint."""
    parsed = urlsplit(server_url)
    return f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource{parsed.path}"


async def check_availability(
    server_url: str,
    *,
    attempts: int = 3,
    timeout: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Require healthy OAuth metadata and a non-server-error MCP endpoint."""
    owned_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout, follow_redirects=False)
    metadata_url = protected_resource_url(server_url)
    last_error = "availability check did not run"
    try:
        for attempt in range(1, attempts + 1):
            try:
                metadata = await http.get(metadata_url)
                endpoint = await http.get(server_url, headers={"Accept": "application/json"})
                if metadata.status_code != 200:
                    raise SmokeFailure(f"OAuth metadata returned HTTP {metadata.status_code}")
                try:
                    metadata.json()
                except ValueError as exc:
                    raise SmokeFailure("OAuth metadata was not valid JSON") from exc
                if endpoint.status_code >= 500 or endpoint.status_code == 404:
                    raise SmokeFailure(f"MCP endpoint returned HTTP {endpoint.status_code}")
                return {
                    "metadata_status": metadata.status_code,
                    "endpoint_status": endpoint.status_code,
                    "attempts": attempt,
                }
            except (httpx.HTTPError, SmokeFailure) as exc:
                last_error = str(exc)
                if attempt < attempts:
                    await asyncio.sleep(2 ** (attempt - 1))
        raise SmokeFailure(f"hosted availability failed after {attempts} attempts: {last_error}")
    finally:
        if owned_client:
            await http.aclose()


async def check_functional(
    server_url: str,
    token: str,
    *,
    min_tools: int = 100,
    client_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Run representative registered-IP, corpus, fee, and resource checks."""
    if client_factory is None:
        from fastmcp import Client

        client_factory = Client

    async with client_factory(server_url, auth=token, timeout=30) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        if len(tools) < min_tools:
            raise SmokeFailure(f"tool count {len(tools)} is below floor {min_tools}")
        missing = REQUIRED_TOOLS - tool_names
        if missing:
            raise SmokeFailure(f"required tools missing: {', '.join(sorted(missing))}")

        calls = {
            "registered_ip": ("search_patents_global", {"query": "battery", "page_size": 1}),
            "substantive_law": ("search_mpep", {"query": "subject matter eligibility", "limit": 1}),
            "fees": ("list_fee_jurisdictions", {}),
        }
        for label, (name, arguments) in calls.items():
            result = await client.call_tool(name, arguments)
            if getattr(result, "isError", False):
                raise SmokeFailure(f"{label} tool check returned an MCP error")

        templates = await client.list_resource_templates()
        if not templates:
            raise SmokeFailure("server exposed no resource templates")
        return {
            "tool_count": len(tools),
            "tool_checks": sorted(calls),
            "resource_template_count": len(templates),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--availability-only", action="store_true")
    parser.add_argument("--token-env", default="PCA_HOSTED_SMOKE_TOKEN")
    parser.add_argument("--min-tools", type=int, default=100)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    return parser


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    report = {
        "url": args.url,
        "availability": await check_availability(args.url, attempts=args.attempts),
    }
    if not args.availability_only:
        token = os.getenv(args.token_env)
        if not token:
            raise SmokeFailure(f"{args.token_env} is required for functional checks")
        report["functional"] = await check_functional(args.url, token, min_tools=args.min_tools)
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = asyncio.run(_run(args))
    except SmokeFailure as exc:
        print(f"Hosted smoke failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        availability = report["availability"]
        print(
            f"Hosted availability passed: metadata={availability['metadata_status']} "
            f"endpoint={availability['endpoint_status']} attempts={availability['attempts']}"
        )
        if functional := report.get("functional"):
            print(
                f"Hosted functional smoke passed: tools={functional['tool_count']} "
                f"resource_templates={functional['resource_template_count']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

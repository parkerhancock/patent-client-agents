#!/usr/bin/env python3
"""Check public availability for the hosted MCP deployment."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any
from urllib.parse import urlsplit

import httpx

DEFAULT_URL = "https://mcp.patentclient.com/mcp"


class SmokeFailure(RuntimeError):
    """A hosted smoke check failed."""


def protected_resource_url(server_url: str) -> str:
    """Return the RFC 9728 metadata URL for an MCP endpoint."""
    parsed = urlsplit(server_url)
    return f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource{parsed.path}"


def health_url(server_url: str) -> str:
    """Return the deployment health URL for an MCP endpoint."""
    parsed = urlsplit(server_url)
    return f"{parsed.scheme}://{parsed.netloc}/-/health"


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
    deployment_health_url = health_url(server_url)
    last_error = "availability check did not run"
    try:
        for attempt in range(1, attempts + 1):
            try:
                health = await http.get(deployment_health_url)
                metadata = await http.get(metadata_url)
                endpoint = await http.get(server_url, headers={"Accept": "application/json"})
                if health.status_code != 200:
                    raise SmokeFailure(f"health endpoint returned HTTP {health.status_code}")
                try:
                    health_payload = health.json()
                except ValueError as exc:
                    raise SmokeFailure("health response was not valid JSON") from exc
                if health_payload.get("status") != "ok":
                    raise SmokeFailure("health response did not report ok")
                if metadata.status_code != 200:
                    raise SmokeFailure(f"OAuth metadata returned HTTP {metadata.status_code}")
                try:
                    metadata.json()
                except ValueError as exc:
                    raise SmokeFailure("OAuth metadata was not valid JSON") from exc
                if endpoint.status_code >= 500 or endpoint.status_code == 404:
                    raise SmokeFailure(f"MCP endpoint returned HTTP {endpoint.status_code}")
                return {
                    "health_status": health.status_code,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    return parser


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "url": args.url,
        "availability": await check_availability(args.url, attempts=args.attempts),
    }


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
            f"Hosted availability passed: health={availability['health_status']} "
            f"metadata={availability['metadata_status']} "
            f"endpoint={availability['endpoint_status']} attempts={availability['attempts']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate read-only and provenance schemas across the exposed MCP surface."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "coverage" / "sources.yaml"
TOOL_SOURCES_PATH = ROOT / "coverage" / "tool-sources.yaml"

CORE_PROVENANCE_FIELDS = {"retrieved_at", "source_url", "source_name", "connector_version"}
CATEGORY_PROVENANCE_FIELDS = {
    "corpus_synced_at",
    "corpus_version",
    "effective_date",
    "as_of_status",
}

# These older tools predate the universal envelope contract. Keeping the
# exception list here makes that debt finite: CI rejects new exceptions and
# reports an exception that becomes compliant so it can be removed.
LEGACY_PROVENANCE_EXCEPTIONS = {
    "download_cafc_pdf",
    "download_file_history",
    "download_ilpo_tm",
    "download_inpi_br_bulk",
    "download_ipa_bulk",
    "download_patent_pdf",
    "download_prh_design_image",
    "download_prh_trademark_image",
    "download_ptab_appeal_decisions",
    "download_ptab_interference_decisions",
    "download_ptab_trial_decisions",
    "download_ptab_trial_documents",
    "download_usitc_attachment",
    "download_usitc_investigation_documents",
    "get_bulk_dataset",
    "get_file_history_item",
    "get_forward_citations",
    "get_jpo_documents",
    "get_patent_claims",
    "get_patent_family",
    "get_patent_figures",
    "search_bulk_datasets",
}

CONTRACT_ENV = {
    "CANLII_API_KEY": "contract-check",
    "EUIPO_CLIENT_ID": "contract-check",
    "EUIPO_CLIENT_SECRET": "contract-check",
    "INPI_USERNAME": "contract-check",
    "INPI_PASSWORD": "contract-check",
    "IPAUSTRALIA_CLIENT_ID": "contract-check",
    "IPAUSTRALIA_CLIENT_SECRET": "contract-check",
    "JPO_API_USERNAME": "contract-check",
    "JPO_API_PASSWORD": "contract-check",
    "KIPO_KIPRIS_API_KEY": "contract-check",
    "KIPO_KIPRIS_BASE_URL": "https://kipris.example.test/openapi/service",
    "TIPO_API_KEY": "contract-check",
    "USITC_EDIS_TOKEN": "contract-check",
}


def validate_tools(tools: Iterable[Any]) -> list[str]:
    """Return contract violations for a collection of FastMCP tools."""
    errors = []
    seen = set()
    for tool in tools:
        name = tool.name
        seen.add(name)
        annotations = tool.annotations
        if annotations is None or annotations.readOnlyHint is not True:
            errors.append(f"{name}: readOnlyHint must be true")

        output_schema = tool.output_schema
        provenance_errors = _validate_provenance_schema(name, output_schema)
        if name in LEGACY_PROVENANCE_EXCEPTIONS:
            if not provenance_errors:
                errors.append(f"{name}: now compliant; remove its legacy exception")
            continue
        errors.extend(provenance_errors)
    unknown_exceptions = LEGACY_PROVENANCE_EXCEPTIONS - seen
    for name in sorted(unknown_exceptions):
        errors.append(f"{name}: legacy exception does not match an exposed tool")
    return errors


def validate_tool_sources(
    tools: Iterable[Any],
    server_tools: dict[str, set[str]],
    sources: Iterable[dict[str, Any]],
    groups: Iterable[dict[str, Any]],
) -> list[str]:
    """Return violations in the MCP tool-to-source category manifest."""
    errors: list[str] = []
    exposed = {tool.name for tool in tools}
    active_sources = {
        source["id"]: source for source in sources if source.get("status") in {"active", "beta"}
    }
    sources_by_module: dict[str, list[dict[str, Any]]] = {}
    for source in active_sources.values():
        module = (source.get("connector") or {}).get("module")
        if module:
            sources_by_module.setdefault(module, []).append(source)

    mapped_tools: dict[str, int] = {}
    mapped_source_ids: set[str] = set()
    for index, group in enumerate(groups):
        label = f"tool source group {index + 1}"
        server = group.get("server")
        if server not in server_tools:
            errors.append(f"{label}: unknown MCP server {server!r}")
            continue

        available = server_tools[server]
        names = set(group.get("tools") or available)
        unknown_tools = names - available
        if unknown_tools:
            errors.append(
                f"{label}: tools not exposed by {server}: {', '.join(sorted(unknown_tools))}"
            )
        for name in names & available:
            mapped_tools[name] = mapped_tools.get(name, 0) + 1

        modules = group.get("connector_modules") or []
        resolved_sources = [
            source for module in modules for source in sources_by_module.get(module, [])
        ]
        missing_modules = set(modules) - set(sources_by_module)
        if missing_modules:
            errors.append(
                f"{label}: no active source rows for {', '.join(sorted(missing_modules))}"
            )
        if not resolved_sources:
            errors.append(f"{label}: must resolve at least one active source row")
            continue

        mapped_source_ids.update(source["id"] for source in resolved_sources)
        categories = {source.get("category") for source in resolved_sources}
        if None in categories or "" in categories:
            errors.append(f"{label}: source rows must have non-null categories")
        non_null_categories = {category for category in categories if category}
        if len(non_null_categories) > 1:
            errors.append(
                f"{label}: source rows resolve to multiple categories: "
                f"{', '.join(sorted(non_null_categories))}"
            )

    missing_tools = exposed - set(mapped_tools)
    if missing_tools:
        errors.append(f"unmapped MCP tools: {', '.join(sorted(missing_tools))}")
    duplicate_tools = {name for name, count in mapped_tools.items() if count > 1}
    if duplicate_tools:
        errors.append(f"multiply mapped MCP tools: {', '.join(sorted(duplicate_tools))}")
    unknown_mapped_tools = set(mapped_tools) - exposed
    if unknown_mapped_tools:
        errors.append(
            f"tool source manifest references unshipped tools: "
            f"{', '.join(sorted(unknown_mapped_tools))}"
        )

    missing_sources = set(active_sources) - mapped_source_ids
    if missing_sources:
        errors.append(f"active source rows without MCP tools: {', '.join(sorted(missing_sources))}")
    return errors


def _validate_provenance_schema(name: str, output_schema: Any) -> list[str]:
    """Return provenance-schema violations for one named tool."""
    errors = []
    if not isinstance(output_schema, dict) or output_schema.get("type") != "object":
        return [f"{name}: output schema must be an object"]
    if "provenance" not in output_schema.get("required", []):
        return [f"{name}: output schema must require provenance"]
    provenance = output_schema.get("properties", {}).get("provenance")
    if not isinstance(provenance, dict) or provenance.get("type") != "object":
        return [f"{name}: provenance schema must be an object"]

    declared = set(provenance.get("properties", {}))
    required = set(provenance.get("required", []))
    missing_core = CORE_PROVENANCE_FIELDS - required
    if missing_core:
        errors.append(f"{name}: provenance must require {', '.join(sorted(missing_core))}")
    missing_category = CATEGORY_PROVENANCE_FIELDS - declared
    if missing_category:
        errors.append(f"{name}: provenance must declare {', '.join(sorted(missing_category))}")
    return errors


async def _run() -> int:
    for name, value in CONTRACT_ENV.items():
        os.environ.setdefault(name, value)
    import patent_client_agents.mcp.full as mcp_package

    ip_mcp = mcp_package.ip_mcp

    tools = await ip_mcp.list_tools()
    errors = validate_tools(tools)
    server_tools = {}
    for name, server in vars(mcp_package).items():
        if name.endswith("_mcp") and name != "ip_mcp":
            server_tools[name] = {tool.name for tool in await server.list_tools()}

    sources_document = yaml.safe_load(SOURCES_PATH.read_text())
    tool_sources_document = yaml.safe_load(TOOL_SOURCES_PATH.read_text())
    errors.extend(
        validate_tool_sources(
            tools,
            server_tools,
            sources_document["sources"],
            tool_sources_document["groups"],
        )
    )
    if errors:
        for error in errors:
            print(f"MCP contract violation: {error}", file=sys.stderr)
        return 1
    compliant = len(tools) - len(LEGACY_PROVENANCE_EXCEPTIONS)
    print(
        f"Validated {len(tools)} read-only MCP tools: {compliant} provenance schemas, "
        f"{len(LEGACY_PROVENANCE_EXCEPTIONS)} tracked legacy exceptions, and complete "
        "source-category mappings."
    )
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())

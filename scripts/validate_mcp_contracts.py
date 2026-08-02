#!/usr/bin/env python3
"""Validate read-only and provenance schemas across the exposed MCP surface."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Iterable
from typing import Any

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
    from patent_client_agents.mcp import ip_mcp

    tools = await ip_mcp.list_tools()
    errors = validate_tools(tools)
    if errors:
        for error in errors:
            print(f"MCP contract violation: {error}", file=sys.stderr)
        return 1
    compliant = len(tools) - len(LEGACY_PROVENANCE_EXCEPTIONS)
    print(
        f"Validated {len(tools)} read-only MCP tools: {compliant} provenance schemas, "
        f"{len(LEGACY_PROVENANCE_EXCEPTIONS)} tracked legacy exceptions."
    )
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())

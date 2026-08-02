from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_mcp_contracts.py"
SPEC = importlib.util.spec_from_file_location("validate_mcp_contracts", SCRIPT)
assert SPEC and SPEC.loader
contracts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contracts)


def _tool(
    *,
    name="example",
    read_only=True,
    required=None,
    provenance_required=None,
    provenance_fields=None,
):
    fields = contracts.CORE_PROVENANCE_FIELDS | contracts.CATEGORY_PROVENANCE_FIELDS
    return SimpleNamespace(
        name=name,
        annotations=SimpleNamespace(readOnlyHint=read_only),
        output_schema={
            "type": "object",
            "required": ["provenance"] if required is None else required,
            "properties": {
                "provenance": {
                    "type": "object",
                    "required": (
                        list(contracts.CORE_PROVENANCE_FIELDS)
                        if provenance_required is None
                        else provenance_required
                    ),
                    "properties": {
                        field: {"type": "string"}
                        for field in (fields if provenance_fields is None else provenance_fields)
                    },
                }
            },
        },
    )


def test_validate_tools_accepts_complete_contract():
    contracts.LEGACY_PROVENANCE_EXCEPTIONS = set()
    assert contracts.validate_tools([_tool()]) == []


def test_validate_tools_reports_surface_violations():
    contracts.LEGACY_PROVENANCE_EXCEPTIONS = set()
    tool = _tool(
        read_only=False,
        required=[],
        provenance_required=[],
        provenance_fields=[],
    )

    errors = contracts.validate_tools([tool])

    assert errors == [
        "example: readOnlyHint must be true",
        "example: output schema must require provenance",
    ]


def test_validate_tools_reports_provenance_field_violations():
    contracts.LEGACY_PROVENANCE_EXCEPTIONS = set()
    tool = _tool(provenance_required=[], provenance_fields=[])

    errors = contracts.validate_tools([tool])

    assert errors == [
        "example: provenance must require connector_version, retrieved_at, source_name, source_url",
        "example: provenance must declare as_of_status, corpus_synced_at, corpus_version, effective_date",
    ]


def test_validate_tools_allows_only_tracked_legacy_gaps():
    contracts.LEGACY_PROVENANCE_EXCEPTIONS = {"legacy"}

    assert contracts.validate_tools([_tool(name="legacy", required=[])]) == []


def test_validate_tools_rejects_stale_legacy_exception():
    contracts.LEGACY_PROVENANCE_EXCEPTIONS = {"legacy"}

    assert contracts.validate_tools([_tool(name="legacy")]) == [
        "legacy: now compliant; remove its legacy exception"
    ]


def _source(source_id="US/Example", module="example.module", category="registered_ip"):
    return {
        "id": source_id,
        "status": "active",
        "category": category,
        "connector": {"module": module},
    }


def test_validate_tool_sources_accepts_complete_mapping():
    errors = contracts.validate_tool_sources(
        [_tool()],
        {"example_mcp": {"example"}},
        [_source()],
        [{"server": "example_mcp", "connector_modules": ["example.module"]}],
    )

    assert errors == []


def test_validate_tool_sources_reports_missing_tool_and_source():
    errors = contracts.validate_tool_sources(
        [_tool()],
        {"example_mcp": {"example"}},
        [_source(), _source("US/Orphan", "orphan.module")],
        [],
    )

    assert errors == [
        "unmapped MCP tools: example",
        "active source rows without MCP tools: US/Example, US/Orphan",
    ]


def test_validate_tool_sources_rejects_unknowns_duplicates_and_mixed_categories():
    errors = contracts.validate_tool_sources(
        [_tool()],
        {"example_mcp": {"example"}},
        [
            _source(),
            _source("US/Other", "other.module", "fees"),
        ],
        [
            {
                "server": "example_mcp",
                "tools": ["example", "missing"],
                "connector_modules": ["example.module", "other.module"],
            },
            {
                "server": "example_mcp",
                "connector_modules": ["example.module"],
            },
            {
                "server": "missing_mcp",
                "connector_modules": ["missing.module"],
            },
        ],
    )

    assert errors == [
        "tool source group 1: tools not exposed by example_mcp: missing",
        "tool source group 1: source rows resolve to multiple categories: fees, registered_ip",
        "tool source group 3: unknown MCP server 'missing_mcp'",
        "multiply mapped MCP tools: example",
    ]


def test_validate_tool_sources_rejects_null_category_and_missing_module():
    errors = contracts.validate_tool_sources(
        [_tool()],
        {"example_mcp": {"example"}},
        [_source(category=None)],
        [
            {
                "server": "example_mcp",
                "connector_modules": ["example.module", "missing.module"],
            }
        ],
    )

    assert errors == [
        "tool source group 1: no active source rows for missing.module",
        "tool source group 1: source rows must have non-null categories",
    ]

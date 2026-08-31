#!/usr/bin/env python3
"""Validate the Markdown source catalog and build its human-readable views.

The Markdown records under ``catalog/sources/`` are canonical. Country pages
and ``catalog/worldwide.md`` are generated artifacts.

Usage:
    uv run python scripts/build_source_catalog.py
    uv run python scripts/build_source_catalog.py --check
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "catalog"
SOURCES_DIR = CATALOG_DIR / "sources"
COUNTRIES_DIR = CATALOG_DIR / "countries"
WORLDWIDE_PATH = CATALOG_DIR / "worldwide.md"
COVERAGE_MANIFEST_PATH = ROOT / "coverage" / "sources.yaml"

LITIGATION_CAPABILITIES = (
    "pending_cases",
    "closed_cases",
    "party_search",
    "broad_discovery",
    "exact_case_lookup",
    "docket_events",
    "filed_documents",
    "decisions",
    "patent_identifiers",
)
REGISTERED_IP_CAPABILITIES = (
    "bibliographic",
    "full_text",
    "prosecution",
    "legal_status",
    "assignments",
    "oppositions",
    "classification",
    "bulk_data",
)
SUBSTANTIVE_LAW_CAPABILITIES = (
    "guidelines",
    "case_law",
    "statutes",
    "treaties",
    "full_text_search",
    "citation_lookup",
    "point_in_time",
)
FEE_CAPABILITIES = (
    "current_schedule",
    "effective_date",
    "historical_schedule",
    "machine_readable",
    "calculator",
)
EXTERNAL_CAPABILITIES = ("query_api", "bulk_data")
CATEGORY_CAPABILITIES = {
    "adjudicative_records": LITIGATION_CAPABILITIES,
    "registered_ip": REGISTERED_IP_CAPABILITIES,
    "substantive_law": SUBSTANTIVE_LAW_CAPABILITIES,
    "fees": FEE_CAPABILITIES,
    "external": EXTERNAL_CAPABILITIES,
}
# Backward-compatible name used by focused unit tests and migration helpers.
CAPABILITIES = LITIGATION_CAPABILITIES
CAPABILITY_LABELS = {
    "pending_cases": "Pending cases",
    "closed_cases": "Closed cases",
    "party_search": "Party search",
    "broad_discovery": "Broad discovery",
    "exact_case_lookup": "Exact-case lookup",
    "docket_events": "Docket events",
    "filed_documents": "Filed documents",
    "decisions": "Decisions",
    "patent_identifiers": "Patent identifiers",
    "bibliographic": "Bibliographic data",
    "full_text": "Full text",
    "prosecution": "Prosecution history",
    "legal_status": "Legal status",
    "assignments": "Assignments",
    "oppositions": "Oppositions",
    "classification": "Classification",
    "bulk_data": "Bulk data",
    "guidelines": "Guidelines",
    "case_law": "Case law",
    "statutes": "Statutes",
    "treaties": "Treaties",
    "full_text_search": "Full-text search",
    "citation_lookup": "Citation lookup",
    "point_in_time": "Point-in-time law",
    "current_schedule": "Current schedule",
    "effective_date": "Effective date",
    "historical_schedule": "Historical schedules",
    "machine_readable": "Machine-readable fees",
    "calculator": "Fee calculator",
    "query_api": "Query API",
}
CAPABILITY_VALUES = {"full", "partial", "none", "unknown"}
CAPABILITY_RANK = {"none": 0, "unknown": 1, "partial": 2, "full": 3}

SOURCE_STATUSES = {"active", "retired", "announced", "unverified"}
SOURCE_TYPES = {
    "assignment_database",
    "classification_database",
    "case_list",
    "case_lookup",
    "commercial_database",
    "data_feed",
    "external_dataset",
    "fee_schedule",
    "hearing_calendar",
    "judgment_database",
    "legal_corpus",
    "registry",
}
AVAILABILITIES = {
    "public",
    "credentialed",
    "commercial",
    "parties_only",
    "manual_only",
    "unavailable",
    "unknown",
}
AUDIENCES = {"public", "registered_users", "parties", "subscribers", "institutions"}
FORMATS = {"html", "pdf", "xls", "json", "xml", "csv", "proprietary", "unknown"}
AUTOMATION_POSTURES = {
    "permitted",
    "byok_only",
    "approval_required",
    "contract_required",
    "prohibited",
    "technically_blocked",
    "unclear",
}
CONNECTOR_STATUSES = {"shipped", "candidate", "planned", "blocked", "skipped", "external"}
BLOCKERS = {
    "account_required",
    "captcha",
    "commercial_contract",
    "geofence",
    "identity_verification",
    "license",
    "no_api",
    "parties_only",
    "required_identifiers",
    "tos",
    "unknown",
    "unstable_coverage",
}
RIGHTS = {
    "patent",
    "utility_model",
    "trademark",
    "design",
    "copyright",
    "trade_secret",
    "plant_variety",
    "unfair_competition",
    "gi",
}
CATEGORIES = set(CATEGORY_CAPABILITIES)
REQUIRED_HEADINGS = (
    "What this source contains",
    "Scope limitations",
    "Access and connector assessment",
    "Connector coverage",
    "Known gaps",
    "Evidence",
)
COUNTRY_NAMES = {
    "AU": "Australia",
    "BR": "Brazil",
    "CA": "Canada",
    "CH": "Switzerland",
    "CN": "China",
    "DE": "Germany",
    "EM": "European Union Intellectual Property Office",
    "EP": "European Patent Organisation",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "IL": "Israel",
    "IN": "India",
    "JP": "Japan",
    "KR": "South Korea",
    "NZ": "New Zealand",
    "SE": "Sweden",
    "SG": "Singapore",
    "TH": "Thailand",
    "TR": "Türkiye",
    "TW": "Taiwan",
    "UP": "Unitary Patent",
    "UPC": "Unified Patent Court",
    "US": "United States",
    "WO": "International and worldwide sources",
}
GENERATED_MARKER = "<!-- Generated by scripts/build_source_catalog.py; do not edit. -->"
YAML_GENERATED_MARKER = (
    "# Generated by scripts/build_source_catalog.py from catalog/sources; do not edit."
)
CATEGORY_LABELS = {
    "adjudicative_records": "Litigation and adjudicative records",
    "registered_ip": "Registered IP",
    "substantive_law": "Substantive law",
    "fees": "Fees",
    "external": "External data",
}
CATEGORY_ORDER = tuple(CATEGORY_LABELS)


@dataclass(frozen=True)
class SourceRecord:
    """One canonical Markdown source record."""

    path: Path
    metadata: dict[str, Any]
    body: str

    @property
    def id(self) -> str:
        return str(self.metadata.get("id", ""))

    @property
    def name(self) -> str:
        return str(self.metadata.get("name", self.id))

    @property
    def jurisdictions(self) -> list[str]:
        value = self.metadata.get("jurisdictions")
        return value if isinstance(value, list) else []

    @property
    def connector(self) -> dict[str, Any]:
        value = self.metadata.get("connector")
        return value if isinstance(value, dict) else {}

    @property
    def access(self) -> dict[str, Any]:
        value = self.metadata.get("access")
        return value if isinstance(value, dict) else {}

    @property
    def capabilities(self) -> dict[str, Any]:
        value = self.metadata.get("capabilities")
        return value if isinstance(value, dict) else {}

    @property
    def category(self) -> str:
        return str(self.metadata.get("category", ""))

    @property
    def coverage(self) -> dict[str, Any] | None:
        value = self.metadata.get("coverage")
        return value if isinstance(value, dict) else None


def parse_record(path: Path) -> SourceRecord:
    """Parse YAML frontmatter and Markdown body from one source record."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, flags=re.DOTALL)
    if not match:
        raise ValueError("must start with YAML frontmatter bounded by --- lines")
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter must be a mapping")
    return SourceRecord(path=path, metadata=metadata, body=match.group(2))


def load_records(sources_dir: Path = SOURCES_DIR) -> tuple[list[SourceRecord], list[str]]:
    """Load every canonical record, returning records and parse errors."""
    records: list[SourceRecord] = []
    errors: list[str] = []
    for path in sorted(sources_dir.glob("*/*.md")):
        try:
            records.append(parse_record(path))
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
    return records, errors


def _is_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _date_value(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _check_vocab(
    errors: list[str], field: str, value: Any, vocabulary: set[str], *, multiple: bool = False
) -> None:
    values = value if multiple and isinstance(value, list) else [value]
    if multiple and not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return
    invalid = [item for item in values if item not in vocabulary]
    if invalid:
        errors.append(f"{field} contains invalid value(s): {invalid}")


def validate_record(record: SourceRecord, *, today: dt.date | None = None) -> list[str]:
    """Return schema and content errors for one record."""
    today = today or dt.date.today()
    data = record.metadata
    errors: list[str] = []
    required = {
        "id",
        "name",
        "jurisdictions",
        "institution",
        "source_type",
        "official_url",
        "last_verified",
        "source_status",
        "category",
        "rights",
        "access",
        "capabilities",
        "connector",
    }
    missing = sorted(required.difference(data))
    if missing:
        errors.append(f"missing required field(s): {missing}")

    record_id = data.get("id")
    if not isinstance(record_id, str) or not re.fullmatch(
        r"[A-Z]{2,3}(?:/[A-Za-z0-9_]+)+", record_id
    ):
        errors.append("id must match [A-Z]{2,3}(/segment)+")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name must be non-empty text")

    jurisdictions = data.get("jurisdictions")
    if not isinstance(jurisdictions, list) or not jurisdictions:
        errors.append("jurisdictions must be a non-empty list")
    elif any(
        not isinstance(code, str) or not re.fullmatch(r"[A-Z]{2,3}", code) for code in jurisdictions
    ):
        errors.append("jurisdictions must contain uppercase 2-3 character codes")
    elif len(jurisdictions) != len(set(jurisdictions)):
        errors.append("jurisdictions must not contain duplicates")

    if not _is_url(data.get("official_url")):
        errors.append("official_url must be an HTTP(S) URL")

    verified = _date_value(data.get("last_verified"))
    if verified is None:
        errors.append("last_verified must be an ISO date")
    elif verified > today:
        errors.append("last_verified cannot be in the future")
    elif data.get("source_status") == "active" and (today - verified).days > 365:
        errors.append("active source last_verified is more than 365 days old")

    _check_vocab(errors, "source_status", data.get("source_status"), SOURCE_STATUSES)
    _check_vocab(errors, "source_type", data.get("source_type"), SOURCE_TYPES)
    _check_vocab(errors, "category", data.get("category"), CATEGORIES)
    _check_vocab(errors, "rights", data.get("rights"), RIGHTS, multiple=True)

    access = record.access
    for field in ("availability", "audience", "formats", "automation_posture"):
        if field not in access:
            errors.append(f"access.{field} is required")
    _check_vocab(errors, "access.availability", access.get("availability"), AVAILABILITIES)
    _check_vocab(errors, "access.audience", access.get("audience"), AUDIENCES)
    _check_vocab(errors, "access.formats", access.get("formats"), FORMATS, multiple=True)
    _check_vocab(
        errors,
        "access.automation_posture",
        access.get("automation_posture"),
        AUTOMATION_POSTURES,
    )

    capabilities = record.capabilities
    expected_capabilities = CATEGORY_CAPABILITIES.get(record.category, ())
    missing_capabilities = sorted(set(expected_capabilities).difference(capabilities))
    extra_capabilities = sorted(set(capabilities).difference(expected_capabilities))
    if missing_capabilities:
        errors.append(f"capabilities missing field(s): {missing_capabilities}")
    if extra_capabilities:
        errors.append(f"capabilities contain unknown field(s): {extra_capabilities}")
    for field in expected_capabilities:
        _check_vocab(errors, f"capabilities.{field}", capabilities.get(field), CAPABILITY_VALUES)

    connector = record.connector
    status = connector.get("status")
    _check_vocab(errors, "connector.status", status, CONNECTOR_STATUSES)
    blockers = connector.get("blockers", [])
    _check_vocab(errors, "connector.blockers", blockers, BLOCKERS, multiple=True)
    if status == "shipped":
        module = connector.get("module")
        if not isinstance(module, str) or not module.startswith("patent_client_agents."):
            errors.append("shipped connector requires a patent_client_agents module")
        elif not (ROOT / "src" / Path(*module.split("."))).exists():
            errors.append(f"connector.module does not resolve in src/: {module}")
        if blockers:
            errors.append("shipped connector cannot declare blockers")
    elif connector.get("module") is not None:
        errors.append("only shipped connectors may declare connector.module")
    if status == "blocked" and not blockers:
        errors.append("blocked connector requires at least one blocker")

    headings = re.findall(r"^## (.+)$", record.body, flags=re.MULTILINE)
    for heading in REQUIRED_HEADINGS:
        if heading not in headings:
            errors.append(f"missing Markdown heading: ## {heading}")
    evidence = re.search(
        r"^## Evidence\s*\n(.*?)(?=^## |\Z)", record.body, re.MULTILINE | re.DOTALL
    )
    if evidence and not re.search(r"\[[^]]+\]\(https?://[^)]+\)", evidence.group(1)):
        errors.append("Evidence section must contain at least one HTTP(S) Markdown link")

    coverage = record.coverage
    if coverage is not None:
        if record.connector.get("status") != "shipped":
            errors.append("coverage-backed record requires connector.status=shipped")
        if not record.connector.get("module"):
            errors.append("coverage-backed record requires connector.module")
        order = coverage.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 0:
            errors.append("coverage.order must be a non-negative integer")
        if len(record.jurisdictions) != 1 and not coverage.get("jurisdiction"):
            errors.append("multi-jurisdiction coverage record requires coverage.jurisdiction")
        for field in ("data_types", "access", "status"):
            if field not in coverage:
                errors.append(f"coverage.{field} is required")
        if not isinstance(coverage.get("data_types"), list):
            errors.append("coverage.data_types must be a list")
        if not isinstance(coverage.get("access"), dict):
            errors.append("coverage.access must be a mapping")
    return errors


def validate_catalog(
    records: list[SourceRecord], parse_errors: list[str] | None = None
) -> list[str]:
    """Return all catalog errors with source paths attached."""
    errors = list(parse_errors or [])
    seen: dict[str, Path] = {}
    coverage_orders: dict[int, Path] = {}
    for record in records:
        prefix = str(record.path.relative_to(ROOT))
        for error in validate_record(record):
            errors.append(f"{prefix}: {error}")
        if record.id in seen:
            errors.append(f"{prefix}: duplicate id {record.id!r} (also in {seen[record.id]})")
        else:
            seen[record.id] = record.path
        if (
            record.coverage is not None
            and isinstance(record.coverage.get("order"), int)
            and not isinstance(record.coverage.get("order"), bool)
        ):
            order = record.coverage["order"]
            if order in coverage_orders:
                errors.append(
                    f"{prefix}: duplicate coverage.order {order} "
                    f"(also in {coverage_orders[order].relative_to(ROOT)})"
                )
            else:
                coverage_orders[order] = record.path
    if not records:
        errors.append("catalog/sources contains no source records")
    if coverage_orders:
        expected_orders = set(range(len(coverage_orders)))
        missing_orders = sorted(expected_orders.difference(coverage_orders))
        unexpected_orders = sorted(set(coverage_orders).difference(expected_orders))
        if missing_orders or unexpected_orders:
            errors.append(
                "catalog/sources: coverage.order values must be contiguous from zero "
                f"(missing={missing_orders}, unexpected={unexpected_orders})"
            )
    return errors


def build_coverage_source(record: SourceRecord) -> dict[str, Any] | None:
    """Project one canonical record into the legacy coverage-row contract."""
    coverage = record.coverage
    if coverage is None:
        return None
    jurisdiction = coverage.get("jurisdiction") or record.jurisdictions[0]
    projected: dict[str, Any] = {
        "id": record.id,
        "name": coverage.get("name", record.name),
        "jurisdiction": jurisdiction,
    }
    if coverage.get("wipo_st3_code") is not None:
        projected["wipo_st3_code"] = coverage["wipo_st3_code"]
    projected.update(
        {
            "issuing_body": coverage.get("issuing_body", record.metadata["institution"]),
            "rights": coverage.get("rights", record.metadata["rights"]),
            "data_types": coverage["data_types"],
            "access": coverage["access"],
            "status": coverage["status"],
        }
    )
    module = record.connector.get("module")
    if module:
        projected["connector"] = {"module": module}
    last_verified = (
        coverage["last_verified"]
        if "last_verified" in coverage
        else record.metadata.get("last_verified")
    )
    if last_verified is not None:
        projected["last_verified"] = last_verified
    for field in (
        "category",
        "transport",
        "update_strategy",
        "update_cadence",
        "last_synced",
        "corpus_version",
        "notes",
    ):
        if coverage.get(field) is not None:
            projected[field] = coverage[field]
    return projected


def build_coverage_sources(records: list[SourceRecord]) -> list[dict[str, Any]]:
    """Project all manifest-backed records in their compatibility order."""
    included = [record for record in records if record.coverage is not None]
    included.sort(key=lambda record: record.coverage["order"] if record.coverage else -1)
    return [projected for record in included if (projected := build_coverage_source(record))]


class _CatalogDumper(yaml.SafeDumper):
    """Readable YAML: compact scalar lists and literal multiline notes."""


def _represent_catalog_list(dumper: _CatalogDumper, value: list[Any]) -> yaml.Node:
    node = dumper.represent_list(value)
    if all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
        node.flow_style = True
    return node


def _represent_catalog_string(dumper: _CatalogDumper, value: str) -> yaml.Node:
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str", value, style="|" if "\n" in value else None
    )


_CatalogDumper.add_representer(list, _represent_catalog_list)
_CatalogDumper.add_representer(str, _represent_catalog_string)


def render_coverage_manifest(records: list[SourceRecord]) -> str:
    """Render the generated compatibility YAML manifest."""
    payload = {"sources": build_coverage_sources(records)}
    dumped = yaml.dump(
        payload,
        Dumper=_CatalogDumper,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    return f"{YAML_GENERATED_MARKER}\n{dumped}"


def catalog_group(record: SourceRecord) -> str:
    """Place a source in one exclusive country-page section."""
    status = record.connector.get("status")
    availability = record.access.get("availability")
    posture = record.access.get("automation_posture")
    if status == "shipped":
        return "Connected sources"
    if availability == "commercial":
        return "Commercial sources"
    if status in {"candidate", "planned"}:
        return "Connectable sources not yet built"
    if availability in {"credentialed", "parties_only", "manual_only"}:
        return "Manual or restricted sources"
    if availability == "unavailable" or posture in {"prohibited", "technically_blocked"}:
        return "Unavailable sources"
    return "Manual or restricted sources"


def best_capability(records: list[SourceRecord], capability: str) -> tuple[str, list[SourceRecord]]:
    """Return the best cataloged grade and records providing it."""
    if not records:
        return "none", []
    best = max(
        (str(record.capabilities.get(capability, "unknown")) for record in records),
        key=CAPABILITY_RANK.__getitem__,
    )
    return best, [record for record in records if record.capabilities.get(capability) == best]


def _source_link(record: SourceRecord, output_dir: Path) -> str:
    relative = Path(os.path.relpath(record.path, output_dir)).as_posix()
    return f"[{record.name}]({relative})"


def _source_table(records: list[SourceRecord], output_dir: Path) -> list[str]:
    if not records:
        return ["No sources are currently cataloged in this category.", ""]
    lines = [
        "| Source | Category | Type | Access | Automation | Connector |",
        "|---|---|---|---|---|---|",
    ]
    for record in sorted(records, key=lambda item: (item.name.casefold(), item.id)):
        lines.append(
            "| "
            + " | ".join(
                (
                    _source_link(record, output_dir),
                    CATEGORY_LABELS[record.category],
                    str(record.metadata["source_type"]),
                    str(record.access["availability"]),
                    str(record.access["automation_posture"]),
                    str(record.connector["status"]),
                )
            )
            + " |"
        )
    return [*lines, ""]


def render_country(code: str, records: list[SourceRecord]) -> str:
    """Render one generated jurisdiction summary."""
    output_path = COUNTRIES_DIR / f"{code.lower()}.md"
    country = COUNTRY_NAMES.get(code, code)
    lines = [
        GENERATED_MARKER,
        "",
        f"# {country} ({code}) source catalog",
        "",
        "This page summarizes the canonical source records for this jurisdiction. Capability",
        "grades describe the upstream source, not merely the connector we have built.",
        "",
        "## Inventory at a glance",
        "",
        "| Category | Sources | Connected |",
        "|---|---:|---:|",
    ]
    categories = [
        category for category in CATEGORY_ORDER if any(r.category == category for r in records)
    ]
    for category in categories:
        category_records = [record for record in records if record.category == category]
        connected_count = sum(
            record.connector.get("status") == "shipped" for record in category_records
        )
        lines.append(
            f"| {CATEGORY_LABELS[category]} | {len(category_records)} | {connected_count} |"
        )
    lines.append("")

    for category in categories:
        category_records = [record for record in records if record.category == category]
        connected_records = [
            record for record in category_records if record.connector.get("status") == "shipped"
        ]
        lines.extend((f"## {CATEGORY_LABELS[category]} capabilities", ""))
        lines.extend(
            (
                "| Capability | Best source coverage | Connected coverage | Best source(s) |",
                "|---|---|---|---|",
            )
        )
        for capability in CATEGORY_CAPABILITIES[category]:
            grade, providers = best_capability(category_records, capability)
            connected_grade, _ = best_capability(connected_records, capability)
            links = ", ".join(_source_link(record, output_path.parent) for record in providers)
            lines.append(
                f"| {CAPABILITY_LABELS[capability]} | {grade} | {connected_grade} | {links} |"
            )
        lines.append("")

    groups = (
        "Connected sources",
        "Connectable sources not yet built",
        "Manual or restricted sources",
        "Commercial sources",
        "Unavailable sources",
    )
    for group in groups:
        lines.extend((f"## {group}", ""))
        lines.extend(
            _source_table(
                [record for record in records if catalog_group(record) == group], output_path.parent
            )
        )

    lines.extend(("## Known coverage gaps", ""))
    lines.append(
        "- **Jurisdiction scope:** capability grades apply within each source's stated scope; "
        "they do not establish comprehensive jurisdiction-wide coverage."
    )
    lines.append(
        "- **Capability confidence:** mechanically migrated `partial` grades preserve the "
        "legacy manifest's positive coverage claim without asserting completeness."
    )
    lines.extend(("", "See each source record for scope limitations and supporting evidence.", ""))
    return "\n".join(lines)


def render_worldwide(records: list[SourceRecord]) -> str:
    """Render the cross-jurisdiction matrix."""
    codes = sorted({code for record in records for code in record.jurisdictions})
    selected = (
        "pending_cases",
        "party_search",
        "exact_case_lookup",
        "docket_events",
        "filed_documents",
        "decisions",
        "patent_identifiers",
    )
    lines = [
        GENERATED_MARKER,
        "",
        "# Worldwide source catalog",
        "",
        "This inventory includes connected, connectable, restricted, commercial, and blocked",
        "sources. Counts do not imply comprehensive jurisdiction-wide coverage.",
        "",
        "## Inventory by jurisdiction",
        "",
        "| Jurisdiction | Sources | Connected | Registered IP | Litigation | Substantive law | Fees | External |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for code in codes:
        country_records = [record for record in records if code in record.jurisdictions]
        country_link = f"[{COUNTRY_NAMES.get(code, code)} ({code})](countries/{code.lower()}.md)"
        counts = {
            category: sum(record.category == category for record in country_records)
            for category in CATEGORY_ORDER
        }
        connected_count = sum(
            record.connector.get("status") == "shipped" for record in country_records
        )
        lines.append(
            f"| {country_link} | {len(country_records)} | {connected_count} | "
            f"{counts['registered_ip']} | {counts['adjudicative_records']} | "
            f"{counts['substantive_law']} | {counts['fees']} | {counts['external']} |"
        )

    litigation_codes = sorted(
        {
            code
            for record in records
            if record.category == "adjudicative_records"
            for code in record.jurisdictions
        }
    )
    lines.extend(
        (
            "",
            "## Litigation and adjudicative capabilities",
            "",
            "Each cell shows best cataloged coverage followed by best connected coverage.",
            "",
            "| Jurisdiction | Sources | "
            + " | ".join(CAPABILITY_LABELS[item] for item in selected)
            + " |",
            "|---|---:|" + "---|" * len(selected),
        )
    )
    for code in litigation_codes:
        country_records = [
            record
            for record in records
            if code in record.jurisdictions and record.category == "adjudicative_records"
        ]
        connected = [
            record for record in country_records if record.connector.get("status") == "shipped"
        ]
        grades = [
            f"{best_capability(country_records, capability)[0]} / "
            f"{best_capability(connected, capability)[0]}"
            for capability in selected
        ]
        country_link = f"[{COUNTRY_NAMES.get(code, code)} ({code})](countries/{code.lower()}.md)"
        lines.append(f"| {country_link} | {len(country_records)} | " + " | ".join(grades) + " |")
    lines.extend(("", "Canonical records live under [`catalog/sources/`](sources/).", ""))
    return "\n".join(lines)


def build_outputs(records: list[SourceRecord]) -> dict[Path, str]:
    """Return every generated output and its expected content."""
    codes = sorted({code for record in records for code in record.jurisdictions})
    outputs = {
        COUNTRIES_DIR / f"{code.lower()}.md": render_country(
            code, [record for record in records if code in record.jurisdictions]
        )
        for code in codes
    }
    outputs[WORLDWIDE_PATH] = render_worldwide(records)
    outputs[COVERAGE_MANIFEST_PATH] = render_coverage_manifest(records)
    return outputs


def _check_outputs(outputs: dict[Path, str]) -> list[str]:
    errors = []
    for path, expected in outputs.items():
        if not path.exists():
            errors.append(f"missing generated file: {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != expected:
            errors.append(f"generated file is stale: {path.relative_to(ROOT)}")
    expected_country_paths = {path for path in outputs if path.parent == COUNTRIES_DIR}
    for path in COUNTRIES_DIR.glob("*.md"):
        if path not in expected_country_paths:
            errors.append(f"unexpected generated country file: {path.relative_to(ROOT)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate records and generated files")
    args = parser.parse_args(argv)

    records, parse_errors = load_records()
    errors = validate_catalog(records, parse_errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    outputs = build_outputs(records)
    if args.check:
        errors = _check_outputs(outputs)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Source catalog valid: {len(records)} records, {len(outputs)} generated views.")
        return 0

    COUNTRIES_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
    print(f"Built {len(outputs)} views from {len(records)} source records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

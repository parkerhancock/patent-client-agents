#!/usr/bin/env python3
"""Build ``coverage/coverage.json`` from ``coverage/sources.yaml``.

The YAML is the human-edited source of truth; the JSON is the build
artifact the public coverage page fetches at runtime.

Validates against closed vocabularies, computes rollup stats, and
writes a JSON document shaped for the matrix/map UI.

Exit 0 on success, non-zero on any validation failure.

Usage:
    uv run python scripts/build_coverage.py
    uv run python scripts/build_coverage.py --check  # validate, don't write
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES_YAML = ROOT / "coverage" / "sources.yaml"
COVERAGE_JSON = ROOT / "coverage" / "coverage.json"
STATE_YAML = ROOT / "research" / "STATE.yaml"
ATLAS_JSON = ROOT / "coverage" / "atlas.json"

DOCS_BASE_URL = "https://docs.patentclient.com/patent-client-index"
GITHUB_RESEARCH_URL = "https://github.com/parkerhancock/patent-client-agents/blob/main/research"

# Rating vocabulary. Mirrored in docs_hooks/sync_patent_client_index.py —
# keep both in sync until lifted into a shared module.
# (emoji, short_label, one-line description used as fallback basis.)
RATING_LABELS: dict[str, tuple[str, str, str]] = {
    "green": ("🟢", "Green", "Live API, queryable, ToS-clean."),
    "yellow_byok": (
        "🟡",
        "Yellow — BYOK",
        "Live API, per-user keys required (ToS forbids shared-key proxy).",
    ),
    "yellow_paid": (
        "🟡",
        "Yellow — Paid",
        "Programmatic access only behind a paid contract or subscription.",
    ),
    "red_tos": ("🔴", "Red — ToS", "Terms of use prohibit programmatic / automated access."),
    "red_no_api": (
        "🔴",
        "Red — No API",
        "No queryable API surface; HTML-only or bulk-dump access.",
    ),
    "red_bulk_only": ("🔴", "Red — Bulk only", "Bulk download exists but no per-query API."),
    "red_contract": ("🔴", "Red — Contract", "Access requires a paper / wet-signature contract."),
    "red_blocked": (
        "🔴",
        "Red — Blocked",
        "Access path exists but is currently blocked (egress filter, geofence, etc.).",
    ),
    "green_transitive": (
        "🟢",
        "Green — Transitive",
        "No native API; covered transitively via a regional or higher-layer connector we already operate.",
    ),
    "watch": ("⚪", "Watch", "Monitoring for changes; no decision yet."),
    "tbd": ("⚪", "TBD", "Research pending."),
}

# ISO 3166-1 alpha-2 → UN M.49 macro-region bucket. Limited to the
# countries that appear in research/STATE.yaml; extend as we add entities.
ISO_TO_REGION: dict[str, str] = {
    # Americas
    "US": "americas",
    "CA": "americas",
    "MX": "americas",
    "BR": "americas",
    "AR": "americas",
    # Europe
    "DE": "europe",
    "GB": "europe",
    "FR": "europe",
    "CH": "europe",
    "NL": "europe",
    "SE": "europe",
    "FI": "europe",
    "AT": "europe",
    "ES": "europe",
    "IT": "europe",
    "RU": "europe",
    # Asia
    "JP": "asia",
    "KR": "asia",
    "CN": "asia",
    "IN": "asia",
    "TW": "asia",
    "SG": "asia",
    "ID": "asia",
    "TH": "asia",
    "PH": "asia",
    "AE": "asia",
    "SA": "asia",
    "IL": "asia",
    "TR": "asia",
    # Oceania
    "AU": "oceania",
    "NZ": "oceania",
    # Africa — surveyed nationals
    "ZA": "africa",
    "EG": "africa",
    "NG": "africa",
    "MA": "africa",
    # Africa — ARIPO members (22; transitively covered via EPO OPS country code AP)
    "BW": "africa",  # Botswana
    "CV": "africa",  # Cabo Verde
    "SZ": "africa",  # eSwatini
    "GM": "africa",  # Gambia
    "GH": "africa",  # Ghana
    "KE": "africa",  # Kenya
    "LS": "africa",  # Lesotho
    "LR": "africa",  # Liberia
    "MW": "africa",  # Malawi
    "MU": "africa",  # Mauritius
    "MZ": "africa",  # Mozambique
    "NA": "africa",  # Namibia
    "RW": "africa",  # Rwanda
    "ST": "africa",  # São Tomé and Príncipe
    "SC": "africa",  # Seychelles
    "SL": "africa",  # Sierra Leone
    "SO": "africa",  # Somalia
    "SD": "africa",  # Sudan
    "TZ": "africa",  # Tanzania (mainland)
    "UG": "africa",  # Uganda
    "ZM": "africa",  # Zambia
    "ZW": "africa",  # Zimbabwe
    # Africa — OAPI members (17; transitively covered via EPO OPS country code OA)
    "BJ": "africa",  # Benin
    "BF": "africa",  # Burkina Faso
    "CM": "africa",  # Cameroon
    "CF": "africa",  # Central African Republic
    "TD": "africa",  # Chad
    "KM": "africa",  # Comoros
    "CG": "africa",  # Republic of Congo
    "CI": "africa",  # Côte d'Ivoire
    "GQ": "africa",  # Equatorial Guinea
    "GA": "africa",  # Gabon
    "GN": "africa",  # Guinea
    "GW": "africa",  # Guinea-Bissau
    "ML": "africa",  # Mali
    "MR": "africa",  # Mauritania
    "NE": "africa",  # Niger
    "SN": "africa",  # Senegal
    "TG": "africa",  # Togo
}

RIGHTS = {"patent", "trademark", "design", "copyright", "plant_variety", "gi", "trade_secret"}
DATA_TYPES = {
    "bibliographic",
    "full_text",
    "prosecution",
    "legal_status",
    "assignments",
    "oppositions",
    "tribunal_proceedings",
    "litigation",
    "classification",
    "guidelines",
    "case_law",
    "statutes",
    "treaties",
    "bulk_data",
    "fees",
}
ACCESS_METHODS = {
    "rest_api",
    "bulk_download",
    "website_scrape",
    "pdf_download",
    "ftp",
    "mcp_passthrough",
}
AUTH_KINDS = {
    "none",
    "api_key",
    "oauth2_client_credentials",
    "oauth2_password",
    "cookie_token",
    "account_required",
}
STATUSES = {"active", "beta", "planned", "candidate", "blocked", "external", "deprecated"}

# CONNECTOR_STANDARDS.md §6 closed vocabularies.
CATEGORIES = {"registered_ip", "substantive_law"}
TRANSPORTS = {"mcp_proxy", "mcp_local"}
UPDATE_STRATEGIES = {"live_proxy", "scheduled_recrawl", "vendor_changefeed", "manual"}
UPDATE_CADENCES = {"weekly", "monthly", "quarterly", "semiannual", "annual", "irregular"}

# CONNECTOR_STANDARDS.md §6 check #5: maps update_cadence → days.
# A category-2 entry whose update_strategy is scheduled_recrawl or
# vendor_changefeed fails CI if `last_synced` is older than
# 2 × the value below. `irregular` skips the staleness check.
CADENCE_DAYS = {
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "semiannual": 180,
    "annual": 365,
    "irregular": None,
}

# Per-status freshness expectations. last_verified must be within N days.
FRESHNESS_DAYS = {"active": 365, "beta": 365}

# Regional + ISO codes accepted in jurisdiction. We don't validate against the
# full ISO 3166 list; we just sanity-check shape.
JURIS_REGEX = re.compile(r"^([A-Z]{2}|UPC|UP)$")

# WIPO Standard ST.3 — two- or three-character codes for IP-issuing
# entities. We accept the ISO 3166-1 alpha-2 codes and the regional
# codes ST.3 carves out (EP, WO, EM, AP, OA, EA, GC, BX), plus UP and
# UPC which are post-ST.3 additions specific to the Unitary Patent
# system that we treat as first-class jurisdictions.
ST3_REGEX = re.compile(r"^([A-Z]{2}|EP|WO|EM|AP|OA|EA|GC|BX|UP|UPC)$")

ID_REGEX = re.compile(r"^[A-Z]{2,3}(/[A-Za-z0-9_]+)+$")


def fail(errors: list[str], path: str, message: str) -> None:
    errors.append(f"{path}: {message}")


def warn(warnings: list[str], path: str, message: str) -> None:
    warnings.append(f"{path}: {message}")


def validate_source(
    source: dict[str, Any],
    idx: int,
    errors: list[str],
    warnings: list[str],
) -> None:
    sid = source.get("id", f"<index {idx}>")
    path = f"sources[{idx}] {sid}"

    for required in (
        "id",
        "name",
        "jurisdiction",
        "issuing_body",
        "rights",
        "data_types",
        "access",
        "status",
    ):
        if required not in source:
            fail(errors, path, f"missing required key: {required}")

    if "id" in source and not ID_REGEX.match(source["id"]):
        fail(errors, path, f"id {source['id']!r} must match {ID_REGEX.pattern}")

    if "jurisdiction" in source and not JURIS_REGEX.match(source["jurisdiction"]):
        fail(errors, path, f"jurisdiction {source['jurisdiction']!r} must be ISO-2 or UPC/UP")

    if "wipo_st3_code" in source and not ST3_REGEX.match(source["wipo_st3_code"]):
        fail(
            errors,
            path,
            f"wipo_st3_code {source['wipo_st3_code']!r} must match WIPO Standard ST.3 codes "
            f"({ST3_REGEX.pattern})",
        )

    rights = source.get("rights") or []
    for r in rights:
        if r not in RIGHTS:
            fail(errors, path, f"rights entry {r!r} not in {sorted(RIGHTS)}")

    for dt_ in source.get("data_types") or []:
        if dt_ not in DATA_TYPES:
            fail(errors, path, f"data_types entry {dt_!r} not in {sorted(DATA_TYPES)}")

    access = source.get("access") or {}
    if access.get("method") and access["method"] not in ACCESS_METHODS:
        fail(errors, path, f"access.method {access['method']!r} not in {sorted(ACCESS_METHODS)}")
    if access.get("auth") and access["auth"] not in AUTH_KINDS:
        fail(errors, path, f"access.auth {access['auth']!r} not in {sorted(AUTH_KINDS)}")

    status = source.get("status")
    if status and status not in STATUSES:
        fail(errors, path, f"status {status!r} not in {sorted(STATUSES)}")

    if status in {"blocked", "deprecated", "candidate", "external"} and not source.get("notes"):
        fail(errors, path, f"status={status!r} requires a notes field explaining the rationale")

    if status in {"active", "beta"}:
        connector = source.get("connector") or {}
        module = connector.get("module")
        if not module:
            fail(errors, path, "active/beta source requires connector.module")
        else:
            module_path = ROOT / "src" / module.replace(".", "/")
            if not (
                module_path.exists() or (module_path.parent / f"{module_path.name}.py").exists()
            ):
                fail(
                    errors, path, f"connector.module {module!r} does not import (no {module_path})"
                )

        last_verified = source.get("last_verified")
        if not last_verified:
            fail(errors, path, f"status={status!r} requires last_verified")
        elif isinstance(last_verified, dt.date):
            age = (dt.date.today() - last_verified).days
            if age > FRESHNESS_DAYS[status]:
                fail(
                    errors,
                    path,
                    f"last_verified {last_verified} is {age}d old (limit {FRESHNESS_DAYS[status]}d)",
                )
        else:
            fail(
                errors,
                path,
                f"last_verified must be a YAML date (got {type(last_verified).__name__})",
            )

        # ── CONNECTOR_STANDARDS.md §6 checks ────────────────────────────

        # Check #1: every active/beta entry has `category`.
        category = source.get("category")
        if not category:
            fail(
                errors,
                path,
                "status=active/beta requires category (registered_ip or substantive_law)",
            )
        elif category not in CATEGORIES:
            fail(errors, path, f"category {category!r} not in {sorted(CATEGORIES)}")

        # Check #2: every active/beta entry has `transport`.
        transport = source.get("transport")
        if not transport:
            fail(errors, path, "status=active/beta requires transport (mcp_proxy or mcp_local)")
        elif transport not in TRANSPORTS:
            fail(errors, path, f"transport {transport!r} not in {sorted(TRANSPORTS)}")

        # Check #3: transport=mcp_local + category=substantive_law requires the
        # connector module to expose a `get_corpus_status()` callable. As of
        # the row-18 rollout (TMEP, EPC, EPO Guidelines, EPO Case Law, PCT
        # Guidelines, EPO UP Guidelines, UKIPO MoPP, UPC Statutes — plus
        # MPEP from row 17), all category-2 mcp_local connectors expose
        # the callable, so this is now a hard error. Skip for
        # category=registered_ip entries (they don't owe the surface).
        if transport == "mcp_local" and category == "substantive_law" and module:
            try:
                imported = importlib.import_module(module)
            except Exception as exc:  # noqa: BLE001 — surface any import failure clearly
                fail(
                    errors,
                    path,
                    f"transport=mcp_local: could not import {module!r} to check "
                    f"for get_corpus_status() ({type(exc).__name__}: {exc})",
                )
            else:
                if not callable(getattr(imported, "get_corpus_status", None)):
                    fail(
                        errors,
                        path,
                        f"transport=mcp_local: connector {module!r} must expose a "
                        f"get_corpus_status() callable (CONNECTOR_STANDARDS.md §4)",
                    )

        # Checks #4–6 apply only to category-2 entries.
        if category == "substantive_law":
            update_strategy = source.get("update_strategy")
            update_cadence = source.get("update_cadence")

            # Check #4: update_strategy + update_cadence required.
            if not update_strategy:
                fail(errors, path, "category=substantive_law active/beta requires update_strategy")
            elif update_strategy not in UPDATE_STRATEGIES:
                fail(
                    errors,
                    path,
                    f"update_strategy {update_strategy!r} not in {sorted(UPDATE_STRATEGIES)}",
                )
            if not update_cadence:
                fail(errors, path, "category=substantive_law active/beta requires update_cadence")
            elif update_cadence not in UPDATE_CADENCES:
                fail(
                    errors,
                    path,
                    f"update_cadence {update_cadence!r} not in {sorted(UPDATE_CADENCES)}",
                )

            # transport=mcp_local additionally requires last_synced + corpus_version.
            last_synced = source.get("last_synced")
            corpus_version = source.get("corpus_version")
            if transport == "mcp_local":
                if not last_synced:
                    fail(
                        errors,
                        path,
                        "category=substantive_law + transport=mcp_local requires last_synced",
                    )
                elif not isinstance(last_synced, dt.date):
                    fail(
                        errors,
                        path,
                        f"last_synced must be a YAML date (got {type(last_synced).__name__})",
                    )
                if not corpus_version:
                    fail(
                        errors,
                        path,
                        "category=substantive_law + transport=mcp_local requires corpus_version",
                    )

            # Check #5: scheduled_recrawl / vendor_changefeed staleness gate.
            if (
                update_strategy in {"scheduled_recrawl", "vendor_changefeed"}
                and isinstance(last_synced, dt.date)
                and update_cadence in CADENCE_DAYS
                and CADENCE_DAYS[update_cadence] is not None
            ):
                limit = 2 * CADENCE_DAYS[update_cadence]
                age = (dt.date.today() - last_synced).days
                if age > limit:
                    fail(
                        errors,
                        path,
                        f"last_synced {last_synced} is {age}d old; update_strategy="
                        f"{update_strategy!r} with update_cadence={update_cadence!r} caps at "
                        f"{limit}d (2 × cadence)",
                    )

            # Check #6: update_strategy=manual emits a warning every CI run.
            if update_strategy == "manual":
                warn(
                    warnings,
                    path,
                    "update_strategy=manual: re-sync or re-classify (CONNECTOR_STANDARDS.md §6 check #6)",
                )


# Top 30 patent offices by 2023 annual filing volume, per WIPO IP
# Statistics Data Center / WIPI 2024. Sourced from WIPO published
# figures (https://www.wipo.int/ipstats/en/). Used to compute a
# "top-N covered" metric on the coverage page.
TOP30_FILING_VOLUME = [
    "CN",
    "US",
    "JP",
    "KR",
    "DE",
    "IN",
    "BR",
    "CA",
    "AU",
    "MX",
    "RU",
    "GB",
    "FR",
    "IT",
    "ES",
    "SE",
    "NL",
    "CH",
    "BE",
    "PL",
    "DK",
    "TW",
    "SG",
    "HK",
    "TH",
    "MY",
    "PH",
    "VN",
    "ID",
    "KH",
]


def compute_summary(sources: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    jurisdictions: set[str] = set()
    tracked_jurisdictions: set[str] = set()
    rights_covered: set[str] = set()
    data_types_covered: set[str] = set()

    for s in sources:
        status = s.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        tracked_jurisdictions.add(s["jurisdiction"])
        if s.get("status") in {"active", "beta"}:
            jurisdictions.add(s["jurisdiction"])
            for r in s.get("rights") or []:
                rights_covered.add(r)
            for d in s.get("data_types") or []:
                data_types_covered.add(d)

    # Top-30 patent offices by 2023 filing volume — count those for
    # which we have at least one entry in any status (active, beta,
    # candidate, blocked, external). A `candidate` row still counts as
    # "tracked"; only a complete absence is a real gap.
    top30_tracked = [c for c in TOP30_FILING_VOLUME if c in tracked_jurisdictions]

    return {
        "total": len(sources),
        "by_status": by_status,
        "active_jurisdictions": sorted(jurisdictions),
        "rights_covered": sorted(rights_covered),
        "data_types_covered": sorted(data_types_covered),
        "top30_filing_volume": {
            "list": TOP30_FILING_VOLUME,
            "tracked": top30_tracked,
            "missing": [c for c in TOP30_FILING_VOLUME if c not in tracked_jurisdictions],
            "tracked_count": len(top30_tracked),
            "total": len(TOP30_FILING_VOLUME),
            "source": "WIPO IP Statistics Data Center (https://www.wipo.int/ipstats/en/), WIPI 2024 report, 2023 filing data",
        },
    }


def build_matrix(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-jurisdiction × rights cells, ready for the matrix UI.

    Each cell records the strongest status among sources touching that
    (jurisdiction, right) pair, plus the source IDs underneath.
    """
    status_rank = {
        "active": 5,
        "beta": 4,
        "planned": 3,
        "candidate": 2,
        "blocked": 1,
        "external": 1,
        "deprecated": 0,
    }

    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for s in sources:
        juris = s["jurisdiction"]
        for right in s.get("rights") or []:
            key = (juris, right)
            entry = cells.setdefault(
                key,
                {
                    "jurisdiction": juris,
                    "right": right,
                    "status": s["status"],
                    "sources": [],
                },
            )
            entry["sources"].append(s["id"])
            if status_rank.get(s["status"], -1) > status_rank.get(entry["status"], -1):
                entry["status"] = s["status"]

    return sorted(cells.values(), key=lambda c: (c["jurisdiction"], c["right"]))


def serialize(obj: Any) -> Any:
    if isinstance(obj, dt.date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize(v) for v in obj]
    return obj


# ─── atlas.json — office-centric fusion of STATE.yaml + sources.yaml ────


def _source_matches_entity(source_id: str, entity_id: str) -> bool:
    """``US/USPTO/ODP/Applications`` matches entity ``US/USPTO``."""
    return source_id == entity_id or source_id.startswith(entity_id + "/")


def _region_for(entity: dict[str, Any]) -> str:
    layer = entity.get("layer", "")
    if layer == "multilateral":
        return "multilateral"
    if layer == "regional":
        return "regional"
    iso = entity.get("iso2") or ""
    return ISO_TO_REGION.get(iso, "other")


def _synopsis_url(entity: dict[str, Any]) -> str | None:
    syn = entity.get("synopsis")
    if not syn:
        return None
    # ``national/kr-kipo.md`` → ``https://docs.../national/kr-kipo/``
    slug = syn.replace(".md", "").lstrip("/")
    return f"{DOCS_BASE_URL}/{slug}/"


def _github_research_url(entity: dict[str, Any]) -> str | None:
    syn = entity.get("synopsis")
    if not syn:
        return None
    return f"{GITHUB_RESEARCH_URL}/{syn.lstrip('/')}"


def build_atlas_entities(
    sources: list[dict[str, Any]],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    state_entities = state.get("entities", [])
    # Match sources to entities longest-prefix first so e.g.
    # ``US/USPTO/ODP/Applications`` binds to ``US/USPTO`` rather than ``US``.
    entity_ids_sorted = sorted((e.get("id", "") for e in state_entities), key=len, reverse=True)
    sources_by_entity: dict[str, list[dict[str, Any]]] = {eid: [] for eid in entity_ids_sorted}
    for src in sources:
        sid = src.get("id", "")
        for eid in entity_ids_sorted:
            if eid and _source_matches_entity(sid, eid):
                sources_by_entity[eid].append(src)
                break

    out: list[dict[str, Any]] = []
    for entity in state_entities:
        eid = entity.get("id", "")
        rating_code = entity.get("rating", "tbd")
        emoji, label, default_basis = RATING_LABELS.get(rating_code, RATING_LABELS["tbd"])
        basis = entity.get("rating_basis", "").strip() or default_basis
        out.append(
            {
                "id": eid,
                "name": entity.get("name", ""),
                "layer": entity.get("layer", ""),
                "iso2": entity.get("iso2") if entity.get("iso2") != "n/a" else None,
                "region": _region_for(entity),
                "rights": list(entity.get("rights", [])),
                "rating": rating_code,
                "rating_emoji": emoji,
                "rating_label": label,
                "rating_basis": basis,
                "connector_status": entity.get("connector_status", "none"),
                "last_verified": (
                    entity["last_verified"].isoformat()
                    if isinstance(entity.get("last_verified"), dt.date)
                    else entity.get("last_verified")
                ),
                "synopsis_url": _synopsis_url(entity),
                "github_research_url": _github_research_url(entity),
                "shipped_sources": [
                    {
                        "id": s.get("id"),
                        "name": s.get("name"),
                        "rights": s.get("rights", []),
                        "data_types": s.get("data_types", []),
                        "access_method": (s.get("access") or {}).get("method"),
                        "auth": (s.get("access") or {}).get("auth"),
                        "status": s.get("status"),
                        "module": (s.get("connector") or {}).get("module"),
                    }
                    for s in sources_by_entity.get(eid, [])
                ],
            }
        )
    return out


def build_atlas_unattached_sources(
    sources: list[dict[str, Any]],
    state_entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sources that don't bind to any STATE entity (third-party DBs, court
    repositories, substantive-law corpora not tied to a registry office).
    Kept as a separate top-level list so the office-centric atlas stays
    clean.
    """
    entity_ids_sorted = sorted((e.get("id", "") for e in state_entities), key=len, reverse=True)
    unattached = []
    for src in sources:
        sid = src.get("id", "")
        matched = any(eid and _source_matches_entity(sid, eid) for eid in entity_ids_sorted)
        if not matched:
            unattached.append(src)
    return unattached


def compute_atlas_summary(entities: list[dict[str, Any]]) -> dict[str, Any]:
    by_rating: dict[str, int] = {}
    by_connector_status: dict[str, int] = {}
    by_region: dict[str, int] = {}
    by_layer: dict[str, int] = {}
    synopses_filled = 0

    for e in entities:
        by_rating[e["rating"]] = by_rating.get(e["rating"], 0) + 1
        cs = e.get("connector_status", "none")
        by_connector_status[cs] = by_connector_status.get(cs, 0) + 1
        by_region[e["region"]] = by_region.get(e["region"], 0) + 1
        by_layer[e["layer"]] = by_layer.get(e["layer"], 0) + 1
        if e.get("synopsis_url"):
            synopses_filled += 1

    return {
        "total_entities": len(entities),
        "by_rating": by_rating,
        "by_connector_status": by_connector_status,
        "by_region": by_region,
        "by_layer": by_layer,
        "synopses_filled": synopses_filled,
    }


def build_atlas_payload(
    sources: list[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    entities = build_atlas_entities(sources, state)
    unattached = build_atlas_unattached_sources(sources, state.get("entities", []))
    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "schema_version": 1,
        "summary": compute_atlas_summary(entities),
        "entities": serialize(entities),
        "unattached_sources": serialize(unattached),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate only; don't write")
    args = parser.parse_args()

    data = yaml.safe_load(SOURCES_YAML.read_text())
    sources = data.get("sources") or []

    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    for idx, source in enumerate(sources):
        sid = source.get("id")
        if sid in seen_ids:
            errors.append(f"sources[{idx}]: duplicate id {sid!r}")
        seen_ids.add(sid)
        validate_source(source, idx, errors, warnings)

    if warnings:
        print(f"{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    if errors:
        print(f"{len(errors)} validation error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    payload = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "schema_version": 1,
        "summary": compute_summary(sources),
        "matrix": build_matrix(sources),
        "sources": serialize(sources),
    }

    state = yaml.safe_load(STATE_YAML.read_text()) if STATE_YAML.exists() else {"entities": []}
    atlas_payload = build_atlas_payload(sources, state)

    if args.check:
        print(
            f"OK — {len(sources)} sources validated; "
            f"{len(atlas_payload['entities'])} atlas entities; "
            f"{len(atlas_payload['unattached_sources'])} unattached sources"
        )
        return 0

    COVERAGE_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {COVERAGE_JSON.relative_to(ROOT)} — {len(sources)} sources")

    ATLAS_JSON.write_text(json.dumps(atlas_payload, indent=2) + "\n")
    print(
        f"Wrote {ATLAS_JSON.relative_to(ROOT)} — "
        f"{len(atlas_payload['entities'])} entities, "
        f"{len(atlas_payload['unattached_sources'])} unattached sources"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

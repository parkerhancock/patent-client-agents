#!/usr/bin/env python3
"""Build ``coverage/profiles-snapshot/`` from ``research/wipo_profiles/``.

For each per-country markdown file, extracts the structured fields
(ISO-2 code, WIPO member-since year, treaty count, GII ranking, IP
office names, quick-links table, lead summary) and writes them as a
JSON document the patentclient.com/profiles page consumes.

Also emits ``index.json`` with one lean row per jurisdiction for the
browse-cards UI.

Usage:
    uv run python scripts/build_profiles_snapshot.py
    uv run python scripts/build_profiles_snapshot.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = ROOT / "research" / "wipo_profiles"
SNAPSHOT_DIR = ROOT / "coverage" / "profiles-snapshot"

# Markdown table row: | Key | Value |
_TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$")
_H1 = re.compile(r"^#\s+(.+?)\s*—\s*WIPO Country IP Profile")
_SECTION_H2 = re.compile(r"^##\s+(.+?)\s*$")
_SOURCE = re.compile(r"^\*\*Source:\*\*\s+(\S+)")
_SNAPSHOT = re.compile(r"^\*\*Snapshot:\*\*\s+(\S+)")


def _parse_profile(md_path: Path) -> dict[str, Any] | None:
    """Parse one wipo_profiles/{iso2}.md file into a structured dict."""
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    iso2 = md_path.stem.upper()
    country_name: str | None = None
    fields: dict[str, str] = {}
    quick_links: list[dict[str, str]] = []
    lead_summary_lines: list[str] = []

    section: str | None = None
    in_summary = False

    for line in lines:
        if m := _H1.match(line):
            country_name = m.group(1).strip()
            continue
        if m := _SOURCE.match(line):
            fields["source_url"] = m.group(1)
            continue
        if m := _SNAPSHOT.match(line):
            fields["snapshot_at"] = m.group(1)
            continue
        if m := _SECTION_H2.match(line):
            section = m.group(1).strip()
            in_summary = section.lower().startswith("lead summary")
            continue

        # Skip table-header separator rows (|---|---|).
        if re.match(r"^\|[\s:|-]+\|\s*$", line):
            continue

        if section is None and (m := _TABLE_ROW.match(line)):
            key, val = m.group(1).strip(), m.group(2).strip()
            if key.lower() == "field" and val.lower() == "value":
                continue
            # Strip backtick wrapping on values like `JP`.
            val = val.strip("`")
            fields[_slugify_key(key)] = val
        elif section and section.lower().startswith("quick links"):
            if m := _TABLE_ROW.match(line):
                resource, url = m.group(1).strip(), m.group(2).strip()
                if resource.lower() == "resource" and url.lower() == "url":
                    continue
                quick_links.append({"resource": resource, "url": url})
        elif in_summary:
            if line.startswith("##"):
                in_summary = False
            elif line.strip():
                lead_summary_lines.append(line.strip())

    if country_name is None:
        print(f"  skip {md_path.name}: no H1 header", file=sys.stderr)
        return None

    treaty_count = _safe_int(fields.get("wipo_treaty_count"))
    member_since = _safe_int(fields.get("wipo_member_since"))
    gii_rank = _extract_gii_rank(fields.get("gii_ranking", ""))

    return {
        "iso2": iso2,
        "country_name": country_name,
        "wipo_member_since": member_since,
        "wipo_treaty_count": treaty_count,
        "gii_rank": gii_rank,
        "gii_ranking_text": fields.get("gii_ranking"),
        "national_ip_offices": fields.get("national_ip_offices"),
        "source_url": fields.get("source_url"),
        "snapshot_at": fields.get("snapshot_at"),
        "quick_links": quick_links,
        "lead_summary": "\n".join(lead_summary_lines).strip() or None,
    }


def _slugify_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def _safe_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


_GII_PATTERN = re.compile(r"ranks\s+(\d+)(?:st|nd|rd|th)\s+among", re.IGNORECASE)


def _extract_gii_rank(text: str) -> int | None:
    if m := _GII_PATTERN.search(text):
        return int(m.group(1))
    return None


def _write_profile(profile: dict[str, Any]) -> Path:
    out = SNAPSHOT_DIR / f"{profile['iso2'].lower()}.json"
    out.write_text(json.dumps(profile, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return out


def _write_index(profiles: list[dict[str, Any]]) -> None:
    rows = [
        {
            "iso2": p["iso2"],
            "country_name": p["country_name"],
            "national_ip_offices": p["national_ip_offices"],
            "wipo_member_since": p["wipo_member_since"],
            "wipo_treaty_count": p["wipo_treaty_count"],
            "gii_rank": p["gii_rank"],
            "snapshot_at": p["snapshot_at"],
        }
        for p in profiles
    ]
    rows.sort(key=lambda r: r["country_name"])
    payload = {
        "schema_version": 1,
        "total_profiles": len(rows),
        "profiles": rows,
    }
    (SNAPSHOT_DIR / "index.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--check",
        action="store_true",
        help="Parse every file but do not write JSON outputs.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    md_files = sorted(PROFILES_DIR.glob("*.md"))
    md_files = [f for f in md_files if f.stem.lower() != "readme"]
    print(f"Parsing {len(md_files)} WIPO country profiles...")
    if not args.check:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    profiles: list[dict[str, Any]] = []
    failures: list[str] = []
    for md in md_files:
        profile = _parse_profile(md)
        if profile is None:
            failures.append(md.name)
            continue
        profiles.append(profile)
        if not args.check:
            _write_profile(profile)

    if not args.check:
        _write_index(profiles)
        print(f"Wrote {len(profiles)} profile files + index.json to {SNAPSHOT_DIR}")
    else:
        print(f"Parsed {len(profiles)} profiles successfully (--check; not writing)")

    if failures:
        print(f"\n{len(failures)} files failed to parse:", file=sys.stderr)
        for name in failures:
            print(f"  - {name}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

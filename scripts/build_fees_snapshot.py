#!/usr/bin/env python3
"""Build ``coverage/fees-snapshot/`` from the live fee scrapers.

For each ``(office_code, right)`` route in the registry, calls the
scraper once and writes its FeeSchedule to a JSON file. Also emits an
``index.json`` containing lean ``JurisdictionMeta`` rows for the
browse-fees page.

The resulting tree is the build artifact the patentclient.com fees UI
fetches from the edge CDN. The website never talks to the MCP server
at runtime — it reads these static files. The live MCP path remains
available for "refresh on demand" workflows.

Exit 0 on success, 1 on partial success, and 2 if every scraper fails.

Usage:
    uv run python scripts/build_fees_snapshot.py
    uv run python scripts/build_fees_snapshot.py --check
    uv run python scripts/build_fees_snapshot.py --offices USPTO,EPO,JPO
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from patent_client_agents.fees.client import _to_meta
from patent_client_agents.fees.registry import _DISPATCH, OFFICES

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "coverage" / "fees-snapshot"


async def _build_one(
    office: str, right: Any, scraper: Any
) -> tuple[dict, dict] | tuple[None, None]:
    """Return ``(schedule_dict, meta_dict)`` or ``(None, None)`` on failure."""
    try:
        schedule = await scraper()
    except Exception as exc:  # noqa: BLE001 — surface every scraper failure
        print(f"  FAIL {office}/{right.value}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None, None
    return (
        schedule.model_dump(mode="json"),
        _to_meta(schedule).model_dump(mode="json"),
    )


async def _build_all(only: set[str] | None) -> tuple[list[dict], list[tuple[str, str]]]:
    """Run every scraper and return (meta_rows, failures)."""
    meta_rows: list[dict] = []
    failures: list[tuple[str, str]] = []
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    for (office, right), scraper in _DISPATCH.items():
        if only and office not in only:
            continue
        print(f"  {office}/{right.value} ... ", end="", flush=True)
        schedule_dict, meta_dict = await _build_one(office, right, scraper)
        if schedule_dict is None:
            failures.append((office, right.value))
            print("FAIL")
            continue
        out = SNAPSHOT_DIR / f"{office}-{right.value}.json"
        out.write_text(json.dumps(schedule_dict, indent=2, sort_keys=True) + "\n")
        meta_rows.append(meta_dict)
        print(f"ok ({len(schedule_dict['fees'])} fees)")

    return meta_rows, failures


def _write_index(meta_rows: list[dict], failures: list[tuple[str, str]]) -> None:
    """Write index.json — lean rows for the browse page.

    Includes a ``failures`` array so the UI can show "currently unavailable"
    rows for offices whose upstream is temporarily down (e.g. INPI-FR 503).
    """
    by_office: dict[str, list[dict]] = {}
    for row in meta_rows:
        by_office.setdefault(row["office_code"], []).append(row)
    payload = {
        "schema_version": 1,
        "offices_covered": sorted(by_office),
        "total_schedules": len(meta_rows),
        "schedules": meta_rows,
        "failures": [{"office_code": o, "right": r} for o, r in failures],
    }
    (SNAPSHOT_DIR / "index.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--check",
        action="store_true",
        help="Validate by running every scraper but do not write files.",
    )
    p.add_argument(
        "--offices",
        type=str,
        default=None,
        help="Comma-separated office codes to include (default: all).",
    )
    return p.parse_args()


async def _main() -> int:
    args = _parse_args()
    only: set[str] | None = (
        {s.strip().upper() for s in args.offices.split(",")} if args.offices else None
    )
    if only:
        unknown = only - set(OFFICES)
        if unknown:
            print(f"Unknown office codes: {sorted(unknown)}", file=sys.stderr)
            return 2

    print(f"Building fees snapshot ({len(_DISPATCH)} routes)...")
    if args.check:
        print("(--check mode: not writing files)")

    meta_rows, failures = await _build_all(only)

    if args.check:
        # Throw away artifacts written during --check; re-running without
        # --check is the path to actually publish.
        for path in SNAPSHOT_DIR.glob("*.json"):
            path.unlink()
    elif not meta_rows:
        # Keep the last known-good index. The nightly workflow treats this
        # result as a hard failure and must not publish an empty index.
        print(
            f"\nNo schedules built; {SNAPSHOT_DIR / 'index.json'} left untouched",
            file=sys.stderr,
        )
    elif only:
        # Partial build — do NOT rewrite index.json with incomplete data;
        # only the per-route schedule files we just touched are valid.
        print(
            f"\nWrote {len(meta_rows)} schedule files to {SNAPSHOT_DIR} "
            "(partial build; index.json left untouched)"
        )
    else:
        _write_index(meta_rows, failures)
        print(f"\nWrote {len(meta_rows)} schedule files + index.json to {SNAPSHOT_DIR}")

    if failures:
        print(f"\n{len(failures)} failures:", file=sys.stderr)
        for office, right in failures:
            print(f"  - {office}/{right}", file=sys.stderr)
        return 2 if not meta_rows else 1

    if not meta_rows:
        return 2

    print(f"All {len(meta_rows)} schedules built successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))

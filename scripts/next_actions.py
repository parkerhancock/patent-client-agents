#!/usr/bin/env python3
"""Report actionable rows from ``research/STATE.yaml`` and verify its stats."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE = ROOT / "research" / "STATE.yaml"
STATUSES = ("shipped", "in_progress", "spec_ready", "planned", "blocked")
PASSIVE_ACTIONS = {"none", "monitor", "monitor_partner_api", "link_only_atlas_card"}


def load_state(path: Path = DEFAULT_STATE) -> dict[str, Any]:
    """Load the pipeline state document."""
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("entities"), list):
        raise ValueError(f"{path} must contain an entities list")
    return data


def compute_stats(entities: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Compute the declared summary values from entity rows."""
    rows = list(entities)
    stats = {
        "total_entities": len(rows),
        "synopses_filled": sum(bool(row.get("synopsis")) for row in rows),
        "next_unblocked_synopses": sum(
            row.get("next_action") == "synopsis_discovery" and not row.get("blocked_by")
            for row in rows
        ),
        "green_transitive_states": sum(row.get("rating") == "green_transitive" for row in rows),
    }
    for status in STATUSES:
        stats[f"connectors_{status}"] = sum(row.get("connector_status") == status for row in rows)
    return stats


def stats_errors(data: dict[str, Any]) -> list[str]:
    """Return differences between declared and computed stats."""
    declared = data.get("stats") or {}
    computed = compute_stats(data["entities"])
    return [
        f"{key}: declared {declared.get(key)!r}, computed {value}"
        for key, value in computed.items()
        if declared.get(key) != value
    ]


def select_entities(
    entities: Iterable[dict[str, Any]],
    *,
    action: str | None = None,
    status: str | None = None,
    rating: str | None = None,
    include_blocked: bool = False,
) -> list[dict[str, Any]]:
    """Select active rows that match optional pipeline filters."""
    selected = []
    for row in entities:
        if not include_blocked and row.get("blocked_by"):
            continue
        if action is None and row.get("next_action") in PASSIVE_ACTIONS:
            continue
        if action is not None and row.get("next_action") != action:
            continue
        if status is not None and row.get("connector_status") != status:
            continue
        if rating is not None and row.get("rating") != rating:
            continue
        selected.append(row)
    return selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--action")
    parser.add_argument("--status")
    parser.add_argument("--rating")
    parser.add_argument("--include-blocked", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check-stats", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = load_state(args.state)

    if args.check_stats:
        errors = stats_errors(data)
        if errors:
            for error in errors:
                print(f"STATE stats mismatch: {error}", file=sys.stderr)
            return 1
        print("STATE stats match entity rows.")
        return 0

    rows = select_entities(
        data["entities"],
        action=args.action,
        status=args.status,
        rating=args.rating,
        include_blocked=args.include_blocked,
    )
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0

    print("id\tstatus\trating\tnext_action\tname")
    for row in rows:
        print(
            "\t".join(
                str(row.get(key, ""))
                for key in ("id", "connector_status", "rating", "next_action", "name")
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

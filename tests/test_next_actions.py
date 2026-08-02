from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "next_actions.py"
SPEC = importlib.util.spec_from_file_location("next_actions", SCRIPT)
assert SPEC and SPEC.loader
next_actions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(next_actions)


def _rows():
    return [
        {
            "id": "A",
            "name": "Alpha",
            "synopsis": "alpha.md",
            "rating": "green",
            "connector_status": "shipped",
            "next_action": "none",
            "blocked_by": [],
        },
        {
            "id": "B",
            "name": "Beta",
            "synopsis": None,
            "rating": "tbd",
            "connector_status": "planned",
            "next_action": "synopsis_discovery",
            "blocked_by": [],
        },
        {
            "id": "C",
            "name": "Gamma",
            "synopsis": None,
            "rating": "green_transitive",
            "connector_status": "blocked",
            "next_action": "connector_build",
            "blocked_by": ["B"],
        },
    ]


def test_compute_stats_from_rows():
    assert next_actions.compute_stats(_rows()) == {
        "total_entities": 3,
        "synopses_filled": 1,
        "next_unblocked_synopses": 1,
        "green_transitive_states": 1,
        "connectors_shipped": 1,
        "connectors_in_progress": 0,
        "connectors_spec_ready": 0,
        "connectors_planned": 1,
        "connectors_blocked": 1,
    }


def test_select_entities_defaults_to_unblocked_active_rows():
    assert [row["id"] for row in next_actions.select_entities(_rows())] == ["B"]


def test_select_entities_supports_filters_and_blocked_rows():
    rows = next_actions.select_entities(
        _rows(), action="connector_build", rating="green_transitive", include_blocked=True
    )
    assert [row["id"] for row in rows] == ["C"]


def test_stats_errors_reports_drift():
    data = {
        "stats": {**next_actions.compute_stats(_rows()), "total_entities": 2},
        "entities": _rows(),
    }
    assert next_actions.stats_errors(data) == ["total_entities: declared 2, computed 3"]

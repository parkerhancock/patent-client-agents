from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from scripts import build_source_catalog


def test_repository_catalog_is_valid() -> None:
    records, parse_errors = build_source_catalog.load_records()

    assert not build_source_catalog.validate_catalog(records, parse_errors)
    assert len(records) == 120


def test_coverage_manifest_is_fully_projected_from_canonical_records() -> None:
    records, _ = build_source_catalog.load_records()
    projected = build_source_catalog.build_coverage_sources(records)

    assert len(projected) == 114
    assert len({source["id"] for source in projected}) == 114
    orders = sorted(record.coverage["order"] for record in records if record.coverage)
    assert orders == list(range(114))


def test_rendered_coverage_manifest_matches_projected_records() -> None:
    records, _ = build_source_catalog.load_records()

    rendered = yaml.safe_load(build_source_catalog.render_coverage_manifest(records))

    assert rendered["sources"] == build_source_catalog.build_coverage_sources(records)


def test_catalog_rejects_noncontiguous_coverage_order() -> None:
    records, _ = build_source_catalog.load_records()
    original = [record for record in records if record.coverage][:2]
    first = build_source_catalog.SourceRecord(
        path=original[0].path,
        metadata={**original[0].metadata, "coverage": {**original[0].coverage, "order": 0}},
        body=original[0].body,
    )
    second = build_source_catalog.SourceRecord(
        path=original[1].path,
        metadata={**original[1].metadata, "coverage": {**original[1].coverage, "order": 2}},
        body=original[1].body,
    )

    errors = build_source_catalog.validate_catalog([first, second])

    assert any("coverage.order values must be contiguous" in error for error in errors)


def test_generated_source_catalog_views_are_current() -> None:
    records, _ = build_source_catalog.load_records()
    outputs = build_source_catalog.build_outputs(records)

    assert not build_source_catalog._check_outputs(outputs)


def test_shared_commercial_source_appears_in_each_pilot_country() -> None:
    records, _ = build_source_catalog.load_records()
    darts = next(record for record in records if record.id == "WO/Clarivate/DartsIP")

    assert darts.jurisdictions == ["CN", "JP", "KR"]
    for code in darts.jurisdictions:
        rendered = build_source_catalog.render_country(
            code, [record for record in records if code in record.jurisdictions]
        )
        assert "## Commercial sources" in rendered
        assert "Darts-IP" in rendered


def test_blocked_record_requires_a_blocker(tmp_path: Path) -> None:
    path = tmp_path / "blocked.md"
    metadata = {
        "id": "JP/Test/Blocked",
        "name": "Blocked test",
        "jurisdictions": ["JP"],
        "institution": "Test",
        "source_type": "case_lookup",
        "official_url": "https://example.com",
        "last_verified": dt.date(2026, 8, 21),
        "source_status": "active",
        "category": "adjudicative_records",
        "rights": ["patent"],
        "access": {
            "availability": "manual_only",
            "audience": "public",
            "formats": ["html"],
            "automation_posture": "technically_blocked",
        },
        "capabilities": {field: "none" for field in build_source_catalog.CAPABILITIES},
        "connector": {"status": "blocked", "blockers": []},
    }
    body = "\n".join(f"## {heading}\n" for heading in build_source_catalog.REQUIRED_HEADINGS)
    body += "\n- [Evidence](https://example.com)\n"
    record = build_source_catalog.SourceRecord(path=path, metadata=metadata, body=body)

    assert (
        "blocked connector requires at least one blocker"
        in build_source_catalog.validate_record(record, today=dt.date(2026, 8, 21))
    )


def test_capability_rollup_prefers_full_over_partial() -> None:
    records, _ = build_source_catalog.load_records()
    japan = [record for record in records if "JP" in record.jurisdictions]

    grade, providers = build_source_catalog.best_capability(japan, "decisions")

    assert grade == "partial"
    assert providers

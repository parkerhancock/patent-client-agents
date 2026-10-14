"""Contract test for every bundled corpus package's ``get_corpus_status()``.

Each package reads its version from different ``meta`` keys and may fall
back to a snapshot-date label. The table below is the spec for each
package's output; the cases run against a corpus built from the package's
own DDL with synthetic ``meta`` rows. Package-specific cases that depend on
what a real build writes stay in ``tests/<pkg>/test_corpus_status.py``.
"""

from __future__ import annotations

import importlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.shared.corpus import parse_snapshot_date


@dataclass(frozen=True)
class Spec:
    package: str
    env_var: str
    version_keys: tuple[str, ...] = ("source_version",)
    snapshot_label: str | None = None  # e.g. "snapshot-{}"


SPECS = [
    Spec("mpep", "MPEP_CORPUS_PATH"),
    Spec("tmep", "TMEP_CORPUS_PATH"),
    Spec("epc", "EPC_CORPUS_PATH", ("epc_year",)),
    Spec("epo_case_law", "CASELAW_CORPUS_PATH", ("caselaw_year",)),
    Spec("epo_guidelines", "GUIDELINES_CORPUS_PATH", ("guidelines_year",)),
    Spec("epo_pct_guidelines", "PCT_GUIDELINES_CORPUS_PATH", ("source_version", "guidelines_year")),
    Spec(
        "epo_up_guidelines", "UP_GUIDELINES_CORPUS_PATH", ("source_version", "up_guidelines_year")
    ),
    Spec("inpi_br_statutes", "INPI_BR_STATUTES_CORPUS_PATH", ("lpi_year",)),
    Spec("ilpo_statutes", "ILPO_STATUTES_CORPUS_PATH"),
    Spec("legifrance_ip", "LEGIFRANCE_IP_CORPUS_PATH"),
    Spec("dpma_statutes", "DPMA_STATUTES_CORPUS_PATH", snapshot_label="snapshot-{}"),
    Spec("ipo_in_mppp", "IPO_IN_MPPP_CORPUS_PATH", snapshot_label="snapshot-{}"),
    Spec("ipo_in_statutes", "IPO_IN_STATUTES_CORPUS_PATH", snapshot_label="snapshot-{}"),
    Spec("tw_trade_secrets", "TW_TRADE_SECRETS_CORPUS_PATH", snapshot_label="snapshot-{}"),
    Spec("ukipo_mopp", "MOPP_CORPUS_PATH", snapshot_label="snapshot-{}"),
    Spec("ipos_manuals", "IPOS_MANUALS_CORPUS_PATH", snapshot_label="snapshot {}"),
    Spec("ipos_statutes", "IPOS_STATUTES_CORPUS_PATH", snapshot_label="snapshot {}"),
    # The consolidated UPC PDFs carry no vendor version; the snapshot is the version.
    Spec("upc_statutes", "UPC_STATUTES_CORPUS_PATH", (), snapshot_label="snapshot {}"),
]


@pytest.fixture(params=SPECS, ids=lambda spec: spec.package)
def spec(request: pytest.FixtureRequest) -> Spec:
    return request.param


@pytest.fixture
def status_with_meta(spec: Spec, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Return ``f(meta) -> status`` that builds a corpus with ``meta`` and reads it."""
    get_corpus_status = importlib.import_module(
        f"patent_client_agents.{spec.package}"
    ).get_corpus_status
    ddl = importlib.import_module(f"patent_client_agents.{spec.package}.corpus.schema").DDL
    counter = iter(range(1_000))

    def read(meta: dict[str, str]):
        db_path = tmp_path / f"corpus{next(counter)}.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(ddl)
            conn.executemany("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", meta.items())
            conn.commit()
        finally:
            conn.close()
        monkeypatch.setenv(spec.env_var, str(db_path))
        return get_corpus_status()

    return read


def _fallback(spec: Spec, snapshot: str) -> str:
    return spec.snapshot_label.format(snapshot) if spec.snapshot_label else "unknown"


def test_package_exposes_callable_and_status_type(spec: Spec) -> None:
    module = importlib.import_module(f"patent_client_agents.{spec.package}")
    assert callable(module.get_corpus_status)
    assert "get_corpus_status" in module.__all__
    assert set(module.CorpusStatus.__annotations__) == {"corpus_synced_at", "corpus_version"}


def test_missing_corpus_reports_unknown(
    spec: Spec, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(spec.env_var, str(tmp_path / "missing.db"))
    module = importlib.import_module(f"patent_client_agents.{spec.package}")
    assert module.get_corpus_status() == {"corpus_synced_at": None, "corpus_version": "unknown"}


def test_version_key_and_snapshot_date(spec: Spec, status_with_meta) -> None:
    meta = {"snapshot_date": "2026-03-10"}
    expected = _fallback(spec, "2026-03-10")
    if spec.version_keys:
        meta[spec.version_keys[0]] = "Edition-7"
        expected = "Edition-7"
    status = status_with_meta(meta)
    assert status["corpus_version"] == expected
    assert status["corpus_synced_at"] == datetime(2026, 3, 10, tzinfo=UTC)


def test_first_version_key_wins(spec: Spec, status_with_meta) -> None:
    if len(spec.version_keys) < 2:
        pytest.skip("reads a single version key")
    meta = {key: f"v-{key}" for key in spec.version_keys}
    assert status_with_meta(meta)["corpus_version"] == f"v-{spec.version_keys[0]}"
    later = {key: f"v-{key}" for key in spec.version_keys[1:]}
    assert status_with_meta(later)["corpus_version"] == f"v-{spec.version_keys[1]}"


def test_snapshot_only_uses_package_fallback(spec: Spec, status_with_meta) -> None:
    status = status_with_meta({"snapshot_date": "2026-02-15"})
    assert status["corpus_version"] == _fallback(spec, "2026-02-15")


def test_empty_meta_reports_unknown(spec: Spec, status_with_meta) -> None:
    assert status_with_meta({}) == {"corpus_synced_at": None, "corpus_version": "unknown"}


def test_malformed_snapshot_date_drops_synced_at_only(spec: Spec, status_with_meta) -> None:
    meta = {"snapshot_date": "not-a-date"}
    expected = _fallback(spec, "not-a-date")
    if spec.version_keys:
        meta[spec.version_keys[-1]] = "R-07.2022"
        expected = "R-07.2022"
    status = status_with_meta(meta)
    assert status["corpus_version"] == expected
    assert status["corpus_synced_at"] is None


def test_moving_label_current_is_not_a_version(spec: Spec, status_with_meta) -> None:
    """``"current"`` is a moving label, not a version (CONNECTOR_STANDARDS §4)."""
    status = status_with_meta({"source_version": "current", "snapshot_date": "2026-01-02"})
    assert status["corpus_version"] == _fallback(spec, "2026-01-02")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("2026-05-13", datetime(2026, 5, 13, tzinfo=UTC)),
        ("2026-05-13T10:30:00", datetime(2026, 5, 13, 10, 30, tzinfo=UTC)),
        ("2026-05-13T10:30:00+02:00", datetime(2026, 5, 13, 8, 30, tzinfo=UTC)),
        ("not-a-date", None),
    ],
)
def test_parse_snapshot_date(raw: str | None, expected: datetime | None) -> None:
    assert parse_snapshot_date(raw) == expected

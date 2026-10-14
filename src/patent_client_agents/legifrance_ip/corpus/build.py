"""Build the Légifrance IP statutes corpus from the bundled JSONL seed.

Console-script entry point for
``patent-client-agents-build-legifrance-ip-corpus``. Reads
``patent_client_agents/legifrance_ip/data/seed.jsonl`` (one JSON object
per line, schema documented below) and writes the schema defined in
:mod:`patent_client_agents.legifrance_ip.corpus.schema`.

This builder **does not** fetch from Légifrance. The seed is hardcoded
so the corpus is reproducible from the wheel alone — no API access
required. Subsequent seed releases bump ``CORPUS_VERSION`` here.

Seed schema (``data/seed.jsonl``)::

    {"statute": "CPI", "section": "L611-1",
     "title": "Brevetabilité",
     "text": "Toute invention peut faire l'objet ..."}

``statute`` is the law collection (``CPI`` for Code de la propriété
intellectuelle, ``Code de commerce`` for L.151 trade secrets);
``section`` is the article number (no leading ``L.``); ``title`` is the
heading; ``text`` is the canonical article body.

Run manually::

    patent-client-agents-build-legifrance-ip-corpus \\
        --output ~/.cache/patent_client_agents/legifrance_ip.db
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from patent_client_agents.shared.corpus import atomic_output, run_build_cli

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

# Bump when the bundled seed changes substantively (new articles, text
# revisions). ``get_corpus_status()`` reports this via Provenance so
# agents can quote it.
CORPUS_VERSION = "seed v1"


@dataclass(frozen=True)
class SeedRow:
    """One row from the bundled JSONL seed."""

    statute: str
    section: str
    title: str | None
    text: str


def _seed_path() -> Path:
    """Return the absolute path to the bundled ``data/seed.jsonl``.

    Uses ``importlib.resources`` so the lookup works regardless of how
    the wheel is installed (editable, zipped, frozen).
    """
    ref = resources.files("patent_client_agents.legifrance_ip") / "data" / "seed.jsonl"
    return Path(str(ref))


def load_seed(path: Path | None = None) -> list[SeedRow]:
    """Parse the bundled JSONL seed into :class:`SeedRow` objects.

    Skips blank lines so a trailing newline doesn't trip the parser.
    Raises ``ValueError`` on the first malformed row — we want a build
    failure to be loud, not silent.
    """
    target = path or _seed_path()
    rows: list[SeedRow] = []
    with target.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{target}:{line_no}: invalid JSON ({exc.msg})") from exc
            try:
                rows.append(
                    SeedRow(
                        statute=str(payload["statute"]),
                        section=str(payload["section"]),
                        title=payload.get("title"),
                        text=str(payload["text"]),
                    )
                )
            except KeyError as exc:
                raise ValueError(f"{target}:{line_no}: missing required key {exc}") from exc
    return rows


def write_corpus(rows: Iterable[SeedRow], output: Path) -> int:
    """Initialize the schema and insert article rows. Returns row count."""
    with atomic_output(output) as tmp_path:
        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(DDL)
            seen: set[tuple[str, str]] = set()
            inserted = 0
            for row in rows:
                key = (row.statute, row.section)
                if key in seen:
                    continue
                seen.add(key)
                conn.execute(
                    """
                    INSERT INTO sections (statute, section, title, text)
                    VALUES (?, ?, ?, ?)
                    """,
                    (row.statute, row.section, row.title, row.text),
                )
                inserted += 1
            snapshot_date = datetime.now(UTC).strftime("%Y-%m-%d")
            meta_rows = [
                ("schema_version", str(SCHEMA_VERSION)),
                ("snapshot_date", snapshot_date),
                ("source_version", CORPUS_VERSION),
                ("section_count", str(inserted)),
            ]
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                meta_rows,
            )
            conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
            conn.commit()
            # VACUUM must run outside any open transaction.
            conn.isolation_level = None
            conn.execute("VACUUM")
        finally:
            conn.close()
    return inserted


def build_corpus(output: Path, *, seed_path: Path | None = None) -> int:
    """Materialize the corpus at ``output`` from the bundled seed."""
    rows = load_seed(seed_path)
    return write_corpus(rows, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="patent-client-agents-build-legifrance-ip-corpus",
        description=(
            "Build the Légifrance IP statutes SQLite/FTS5 corpus from "
            "the bundled JSONL seed. The wheel ships both the builder "
            "and the seed; no network access is required."
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Path to write the corpus SQLite file. Parent dirs created on demand.",
    )
    parser.add_argument(
        "--seed",
        type=Path,
        default=None,
        help="Override the bundled seed JSONL (defaults to data/seed.jsonl in the wheel).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log build progress to stderr.",
    )
    args = parser.parse_args(argv)
    return run_build_cli(
        lambda: build_corpus(args.output, seed_path=args.seed),
        verbose=args.verbose,
        done=lambda count, _elapsed: (
            f"Wrote {count} Légifrance IP articles to {args.output} (version {CORPUS_VERSION})"
        ),
        to_stderr=True,
        catch_errors=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())

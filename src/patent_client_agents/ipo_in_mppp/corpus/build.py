"""Build the IPO India MPPP SQLite/FTS5 corpus from a JSON seed.

The IPO India MPPP (Manual of Patent Practice & Procedure) v3.0 (2019)
is published as a single ~400-page PDF. Refresh requires scraping the
PDF off ipindia.gov.in and re-chunking — outside the runtime path.
The seed file at ``data/ipo_in_mppp/seed.jsonl`` is the build input.

Each record shape::

    {
        "section_number": "04.05.01",
        "chapter": "Chapter 4",
        "title": "Examination of patent applications",
        "text": "...full section text...",
        "source_url": "https://ipindia.gov.in/..."
    }

Console-script entry point for
``patent-client-agents-build-ipo-in-mppp-corpus``.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from patent_client_agents.shared.corpus import atomic_output, load_jsonl_seed, run_build_cli

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed.jsonl"


def build_corpus(
    output_path: Path,
    *,
    seed_path: Path = DEFAULT_SEED_PATH,
    source_version: str | None = "v3.0 (2019)",
) -> int:
    """Write the corpus to ``output_path`` and return the row count."""
    with atomic_output(output_path) as tmp_path:
        seed_rows = load_jsonl_seed(seed_path, ("section_number", "text"))
        logger.info("Loaded %d seed rows from %s", len(seed_rows), seed_path)

        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(DDL)
            snapshot = datetime.now(UTC).strftime("%Y-%m-%d")
            meta_pairs = [
                ("schema_version", str(SCHEMA_VERSION)),
                ("snapshot_date", snapshot),
                ("section_count", str(len(seed_rows))),
            ]
            if source_version:
                meta_pairs.append(("source_version", source_version))
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                meta_pairs,
            )
            conn.executemany(
                "INSERT INTO sections (section_number, chapter, title, text, source_url) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        row["section_number"],
                        row.get("chapter"),
                        row.get("title"),
                        row["text"],
                        row.get("source_url"),
                    )
                    for row in seed_rows
                ],
            )
            conn.commit()
        finally:
            conn.close()

    logger.info("Wrote %d sections to %s", len(seed_rows), output_path)
    return len(seed_rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the IPO India MPPP SQLite/FTS5 corpus from the bundled JSON seed."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".cache" / "patent_client_agents" / "ipo_in_mppp.db",
        help="Path to write the corpus to (default: ~/.cache/patent_client_agents/ipo_in_mppp.db)",
    )
    parser.add_argument(
        "--seed",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help="JSON-lines seed file to ingest (default: bundled seed.jsonl).",
    )
    parser.add_argument(
        "--source-version",
        default="v3.0 (2019)",
        help="Vendor edition label (defaults to the v3.0 2019 publication).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable INFO logging.",
    )
    args = parser.parse_args(argv)

    return run_build_cli(
        lambda: build_corpus(
            args.output,
            seed_path=args.seed,
            source_version=args.source_version,
        ),
        verbose=args.verbose,
        done=lambda count, _elapsed: f"Wrote {count} sections to {args.output}",
    )


if __name__ == "__main__":
    sys.exit(main())

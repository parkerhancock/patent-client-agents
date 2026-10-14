"""Build the Taiwan Trade Secrets Act SQLite/FTS5 corpus from a JSON seed.

The seed file ships in the repo at
``src/patent_client_agents/tw_trade_secrets/data/seed.jsonl`` and
contains one JSON object per Article of the Taiwan Trade Secrets Act
(營業秘密法), in the official English translation published by the
Laws & Regulations Database of the Republic of China
(``law.moj.gov.tw/Eng``). Each record has:

    {
        "section": "13-1",
        "title": "Criminal Liability",
        "text": "...full Article text..."
    }

Console-script entry point for
``patent-client-agents-build-tw-trade-secrets-corpus``.

The seed approach (rather than scraping law.moj.gov.tw at build time)
keeps the connector deterministic and CI-friendly — the seed is itself
the artifact under version control, and refreshing it is a deliberate
documented step. See ``CONNECTOR_STANDARDS.md`` §4 ``update_strategy =
scheduled_recrawl`` / cadence ``irregular`` for the policy.
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

# The seed file lives alongside the package source. Cloud deploys can
# override via ``--seed`` to point at a freshly recrawled JSONL.
DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed.jsonl"


def build_corpus(
    output_path: Path,
    *,
    seed_path: Path = DEFAULT_SEED_PATH,
    source_version: str | None = None,
) -> int:
    """Write the corpus to ``output_path`` and return the row count.

    Builds into a temp path first so a half-finished run can't corrupt
    an existing database.
    """
    with atomic_output(output_path) as tmp_path:
        seed_rows = load_jsonl_seed(seed_path, ("section", "text"))
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
                "INSERT INTO sections (section, title, text) VALUES (?, ?, ?)",
                [(row["section"], row.get("title"), row["text"]) for row in seed_rows],
            )
            conn.commit()
        finally:
            conn.close()

    logger.info("Wrote %d sections to %s", len(seed_rows), output_path)
    return len(seed_rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Taiwan Trade Secrets Act SQLite/FTS5 corpus from the bundled JSON seed."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".cache" / "patent_client_agents" / "tw_trade_secrets.db",
        help=(
            "Path to write the corpus to "
            "(default: ~/.cache/patent_client_agents/tw_trade_secrets.db)"
        ),
    )
    parser.add_argument(
        "--seed",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help="JSON-lines seed file to ingest (default: bundled seed.jsonl).",
    )
    parser.add_argument(
        "--source-version",
        default=None,
        help="Optional vendor version label (rarely set for TW Trade Secrets).",
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

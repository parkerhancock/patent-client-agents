"""Copy a few real rows from the TMEP corpus into a small test fixture.

Maintenance only; tests never run this. It reuses the EPO legal extractor
(same outline schema): the source opens read-only and immutable, compressed
HTML BLOBs and the dictionary are copied byte for byte, plaintext as stored,
and the full-text index is rebuilt over the subset. The default source is the
deployed snapshot (gs://patentclient-mcp-corpora/tmep/2026-05-13/tmep.db,
copied to ``.data/tmep/gcs/tmep.db``).
"""

from __future__ import annotations

import argparse
import importlib.util
import sqlite3
from contextlib import closing
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 1207 family (likelihood of confusion), the 1209.03(u) href from the Python
# docstring, a "ch1300_..." style href, and 1401.02(a) (80,980 characters of
# text, beyond the 32,000-character inline budget).
HREFS = [
    "TMEP-1200d1e5036.html",
    "TMEP-1200d1e5044.html",
    "TMEP-1200d1e5130.html",
    "TMEP-1200d1e8145.html",
    "TMEP-900d1e489.html",
    "ch1300_d2266f_1dcc2_11c.html",
    "TMEP-1400d1e32.html",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=HERE.parent / ".data" / "tmep" / "gcs" / "tmep.db"
    )
    parser.add_argument(
        "--output", type=Path, default=HERE.parent / "tests" / "fixtures" / "tmep" / "tmep.db"
    )
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("epo_fixtures", HERE / "extract-epo-legal-fixtures.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    module.extract(args.source, args.output, HREFS)
    # The copied meta says section_count=1751; the reader checks it against
    # the rows, so record the subset's count. Other meta is left as stored.
    with closing(sqlite3.connect(args.output)) as out:
        out.execute("UPDATE meta SET value = ? WHERE key = 'section_count'", (str(len(HREFS)),))
        out.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

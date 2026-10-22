"""Copy a few real rows from the UKIPO MoPP corpus into a small test fixture.

Maintenance only; tests never run this. It reuses the EPO legal extractor
(same outline schema): the source opens read-only and immutable, compressed
HTML BLOBs and the dictionary are copied byte for byte, plaintext as stored,
and the full-text index is rebuilt over the subset. The default source is the
prepared copy of the deployed snapshot
(gs://patentclient-mcp-corpora/ukipo_mopp/2026-05-14/mopp.db, prepared into
``.data/ukipo_mopp/mopp.db``; see docs/ukipo-mopp.md).
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Section 73 (33,235 characters of text, beyond the 32,000-character inline
# budget), section 4A (stored slug with a leading dash), the "sections-11-..."
# page the builder stored without a section number, section 4, section 102A
# (a lettered number) and the glossary (a slug-only page).
HREFS = [
    "section-73-comptroller-s-power-to-revoke-patents-on-his-own-initiative",
    "-section-4a-methods-of-treatment-or-diagnosis",
    "sections-11-effect-of-transfer-of-application-under-s-8-or-10",
    "section-4-industrial-application",
    "section-102a-right-of-audience-etc-in-proceedings-on-appeal-from-the-comptroller-repealed",
    "glossary-of-terms-and-abbreviations-used-in-this-manual",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=HERE.parent / ".data" / "ukipo_mopp" / "mopp.db"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE.parent / "tests" / "fixtures" / "ukipo-mopp" / "mopp.db",
    )
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("epo_fixtures", HERE / "extract-epo-legal-fixtures.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # The MoPP meta records no section_count, so it is copied as stored.
    module.extract(args.source, args.output, HREFS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

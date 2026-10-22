"""Regenerate python-parity.json from the Python reference implementation.

The expected values in python-parity.json are Python ``unified.py`` output on
real inputs, so tests/unified.test.ts can check the TypeScript port against
it. Inputs:

* ``odp-claim-texts.json``: the 32 ODP claim texts for US 10,765,880, as
  ``ApplicationsClient.getGrantedClaims("10765880")`` returns them when it
  replays ``tests/cassettes/odp-application-granted-claims.yaml`` (the test
  asserts they still match), plus a few edge-case strings defined below.
* ``tests/fixtures/google-patents/*.html.gz``: archived Google Patents pages.

Run from the patent-client-agents root with its Python environment:

    .venv/bin/python typescript/tests/fixtures/unified/generate_python_parity.py
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from patent_client_agents.unified import (
    build_canonical_claim,
    google_limitations_from_html,
    odp_limitations_from_text,
)

HERE = Path(__file__).resolve().parent
PAGES = HERE.parent / "google-patents"
EDGE_CASES = [
    "12. A device comprising:\n    a housing; and\n        a lid.",
    "  2 spaces only",
    "1.5 mm thick plate.",
    "3. \n\n    trailing   \n",
    "10.no space after dot",
]
GOOGLE = [
    "US7654321B2",
    "US20230012345A1",
    "EP3456789A1",
    "WO2020123456A1",
    "JP2019000001A",
    "CN110000000A",
]


def main() -> None:
    odp_texts = json.loads((HERE / "odp-claim-texts.json").read_text())
    google = {}
    for name in GOOGLE:
        html = gzip.decompress((PAGES / f"{name}.html.gz").read_bytes()).decode()
        parsed = google_limitations_from_html(html)
        google[name] = {str(number): parsed[number] for number in sorted(parsed)}
    out = {
        "odp": [
            {"input": text, "limitations": odp_limitations_from_text(text)}
            for text in odp_texts + EDGE_CASES
        ],
        "odp_canonical": [
            build_canonical_claim(index, odp_limitations_from_text(text), "independent", None)
            for index, text in enumerate(odp_texts, start=1)
        ],
        "google": google,
    }
    (HERE / "python-parity.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n"
    )


if __name__ == "__main__":
    main()

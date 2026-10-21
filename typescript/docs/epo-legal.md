# EPO legal corpus access

October 21, 2026. The TypeScript library reads five books published under
`www.epo.org/en/legal/`. They are offline SQLite/FTS5 snapshots on the same
outline schema and read-only lifecycle as [MPEP](mpep.md). No office API key is
needed. The MCP adapter uses a separate `epo:read` scope for HTTP access.

| Book | Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- | --- |
| European Patent Convention (Articles and Implementing Regulations) | `EpcClient` | `search_epc`, `get_epc_section` | `epc://corpus/status` | `EPC_CORPUS_PATH` |
| Case Law of the Boards of Appeal | `EpoCaseLawClient` | `search_epo_case_law`, `get_epo_case_law_section` | `epo-case-law://corpus/status` | `CASELAW_CORPUS_PATH` |
| Guidelines for Examination (Parts A to H) | `EpoGuidelinesClient` | `search_epo_guidelines`, `get_epo_guidelines_section` | `epo-guidelines://corpus/status` | `GUIDELINES_CORPUS_PATH` |
| PCT-EPO Guidelines | `EpoPctGuidelinesClient` | `search_epo_pct_guidelines`, `get_epo_pct_guidelines_section` | `epo-pct-guidelines://corpus/status` | `PCT_GUIDELINES_CORPUS_PATH` |
| Unitary Patent Guidelines | `EpoUpGuidelinesClient` | `search_epo_up_guidelines`, `get_epo_up_guidelines_section` | `epo-up-guidelines://corpus/status` | `UP_GUIDELINES_CORPUS_PATH` |

Tool names, path variables and default file names match the Python connector.
Each path variable has matching `_CORPUS_SHA256` (decoded SQLite) and
`_CORPUS_FILE_SHA256` (distributed file) pins. Without a path, a client uses
the Python cache location `~/.cache/patent_client_agents/<file>.db`. Those
Python files are WAL-mode databases and need preparation before Bun reads them.

## What is shared and what is book-specific

`EpoLegalCorpusClient` holds the shared behavior: search, citation-first section
lookup, `resolveSectionHref`, `listVersions` and corpus status. Each book is a
plain configuration object (`EPC_BOOK`, `EPO_CASE_LAW_BOOK` and so on) with its
own citation grammar, slug parsing, path labels and result URL suffix.

Retrieved sections carry an explicit `citation` derived from the stored slug:

- EPC: `{ kind: "article" | "rule", number }`, from `a54` or `r71`.
- Case Law: `{ part, subpart, section }`, from `clr_i_d_9_1`. Front and back
  matter such as `clr_foreword` has no position and returns `null`.
- EPO and PCT-EPO Guidelines: `{ part, chapter, section }`, from `g_ii_3_1`.
- UP Guidelines: `{ section }`, from `section_1_2_1`.

Section references accept the citation forms the Python clients accept (for
example `Art. 54`, `R. 71`, `I-D-9-1`, `G.II.3.1`, `B-III, 2.3.3`, `§ 1.2.1`),
stored slugs, `/en/legal/<book>/<year>/` paths and full epo.org URLs. As an
addition to Python, Guidelines, Case Law and UP Guidelines citations also
fall back to the stored `section_number` form. Search, cursors, lean
projections and the artifact delivery of HTML follow the MPEP tools.

## Edition and freshness

The Python builders record an edition year (`epc_year`, `caselaw_year`,
`guidelines_year`, `up_guidelines_year`) for the URL path they crawled, plus a
`snapshot_date` for the build. The client reports that year as `edition` and
`corpus_version`, and the snapshot date as `corpus_synced_at`. If the year key
is missing, the edition comes only from a `source` value on the exact
`https://www.epo.org/en/legal/<book>/<year>` path; other values stay `unknown`.
`current` selects the installed snapshot, and other versions fail.

Unlike MPEP's legacy `current` label, these years are concrete edition labels,
so they are not reported as unknown. They are still unverified:
`release_verified` is always `false`. No EPO release check exists in this port.
The installed snapshots (all built May 14, 2026) record EPC 2020, Case Law
2022, Guidelines 2024, PCT-EPO Guidelines 2024 and UP Guidelines 2026. Nobody
has checked whether EPO has since published later Guidelines or Case Law
editions, or whether the year-specific URLs served the requested edition.

## Prepare, package and verify local artifacts

Building fresh corpora from epo.org was out of scope for this slice. The
existing Python builders (`patent-client-agents-build-epc-corpus` and its
siblings) remain the acquisition path. The MPEP preparation script is
outline-generic and works unchanged for these books. From `typescript/`:

```sh
mkdir -p .data/epo-legal
for name in epc caselaw guidelines pct_guidelines up_guidelines; do
  uv run --frozen --no-sync python scripts/prepare-mpep-corpus.py \
    --input "$HOME/.cache/patent_client_agents/$name.db" \
    --output ".data/epo-legal/$name.db"
  bun scripts/compress-corpus.ts \
    --input ".data/epo-legal/$name.db" \
    --output ".data/epo-legal/$name.db.zst"
done
bun run verify:epo-legal --dir .data/epo-legal
```

The preparation script's JSON output reports `source_version: unknown` because
it reads MPEP's key. The edition years are preserved in metadata unchanged.
Its error messages also say "MPEP"; those labels are cosmetic.

On October 21, 2026 this sequence ran against the local May 14 snapshots. The
verifier configured each packaged file and both pins, then exercised the library
and the default MCP server. The results:

| Book | Sections | Prepared bytes | Zstandard bytes | Decoded SHA-256 |
| --- | --- | --- | --- | --- |
| EPC 2020 | 356 | 1,540,096 | 604,119 | `edd3b7d40d5383400961f92291cd284cd0821e6350b791c926183466cef8f628` |
| Case Law 2022 | 2,631 | 21,151,744 | 8,808,711 | `c0054ee284e467b2b7109b57b5840fd5b72ae4189e2ca5dfc485cd50ae27b087` |
| Guidelines 2024 | 1,771 | 6,275,072 | 2,453,326 | `6589efe366740d429b0fc8cca0623c403bb4c03b9505c4fedcd42f500516f33d` |
| PCT-EPO Guidelines 2024 | 756 | 1,826,816 | 667,742 | `80216f4a743e35dd241e5ad4eda507211651542f670e5544fd6bf7ad347a2fe4` |
| UP Guidelines 2026 | 142 | 663,552 | 374,684 | `e28802ba804d98de7f77d75c0fa3c420da034c53132664becfb8be8050225bff` |

The artifacts stay under ignored `.data/` and were not deployed. Configure
artifacts by absolute path with both pins from each packaging manifest.

## Known source-data limits

The crawled text runs heading words into preceding numbers. For example, Article
54 is stored as `Article 5442, 43Novelty`, so FTS indexes `43novelty` instead of
`novelty`, and a search for "novelty" misses the Article 54 heading. The
defect is in the Python-built artifacts, not the reader. The port does not
rewrite stored text; fixing it belongs in the builders.

Python returned an empty snippet for EPC, Case Law and Guidelines hits and a
title for PCT-EPO and UP hits. The TypeScript tools return the FTS snippet for
all five books.

## Tests

[Fixtures](../tests/fixtures/epo-legal/README.md) hold three or four real rows
per book, copied read-only from the local snapshots with their compressed HTML
and dictionaries. [Library tests](../tests/epo-legal-client.test.ts) cover
search, every citation form, decoded HTML hashes, editions, metadata gaps,
untrusted source paths, missing/WAL/pinned artifacts and environment
configuration. [MCP tests](../tests/epo-legal-mcp.test.ts) cover the actual
tools, cursors, missing entries, HTML artifacts, status resources and the
`epo:read` scope on the authenticated HTTP listener. All run offline.

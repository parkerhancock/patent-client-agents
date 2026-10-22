# IPO India statutes and MPPP

October 22, 2026. The TypeScript library reads the two Indian Patent Office
corpora of the Python package: the IP statutes (Patents Act 1970, Patent Rules
2003, Designs Act 2000, Trade Marks Act 1999, Copyright Act 1957) and the
Manual of Patent Office Practice and Procedure (MPPP v3.0, 2019). Both are
offline SQLite/FTS5 snapshots read through the same verified-artifact lifecycle
as [MPEP](mpep.md) and the [UPC statutes](upc-statutes.md). No API key is
needed. The MCP adapter uses a separate `ipoin:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `IpoInStatutesClient` | `search_ipo_in_statutes`, `get_ipo_in_section` | `ipo-in-statutes://corpus/status` | `IPO_IN_STATUTES_CORPUS_PATH` |
| `IpoInMpppClient` | `search_ipo_in_mppp`, `get_ipo_in_mppp_section` | `ipo-in-mppp://corpus/status` | `IPO_IN_MPPP_CORPUS_PATH` |

Tool names and parameters (`query`, `statute`, `limit`, `offset`, `syntax`,
`sort`, `full` for search; `citation` as a string or list for get), the path
variables and the default file names
(`~/.cache/patent_client_agents/ipo_in_statutes.db`, `ipo_in_mppp.db`) match
Python. `<PREFIX>_CORPUS_SHA256` pins the decoded SQLite bytes and
`<PREFIX>_CORPUS_FILE_SHA256` the distributed file. Python's usage-text
resources (`resource://ipo_in_*/usage`) were never registered on its MCP
server and are not ported.

The curated facade routes `search_legal_reference` / `get_legal_reference`
with `corpus='india_statutes'` and `'india_mppp'` to the same functions, so
results keep the India hit shape (`statute_name`, `section_number`, `title`,
`snippet`; MPPP adds `chapter`) and summaries, as the Python facade forwards
the per-corpus envelope verbatim. The `statute` filter applies to
`india_statutes` only.

## Where the corpus comes from

The runtime never fetches or rebuilds anything. In Python, both builders read
only the JSON seeds bundled in the package
(`src/patent_client_agents/ipo_in_statutes/data/seed.jsonl`, 26 sections;
`ipo_in_mppp/data/seed.jsonl`, 12 sections). There is no crawler. The deploy
repository's Dockerfile copies only the UPC statutes database, its bootstrap
manifest at `gs://patentclient-mcp-corpora/manifest.json` lists the eight
outline corpora and no India corpus, and the deploy image never runs the India
builders. On October 22 the deployed facade answered
`search_legal_reference(corpus='india_statutes')` with "IPO India statutes
corpus not found at /home/law-tools/.cache/patent_client_agents/ipo_in_statutes.db".
So the deployed Python server serves nothing for India, and there is no
deployed artifact to reuse.

The artifacts for this port are therefore the Python builders' output from
their seeds, built locally at commit `53a07989`, then prepared and packaged.
From `typescript/`:

```sh
mkdir -p .data/ipo-in/build
uv run --project .. --frozen patent-client-agents-build-ipo-in-statutes-corpus \
  --output .data/ipo-in/build/ipo_in_statutes.db
uv run --project .. --frozen patent-client-agents-build-ipo-in-mppp-corpus \
  --output .data/ipo-in/build/ipo_in_mppp.db
for name in ipo_in_statutes ipo_in_mppp; do
  uv run --project .. --frozen --no-sync python scripts/prepare-mpep-corpus.py \
    --input .data/ipo-in/build/$name.db --output .data/ipo-in/$name.db
  bun scripts/compress-corpus.ts \
    --input .data/ipo-in/$name.db --output .data/ipo-in/$name.db.zst
done
bun run verify:ipo-in \
  --statutes .data/ipo-in/ipo_in_statutes.db.zst \
  --mppp .data/ipo-in/ipo_in_mppp.db.zst
```

The builders write WAL-mode files, so the generic preparation script backs
them up into DELETE journal mode (its "MPEP" wording is cosmetic here). The
build date becomes `meta.snapshot_date`; a rebuild from the same seed changes
that date and therefore the hashes, not the content.

| Corpus | Seed SHA-256 | Rows | Prepared bytes | Zstandard bytes | Decoded SHA-256 | File SHA-256 |
| --- | --- | --- | --- | --- | --- | --- |
| Statutes | `efbee2e3…3fba83` | 26 | 86,016 | 18,421 | `229ff9cba90ab13cdb86391cc79222fa72f8a2584fab7809848a94a93b4a42d8` | `53ed3cc88065e89d254474b57fbf34f817d9ce2a5967b87996e64aee7be81c2d` |
| MPPP | `c40fb9f0…5e7160` | 12 | 57,344 | 8,260 | `856b91aa136641e71f508bfe3cce5d692345aeddf009c0a567c52ee29ba58884` | `3ed8f5ca76dfaec8f6f547a46c1b8739170cafcaf1d1b9a61089c53c10134e70` |

The artifacts stay under ignored `.data/ipo-in/` and were not deployed.
Because the complete corpora are this small, the prepared databases are also
the test fixtures (`tests/fixtures/ipo-in/`).

## Source-data limits

These are properties of the Python seeds, carried over unchanged:

- The seeds are short excerpts (about 260 to 500 characters per row), not the
  full Acts or manual. The statutes seed covers 26 hand-picked sections; the
  MPPP seed 12.
- The MPPP seed does not match MPPP v3.0. The official PDF
  (`ipindia.gov.in/.../Manual_for_Patent_Office_Practice_and_Procedure_.pdf`,
  downloaded with a plain request on October 22, 1,658,264 bytes, SHA-256
  `73d52f8b8073d3d0699f5e99a321d0428646b7d3bb80fb51abebca6db9fbb311`,
  "Version 3.0, 26th November, 2019") numbers its chapters differently: 04 is
  Publication of Application, 05.04 is Priority of Claim, 07.02 is
  International Application under PCT, examination is Chapter 09 and
  compulsory licensing Chapter 14. The seed instead labels 04.05 as the FER,
  05.04 as post-grant opposition and 07.02 as Form 27. The opening words of
  none of the twelve seed texts appear in the PDF's extracted text; two share
  a short later phrase with it. Treat MPPP
  citations and text from this corpus as unverified paraphrase.
- The statute texts read as abridged excerpts of the official wording (for
  example §2 gives only clauses (j) and (ja)). They were not checked against
  India Code: `indiacode.nic.in` redirects to `www.indiacode.nic.in`, which
  did not answer plain requests within 40 seconds. No other access method was
  tried.
- Stored source URLs are partly wrong: the Designs Act and the Trade Marks Act
  rows share India Code handle `123456789/1993`, and the two ipindia.gov.in
  pages used for §3(d) and the Patent Rules return 404. The port reports the
  stored URLs as they are.

Rebuilding from the official sources would need a new builder (India Code
pages for the Acts and Rules, the MPPP PDF for the manual); none exists in
either language.

## Behavior and Python bugs fixed

Search matches Python: BM25 rank, the same `<mark>` snippets (40 tokens),
`limit + 1` paging and the same lean projection (snippets cut at 400
characters). The verifier compared 12 searches and 10 gets with the Python
clients over the same databases with no difference. Ties in rank fall back
to row order. Python behavior the port corrects:

1. FTS5 operators ran from caller text. Python quoted only tokens with
   punctuation, so `infringement OR zzz` returned four hits and a bare `NOT`
   raised an FTS5 syntax error. Every term is now quoted text; `syntax='or'`
   is the way to widen.
2. Outline sort was lexicographic (`107A`, `122`, `146`, `2`, `25(1)`, …).
   It is now natural section order within each Act (`2`, `3`, `3(d)`, `8`,
   `25(1)`, …), applied before paging.
3. Citation parsing rejected or mis-resolved common forms: `§107A` raised
   "could not parse" (the tool description advertises it);
   `Section 25(2) of the Patents Act, 1970` looked up an Act named
   "Patents Act, 1970"; `Section 3(d) of Patents Act` looked up "of Patents
   Act"; `Patents Act section 3` failed. All now resolve. Statute names ignore
   case, punctuation, a leading "the" and a trailing year, and accept singular
   spellings ("Patent Act", "Trade Mark Act").
4. Section numbers were case-sensitive (`107a` was not found). They now match
   case-insensitively, and spaces inside `3 (d)` are ignored.
5. A `Rule N` citation without an Act searched every Act, so `Rule 13`
   returned Copyright Act section 13. It now means the Patent Rules.
6. MPPP references had to use the stored two-digit form; `MPPP 4.5.1` was not
   found. Unpadded components now match.

The MPPP status version is the stored `source_version` (`v3.0 (2019)`); the
statutes have none, so, as in Python, the version is `snapshot-<date>`. An
ambiguous bare number (`Section 2`, in both the Patents Act and the Trade
Marks Act) or an unparseable citation fails the whole call, as Python's
`ValueError` does, including inside a list; missing sections in a list go to
`not_found`, and a single missing string is an error. Section texts beyond a
32,000-character inline budget would be delivered as text artifacts, as the
other corpus tools do; no seed row comes close.

The facade's `syntax` parameter has no schema default. The Python facade
forwarded its own `'adj'` default to `india_statutes` although its
description says statute corpora default to all-terms matching; the port
applies `'and'` for `india_statutes` and `'adj'` for every other corpus when
the caller gives none.

## Tests

[Library tests](../tests/ipo-in-client.test.ts) cover citation and reference
parsing, status, search with and without the statute filter, natural outline
paging, FTS operator quoting, every seed row's text hash, Zstandard bytes,
missing, WAL, schema and pin failures, metadata gaps and the environment
variables. [MCP tests](../tests/ipo-in-mcp.test.ts) cover the four tools,
`not_found`, the status resources, the curated facade routing (including the
per-corpus syntax default) and the `ipoin:read` scope on the authenticated
HTTP listener. All run offline from the committed fixtures. The Node smoke run
reads the statutes fixture as Zstandard bytes and the browser smoke run the
MPPP fixture as bytes.
[`scripts/verify-ipo-in.ts`](../scripts/verify-ipo-in.ts) checks a packaged
pair against its manifests, the Python seeds and the Python clients, and calls
the default full and curated servers; `scripts/live-facade.ts` has four India
probes, which need the two path variables set.

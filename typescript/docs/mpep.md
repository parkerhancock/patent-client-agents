# MPEP corpus access

MPEP is the first TypeScript offline corpus connector. The Bun library reads a
verified SQLite/FTS5 snapshot, including dictionary-compressed HTML. Whole-file
Zstandard distribution follows the shared [corpus pattern](corpus-pattern.md). The MCP
adapter adds `search_mpep`, list-accepting `get_mpep_section`, and the protected
`mpep://corpus/status` resource. No office API key is needed. HTTP access uses
the existing `uspto:read` scope.

## Source release and freshness

The [official-source review](mpep-source-review.md) checked USPTO on October 20,
2026: Ninth Edition, Revision 01.2024 (`E9_R-01.2024`), published November 2024,
with a January 31, 2024 substantive cutoff. The separately archived subsequent
publications and five superseding memoranda are **not incorporated** into this
base-manual corpus. The subsequent-publications listing is current through July
20, 2026; that date is distinct from our October check.

Each corpus response distinguishes installed release, source sync/snapshot time,
access time, substantive cutoff and interim-update coverage. `current` means
the installed snapshot. Only that snapshot is retained; requests for another
release fail. Unknown/moving version labels remain `unknown`. A dated
`release_check` compares the artifact with the last verified base release; it
does not perform a live release check or establish present-day legal currency.

## Build a fresh artifact outside the runtime

The maintenance command reuses this repository's existing Python acquisition
and compression code. Python, lxml and zstandard are maintenance dependencies;
the TypeScript library and MCP service never start Python or crawl on demand.
Run from the repository root with its existing Python environment:

```sh
uv run --frozen --no-sync python typescript/scripts/build-mpep-corpus.py \
  --output typescript/.data/mpep/mpep.db
```

The builder discovers the pinned release's official table of contents, archives
its root responses, checks release identity and chapter coverage, and publishes
a standalone database plus `mpep.manifest.json`. It fails on missing responses,
insufficient budgets, changed releases or integrity failures instead of silently
publishing a partial crawl. Existing output files are not overwritten. Source
responses and the large artifact stay under ignored `.data/`; small compatibility
fixtures and the separate release-source archive are committed.

The manifest records the actual extraction scope and limitations. Numbered
sections and canonical root documents are not a promise of every possible
subsection granularity in appendices, form-paragraph books or indexes. Check
the recorded coverage before relying on a particular document type.

After building, package the standalone database with the Bun command in the
[corpus pattern](corpus-pattern.md). This preserves the decoded database hash
and all source freshness metadata. Keep the source database as a local rollback
copy; runtime needs only the compressed file and trusted configuration pins.

## Prepare an existing compressed Python artifact

The runtime accepts standalone SQLite files in DELETE journal mode. It rejects
WAL-mode headers with `CORPUS_WAL_UNSUPPORTED`: a checksum of the main file
cannot safely authenticate data replayed from an unpinned neighbouring WAL.
Do not patch SQLite header bytes or copy sidecars into runtime storage.

For an existing artifact, make a new standalone copy explicitly:

```sh
mkdir -p typescript/.data
uv run --frozen --no-sync python typescript/scripts/prepare-mpep-corpus.py \
  --input "$HOME/.cache/patent_client_agents/mpep.db" \
  --output typescript/.data/mpep-legacy-prepared.db
```

An optional `--sha256 HEX` checks the input pin. Preparation uses a read-only,
immutable view of the main file and intentionally excludes WAL changes. It
preserves section bytes, compression dictionaries and metadata, checks integrity,
and publishes without overwriting existing output. It reports a new artifact
SHA-256. It does not upgrade unknown release metadata or refresh old content.
For a database actively being written, publish a checked standalone artifact
from its owner rather than expecting this command to include pending WAL data.

## Use the library and MCP

From `typescript/`, configure an absolute artifact path and its manifest pin:

```sh
export MPEP_CORPUS_PATH="$PWD/.data/mpep/mpep.db.zst"
export MPEP_CORPUS_SHA256="THE_DECODED_SHA256_FROM_THE_PACKAGING_MANIFEST"
export MPEP_CORPUS_FILE_SHA256="THE_FILE_SHA256_FROM_THE_PACKAGING_MANIFEST"
bun run --cwd packages/mcp start
```

The library also accepts `corpusPath`, `expectedSha256` (decoded SQLite) and
`expectedFileSha256` (distributed file) directly. Both pins are optional for
legacy compatibility; configure both when distributing compressed artifacts. Explicit
options take precedence over environment values. Without a path, it uses the
existing Python cache location for compatibility; legacy WAL files still need
preparation. A missing artifact produces an unavailable status and a useful
error on queries, without downloading or creating a database.

```ts
import { MpepClient } from "@patent-client-agents/client";

const mpep = new MpepClient();
try {
  const status = await mpep.getCorpusStatus();
  const hits = await mpep.search({ query: "subject matter eligibility", limit: 5 });
  const section = await mpep.getSection("2106");
  const href = await mpep.resolveSectionHref("2106.04(a)");
  const installed = await mpep.listVersions();
} finally {
  mpep.close();
}
```

Search supports `adj`/`exact` phrases, `and`, `or`, relevance/outline sorting,
limit and offset. User terms are quoted as FTS text, not executed as raw MATCH
syntax. Section references accept numbers or stored eMPEP hrefs. The source URL,
decoded HTML SHA-256 and section revision travel with retrieved content.

MCP searches are lean by default. Cursors bind query options and artifact/build
identity. Section fetches preserve portfolio order; individual missing entries
are reported when other entries succeed. HTML and text exceeding the aggregate
inline budget use the existing protected artifact-download interface. HTTP
single-use links remain the default alongside authenticated REST.

## Runtime guarantees and limits

The reader hashes at most 256 MiB of file data, checks the file pin, decodes
whole-file Zstandard with a separate 256 MiB output bound when present, and
checks the decoded SQLite pin. It opens exactly those verified decoded bytes
as an immutable read-only in-memory SQLite database. It never opens a
second mutable path after verifying the hash, so path replacement and WAL
replay cannot substitute unverified content. Schema, section count and expected
FTS layout are validated before the artifact is available. A process keeps its
snapshot until closed/recreated; artifact publication does not hot-swap readers.

libzstd compiled to WebAssembly (`@bokuweb/zstd-wasm`) handles dictionary and
plain frames; dictionary cells must declare their decoded size, which is checked
against the limit before decoding. HTML plus text is limited to 16 MiB per section by
default (`maxSectionBytes` is explicit configuration). Both decoding and SQLite use third-party WebAssembly builds so the same
reader runs in every runtime ([runtimes](runtimes.md)); there is no Python
runtime bridge or native addon.
The in-memory snapshot costs memory proportional to the artifact; very large
corpora need a separately measured design rather than raising limits blindly.

Corpus provenance has `cache_hit: true`, source-time `retrieved_at`, current
`accessed_at`, `corpus_synced_at` and `corpus_version`. Unknown source times are
null. Date-only snapshot metadata remains visible in status and is represented
at UTC midnight without claiming a precise fetch time. Network provenance keeps
its existing non-null time and `cache_hit: false` contract.

Maintenance records `artifact_built_at` separately from source retrieval/sync
time. Rebuilding with `--from-archive` verifies the saved response hashes and
preserves their retrieval dates; it must not make old content appear freshly
fetched. The source-time range remains in artifact metadata and receipts.

## Verification

Ordinary tests use small committed SQLite fixtures with real schema and a real
legacy dictionary-compressed section. Tests cover pinning, WAL rejection,
path replacement, decompression limits, malformed schemas, FTS queries,
versions, freshness and actual MCP behavior. No tests silently crawl USPTO.

For a full local artifact check from `typescript/`:

```sh
bun run verify:mpep --corpus "$MPEP_CORPUS_PATH" \
  --sha256 "$MPEP_CORPUS_SHA256" --file-sha256 "$MPEP_CORPUS_FILE_SHA256"
```

This verifies library access, default MCP wiring, matching HTML artifact bytes
and cleanup. It prints verification metadata and the content hash, not section
text. Python maintenance tests are separate from `bun test`; run the focused
files under `typescript/scripts/test_*mpep*.py` when changing acquisition or
preparation. No production corpus, service or deployment is changed here.

The October 20 [build receipt](../references/mpep/corpus-build.json),
[source-response hashes](../references/mpep/corpus-sources.json) and
[validation receipt](../references/mpep/validation.json) record the local
3,055-row artifact and its pin. It passed library/default-MCP artifact checks
and network-disabled Linux ARM64/AMD64 reader checks. The existing compressed
legacy corpus also passed after explicit preparation and remained an unknown
release. Rebuilding may change artifact bytes and timestamps; use the new
manifest's pin rather than copying the historical validation pin.

Whole-file packaging reduced this snapshot from 48,697,344 to 17,014,840 bytes
(65.06% smaller), with the decoded database hash and source metadata unchanged.
The [packaging receipt](../references/mpep/corpus-package.json) records both
identities. The compressed file passed the same default MCP/artifact checks
and network-disabled Linux ARM64/AMD64 reader checks. The expanded database
remains a local rollback copy; runtime does not write an expanded file.

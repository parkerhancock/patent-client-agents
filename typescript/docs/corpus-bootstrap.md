# Corpus bootstrap

October 22, 2026. Phase 0 of the [shadow deploy plan](deploy-plan.md). Nothing
here has been uploaded; the publish script has only been run as a dry run.

A hosted TypeScript server reads twelve offline corpora. Each is a packaged
DELETE-journal SQLite file in one Zstandard frame, as the
[corpus pattern](corpus-pattern.md) describes. At container start the
bootstrap downloads them from Cloud Storage, checks both pins, and hands the
readers their paths and pins through environment variables. The TypeScript
manifest and objects live under a separate `ts/` prefix in
`gs://patentclient-mcp-corpora`, so the Python manifest and its blobs are
untouched.

## Manifest

`gs://patentclient-mcp-corpora/ts/manifest.json`:

```json
{
  "schema": "patent-client-agents.ts-corpora",
  "schema_version": 1,
  "generated_at": "2026-10-22T18:00:00.000Z",
  "corpora": {
    "epc": {
      "snapshot": "2026-05-14",
      "uri": "gs://patentclient-mcp-corpora/ts/epc/2026-05-14/epc.db.zst",
      "file": "epc.db.zst",
      "compression": "zstd",
      "file_sha256": "ddb2058b…",
      "file_bytes": 604119,
      "decoded_sha256": "edd3b7d4…",
      "decoded_bytes": 1540096,
      "metadata": { "schema_version": "1", "snapshot_date": "2026-05-14", "epc_year": "2020" }
    }
  }
}
```

The schema is strict: unknown top-level or entry keys, a different `schema`
or `schema_version`, malformed hashes, sizes above the readers' 256 MiB limit,
a `uri` that is not `gs://` or does not end in `file`, and corpus ids the
bootstrap does not know are all rejected. `snapshot` is the corpus's
`meta.snapshot_date`; `metadata` copies `schema_version`, `snapshot_date`,
`source_version` and any `*_year` key from the corpus `meta` table for
reference only. Corpus ids and the reader variables they set:

| Corpus id | Reader prefix |
| --- | --- |
| `mpep` | `MPEP` |
| `tmep` | `TMEP` |
| `ukipo_mopp` | `MOPP` |
| `epc` | `EPC` |
| `epo_case_law` | `CASELAW` |
| `epo_guidelines` | `GUIDELINES` |
| `epo_pct_guidelines` | `PCT_GUIDELINES` |
| `epo_up_guidelines` | `UP_GUIDELINES` |
| `upc_statutes` | `UPC_STATUTES` |
| `dpma_statutes` | `DPMA_STATUTES` |
| `ipo_in_statutes` | `IPO_IN_STATUTES` |
| `ipo_in_mppp` | `IPO_IN_MPPP` |

Each prefix yields `<PREFIX>_CORPUS_PATH`, `<PREFIX>_CORPUS_SHA256` (decoded
SQLite) and `<PREFIX>_CORPUS_FILE_SHA256` (distributed file). The mapping is
fixed in code rather than read from the manifest, so a manifest cannot set
arbitrary variables. Taiwan trade secrets is bundled in the client and needs
no corpus.

## Bootstrap

```ts
import { bootstrapCorpora } from "@patent-client-agents/client/corpus-bootstrap";

const env = await bootstrapCorpora(
  "gs://patentclient-mcp-corpora/ts/manifest.json",
  "/tmp/corpora",
  { log: console.log },
);
Object.assign(process.env, env); // before constructing the server
```

The module is server-only (Node and Bun) and is a separate package export. The
package index does not re-export it, so browser bundles of the client never
see it; the portability test checks this.

The bootstrap gets an access token, reads the manifest through the Cloud
Storage JSON API (`alt=media`, 1 MiB cap), validates it, and checks that every
requested corpus (all twelve by default, or `options.corpora`) has an entry.
Each artifact goes to `<cacheDir>/<corpus>/<snapshot>/<file>`. If a file is
already there, it is rehashed: file size and SHA-256, then a streaming
Zstandard decode for the decoded size and SHA-256. A match is reused without a
download. Otherwise the object is streamed to a temporary name in the same
directory (capped at `file_bytes`), verified the same way, and renamed into
place. The downloads run concurrently and all settle before the call returns
or throws, so no temporary file is left behind.

Every failure throws `CorpusBootstrapError` with a code: `MANIFEST_INVALID`,
`CORPUS_MISSING`, `AUTH_FAILED`, `DOWNLOAD_FAILED` or `VERIFICATION_FAILED`.
There is no retry and no fallback to a cached older snapshot. The container
crashes and Cloud Run restarts it, which is the retry. A cached file that fails
verification is not an error; it is replaced by a fresh download.

Tokens come from `options.auth`. The default, `auto`, uses
`GOOGLE_APPLICATION_CREDENTIALS` or gcloud's
`~/.config/gcloud/application_default_credentials.json` when that file exists
(authorized-user credentials only, refreshed at the OAuth token endpoint), and
otherwise the metadata server (`GCE_METADATA_HOST` or
`metadata.google.internal`), which is what Cloud Run uses. `metadata`, `adc`
or a function returning a token force one path. Only `fetch` is used; there is
no Google SDK. The runtime service account needs `storage.objects.get` on the
bucket.

The pins come from the manifest, so they detect corruption and truncation but
not a deliberate replacement of both the object and the manifest. Bucket write
access is the trust boundary, as it is for Python.

## Publishing

`scripts/publish-corpora.ts` reads the twelve packaged artifacts from
`.data/` at fixed paths (the table below), checks each against its packaging
manifest (`<file>.manifest.json`), decodes it, confirms DELETE journal mode,
reads `meta.snapshot_date`, and builds the manifest. It runs offline and
uploads nothing unless given `--execute`:

```sh
bun scripts/publish-corpora.ts                 # dry run: prints uploads and manifest
bun scripts/publish-corpora.ts --execute --gcloud-account parker.d.hancock@gmail.com
```

With `--execute`, each object is created with `ifGenerationMatch=0`. An
existing object with the same MD5 and size is skipped; one with different
bytes stops the publish, because a snapshot path is never rewritten. The
manifest is then written with `ifGenerationMatch` set to the generation read
just before the write (0 when absent). If another writer got there first,
Cloud Storage answers 412 and the publish fails without overwriting; rerun it.
The manifest always lists all twelve corpora from the local artifacts, so the
dry run shows exactly what would be written apart from `generated_at`.

To ship a new corpus build, package it with `scripts/compress-corpus.ts` at
the path below, run the dry run, review it, then run with `--execute`. Running
containers keep their files until restart.

## Artifacts

Prepared October 22, 2026. The five EPO books came from the deployed Python
blobs listed in `gs://patentclient-mcp-corpora/manifest.json`; each download
matched that manifest's SHA-256. The blobs are WAL-mode, so each was prepared
with `scripts/prepare-mpep-corpus.py --sha256 <python pin>` and packaged with
`scripts/compress-corpus.ts`. The decoded hashes equal the ones in
[EPO legal](epo-legal.md) from the local May 14 snapshots, so the deployed
blobs and those snapshots hold the same data. The other seven were copied from
the main checkout's `.data/`. MoPP had no packaging manifest there, so one was
written from the file; its hashes match [UKIPO MoPP](ukipo-mopp.md). Every
artifact passed its `verify:*` script (library and default MCP server), and a
local end-to-end run of the bootstrap against a fake bucket holding these
files left all twelve readers available from the returned variables.

| Corpus | Snapshot | Local path (`typescript/.data/`) | Compressed bytes | File SHA-256 | Decoded bytes | Decoded SHA-256 |
| --- | --- | --- | --- | --- | --- | --- |
| `mpep` | 2026-10-20 | `mpep/mpep.db.zst` | 17,014,840 | `3d862a00c26f5e0c169d41510fae52d5aa86b837df57340b961cfd06747268fa` | 48,697,344 | `1771226e8c16985058fc6673b8ee534e76a04b59d941abe166701b582f244060` |
| `tmep` | 2026-05-13 | `tmep/tmep.db.zst` | 3,316,287 | `398814bd370d146e5fbe9c8471564d4c828faea6b2ff359f559780be39ac780a` | 8,417,280 | `2d678fdf821fb94dd7aec66c738a91bc9cbffee2adb2a4e438abf48d8cd52aa8` |
| `ukipo_mopp` | 2026-05-14 | `ukipo_mopp/mopp.db.zst` | 2,560,203 | `d48e10116b928c76677137799da7dd9eadbd80a3643e5c82c2f21af61c3ea785` | 5,525,504 | `4bd204a2873034ecfc4078513dc81bdebf9c75c54330e46a1587486e9af4ddac` |
| `epc` | 2026-05-14 | `epo-legal/epc.db.zst` | 604,119 | `ddb2058b95b1bf93a5d6e6cf4371ff76b739fa645d4f66b67108fe692294efd8` | 1,540,096 | `edd3b7d40d5383400961f92291cd284cd0821e6350b791c926183466cef8f628` |
| `epo_case_law` | 2026-05-14 | `epo-legal/caselaw.db.zst` | 8,808,711 | `262f865448dea273ed50111d60480193d6827cabc4419f9a643be18efd6488b7` | 21,151,744 | `c0054ee284e467b2b7109b57b5840fd5b72ae4189e2ca5dfc485cd50ae27b087` |
| `epo_guidelines` | 2026-05-14 | `epo-legal/guidelines.db.zst` | 2,453,326 | `ad780ca486e8e77a81548e6a72bc5f54eaeb0e8659e4156bd6685645149bc14d` | 6,275,072 | `6589efe366740d429b0fc8cca0623c403bb4c03b9505c4fedcd42f500516f33d` |
| `epo_pct_guidelines` | 2026-05-14 | `epo-legal/pct_guidelines.db.zst` | 667,742 | `144f059678c20554fe8c652818f9a32dfd8aa2ed44fad4e4f82c75e47d008765` | 1,826,816 | `80216f4a743e35dd241e5ad4eda507211651542f670e5544fd6bf7ad347a2fe4` |
| `epo_up_guidelines` | 2026-05-14 | `epo-legal/up_guidelines.db.zst` | 374,684 | `4eddfc98ca4a104b573472b8fafbce12a71bdd7568365078e08f1bc4ee448fea` | 663,552 | `e28802ba804d98de7f77d75c0fa3c420da034c53132664becfb8be8050225bff` |
| `upc_statutes` | 2026-05-14 | `upc/upc_statutes.db.zst` | 652,442 | `8f8477f68912ba8fb42704cdac10cd55797794b968de55778cdea90e91dca50d` | 1,986,560 | `2d1fd1e1aadefe3fd6122cd3488acab80ddd14304eecb3efd5c6ea204fbac0b9` |
| `dpma_statutes` | 2026-10-22 | `dpma_statutes/dpma_statutes.db.zst` | 402,417 | `2a59048b1775ef370dcaf41f6196d3990e02412d50005a5af58fd390341bc83c` | 1,470,464 | `211bf701e26fb7f9719d0a20929596424711ae89e43130f30d220b8e74cefee2` |
| `ipo_in_statutes` | 2026-10-22 | `ipo-in/ipo_in_statutes.db.zst` | 388,487 | `96aeed06437c05bdaef4f943c7b1b81599dd6f315ee433d158fe151a8bf9f55f` | 1,404,928 | `82bfaea2cabe9dda467590bed2af231edafaf683308f69f09015ee72b5314671` |
| `ipo_in_mppp` | 2026-10-22 | `ipo-in/ipo_in_mppp.db.zst` | 199,121 | `00905acf0d481c4323fd8cd6ebb47915a49b7c55c515749c7b5a426770affe7d` | 688,128 | `b2e440776a7b45048ec20b37b5054d327cde309978cb87a4c2899911bc9f6b5b` |

Total: 37,442,379 bytes compressed (35.7 MiB) and 99,647,488 bytes decoded
(95.0 MiB). Baking the files into the image would add about 36 MB; the
bootstrap adds a download of the same size at cold start. Locally, against a
fake bucket, a full bootstrap took about 0.2 s and a verified rerun 0.15 s;
the time from Cloud Run to Cloud Storage has not been measured. Steady-state memory is the decoded size plus each
reader's in-memory SQLite copy once a corpus is opened, whichever way the files
arrive.

The EPO heading defect noted in [EPO legal](epo-legal.md) is present in the
deployed blobs: EPC Article 54 reads `Article 5442, 43Novelty`, a search for
`novelty` returns no hits and `43novelty` returns `a54`. It was not fixed
here; the fix belongs in the Python builders.

## Tests

[`tests/corpus-bootstrap.test.ts`](../tests/corpus-bootstrap.test.ts) runs
offline against a fake metadata server and a fake JSON API. It covers the
happy path with a real EPC fixture opened by `EpcClient` from the returned
variables, an idempotent rerun with no downloads, replacement of a corrupted
cached file, decoded and file SHA-256 mismatches, truncated and oversized
downloads, a missing manifest entry, object and manifest HTTP errors, manifest
schema and entry errors, metadata-server failures, application-default
user credentials, and the publish dry run (its manifest is served back and the
bootstrap accepts all twelve corpora). The Node smoke run imports the
bootstrap subpath from the built package and verifies a packaged fixture.

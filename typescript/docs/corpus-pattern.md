# Compressed corpus pattern

Ship a standalone SQLite/FTS5 snapshot as one Zstandard file. Decode it once
in memory and open the verified SQLite bytes read-only. MPEP is the reference
implementation; acquisition and schema-specific parsing stay in maintenance
commands outside requests.

## Artifact and identity

Use a single standard [Zstandard frame](https://github.com/facebook/zstd/blob/dev/doc/zstd_compression_format.md)
at level 9. Keep SQLite text columns readable by FTS5;
per-cell dictionary compression of HTML can remain inside the database. The
outer layer reduces storage and transfer without changing schema, search,
section content or release metadata.

The packaging manifest carries two identities:

| Field | Meaning |
| --- | --- |
| `sha256`, `bytes` | Decoded standalone SQLite bytes; stable across repackaging |
| `file_sha256`, `file_bytes` | Exact distributed file bytes |
| `compression` | `zstd` for the distributed file |
| `metadata` | Original source/build metadata, when a checked source manifest is supplied |

Configure both hashes from a trusted release manifest. Checksums detect changes;
they do not establish authenticity if an attacker can replace both the file and
its expected pins. Keep release pins under the same review as application
configuration. Runtime options remain optional for compatibility with existing
local SQLite use; an omitted pin is not verified.

For MPEP, `expectedSha256` / `MPEP_CORPUS_SHA256` pins the decoded SQLite database.
`expectedFileSha256` / `MPEP_CORPUS_FILE_SHA256` pins the distributed file. The
status fields `artifact_sha256`, `file_sha256` and `compression` expose observed
identity. Pagination remains bound to decoded corpus identity, so lossless
repackaging alone does not change the snapshot.

## Maintenance publication

First build or explicitly prepare a standalone database in DELETE journal mode.
Close the writer and verify SQLite integrity. Do not package a live database or
expect a neighbouring WAL to become part of the artifact.

From `typescript/`:

```sh
bun scripts/compress-corpus.ts \
  --input .data/mpep/mpep.db \
  --output .data/mpep/mpep.db.zst \
  --manifest .data/mpep/mpep.manifest.json
```

Packaging checks the source manifest's hash and size when supplied, verifies a
compression/decompression round trip, and publishes the compressed file and its
manifest (`OUTPUT.manifest.json`) without overwriting existing paths. Stage both files first, then activate the reviewed path and pins after
packaging succeeds. The original database remains available for rollback. Use the new packaging manifest for file pins.

Source retrieval dates, snapshot/sync dates, edition, revision and substantive
cutoff belong to the source snapshot. Compression must not update them. A new
packaging receipt does not imply a fresh source fetch, release check or inclusion
of subsequent guidance. Preserve unknown source metadata as unknown.

## Runtime lifecycle

The shared [outline reader](../packages/client/src/corpus/outline.ts) reads at
most 256 MiB of encoded bytes, checks the configured file pin before decoding,
and detects Zstandard by its frame magic rather than a filename extension.
The reader validates frame boundaries and rejects truncation, concatenated
frames and trailing bytes. Decoding uses libzstd compiled to WebAssembly, which
verifies frame checksums; frames without a declared size decode into a buffer
that doubles up to the same 256 MiB limit. The reader
checks the decoded pin before deserializing those same bytes into a read-only
SQLite WebAssembly database. Both run in Bun, Node and browsers
([runtimes](runtimes.md)). It rejects WAL headers and unsupported schema/FTS layouts. Nothing
writes an expanded database to disk or consults sidecars.

Open once per client, reuse the in-memory snapshot, and close it with its owner.
A new file publication does not hot-swap existing readers. Decompression runs
synchronously on first use; preload during service startup if that latency
matters. Peak memory includes compressed input, decoded buffers and SQLite's
in-memory snapshot. This pattern saves disk and transfer, not steady-state RAM.
Corpora approaching the limits need measurement and a separate design review.

## Proof required for another corpus

- Prove decoded hashes, section HTML, FTS snippets and source metadata match the
  standalone database, including existing dictionary-compressed content.
- Exercise encoded and decoded pin failures, malformed/truncated compression,
  size bounds, WAL rejection and open/close behavior with offline fixtures.
- Verify through the library and actual MCP adapter. Keep document downloads
  outside model context and preserve source provenance in both interfaces.

No Python subprocess, browser, decoder package or Rust/WASM module is required
at runtime. Future corpus schemas can reuse this lifecycle while retaining
schema-specific validation and retrieval methods.

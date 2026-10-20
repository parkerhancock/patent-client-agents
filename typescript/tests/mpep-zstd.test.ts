import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import {
  mkdtemp,
  readdir,
  readFile,
  rename,
  rmdir,
  truncate,
  unlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { constants, zstdCompressSync, zstdDecompressSync } from "node:zlib";
import {
  getMpepCorpusStatus,
  MpepClient,
} from "../packages/client/src/mpep.js";

const fixtures = join(import.meta.dir, "fixtures", "mpep");
const hash = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");
async function temporary(
  run: (directory: string, filename: string) => Promise<void>,
) {
  const directory = await mkdtemp(join(tmpdir(), "pca-mpep-zstd-"));
  try {
    await run(directory, join(directory, "corpus.db.zst"));
  } finally {
    for (const name of await readdir(directory))
      await unlink(join(directory, name));
    await rmdir(directory);
  }
}

// A valid, tiny RLE-block frame can exercise decoded limits without a large input allocation.
function rleFrame(size: number, includeSize: boolean) {
  const header = Buffer.alloc(includeSize ? 9 : 6);
  header.set([0x28, 0xb5, 0x2f, 0xfd]);
  header[4] = includeSize ? 0xa0 : 0;
  if (includeSize) header.writeUInt32LE(size, 5);
  else header[5] = 56; // 128 KiB window, independent of the total output size.
  const chunks = [header];
  for (let remaining = size; remaining > 0; ) {
    const length = Math.min(remaining, 128 * 1024);
    remaining -= length;
    const block = Buffer.alloc(4);
    block.writeUIntLE((length << 3) | 2 | Number(remaining === 0), 0, 3);
    chunks.push(block);
  }
  return Buffer.concat(chunks);
}

test("whole-file Zstandard loading preserves SQLite identity, inner dictionary HTML and metadata", async () => {
  await temporary(async (directory, filename) => {
    const decoded = await readFile(join(fixtures, "compressed.db"));
    const encoded = zstdCompressSync(decoded, {
      params: { [constants.ZSTD_c_checksumFlag]: 1 },
    });
    await writeFile(filename, encoded);
    const client = new MpepClient({
      corpusPath: filename,
      expectedSha256: hash(decoded),
      expectedFileSha256: hash(encoded),
    });
    try {
      const status = await client.getCorpusStatus();
      expect(status).toMatchObject({
        available: true,
        compression: "zstd",
        artifact_sha256: hash(decoded),
        file_sha256: hash(encoded),
        source_version: "unknown",
        snapshot_date: "2026-05-21",
        release_check: { comparison: "unknown" },
      });
      expect(status.file_sha256).not.toBe(status.artifact_sha256);
      expect((await client.getSection("2106")).content_sha256).toBe(
        "cd6d838cc1040617ffe3028a4741c2cec7000f9148c5e0977cf2e44a613d579c",
      );
      expect(
        (await client.search({ query: "patent", limit: 1 })).hits,
      ).toHaveLength(1);
      expect((await client.getSection("2106.99")).html).toBe(
        "<p>Uncompressed patent row.</p>",
      );
      expect(await readdir(directory)).toEqual(["corpus.db.zst"]);
      expect(hash(await readFile(filename))).toBe(hash(encoded));
    } finally {
      client.close();
    }
  });
});

test("plain and Zstandard artifacts permit either optional pin while validating both independently", async () => {
  await temporary(async (_directory, filename) => {
    const decoded = await readFile(join(fixtures, "plain.db"));
    for (const encoded of [decoded, zstdCompressSync(decoded)]) {
      await writeFile(filename, encoded);
      for (const pins of [
        {},
        { expectedSha256: hash(decoded) },
        { expectedFileSha256: hash(encoded) },
        { expectedSha256: hash(decoded), expectedFileSha256: hash(encoded) },
      ]) {
        const status = await getMpepCorpusStatus({
          corpusPath: filename,
          ...pins,
        });
        expect(status).toMatchObject({
          available: true,
          file_sha256: hash(encoded),
          artifact_sha256: hash(decoded),
          compression: encoded === decoded ? "none" : "zstd",
          release_check: { comparison: "matches_latest_checked" },
          interim_updates_coverage: "not_included",
        });
      }
      expect(
        (
          await getMpepCorpusStatus({
            corpusPath: filename,
            expectedFileSha256: "0".repeat(64),
            expectedSha256: hash(decoded),
          })
        ).error,
      ).toMatchObject({
        code: "CHECKSUM_MISMATCH",
        message: "Corpus file SHA-256 does not match its pin.",
      });
      expect(
        (
          await getMpepCorpusStatus({
            corpusPath: filename,
            expectedFileSha256: hash(encoded),
            expectedSha256: "0".repeat(64),
          })
        ).error,
      ).toMatchObject({
        code: "CHECKSUM_MISMATCH",
        message: "Corpus SHA-256 does not match its pin.",
      });
    }
  });
});

test("frame validation rejects truncation, garbage, extra frames, reserved flags and checksum damage", async () => {
  await temporary(async (_directory, filename) => {
    const decoded = await readFile(join(fixtures, "plain.db"));
    const encoded = zstdCompressSync(decoded, {
      params: { [constants.ZSTD_c_checksumFlag]: 1 },
    });
    const checksumDamage = Buffer.from(encoded);
    checksumDamage[checksumDamage.length - 1] =
      (checksumDamage[checksumDamage.length - 1] ?? 0) ^ 1;
    const reservedFlag = Buffer.from(encoded);
    reservedFlag[4] = (reservedFlag[4] ?? 0) | 8;
    for (const malformed of [
      encoded.subarray(0, 4),
      encoded.subarray(0, encoded.length - 1),
      encoded.subarray(0, encoded.length - 5),
      Buffer.concat([encoded, Buffer.from([1, 2, 3])]),
      Buffer.concat([encoded, encoded]),
      checksumDamage,
      reservedFlag,
    ]) {
      await writeFile(filename, malformed);
      const status = await getMpepCorpusStatus({
        corpusPath: filename,
        expectedFileSha256: hash(malformed),
      });
      expect(status.available).toBe(false);
      expect(status.error?.code).toBe("DECOMPRESSION_FAILED");
    }
  });
});

test("frames without content-size metadata decode, while known and unknown-size bombs stay bounded", async () => {
  expect(zstdDecompressSync(rleFrame(100, false))).toEqual(Buffer.alloc(100));
  await temporary(async (_directory, filename) => {
    const decoded = await readFile(join(fixtures, "plain.db"));
    await writeFile(
      filename,
      zstdCompressSync(decoded, {
        params: { [constants.ZSTD_c_contentSizeFlag]: 0 },
      }),
    );
    expect(
      (
        await getMpepCorpusStatus({
          corpusPath: filename,
          expectedSha256: hash(decoded),
        })
      ).available,
    ).toBe(true);
    for (const includeSize of [true, false]) {
      await writeFile(filename, rleFrame(257 * 1024 * 1024, includeSize));
      expect(
        (await getMpepCorpusStatus({ corpusPath: filename })).error?.code,
      ).toBe("CORPUS_TOO_LARGE");
    }
    await writeFile(filename, Buffer.from([0x28, 0xb5, 0x2f, 0xfd]));
    await truncate(filename, 257 * 1024 * 1024);
    expect(
      (await getMpepCorpusStatus({ corpusPath: filename })).error?.code,
    ).toBe("CORPUS_TOO_LARGE");
  });
});

test("compressed WAL snapshots remain rejected and loaded snapshots stay immutable across replacement", async () => {
  await temporary(async (directory, filename) => {
    const plain = await readFile(join(fixtures, "plain.db"));
    const mutable = join(directory, "mutable.db");
    await writeFile(mutable, plain);
    const db = new Database(mutable);
    db.exec("PRAGMA journal_mode = WAL; PRAGMA wal_checkpoint(TRUNCATE)");
    db.close();
    await writeFile(filename, zstdCompressSync(await readFile(mutable)));
    expect(
      (await getMpepCorpusStatus({ corpusPath: filename })).error?.code,
    ).toBe("CORPUS_WAL_UNSUPPORTED");
    const encoded = zstdCompressSync(plain);
    await writeFile(filename, encoded);
    const client = new MpepClient({
      corpusPath: filename,
      expectedSha256: hash(plain),
      expectedFileSha256: hash(encoded),
    });
    try {
      expect((await client.getCorpusStatus()).available).toBe(true);
      const replacement = join(directory, "replacement.zst");
      await writeFile(replacement, "not a corpus");
      await rename(replacement, filename);
      expect((await client.getSection("2106")).version).toBe("E9_R-01.2024");
      expect((await client.getCorpusStatus()).file_sha256).toBe(hash(encoded));
      client.close();
      expect((await client.getCorpusStatus()).error?.code).toBe(
        "CHECKSUM_MISMATCH",
      );
    } finally {
      client.close();
    }
  });
});

test("file pin environment fallback rejects empty configuration and explicit pins override it", async () => {
  const previous = process.env.MPEP_CORPUS_FILE_SHA256;
  const decoded = await readFile(join(fixtures, "plain.db"));
  try {
    process.env.MPEP_CORPUS_FILE_SHA256 = "";
    expect(
      () => new MpepClient({ corpusPath: join(fixtures, "plain.db") }),
    ).toThrow();
    process.env.MPEP_CORPUS_FILE_SHA256 = hash(decoded);
    expect(
      (await getMpepCorpusStatus({ corpusPath: join(fixtures, "plain.db") }))
        .available,
    ).toBe(true);
    process.env.MPEP_CORPUS_FILE_SHA256 = "0".repeat(64);
    expect(
      (
        await getMpepCorpusStatus({
          corpusPath: join(fixtures, "plain.db"),
          expectedFileSha256: hash(decoded),
        })
      ).available,
    ).toBe(true);
  } finally {
    if (previous === undefined) delete process.env.MPEP_CORPUS_FILE_SHA256;
    else process.env.MPEP_CORPUS_FILE_SHA256 = previous;
  }
});

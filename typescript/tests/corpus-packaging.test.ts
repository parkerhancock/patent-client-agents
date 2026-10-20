import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import {
  mkdtemp,
  open,
  readdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { zstdDecompressSync } from "node:zlib";
import { packageCorpus } from "../scripts/compress-corpus.js";

const hash = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

async function fixture() {
  const directory = await mkdtemp(join(tmpdir(), "pca-corpus-package-"));
  const input = join(directory, "source.db");
  const output = join(directory, "source.db.zst");
  const db = new Database(input, { create: true });
  try {
    db.exec("PRAGMA journal_mode=DELETE; CREATE TABLE sample(text TEXT)");
    db.query("INSERT INTO sample VALUES (?)").run(
      "Unicode corpus € 日 ".repeat(100),
    );
  } finally {
    db.close();
  }
  return {
    directory,
    input,
    output,
    async close() {
      await rm(directory, { recursive: true });
    },
  };
}

test("whole-file packaging preserves exact SQLite bytes, pins and old freshness metadata", async () => {
  const api = await fixture();
  try {
    const original = await readFile(api.input);
    const source = {
      file: "source.db",
      sha256: hash(original),
      bytes: original.length,
      source_last_retrieved_at: "2024-11-01T14:15:00+00:00",
      artifact_built_at: "2026-10-20T00:00:00+00:00",
      metadata: {
        synced_at: "2024-11-01T14:15:00+00:00",
        snapshot_date: "2024-11-01",
        source_version: "historical-release",
        custom: "retained",
      },
      unknown_source_fields: { empty: "", enabled: false },
    };
    const manifestPath = join(api.directory, "source.manifest.json");
    await writeFile(manifestPath, JSON.stringify(source));
    const result = await packageCorpus({
      input: api.input,
      output: api.output,
      manifest: manifestPath,
    });
    const compressed = await readFile(api.output);
    expect(zstdDecompressSync(compressed)).toEqual(original);
    expect(await readFile(api.input)).toEqual(original);
    expect(result).toMatchObject({
      file: "source.db.zst",
      compression: "zstd",
      sha256: source.sha256,
      bytes: original.length,
      decoded_sha256: source.sha256,
      decoded_bytes: original.length,
      file_sha256: hash(compressed),
      file_bytes: compressed.length,
      metadata: source.metadata,
      source_last_retrieved_at: source.source_last_retrieved_at,
      artifact_built_at: source.artifact_built_at,
      unknown_source_fields: source.unknown_source_fields,
    });
    expect(
      JSON.parse(await readFile(`${api.output}.manifest.json`, "utf8")),
    ).toEqual(result);
    expect(compressed.length).toBeLessThan(original.length);
  } finally {
    await api.close();
  }
});

test("source manifest mismatch or malformed metadata cannot be trusted or published", async () => {
  const api = await fixture();
  try {
    const bytes = await readFile(api.input);
    const manifest = join(api.directory, "source.manifest.json");
    for (const value of [
      { sha256: "0".repeat(64), bytes: bytes.length },
      { sha256: hash(bytes), bytes: bytes.length + 1 },
      { sha256: hash(bytes) },
      [],
      "invalid JSON",
    ]) {
      await writeFile(
        manifest,
        value === "invalid JSON" ? value : JSON.stringify(value),
      );
      await expect(
        packageCorpus({ input: api.input, output: api.output, manifest }),
      ).rejects.toThrow("Source manifest hash/size");
      expect(await readdir(api.directory)).not.toContain("source.db.zst");
      expect(await readdir(api.directory)).not.toContain(
        "source.db.zst.manifest.json",
      );
    }
  } finally {
    await api.close();
  }
});

test("existing output or output manifest is never overwritten", async () => {
  for (const suffix of ["", ".manifest.json"]) {
    const api = await fixture();
    try {
      await writeFile(`${api.output}${suffix}`, "preserve me");
      await expect(
        packageCorpus({ input: api.input, output: api.output }),
      ).rejects.toThrow("already exists");
      expect(await readFile(`${api.output}${suffix}`, "utf8")).toBe(
        "preserve me",
      );
      expect(
        (await readdir(api.directory)).filter((name) =>
          name.startsWith(".corpus-package-"),
        ),
      ).toEqual([]);
    } finally {
      await api.close();
    }
  }
});

test("concurrent publication leaves exactly one verified artifact and no staging files", async () => {
  const api = await fixture();
  try {
    const results = await Promise.allSettled([
      packageCorpus({ input: api.input, output: api.output }),
      packageCorpus({ input: api.input, output: api.output }),
    ]);
    expect(results.filter((item) => item.status === "fulfilled")).toHaveLength(
      1,
    );
    expect(results.filter((item) => item.status === "rejected")).toHaveLength(
      1,
    );
    expect(zstdDecompressSync(await readFile(api.output))).toEqual(
      await readFile(api.input),
    );
    expect(
      (await readdir(api.directory)).filter((name) =>
        name.startsWith(".corpus-package-"),
      ),
    ).toEqual([]);
  } finally {
    await api.close();
  }
});

test("WAL, invalid SQLite and oversized inputs fail before publication", async () => {
  const api = await fixture();
  try {
    const original = await readFile(api.input);
    const wal = Buffer.from(original);
    wal[18] = 2;
    wal[19] = 2;
    for (const [name, body, message] of [
      ["wal.db", wal, "DELETE-mode"],
      ["invalid.db", Buffer.from("not SQLite"), "standalone SQLite"],
      ["truncated.db", original.subarray(0, original.length / 2), "integrity"],
    ] as const) {
      const input = join(api.directory, name);
      await writeFile(input, body);
      await expect(
        packageCorpus({ input, output: api.output }),
      ).rejects.toThrow(message);
    }
    const input = join(api.directory, "too-large.db");
    const file = await open(input, "wx");
    try {
      await file.truncate(256 * 1024 * 1024 + 1);
    } finally {
      await file.close();
    }
    await expect(packageCorpus({ input, output: api.output })).rejects.toThrow(
      "size limit",
    );
    expect(await readdir(api.directory)).not.toContain("source.db.zst");
  } finally {
    await api.close();
  }
});

import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { copyFile, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  DPMA_STATUTES_SOURCE_URL,
  DpmaStatutesClient,
  parseDpmaCitation,
  resolveDpmaStatute,
} from "../packages/client/src/dpma-statutes.js";
import { CorpusProvenanceSchema } from "../packages/client/src/models.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "dpma-statutes",
  "dpma_statutes.db",
);
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");

async function withCopy(sql: string, run: (filename: string) => Promise<void>) {
  const directory = await mkdtemp(join(tmpdir(), "pca-dpma-statutes-test-"));
  const filename = join(directory, "dpma_statutes.db");
  await copyFile(fixture, filename);
  const db = new Database(filename);
  try {
    db.exec(sql);
  } finally {
    db.close();
  }
  try {
    await run(filename);
  } finally {
    await rm(directory, { recursive: true });
  }
}
const code = async (promise: Promise<unknown>) => {
  try {
    await promise;
  } catch (error) {
    return error instanceof CorpusError ? error.code : String(error);
  }
  return "resolved";
};

test("citations parse as Python does, plus German subdivisions and bare-number Act forms", () => {
  expect(parseDpmaCitation("§ 1 PatG")).toEqual({
    section: "1",
    statute: "PatG",
  });
  expect(parseDpmaCitation("§ 139 PatG")).toEqual({
    section: "139",
    statute: "PatG",
  });
  expect(parseDpmaCitation("Section 14 MarkenG")).toEqual({
    section: "14",
    statute: "MarkenG",
  });
  expect(parseDpmaCitation("Sec. 14 of the Trade Mark Act")).toEqual({
    section: "14",
    statute: "MarkenG",
  });
  expect(parseDpmaCitation("S. 139 PatG")).toEqual({
    section: "139",
    statute: "PatG",
  });
  expect(parseDpmaCitation("§5 geschgehg")).toEqual({
    section: "5",
    statute: "GeschGehG",
  });
  expect(parseDpmaCitation("139")).toEqual({ section: "139", statute: null });
  // Python fails these; the section is returned whole.
  expect(parseDpmaCitation("§ 139 Abs. 1 PatG")).toEqual({
    section: "139",
    statute: "PatG",
  });
  expect(parseDpmaCitation("§ 2 Nr. 1 GeschGehG")).toEqual({
    section: "2",
    statute: "GeschGehG",
  });
  expect(parseDpmaCitation("139 PatG")).toEqual({
    section: "139",
    statute: "PatG",
  });
  expect(parseDpmaCitation("§ 16A PatG").section).toBe("16a");
  // Unknown Acts pass through, so the lookup reports not found.
  expect(parseDpmaCitation("§ 1 BGB").statute).toBe("BGB");
  expect(() => parseDpmaCitation("Article 54 EPC")).toThrow(
    "Could not parse citation",
  );
  expect(resolveDpmaStatute(" Geschäftsgeheimnisgesetz ")).toBe("GeschGehG");
  expect(resolveDpmaStatute("copyright act")).toBe("UrhG");
});

test("DPMA status, sections and search come from the Python-built corpus", async () => {
  const before = hash(await readFile(fixture));
  const client = new DpmaStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "DPMA statutes",
      corpus_version: "snapshot-2026-10-22",
      schema_version: 1,
      section_count: 12,
      snapshot_date: "2026-10-22",
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
      compression: "none",
      source_url: DPMA_STATUTES_SOURCE_URL,
      metadata: { section_count: "12" },
    });
    expect(status.artifact_sha256).toBe(before);
    expect(await client.listStatutes()).toEqual([
      "DesignG",
      "GebrMG",
      "GeschGehG",
      "MarkenG",
      "PatG",
      "UrhG",
    ]);

    const section = await client.getSectionByCitation("§ 139 PatG");
    expect(section).toMatchObject({
      statute: "PatG",
      section: "139",
      title: "Unterlassungs- und Schadensersatzanspruch",
    });
    expect(section.text).toStartWith("(1) Wer entgegen den §§ 9 bis 13");
    expect(CorpusProvenanceSchema.parse(section.provenance)).toMatchObject({
      source_url: DPMA_STATUTES_SOURCE_URL,
      source_name: "DPMA Germany — IP statutes",
      corpus_version: "snapshot-2026-10-22",
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
    });
    expect((await client.getSection("97")).statute).toBe("UrhG");
    expect(
      (await client.getSection("1", { statute: "Gebrauchsmustergesetz" }))
        .statute,
    ).toBe("GebrMG");
    expect(await code(client.getSection("1"))).toBe("AMBIGUOUS_SECTION");
    await expect(client.getSection("1")).rejects.toThrow(
      "exists in: DesignG, GebrMG, GeschGehG, PatG, UrhG",
    );
    expect(await code(client.getSection("999"))).toBe("SECTION_NOT_FOUND");
    expect(await code(client.getSectionByCitation("§ 1 BGB"))).toBe(
      "SECTION_NOT_FOUND",
    );
    await expect(client.getSectionByCitation("§ 4 PatG")).rejects.toThrow(
      "Section '4' not found in 'PatG'.",
    );
    expect(await code(client.getSectionByCitation("Article 54"))).toBe(
      "INVALID_CITATION",
    );

    const hits = await client.search({ query: "Unterlassung" });
    expect(hits.statute).toBeNull();
    expect(
      hits.hits.map((hit) => `${hit.statute} ${hit.section}`).sort(),
    ).toEqual(["PatG 139", "UrhG 97"]);
    expect(hits.hits[0]).toEqual({
      statute: expect.any(String),
      section: expect.any(String),
      title: expect.any(String),
      snippet: expect.stringContaining("<mark>Unterlassung</mark>"),
      rank: expect.any(Number),
    });
    const patg = await client.search({
      query: "Unterlassung",
      statute: "patentgesetz",
    });
    expect(patg.statute).toBe("PatG");
    expect(patg.hits.map((hit) => hit.section)).toEqual(["139"]);
    expect(
      (await client.search({ query: "Unterlassung", statute: "BGB" })).hits,
    ).toEqual([]);

    // 'and' (default) needs every term; 'or' any; 'adj' the phrase.
    expect(
      (await client.search({ query: "Erfindung Gebrauchsmuster" })).hits,
    ).toEqual([]);
    expect(
      (
        await client.search({
          query: "Erfindung Gebrauchsmuster",
          syntax: "or",
        })
      ).hits.length,
    ).toBeGreaterThan(1);
    expect(
      (
        await client.search({
          query: "erfinderischen Tätigkeit",
          syntax: "adj",
        })
      ).hits.map((hit) => `${hit.statute} ${hit.section}`),
    ).toEqual(["PatG 1"]);

    // Outline order is numeric within an Act (Python sorts "139" before "3").
    const outline = await client.search({
      query: "Erfindungen Erfindung Verletzten",
      syntax: "or",
      sort: "outline",
      statute: "PatG",
    });
    expect(outline.hits.map((hit) => hit.section)).toEqual(["1", "3", "139"]);

    const first = await client.search({
      query: "Gesetzes",
      syntax: "or",
      limit: 1,
    });
    const second = await client.search({
      query: "Gesetzes",
      syntax: "or",
      limit: 1,
      offset: 1,
    });
    expect(first.has_more).toBe(true);
    expect(second.hits).toHaveLength(1);
    expect(second.hits[0]).not.toEqual(first.hits[0]);
    expect((await client.search({ query: "   " })).hits).toEqual([]);
  } finally {
    client.close();
  }
  expect(hash(await readFile(fixture))).toBe(before);
});

test("FTS5 operators in queries are matched as text, not syntax", async () => {
  const client = new DpmaStatutesClient({ corpusPath: fixture });
  try {
    // Python leaves bare words unquoted: NOT alone is an FTS5 syntax error and
    // OR in 'and' mode turns into a disjunction.
    expect((await client.search({ query: "NOT" })).hits).toEqual([]);
    expect(
      (await client.search({ query: "Unterlassung OR Marke" })).hits,
    ).toEqual([]);
    expect(
      (await client.search({ query: 'statute:PatG "Neuheit' })).hits,
    ).toEqual([]);
  } finally {
    client.close();
  }
});

test("Zstandard bytes, pins and the environment variables configure the reader", async () => {
  const bytes = new Uint8Array(await readFile(fixture));
  const compressed = new Uint8Array(zstdCompressSync(bytes));
  const fromBytes = new DpmaStatutesClient({
    source: compressed,
    expectedSha256: hash(bytes),
    expectedFileSha256: hash(compressed),
  });
  try {
    const status = await fromBytes.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      compression: "zstd",
      artifact_sha256: hash(bytes),
      file_sha256: hash(compressed),
    });
  } finally {
    fromBytes.close();
  }
  const wrongPin = new DpmaStatutesClient({
    corpusPath: fixture,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrongPin.getCorpusStatus()).error?.code).toBe(
    "CHECKSUM_MISMATCH",
  );
  expect(await code(wrongPin.search({ query: "Patente" }))).toBe(
    "CHECKSUM_MISMATCH",
  );

  const saved = { ...process.env };
  try {
    process.env.DPMA_STATUTES_CORPUS_PATH = fixture;
    process.env.DPMA_STATUTES_CORPUS_SHA256 = hash(bytes);
    const fromEnv = new DpmaStatutesClient();
    expect((await fromEnv.getCorpusStatus()).available).toBe(true);
    fromEnv.close();
    process.env.DPMA_STATUTES_CORPUS_PATH = join(tmpdir(), "missing-dpma.db");
    const missing = await new DpmaStatutesClient().getCorpusStatus();
    expect(missing).toMatchObject({
      available: false,
      corpus_version: "unknown",
      corpus_synced_at: null,
      section_count: null,
      error: { code: "CORPUS_UNAVAILABLE" },
    });
    expect(missing.error?.message).toContain("DPMA_STATUTES_CORPUS_PATH");
    expect(
      () =>
        new DpmaStatutesClient({ corpusPath: fixture, expectedSha256: "x" }),
    ).toThrow();
  } finally {
    process.env = saved;
  }
});

test("WAL files, other schemas and metadata gaps are reported, not guessed", async () => {
  const directory = await mkdtemp(join(tmpdir(), "pca-dpma-wal-"));
  try {
    const wal = join(directory, "wal.db");
    const bytes = new Uint8Array(await readFile(fixture));
    bytes[18] = 2;
    bytes[19] = 2;
    await writeFile(wal, bytes);
    expect(
      (await new DpmaStatutesClient({ corpusPath: wal }).getCorpusStatus())
        .error?.code,
    ).toBe("CORPUS_WAL_UNSUPPORTED");
  } finally {
    await rm(directory, { recursive: true });
  }
  await withCopy(
    "UPDATE meta SET value = '2' WHERE key = 'schema_version'",
    async (filename) => {
      expect(
        (
          await new DpmaStatutesClient({
            corpusPath: filename,
          }).getCorpusStatus()
        ).error?.code,
      ).toBe("UNSUPPORTED_SCHEMA");
    },
  );
  await withCopy("DROP TABLE sections_fts", async (filename) => {
    expect(
      (await new DpmaStatutesClient({ corpusPath: filename }).getCorpusStatus())
        .error?.code,
    ).toBe("INVALID_CORPUS");
  });
  await withCopy(
    "INSERT INTO meta VALUES ('source_version', '2026-annual'); UPDATE meta SET value = 'not-a-date' WHERE key = 'snapshot_date'",
    async (filename) => {
      const client = new DpmaStatutesClient({ corpusPath: filename });
      const status = await client.getCorpusStatus();
      expect(status).toMatchObject({
        corpus_version: "2026-annual",
        corpus_synced_at: null,
      });
      client.close();
    },
  );
  await withCopy(
    "INSERT INTO meta VALUES ('source_version', 'current'); DELETE FROM meta WHERE key = 'snapshot_date'",
    async (filename) => {
      const client = new DpmaStatutesClient({ corpusPath: filename });
      expect((await client.getCorpusStatus()).corpus_version).toBe("unknown");
      client.close();
    },
  );
});

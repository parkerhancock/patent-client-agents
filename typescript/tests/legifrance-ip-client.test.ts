import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { copyFile, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  LEGIFRANCE_IP_SOURCE_URL,
  LegifranceIpClient,
  normalizeLegifranceSection,
  parseLegifranceCitation,
} from "../packages/client/src/legifrance-ip.js";
import { CorpusProvenanceSchema } from "../packages/client/src/models.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "legifrance-ip",
  "legifrance_ip.db",
);
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");
const code = async (promise: Promise<unknown>) => {
  try {
    await promise;
  } catch (error) {
    return error instanceof CorpusError ? error.code : String(error);
  }
  return "resolved";
};
async function withCopy(sql: string, run: (filename: string) => Promise<void>) {
  const directory = await mkdtemp(join(tmpdir(), "pca-legifrance-test-"));
  const filename = join(directory, "legifrance_ip.db");
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

test("citations parse as Python's parse_citation does, plus long names and bare numbers", () => {
  for (const [citation, statute, section] of [
    ["L. 611-10 CPI", "CPI", "L611-10"],
    ["Art. L. 611-10 CPI", "CPI", "L611-10"],
    ["Article L. 611-10 CPI", "CPI", "L611-10"],
    ["L611-10 CPI", "CPI", "L611-10"],
    ["L. 151-1 Code de commerce", "Code de commerce", "L151-1"],
    ["L 611.10 CPI", "CPI", "L611-10"],
    ["l. 611-10 cpi", "CPI", "L611-10"],
    ["L. 151-1 Code  de  commerce", "Code de commerce", "L151-1"],
    // Python rejects these.
    [
      "article L. 613-3 du code de la propriété intellectuelle",
      "CPI",
      "L613-3",
    ],
    ["L. 151-1 C. com.", "Code de commerce", "L151-1"],
    ["L. 615-5-1-1 CPI", "CPI", "L615-5-1-1"],
    ["L. 611-10", null, "L611-10"],
  ])
    expect(parseLegifranceCitation(citation as string)).toEqual({
      statute: statute as "CPI" | "Code de commerce" | null,
      section: section as string,
    });
  for (const bad of ["not a citation", "611-10 CPI", "L. 611-10 Code civil"])
    expect(() => parseLegifranceCitation(bad)).toThrow(
      "could not parse citation",
    );
  expect(normalizeLegifranceSection("L611-10")).toBe("L611-10");
  expect(normalizeLegifranceSection("L. 611-10")).toBe("L611-10");
  expect(normalizeLegifranceSection("L 611.10")).toBe("L611-10");
});

test("status and articles come from the DILA LEGI build", async () => {
  const client = new LegifranceIpClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      corpus_version: "LEGI 20261021-213023",
      schema_version: 1,
      section_count: 13,
      snapshot_date: "2026-10-21",
      corpus_synced_at: "2026-10-21T00:00:00.000Z",
      compression: "none",
      source_url: LEGIFRANCE_IP_SOURCE_URL,
      codes: [
        {
          statute: "CPI",
          id: "LEGITEXT000006069414",
          title: "Code de la propriété intellectuelle",
          kept: "^L\\d",
          articles: 877,
        },
        {
          statute: "Code de commerce",
          id: "LEGITEXT000005634379",
          title: "Code de commerce",
          kept: "^L15[1-4]-",
          articles: 20,
        },
      ],
    });
    const article = await client.getSection("L. 611-10 CPI");
    expect(article).toMatchObject({
      statute: "CPI",
      section: "L611-10",
      title: "Section 3 : Inventions brevetables",
      article_id: "LEGIARTI000019298703",
      in_force_since: "2008-08-06",
      breadcrumb:
        "Partie législative > Deuxième partie : La propriété industrielle > Livre VI : Protection des inventions et des connaissances techniques > Titre Ier : Brevets d'invention > Chapitre Ier : Champ d'application > Section 3 : Inventions brevetables",
      url: "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000019298703",
    });
    expect(article.text).toStartWith(
      "1. Sont brevetables, dans tous les domaines technologiques, les inventions nouvelles impliquant une activité inventive et susceptibles d'application industrielle.",
    );
    expect(article.text.split("\n").length).toBeGreaterThan(3);
    expect(CorpusProvenanceSchema.parse(article.provenance)).toMatchObject({
      source_url: LEGIFRANCE_IP_SOURCE_URL,
      corpus_version: "LEGI 20261021-213023",
      cache_hit: true,
    });
    const secret = await client.getSection("Art. L. 151-1 Code de commerce");
    expect(secret.text).toStartWith(
      "Est protégée au titre du secret des affaires toute information répondant aux critères suivants :\n1° ",
    );
    expect(secret.breadcrumb).toContain(
      "Titre V : De la protection du secret des affaires",
    );
    expect((await client.getSection("L. 613-3")).statute).toBe("CPI");
    expect((await client.getBySectionNumber("CPI", "L. 711-1")).section).toBe(
      "L711-1",
    );
    expect(await code(client.getSection("L. 999-99 CPI"))).toBe(
      "SECTION_NOT_FOUND",
    );
    expect(await code(client.getSection("L. 151-1 CPI"))).toBe(
      "SECTION_NOT_FOUND",
    );
    expect(await code(client.getSection("L. 999-99"))).toBe(
      "SECTION_NOT_FOUND",
    );
    expect(await code(client.getSection("Code civil 1240"))).toBe(
      "INVALID_CITATION",
    );
    expect(await code(client.getBySectionNumber("Code civil", "L1"))).toBe(
      "SECTION_NOT_FOUND",
    );
  } finally {
    client.close();
  }
});

test("search folds diacritics, filters by code, quotes terms and pages", async () => {
  const client = new LegifranceIpClient({ corpusPath: fixture });
  try {
    const hits = await client.search({ query: "brevetabilite" });
    const accented = await client.search({ query: "brevetabilité" });
    expect(hits.hits.map((hit) => hit.section)).toEqual(
      accented.hits.map((hit) => hit.section),
    );
    const secret = await client.search({ query: "secret des affaires" });
    expect(new Set(secret.hits.map((hit) => hit.statute))).toEqual(
      new Set(["Code de commerce"]),
    );
    expect(secret.hits[0]).toMatchObject({
      snippet: expect.stringContaining("<mark>"),
      rank: expect.any(Number),
    });
    const brevet = await client.search({ query: "brevet", statute: "CPI" });
    expect(brevet.statute).toBe("CPI");
    expect(brevet.hits.every((hit) => hit.statute === "CPI")).toBe(true);
    expect(
      (await client.search({ query: "brevet", statute: "Code de commerce" }))
        .hits,
    ).toEqual([]);
    const all = await client.search({ query: "brevet", limit: 100 });
    const page = await client.search({ query: "brevet", limit: 2, offset: 1 });
    expect(page).toMatchObject({ limit: 2, offset: 1, has_more: true });
    expect(page.hits.map((hit) => hit.section)).toEqual(
      all.hits.slice(1, 3).map((hit) => hit.section),
    );
    expect(
      (await client.search({ query: "brevet marque", syntax: "or" })).hits
        .length,
    ).toBeGreaterThan(
      (await client.search({ query: "brevet marque" })).hits.length,
    );
    expect(await code(client.search({ query: "L.611-10 NOT NEAR(" }))).toBe(
      "resolved",
    );
    expect(
      await code(client.search({ query: "x", statute: "Code civil" as "CPI" })),
    ).toContain("expected one of");
  } finally {
    client.close();
  }
});

test("Zstandard bytes, pins and the environment variables configure the reader", async () => {
  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new Uint8Array(zstdCompressSync(bytes));
  const fromBytes = new LegifranceIpClient({
    source: packed,
    expectedSha256: hash(bytes),
    expectedFileSha256: hash(packed),
  });
  try {
    expect(await fromBytes.getCorpusStatus()).toMatchObject({
      available: true,
      compression: "zstd",
      artifact_sha256: hash(bytes),
      file_sha256: hash(packed),
    });
    expect((await fromBytes.getSection("L. 711-1 CPI")).section).toBe("L711-1");
  } finally {
    fromBytes.close();
  }
  const wrong = new LegifranceIpClient({
    source: bytes,
    expectedFileSha256: "0".repeat(64),
  });
  expect(await code(wrong.search({ query: "marque" }))).toBe(
    "CHECKSUM_MISMATCH",
  );
  const saved = { ...process.env };
  try {
    process.env.LEGIFRANCE_IP_CORPUS_PATH = fixture;
    process.env.LEGIFRANCE_IP_CORPUS_SHA256 = hash(bytes);
    const fromEnv = new LegifranceIpClient();
    try {
      expect((await fromEnv.getCorpusStatus()).available).toBe(true);
    } finally {
      fromEnv.close();
    }
    process.env.LEGIFRANCE_IP_CORPUS_PATH = join(tmpdir(), "missing-fr.db");
    const status = await new LegifranceIpClient().getCorpusStatus();
    expect(status).toMatchObject({
      available: false,
      corpus_version: "unknown",
      corpus_synced_at: null,
    });
    expect(status.error?.message).toContain("LEGIFRANCE_IP_CORPUS_PATH");
  } finally {
    process.env = saved;
  }
});

test("a Python seed-shaped build, WAL files and other schemas", async () => {
  // Python's schema without the added columns: fields read as null.
  await withCopy(
    `CREATE TABLE plain AS SELECT rowid, statute, section, title, text FROM sections;
     DROP TABLE sections_fts; DROP TABLE sections;
     CREATE TABLE sections (rowid INTEGER PRIMARY KEY, statute TEXT NOT NULL, section TEXT NOT NULL, title TEXT, text TEXT NOT NULL, UNIQUE(statute, section));
     INSERT INTO sections SELECT * FROM plain; DROP TABLE plain;
     CREATE VIRTUAL TABLE sections_fts USING fts5(title, text, content='sections', content_rowid='rowid', tokenize="unicode61 remove_diacritics 2");
     INSERT INTO sections_fts(sections_fts) VALUES ('rebuild');
     UPDATE meta SET value = 'seed v1' WHERE key = 'source_version';
     DELETE FROM meta WHERE key = 'codes';`,
    async (filename) => {
      const client = new LegifranceIpClient({ corpusPath: filename });
      try {
        expect(await client.getCorpusStatus()).toMatchObject({
          corpus_version: "seed v1",
          codes: null,
        });
        expect(await client.getSection("L. 611-10 CPI")).toMatchObject({
          article_id: null,
          in_force_since: null,
          breadcrumb: null,
          url: null,
          title: "Section 3 : Inventions brevetables",
        });
        expect(
          (await client.search({ query: "brevetabilite" })).hits.length,
        ).toBeGreaterThan(0);
      } finally {
        client.close();
      }
    },
  );
  const directory = await mkdtemp(join(tmpdir(), "pca-legifrance-wal-"));
  try {
    const bytes = new Uint8Array(await readFile(fixture));
    bytes[18] = 2;
    bytes[19] = 2;
    const wal = join(directory, "wal.db");
    await writeFile(wal, bytes);
    expect(
      (await new LegifranceIpClient({ corpusPath: wal }).getCorpusStatus())
        .error?.code,
    ).toBe("CORPUS_WAL_UNSUPPORTED");
  } finally {
    await rm(directory, { recursive: true });
  }
  await withCopy(
    "UPDATE meta SET value = '3' WHERE key = 'schema_version'",
    async (filename) => {
      expect(
        (
          await new LegifranceIpClient({
            corpusPath: filename,
          }).getCorpusStatus()
        ).error?.code,
      ).toBe("UNSUPPORTED_SCHEMA");
    },
  );
});

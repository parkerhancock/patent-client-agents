import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { copyFile, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import {
  compareSectionNumbers,
  IPO_IN_MPPP_PDF_URL,
  IPO_IN_STATUTES_SOURCE_URL,
  IpoInCitationError,
  IpoInMpppClient,
  IpoInStatutesClient,
  normalizeMpppReference,
  parseIpoInCitation,
  resolveIpoInStatute,
} from "../packages/client/src/ipo-in.js";
import { CorpusProvenanceSchema } from "../packages/client/src/models.js";

const dir = join(import.meta.dir, "fixtures", "ipo-in");
const statutesDb = join(dir, "ipo_in_statutes.db");
const mpppDb = join(dir, "ipo_in_mppp.db");
const seedDir = join(
  import.meta.dir,
  "..",
  "..",
  "src",
  "patent_client_agents",
);
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");
async function seed(name: string) {
  return (await readFile(join(seedDir, name, "data", "seed.jsonl"), "utf8"))
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as Record<string, string>);
}
async function withCopy(
  source: string,
  sql: string,
  run: (filename: string) => Promise<void>,
) {
  const directory = await mkdtemp(join(tmpdir(), "pca-ipo-in-test-"));
  const filename = join(directory, "copy.db");
  await copyFile(source, filename);
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

test("statute citations parse Python's forms and the ones it rejected", () => {
  const cases: [string, string, string | null][] = [
    ["Section 3(d) Patents Act", "3(d)", "Patents Act"],
    ["Section 25(2)", "25(2)", null],
    ["Rule 71 Patent Rules", "71", "Patent Rules"],
    ["S. 84", "84", null],
    ["3(d)", "3(d)", null],
    ["Section 25(2) of the Patents Act", "25(2)", "Patents Act"],
    // Python: unparseable, or the statute kept "of"/", 1970".
    ["§107A", "107A", null],
    ["§ 3 (d)", "3(d)", null],
    ["Section 25(2) of the Patents Act, 1970", "25(2)", "Patents Act"],
    ["Section 3(d) of Patents Act", "3(d)", "Patents Act"],
    ["Patents Act, section 3(d)", "3(d)", "Patents Act"],
    ["Trade Mark Act s. 29", "29", "Trade Marks Act"],
    // A rule without an Act is a Patent Rule (Python searched every Act).
    ["Rule 13", "13", "Patent Rules"],
  ];
  for (const [input, section, statute] of cases)
    expect([input, parseIpoInCitation(input)]).toEqual([
      input,
      { section_number: section, statute_name: statute },
    ]);
  expect(() => parseIpoInCitation("Patents Act")).toThrow(IpoInCitationError);
  expect(resolveIpoInStatute("PATENTS ACT 1970")).toBe("Patents Act");
  expect(resolveIpoInStatute("the Copyright Act, 1957")).toBe("Copyright Act");
  expect(resolveIpoInStatute("Patent Act")).toBe("Patents Act");
  expect(resolveIpoInStatute(" Unknown Act ")).toBe("Unknown Act");
  expect(normalizeMpppReference("MPPP Chapter 04.05.01")).toBe("04.05.01");
  expect(normalizeMpppReference("Ch. 4.5")).toBe("4.5");
  expect(() => normalizeMpppReference("chapter four")).toThrow(
    IpoInCitationError,
  );
  expect(
    ["107A", "25(1)", "3(d)", "2", "3", "25(2)", "146"].sort(
      compareSectionNumbers,
    ),
  ).toEqual(["2", "3", "3(d)", "25(1)", "25(2)", "107A", "146"]);
});

test("IPO India statutes status, search and sections come from the Python-built seed corpus", async () => {
  const client = new IpoInStatutesClient({ corpusPath: statutesDb });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "IPO India statutes",
      corpus_version: "snapshot-2026-10-22",
      schema_version: 1,
      section_count: 26,
      snapshot_date: "2026-10-22",
      source_version: null,
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
      compression: "none",
      source_url: IPO_IN_STATUTES_SOURCE_URL,
    });
    expect(status.artifact_sha256).toBe(hash(await readFile(statutesDb)));
    expect(await client.listStatutes()).toEqual([
      "Copyright Act",
      "Designs Act",
      "Patent Rules",
      "Patents Act",
      "Trade Marks Act",
    ]);

    const efficacy = await client.search({ query: "efficacy" });
    expect(efficacy).toMatchObject({
      query: "efficacy",
      statute_name: null,
      has_more: false,
      offset: 0,
      limit: 10,
    });
    expect(efficacy.hits).toEqual([
      {
        statute_name: "Patents Act",
        section_number: "3(d)",
        title: "Section 3(d) — incremental improvement bar (anti-evergreening)",
        snippet: expect.stringContaining("<mark>efficacy</mark>"),
        rank: expect.any(Number),
      },
    ]);
    CorpusProvenanceSchema.parse(efficacy.provenance);
    expect(efficacy.provenance).toMatchObject({
      source_url: IPO_IN_STATUTES_SOURCE_URL,
      source_name: "IPO India — IP statutes",
      corpus_version: "snapshot-2026-10-22",
    });

    const filtered = await client.search({
      query: "registered",
      statute: "trade marks act 1999",
    });
    expect(filtered.statute_name).toBe("Trade Marks Act");
    expect(
      filtered.hits.every((hit) => hit.statute_name === "Trade Marks Act"),
    ).toBe(true);
    expect(
      (await client.search({ query: "registered", statute: "Nonexistent" }))
        .hits,
    ).toEqual([]);

    // Natural outline order (Python sorted "107A" before "2").
    const outline = await client.search({
      query: "the",
      statute: "Patents Act",
      sort: "outline",
      limit: 100,
    });
    expect(outline.hits.map((hit) => hit.section_number)).toEqual([
      "2",
      "3",
      "3(d)",
      "8",
      "25(1)",
      "25(2)",
      "53",
      "84",
      "107A",
      "122",
      "146",
    ]);
    const page = await client.search({
      query: "the",
      statute: "Patents Act",
      sort: "outline",
      limit: 4,
      offset: 4,
    });
    expect(page.hits.map((hit) => hit.section_number)).toEqual([
      "25(1)",
      "25(2)",
      "53",
      "84",
    ]);
    expect(page.has_more).toBe(true);

    const section = await client.getSectionByCitation(
      "Section 3(d) of the Patents Act, 1970",
    );
    expect(section).toMatchObject({
      statute_name: "Patents Act",
      section_number: "3(d)",
      source_url:
        "https://ipindia.gov.in/writereaddata/portal/ev/sections/ps3.html",
      corpus_version: "snapshot-2026-10-22",
    });
    expect(section.provenance.source_url).toBe(section.source_url ?? "");
    expect((await client.getSection("107a")).section_number).toBe("107A");
    expect((await client.getSectionByCitation("Rule 71")).statute_name).toBe(
      "Patent Rules",
    );
    await expect(client.getSectionByCitation("Section 2")).rejects.toThrow(
      "ambiguous — exists in: Patents Act, Trade Marks Act",
    );
    await expect(
      client.getSectionByCitation("Section 999 Patents Act"),
    ).rejects.toMatchObject({ code: "SECTION_NOT_FOUND" });

    // Every seed row is stored and returned unchanged.
    for (const row of await seed("ipo_in_statutes")) {
      const stored = await client.getSection(row.section_number as string, {
        statute: row.statute_name as string,
      });
      expect(stored.content_sha256).toBe(hash(row.text as string));
      expect(stored.text).toBe(row.text as string);
    }
  } finally {
    client.close();
  }
});

test("IPO India search quotes caller syntax instead of executing FTS operators", async () => {
  const client = new IpoInStatutesClient({ corpusPath: statutesDb });
  try {
    // Python ran OR as an operator (4 hits) and raised on a bare NOT.
    expect(
      (await client.search({ query: "infringement OR zzz" })).hits,
    ).toEqual([]);
    // A bare NOT is the word "not", which several sections contain.
    expect((await client.search({ query: "NOT" })).hits.length).toBeGreaterThan(
      3,
    );
    expect(
      (await client.search({ query: "infringement OR zzz", syntax: "or" })).hits
        .length,
    ).toBeGreaterThan(1);
    expect(
      (await client.search({ query: "well-known mark", syntax: "adj" })).hits,
    ).toHaveLength(1);
    expect((await client.search({ query: "  " })).hits).toEqual([]);
    const controller = new AbortController();
    controller.abort();
    await expect(
      client.search({ query: "patent", signal: controller.signal }),
    ).rejects.toMatchObject({ code: "ABORTED" });
  } finally {
    client.close();
  }
});

test("IPO India MPPP status, search and sections, including unpadded references", async () => {
  const client = new IpoInMpppClient({ corpusPath: mpppDb });
  try {
    expect(await client.getCorpusStatus()).toMatchObject({
      available: true,
      label: "IPO India MPPP",
      corpus_version: "v3.0 (2019)",
      source_version: "v3.0 (2019)",
      section_count: 12,
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
      source_url: IPO_IN_MPPP_PDF_URL,
    });
    const hits = await client.search({ query: "opposition" });
    expect(hits.hits.map((hit) => hit.section_number).sort()).toEqual([
      "05.03",
      "05.04",
    ]);
    expect(hits.hits[0]?.chapter).toBe("Chapter 5");
    expect(
      (
        await client.search({ query: "the", sort: "outline", limit: 3 })
      ).hits.map((hit) => hit.section_number),
    ).toEqual(["01.01", "02.03", "03.04"]);
    for (const ref of ["04.05.01", "Chapter 04.05.01", "MPPP 4.5.1"])
      expect((await client.getSection(ref)).section_number).toBe("04.05.01");
    const section = await client.getSection("07.02");
    expect(section).toMatchObject({
      chapter: "Chapter 7",
      source_url: IPO_IN_MPPP_PDF_URL,
      corpus_version: "v3.0 (2019)",
    });
    await expect(client.getSection("99.99")).rejects.toMatchObject({
      code: "SECTION_NOT_FOUND",
    });
    for (const row of await seed("ipo_in_mppp"))
      expect(
        (await client.getSection(row.section_number as string)).content_sha256,
      ).toBe(hash(row.text as string));
  } finally {
    client.close();
  }
});

test("IPO India corpora read Zstandard bytes and report unavailable, WAL, schema and pin failures", async () => {
  const decoded = await readFile(statutesDb);
  const encoded = new Uint8Array(zstdCompressSync(decoded));
  const packed = new IpoInStatutesClient({
    source: encoded,
    expectedSha256: hash(decoded),
    expectedFileSha256: hash(encoded),
  });
  try {
    expect(await packed.getCorpusStatus()).toMatchObject({
      available: true,
      compression: "zstd",
      artifact_sha256: hash(decoded),
      file_sha256: hash(encoded),
    });
    expect((await packed.search({ query: "efficacy" })).hits).toHaveLength(1);
  } finally {
    packed.close();
  }
  const wrong = new IpoInMpppClient({
    corpusPath: mpppDb,
    expectedFileSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).error?.code).toBe("CHECKSUM_MISMATCH");
  expect(
    () => new IpoInMpppClient({ corpusPath: mpppDb, expectedSha256: "x" }),
  ).toThrow();

  const directory = await mkdtemp(join(tmpdir(), "pca-ipo-in-missing-"));
  try {
    const client = new IpoInStatutesClient({
      corpusPath: join(directory, "absent.db"),
    });
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: false,
      corpus_version: "unknown",
      corpus_synced_at: null,
    });
    expect(status.error?.message).toContain("IPO_IN_STATUTES_CORPUS_PATH");
    await expect(client.search({ query: "x" })).rejects.toMatchObject({
      code: "CORPUS_UNAVAILABLE",
    });
    client.close();
  } finally {
    await rm(directory, { recursive: true });
  }

  for (const [source, sql, code] of [
    [statutesDb, "PRAGMA journal_mode=WAL", "CORPUS_WAL_UNSUPPORTED"],
    [
      mpppDb,
      "UPDATE meta SET value = '2' WHERE key = 'schema_version'",
      "UNSUPPORTED_SCHEMA",
    ],
    [statutesDb, "DROP TABLE sections_fts", "INVALID_CORPUS"],
    // A statutes file is not an MPPP corpus.
    [statutesDb, "SELECT 1", "INVALID_CORPUS"],
  ] as const)
    await withCopy(source, sql, async (filename) => {
      const client =
        source === statutesDb && sql === "SELECT 1"
          ? new IpoInMpppClient({ corpusPath: filename })
          : source === statutesDb
            ? new IpoInStatutesClient({ corpusPath: filename })
            : new IpoInMpppClient({ corpusPath: filename });
      try {
        expect([sql, (await client.getCorpusStatus()).error?.code]).toEqual([
          sql,
          code,
        ]);
      } finally {
        client.close();
      }
    });
});

test("IPO India metadata gaps stay unknown and clients read the Python environment variables", async () => {
  await withCopy(
    mpppDb,
    "DELETE FROM meta WHERE key IN ('source_version', 'snapshot_date')",
    async (filename) => {
      const client = new IpoInMpppClient({ corpusPath: filename });
      try {
        expect(await client.getCorpusStatus()).toMatchObject({
          available: true,
          corpus_version: "unknown",
          corpus_synced_at: null,
        });
      } finally {
        client.close();
      }
    },
  );
  const saved = {
    path: process.env.IPO_IN_MPPP_CORPUS_PATH,
    pin: process.env.IPO_IN_MPPP_CORPUS_SHA256,
  };
  process.env.IPO_IN_MPPP_CORPUS_PATH = mpppDb;
  process.env.IPO_IN_MPPP_CORPUS_SHA256 = "0".repeat(64);
  try {
    const client = new IpoInMpppClient();
    expect((await client.getCorpusStatus()).error?.code).toBe(
      "CHECKSUM_MISMATCH",
    );
    client.close();
  } finally {
    for (const [key, value] of [
      ["IPO_IN_MPPP_CORPUS_PATH", saved.path],
      ["IPO_IN_MPPP_CORPUS_SHA256", saved.pin],
    ] as const)
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
  }
});

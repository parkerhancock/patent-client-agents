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
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");
const PDF = (page: number) =>
  `https://ipindia.gov.in/storage/uploads/docs-operator/73b5bf10-b04e-4f45-abef-87ff117315dc.pdf#page=${page}`;
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

test("IPO India statutes status, search and sections come from the official-text fixture", async () => {
  const client = new IpoInStatutesClient({ corpusPath: statutesDb });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "IPO India statutes",
      corpus_version: "snapshot-2026-10-22",
      schema_version: 1,
      section_count: 37,
      snapshot_date: "2026-10-22",
      source_version: null,
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
      compression: "none",
      source_url: IPO_IN_STATUTES_SOURCE_URL,
    });
    expect(status.metadata.source_patents_act).toContain(
      "incorporating all amendments till 01-08-2024",
    );
    expect(status.metadata.source_patent_rules).toContain("G.S.R. 865(E)");
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
        section_number: "3",
        title: "What are not inventions",
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
    expect(filtered.hits.map((hit) => hit.section_number).sort()).toEqual([
      "11",
      "2",
      "29",
      "9",
    ]);
    expect(
      (await client.search({ query: "registered", statute: "Nonexistent" }))
        .hits,
    ).toEqual([]);

    // Natural outline order (Python sorted "107A" before "11A" and "2").
    const outline = await client.search({
      query: "the",
      statute: "Patents Act",
      sort: "outline",
      limit: 100,
    });
    expect(outline.hits.map((hit) => hit.section_number)).toEqual([
      "1",
      "2",
      "3",
      "5",
      "8",
      "11A",
      "25",
      "48",
      "53",
      "84",
      "107A",
      "122",
      "124A",
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
      "8",
      "11A",
      "25",
      "48",
    ]);
    expect(page.has_more).toBe(true);

    // Whole sections are stored; a clause citation returns its section.
    const section = await client.getSectionByCitation(
      "Section 3(d) of the Patents Act, 1970",
    );
    expect(section).toMatchObject({
      statute_name: "Patents Act",
      section_number: "3",
      subdivision: "(d)",
      title: "What are not inventions",
      source_url: PDF(9),
      corpus_version: "snapshot-2026-10-22",
    });
    expect(section.text).toContain(
      "[(d) the mere discovery of a new form of a known substance which does not result in the enhancement of the known efficacy of that substance",
    );
    // Superscript amendment markers and page-foot footnotes are not text.
    expect(section.text).not.toMatch(/Subs\. by|Ins\. by|w\.e\.f\./);
    expect(section.provenance.source_url).toBe(section.source_url ?? "");
    expect(
      await client.getSectionByCitation("Section 25(2) Patents Act"),
    ).toMatchObject({ section_number: "25", subdivision: "(2)" });
    expect(
      (await client.getSection("107a", { statute: "Patents Act" }))
        .section_number,
    ).toBe("107A");
    // "§107A" is a section, so the Patent Rules' rule 107A does not compete.
    expect(await client.getSectionByCitation("§107A")).toMatchObject({
      statute_name: "Patents Act",
      title: "Certain acts not to be considered as infringement",
    });
    await expect(client.getSection("107A")).rejects.toThrow(
      "ambiguous — exists in: Patent Rules, Patents Act",
    );
    const rule = await client.getSectionByCitation("Rule 13");
    expect(rule).toMatchObject({
      statute_name: "Patent Rules",
      section_number: "13",
      title: "Specifications",
      source_url: "https://ipindia.gov.in/acts/patent-rules-2003/rule-13",
    });
    expect(rule.text).toStartWith(
      "(1) Every specification, whether provisional or complete, shall be made in Form 2.",
    );
    // Chapter XIV-A comes from the Patents (Amendment) Rules, 2025.
    expect((await client.getSectionByCitation("Rule 107A")).text).toContain(
      '"adjudicating officer" means an officer authorised under section 124A',
    );
    const nine = await client.getSectionByCitation("Section 9 Trade Marks Act");
    expect(nine.title).toBe("Absolute grounds for refusal of registration");
    expect(nine.text).toContain(
      "(a) which are devoid of any distinctive character",
    );
    await expect(client.getSectionByCitation("Section 2")).rejects.toThrow(
      "ambiguous — exists in: Copyright Act, Designs Act, Patents Act, Trade Marks Act",
    );
    await expect(
      client.getSectionByCitation("Section 999 Patents Act"),
    ).rejects.toMatchObject({ code: "SECTION_NOT_FOUND" });
    await expect(
      client.getSectionByCitation("Section 999(a) Patents Act"),
    ).rejects.toMatchObject({ code: "SECTION_NOT_FOUND" });
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
      (await client.search({ query: "well-known trade mark", syntax: "adj" }))
        .hits.length,
    ).toBeGreaterThan(0);
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
      corpus_version: "v3.0 (2019-11-26)",
      source_version: "v3.0 (2019-11-26)",
      section_count: 14,
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
      source_url: IPO_IN_MPPP_PDF_URL,
    });
    const hits = await client.search({ query: "first examination report" });
    expect(hits.hits.map((hit) => hit.section_number)).toEqual([
      "09.04",
      "09.01",
    ]);
    expect(hits.hits[0]?.chapter).toBe("Chapter 09: Examination and Grant");
    expect(
      (
        await client.search({ query: "the", sort: "outline", limit: 3 })
      ).hits.map((hit) => hit.section_number),
    ).toEqual(["01", "04.01", "04.02"]);
    for (const ref of ["09.03.05.04", "Chapter 09.03.05.04", "MPPP 9.3.5.4"])
      expect((await client.getSection(ref)).section_number).toBe("09.03.05.04");
    const pct = await client.getSection("07.02");
    expect(pct).toMatchObject({
      chapter:
        "Chapter 07: Convention Application, International Application and National Phase Application",
      title: "International Application under PCT",
      source_url: `${IPO_IN_MPPP_PDF_URL}#page=55`,
      corpus_version: "v3.0 (2019-11-26)",
    });
    // A heading with no text of its own keeps the heading line; marginal
    // statutory references go on a separate last line.
    expect(pct.text).toBe("07.02 International Application under PCT");
    expect((await client.getSection("07.02.01")).text).toEndWith(
      "\n[Marginal references: Section 39, 118, Rule 4]",
    );
    const examination = await client.getSection("MPPP 09.03");
    expect(examination.title).toBe("Examination of application");
    expect((await client.getSection("9")).title).toBe("Examination and Grant");
    expect((await client.getSection("09.03.05.04")).text).toContain(
      "Explanation to Section 3(d) further clarifies",
    );
    await expect(client.getSection("99.99")).rejects.toMatchObject({
      code: "SECTION_NOT_FOUND",
    });
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

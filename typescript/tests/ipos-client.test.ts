import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { copyFile, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import {
  compareIposLabels,
  IPOS_MANUALS_SOURCE_URL,
  IPOS_STATUTES_SOURCE_URL,
  IposManualsClient,
  IposStatutesClient,
  parseIposCitation,
  parseIposManualCitation,
  resolveIposManual,
  resolveIposStatute,
} from "../packages/client/src/ipos.js";
import { CorpusProvenanceSchema } from "../packages/client/src/models.js";

const dir = join(import.meta.dir, "fixtures", "ipos");
const statutesDb = join(dir, "ipos_statutes.db");
const manualsDb = join(dir, "ipos_manuals.db");
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");
const PEG_PDF =
  "https://isomer-user-content.by.gov.sg/61/d159c40c-f15d-49d6-97de-feb33bca527f/examination-guidelines-for-patent-applications.pdf";

async function withCopy(
  source: string,
  sql: string,
  run: (filename: string) => Promise<void>,
) {
  const directory = await mkdtemp(join(tmpdir(), "pca-ipos-test-"));
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

test("statute citations parse Python's forms, Schedules and the ones it misread", () => {
  const cases: [string, string | null, string][] = [
    // Python's documented forms.
    ["Section 13 Patents Act", "patents", "13"],
    ["Patents Act s. 13", "patents", "13"],
    ["s 27(1) Trade Marks Act", "tm", "27(1)"],
    ["13 Patents Act", "patents", "13"],
    ["Patents Act 13", "patents", "13"],
    ["Section 29A Patents Act", "patents", "29A"],
    // Added: "of the", year and edition suffixes, §, lower-case suffixes.
    ["Section 13 of the Patents Act 1994", "patents", "13"],
    ["s. 190 Copyright Act 2021", "copyright", "190"],
    ["§13 Patents Act", "patents", "13"],
    ["section 29a PA1994", "patents", "29A"],
    ["Section 8(2)(b) of the Trade Marks Act", "tm", "8(2)(b)"],
    ["Section 13", null, "13"],
    ["First Schedule Trade Marks Act", "tm", "First Schedule"],
    ["Schedule to the Patents Act", "patents", "Schedule"],
    ["Schedule 2 TMA1998", "tm", "Second Schedule"],
  ];
  for (const [input, statute, label] of cases)
    expect([input, parseIposCitation(input)]).toEqual([
      input,
      { statute, section_label: label },
    ]);
  // Python read this as section 2021 of the Copyright Act.
  expect(parseIposCitation("Copyright Act 2021")).toBeNull();
  expect(parseIposCitation("Patents Act")).toBeNull();
  expect(resolveIposStatute("The Trade Marks Act 1998")).toBe("tm");
  expect(resolveIposStatute("Registered Designs Act (2020 Rev. Ed.)")).toBe(
    "designs",
  );
  expect(resolveIposStatute(" Unknown Act ")).toBe("unknown act");

  expect(parseIposManualCitation("IPOS PEG 8.12")).toEqual({
    manual: "peg",
    section_label: "8.12",
  });
  expect(parseIposManualCitation("TM Work Manual 7.5.2")).toEqual({
    manual: "tm",
    section_label: "7.5.2",
  });
  expect(parseIposManualCitation("7.5.2 of the IPOS TM Work Manual")).toEqual({
    manual: "tm",
    section_label: "7.5.2",
  });
  expect(parseIposManualCitation("Designs Work Manual 2.1")).toEqual({
    manual: "designs",
    section_label: "2.1",
  });
  expect(parseIposManualCitation("Patent Examination Guidelines 4.1")).toEqual({
    manual: "peg",
    section_label: "4.1",
  });
  expect(parseIposManualCitation("MPEP 2106")).toBeNull();
  expect(parseIposManualCitation("8.12")).toBeNull();
  expect(resolveIposManual("Trade Marks Work Manual")).toBe("tm");
  expect(
    ["13A", "2", "117", "13", "Schedule", "1.10", "1.2"].sort(
      compareIposLabels,
    ),
  ).toEqual(["1.2", "1.10", "2", "13", "13A", "117", "Schedule"]);
});

test("IPOS statutes status, list, search and sections come from the official-text fixture", async () => {
  const client = new IposStatutesClient({ corpusPath: statutesDb });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "IPOS statutes",
      corpus_version: "2020 Revised Edition, in force from 2025-03-09",
      schema_version: 1,
      section_count: 19,
      snapshot_date: "2026-10-22",
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
      compression: "none",
      source_url: IPOS_STATUTES_SOURCE_URL,
    });
    expect(status.metadata.source_patents).toContain(
      "Patents Act 1994 (2020 Revised Edition, amended up to March 9, 2025)",
    );
    expect(status.artifact_sha256).toBe(hash(await readFile(statutesDb)));
    expect(await client.meta()).toEqual({
      schema_version: 1,
      snapshot_date: "2026-10-22",
      section_count: 19,
      document_count: 4,
      source_version: "2020 Revised Edition, in force from 2025-03-09",
    });
    expect(await client.listStatutes()).toEqual([
      {
        statute: "patents",
        short_name: "Patents Act",
        title: "Patents Act 1994 (2020 Revised Edition)",
        source_url: "https://www.wipo.int/wipolex/en/legislation/details/23204",
        source_version:
          "2020 Revised Edition, informal consolidation in force from 2025-03-09",
        sso_url: "https://sso.agc.gov.sg/Act/PA1994",
      },
      expect.objectContaining({ statute: "tm", short_name: "Trade Marks Act" }),
      expect.objectContaining({
        statute: "designs",
        short_name: "Registered Designs Act",
      }),
      expect.objectContaining({
        statute: "copyright",
        title: "Copyright Act 2021",
        sso_url: "https://sso.agc.gov.sg/Act/CA2021",
      }),
    ]);

    const inventive = await client.search({
      query: "inventive step",
      statute: "Patents Act",
    });
    expect(inventive).toMatchObject({
      query: "inventive step",
      statute: "patents",
      page: 1,
      per_page: 10,
      has_more: false,
    });
    expect(inventive.hits.map((hit) => hit.section_label)).toContain("15");
    expect(inventive.hits[0]).toMatchObject({
      statute: "patents",
      short_name: "Patents Act",
      snippet: expect.stringContaining("<mark>"),
      rank: expect.any(Number),
    });
    CorpusProvenanceSchema.parse(inventive.provenance);
    const paged = await client.search({ query: "the", per_page: 2, page: 2 });
    expect(paged.hits).toHaveLength(2);
    expect(paged.has_more).toBe(true);
    const ordered = await client.search({
      query: "registered",
      sort: "statute",
      per_page: 100,
    });
    expect(ordered.hits.map((hit) => hit.statute)).toEqual(
      [...ordered.hits.map((hit) => hit.statute)].sort(),
    );

    const s13 = await client.getByCitation("Section 13 Patents Act");
    expect(s13).toMatchObject({
      statute: "patents",
      short_name: "Patents Act",
      statute_title: "Patents Act 1994 (2020 Revised Edition)",
      section_label: "13",
      title: "Patentable inventions",
      breadcrumb: "Patents Act › Part 3 PATENTABILITY › Section 13",
      sso_url: "https://sso.agc.gov.sg/Act/PA1994?ProvIds=pr13-#pr13-",
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/23204",
    });
    expect(s13.text).toStartWith(
      "13.—(1) Subject to subsection (2), a patentable invention is one that satisfies the following conditions:\n(a) the invention is new;\n(b) it involves an inventive step; and\n(c) it is capable of industrial application.",
    );
    // The heading of section 14 belongs to section 14, not the end of 13.
    expect(s13.text).not.toContain("Novelty");
    expect(s13.provenance.source_url).toBe(s13.sso_url as string);

    const sub = await client.getByCitation("s 8(2)(b) Trade Marks Act");
    expect(sub).toMatchObject({
      section_label: "8",
      subdivision: "(2)(b)",
      title: "Relative grounds for refusal of registration",
    });
    expect(
      (await client.getByCitation("First Schedule Trade Marks Act")).title,
    ).toBe("Collective Marks");
    expect((await client.getSection("109", { statute: "pa" })).text).toBe(
      "109. [Repealed by Act 16 of 2016]",
    );
    expect(
      (await client.getByCitation("Section 191 of the Copyright Act 2021"))
        .text,
    ).toContain("(d) the effect of the use upon the potential market");
    expect((await client.getSection("190")).statute).toBe("copyright");
    await expect(client.getSection("2")).rejects.toMatchObject({
      code: "AMBIGUOUS_SECTION",
    });
    await expect(
      client.getByCitation("Section 999 Patents Act"),
    ).rejects.toMatchObject({ code: "SECTION_NOT_FOUND" });
    await expect(client.getByCitation("Patents Act")).rejects.toMatchObject({
      code: "SECTION_NOT_FOUND",
    });
    const aborted = new AbortController();
    aborted.abort();
    await expect(
      client.search({ query: "patent", signal: aborted.signal }),
    ).rejects.toMatchObject({ code: "ABORTED" });
  } finally {
    client.close();
  }
});

test("IPOS search quotes caller syntax instead of executing FTS operators", async () => {
  const client = new IposStatutesClient({ corpusPath: statutesDb });
  try {
    for (const query of ['"', "NEAR(", "section:13", "-patent", "*", "AND"])
      expect((await client.search({ query })).hits).toBeArray();
    expect((await client.search({ query: "  " })).hits).toEqual([]);
    const phrase = await client.search({
      query: "inventive step",
      syntax: "exact",
    });
    expect(phrase.hits.length).toBeGreaterThan(0);
    expect(
      (await client.search({ query: "novelty zzzzqq", syntax: "or" })).hits
        .length,
    ).toBeGreaterThan(0);
    expect(() => client.search({ query: "x", per_page: 101 })).toThrow();
  } finally {
    client.close();
  }
});

test("IPOS manuals status, list, search and sections, with per-chapter versions", async () => {
  const client = new IposManualsClient({ corpusPath: manualsDb });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "IPOS manuals",
      // No single version covers three manuals, so Python's snapshot label applies.
      corpus_version: "snapshot 2026-10-22",
      section_count: 11,
      source_url: IPOS_MANUALS_SOURCE_URL,
    });
    expect(status.metadata.source_tm).toContain("17: Version 5 (March 2025)");
    expect((await client.meta()).document_count).toBe(3);
    expect(await client.listManuals()).toEqual([
      {
        manual: "peg",
        short_name: "PEG",
        title: "IPOS Examination Guidelines for Patent Applications",
        source_url: "https://www.ipos.gov.sg/about-ip/patents/guides/",
        source_version: "Version Oct 2023 (released 11 October 2023)",
      },
      {
        manual: "tm",
        short_name: "TM Work Manual",
        title: "IPOS Trade Marks Work Manual",
        source_url: "https://www.ipos.gov.sg/about-ip/trade-marks/tm-guides/",
        source_version: null,
      },
      {
        manual: "designs",
        short_name: "Designs Guidelines",
        title: "IPOS Registered Designs — Guidelines for Non-Physical Products",
        source_url: "https://www.ipos.gov.sg/about-ip/designs/guides/",
        source_version: "Version Jun 2022 (released 2 June 2022)",
      },
    ]);

    const visual = await client.search({
      query: "visual similarity",
      manual: "TM Work Manual",
    });
    expect(visual.manual).toBe("tm");
    expect(visual.hits[0]).toMatchObject({
      manual: "tm",
      section_label: "7.5.2.5.2",
      title: "Visual Similarity",
    });
    expect((await client.search({ query: "discovery" })).hits[0]).toMatchObject(
      { manual: "peg", section_label: "8.12", title: "Discoveries" },
    );

    const peg = await client.getByCitation("IPOS PEG 8.12");
    expect(peg).toMatchObject({
      manual: "peg",
      short_name: "PEG",
      section_label: "8.12",
      title: "Discoveries",
      breadcrumb:
        "PEG › Chapter 8 PATENTABLE SUBJECT MATTER AND INDUSTRIAL APPLICABILITY › A. Statutory requirements › Discoveries › 8.12",
      source_url: `${PEG_PDF}#page=294`,
      source_version: "Version Oct 2023 (released 11 October 2023)",
    });
    expect(peg.text).toStartWith(
      "To find a material or microorganism that pre-existed in nature would represent a discovery",
    );
    expect(peg.provenance.source_url).toBe(`${PEG_PDF}#page=294`);
    const tm = await client.getByCitation("17.3.1 TM Work Manual");
    expect(tm).toMatchObject({
      title: "Duration of Registration",
      source_version: "Version 5 (March 2025)",
      breadcrumb:
        "TM Work Manual › Chapter 17 Renewal › 17.3 BACKGROUND › 17.3.1 Duration of Registration",
    });
    expect(
      (await client.getSection("Designs Work Manual", "2.1")).text,
    ).toContain("should not be tangible");
    await expect(client.getByCitation("PEG 99.1")).rejects.toMatchObject({
      code: "SECTION_NOT_FOUND",
    });
    await expect(client.getByCitation("chapter four")).rejects.toMatchObject({
      code: "SECTION_NOT_FOUND",
    });
  } finally {
    client.close();
  }
});

test("IPOS corpora read Zstandard bytes, Python-built files and report unavailable, WAL, schema and pin failures", async () => {
  const decoded = await readFile(statutesDb);
  const encoded = new Uint8Array(zstdCompressSync(decoded));
  const packed = new IposStatutesClient({
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
    expect(
      (await packed.search({ query: "fair use" })).hits.length,
    ).toBeGreaterThan(0);
  } finally {
    packed.close();
  }
  const wrong = new IposManualsClient({
    corpusPath: manualsDb,
    expectedFileSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).error?.code).toBe("CHECKSUM_MISMATCH");
  expect(
    () => new IposManualsClient({ corpusPath: manualsDb, expectedSha256: "x" }),
  ).toThrow();

  // Python's builder writes no sso_url column; the Act link is derived instead.
  await withCopy(
    statutesDb,
    "ALTER TABLE sections DROP COLUMN sso_url",
    async (filename) => {
      const client = new IposStatutesClient({ corpusPath: filename });
      try {
        expect(
          (await client.getByCitation("Section 13 Patents Act")).sso_url,
        ).toBe("https://sso.agc.gov.sg/Act/PA1994");
      } finally {
        client.close();
      }
    },
  );

  const directory = await mkdtemp(join(tmpdir(), "pca-ipos-missing-"));
  try {
    const client = new IposStatutesClient({
      corpusPath: join(directory, "absent.db"),
    });
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: false,
      corpus_version: "unknown",
      corpus_synced_at: null,
    });
    expect(status.error?.message).toContain("IPOS_STATUTES_CORPUS_PATH");
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
      manualsDb,
      "UPDATE meta SET value = '2' WHERE key = 'schema_version'",
      "UNSUPPORTED_SCHEMA",
    ],
    [statutesDb, "DROP TABLE sections_fts", "INVALID_CORPUS"],
    // A statutes file is not a manuals corpus.
    [statutesDb, "SELECT 1", "INVALID_CORPUS"],
  ] as const)
    await withCopy(source, sql, async (filename) => {
      const client =
        source === statutesDb && sql !== "SELECT 1"
          ? new IposStatutesClient({ corpusPath: filename })
          : new IposManualsClient({ corpusPath: filename });
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

test("IPOS clients read Python's environment variables", async () => {
  const saved = {
    path: process.env.IPOS_MANUALS_CORPUS_PATH,
    pin: process.env.IPOS_MANUALS_CORPUS_SHA256,
  };
  process.env.IPOS_MANUALS_CORPUS_PATH = manualsDb;
  process.env.IPOS_MANUALS_CORPUS_SHA256 = "0".repeat(64);
  try {
    const client = new IposManualsClient();
    expect((await client.getCorpusStatus()).error?.code).toBe(
      "CHECKSUM_MISMATCH",
    );
    client.close();
  } finally {
    for (const [key, value] of [
      ["IPOS_MANUALS_CORPUS_PATH", saved.path],
      ["IPOS_MANUALS_CORPUS_SHA256", saved.pin],
    ] as const)
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
  }
});

import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  isRospatentCode,
  parseRospatentCitation,
  ROSPATENT_STATUTES_SOURCE_URL,
  RospatentArticleSchema,
  RospatentStatutesClient,
} from "../packages/client/src/rospatent-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "rospatent-statutes",
  "rospatent_statutes.db",
);
const hash = (value: Uint8Array) =>
  createHash("sha256").update(value).digest("hex");
const article = (citation: string) =>
  parseRospatentCitation(citation)?.section_number ?? null;

test("Civil Code names resolve in English, abbreviations and Russian", () => {
  for (const name of [
    "Civil Code",
    "the Civil Code of the Russian Federation",
    "Part Four of the Civil Code",
    "Civil Code (Part Four)",
    "CC RF",
    "RF CC",
    "Russian Civil Code",
    "ГК РФ",
    "Гражданского кодекса Российской Федерации",
  ])
    expect(isRospatentCode(name)).toBe(true);
  expect(isRospatentCode("Patents Law")).toBe(false);
  expect(isRospatentCode("Tax Code")).toBe(false);
});

test("citations parse in both orders, with items dropped and inserted articles kept", () => {
  expect(parseRospatentCitation("Article 1350 Civil Code")).toEqual({
    statute: "civil_code",
    section_number: "1350",
  });
  expect(article("Civil Code Art. 1350(1)")).toBe("1350");
  expect(article("Art. 1484 CC RF")).toBe("1484");
  expect(article("Article 1350")).toBe("1350");
  expect(article("art. 1229(3)(2) of the Civil Code")).toBe("1229");
  expect(article("Item 1 of Article 1229 of the Civil Code")).toBe("1229");
  expect(article("Article 1350, item 2, Civil Code")).toBe("1350");
  expect(article("Article 1231.1")).toBe("1231.1");
  expect(article("Article 1358.1 of Part Four of the Civil Code")).toBe(
    "1358.1",
  );
  expect(article("Civil Code of the Russian Federation, Article 1252")).toBe(
    "1252",
  );
  expect(article("ст. 1484 ГК РФ")).toBe("1484");
  expect(article("п. 1 ст. 1350 ГК РФ")).toBe("1350");
  expect(article("статья 1515 Гражданского кодекса")).toBe("1515");
  // Another statute, no article marker, or no number.
  expect(parseRospatentCitation("Article 6 Patents Law")).toBeNull();
  expect(parseRospatentCitation("1350")).toBeNull();
  expect(parseRospatentCitation("Civil Code")).toBeNull();
  expect(parseRospatentCitation("")).toBeNull();
  expect(parseRospatentCitation("nonsense")).toBeNull();
});

test("status reports the translation's currency and the WIPO Lex record", async () => {
  const before = hash(await readFile(fixture));
  const client = new RospatentStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "Rospatent statutes",
      corpus_version:
        "WIPO Lex 22547 English translation, amended up to 2024-03-22",
      schema_version: 1,
      section_count: 16,
      snapshot_date: "2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
      compression: "none",
      source_url: ROSPATENT_STATUTES_SOURCE_URL,
      translation_amended_up_to: "2024-03-22",
      russian_amended_up_to: "2025-08-03",
      version_note: expect.stringContaining("The Russian text controls."),
      legislation: {
        wipolex_id: "22547",
        pdf_url:
          "https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/ru/ru421en_1.pdf",
        pdf_sha256: expect.stringMatching(/^[a-f\d]{64}$/),
        latest_record_url:
          "https://www.wipo.int/wipolex/en/legislation/details/23256",
      },
      repealed_chapters: [
        {
          chapter: expect.stringMatching(/^Chapter 77\./),
          note: "Invalid from January 1, 2022 - Federal Law No. 456-FZ of December 22, 2020",
        },
      ],
      // The fixture is a 16-article subset of the 329-article build.
      metadata: { section_count: "16", fixture_subset_of: "329" },
    });
    expect(status.artifact_sha256).toBe(before);
    expect(await client.meta()).toEqual({
      schema_version: 1,
      snapshot_date: "2026-10-26",
      source_version:
        "WIPO Lex 22547 English translation, amended up to 2024-03-22",
      section_count: 16,
    });
    expect(hash(await readFile(fixture))).toBe(before);
  } finally {
    client.close();
  }
});

test("articles carry their headings; repealed and missing ones are handled", async () => {
  const client = new RospatentStatutesClient({ corpusPath: fixture });
  try {
    const patentability = await client.getArticleByCitation(
      "Civil Code Art. 1350(1)",
    );
    expect(RospatentArticleSchema.parse(patentability)).toBeTruthy();
    expect(patentability).toMatchObject({
      statute: "civil_code",
      section_number: "1350",
      section_label: "Article 1350 Civil Code",
      title: "The Conditions for Patentability of an Invention",
      chapter: "Chapter 72. The Patent Law",
      paragraph: "§ 1. Basic Provisions",
      subparagraph: null,
      repealed: false,
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/22547",
      provenance: {
        source_url: ROSPATENT_STATUTES_SOURCE_URL,
        corpus_version:
          "WIPO Lex 22547 English translation, amended up to 2024-03-22",
        cache_hit: true,
      },
    });
    const lines = patentability?.text.split("\n") ?? [];
    expect(lines[0]).toStartWith("1. A technical solution in any area");
    expect(lines).toContain("5) computer programs;");

    expect(await client.getArticle("1484")).toMatchObject({
      paragraph:
        "§ 2. The Right to a Trademark and the Right to a Service Mark",
      subparagraph:
        "2. Using a Trademark and Disposing of the Exclusive Right to a Trademark",
    });
    expect((await client.getArticle("1231.1"))?.title).toBe(
      "Objects Including Official Symbols, Denominations and Distinctive Marks",
    );
    expect(await client.getArticle("1478")).toMatchObject({
      title: null,
      repealed: true,
      text: "Invalid from June 29, 2023 - Federal Law No. 193-FZ of June 28, 2022",
    });
    expect(await client.getArticle("1999")).toBeNull();
    expect(
      await client.getArticleByCitation("Article 6 Patents Law"),
    ).toBeNull();
  } finally {
    client.close();
  }
});

test("search ranks, filters by chapter, pages and orders without MATCH syntax", async () => {
  const client = new RospatentStatutesClient({ corpusPath: fixture });
  try {
    const patents = await client.search({
      query: "invention",
      chapter: 72,
    });
    expect(patents.chapter).toBe(72);
    expect(patents.hits.length).toBeGreaterThan(0);
    expect(
      patents.hits.every((hit) => hit.chapter.startsWith("Chapter 72.")),
    ).toBe(true);
    expect(patents.hits[0]?.snippet).toContain("<mark>");
    expect(typeof patents.hits[0]?.rank).toBe("number");

    const paged = await client.search({ query: "right", per_page: 1 });
    expect(paged.hits).toHaveLength(1);
    expect(paged.has_more).toBe(true);
    const second = await client.search({
      query: "right",
      per_page: 1,
      page: 2,
    });
    expect(second.hits[0]?.section_number).not.toBe(
      paged.hits[0]?.section_number,
    );

    // Numeric outline order, inserted articles after their base.
    const outline = await client.search({
      query: "the",
      sort: "outline",
      per_page: 100,
    });
    const numbers = outline.hits.map((hit) => hit.section_number);
    expect(numbers.indexOf("1231.1")).toBeGreaterThan(numbers.indexOf("1229"));
    expect(numbers.indexOf("1231.1")).toBeLessThan(numbers.indexOf("1248"));
    expect(numbers.at(-1)).toBe("1541");
    expect(outline.hits.every((hit) => hit.rank === null)).toBe(true);

    for (const query of ["NEAR(right", 'right" OR "x', "know-how", "*"])
      await client.search({ query });
    expect((await client.search({ query: "   " })).hits).toEqual([]);
    expect(
      (await client.search({ query: "know-how", syntax: "exact" })).hits[0]
        ?.section_number,
    ).toBe("1465");
    await expect(client.search({ query: "x", chapter: 68 })).rejects.toThrow();
    await expect(
      client.search({ query: "x", per_page: 101 }),
    ).rejects.toThrow();
  } finally {
    client.close();
  }
});

test("a missing corpus reports how to supply one, and zstd bytes open in memory", async () => {
  const missing = new RospatentStatutesClient({
    corpusPath: join(
      import.meta.dir,
      "fixtures",
      "rospatent-statutes",
      "absent.db",
    ),
  });
  const status = await missing.getCorpusStatus();
  expect(status.available).toBe(false);
  expect(status.legislation).toBeNull();
  expect(status.error?.message).toContain("ROSPATENT_STATUTES_CORPUS_PATH");
  await expect(missing.getArticle("1350")).rejects.toBeInstanceOf(CorpusError);

  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new RospatentStatutesClient({
    source: new Uint8Array(zstdCompressSync(bytes)),
    expectedSha256: hash(bytes),
  });
  try {
    expect((await packed.getCorpusStatus()).compression).toBe("zstd");
    expect((await packed.getArticleByCitation("Art. 1484 CC RF"))?.title).toBe(
      "The Exclusive Right to a Trademark",
    );
  } finally {
    packed.close();
  }
  const wrong = new RospatentStatutesClient({
    source: bytes,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).available).toBe(false);
});

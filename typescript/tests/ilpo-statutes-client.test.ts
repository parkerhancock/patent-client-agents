import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  ILPO_STATUTE_ALIASES,
  ILPO_STATUTES_SOURCE_URL,
  IlpoSectionSchema,
  IlpoStatutesClient,
  parseIlpoCitation,
  resolveIlpoStatute,
} from "../packages/client/src/ilpo-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "ilpo-statutes",
  "ilpo_statutes.db",
);
const hash = (value: Uint8Array) =>
  createHash("sha256").update(value).digest("hex");

test("statute aliases resolve as in Python, trade secrets to the Commercial Torts Law", () => {
  expect(resolveIlpoStatute("Patents Law")).toBe("patents");
  expect(resolveIlpoStatute("trade marks")).toBe("trademarks");
  expect(resolveIlpoStatute(" Trade  Secret ")).toBe("commercial_torts");
  expect(resolveIlpoStatute("trade secrets")).toBe("commercial_torts");
  expect(resolveIlpoStatute("commercial torts")).toBe("commercial_torts");
  // Unknown names pass through lowercased, so lookups report nothing.
  expect(resolveIlpoStatute("Unknown")).toBe("unknown");
  expect(ILPO_STATUTE_ALIASES["trade secret"]).toBe("commercial_torts");
});

test("citations parse in both orders, with Python's forms and a few it missed", () => {
  expect(parseIlpoCitation("Section 3 Patents Law")).toEqual({
    statute: "patents",
    section_number: "3",
  });
  expect(parseIlpoCitation("Section 1 Trade Marks Ordinance")).toEqual({
    statute: "trademarks",
    section_number: "1",
  });
  expect(parseIlpoCitation("Article 6 Commercial Torts Law")).toEqual({
    statute: "commercial_torts",
    section_number: "6",
  });
  expect(parseIlpoCitation("§3 Patents Law")?.section_number).toBe("3");
  expect(parseIlpoCitation("Patents Law §3")?.statute).toBe("patents");
  expect(parseIlpoCitation("Patents Law Section 3")?.section_number).toBe("3");
  expect(parseIlpoCitation("Commercial Torts Law Article 6")?.statute).toBe(
    "commercial_torts",
  );
  expect(parseIlpoCitation("section 3 patents law")?.statute).toBe("patents");
  expect(parseIlpoCitation("Article 6 Trade Secret")?.statute).toBe(
    "commercial_torts",
  );
  // Python's pattern rejects these.
  expect(parseIlpoCitation("Section 6(b) Commercial Torts Law")).toEqual({
    statute: "commercial_torts",
    section_number: "6",
  });
  expect(parseIlpoCitation("s. 54a of the Patents Law, 5727-1967")).toEqual({
    statute: "patents",
    section_number: "54A",
  });
  expect(
    parseIlpoCitation("Section 56D1 Trade Marks Ordinance")?.section_number,
  ).toBe("56D1");
  expect(parseIlpoCitation("")).toBeNull();
  expect(parseIlpoCitation("nonsense")).toBeNull();
  expect(parseIlpoCitation("Article 6 No Such Statute")).toBeNull();
});

test("status, statutes and sections come from the WIPO Lex build", async () => {
  const before = hash(await readFile(fixture));
  const client = new IlpoStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "ILPO statutes",
      corpus_version: "WIPO Lex English translations, 2026-10-22",
      schema_version: 1,
      section_count: 15,
      snapshot_date: "2026-10-22",
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
      compression: "none",
      source_url: ILPO_STATUTES_SOURCE_URL,
      // The fixture is a 15-section subset of the 576-section build.
      metadata: { section_count: "15", fixture_subset_of: "576" },
    });
    expect(status.artifact_sha256).toBe(before);
    const statutes = await client.listStatutes();
    expect(statutes.map((item) => [item.statute, item.section_count])).toEqual([
      ["patents", 5],
      ["trademarks", 3],
      ["designs", 2],
      ["copyright", 2],
      ["commercial_torts", 3],
    ]);
    expect(statutes[4]).toMatchObject({
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/2375",
      short_name: "Commercial Torts Law",
      title: "Commercial Torts Law, 5759-1999",
      version: expect.stringContaining("Year of Version: 1999"),
      pdf_url:
        "https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/il/il012en.pdf",
      pdf_sha256: expect.stringMatching(/^[a-f\d]{64}$/),
    });
    expect(await client.meta()).toEqual({
      schema_version: 1,
      snapshot_date: "2026-10-22",
      source_version: "WIPO Lex English translations, 2026-10-22",
      section_count: 15,
    });

    const section = await client.getSectionByCitation(
      "Article 6 Commercial Torts Law",
    );
    expect(IlpoSectionSchema.parse(section)).toBeTruthy();
    expect(section).toMatchObject({
      statute: "commercial_torts",
      section_number: "6",
      section_label: "Section 6 Commercial Torts Law",
      title: "Prohibition against misappropriation of a trade secret",
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/2375",
      provenance: {
        source_url: ILPO_STATUTES_SOURCE_URL,
        corpus_version: "WIPO Lex English translations, 2026-10-22",
        cache_hit: true,
      },
    });
    const lines = section?.text.split("\n") ?? [];
    expect(lines[0]).toBe(
      "(a) A person shall not misappropriate another’s trade secret.",
    );
    // The PDF prints "(Two)", "(Three)"; the text cites "paragraph (b)(1)".
    expect(lines[1]).toStartWith("(b) Any of the following acts");
    expect(section?.text).toContain("(c) The revealing of a trade secret");

    const patent = await client.getSection("Patents Law", "54a");
    expect(patent?.title).toBe("Experimental act in order to obtain license");
    expect(
      (await client.getSection("patents", "3"))?.text.split("\n").at(-1),
    ).toBe("[Margin notes: (amendment no. 4) 1999]");
    expect(
      (await client.getSectionByCitation("Section 13 Trade Secrets"))?.title,
    ).toBe("Statutory damages");
    expect(await client.getSection("patents", "9999")).toBeNull();
    expect(await client.getSection("nonsense", "3")).toBeNull();
    expect(await client.getSectionByCitation("nonsense")).toBeNull();
    expect(hash(await readFile(fixture))).toBe(before);
  } finally {
    client.close();
  }
});

test("search ranks, filters, pages and orders like Python, without MATCH syntax", async () => {
  const client = new IlpoStatutesClient({ corpusPath: fixture });
  try {
    const scoped = await client.search({
      query: "trade secret",
      statute: "trade secrets",
    });
    expect(scoped.statute).toBe("commercial_torts");
    expect(scoped.hits.length).toBeGreaterThan(0);
    expect(scoped.hits.every((hit) => hit.statute === "commercial_torts")).toBe(
      true,
    );
    expect(scoped.hits[0]?.snippet).toContain("<mark>");
    expect(typeof scoped.hits[0]?.rank).toBe("number");

    const unscoped = await client.search({ query: "invention" });
    expect(new Set(unscoped.hits.map((hit) => hit.statute))).toEqual(
      new Set(["patents"]),
    );
    const paged = await client.search({ query: "invention", per_page: 1 });
    expect(paged.hits).toHaveLength(1);
    expect(paged.has_more).toBe(true);
    const second = await client.search({
      query: "invention",
      per_page: 1,
      page: 2,
    });
    expect(second.page).toBe(2);
    expect(second.hits[0]?.section_number).not.toBe(
      paged.hits[0]?.section_number,
    );

    // Numeric outline order (Python sorts section numbers as text).
    const outline = await client.search({
      query: "invention OR design",
      syntax: "or",
      sort: "outline",
      per_page: 50,
    });
    const patents = outline.hits
      .filter((hit) => hit.statute === "patents")
      .map((hit) => hit.section_number);
    expect(patents).toEqual(["2", "3", "4", "5", "54A"]);
    expect(outline.hits.every((hit) => hit.rank === null)).toBe(true);

    // Operators and punctuation are literal text, never FTS5 syntax.
    for (const query of ["NEAR(trade", 'trade" OR "x', "trade-secret", "*"])
      await client.search({ query });
    expect((await client.search({ query: "   " })).hits).toEqual([]);
    expect((await client.search({ query: "fair use" })).hits[0]).toMatchObject({
      statute: "copyright",
      section_number: "19",
    });
    await expect(
      client.search({ query: "x", per_page: 101 }),
    ).rejects.toThrow();
  } finally {
    client.close();
  }
});

test("a missing corpus reports how to supply one, and zstd bytes open in memory", async () => {
  const missing = new IlpoStatutesClient({
    corpusPath: join(import.meta.dir, "fixtures", "ilpo-statutes", "absent.db"),
  });
  const status = await missing.getCorpusStatus();
  expect(status.available).toBe(false);
  expect(status.statutes).toBeNull();
  expect(status.error?.message).toContain("ILPO_STATUTES_CORPUS_PATH");
  await expect(missing.listStatutes()).rejects.toBeInstanceOf(CorpusError);

  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new IlpoStatutesClient({
    source: new Uint8Array(zstdCompressSync(bytes)),
    expectedSha256: hash(bytes),
  });
  try {
    expect((await packed.getCorpusStatus()).compression).toBe("zstd");
    expect(
      (await packed.getSectionByCitation("Section 19 Copyright Act"))?.title,
    ).toBe("Fair Use");
  } finally {
    packed.close();
  }
  const wrong = new IlpoStatutesClient({
    source: bytes,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).available).toBe(false);
});

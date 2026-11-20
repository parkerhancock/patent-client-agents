import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  normalizeThaiDipSectionNumber,
  parseThaiDipCitation,
  resolveThaiDipStatute,
  THAI_DIP_STATUTES_AUTHORITY,
  THAI_DIP_STATUTES_SOURCE_URL,
  ThaiDipSectionSchema,
  ThaiDipStatutesClient,
} from "../packages/client/src/thai-dip-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "thai-dip-statutes",
  "thai_dip_statutes.db",
);
const hash = (value: Uint8Array) =>
  createHash("sha256").update(value).digest("hex");

test("act names and aliases resolve to the four keys", () => {
  expect(resolveThaiDipStatute("Patent Act")).toBe("patent");
  expect(resolveThaiDipStatute("petty patent")).toBe("patent");
  expect(resolveThaiDipStatute("trade marks")).toBe("trademark");
  expect(resolveThaiDipStatute("TM")).toBe("trademark");
  expect(resolveThaiDipStatute(" Trade  Secrets Act ")).toBe("trade_secrets");
  expect(resolveThaiDipStatute("copyright act")).toBe("copyright");
  // Unknown names pass through lowercased, so lookups report nothing.
  expect(resolveThaiDipStatute("Unknown")).toBe("unknown");
});

test("citations parse in both orders, with inserted sections and subsections", () => {
  expect(parseThaiDipCitation("Section 36 Patent Act")).toEqual({
    statute: "patent",
    section_number: "36",
  });
  expect(parseThaiDipCitation("Patent Act s. 36")).toEqual({
    statute: "patent",
    section_number: "36",
  });
  expect(parseThaiDipCitation("Section 6 Trade Secrets Act")).toEqual({
    statute: "trade_secrets",
    section_number: "6",
  });
  expect(
    parseThaiDipCitation("Section 36 bis Patent Act")?.section_number,
  ).toBe("36bis");
  expect(parseThaiDipCitation("s. 36bis Patent Act")?.section_number).toBe(
    "36bis",
  );
  expect(
    parseThaiDipCitation("Section 65 decies Patent Act")?.section_number,
  ).toBe("65decies");
  expect(
    parseThaiDipCitation("Section 106 quarter Trademark Act")?.section_number,
  ).toBe("106quater");
  expect(parseThaiDipCitation("Section 36/1 Copyright Act")).toEqual({
    statute: "copyright",
    section_number: "36/1",
  });
  expect(
    parseThaiDipCitation("Trademark Act, Section 109 / 1")?.section_number,
  ).toBe("109/1");
  expect(
    parseThaiDipCitation("s. 15(5) of the Copyright Act B.E. 2537 (1994)"),
  ).toEqual({ statute: "copyright", section_number: "15" });
  expect(
    parseThaiDipCitation("Section 31 paragraph one Trademark Act")
      ?.section_number,
  ).toBe("31");
  expect(parseThaiDipCitation("§ 6 Trade Secrets Act")?.statute).toBe(
    "trade_secrets",
  );
  expect(normalizeThaiDipSectionNumber("65 Novies")).toBe("65nonies");
  expect(parseThaiDipCitation("")).toBeNull();
  expect(parseThaiDipCitation("nonsense")).toBeNull();
  expect(parseThaiDipCitation("Section 6 No Such Act")).toBeNull();
});

test("status, acts and sections come from the WIPO Lex build", async () => {
  const before = hash(await readFile(fixture));
  const client = new ThaiDipStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "Thailand IP statutes",
      corpus_version: "WIPO Lex English translations, 2026-10-26",
      schema_version: 1,
      section_count: 16,
      snapshot_date: "2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
      compression: "none",
      source_url: THAI_DIP_STATUTES_SOURCE_URL,
      authority: THAI_DIP_STATUTES_AUTHORITY,
      // The fixture is a 16-section subset of the 401-section build.
      metadata: { section_count: "16", fixture_subset_of: "401" },
    });
    expect(status.artifact_sha256).toBe(before);
    const statutes = await client.listStatutes();
    expect(statutes.map((item) => [item.statute, item.section_count])).toEqual([
      ["patent", 5],
      ["trademark", 4],
      ["copyright", 4],
      ["trade_secrets", 3],
    ]);
    expect(statutes[0]).toMatchObject({
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/3807",
      short_name: "Patent Act",
      title: "Patent Act B.E. 2522 (1979)",
      version: expect.stringContaining("Patent Act (No. 3) B.E. 2542"),
      wipo_summary: expect.stringContaining("Year of Version: 1999"),
      pdf_url:
        "https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/th/th007en_1.pdf",
      pdf_sha256: expect.stringMatching(/^[a-f\d]{64}$/),
    });
    expect(statutes[2]?.version).toContain("(No. 5) B.E. 2565 (2022)");
    expect(await client.meta()).toEqual({
      schema_version: 1,
      snapshot_date: "2026-10-26",
      source_version: "WIPO Lex English translations, 2026-10-26",
      section_count: 16,
    });

    const section = await client.getSectionByCitation(
      "Section 36 bis Patent Act",
    );
    expect(ThaiDipSectionSchema.parse(section)).toBeTruthy();
    expect(section).toMatchObject({
      statute: "patent",
      section_number: "36bis",
      section_label: "Section 36bis Patent Act",
      title: null,
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/3807",
      authority: THAI_DIP_STATUTES_AUTHORITY,
      provenance: {
        source_url: THAI_DIP_STATUTES_SOURCE_URL,
        corpus_version: "WIPO Lex English translations, 2026-10-26",
        cache_hit: true,
      },
    });
    expect(section?.text).toStartWith(
      "The scope of the rights of the patentee under Section 36",
    );
    expect(section?.text.split("\n").at(-1)).toBe(
      "[Notes: as revised by the Patent Act (No. 2) B.E. 2535]",
    );

    const secrets = await client.getSectionByCitation(
      "Section 6 Trade Secrets Act",
    );
    expect(secrets?.text).toContain("contrary to honest trade practices");
    const madrid = await client.getSection("Trademark Act", "109 / 1");
    expect(madrid?.text.split("\n").at(-1)).toBe(
      "[Notes: Section 109/1 added by Trademark Act (No. 3) B.E. 2559]",
    );
    expect(
      (await client.getSectionByCitation("Copyright Act s. 32/1"))?.text,
    ).toContain("shall not be deemed an infringement of copyright");
    expect(await client.getSection("patent", "999")).toBeNull();
    expect(await client.getSection("nonsense", "3")).toBeNull();
    expect(await client.getSectionByCitation("nonsense")).toBeNull();
    expect(hash(await readFile(fixture))).toBe(before);
  } finally {
    client.close();
  }
});

test("search ranks, filters, pages and orders in printed order, without MATCH syntax", async () => {
  const client = new ThaiDipStatutesClient({ corpusPath: fixture });
  try {
    const scoped = await client.search({
      query: "trade secrets",
      statute: "Trade Secrets Act",
    });
    expect(scoped.statute).toBe("trade_secrets");
    expect(scoped.hits.length).toBeGreaterThan(0);
    expect(scoped.hits.every((hit) => hit.statute === "trade_secrets")).toBe(
      true,
    );
    expect(scoped.hits[0]?.snippet).toContain("<mark>");
    expect(typeof scoped.hits[0]?.rank).toBe("number");

    const petty = await client.search({ query: "petty patent" });
    expect(new Set(petty.hits.map((hit) => hit.statute))).toEqual(
      new Set(["patent"]),
    );
    const paged = await client.search({ query: "patent", per_page: 1 });
    expect(paged.hits).toHaveLength(1);
    expect(paged.has_more).toBe(true);
    const second = await client.search({
      query: "patent",
      per_page: 1,
      page: 2,
    });
    expect(second.page).toBe(2);
    expect(second.hits[0]?.section_number).not.toBe(
      paged.hits[0]?.section_number,
    );

    // Outline order is printed order: 36 before 36bis before 65bis, 28bis before 109/1.
    const outline = await client.search({
      query: "patent OR trademark OR copyright",
      syntax: "or",
      sort: "outline",
      per_page: 50,
    });
    expect(
      outline.hits
        .filter((hit) => hit.statute === "patent")
        .map((hit) => hit.section_number),
    ).toEqual(["3", "5", "36", "36bis", "65bis"]);
    expect(
      outline.hits
        .filter((hit) => hit.statute === "copyright")
        .map((hit) => hit.section_number),
    ).toEqual(["4", "15", "32", "32/1"]);
    expect(outline.hits[0]?.statute).toBe("patent");
    expect(outline.hits.every((hit) => hit.rank === null)).toBe(true);

    // Operators and punctuation are literal text, never FTS5 syntax.
    for (const query of ["NEAR(trade", 'trade" OR "x', "trade-secret", "*"])
      await client.search({ query });
    expect((await client.search({ query: "   " })).hits).toEqual([]);
    expect(
      (await client.search({ query: "registrable distinctive" })).hits[0],
    ).toMatchObject({ statute: "trademark", section_number: "6" });
    await expect(
      client.search({ query: "x", per_page: 101 }),
    ).rejects.toThrow();
  } finally {
    client.close();
  }
});

test("a missing corpus reports how to supply one, and zstd bytes open in memory", async () => {
  const missing = new ThaiDipStatutesClient({
    corpusPath: join(
      import.meta.dir,
      "fixtures",
      "thai-dip-statutes",
      "absent.db",
    ),
  });
  const status = await missing.getCorpusStatus();
  expect(status.available).toBe(false);
  expect(status.statutes).toBeNull();
  expect(status.authority).toBe(THAI_DIP_STATUTES_AUTHORITY);
  expect(status.error?.message).toContain("THAI_DIP_STATUTES_CORPUS_PATH");
  await expect(missing.listStatutes()).rejects.toBeInstanceOf(CorpusError);

  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new ThaiDipStatutesClient({
    source: new Uint8Array(zstdCompressSync(bytes)),
    expectedSha256: hash(bytes),
  });
  try {
    expect((await packed.getCorpusStatus()).compression).toBe("zstd");
    expect(
      (await packed.getSectionByCitation("Section 6 Trademark Act"))?.text,
    ).toStartWith("To be registrable, a trademark must");
  } finally {
    packed.close();
  }
  const wrong = new ThaiDipStatutesClient({
    source: bytes,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).available).toBe(false);
  const wrongFile = new ThaiDipStatutesClient({
    source: new Uint8Array(zstdCompressSync(bytes)),
    expectedFileSha256: "0".repeat(64),
  });
  expect((await wrongFile.getCorpusStatus()).available).toBe(false);
});

import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  KIPO_STATUTE_ALIASES,
  KIPO_STATUTES_AUTHORITY_NOTE,
  KIPO_STATUTES_SOURCE_URL,
  KipoSectionSchema,
  KipoStatutesClient,
  parseKipoCitation,
  resolveKipoStatute,
} from "../packages/client/src/kipo-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "kipo-statutes",
  "kipo_statutes.db",
);
const hash = (value: Uint8Array) =>
  createHash("sha256").update(value).digest("hex");

test("statute names, aliases and Korean short names resolve to keys", () => {
  expect(resolveKipoStatute("Patent Act")).toBe("patent");
  expect(resolveKipoStatute("the Design Protection Act")).toBe("design");
  expect(resolveKipoStatute(" Trade  Secrets ")).toBe("unfair_competition");
  expect(
    resolveKipoStatute(
      "Unfair Competition Prevention and Trade Secret Protection Act",
    ),
  ).toBe("unfair_competition");
  expect(resolveKipoStatute("상표법")).toBe("trademark");
  expect(resolveKipoStatute("TM")).toBe("trademark");
  // Unknown names pass through lowercased, so lookups report nothing.
  expect(resolveKipoStatute("Unknown")).toBe("unknown");
  expect(KIPO_STATUTE_ALIASES["invention promotion act"]).toBe(
    "invention_promotion",
  );
});

test("citations parse in both orders, with branch articles and paragraph markers", () => {
  expect(parseKipoCitation("Article 29 Patent Act")).toEqual({
    statute: "patent",
    section_number: "29",
  });
  expect(parseKipoCitation("Patent Act Art. 29(1)")).toEqual({
    statute: "patent",
    section_number: "29",
  });
  expect(parseKipoCitation("Article 29-2 of the Patent Act")).toEqual({
    statute: "patent",
    section_number: "29-2",
  });
  expect(parseKipoCitation("Art. 2(1) 3 Trademark Act")).toEqual({
    statute: "trademark",
    section_number: "2",
  });
  expect(parseKipoCitation("Article 29 (1) 2 Patent Act")?.section_number).toBe(
    "29",
  );
  expect(parseKipoCitation("Copyright Act Article 35-5")).toEqual({
    statute: "copyright",
    section_number: "35-5",
  });
  expect(parseKipoCitation("Article 2 Trade Secrets")?.statute).toBe(
    "unfair_competition",
  );
  expect(parseKipoCitation("§ 94 Patent Act")?.section_number).toBe("94");
  expect(parseKipoCitation("특허법 제29조")).toEqual({
    statute: "patent",
    section_number: "29",
  });
  expect(parseKipoCitation("article 7 - 2 patent act")?.section_number).toBe(
    "7-2",
  );
  expect(parseKipoCitation("")).toBeNull();
  expect(parseKipoCitation("nonsense")).toBeNull();
  expect(parseKipoCitation("Article 6 No Such Act")).toBeNull();
});

test("status, statutes and articles come from the KLRI build", async () => {
  const before = hash(await readFile(fixture));
  const client = new KipoStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "KIPO statutes",
      corpus_version: "KLRI English translations (elaw.klri.re.kr), 2026-10-26",
      schema_version: 1,
      section_count: 14,
      snapshot_date: "2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
      compression: "none",
      source_url: KIPO_STATUTES_SOURCE_URL,
      authority_note: KIPO_STATUTES_AUTHORITY_NOTE,
      // The fixture is a 14-article subset of the 1,202-article build.
      metadata: { section_count: "14", fixture_subset_of: "1202" },
    });
    expect(status.authority_note).toContain("Korean text controls");
    expect(status.artifact_sha256).toBe(before);
    const statutes = await client.listStatutes();
    expect(statutes.map((item) => [item.statute, item.section_count])).toEqual([
      ["patent", 5],
      ["utility_model", 1],
      ["design", 2],
      ["trademark", 2],
      ["unfair_competition", 2],
      ["invention_promotion", 1],
      ["copyright", 1],
    ]);
    expect(statutes[0]).toMatchObject({
      source_url:
        "https://elaw.klri.re.kr/eng_service/lawView.do?hseq=68595&lang=ENG",
      short_name: "Patent Act",
      title: "PATENT ACT",
      korean_title: "특허법",
      version: "Act No. 20322, Feb. 20, 2024",
      act_number: "20322",
      promulgation_date: "2024-02-20",
      content_url:
        "https://elaw.klri.re.kr/eng_service/lawViewContent.do?hseq=68595&lang=ENG",
      sha256: expect.stringMatching(/^[a-f\d]{64}$/),
    });
    expect(statutes[6]?.version).toBe("Act No. 21336, Feb. 10, 2026");
    expect(await client.meta()).toEqual({
      schema_version: 1,
      snapshot_date: "2026-10-26",
      source_version: "KLRI English translations (elaw.klri.re.kr), 2026-10-26",
      section_count: 14,
    });

    const article = await client.getSectionByCitation("Patent Act Art. 29(1)");
    expect(KipoSectionSchema.parse(article)).toBeTruthy();
    expect(article).toMatchObject({
      statute: "patent",
      section_number: "29",
      section_label: "Article 29 Patent Act",
      title: "Requirements for Patent Registration",
      source_url:
        "https://elaw.klri.re.kr/eng_service/lawView.do?hseq=68595&lang=ENG",
      provenance: {
        source_url: KIPO_STATUTES_SOURCE_URL,
        corpus_version:
          "KLRI English translations (elaw.klri.re.kr), 2026-10-26",
        cache_hit: true,
      },
    });
    const lines = article?.text.split("\n") ?? [];
    expect(lines[0]).toBe(
      "(1) An invention having industrial applicability, other than the following, is patentable:",
    );
    expect(lines.at(-1)).toBe("[This Article Wholly Amended on Jun. 11, 2014]");

    const branch = await client.getSection("Patent Act", "7-2");
    expect(branch?.section_label).toBe("Article 7-2 Patent Act");
    const deleted = await client.getSection("patent", "26");
    expect(deleted).toMatchObject({
      title: null,
      text: "Deleted. <Dec. 2, 2011>",
    });
    // The source split Article 76's one sentence into a separate block.
    expect(
      (await client.getSectionByCitation("Article 76 Design Protection Act"))
        ?.text,
    ).toStartWith("Article 135 (excluding subparagraph 6 thereof) shall apply");
    expect(
      (await client.getSectionByCitation("Article 35-5 Copyright Act"))?.title,
    ).toBe("Fair use of works");
    expect(
      (await client.getSectionByCitation("Article 10 Trade Secrets"))?.title,
    ).toBe("Right to request prohibition of infringement of trade secrets");
    expect(await client.getSection("patent", "9999")).toBeNull();
    expect(await client.getSection("nonsense", "3")).toBeNull();
    expect(await client.getSectionByCitation("nonsense")).toBeNull();
    expect(hash(await readFile(fixture))).toBe(before);
  } finally {
    client.close();
  }
});

test("search ranks, filters, pages and orders branch articles, without MATCH syntax", async () => {
  const client = new KipoStatutesClient({ corpusPath: fixture });
  try {
    const scoped = await client.search({
      query: "trade secret",
      statute: "trade secrets",
    });
    expect(scoped.statute).toBe("unfair_competition");
    expect(scoped.hits.length).toBeGreaterThan(0);
    expect(
      scoped.hits.every((hit) => hit.statute === "unfair_competition"),
    ).toBe(true);
    expect(scoped.hits[0]?.snippet).toContain("<mark>");
    expect(typeof scoped.hits[0]?.rank).toBe("number");

    const paged = await client.search({ query: "invention", per_page: 1 });
    expect(paged.hits).toHaveLength(1);
    expect(paged.has_more).toBe(true);
    const second = await client.search({
      query: "invention",
      per_page: 1,
      page: 2,
    });
    expect(second.page).toBe(2);
    expect(second.hits[0]?.section_label).not.toBe(
      paged.hits[0]?.section_label,
    );

    // Corpus statute order, then numeric with branch articles after their base.
    const outline = await client.search({
      query: "patent OR deleted OR design OR trademark OR work",
      syntax: "or",
      sort: "outline",
      per_page: 50,
    });
    expect(
      outline.hits
        .filter((hit) => hit.statute === "patent")
        .map((hit) => hit.section_number),
    ).toEqual(["2", "7-2", "26", "29", "94"]);
    expect(outline.hits[0]?.statute).toBe("patent");
    expect(outline.hits.at(-1)?.statute).toBe("copyright");
    expect(outline.hits.every((hit) => hit.rank === null)).toBe(true);

    // Operators and punctuation are literal text, never FTS5 syntax.
    for (const query of ["NEAR(trade", 'trade" OR "x', "trade-secret", "*"])
      await client.search({ query });
    expect((await client.search({ query: "   " })).hits).toEqual([]);
    expect((await client.search({ query: "fair use" })).hits[0]).toMatchObject({
      statute: "copyright",
      section_number: "35-5",
    });
    await expect(
      client.search({ query: "x", per_page: 101 }),
    ).rejects.toThrow();
  } finally {
    client.close();
  }
});

test("a missing corpus reports how to supply one, and zstd bytes open in memory", async () => {
  const missing = new KipoStatutesClient({
    corpusPath: join(import.meta.dir, "fixtures", "kipo-statutes", "absent.db"),
  });
  const status = await missing.getCorpusStatus();
  expect(status.available).toBe(false);
  expect(status.statutes).toBeNull();
  expect(status.error?.message).toContain("KIPO_STATUTES_CORPUS_PATH");
  await expect(missing.listStatutes()).rejects.toBeInstanceOf(CorpusError);

  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new KipoStatutesClient({
    source: new Uint8Array(zstdCompressSync(bytes)),
    expectedSha256: hash(bytes),
  });
  try {
    expect((await packed.getCorpusStatus()).compression).toBe("zstd");
    expect(
      (await packed.getSectionByCitation("Article 10 Invention Promotion Act"))
        ?.title,
    ).toBe("Service invention");
  } finally {
    packed.close();
  }
  const wrong = new KipoStatutesClient({
    source: bytes,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).available).toBe(false);
});

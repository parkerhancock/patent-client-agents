import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import {
  CNIPA_STATUTE_ALIASES,
  CNIPA_STATUTES_NOTICE,
  CNIPA_STATUTES_SOURCE_URL,
  CnipaSectionSchema,
  CnipaStatutesClient,
  parseCnipaCitation,
  resolveCnipaStatute,
} from "../packages/client/src/cnipa-statutes.js";
import { CorpusError } from "../packages/client/src/corpus/outline.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "cnipa-statutes",
  "cnipa_statutes.db",
);
const hash = (value: Uint8Array) =>
  createHash("sha256").update(value).digest("hex");
const VERSION = "WIPO Lex English translations, 2026-10-26";

test("statute names resolve with or without the People's Republic of China", () => {
  expect(resolveCnipaStatute("Patent Law")).toBe("patent_law");
  expect(
    resolveCnipaStatute("Patent Law of the People’s Republic of China"),
  ).toBe("patent_law");
  expect(resolveCnipaStatute("PRC Patent Law")).toBe("patent_law");
  expect(resolveCnipaStatute("Chinese Patent Law (2020)")).toBe("patent_law");
  expect(resolveCnipaStatute("Implementing Regulations")).toBe(
    "patent_regulations",
  );
  expect(
    resolveCnipaStatute(
      "Regulations for the Implementation of the Trademark Law",
    ),
  ).toBe("trademark_regulations");
  expect(resolveCnipaStatute(" Trade  Secrets ")).toBe(
    "anti_unfair_competition",
  );
  expect(resolveCnipaStatute("AUCL")).toBe("anti_unfair_competition");
  expect(resolveCnipaStatute("Law Against Unfair Competition")).toBe(
    "anti_unfair_competition",
  );
  expect(resolveCnipaStatute("copyright")).toBe("copyright_law");
  // Unknown names pass through normalized, so lookups report nothing.
  expect(resolveCnipaStatute("Unknown")).toBe("unknown");
  expect(CNIPA_STATUTE_ALIASES["trade secret"]).toBe("anti_unfair_competition");
});

test("citations parse in both orders, with paragraph markers and units checked", () => {
  expect(parseCnipaCitation("Article 22 Patent Law")).toEqual({
    statute: "patent_law",
    section_number: "22",
  });
  expect(parseCnipaCitation("Patent Law Art. 22(3)")).toEqual({
    statute: "patent_law",
    section_number: "22",
  });
  expect(
    parseCnipaCitation(
      "Article 22 of the Patent Law of the People's Republic of China",
    ),
  ).toEqual({ statute: "patent_law", section_number: "22" });
  expect(
    parseCnipaCitation("Art. 22, paragraph 3 Patent Law")?.section_number,
  ).toBe("22");
  expect(parseCnipaCitation("Patent Law Article 022")?.section_number).toBe(
    "22",
  );
  expect(parseCnipaCitation("Rule 20 Implementing Regulations")).toEqual({
    statute: "patent_regulations",
    section_number: "20",
  });
  expect(
    parseCnipaCitation(
      "Rule 20 of the Implementing Regulations of the Patent Law",
    ),
  ).toEqual({ statute: "patent_regulations", section_number: "20" });
  expect(parseCnipaCitation("Article 9 AUCL")).toEqual({
    statute: "anti_unfair_competition",
    section_number: "9",
  });
  expect(parseCnipaCitation("Trademark Law Art. 13")?.statute).toBe(
    "trademark_law",
  );
  expect(
    parseCnipaCitation("Article 3 Trademark Implementing Regulations")?.statute,
  ).toBe("trademark_regulations");
  expect(parseCnipaCitation("24 Copyright Law")?.statute).toBe("copyright_law");
  // The 2010 Regulations number by Rule; "Article 20" names a 2023 provision.
  expect(parseCnipaCitation("Article 20 Implementing Regulations")).toBeNull();
  expect(parseCnipaCitation("Rule 22 Patent Law")).toBeNull();
  expect(parseCnipaCitation("")).toBeNull();
  expect(parseCnipaCitation("nonsense")).toBeNull();
  expect(parseCnipaCitation("Article 6 No Such Statute")).toBeNull();
});

test("status, statutes and provisions come from the WIPO Lex build", async () => {
  const before = hash(await readFile(fixture));
  const client = new CnipaStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "CNIPA statutes",
      corpus_version: VERSION,
      schema_version: 1,
      section_count: 13,
      snapshot_date: "2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
      compression: "none",
      source_url: CNIPA_STATUTES_SOURCE_URL,
      notice: CNIPA_STATUTES_NOTICE,
      // The fixture is a 13-provision subset of the 476-provision build.
      metadata: { section_count: "13", fixture_subset_of: "476" },
    });
    expect(status.notice).toContain("the Chinese text controls");
    expect(status.artifact_sha256).toBe(before);
    const statutes = await client.listStatutes();
    expect(statutes.map((item) => [item.statute, item.section_count])).toEqual([
      ["patent_law", 4],
      ["patent_regulations", 2],
      ["trademark_law", 2],
      ["trademark_regulations", 1],
      ["anti_unfair_competition", 2],
      ["copyright_law", 2],
    ]);
    expect(statutes[2]).toMatchObject({
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/23875",
      short_name: "Trademark Law",
      unit: "Article",
      version: expect.stringContaining("Year of Version: 2026"),
      translation_version: expect.stringContaining("April 23, 2019"),
      pdf_url:
        "https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/cn/cn410en_1.pdf",
      zh_pdf_url:
        "https://wipolex-res.wipo.int/edocs/lexdocs/laws/zh/cn/cn516zh_1.pdf",
      pdf_sha256: expect.stringMatching(/^[a-f\d]{64}$/),
    });
    expect(statutes[1]).toMatchObject({
      unit: "Rule",
      translation_version: expect.stringContaining("January 9, 2010"),
    });
    expect(await client.meta()).toEqual({
      schema_version: 1,
      snapshot_date: "2026-10-26",
      source_version: VERSION,
      section_count: 13,
    });

    const novelty = await client.getSectionByCitation("Patent Law Art. 22(3)");
    expect(CnipaSectionSchema.parse(novelty)).toBeTruthy();
    expect(novelty).toMatchObject({
      statute: "patent_law",
      section_number: "22",
      section_label: "Article 22 Patent Law",
      title: "Chapter II Requirements for Granting Patent Rights",
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/21027",
      provenance: {
        source_url: CNIPA_STATUTES_SOURCE_URL,
        corpus_version: VERSION,
        cache_hit: true,
      },
    });
    const paragraphs = novelty?.text.split("\n") ?? [];
    expect(paragraphs).toHaveLength(5);
    expect(paragraphs[0]).toBe(
      "Any invention or utility model for which a patent right is to be granted shall meet the requirements of novelty, inventiveness and practical use.",
    );
    expect(paragraphs[2]).toStartWith("Inventiveness means that");

    const rule = await client.getSectionByCitation(
      "Rule 6 Implementing Regulations",
    );
    expect(rule?.section_label).toBe("Rule 6 Patent Implementing Regulations");
    expect(rule?.text.split("\n").at(-1)).toBe(
      "[Note: Incorporating original Rule 7]",
    );
    expect(
      (await client.getSection("Copyright Law", "Article 24"))?.title,
    ).toBe("Chapter II Copyright, Section 4 Limitations on Rights");
    expect(
      (await client.getSectionByCitation("Article 9 trade secrets"))?.text,
    ).toContain("“a trade secret” means");
    expect(await client.getSection("patent_law", "999")).toBeNull();
    expect(await client.getSection("nonsense", "3")).toBeNull();
    expect(await client.getSectionByCitation("nonsense")).toBeNull();
    expect(hash(await readFile(fixture))).toBe(before);
  } finally {
    client.close();
  }
});

test("search ranks, filters, pages and orders without MATCH syntax", async () => {
  const client = new CnipaStatutesClient({ corpusPath: fixture });
  try {
    const scoped = await client.search({
      query: "trade secret",
      statute: "trade secrets",
    });
    expect(scoped.statute).toBe("anti_unfair_competition");
    expect(scoped.hits.map((hit) => hit.section_number).sort()).toEqual([
      "32",
      "9",
    ]);
    expect(scoped.hits[0]?.snippet).toContain("<mark>");
    expect(typeof scoped.hits[0]?.rank).toBe("number");

    const unscoped = await client.search({ query: "well-known trademark" });
    expect(new Set(unscoped.hits.map((hit) => hit.statute))).toEqual(
      new Set(["trademark_law", "trademark_regulations"]),
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
    expect(second.hits[0]?.section_label).not.toBe(
      paged.hits[0]?.section_label,
    );

    // Statutes in key order, numbers numerically ("2" < "22" < "82").
    const outline = await client.search({
      query: "law",
      sort: "outline",
      per_page: 50,
    });
    expect(
      outline.hits
        .filter((hit) => hit.statute === "patent_law")
        .map((hit) => hit.section_number),
    ).toEqual(["2", "22", "26", "82"]);
    expect(outline.hits[0]?.statute).toBe("patent_law");
    expect(outline.hits.at(-1)?.statute).toBe("copyright_law");
    expect(outline.hits.every((hit) => hit.rank === null)).toBe(true);

    // Operators and punctuation are literal text, never FTS5 syntax.
    for (const query of ["NEAR(trade", 'trade" OR "x', "anti-unfair", "*"])
      await client.search({ query });
    expect((await client.search({ query: "   " })).hits).toEqual([]);
    await expect(
      client.search({ query: "x", per_page: 101 }),
    ).rejects.toThrow();
  } finally {
    client.close();
  }
});

test("a missing corpus reports how to supply one, and zstd bytes open in memory", async () => {
  const missing = new CnipaStatutesClient({
    corpusPath: join(
      import.meta.dir,
      "fixtures",
      "cnipa-statutes",
      "absent.db",
    ),
  });
  const status = await missing.getCorpusStatus();
  expect(status.available).toBe(false);
  expect(status.statutes).toBeNull();
  expect(status.notice).toBe(CNIPA_STATUTES_NOTICE);
  expect(status.error?.message).toContain("CNIPA_STATUTES_CORPUS_PATH");
  await expect(missing.listStatutes()).rejects.toBeInstanceOf(CorpusError);

  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new CnipaStatutesClient({
    source: new Uint8Array(zstdCompressSync(bytes)),
    expectedSha256: hash(bytes),
  });
  try {
    expect((await packed.getCorpusStatus()).compression).toBe("zstd");
    expect(
      (await packed.getSectionByCitation("Article 3 Copyright Law"))?.title,
    ).toBe("Chapter I General Provisions");
  } finally {
    packed.close();
  }
  const wrong = new CnipaStatutesClient({
    source: bytes,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).available).toBe(false);
});

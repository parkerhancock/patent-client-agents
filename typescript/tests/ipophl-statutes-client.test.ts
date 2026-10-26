import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  IPOPHL_STATUTES_SOURCE_URL,
  IpophlSectionSchema,
  IpophlStatutesClient,
  parseIpophlCitation,
  resolveIpophlStatute,
} from "../packages/client/src/ipophl-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "ipophl-statutes",
  "ipophl_statutes.db",
);
const hash = (value: Uint8Array) =>
  createHash("sha256").update(value).digest("hex");
const VERSION = "LawPhil, Acts as enacted, 2026-10-26";

test("statute names, aliases and Republic Act numbers resolve to keys", () => {
  expect(resolveIpophlStatute("IP Code")).toBe("ra8293");
  expect(
    resolveIpophlStatute("the Intellectual Property Code of the Philippines"),
  ).toBe("ra8293");
  expect(resolveIpophlStatute("R.A. No. 8293")).toBe("ra8293");
  expect(resolveIpophlStatute("Republic Act No. 10372")).toBe("ra10372");
  expect(resolveIpophlStatute("RA 9150")).toBe("ra9150");
  expect(resolveIpophlStatute("ra9502")).toBe("ra9502");
  expect(resolveIpophlStatute("Cheaper Medicines Act")).toBe("ra9502");
  expect(resolveIpophlStatute("IP Code (1997)")).toBe("ra8293");
  // Unknown names pass through lowercased, so lookups report nothing.
  expect(resolveIpophlStatute("Unknown")).toBe("unknown");
});

test("citations parse in both orders, dropping subsections and paragraphs", () => {
  expect(parseIpophlCitation("Section 21 IP Code")).toEqual({
    statute: "ra8293",
    section_number: "21",
  });
  expect(parseIpophlCitation("Sec. 123.1(d) RA 8293")).toEqual({
    statute: "ra8293",
    section_number: "123",
  });
  expect(parseIpophlCitation("Section 3 RA 10372")).toEqual({
    statute: "ra10372",
    section_number: "3",
  });
  expect(
    parseIpophlCitation(
      "Section 22 of the Intellectual Property Code of the Philippines",
    )?.section_number,
  ).toBe("22");
  expect(parseIpophlCitation("RA 8293 Sec. 22")?.statute).toBe("ra8293");
  expect(parseIpophlCitation("R.A. No. 8293, Section 72.1")).toEqual({
    statute: "ra8293",
    section_number: "72",
  });
  expect(parseIpophlCitation("§ 72.1 R.A. No. 8293")?.section_number).toBe(
    "72",
  );
  expect(parseIpophlCitation("SEC. 5 Republic Act No. 9502")?.statute).toBe(
    "ra9502",
  );
  expect(parseIpophlCitation("Section 93-A RA 8293")?.section_number).toBe(
    "93A",
  );
  expect(parseIpophlCitation("section 9a ip code")?.section_number).toBe("9A");
  expect(parseIpophlCitation("")).toBeNull();
  expect(parseIpophlCitation("nonsense")).toBeNull();
  expect(parseIpophlCitation("Section 6 Patents Act")).toBeNull();
  expect(parseIpophlCitation("Section 5 RA 6675")).toBeNull();
});

test("status, Acts and sections come from the LawPhil build", async () => {
  const before = hash(await readFile(fixture));
  const client = new IpophlStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "IPOPHL statutes",
      corpus_version: VERSION,
      schema_version: 1,
      section_count: 16,
      snapshot_date: "2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
      compression: "none",
      source_url: IPOPHL_STATUTES_SOURCE_URL,
      text_status: expect.stringContaining("not consolidated"),
      // The fixture is a 16-section subset of the 327-section build.
      metadata: { section_count: "16", fixture_subset_of: "327" },
    });
    expect(status.artifact_sha256).toBe(before);
    const statutes = await client.listStatutes();
    expect(statutes.map((item) => [item.statute, item.section_count])).toEqual([
      ["ra8293", 10],
      ["ra9150", 2],
      ["ra9502", 2],
      ["ra10372", 2],
    ]);
    expect(statutes[2]).toMatchObject({
      source_url:
        "https://lawphil.net/statutes/repacts/ra2008/ra_9502_2008.html",
      short_name: "RA 9502",
      role: "amendment",
      approved: "2008-06-06",
      page_title: expect.stringMatching(/^AN ACT PROVIDING FOR CHEAPER/),
      page_sha256: expect.stringMatching(/^[a-f\d]{64}$/),
      missing_sections: ["8"],
    });
    expect(await client.meta()).toEqual({
      schema_version: 1,
      snapshot_date: "2026-10-26",
      source_version: VERSION,
      section_count: 16,
    });

    const section = await client.getSectionByCitation("Section 22 IP Code");
    expect(IpophlSectionSchema.parse(section)).toBeTruthy();
    expect(section).toMatchObject({
      statute: "ra8293",
      section_number: "22",
      section_label: "Section 22 RA 8293",
      title: "Non-Patentable Inventions",
      source_url:
        "https://lawphil.net/statutes/repacts/ra1997/ra_8293_1997.html",
      amended_by: ["Section 5 RA 9502"],
      provenance: {
        source_url: IPOPHL_STATUTES_SOURCE_URL,
        corpus_version: VERSION,
        cache_hit: true,
      },
    });
    const lines = section?.text.split("\n") ?? [];
    expect(lines[0]).toBe(
      "The following shall be excluded from patent protection:",
    );
    // As enacted: the 2008 drug-discovery clause is in RA 9502, not here.
    expect(lines[1]).toBe(
      "22.1. Discoveries, scientific theories and mathematical methods;",
    );
    expect(section?.text).toEndWith("(Sec. 8, R.A. No. 165a)");

    const government = await client.getSection("IP Code", "74");
    expect(government?.amended_by).toEqual([
      "Section 8 RA 9502 (not on the source page)",
    ]);
    expect((await client.getSection("ra8293", "21"))?.amended_by).toEqual([]);
    const amendment = await client.getSectionByCitation("Section 5 RA 9502");
    expect(amendment).toMatchObject({ title: null, amended_by: [] });
    expect(amendment?.text).toContain('"SEC. 22.');
    expect(
      (await client.getSectionByCitation("Section 7 RA 9502"))?.text,
    ).toContain(
      "[Source note: LawPhil's page repeats part of the new Section 72",
    );
    expect(
      (await client.getSectionByCitation("Section 3 RA 10372"))?.text,
    ).toContain('"SEC. 9A. The Bureau of Copyright and Other Related Rights.');
    expect(
      (await client.getSectionByCitation("Sec. 123.1(d) RA 8293"))?.title,
    ).toBe("Registrability");
    expect(await client.getSection("ra8293", "9999")).toBeNull();
    expect(await client.getSection("nonsense", "3")).toBeNull();
    expect(
      await client.getSectionByCitation("Section 93-A IP Code"),
    ).toBeNull();
    expect(await client.getSectionByCitation("nonsense")).toBeNull();
    expect(hash(await readFile(fixture))).toBe(before);
  } finally {
    client.close();
  }
});

test("search ranks, filters, pages and orders by Act, without MATCH syntax", async () => {
  const client = new IpophlStatutesClient({ corpusPath: fixture });
  try {
    const scoped = await client.search({
      query: "inventive step",
      statute: "IP Code",
    });
    expect(scoped.statute).toBe("ra8293");
    expect(scoped.hits.length).toBeGreaterThan(0);
    expect(scoped.hits.every((hit) => hit.statute === "ra8293")).toBe(true);
    expect(scoped.hits[0]?.snippet).toContain("<mark>");
    expect(typeof scoped.hits[0]?.rank).toBe("number");

    const unscoped = await client.search({ query: "drugs medicines" });
    expect(new Set(unscoped.hits.map((hit) => hit.statute))).toEqual(
      new Set(["ra9502"]),
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

    // Act order (not alphabetical: ra10372 sorts last), then numeric sections.
    const outline = await client.search({
      query: "patent copyright",
      syntax: "or",
      sort: "outline",
      per_page: 50,
    });
    const statutes = [...new Set(outline.hits.map((hit) => hit.statute))];
    expect(statutes).toEqual(["ra8293", "ra9150", "ra9502", "ra10372"]);
    const code = outline.hits
      .filter((hit) => hit.statute === "ra8293")
      .map((hit) => Number(hit.section_number));
    expect(code).toEqual([...code].sort((a, b) => a - b));
    expect(outline.hits.every((hit) => hit.rank === null)).toBe(true);

    // Operators and punctuation are literal text, never FTS5 syntax.
    for (const query of ["NEAR(patent", 'patent" OR "x', "layout-design", "*"])
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
  const missing = new IpophlStatutesClient({
    corpusPath: join(
      import.meta.dir,
      "fixtures",
      "ipophl-statutes",
      "absent.db",
    ),
  });
  const status = await missing.getCorpusStatus();
  expect(status.available).toBe(false);
  expect(status.statutes).toBeNull();
  expect(status.error?.message).toContain("IPOPHL_STATUTES_CORPUS_PATH");
  await expect(missing.listStatutes()).rejects.toBeInstanceOf(CorpusError);

  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new IpophlStatutesClient({
    source: new Uint8Array(zstdCompressSync(bytes)),
    expectedSha256: hash(bytes),
  });
  try {
    expect((await packed.getCorpusStatus()).compression).toBe("zstd");
    expect(
      (await packed.getSectionByCitation("Section 21 IP Code"))?.title,
    ).toBe("Patentable Inventions");
  } finally {
    packed.close();
  }
  const wrong = new IpophlStatutesClient({
    source: bytes,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).available).toBe(false);
});

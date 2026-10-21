import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { copyFile, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  EpcClient,
  EpoCaseLawClient,
  EpoGuidelinesClient,
  type EpoLegalCorpusClient,
  EpoPctGuidelinesClient,
  EpoUpGuidelinesClient,
  normalizeEpoHref,
} from "../packages/client/src/epo-legal.js";
import { CorpusProvenanceSchema } from "../packages/client/src/models.js";

const fixtures = join(import.meta.dir, "fixtures", "epo-legal");
const fixture = (name: string) => join(fixtures, `${name}.db`);
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");

async function withCopy(
  name: string,
  sql: string,
  run: (filename: string) => Promise<void>,
) {
  const directory = await mkdtemp(join(tmpdir(), "pca-epo-legal-test-"));
  const filename = join(directory, "corpus.db");
  await copyFile(fixture(name), filename);
  if (sql) {
    const db = new Database(filename);
    try {
      db.exec(sql);
    } finally {
      db.close();
    }
  }
  try {
    await run(filename);
  } finally {
    await rm(directory, { recursive: true });
  }
}

interface BookCase {
  name: string;
  make: (corpusPath: string) => EpoLegalCorpusClient<unknown>;
  edition: string;
  query: string;
  firstHit: { href: string; path: string[]; result_url: string };
  references: [string, string, unknown][];
  hashed: [string, string];
  sectionNumber: [string, string];
}

const books: BookCase[] = [
  {
    name: "epc",
    make: (corpusPath) => new EpcClient({ corpusPath }),
    edition: "2020",
    query: "inventive step",
    firstHit: {
      href: "a52",
      path: ["Article", "Article 52"],
      result_url: "https://www.epo.org/en/legal/epc/2020/a52.html",
    },
    references: [
      ["Article 54", "a54", { kind: "article", number: "54" }],
      ["Art. 54", "a54", { kind: "article", number: "54" }],
      ["R. 71", "r71", { kind: "rule", number: "71" }],
      ["rule 1", "r1", { kind: "rule", number: "1" }],
      ["a52", "a52", { kind: "article", number: "52" }],
      [
        "https://www.epo.org/en/legal/epc/2020/r71.html",
        "r71",
        { kind: "rule", number: "71" },
      ],
    ],
    hashed: [
      "a54",
      "bb3a6e41c70b65a77a5ae7cbe2382a6bb3e17038ebaa7aa2d8c4a572e9713dfc",
    ],
    sectionNumber: ["Article 54", "a54"],
  },
  {
    name: "caselaw",
    make: (corpusPath) => new EpoCaseLawClient({ corpusPath }),
    edition: "2022",
    query: "inventive step",
    firstHit: {
      href: "clr_i_d_9_1",
      path: ["Part I", "I.D.9.1"],
      result_url: "https://www.epo.org/en/legal/case-law/2022/clr_i_d_9_1.html",
    },
    references: [
      ["I.A.1", "clr_i_a_1", { part: "I", subpart: "A", section: "1" }],
      ["I-C-5-2", "clr_i_c_5_2", { part: "I", subpart: "C", section: "5.2" }],
      ["clr_foreword", "clr_foreword", null],
      [
        "/en/legal/case-law/2022/clr_i_d_9_1.html",
        "clr_i_d_9_1",
        { part: "I", subpart: "D", section: "9.1" },
      ],
    ],
    hashed: [
      "clr_i_a_1",
      "2a7f790e1b6817d33172cc4646636e4323138d3432f426fe6cdb1d4742b0363a",
    ],
    sectionNumber: ["I.A.1", "clr_i_a_1"],
  },
  {
    name: "guidelines",
    make: (corpusPath) => new EpoGuidelinesClient({ corpusPath }),
    edition: "2024",
    query: "discoveries",
    firstHit: {
      href: "g_ii_3_1",
      path: ["Part G", "G-II, 3.1"],
      result_url:
        "https://www.epo.org/en/legal/guidelines-epc/2024/g_ii_3_1.html",
    },
    references: [
      ["G-II, 3.1", "g_ii_3_1", { part: "G", chapter: "II", section: "3.1" }],
      ["G II 3.1", "g_ii_3_1", { part: "G", chapter: "II", section: "3.1" }],
      ["G.II.3", "g_ii_3", { part: "G", chapter: "II", section: "3" }],
      ["A-I", "a_i", { part: "A", chapter: "I", section: null }],
      [
        "g_vii_5_4.html",
        "g_vii_5_4",
        { part: "G", chapter: "VII", section: "5.4" },
      ],
    ],
    hashed: [
      "g_ii_3_1",
      "c6c8969a05f2aef78bfa281d99dde59d66183c9044408d450fd129c20672e57b",
    ],
    sectionNumber: ["G-II, 3.1", "g_ii_3_1"],
  },
  {
    name: "pct_guidelines",
    make: (corpusPath) => new EpoPctGuidelinesClient({ corpusPath }),
    edition: "2024",
    query: "scope",
    firstHit: {
      href: "b_iii_1",
      path: ["Part B", "B-III, 1"],
      result_url:
        "https://www.epo.org/en/legal/guidelines-pct/2024/b_iii_1.html",
    },
    references: [
      [
        "B-III, 2.3.3",
        "b_iii_2_3_3",
        { part: "B", chapter: "III", section: "2.3.3" },
      ],
      ["B-III", "b_iii", { part: "B", chapter: "III", section: null }],
      [
        "https://www.epo.org/en/legal/guidelines-pct/2024/b_iii_1.html",
        "b_iii_1",
        { part: "B", chapter: "III", section: "1" },
      ],
    ],
    hashed: [
      "b_iii_2_3_3",
      "8abf39e4e6308e5c434d727dfa97f7bee45fcc7e433cda737a52a2b344749c50",
    ],
    sectionNumber: ["B-III, 1", "b_iii_1"],
  },
  {
    name: "up_guidelines",
    make: (corpusPath) => new EpoUpGuidelinesClient({ corpusPath }),
    edition: "2026",
    query: "new",
    firstHit: {
      href: "section_2_4",
      path: ["Section 2", "2.4"],
      result_url: "https://www.epo.org/en/legal/guidelines-up/2026/section_2_4",
    },
    references: [
      ["1.2.1", "section_1_2_1", { section: "1.2.1" }],
      ["Section 2.4", "section_2_4", { section: "2.4" }],
      ["§ 1", "section_1", { section: "1" }],
      ["section_1_2_1", "section_1_2_1", { section: "1.2.1" }],
      [
        "https://www.epo.org/en/legal/guidelines-up/2026/section_2_4",
        "section_2_4",
        { section: "2.4" },
      ],
    ],
    hashed: [
      "section_1_2_1",
      "ea262d25a9a2896f454a7ae9cb2d8e755d763c1db36f7b6aab8c34addffa1ce1",
    ],
    sectionNumber: ["1.2.1", "section_1_2_1"],
  },
];

for (const book of books)
  test(`${book.name}: search, citation lookup, compressed HTML and status from real rows`, async () => {
    const before = hash(await readFile(fixture(book.name)));
    const client = book.make(fixture(book.name));
    try {
      const status = await client.getCorpusStatus();
      expect(status).toMatchObject({
        available: true,
        edition: book.edition,
        corpus_version: book.edition,
        release_verified: false,
        schema_version: 1,
        snapshot_date: "2026-05-14",
        corpus_synced_at: "2026-05-14T00:00:00.000Z",
        compression: "none",
      });
      expect(status.artifact_sha256).toBe(before);

      const search = await client.search({ query: book.query, limit: 1 });
      expect(search.hits[0]).toMatchObject(book.firstHit);
      expect(search.hits[0]?.snippet).toContain("<mark>");
      expect(search.provenance.corpus_version).toBe(book.edition);
      expect(CorpusProvenanceSchema.parse(search.provenance).cache_hit).toBe(
        true,
      );

      for (const [reference, href, citation] of book.references) {
        const section = await client.getSection(reference);
        expect([reference, section.href]).toEqual([reference, href]);
        expect(section.citation).toEqual(citation);
        expect(section.source_url).toContain(`/${book.edition}/${href}`);
        expect(section.html).toStartWith("<");
        expect(section.text.length).toBeGreaterThan(100);
      }
      const [href, digest] = book.hashed;
      const hashed = await client.getSection(href);
      expect(hashed.content_sha256).toBe(digest);
      expect(hash(hashed.html)).toBe(digest);
      expect(hashed.provenance.source_url).toBe(hashed.source_url);

      expect(await client.resolveSectionHref(book.sectionNumber[0])).toBe(
        book.sectionNumber[1],
      );
      expect(await client.resolveSectionHref("no such section")).toBeNull();
      expect(await client.listVersions()).toEqual([
        {
          label: `${client.book.label} ${book.edition} edition (installed snapshot 2026-05-14)`,
          value: book.edition,
          current: true,
        },
      ]);
      expect(
        (await client.getSection(href, { version: book.edition })).href,
      ).toBe(href);
      await expect(
        client.getSection(href, { version: "1999" }),
      ).rejects.toMatchObject({ code: "VERSION_UNAVAILABLE" });
      await expect(client.getSection("Z-IX, 99")).rejects.toMatchObject({
        code: "SECTION_NOT_FOUND",
      });
    } finally {
      client.close();
    }
    expect(hash(await readFile(fixture(book.name)))).toBe(before);
  });

test("EPO search quotes caller syntax, paginates and sorts by outline", async () => {
  const client = new EpcClient({ corpusPath: fixture("epc") });
  try {
    const first = await client.search({
      query: "patent",
      sort: "outline",
      limit: 2,
    });
    expect(first.hits.map((hit) => hit.section_number)).toEqual([
      "Article 52",
      "Article 54",
    ]);
    expect(first.has_more).toBe(true);
    const rest = await client.search({
      query: "patent",
      sort: "outline",
      limit: 2,
      offset: 2,
    });
    expect(rest.hits.map((hit) => hit.section_number)).toEqual([
      "Rule 1",
      "Rule 71",
    ]);
    expect(rest.has_more).toBe(false);
    // FTS operators in user input are quoted, never executed.
    expect(
      (await client.search({ query: 'patent" OR "zzz', limit: 5 })).hits,
    ).toEqual([]);
    expect(
      (await client.search({ query: "inventive zzzunknown", syntax: "or" }))
        .hits[0]?.href,
    ).toBe("a52");
    expect(
      (await client.search({ query: "inventive zzzunknown", syntax: "and" }))
        .hits,
    ).toEqual([]);
    expect((await client.search({ query: "   " })).hits).toEqual([]);
    const controller = new AbortController();
    controller.abort();
    await expect(
      client.search({ query: "patent", signal: controller.signal }),
    ).rejects.toMatchObject({ code: "ABORTED" });
  } finally {
    client.close();
  }
});

test("EPO metadata gaps stay unknown and untrusted source paths never become URLs", async () => {
  await withCopy(
    "guidelines",
    "DELETE FROM meta WHERE key IN ('guidelines_year', 'snapshot_date', 'source')",
    async (filename) => {
      const client = new EpoGuidelinesClient({ corpusPath: filename });
      try {
        const status = await client.getCorpusStatus();
        expect(status).toMatchObject({
          available: true,
          edition: null,
          corpus_version: "unknown",
          snapshot_date: null,
          corpus_synced_at: null,
          source_url: "https://www.epo.org/en/legal/guidelines-epc",
        });
        const section = await client.getSection("G-II, 3.1");
        expect(section.version).toBe("unknown");
        expect(section.source_url).toBe(
          "https://www.epo.org/en/legal/guidelines-epc",
        );
        expect(section.provenance).toMatchObject({
          retrieved_at: null,
          corpus_synced_at: null,
          corpus_version: "unknown",
        });
        expect((await client.listVersions())[0]?.value).toBe("current");
        await expect(
          client.getSection("G-II, 3.1", { version: "2024" }),
        ).rejects.toMatchObject({ code: "VERSION_UNAVAILABLE" });
      } finally {
        client.close();
      }
    },
  );
  await withCopy(
    "guidelines",
    "DELETE FROM meta WHERE key = 'guidelines_year'",
    async (filename) => {
      const client = new EpoGuidelinesClient({ corpusPath: filename });
      try {
        // The builder's exact epo.org source path still names the edition.
        expect((await client.getCorpusStatus()).edition).toBe("2024");
      } finally {
        client.close();
      }
    },
  );
  await withCopy(
    "guidelines",
    "DELETE FROM meta WHERE key = 'guidelines_year'; UPDATE meta SET value = 'https://evil.example/en/legal/guidelines-epc/2024' WHERE key = 'source'",
    async (filename) => {
      const client = new EpoGuidelinesClient({ corpusPath: filename });
      try {
        const status = await client.getCorpusStatus();
        expect(status.edition).toBeNull();
        expect(status.source_url).toBe(
          "https://www.epo.org/en/legal/guidelines-epc",
        );
      } finally {
        client.close();
      }
    },
  );
  await withCopy(
    "epc",
    "UPDATE meta SET value = 'current' WHERE key = 'epc_year'; DELETE FROM meta WHERE key = 'source'",
    async (filename) => {
      const client = new EpcClient({ corpusPath: filename });
      try {
        expect((await client.getCorpusStatus()).corpus_version).toBe("unknown");
      } finally {
        client.close();
      }
    },
  );
});

test("EPO corpora report unavailable, WAL and pin failures without creating files", async () => {
  const directory = await mkdtemp(join(tmpdir(), "pca-epo-legal-missing-"));
  const missing = join(directory, "absent.db");
  try {
    const client = new EpoCaseLawClient({ corpusPath: missing });
    const status = await client.getCorpusStatus();
    expect(status.available).toBe(false);
    expect(status.corpus_version).toBe("unknown");
    expect(status.error?.code).toBe("CORPUS_UNAVAILABLE");
    expect(status.error?.message).toContain("EPO Case Law corpus");
    expect(status.error?.message).toContain("CASELAW_CORPUS_PATH");
    await expect(client.search({ query: "patent" })).rejects.toBeInstanceOf(
      CorpusError,
    );
    client.close();
    expect(await Bun.file(missing).exists()).toBe(false);
  } finally {
    await rm(directory, { recursive: true });
  }
  await withCopy("epc", "PRAGMA journal_mode=WAL", async (filename) => {
    const client = new EpcClient({ corpusPath: filename });
    try {
      expect((await client.getCorpusStatus()).error?.code).toBe(
        "CORPUS_WAL_UNSUPPORTED",
      );
    } finally {
      client.close();
    }
  });
  const pinned = new EpcClient({
    corpusPath: fixture("epc"),
    expectedSha256: "0".repeat(64),
  });
  try {
    expect((await pinned.getCorpusStatus()).error?.code).toBe(
      "CHECKSUM_MISMATCH",
    );
  } finally {
    pinned.close();
  }
  expect(
    () => new EpcClient({ corpusPath: fixture("epc"), expectedSha256: "xyz" }),
  ).toThrow();
});

test("EPO clients read their Python-compatible path and pin variables", async () => {
  const saved = {
    path: process.env.UP_GUIDELINES_CORPUS_PATH,
    pin: process.env.UP_GUIDELINES_CORPUS_SHA256,
  };
  const digest = hash(await readFile(fixture("up_guidelines")));
  process.env.UP_GUIDELINES_CORPUS_PATH = fixture("up_guidelines");
  process.env.UP_GUIDELINES_CORPUS_SHA256 = digest;
  const client = new EpoUpGuidelinesClient();
  try {
    expect(await client.getCorpusStatus()).toMatchObject({
      available: true,
      artifact_sha256: digest,
      edition: "2026",
    });
  } finally {
    client.close();
    for (const [key, value] of [
      ["UP_GUIDELINES_CORPUS_PATH", saved.path],
      ["UP_GUIDELINES_CORPUS_SHA256", saved.pin],
    ] as const)
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
  }
});

test("EPO hrefs normalize from slugs, paths and URLs for each book", () => {
  expect(normalizeEpoHref("A54.html", "epc")).toBe("a54");
  expect(
    normalizeEpoHref("https://www.epo.org/en/legal/epc/2020/a54.html", "epc"),
  ).toBe("a54");
  expect(normalizeEpoHref("/legal/case-law/2022/clr_i_a_1", "case-law")).toBe(
    "clr_i_a_1",
  );
  expect(
    normalizeEpoHref(
      "/en/legal/guidelines-up/2026/section_1_2_1",
      "guidelines-up",
    ),
  ).toBe("section_1_2_1");
});

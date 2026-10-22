import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { copyFile, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import { CorpusProvenanceSchema } from "../packages/client/src/models.js";
import {
  getMoppCorpusStatus,
  MoppClient,
  normalizeMoppHref,
} from "../packages/client/src/ukipo-mopp.js";

const fixture = join(import.meta.dir, "fixtures", "ukipo-mopp", "mopp.db");
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");
const INDEX = "https://www.gov.uk/guidance/manual-of-patent-practice-mopp";
const S4A = "-section-4a-methods-of-treatment-or-diagnosis";

test("MoPP status labels the snapshot by date, as Python's get_corpus_status does", async () => {
  const status = await getMoppCorpusStatus({ corpusPath: fixture });
  expect(status).toMatchObject({
    available: true,
    corpus_version: "snapshot-2026-05-14",
    schema_version: 1,
    section_count: 6,
    snapshot_date: "2026-05-14",
    corpus_synced_at: "2026-05-14T00:00:00.000Z",
    compression: "none",
    source_url: INDEX,
    metadata: { source: INDEX },
  });
  expect(status.artifact_sha256).toBe(hash(await readFile(fixture)));
  const missing = await getMoppCorpusStatus({
    corpusPath: join(tmpdir(), "pca-no-such-mopp.db"),
  });
  expect(missing).toMatchObject({
    available: false,
    corpus_version: "unknown",
    error: { code: "CORPUS_UNAVAILABLE" },
  });
  expect(missing.error?.message).toContain("MOPP_CORPUS_PATH");
});

test("MoPP search quotes terms, pages with has_more and links the stored slug", async () => {
  const client = new MoppClient({ corpusPath: fixture });
  try {
    const phrase = await client.search({ query: "methods of treatment" });
    expect(phrase.hits.map((hit) => hit.section_number)).toEqual(["4A", "4"]);
    expect(phrase.hits[0]).toMatchObject({
      title: "4A - Section 4A: methods of treatment or diagnosis",
      href: S4A,
      path: ["4A"],
      // The leading dash is part of the live gov.uk URL.
      result_url: `${INDEX}/${S4A}`,
      snippet: expect.stringContaining("<mark>"),
    });
    expect(CorpusProvenanceSchema.safeParse(phrase.provenance).success).toBe(
      true,
    );
    expect(phrase.provenance).toMatchObject({
      source_url: INDEX,
      source_name: "UKIPO Manual of Patent Practice (MoPP)",
      cache_hit: true,
      retrieved_at: "2026-05-14T00:00:00.000Z",
      corpus_synced_at: "2026-05-14T00:00:00.000Z",
      corpus_version: "snapshot-2026-05-14",
    });

    // Outline order is the stored section_number text order, nulls first, as in Python.
    const outline = await client.search({
      query: "comptroller",
      syntax: "and",
      sort: "outline",
      limit: 3,
    });
    expect(outline.hits.map((hit) => hit.href)).toEqual([
      "glossary-of-terms-and-abbreviations-used-in-this-manual",
      "sections-11-effect-of-transfer-of-application-under-s-8-or-10",
      "section-102a-right-of-audience-etc-in-proceedings-on-appeal-from-the-comptroller-repealed",
    ]);
    // The builder stored no number for "sections-11-..."; the reader takes it from the slug.
    expect(outline.hits.map((hit) => hit.section_number)).toEqual([
      null,
      "11",
      "102A",
    ]);
    expect(outline.has_more).toBe(true);
    const last = await client.search({
      query: "comptroller",
      syntax: "and",
      sort: "outline",
      limit: 3,
      offset: 3,
    });
    expect(last.hits.map((hit) => hit.section_number)).toEqual(["4", "73"]);
    expect(last.has_more).toBe(false);

    expect(
      (await client.search({ query: "diagnosis glossary", syntax: "or" })).hits
        .length,
    ).toBeGreaterThan(1);
    for (const query of ["NEAR(zzqx)", " "])
      expect((await client.search({ query, syntax: "and" })).hits).toEqual([]);
    // FTS syntax in user text is searched as words, never executed.
    const injected = await client.search({
      query: '" OR 1=1 --',
      syntax: "and",
    });
    expect(injected.hits.map((hit) => hit.section_number)).toEqual(["4", "73"]);
    await expect(
      client.search({ query: "patent", limit: 101 }),
    ).rejects.toThrow();
    await expect(client.search({ query: "patent\0" })).rejects.toThrow("NUL");
    await expect(
      client.search({ query: "patent", version: "2025" }),
    ).rejects.toMatchObject({ code: "VERSION_UNAVAILABLE" });
  } finally {
    client.close();
  }
});

test("MoPP sections resolve the references Python misses", async () => {
  const client = new MoppClient({ corpusPath: fixture });
  try {
    const byNumber = await client.getSection("4A");
    expect(byNumber).toMatchObject({
      href: S4A,
      section_number: "4A",
      title: "Section 4A: methods of treatment or diagnosis",
      version: "current",
      source_url: `${INDEX}/${S4A}`,
      // Same decoded HTML hash as Python's MoppClient.get_section("4A").
      content_sha256:
        "a56dcb83cc730fd7efd863acede527b753f5d4a1d9b75241a71e5e96fd0edad4",
    });
    expect(byNumber.content_sha256).toBe(hash(byNumber.html));
    expect(byNumber.text).toHaveLength(52_724);
    expect(byNumber.provenance.source_url).toBe(byNumber.source_url);

    // Python finds none of these: lowercase letters, the unnumbered
    // "sections-11-..." page, paragraph citations, the slug without its dash,
    // and a gov.uk URL with a fragment.
    const cases: [string, string][] = [
      ["4a", S4A],
      [
        "102a",
        "section-102a-right-of-audience-etc-in-proceedings-on-appeal-from-the-comptroller-repealed",
      ],
      ["11", "sections-11-effect-of-transfer-of-application-under-s-8-or-10"],
      ["4.05", "section-4-industrial-application"],
      [
        "73.02",
        "section-73-comptroller-s-power-to-revoke-patents-on-his-own-initiative",
      ],
      ["section-4a-methods-of-treatment-or-diagnosis", S4A],
      [
        `${INDEX}/section-4-industrial-application#ref4-01`,
        "section-4-industrial-application",
      ],
      [
        "/guidance/manual-of-patent-practice-mopp/glossary-of-terms-and-abbreviations-used-in-this-manual",
        "glossary-of-terms-and-abbreviations-used-in-this-manual",
      ],
      [S4A, S4A],
    ];
    for (const [ref, href] of cases)
      expect((await client.getSection(ref)).href).toBe(href);
    expect((await client.getSection("11")).section_number).toBe("11");
    expect(
      (
        await client.getSection(
          "glossary-of-terms-and-abbreviations-used-in-this-manual",
        )
      ).section_number,
    ).toBeNull();
    expect(await client.resolveSectionHref("4a")).toBe(S4A);
    expect(await client.resolveSectionHref("9999")).toBeNull();

    const error = await client.getSection("9999").catch((e) => e);
    expect(error).toBeInstanceOf(CorpusError);
    expect(error).toMatchObject({ code: "SECTION_NOT_FOUND" });
    expect(error.message).toContain("MoPP section '9999'");
    await expect(client.getSection("no-such-page")).rejects.toMatchObject({
      code: "SECTION_NOT_FOUND",
    });
    await expect(
      client.getSection("4", { version: "2024" }),
    ).rejects.toMatchObject({ code: "VERSION_UNAVAILABLE" });
    expect(await client.listVersions()).toEqual([
      {
        label: "current (snapshot 2026-05-14)",
        value: "current",
        current: true,
      },
    ]);
  } finally {
    client.close();
  }
  const small = new MoppClient({ corpusPath: fixture, maxSectionBytes: 4096 });
  try {
    await expect(small.getSection("73")).rejects.toMatchObject({
      code: "SECTION_TOO_LARGE",
    });
  } finally {
    small.close();
  }
});

test("MoPP hrefs normalize from slugs, paths and URLs", () => {
  for (const value of [
    "section-1-patentability",
    " /guidance/manual-of-patent-practice-mopp/section-1-patentability/ ",
    "https://www.gov.uk/guidance/manual-of-patent-practice-mopp/section-1-patentability?x=1#ref1-07",
    "section-1-patentability.html",
  ])
    expect(normalizeMoppHref(value)).toBe("section-1-patentability");
  expect(normalizeMoppHref(`/${S4A}`)).toBe(S4A);
});

test("MoPP artifacts are pinned, Zstandard-packaged and never WAL-mode", async () => {
  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new Uint8Array(zstdCompressSync(bytes));
  const zst = new MoppClient({
    source: packed,
    expectedSha256: hash(bytes),
    expectedFileSha256: hash(packed),
  });
  try {
    expect(await zst.getCorpusStatus()).toMatchObject({
      available: true,
      compression: "zstd",
      artifact_sha256: hash(bytes),
      file_sha256: hash(packed),
    });
    expect((await zst.getSection("4")).title).toBe(
      "Section 4: industrial application",
    );
  } finally {
    zst.close();
  }
  const wrong = new MoppClient({
    corpusPath: fixture,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).error?.code).toBe("CHECKSUM_MISMATCH");
  wrong.close();
  expect(() => new MoppClient({ expectedSha256: "nope" })).toThrow();

  const directory = await mkdtemp(join(tmpdir(), "pca-mopp-test-"));
  try {
    const wal = join(directory, "mopp.db");
    await copyFile(fixture, wal);
    const writer = new Database(wal);
    writer.exec("PRAGMA journal_mode = WAL; PRAGMA wal_checkpoint(TRUNCATE)");
    writer.close();
    const client = new MoppClient({ corpusPath: wal });
    await expect(client.search({ query: "patent" })).rejects.toMatchObject({
      code: "CORPUS_WAL_UNSUPPORTED",
    });
    client.close();
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("MOPP_CORPUS_PATH and its pins configure default consumers", async () => {
  const saved = {
    path: process.env.MOPP_CORPUS_PATH,
    sha: process.env.MOPP_CORPUS_SHA256,
  };
  try {
    process.env.MOPP_CORPUS_PATH = fixture;
    process.env.MOPP_CORPUS_SHA256 = hash(await readFile(fixture));
    expect((await getMoppCorpusStatus()).available).toBe(true);
    process.env.MOPP_CORPUS_SHA256 = "f".repeat(64);
    expect((await getMoppCorpusStatus()).error?.code).toBe("CHECKSUM_MISMATCH");
  } finally {
    for (const [key, value] of [
      ["MOPP_CORPUS_PATH", saved.path],
      ["MOPP_CORPUS_SHA256", saved.sha],
    ] as const)
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
  }
});

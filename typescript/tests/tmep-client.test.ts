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
  getTmepCorpusStatus,
  TmepClient,
} from "../packages/client/src/tmep.js";

const fixture = join(import.meta.dir, "fixtures", "tmep", "tmep.db");
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");

test("TMEP status reports the deployed snapshot's metadata without inventing a release", async () => {
  const status = await getTmepCorpusStatus({ corpusPath: fixture });
  expect(status).toMatchObject({
    available: true,
    corpus_version: "unknown",
    schema_version: 1,
    section_count: 7,
    snapshot_date: "2026-05-13",
    corpus_synced_at: "2026-05-13T00:00:00.000Z",
    compression: "none",
    source_url: "https://tmep.uspto.gov",
    metadata: { source_version: "current" },
  });
  expect(status.artifact_sha256).toBe(hash(await readFile(fixture)));
  const missing = await getTmepCorpusStatus({
    corpusPath: join(tmpdir(), "pca-no-such-tmep.db"),
  });
  expect(missing).toMatchObject({
    available: false,
    corpus_version: "unknown",
    error: { code: "CORPUS_UNAVAILABLE" },
  });
  expect(missing.error?.message).toContain("TMEP_CORPUS_PATH");
});

test("TMEP search quotes terms, pages with has_more and carries corpus provenance", async () => {
  const client = new TmepClient({ corpusPath: fixture });
  try {
    const phrase = await client.search({ query: "likelihood of confusion" });
    expect(phrase.hits.map((hit) => hit.section_number)).toEqual([
      "1207.01",
      "1207.01(a)",
      "1207",
    ]);
    expect(phrase.hits[0]).toMatchObject({
      title: "1207.01 - Likelihood of Confusion",
      href: "TMEP-1200d1e5044.html",
      path: ["Chapter 1200", "1207.01"],
      result_url:
        "https://tmep.uspto.gov/RDMS/TMEP/result?href=TMEP-1200d1e5044.html",
      snippet: expect.stringContaining("<mark>Likelihood of Confusion</mark>"),
    });
    expect(CorpusProvenanceSchema.safeParse(phrase.provenance).success).toBe(
      true,
    );
    expect(phrase.provenance).toMatchObject({
      source_url: "https://tmep.uspto.gov/RDMS/TMEP/search",
      source_name: "USPTO TMEP (Trademark Manual of Examining Procedure)",
      cache_hit: true,
      retrieved_at: "2026-05-13T00:00:00.000Z",
      corpus_synced_at: "2026-05-13T00:00:00.000Z",
      corpus_version: "unknown",
    });

    // Outline order is the stored section_number text order, as in Python.
    const outline = await client.search({
      query: "mark",
      syntax: "and",
      sort: "outline",
      limit: 6,
    });
    expect(outline.hits.map((hit) => hit.section_number)).toEqual([
      "1207",
      "1207.01",
      "1207.01(a)",
      "1209.03(u)",
      "1301.04(i)",
      "1401.02(a)",
    ]);
    expect(outline.has_more).toBe(true);
    const last = await client.search({
      query: "mark",
      syntax: "and",
      sort: "outline",
      limit: 6,
      offset: 6,
    });
    expect(last.hits.map((hit) => hit.section_number)).toEqual(["904"]);
    expect(last.has_more).toBe(false);

    expect(
      (await client.search({ query: "specimens punctuation", syntax: "or" }))
        .hits,
    ).toHaveLength(3);
    for (const query of ["NEAR(mark)", '" OR 1=1 --', " "])
      expect((await client.search({ query, syntax: "and" })).hits).toEqual([]);
    // An FTS operator word is searched as text, as Python quotes it too.
    expect(
      (await client.search({ query: "NOT", syntax: "and" })).hits.length,
    ).toBeGreaterThan(0);
    await expect(
      client.search({ query: "mark", limit: 101 }),
    ).rejects.toThrow();
    await expect(client.search({ query: "mark\0" })).rejects.toThrow("NUL");
    await expect(
      client.search({ query: "mark", version: "2025" }),
    ).rejects.toMatchObject({ code: "VERSION_UNAVAILABLE" });
  } finally {
    client.close();
  }
});

test("TMEP sections resolve by number or href and decode dictionary-compressed HTML", async () => {
  const client = new TmepClient({ corpusPath: fixture });
  try {
    const byNumber = await client.getSection("1207.01");
    expect(byNumber).toMatchObject({
      href: "TMEP-1200d1e5044.html",
      section_number: "1207.01",
      title: "Likelihood of Confusion",
      chapter: "1200",
      version: "current",
      source_url:
        "https://tmep.uspto.gov/RDMS/TMEP/result?href=TMEP-1200d1e5044.html",
      content_sha256:
        "1c95abbac653a701f39d2412986ebaddcb5713321514cc8705213a345ce1a7ae",
    });
    expect(byNumber.content_sha256).toBe(hash(byNumber.html));
    expect(byNumber.text).toHaveLength(12227);
    expect(byNumber.provenance.source_url).toBe(byNumber.source_url);

    // The Python docstring's href, with and without .html, and an odd stored href.
    for (const ref of ["TMEP-1200d1e8145.html", "/TMEP-1200d1e8145"])
      expect((await client.getSection(ref)).section_number).toBe("1209.03(u)");
    expect(
      (await client.getSection("ch1300_d2266f_1dcc2_11c")).section_number,
    ).toBe("1301.04(i)");
    expect(await client.resolveSectionHref("1207.01(a)")).toBe(
      "TMEP-1200d1e5130.html",
    );
    expect(await client.resolveSectionHref("9999")).toBeNull();

    const error = await client.getSection("9999.99").catch((e) => e);
    expect(error).toBeInstanceOf(CorpusError);
    expect(error).toMatchObject({ code: "SECTION_NOT_FOUND" });
    expect(error.message).toContain("TMEP section '9999.99'");
    await expect(client.getSection("TMEP-missing.html")).rejects.toMatchObject({
      code: "SECTION_NOT_FOUND",
    });
    await expect(
      client.getSection("1207", { version: "2024" }),
    ).rejects.toMatchObject({ code: "VERSION_UNAVAILABLE" });
    expect(await client.listVersions()).toEqual([
      {
        label: "current (snapshot 2026-05-13)",
        value: "current",
        current: true,
      },
    ]);
  } finally {
    client.close();
  }
  const small = new TmepClient({ corpusPath: fixture, maxSectionBytes: 4096 });
  try {
    await expect(small.getSection("1401.02(a)")).rejects.toMatchObject({
      code: "SECTION_TOO_LARGE",
    });
  } finally {
    small.close();
  }
});

test("TMEP artifacts are pinned, Zstandard-packaged and never WAL-mode", async () => {
  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new Uint8Array(zstdCompressSync(bytes));
  const zst = new TmepClient({
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
    expect((await zst.getSection("904")).title).toBe("Specimens");
  } finally {
    zst.close();
  }
  const wrong = new TmepClient({
    corpusPath: fixture,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).error?.code).toBe("CHECKSUM_MISMATCH");
  wrong.close();
  expect(() => new TmepClient({ expectedSha256: "nope" })).toThrow();

  const directory = await mkdtemp(join(tmpdir(), "pca-tmep-test-"));
  try {
    const wal = join(directory, "tmep.db");
    await copyFile(fixture, wal);
    const writer = new Database(wal);
    writer.exec("PRAGMA journal_mode = WAL; PRAGMA wal_checkpoint(TRUNCATE)");
    writer.close();
    const client = new TmepClient({ corpusPath: wal });
    await expect(client.search({ query: "mark" })).rejects.toMatchObject({
      code: "CORPUS_WAL_UNSUPPORTED",
    });
    client.close();
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("TMEP_CORPUS_PATH and its pins configure default consumers", async () => {
  const saved = {
    path: process.env.TMEP_CORPUS_PATH,
    sha: process.env.TMEP_CORPUS_SHA256,
  };
  try {
    process.env.TMEP_CORPUS_PATH = fixture;
    process.env.TMEP_CORPUS_SHA256 = hash(await readFile(fixture));
    expect((await getTmepCorpusStatus()).available).toBe(true);
    process.env.TMEP_CORPUS_SHA256 = "f".repeat(64);
    expect((await getTmepCorpusStatus()).error?.code).toBe("CHECKSUM_MISMATCH");
  } finally {
    for (const [key, value] of [
      ["TMEP_CORPUS_PATH", saved.path],
      ["TMEP_CORPUS_SHA256", saved.sha],
    ] as const)
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
  }
});

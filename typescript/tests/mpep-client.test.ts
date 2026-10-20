import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import {
  copyFile,
  mkdtemp,
  readdir,
  readFile,
  rename,
  rm,
  rmdir,
  truncate,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { CorpusProvenanceSchema } from "../packages/client/src/models.js";
import {
  CorpusError,
  getMpepCorpusStatus,
  MpepClient,
} from "../packages/client/src/mpep.js";

const fixtures = join(import.meta.dir, "fixtures", "mpep");
const plain = join(fixtures, "plain.db");
const compressed = join(fixtures, "compressed.db");
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");

async function copied(
  run: (filename: string, directory: string) => Promise<void>,
) {
  const directory = await mkdtemp(join(tmpdir(), "pca-mpep-test-"));
  const filename = join(directory, "corpus.db");
  await copyFile(plain, filename);
  try {
    await run(filename, directory);
  } finally {
    for (const name of await readdir(directory))
      await rm(join(directory, name));
    await rmdir(directory);
  }
}

function mutate(filename: string, sql: string) {
  const db = new Database(filename);
  try {
    db.exec(sql);
  } finally {
    db.close();
  }
}

test("MPEP read-only FTS search preserves safe phrase/term semantics and pagination", async () => {
  await copied(async (filename, directory) => {
    const before = hash(await readFile(filename));
    const client = new MpepClient({ corpusPath: filename });
    try {
      const first = await client.search({
        query: "patent",
        sort: "outline",
        limit: 1,
      });
      expect(first.hits[0]?.section_number).toBe("2106");
      expect(first.hits[0]?.path).toEqual(["Chapter 2100", "2106"]);
      expect(first.has_more).toBe(true);
      const second = await client.search({
        query: "patent",
        sort: "outline",
        limit: 1,
        offset: 1,
      });
      expect(second.hits[0]?.section_number).toBe("2106.04(a)");
      expect(
        (
          await client.search({
            query: "patent",
            sort: "outline",
            limit: 1,
            offset: 2,
          })
        ).has_more,
      ).toBe(false);
      expect(
        (await client.search({ query: "patent eligibility", syntax: "exact" }))
          .hits,
      ).toHaveLength(2);
      expect(
        (
          await client.search({
            query: "eligibility interpretation",
            syntax: "or",
          })
        ).hits,
      ).toHaveLength(3);
      expect(
        (await client.search({ query: "café", syntax: "and" })).hits[0]
          ?.section_number,
      ).toBe("2106.04(a)");
      expect(
        (await client.search({ query: "AND", syntax: "and" })).hits,
      ).toHaveLength(1);
      for (const query of ["NEAR(thing)", '" OR 1=1 --', " "])
        expect((await client.search({ query, syntax: "and" })).hits).toEqual(
          [],
        );
      await expect(
        client.search({ query: "patent", limit: 101 }),
      ).rejects.toThrow();
      await expect(
        client.search({ query: "patent", offset: -1 }),
      ).rejects.toThrow();
      await expect(client.search({ query: "patent\0" })).rejects.toThrow("NUL");
      expect(CorpusProvenanceSchema.safeParse(first.provenance).success).toBe(
        true,
      );
      expect(first.provenance).toMatchObject({
        cache_hit: true,
        retrieved_at: "2026-10-20T12:00:00.000Z",
        corpus_synced_at: "2026-10-20T12:00:00.000Z",
        corpus_version: "E9_R-01.2024",
      });
      expect(first.provenance.accessed_at).toBeString();
      expect(hash(await readFile(filename))).toBe(before);
      expect(await readdir(directory)).toEqual(["corpus.db"]);
    } finally {
      client.close();
    }
  });
});

test("MPEP section numbers/hrefs, hashes and retained release metadata are authoritative", async () => {
  const client = new MpepClient({ corpusPath: plain });
  try {
    const section = await client.getSection("2106", {
      version: "E9_R-01.2024",
    });
    expect(section.title).toBe("Patent Subject Matter Eligibility");
    expect(section.section_revision).toBe("[R-01.2024]");
    expect(section.content_sha256).toBe(hash(section.html));
    expect(section.corpus_metadata.future_metadata).toBe("preserved");
    expect(new URL(section.source_url).searchParams.get("version")).toBe(
      "E9_R-01.2024",
    );
    expect(await client.resolveSectionHref("2106.04(a)")).toBe(
      "ch2100_sub.html",
    );
    expect(await client.resolveSectionHref("9999")).toBeNull();
    for (const href of ["d0e2106", "/current/d0e2106.html", "d0e2106.html"])
      expect((await client.getSection(href)).content_sha256).toBe(
        section.content_sha256,
      );
    await expect(client.getSection("9999")).rejects.toMatchObject({
      code: "SECTION_NOT_FOUND",
    });
    await expect(
      client.getSection("2106", { version: "E8_R-07.2010" }),
    ).rejects.toMatchObject({ code: "VERSION_UNAVAILABLE" });
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      section_count: 3,
      edition: "Ninth Edition",
      revision: "01.2024",
      publication_date: "2024-11",
      substantive_cutoff_date: "2024-01-31",
      interim_updates_coverage: "not_included",
      build_id: "synthetic-test-build",
      release_check: { comparison: "matches_latest_checked" },
    });
    expect((await client.listVersions())[0]).toMatchObject({
      value: "E9_R-01.2024",
      current: true,
    });
  } finally {
    client.close();
  }
});

test("dictionary-compressed legacy HTML decodes exactly and mixed plaintext rows still work", async () => {
  const client = new MpepClient({ corpusPath: compressed });
  try {
    const section = await client.getSection("2106");
    expect(section.html.length).toBe(30184);
    expect(section.text.length).toBe(16989);
    expect(section.content_sha256).toBe(
      "cd6d838cc1040617ffe3028a4741c2cec7000f9148c5e0977cf2e44a613d579c",
    );
    expect(section.version).toBe("unknown");
    expect(section.provenance.corpus_synced_at).toBe(
      "2026-05-21T00:00:00.000Z",
    );
    expect((await client.getSection("2106.99")).html).toBe(
      "<p>Uncompressed patent row.</p>",
    );
    expect(await client.getCorpusStatus()).toMatchObject({
      schema_version: 2,
      source_version: "unknown",
      edition: null,
      revision: null,
      interim_updates_coverage: "unknown",
      release_check: { comparison: "unknown" },
    });
    await expect(
      client.getSection("2106", { version: "E9_R-01.2024" }),
    ).rejects.toMatchObject({ code: "VERSION_UNAVAILABLE" });
    const version = (await client.listVersions())[0]?.value;
    expect(version).toBe("current");
    expect(
      (await client.search({ query: "patent", version })).hits.length,
    ).toBeGreaterThan(0);
  } finally {
    client.close();
  }
});

test("missing source times stay null and a dated release comparison does not assert current law", async () => {
  await copied(async (filename) => {
    mutate(
      filename,
      "DELETE FROM meta WHERE key IN ('synced_at','snapshot_date'); UPDATE meta SET value='E9_R-07.2022' WHERE key='source_version'",
    );
    const client = new MpepClient({ corpusPath: filename });
    try {
      const response = await client.search({ query: "patent" });
      expect(response.provenance.retrieved_at).toBeNull();
      expect(response.provenance.corpus_synced_at).toBeNull();
      expect(response.corpus.release_check.comparison).toBe(
        "different_release",
      );
      expect(response.corpus.release_check.checked_at).toBeString();
      expect(response.corpus.interim_updates_coverage).toBe("not_included");
    } finally {
      client.close();
    }
  });
});

test("artifact pinning and schema validation fail clearly without creating a missing file", async () => {
  await copied(async (filename, directory) => {
    const good = new MpepClient({
      corpusPath: filename,
      expectedSha256: hash(await readFile(filename)),
    });
    expect((await good.getCorpusStatus()).available).toBe(true);
    good.close();
    const bad = new MpepClient({
      corpusPath: filename,
      expectedSha256: "0".repeat(64),
    });
    expect((await bad.getCorpusStatus()).error?.code).toBe("CHECKSUM_MISMATCH");
    bad.close();
    const missingPath = join(directory, "absent.db");
    const status = await getMpepCorpusStatus({ corpusPath: missingPath });
    expect(status.available).toBe(false);
    expect(status.error?.code).toBe("CORPUS_UNAVAILABLE");
    expect(await readdir(directory)).toEqual(["corpus.db"]);
    mutate(filename, "UPDATE meta SET value='99' WHERE key='schema_version'");
    expect(
      (await getMpepCorpusStatus({ corpusPath: filename })).error?.code,
    ).toBe("UNSUPPORTED_SCHEMA");
    for (const schema of [
      "CREATE VIRTUAL TABLE sections_fts USING fts5(text)",
      "CREATE VIRTUAL TABLE sections_fts USING fts5(section_number,title,text,content='other',content_rowid='rowid')",
    ]) {
      await copyFile(plain, filename);
      mutate(filename, `DROP TABLE sections_fts; ${schema}`);
      expect(
        (await getMpepCorpusStatus({ corpusPath: filename })).error?.code,
      ).toBe("INVALID_CORPUS");
    }
    await writeFile(filename, "not SQLite");
    expect(
      (await getMpepCorpusStatus({ corpusPath: filename })).error?.code,
    ).toBe("INVALID_CORPUS");
  });
});

test("section size bounds, corrupt dictionaries and caller cancellation remain explicit", async () => {
  for (const corpusPath of [plain, compressed]) {
    const client = new MpepClient({ corpusPath, maxSectionBytes: 16 });
    try {
      await expect(client.getSection("2106")).rejects.toMatchObject({
        code: "SECTION_TOO_LARGE",
      });
    } finally {
      client.close();
    }
  }
  const client = new MpepClient({ corpusPath: plain });
  const signal = AbortSignal.abort();
  await expect(
    client.search({ query: "patent", signal }),
  ).rejects.toMatchObject({ code: "ABORTED" });
  await expect(client.getSection("2106", { signal })).rejects.toBeInstanceOf(
    CorpusError,
  );
  await expect(
    client.resolveSectionHref("2106", { signal }),
  ).rejects.toMatchObject({ code: "ABORTED" });
  client.close();
  await copied(async (filename) => {
    await copyFile(compressed, filename);
    mutate(filename, "UPDATE compression_dict SET dict_bytes=x'00000000'");
    const corrupt = new MpepClient({ corpusPath: filename });
    try {
      await expect(corrupt.getSection("2106")).rejects.toMatchObject({
        code: "DECOMPRESSION_FAILED",
      });
    } finally {
      corrupt.close();
    }
  });
});

test("checksum pins cannot be bypassed by WAL replay or replacing the opened path", async () => {
  await copied(async (filename) => {
    const writer = new Database(filename);
    try {
      writer.exec("PRAGMA journal_mode = WAL; PRAGMA wal_checkpoint(TRUNCATE)");
      const pinned = hash(await readFile(filename));
      writer.exec(
        "UPDATE meta SET value='E9_R-UNPINNED' WHERE key='source_version'",
      );
      expect(hash(await readFile(filename))).toBe(pinned);
      const client = new MpepClient({
        corpusPath: filename,
        expectedSha256: pinned,
      });
      try {
        expect((await client.getCorpusStatus()).error?.code).toBe(
          "CORPUS_WAL_UNSUPPORTED",
        );
        await expect(client.getSection("2106")).rejects.toMatchObject({
          code: "CORPUS_WAL_UNSUPPORTED",
        });
      } finally {
        client.close();
      }
    } finally {
      writer.close();
    }
  });
  await copied(async (filename, directory) => {
    const pinned = hash(await readFile(filename));
    const client = new MpepClient({
      corpusPath: filename,
      expectedSha256: pinned,
    });
    try {
      expect((await client.getCorpusStatus()).source_version).toBe(
        "E9_R-01.2024",
      );
      const replacement = join(directory, "replacement.db");
      await copyFile(plain, replacement);
      mutate(
        replacement,
        "UPDATE meta SET value='E9_R-UNPINNED' WHERE key='source_version'",
      );
      await rename(replacement, filename);
      expect((await client.getSection("2106")).version).toBe("E9_R-01.2024");
      expect((await client.getCorpusStatus()).artifact_sha256).toBe(pinned);
      client.close();
      expect((await client.getCorpusStatus()).error?.code).toBe(
        "CHECKSUM_MISMATCH",
      );
    } finally {
      client.close();
    }
  });
});

test("artifact buffering refuses oversized files before reading them", async () => {
  await copied(async (filename) => {
    await truncate(filename, 257 * 1024 * 1024);
    expect(
      (await getMpepCorpusStatus({ corpusPath: filename })).error?.code,
    ).toBe("CORPUS_TOO_LARGE");
  });
});

test("MPEP_CORPUS_SHA256 pins default consumers and rejects empty configuration", async () => {
  const previous = process.env.MPEP_CORPUS_SHA256;
  try {
    process.env.MPEP_CORPUS_SHA256 = "";
    expect(() => new MpepClient({ corpusPath: plain })).toThrow();
    process.env.MPEP_CORPUS_SHA256 = hash(await readFile(plain));
    const client = new MpepClient({ corpusPath: plain });
    try {
      expect((await client.getCorpusStatus()).available).toBe(true);
    } finally {
      client.close();
    }
    process.env.MPEP_CORPUS_SHA256 = "0".repeat(64);
    const explicit = new MpepClient({
      corpusPath: plain,
      expectedSha256: hash(await readFile(plain)),
    });
    try {
      expect((await explicit.getCorpusStatus()).available).toBe(true);
    } finally {
      explicit.close();
    }
  } finally {
    if (previous === undefined) delete process.env.MPEP_CORPUS_SHA256;
    else process.env.MPEP_CORPUS_SHA256 = previous;
  }
});

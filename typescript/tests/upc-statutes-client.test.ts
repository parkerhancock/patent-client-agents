import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { copyFile, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusProvenanceSchema } from "../packages/client/src/models.js";
import {
  resolveUpcInstrument,
  UPC_LEGAL_DOCUMENTS_URL,
  UpcStatutesClient,
} from "../packages/client/src/upc-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "upc-statutes",
  "upc_statutes.db",
);
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");
const UPCA_EN_SHA256 =
  "98e59e5145eeeade781586178311ab249dae77a5b8fe2ab5ec8230fe37fe21be";
const FEES_FR_SHA256 =
  "69f50ff3b025346f1ee90c632f96d47a49688b725fd87f4502fb8946cc92e214";

async function withCopy(sql: string, run: (filename: string) => Promise<void>) {
  const directory = await mkdtemp(join(tmpdir(), "pca-upc-statutes-test-"));
  const filename = join(directory, "upc_statutes.db");
  await copyFile(fixture, filename);
  const db = new Database(filename);
  try {
    db.exec(sql);
  } finally {
    db.close();
  }
  try {
    await run(filename);
  } finally {
    await rm(directory, { recursive: true });
  }
}

test("UPC statutes status, search and instruments come from real corpus rows", async () => {
  const before = hash(await readFile(fixture));
  const client = new UpcStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      corpus_version: "snapshot 2026-05-14",
      schema_version: 1,
      instrument_count: 4,
      snapshot_date: "2026-05-14",
      corpus_synced_at: "2026-05-14T00:00:00.000Z",
      compression: "none",
      source_url: UPC_LEGAL_DOCUMENTS_URL,
      // The build's own count, kept as recorded: the fixture holds 4 of 9 rows.
      metadata: { instrument_count: "9" },
    });
    expect(status.artifact_sha256).toBe(before);

    const optOut = await client.search({ query: "opt-out" });
    expect(optOut.hits).toEqual([
      {
        instrument: "upca",
        short_name: "UPCA",
        language: "en",
        snippet: expect.stringContaining("<mark>opt-out</mark>"),
        rank: expect.any(Number),
      },
    ]);
    expect(optOut.has_more).toBe(false);
    expect(optOut.provenance).toMatchObject({
      source_url: UPC_LEGAL_DOCUMENTS_URL,
      source_name: "Unified Patent Court",
      corpus_version: "snapshot 2026-05-14",
      corpus_synced_at: "2026-05-14T00:00:00.000Z",
      retrieved_at: "2026-05-14T00:00:00.000Z",
    });
    expect(CorpusProvenanceSchema.parse(optOut.provenance).cache_hit).toBe(
      true,
    );
    expect(
      (await client.search({ query: "Article 33", syntax: "adj" })).hits[0]
        ?.snippet,
    ).toContain("<mark>Article 33</mark>");

    // English is the default language; null searches all of them.
    expect((await client.search({ query: "Streitwert" })).hits).toEqual([]);
    expect(
      (await client.search({ query: "Streitwert", language: "de" })).hits[0],
    ).toMatchObject({ instrument: "fees", language: "de" });
    const all = await client.search({ query: "fee", language: null });
    expect(
      all.hits.map((hit) => `${hit.instrument}/${hit.language}`).sort(),
    ).toEqual(["fees/de", "fees/en", "fees/fr", "upca/en"]);

    // Instrument aliases resolve before filtering.
    for (const alias of ["court fees", "FEES", "table of court fees"])
      expect(
        (await client.search({ query: "value", instrument: alias })).hits.map(
          (hit) => hit.instrument,
        ),
      ).toEqual(["fees"]);
    expect(
      (await client.search({ query: "value", instrument: "statute" })).hits.map(
        (hit) => hit.instrument,
      ),
    ).toEqual(["upca"]);
    expect(
      (await client.search({ query: "value", instrument: "coc" })).hits,
    ).toEqual([]);

    const first = await client.search({
      query: "fee",
      language: null,
      sort: "instrument",
      limit: 3,
    });
    expect(
      first.hits.map((hit) => `${hit.instrument}/${hit.language}`),
    ).toEqual(["fees/de", "fees/en", "fees/fr"]);
    expect(first.has_more).toBe(true);
    const rest = await client.search({
      query: "fee",
      language: null,
      sort: "instrument",
      limit: 3,
      offset: 3,
    });
    expect(rest.hits.map((hit) => hit.instrument)).toEqual(["upca"]);
    expect(rest.has_more).toBe(false);

    const listed = await client.listInstruments();
    expect(
      listed.instruments.map((item) => `${item.instrument}/${item.language}`),
    ).toEqual(["fees/de", "fees/en", "fees/fr", "upca/en"]);
    expect(listed.instruments[1]).toEqual({
      instrument: "fees",
      short_name: "Fees",
      title: "Consolidated Table of Court Fees and Recoverable Costs",
      language: "en",
      // The stored PDF name has spaces; the reported URL is percent-encoded.
      source_url:
        "https://www.unifiedpatentcourt.org/sites/default/files/upc_documents/Consolidated%20Table%20of%20Court%20fees_EN.pdf",
      source_version: null,
      pdf_pages: 8,
    });
    expect(
      (await client.listInstruments({ language: "FR" })).instruments.map(
        (item) => item.title,
      ),
    ).toEqual([
      "Tableau consolidé des frais de procédure et des dépens recouvrables",
    ]);
  } finally {
    client.close();
  }
  expect(hash(await readFile(fixture))).toBe(before);
});

test("UPC instruments return full text by key or alias and null when not installed", async () => {
  const client = new UpcStatutesClient({ corpusPath: fixture });
  try {
    const upca = await client.getInstrument("Statute");
    expect(upca).toMatchObject({
      instrument: "upca",
      short_name: "UPCA",
      language: "en",
      title:
        "Agreement on a Unified Patent Court (including Annex I, Statute of the UPC)",
      source_url:
        "https://www.unifiedpatentcourt.org/sites/default/files/upc_documents/agreement-on-a-unified-patent-court.pdf",
      pdf_pages: 44,
      corpus_version: "snapshot 2026-05-14",
      content_sha256: UPCA_EN_SHA256,
    });
    expect(upca?.text).toHaveLength(125_255);
    expect(hash(upca?.text ?? "")).toBe(UPCA_EN_SHA256);
    expect(upca?.provenance.source_url).toBe(upca?.source_url);
    const fees = await client.getInstrument("fees", { language: "fr" });
    expect(fees?.content_sha256).toBe(FEES_FR_SHA256);
    expect(fees?.title).toStartWith("Tableau consolidé");
    // The fixture has no Rules of Procedure; the full corpus has no Code of Conduct.
    expect(await client.getInstrument("rules of procedure")).toBeNull();
    expect(await client.getInstrument("coc")).toBeNull();
    expect(await client.getInstrument("upca", { language: "de" })).toBeNull();
    await expect(
      client.getInstrument("upca", { language: "english" }),
    ).rejects.toThrow();
    const small = new UpcStatutesClient({
      corpusPath: fixture,
      maxTextBytes: 10_000,
    });
    try {
      expect((await small.getInstrument("fees"))?.text.length).toBe(6178);
      await expect(small.getInstrument("upca")).rejects.toMatchObject({
        code: "SECTION_TOO_LARGE",
      });
    } finally {
      small.close();
    }
  } finally {
    client.close();
  }
});

test("UPC search quotes caller syntax instead of executing FTS operators", async () => {
  const client = new UpcStatutesClient({ corpusPath: fixture });
  try {
    // Python passes bare words through, so OR/NOT/NEAR run as operators or fail.
    expect((await client.search({ query: "opt-out OR zzz" })).hits).toEqual([]);
    // A lone NOT is an FTS syntax error in Python; here it is the word "not".
    expect(
      (await client.search({ query: "NOT" })).hits.map((hit) => hit.snippet),
    ).toContainEqual(expect.stringContaining("<mark>not</mark>"));
    expect((await client.search({ query: 'value" OR "x' })).hits).toEqual([]);
    expect(
      (await client.search({ query: "opt-out zzzunknown", syntax: "or" }))
        .hits[0]?.instrument,
    ).toBe("upca");
    expect((await client.search({ query: "   " })).hits).toEqual([]);
    const controller = new AbortController();
    controller.abort();
    await expect(
      client.search({ query: "value", signal: controller.signal }),
    ).rejects.toMatchObject({ code: "ABORTED" });
  } finally {
    client.close();
  }
  expect(resolveUpcInstrument(" Rules of Procedure ")).toBe("rop");
  expect(resolveUpcInstrument("Annex I")).toBe("upca");
  expect(resolveUpcInstrument("other")).toBe("other");
});

test("UPC corpora read Zstandard bytes and report unavailable, WAL, schema and pin failures", async () => {
  const decoded = await readFile(fixture);
  const encoded = new Uint8Array(zstdCompressSync(decoded));
  const packed = new UpcStatutesClient({
    source: encoded,
    expectedSha256: hash(decoded),
    expectedFileSha256: hash(encoded),
  });
  try {
    expect(await packed.getCorpusStatus()).toMatchObject({
      available: true,
      compression: "zstd",
      artifact_sha256: hash(decoded),
      file_sha256: hash(encoded),
    });
    expect((await packed.search({ query: "opt-out" })).hits).toHaveLength(1);
  } finally {
    packed.close();
  }
  const wrongFile = new UpcStatutesClient({
    source: encoded,
    expectedFileSha256: "0".repeat(64),
  });
  expect((await wrongFile.getCorpusStatus()).error?.code).toBe(
    "CHECKSUM_MISMATCH",
  );
  const pinned = new UpcStatutesClient({
    corpusPath: fixture,
    expectedSha256: "0".repeat(64),
  });
  expect((await pinned.getCorpusStatus()).error?.code).toBe(
    "CHECKSUM_MISMATCH",
  );
  expect(
    () => new UpcStatutesClient({ corpusPath: fixture, expectedSha256: "x" }),
  ).toThrow();

  const directory = await mkdtemp(join(tmpdir(), "pca-upc-missing-"));
  const missing = join(directory, "absent.db");
  try {
    const client = new UpcStatutesClient({ corpusPath: missing });
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: false,
      corpus_version: "unknown",
      corpus_synced_at: null,
    });
    expect(status.error?.code).toBe("CORPUS_UNAVAILABLE");
    expect(status.error?.message).toContain("UPC statutes corpus");
    expect(status.error?.message).toContain("UPC_STATUTES_CORPUS_PATH");
    await expect(client.search({ query: "value" })).rejects.toMatchObject({
      code: "CORPUS_UNAVAILABLE",
    });
    client.close();
    expect(await Bun.file(missing).exists()).toBe(false);
  } finally {
    await rm(directory, { recursive: true });
  }

  for (const [sql, code] of [
    ["PRAGMA journal_mode=WAL", "CORPUS_WAL_UNSUPPORTED"],
    [
      "UPDATE meta SET value = '2' WHERE key = 'schema_version'",
      "UNSUPPORTED_SCHEMA",
    ],
    ["DROP TABLE instruments_fts", "INVALID_CORPUS"],
  ] as const)
    await withCopy(sql, async (filename) => {
      const client = new UpcStatutesClient({ corpusPath: filename });
      try {
        expect([sql, (await client.getCorpusStatus()).error?.code]).toEqual([
          sql,
          code,
        ]);
      } finally {
        client.close();
      }
    });
});

test("UPC metadata gaps stay unknown and untrusted stored URLs fall back to the documents page", async () => {
  await withCopy(
    "UPDATE meta SET value = 'May 2026' WHERE key = 'snapshot_date'; UPDATE instruments SET source_url = 'https://evil.example/x.pdf' WHERE instrument = 'upca'",
    async (filename) => {
      const client = new UpcStatutesClient({ corpusPath: filename });
      try {
        expect(await client.getCorpusStatus()).toMatchObject({
          available: true,
          corpus_version: "unknown",
          snapshot_date: "May 2026",
          corpus_synced_at: null,
        });
        const upca = await client.getInstrument("upca");
        expect(upca?.source_url).toBe(UPC_LEGAL_DOCUMENTS_URL);
        expect(upca?.provenance).toMatchObject({
          retrieved_at: null,
          corpus_synced_at: null,
          corpus_version: "unknown",
        });
      } finally {
        client.close();
      }
    },
  );
});

test("UPC clients read the Python path and pin variables", async () => {
  const saved = {
    path: process.env.UPC_STATUTES_CORPUS_PATH,
    pin: process.env.UPC_STATUTES_CORPUS_SHA256,
  };
  const digest = hash(await readFile(fixture));
  process.env.UPC_STATUTES_CORPUS_PATH = fixture;
  process.env.UPC_STATUTES_CORPUS_SHA256 = digest;
  const client = new UpcStatutesClient();
  try {
    expect(await client.getCorpusStatus()).toMatchObject({
      available: true,
      artifact_sha256: digest,
    });
  } finally {
    client.close();
    for (const [key, value] of [
      ["UPC_STATUTES_CORPUS_PATH", saved.path],
      ["UPC_STATUTES_CORPUS_SHA256", saved.pin],
    ] as const)
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
  }
});

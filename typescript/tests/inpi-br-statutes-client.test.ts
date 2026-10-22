import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { copyFile, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  INPI_BR_STATUTES_SOURCE_URL,
  InpiBrStatutesClient,
  inpiBrResultUrl,
  inpiBrSlug,
  isInpiBrCitation,
} from "../packages/client/src/inpi-br-statutes.js";
import { CorpusProvenanceSchema } from "../packages/client/src/models.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "inpi-br-statutes",
  "inpi_br_statutes.db",
);
const hash = (value: Uint8Array | string) =>
  createHash("sha256").update(value).digest("hex");
const code = async (promise: Promise<unknown>) => {
  try {
    await promise;
  } catch (error) {
    return error instanceof CorpusError ? error.code : String(error);
  }
  return "resolved";
};
async function withCopy(sql: string, run: (filename: string) => Promise<void>) {
  const directory = await mkdtemp(join(tmpdir(), "pca-inpi-br-test-"));
  const filename = join(directory, "inpi_br_statutes.db");
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

test("citations resolve to slugs as Python's decoder does, plus ordinals and lettered Articles", () => {
  for (const [citation, slug] of [
    ["Art. 6", "art6"],
    ["Art 6", "art6"],
    ["Article 6", "art6"],
    ["Artigo 6", "art6"],
    ["art6", "art6"],
    ["ART6", "art6"],
    ["Art. 195", "art195"],
    ["Art 195 LPI", "art195"],
    ["Art. 195 da LPI", "art195"],
    ["Art. 195(XI)", "art195"],
    ["Art. 195(XI) LPI", "art195"],
    // Python rejects these.
    ["Art. 6º", "art6"],
    ["Art. 229-C", "art229-c"],
    ["art229-c", "art229-c"],
    ["art229c", "art229-c"],
    ["https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#art10", "art10"],
    [
      "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#Art229-C",
      "art229-c",
    ],
  ])
    expect(inpiBrSlug(citation as string)).toBe(slug as string);
  expect(inpiBrSlug("not a citation")).toBeNull();
  expect(inpiBrSlug("99 problems")).toBeNull();
  expect(
    inpiBrSlug("https://www.planalto.gov.br/ccivil_03/leis/l9279.htm"),
  ).toBeNull();
  expect(isInpiBrCitation("Art. 195(XI) LPI")).toBe(true);
  expect(isInpiBrCitation("§ 1º")).toBe(false);
  expect(inpiBrResultUrl("art6")).toBe(
    "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#Art6",
  );
  expect(inpiBrResultUrl("art229-c")).toBe(
    "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#Art229-C",
  );
});

test("status, sections and versions come from the Câmara and WIPO Lex build", async () => {
  const client = new InpiBrStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      corpus_version: "consolidated through Lei nº 14.852, de 3/5/2024",
      schema_version: 1,
      section_count: 9,
      snapshot_date: "2026-10-22",
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
      latest_amendment: "Lei nº 14.852, de 3/5/2024 (2024-05-03)",
      english_version:
        "Law No. 9.279 of May 14, 1996, as enacted (WIPO Lex record 515)",
      compression: "none",
      source_url: INPI_BR_STATUTES_SOURCE_URL,
    });
    expect(status.metadata.lpi_year).toBe("1996");
    expect(await client.listVersions()).toEqual([
      {
        label:
          "LPI (Lei 9.279/1996) consolidated through Lei nº 14.852, de 3/5/2024 (snapshot 2026-10-22)",
        value: "current",
        current: true,
      },
    ]);

    for (const citation of [
      "Art. 6",
      "Art 6",
      "Article 6",
      "art6",
      "Artigo 6",
    ]) {
      const section = await client.getSection(citation);
      expect(section.href).toBe("art6");
      expect(section.article_number).toBe("Art. 6");
    }
    const art6 = await client.getSection("Art. 6º");
    expect(art6).toMatchObject({
      href: "art6",
      title_pt:
        "Ao autor de invenção ou modelo de utilidade será assegurado o direito de obter a patente que lhe garanta a propriedade,…",
      title_en: expect.stringContaining("It shall be assured to the author"),
      title_section: "TÍTULO I — DAS PATENTES",
      version: "current",
      result_url: "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#Art6",
    });
    expect(art6.text_pt.split("\n")).toEqual([
      "Art. 6º Ao autor de invenção ou modelo de utilidade será assegurado o direito de obter a patente que lhe garanta a propriedade, nas condições estabelecidas nesta Lei.",
      "§ 1º Salvo prova em contrário, presume-se o requerente legitimado a obter a patente.",
      expect.stringMatching(/^§ 2º A patente poderá ser requerida/),
      expect.stringMatching(/^§ 3º Quando se tratar de invenção/),
      "§ 4º O inventor será nomeado e qualificado, podendo requerer a não divulgação de sua nomeação.",
    ]);
    expect(art6.text_en?.split("\n")[0]).toBe(
      "Article 6. It shall be assured to the author of an invention or a utility model the right to obtain a patent that guarantees his property, under the conditions established in this Law.",
    );
    expect(art6.html_pt).toStartWith("<p>Art. 6º Ao autor");
    expect(art6.html_en).toStartWith("<p>Article 6. It shall be");
    expect(CorpusProvenanceSchema.parse(art6.provenance)).toMatchObject({
      source_url: INPI_BR_STATUTES_SOURCE_URL,
      corpus_version: "consolidated through Lei nº 14.852, de 3/5/2024",
      cache_hit: true,
    });

    const art195 = await client.getSection("Art. 195(XI) LPI");
    expect(art195.title_section).toBe(
      "TÍTULO V — DOS CRIMES CONTRA A PROPRIEDADE INDUSTRIAL",
    );
    expect(art195.text_pt).toContain(
      "XI - divulga, explora ou utiliza-se, sem autorização, de conhecimentos, informações ou dados confidenciais",
    );
    expect(art195.text_en).toContain(
      "XI. divulges, exploits, or utilizes, without authorization, confidential knowledge",
    );
    // The English is the 1996 text: Art. 40's struck-down sole paragraph remains.
    const art40 = await client.getSection("Art. 40");
    expect(art40.text_pt).toContain("declarado inconstitucional");
    expect(art40.text_en).toContain(
      "The term shall not be less than 10 (ten) years",
    );
    // Italic phrases keep their spaces ("force majeure", not "forcefmajeure").
    expect(art40.text_en).toContain("for reasons of force majeure.");
    // Articles added after 1996 have no translation.
    const lettered = await client.getSection("Art. 229-C");
    expect(lettered).toMatchObject({
      href: "art229-c",
      article_number: "Art. 229-C",
      text_en: null,
      html_en: null,
      title_en: null,
    });
    expect(lettered.text_pt).toBe(
      "Art. 229-C. (Artigo acrescido pela Lei nº 10.196, de 14/2/2001, e revogado pela Lei nº 14.195, de 26/8/2021)",
    );
    const preliminary = await client.getSection("art1");
    expect(preliminary.title_section).toBeNull();
    expect(
      await client.getSection(
        "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#art10",
      ),
    ).toMatchObject({ href: "art10" });
    expect(await client.resolveSectionHref("Art. 195")).toBe("art195");
    expect(await client.resolveSectionHref("Art. 7")).toBeNull();

    expect(await code(client.getSection("art999"))).toBe("SECTION_NOT_FOUND");
    expect(await code(client.getSection("not a citation"))).toBe(
      "SECTION_NOT_FOUND",
    );
    expect(
      await code(client.getSection("Art. 6", { version: "2020" as "current" })),
    ).toBe("VERSION_UNAVAILABLE");
  } finally {
    client.close();
  }
});

test("search covers both languages, defaults to phrases and pages stably", async () => {
  const client = new InpiBrStatutesClient({ corpusPath: fixture });
  try {
    const pt = await client.search({ query: "concorrência desleal" });
    expect(pt.hits.map((hit) => hit.href)).toContain("art195");
    const hit = pt.hits.find((item) => item.href === "art195");
    expect(hit).toMatchObject({
      title: "Art. 195 — Comete crime de concorrência desleal quem:",
      article_number: "Art. 195",
      path: [
        "TÍTULO V — DOS CRIMES CONTRA A PROPRIEDADE INDUSTRIAL",
        "Art. 195",
      ],
      result_url: "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#Art195",
      snippet: expect.stringContaining("<mark>"),
    });
    expect(typeof hit?.rank).toBe("number");
    const en = await client.search({ query: "unfair competition" });
    expect(en.hits.map((item) => item.href)).toContain("art195");
    // Diacritics fold in the unicode61 tokenizer.
    expect(
      (await client.search({ query: "concorrencia desleal" })).hits.length,
    ).toBe(pt.hits.length);
    // 'adj' is a phrase; 'or' widens.
    expect((await client.search({ query: "patente marca" })).hits).toEqual([]);
    const widened = await client.search({
      query: "patente marca",
      syntax: "or",
    });
    expect(widened.hits.length).toBeGreaterThan(1);
    const outline = await client.search({
      query: "patente",
      syntax: "and",
      sort: "outline",
    });
    const numbers = outline.hits.map((item) =>
      Number.parseInt(item.href.slice(3), 10),
    );
    expect(numbers).toEqual([...numbers].sort((a, b) => a - b));
    expect(numbers.length).toBeGreaterThan(2);
    const page = await client.search({
      query: "patente",
      syntax: "and",
      limit: 2,
      offset: 1,
    });
    expect(page).toMatchObject({ limit: 2, offset: 1, has_more: true });
    const all = await client.search({
      query: "patente",
      syntax: "and",
      limit: 100,
    });
    expect(page.hits.map((item) => item.href)).toEqual(
      all.hits.slice(1, 3).map((item) => item.href),
    );
    // Citation punctuation and FTS5 operators are matched as text.
    for (const syntax of ["and", "or"] as const)
      expect(
        await code(
          client.search({
            query: "Art. 54(2) G-II, 1207.01(a) L.611-10 NOT",
            syntax,
          }),
        ),
      ).toBe("resolved");
    expect((await client.search({ query: "   " })).hits).toEqual([]);
  } finally {
    client.close();
  }
});

test("Zstandard bytes, pins and the environment variables configure the reader", async () => {
  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new Uint8Array(zstdCompressSync(bytes));
  const fromBytes = new InpiBrStatutesClient({
    source: packed,
    expectedSha256: hash(bytes),
    expectedFileSha256: hash(packed),
  });
  try {
    const status = await fromBytes.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      compression: "zstd",
      artifact_sha256: hash(bytes),
      file_sha256: hash(packed),
    });
    expect((await fromBytes.getSection("Art. 125")).href).toBe("art125");
  } finally {
    fromBytes.close();
  }
  const wrong = new InpiBrStatutesClient({
    source: bytes,
    expectedSha256: "0".repeat(64),
  });
  expect(await code(wrong.getSection("Art. 6"))).toBe("CHECKSUM_MISMATCH");
  expect((await wrong.getCorpusStatus()).error?.code).toBe("CHECKSUM_MISMATCH");
  const saved = { ...process.env };
  try {
    process.env.INPI_BR_STATUTES_CORPUS_PATH = fixture;
    process.env.INPI_BR_STATUTES_CORPUS_SHA256 = hash(bytes);
    const fromEnv = new InpiBrStatutesClient();
    try {
      expect((await fromEnv.getCorpusStatus()).available).toBe(true);
    } finally {
      fromEnv.close();
    }
    process.env.INPI_BR_STATUTES_CORPUS_PATH = join(tmpdir(), "missing-lpi.db");
    const missing = new InpiBrStatutesClient();
    const status = await missing.getCorpusStatus();
    expect(status).toMatchObject({
      available: false,
      corpus_version: "unknown",
      corpus_synced_at: null,
    });
    expect(status.error?.code).toBe("CORPUS_UNAVAILABLE");
    expect(status.error?.message).toContain("INPI_BR_STATUTES_CORPUS_PATH");
  } finally {
    process.env = saved;
  }
});

test("WAL files, other schemas and metadata gaps are reported, not guessed", async () => {
  const directory = await mkdtemp(join(tmpdir(), "pca-inpi-br-wal-"));
  try {
    const bytes = new Uint8Array(await readFile(fixture));
    bytes[18] = 2;
    bytes[19] = 2;
    const wal = join(directory, "wal.db");
    await writeFile(wal, bytes);
    expect(
      (await new InpiBrStatutesClient({ corpusPath: wal }).getCorpusStatus())
        .error?.code,
    ).toBe("CORPUS_WAL_UNSUPPORTED");
  } finally {
    await rm(directory, { recursive: true });
  }
  await withCopy(
    "UPDATE meta SET value = '2' WHERE key = 'schema_version'",
    async (filename) => {
      const status = await new InpiBrStatutesClient({
        corpusPath: filename,
      }).getCorpusStatus();
      expect(status.error?.code).toBe("UNSUPPORTED_SCHEMA");
    },
  );
  // A Python-style build: no source_version, so lpi_year is the version.
  await withCopy(
    "DELETE FROM meta WHERE key IN ('source_version', 'latest_amendment', 'source_en_version')",
    async (filename) => {
      const client = new InpiBrStatutesClient({ corpusPath: filename });
      const status = await client.getCorpusStatus();
      expect(status).toMatchObject({
        corpus_version: "1996",
        latest_amendment: null,
        english_version: null,
      });
      client.close();
    },
  );
  await withCopy("DROP TABLE sections_fts", async (filename) => {
    const status = await new InpiBrStatutesClient({
      corpusPath: filename,
    }).getCorpusStatus();
    expect(status.error?.code).toBe("INVALID_CORPUS");
  });
});

import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { CorpusError } from "../packages/client/src/corpus/outline.js";
import {
  INPI_AR_STATUTES_NOTICE,
  INPI_AR_STATUTES_SOURCE_URL,
  InpiArSectionSchema,
  InpiArStatutesClient,
  inpiArFtsQuery,
  normalizeInpiArArticle,
  parseInpiArCitation,
  resolveInpiArStatute,
} from "../packages/client/src/inpi-ar-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "inpi-ar-statutes",
  "inpi_ar_statutes.db",
);
const hash = (value: Uint8Array) =>
  createHash("sha256").update(value).digest("hex");

test("statute names, Spanish names and law numbers resolve to the five keys", () => {
  expect(resolveInpiArStatute("Ley 24.481")).toBe("patents");
  expect(resolveInpiArStatute("ley 24481")).toBe("patents");
  expect(resolveInpiArStatute("Ley N° 24.481 (t.o. 1996)")).toBe("patents");
  expect(resolveInpiArStatute("Patent Law")).toBe("patents");
  expect(resolveInpiArStatute("Ley de Marcas")).toBe("trademarks");
  expect(resolveInpiArStatute("Ley Nº 22.362")).toBe("trademarks");
  expect(resolveInpiArStatute("Decreto-Ley 6673/63")).toBe("designs");
  expect(resolveInpiArStatute("diseños industriales")).toBe("designs");
  expect(resolveInpiArStatute("Ley 16.478")).toBe("designs");
  expect(resolveInpiArStatute("Propiedad Intelectual")).toBe("copyright");
  expect(resolveInpiArStatute("11723")).toBe("copyright");
  expect(resolveInpiArStatute("trade secrets")).toBe("trade_secrets");
  expect(resolveInpiArStatute("Ley de Confidencialidad")).toBe("trade_secrets");
  expect(resolveInpiArStatute("información confidencial")).toBe(
    "trade_secrets",
  );
  // Unknown names pass through normalized, so lookups report nothing.
  expect(resolveInpiArStatute("Código Civil")).toBe("codigo civil");
});

test("citations parse in Spanish and English, in both orders", () => {
  const cases: [string, string, string][] = [
    ["Artículo 4 Ley 24.481", "patents", "4"],
    ["art. 4 ley 24481", "patents", "4"],
    ["Ley 22.362 art. 3", "trademarks", "3"],
    ["Article 4 Patent Law", "patents", "4"],
    ["Artículo 4° de la Ley N° 24.481", "patents", "4"],
    ["Ley 24.481, artículo 83", "patents", "83"],
    ["Art. 5 bis Ley 11.723", "copyright", "5 bis"],
    ["Art. 5° bis de la Ley 11.723", "copyright", "5 bis"],
    ["art. 36 quater ley 11723", "copyright", "36 quáter"],
    ["art. 3 inc. a) Ley 22.362", "trademarks", "3"],
    ["Artículo 6 Decreto-Ley 6673/63", "designs", "6"],
    ["art 6 dl 6673/63", "designs", "6"],
    ["Art. 1 Ley 24.766", "trade_secrets", "1"],
    ["Section 3 Trademark Law", "trademarks", "3"],
    ["Ley de Patentes art. 4", "patents", "4"],
  ];
  for (const [citation, statute, number] of cases)
    expect(parseInpiArCitation(citation)).toEqual({
      statute: statute as "patents",
      section_number: number,
    });
  expect(parseInpiArCitation("")).toBeNull();
  expect(parseInpiArCitation("nonsense")).toBeNull();
  expect(parseInpiArCitation("Artículo 4 Ley 99.999")).toBeNull();
  expect(normalizeInpiArArticle("4º")).toBe("4");
  expect(normalizeInpiArArticle("5bis")).toBe("5 bis");
  expect(normalizeInpiArArticle("36 Quáter")).toBe("36 quáter");
  expect(normalizeInpiArArticle("4A")).toBeNull();
});

test("queries are quoted; a trailing * is a prefix", () => {
  expect(inpiArFtsQuery("marca registrada", "and")).toBe(
    '"marca" "registrada"',
  );
  expect(inpiArFtsQuery("patent* NEAR", "or")).toBe('"patent"* OR "NEAR"');
  expect(inpiArFtsQuery("patent*", "adj")).toBe('"patent*"');
  expect(inpiArFtsQuery("*", "and")).toBe('"*"');
  expect(inpiArFtsQuery("  ", "and")).toBe("");
});

test("status, statutes and articles come from the Infoleg build", async () => {
  const before = hash(await readFile(fixture));
  const client = new InpiArStatutesClient({ corpusPath: fixture });
  try {
    const status = await client.getCorpusStatus();
    expect(status).toMatchObject({
      available: true,
      label: "INPI Argentina statutes",
      corpus_version: "Infoleg updated texts, 2026-10-26",
      schema_version: 1,
      section_count: 16,
      snapshot_date: "2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
      compression: "none",
      source_url: INPI_AR_STATUTES_SOURCE_URL,
      notice: INPI_AR_STATUTES_NOTICE,
      // The fixture is a 16-article subset of the 301-article build.
      metadata: {
        section_count: "16",
        fixture_subset_of: "301",
        language: "es",
      },
    });
    expect(status.artifact_sha256).toBe(before);
    const statutes = await client.listStatutes();
    expect(statutes.map((item) => [item.statute, item.section_count])).toEqual([
      ["patents", 4],
      ["trademarks", 4],
      ["designs", 2],
      ["copyright", 4],
      ["trade_secrets", 2],
    ]);
    expect(statutes[0]).toMatchObject({
      source_url:
        "https://servicios.infoleg.gob.ar/infolegInternet/anexos/35000-39999/35001/texact.htm",
      short_name: "Ley 24.481",
      norm_url:
        "https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=35001",
      text_kind: "texact",
      version: expect.stringContaining("Decreto Reglamentario 260/1996"),
      newest_note_date: "2025-09-03",
      text_sha256: expect.stringMatching(/^[a-f\d]{64}$/),
    });
    expect(statutes[4]).toMatchObject({
      text_kind: "norma",
      version: expect.stringContaining("as published"),
    });
    expect(await client.meta()).toEqual({
      schema_version: 1,
      snapshot_date: "2026-10-26",
      source_version: "Infoleg updated texts, 2026-10-26",
      section_count: 16,
    });

    const section = await client.getSectionByCitation("Artículo 4 Ley 24.481");
    expect(InpiArSectionSchema.parse(section)).toBeTruthy();
    expect(section).toMatchObject({
      statute: "patents",
      section_number: "4",
      section_label: "Artículo 4° Ley 24.481",
      title:
        "TITULO II — DE LAS PATENTES DE INVENCION / CAPITULO I — PATENTABILIDAD",
      source_url:
        "https://servicios.infoleg.gob.ar/infolegInternet/anexos/35000-39999/35001/texact.htm",
      provenance: {
        source_url: INPI_AR_STATUTES_SOURCE_URL,
        corpus_version: "Infoleg updated texts, 2026-10-26",
        cache_hit: true,
      },
    });
    const lines = section?.text.split("\n") ?? [];
    expect(lines[0]).toBe(
      "Serán patentables las invenciones de productos o de procedimientos, siempre que sean nuevas, entrañen una actividad inventiva y sean susceptibles de aplicación industrial.",
    );
    expect(lines.at(-1)).toStartWith("e) Habrá aplicación industrial");

    // Notes follow a blank line, the inciso marker kept on a moved inline note.
    const extinction = await client.getSection("Ley 22.362", "23");
    expect(extinction?.text.split("\n\n")).toEqual([
      "El derecho de propiedad de una marca se extingue:\na) por renuncia de su titular;\nb) por vencimiento del término de vigencia, sin que se renueve el registro;\nc) Por la declaración de nulidad o caducidad del registro.",
      "c) (Inciso sustituido por art. 72 de la Ley N° 27.444 B.O. 18/6/2018)",
    ]);
    expect((await client.getSection("patents", "12"))?.text).toEndWith(
      "\n\n(Artículo sustituido por art. 77 de la Ley N° 27.444 B.O. 18/6/2018)",
    );
    // Repealed articles are rows holding Infoleg's note.
    expect((await client.getSectionByCitation("art. 19 ley 22362"))?.text).toBe(
      "(Artículo derogado por art. 69 de la Ley N° 27.444 B.O. 18/6/2018)",
    );
    const inserted = await client.getSection("copyright", "36 quater");
    expect(inserted?.section_label).toBe("Artículo 36 quáter Ley 11.723");
    expect(inserted?.title).toBe("DISPOSICIONES ESPECIALES");
    expect((await client.getSection("11.723", "5bis"))?.section_number).toBe(
      "5 bis",
    );
    expect(
      await client.getSectionByCitation("Art. 6 Decreto-Ley 6673/63"),
    ).toBeNull(); // not in the fixture
    expect(
      (await client.getSectionByCitation("Art. 3 Decreto-Ley 6673/63"))?.text,
    ).toStartWith(
      "A los efectos de este decreto, se considera modelo o diseño",
    );
    expect(
      (await client.getSectionByCitation("Ley 24.766 art. 15"))?.text,
    ).toBe("Comuníquese al Poder Ejecutivo.");
    expect(await client.getSection("patents", "9999")).toBeNull();
    expect(await client.getSection("patents", "4A")).toBeNull();
    expect(await client.getSection("nonsense", "3")).toBeNull();
    expect(await client.getSectionByCitation("nonsense")).toBeNull();
    expect(hash(await readFile(fixture))).toBe(before);
  } finally {
    client.close();
  }
});

test("search folds accents, filters, pages, orders by outline and never runs MATCH syntax", async () => {
  const client = new InpiArStatutesClient({ corpusPath: fixture });
  try {
    // Accents are optional in both directions.
    const plain = await client.search({ query: "informacion secreta" });
    expect(plain.hits[0]).toMatchObject({
      statute: "trade_secrets",
      section_number: "1",
      snippet: expect.stringContaining("<mark>"),
    });
    expect(typeof plain.hits[0]?.rank).toBe("number");
    expect(
      (await client.search({ query: "diseno" })).hits.map((h) => h.statute),
    ).toContain("designs");
    expect(
      (await client.search({ query: "DISEÑO" })).hits.length,
    ).toBeGreaterThan(0);
    // Not stemmed: "patentable" alone misses "patentables"; a prefix finds it.
    expect((await client.search({ query: "patentable" })).hits).toEqual([]);
    expect(
      (await client.search({ query: "patentable*" })).hits.map(
        (h) => h.section_number,
      ),
    ).toContain("4");

    const scoped = await client.search({
      query: "marca",
      statute: "Ley de Marcas",
    });
    expect(scoped.statute).toBe("trademarks");
    expect(scoped.hits.length).toBeGreaterThan(0);
    expect(scoped.hits.every((hit) => hit.statute === "trademarks")).toBe(true);

    const paged = await client.search({ query: "ley", per_page: 1 });
    expect(paged.hits).toHaveLength(1);
    expect(paged.has_more).toBe(true);
    const second = await client.search({ query: "ley", per_page: 1, page: 2 });
    expect(second.page).toBe(2);
    expect(second.hits[0]?.section_label).not.toBe(
      paged.hits[0]?.section_label,
    );

    // Statutes in key order, numbers numeric, insertions after their number.
    const outline = await client.search({
      query: "artículo derogado obras ley",
      syntax: "or",
      sort: "outline",
      per_page: 50,
    });
    const order = outline.hits.map(
      (hit) => `${hit.statute}:${hit.section_number}`,
    );
    expect(order.indexOf("patents:12")).toBeLessThan(
      order.indexOf("patents:90"),
    );
    expect(order.indexOf("copyright:1")).toBeLessThan(
      order.indexOf("copyright:5 bis"),
    );
    expect(order.indexOf("copyright:5 bis")).toBeLessThan(
      order.indexOf("copyright:36 quáter"),
    );
    expect(order.indexOf("copyright:36 quáter")).toBeLessThan(
      order.indexOf("copyright:74 bis"),
    );
    expect(order.indexOf("trademarks:19")).toBeLessThan(
      order.indexOf("designs:14"),
    );
    expect(outline.hits.every((hit) => hit.rank === null)).toBe(true);

    for (const query of ["NEAR(marca", 'marca" OR "x', "marca-registrada", "*"])
      await client.search({ query });
    expect((await client.search({ query: "   " })).hits).toEqual([]);
    await expect(
      client.search({ query: "x", per_page: 101 }),
    ).rejects.toThrow();
  } finally {
    client.close();
  }
});

test("a missing corpus reports how to supply one; zstd bytes and pins open in memory", async () => {
  const missing = new InpiArStatutesClient({
    corpusPath: join(
      import.meta.dir,
      "fixtures",
      "inpi-ar-statutes",
      "absent.db",
    ),
  });
  const status = await missing.getCorpusStatus();
  expect(status.available).toBe(false);
  expect(status.statutes).toBeNull();
  expect(status.notice).toBe(INPI_AR_STATUTES_NOTICE);
  expect(status.error?.message).toContain("INPI_AR_STATUTES_CORPUS_PATH");
  await expect(missing.listStatutes()).rejects.toBeInstanceOf(CorpusError);

  const bytes = new Uint8Array(await readFile(fixture));
  const packed = new InpiArStatutesClient({
    source: new Uint8Array(zstdCompressSync(bytes)),
    expectedSha256: hash(bytes),
  });
  try {
    expect((await packed.getCorpusStatus()).compression).toBe("zstd");
    expect(
      (await packed.getSectionByCitation("Art. 74 bis Ley 11.723"))?.text,
    ).toStartWith("(Artículo derogado");
  } finally {
    packed.close();
  }
  const wrong = new InpiArStatutesClient({
    source: bytes,
    expectedSha256: "0".repeat(64),
  });
  expect((await wrong.getCorpusStatus()).available).toBe(false);
  const wrongFile = new InpiArStatutesClient({
    source: bytes,
    expectedFileSha256: "f".repeat(64),
  });
  expect((await wrongFile.getCorpusStatus()).available).toBe(false);
});

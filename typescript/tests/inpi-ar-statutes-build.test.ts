import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  articleLabel,
  articleStart,
  articleText,
  decodeInfoleg,
  isNote,
  newestNoteDate,
  pageParagraphs,
  parseNormPage,
  parseSource,
  parseStatute,
  SOURCES,
  type StatuteSource,
  splitTrailingNotes,
  statuteRegion,
  wordCoverage,
} from "../scripts/build-inpi-ar-statutes-corpus.js";

/** Encode text as windows-1252, as Infoleg serves its pages. */
function cp1252(text: string): Uint8Array {
  const extra: Record<string, number> = {
    "—": 0x97,
    "–": 0x96,
    "“": 0x93,
    "”": 0x94,
    "…": 0x85,
  };
  return new Uint8Array(
    [...text].map((char) => {
      const code = char.codePointAt(0) as number;
      if (code < 256) return code;
      const mapped = extra[char];
      if (mapped === undefined) throw new Error(`No cp1252 byte for ${char}`);
      return mapped;
    }),
  );
}
const page = (body: string, charset = "windows-1252") =>
  `<html><head><meta http-equiv="Content-Type" content="text/html; charset=${charset}"></head><body><header id="branding"><div id="encabezado_norma">Infoleg</div></header>${body}</body></html>`;
const source = (overrides: Partial<StatuteSource> = {}): StatuteSource => ({
  statute: "test",
  short_name: "Ley 1",
  title: "Ley 1",
  infoleg_id: "1",
  expect: /./,
  stop: /^FIRMA$/,
  last_article: 3,
  ...overrides,
});

test("windows-1252 and ISO-8859-1 pages decode with accents, ñ, º and dashes intact", () => {
  const html = page(
    "<p>ARTICULO 1º — Diseño, información, “patentes” y años…</p>",
  );
  const text = pageParagraphs(decodeInfoleg(cp1252(html)))[0]?.text;
  expect(text).toBe("ARTICULO 1º — Diseño, información, “patentes” y años…");
  // ISO-8859-1 is decoded as windows-1252, the WHATWG rule, so 0x97 stays a dash.
  expect(
    pageParagraphs(
      decodeInfoleg(cp1252(page("<p>Art. 2° — á</p>", "ISO-8859-1"))),
    )[0]?.text,
  ).toBe("Art. 2° — á");
  // A page without a declaration is read as windows-1252; entities decode too.
  expect(
    pageParagraphs(
      decodeInfoleg(
        cp1252("<html><body><P>Protecci&oacute;n 1&#176;<P>ó</body></html>"),
      ),
    ).map((p) => p.text),
  ).toEqual(["Protección 1°", "ó"]);
});

test("paragraphs break at blocks and <br>, and know when they are centered", () => {
  const paragraphs = pageParagraphs(
    page(
      '<p align="center"><b>DE LA EDICION</b></p><p align="justify">a) uno<br>b) dos</p><center>TITULO I</center><script>x()</script>',
    ),
  );
  expect(paragraphs).toEqual([
    { text: "DE LA EDICION", centered: true },
    { text: "a) uno", centered: false },
    { text: "b) dos", centered: false },
    { text: "TITULO I", centered: true },
  ]);
});

test("article openings in every form Infoleg prints, and nothing else", () => {
  expect(articleStart("ARTICULO 1º — Las invenciones")).toEqual({
    base: 1,
    suffix: null,
    rest: "Las invenciones",
  });
  expect(articleStart("Art. 5º bis. — La propiedad")?.suffix).toBe("bis");
  expect(articleStart("Art. 34 bis: Lo dispuesto")?.rest).toBe("Lo dispuesto");
  expect(articleStart("Art. 36 quater. — El")?.suffix).toBe("quáter");
  expect(articleStart("ARTICULO 10 — Quien desee")?.base).toBe(10);
  expect(articleStart("ARTICULO 57. - Presentada")?.base).toBe(57);
  expect(articleStart("ARTICULO 90. —Créase")?.rest).toBe("Créase");
  expect(articleStart("ARTICULO 1°- Las personas")?.rest).toBe("Las personas");
  // Ley 24.766 prints its last article as "l5".
  expect(articleStart("ARTICULO l5- Comuníquese")?.base).toBe(15);
  expect(articleStart("Artículo 5 de la ley establece")).toBeNull();
  expect(articleStart("El artículo 4º — dispone")).toBeNull();
  expect(articleLabel(4, null)).toBe("Artículo 4°");
  expect(articleLabel(5, "bis")).toBe("Artículo 5° bis");
  expect(articleLabel(36, "quáter")).toBe("Artículo 36 quáter");
});

test("Infoleg's notes are recognized whole, trailing or with inciso markers inside", () => {
  expect(
    isNote(
      "Artículo sustituido por art. 77 de la Ley N° 27.444 B.O. 18/6/2018",
    ),
  ).toBe(true);
  expect(isNote("Nota Infoleg: por art. 1° de la Resolución N° 583/2025")).toBe(
    true,
  );
  expect(isNote("60")).toBe(false);
  expect(isNote("Artículo 5° de esta ley")).toBe(false);
  expect(
    splitTrailingNotes(
      "c) Por la declaración de nulidad. (Inciso sustituido por art. 72 de la Ley N° 27.444 B.O. 18/6/2018)",
    ),
  ).toEqual({
    body: "c) Por la declaración de nulidad.",
    notes: [
      "(Inciso sustituido por art. 72 de la Ley N° 27.444 B.O. 18/6/2018)",
    ],
  });
  // Parentheses inside the text stay.
  expect(
    splitTrailingNotes("dentro de SESENTA (60) días (corridos)").notes,
  ).toEqual([]);
  expect(
    newestNoteDate([
      "(Artículo sustituido por art. 1° de la Ley N° 25.859 B.O. 14/1/2004).",
      "(Texto Original restituido por art. 1° del Decreto N° 627/2025 B.O. 3/09/2025.)",
    ]),
  ).toBe("2025-09-03");
});

test("articles split with headings as titles and notes moved to the end", () => {
  const paragraphs = pageParagraphs(
    page(`
<p>LEY DE PRUEBA</p><p>EL CONGRESO SANCIONA:</p>
<p align="center">CAPITULO I</p><p align="center">DE LAS MARCAS</p>
<p align="center">SECCION 1<sup>a</sup></p><p align="center">Derecho de propiedad</p>
<p>ARTICULO 1º — No pueden ser registrados:</p>
<p>a) los nombres;</p>
<p>b) los signos del inciso a) y c) del artículo 3.</p>
<p>(Nota Infoleg: por art. 1° de la Resolución N° 583/2025 B.O. 11/12/2025 se limita el examen de los incisos b), d) e i) del presente artículo)</p>
<p align="center">SECCION 2ª</p><p align="center">Trámites</p>
<p>(Nota Infoleg: por art. 2° de la Resolución N° 583/2025 B.O. 11/12/2025 se modifica el procedimiento de la presente Sección.</p>
<p>Por art. 3° de la misma norma se establece otra cosa.)</p>
<p>ARTICULO 2º — (Artículo derogado por art. 69 de la Ley N° 27.444 B.O. 18/6/2018)</p>
<p>ARTICULO 2º bis — El derecho se extingue:</p>
<p>c) Por la declaración de nulidad. (Inciso sustituido por art. 72 de la Ley N° 27.444 B.O. 18/6/2018)</p>
<p>ARTICULO 9º — Una cita cruzada no es un artículo.</p>
<p>ARTICULO 3º — Comuníquese.</p>
<p>FIRMA</p><p>ARTICULO 4º — después de la firma</p>`),
  );
  const articles = parseStatute(source(), paragraphs);
  expect(articles.map((a) => a.section_number)).toEqual([
    "1",
    "2",
    "2 bis",
    "3",
  ]);
  const [first, repealed, inserted, last] = articles;
  expect(first?.title).toBe(
    "CAPITULO I — DE LAS MARCAS / SECCION 1a — Derecho de propiedad",
  );
  expect(first?.body).toEqual([
    "No pueden ser registrados:",
    "a) los nombres;",
    "b) los signos del inciso a) y c) del artículo 3.",
  ]);
  expect(first?.notes[0]).toStartWith("(Nota Infoleg: por art. 1°");
  // A note after a heading belongs to the next article; it ran over two paragraphs.
  expect(repealed?.title).toBe(
    "CAPITULO I — DE LAS MARCAS / SECCION 2ª — Trámites",
  );
  expect(repealed?.body).toEqual([]);
  expect(repealed?.notes).toEqual([
    "(Nota Infoleg: por art. 2° de la Resolución N° 583/2025 B.O. 11/12/2025 se modifica el procedimiento de la presente Sección. Por art. 3° de la misma norma se establece otra cosa.)",
    "(Artículo derogado por art. 69 de la Ley N° 27.444 B.O. 18/6/2018)",
  ]);
  expect(articleText(repealed as never)).toStartWith("(Nota Infoleg");
  // The inciso keeps its marker on the moved note; "9" does not follow "2 bis".
  expect(articleText(inserted as never)).toBe(
    "El derecho se extingue:\nc) Por la declaración de nulidad.\nARTICULO 9º — Una cita cruzada no es un artículo.\n\nc) (Inciso sustituido por art. 72 de la Ley N° 27.444 B.O. 18/6/2018)",
  );
  expect(last?.body).toEqual(["Comuníquese."]);
  expect(
    statuteRegion(source(), paragraphs)
      .map((p) => p.text)
      .at(-1),
  ).toBe("ARTICULO 3º — Comuníquese.");
});

test("a start marker skips the decree around the law; gaps and a missing end fail loudly", () => {
  const decree = page(
    "<p>Artículo 1º — Apruébase el texto ordenado.</p><p>Artículo 2º — De forma.</p><p>ANEXO I</p><p>ARTICULO 1º — Uno.</p><p>ARTICULO 2º — Dos.</p><p>ANEXO II</p><p>Artículo 1º — Reglamento.</p>",
  );
  const annex = source({
    start: /^ANEXO I$/,
    stop: /^ANEXO II$/,
    last_article: 2,
  });
  expect(
    parseStatute(annex, pageParagraphs(decree)).map((a) => a.body[0]),
  ).toEqual(["Uno.", "Dos."]);
  expect(() =>
    parseStatute(
      source({ last_article: 3 }),
      pageParagraphs(page("<p>ARTICULO 1º — Uno.</p><p>FIRMA</p>")),
    ),
  ).toThrow("not 1-3");
  expect(() =>
    parseStatute(
      source({ last_article: 1 }),
      pageParagraphs(page("<p>ARTICULO 1º — Uno.</p>")),
    ),
  ).toThrow("end of statute not found");
});

test("the norm page gives the heading, dates and the updated-text link", () => {
  const norm =
    parseNormPage(`<html><body><div id="Textos_Completos"><p><strong>Ley&nbsp;
  22362 PODER EJECUTIVO NACIONAL (P.E.N.)</strong> 22-dic-1980 MARCAS Y DESIGNACIONES</p>
  <p>Publicada en el Bolet&iacute;n Oficial del 02-ene-1981</p><p><strong>Resumen:</strong> NUEVO REGIMEN DE MARCAS.</p>
  <p><a href='anexos/15000-19999/18803/norma.htm'><b>Texto completo de la norma</b></a></p>
  <p><a href='anexos/15000-19999/18803/texact.htm'><b>Texto actualizado de la norma</b></a></p></div></body></html>`);
  expect(norm).toMatchObject({
    heading: "Ley 22362",
    date: "22-dic-1980",
    published: "Publicada en el Boletín Oficial del 02-ene-1981",
    summary: "NUEVO REGIMEN DE MARCAS.",
    norma_href: "anexos/15000-19999/18803/norma.htm",
    texact_href: "anexos/15000-19999/18803/texact.htm",
  });
  expect(wordCoverage("uno dos tres", "Uno dós")).toBeCloseTo(2 / 3);
});

test("the source manifest records every statute, its text and its counts", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "..", "scripts", "inpi-ar-statutes-sources.json"),
      "utf8",
    ),
  ) as {
    user_agent: string;
    statutes: {
      statute: string;
      infoleg_id: string;
      text_kind: string;
      text_url: string;
      text_sha256: string;
      text_bytes: number;
      retrieved_at: string;
      section_count: number;
      word_coverage: number;
    }[];
  };
  expect(manifest.user_agent).toBe(
    "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)",
  );
  expect(
    manifest.statutes.map((s) => [s.statute, s.text_kind, s.section_count]),
  ).toEqual([
    ["patents", "texact", 105],
    ["trademarks", "texact", 52],
    ["designs", "texact", 31],
    ["copyright", "texact", 98],
    ["trade_secrets", "norma", 15],
  ]);
  for (const [index, entry] of manifest.statutes.entries()) {
    expect(entry.infoleg_id).toBe(SOURCES[index]?.infoleg_id as string);
    expect(entry.text_url).toStartWith(
      `https://servicios.infoleg.gob.ar/infolegInternet/anexos/`,
    );
    expect(entry.text_url).toEndWith(
      `/${entry.infoleg_id}/${entry.text_kind}.htm`,
    );
    expect(entry.text_sha256).toMatch(/^[a-f\d]{64}$/);
    expect(entry.text_bytes).toBeGreaterThan(10_000);
    expect(entry.retrieved_at).toMatch(/^2026-10-26T/);
    expect(entry.word_coverage).toBeGreaterThan(0.98);
  }
});

test("a whole archived page parses with its note count, newest note and word coverage", () => {
  const bytes = cp1252(
    page(
      "<p>Preámbulo largo que no es ley.</p><p>ARTICULO 1º — Diseño.</p><p>(Artículo sustituido por art. 92 de la Ley N° 27.444 B.O. 18/6/2018)</p><p>ARTICULO 2º — Comuníquese.</p><p>FIRMA</p>",
    ),
  );
  const parsed = parseSource(source({ last_article: 2 }), bytes);
  expect(parsed.articles.map((a) => a.body[0])).toEqual([
    "Diseño.",
    "Comuníquese.",
  ]);
  expect(parsed.note_count).toBe(1);
  expect(parsed.newest_note_date).toBe("2018-06-18");
  // The labels hold the "ARTICULO 1º" words the text drops.
  expect(parsed.word_coverage).toBe(1);
  expect(parsed.page_word_coverage).toBeLessThan(1);
});

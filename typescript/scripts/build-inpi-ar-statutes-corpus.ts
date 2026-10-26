// Builds the INPI Argentina statutes SQLite/FTS5 corpus (the statute-row
// schema the ILPO Israel corpus uses, version 1) from Infoleg, the Argentine
// Ministry of Justice's legislative information service. For each of the
// five IP statutes the builder fetches the Infoleg norm page
// (verNorma.do?id=N), checks that it describes the expected norm, reads the
// link to the updated text ("Texto actualizado de la norma", texact.htm) or,
// where Infoleg keeps none, the text as published ("Texto completo de la
// norma", norma.htm), and archives that page. Plain HTTPS GETs with an honest
// user agent; no browser, cookies or challenge handling.
//
// Infoleg's pages are windows-1252 or ISO-8859-1 (which WHATWG decodes as
// windows-1252); the declared charset is honoured. Paragraphs are read with
// linkedom. An article starts at a paragraph opening "ARTICULO 4º —",
// "Art. 5º bis. —" or "ARTICULO l5-" whose number can follow the previous
// one. Infoleg's notes ("(Artículo sustituido por art. 77 de la Ley N°
// 27.444 B.O. 18/6/2018)", "(Nota Infoleg: …)", a trailing "(Inciso
// sustituido …)") are moved to the end of the article text. Título, Capítulo
// and Sección headings become the row title.
//
// Usage (from typescript/):
//   bun scripts/build-inpi-ar-statutes-corpus.ts --fetch   # download, rewrite the source manifest, build
//   bun scripts/build-inpi-ar-statutes-corpus.ts           # rebuild from the archived pages (sha256-checked)
//   bun scripts/build-inpi-ar-statutes-corpus.ts --fixture # also rewrite the test fixture subset
// Options: --output PATH (default .data/inpi_ar_statutes/inpi_ar_statutes.db,
// must not exist), --raw DIR (default .data/inpi_ar_statutes/raw).
// The output is a standalone DELETE-journal database, ready for
// scripts/compress-corpus.ts without a preparation step.
import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
// linkedom, through the client package that depends on it.
import { parseDocument } from "../packages/client/src/google-patents/dom.js";

const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
export const INFOLEG_ORIGIN = "https://servicios.infoleg.gob.ar";
const root = join(import.meta.dir, "..");
const manifestPath = join(import.meta.dir, "inpi-ar-statutes-sources.json");
const fixturePath = join(
  root,
  "tests/fixtures/inpi-ar-statutes/inpi_ar_statutes.db",
);

export interface StatuteSource {
  statute: string;
  /** Citation name, e.g. 'Ley 24.481'. */
  short_name: string;
  title: string;
  /** Infoleg norm id, found with Infoleg's own search by type and number. */
  infoleg_id: string;
  /** The norm page must match this, so a wrong id fails loudly. */
  expect: RegExp;
  /** Articles start after the first paragraph matching this (the law inside a decree's annex). */
  start?: RegExp;
  /** The statute ends at the first paragraph matching this (signatures, annexes). */
  stop: RegExp;
  /** Highest article number; every number from 1 must be present. */
  last_article: number;
}

/** The five statutes and their Infoleg norms. */
export const SOURCES: StatuteSource[] = [
  {
    statute: "patents",
    short_name: "Ley 24.481",
    title:
      "Ley 24.481 de Patentes de Invención y Modelos de Utilidad (t.o. Decreto 260/96)",
    // Ley 24.481 itself (id 27289) has only the text as enacted; the
    // texto ordenado approved by Decreto 260/96 is where Infoleg keeps the
    // law up to date, as its Anexo I.
    infoleg_id: "35001",
    expect: /TEXTO ORDENADO DE LA LEY N. 24\.481/,
    start: /^ANEXO I$/,
    stop: /^ANEXO II$/,
    last_article: 105,
  },
  {
    statute: "trademarks",
    short_name: "Ley 22.362",
    title: "Ley 22.362 de Marcas y Designaciones",
    infoleg_id: "18803",
    expect: /Ley\s+22362[\s\S]*MARCAS Y DESIGNACIONES/,
    stop: /^VIDELA$/,
    last_article: 52,
  },
  {
    statute: "designs",
    short_name: "Decreto-Ley 6673/63",
    title:
      "Decreto-Ley 6673/63 de Modelos y Diseños Industriales (ratificado por Ley 16.478)",
    infoleg_id: "27687",
    expect: /Decreto\/Ley\s+6673\/1963/,
    stop: /^GUIDO\b/,
    last_article: 31,
  },
  {
    statute: "copyright",
    short_name: "Ley 11.723",
    title: "Ley 11.723 de Régimen Legal de la Propiedad Intelectual",
    infoleg_id: "42755",
    expect: /Ley\s+11723[\s\S]*PROPIEDAD INTELECTUAL/,
    stop: /^Dada en la Sala de Sesiones/i,
    last_article: 89,
  },
  {
    statute: "trade_secrets",
    short_name: "Ley 24.766",
    title:
      "Ley 24.766 de Confidencialidad sobre Información y Productos (información no divulgada)",
    infoleg_id: "41094",
    expect: /Ley\s+24766[\s\S]*CONFIDENCIALIDAD/,
    stop: /^DADA EN LA SALA DE SESIONES/i,
    last_article: 15,
  },
];

/** Articles copied into the committed test fixture. */
const FIXTURE_ARTICLES: Record<string, string[]> = {
  patents: ["4", "8", "12", "90"],
  trademarks: ["3", "10", "19", "23"],
  designs: ["3", "14"],
  copyright: ["1", "5 bis", "36 quáter", "74 bis"],
  trade_secrets: ["1", "15"],
};

// The ILPO statutes schema (version 1) with a Spanish-friendly tokenizer:
// unicode61 with remove_diacritics 2 folds accents (patente/patenté,
// diseño/diseno, información/informacion); no Porter stemming, which is
// English-only.
const DDL = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections (
    rowid          INTEGER PRIMARY KEY,
    statute        TEXT NOT NULL,
    section_number TEXT NOT NULL,
    section_label  TEXT NOT NULL,
    title          TEXT,
    text           TEXT NOT NULL,
    source_url     TEXT,
    UNIQUE(statute, section_number)
);
CREATE INDEX idx_sections_statute ON sections(statute);
CREATE INDEX idx_sections_section_number ON sections(section_number);
CREATE VIRTUAL TABLE sections_fts USING fts5(
    statute, section_label, title, text,
    content='sections', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, statute, section_label, title, text)
    VALUES (new.rowid, new.statute, new.section_label, new.title, new.text);
END;
CREATE TRIGGER sections_ad AFTER DELETE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, statute, section_label, title, text)
    VALUES ('delete', old.rowid, old.statute, old.section_label, old.title, old.text);
END;
CREATE TRIGGER sections_au AFTER UPDATE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, statute, section_label, title, text)
    VALUES ('delete', old.rowid, old.statute, old.section_label, old.title, old.text);
    INSERT INTO sections_fts(rowid, statute, section_label, title, text)
    VALUES (new.rowid, new.statute, new.section_label, new.title, new.text);
END;
`;

// ---------------------------------------------------------------- decoding

/** The charset a page declares in its first bytes, or null. */
export function declaredCharset(bytes: Uint8Array): string | null {
  const head = new TextDecoder("ascii").decode(bytes.slice(0, 4096));
  return /<meta[^>]+charset\s*=\s*["']?([\w-]+)/i.exec(head)?.[1] ?? null;
}

/**
 * Decode an Infoleg page. Pages declare windows-1252 or ISO-8859-1 (WHATWG
 * decodes the latter as windows-1252, so curly quotes and dashes in 0x80-0x9F
 * survive); a page without a declaration is treated as windows-1252.
 */
export function decodeInfoleg(bytes: Uint8Array): string {
  const label = declaredCharset(bytes) ?? "windows-1252";
  let decoder: TextDecoder;
  try {
    decoder = new TextDecoder(label, { fatal: true });
  } catch {
    decoder = new TextDecoder("windows-1252");
  }
  return decoder.decode(bytes);
}

// ---------------------------------------------------------------- paragraphs

export interface Paragraph {
  text: string;
  centered: boolean;
}

const BLOCKS = new Set([
  "P",
  "DIV",
  "H1",
  "H2",
  "H3",
  "H4",
  "H5",
  "H6",
  "LI",
  "UL",
  "OL",
  "TR",
  "TABLE",
  "CENTER",
  "BLOCKQUOTE",
  "PRE",
  "DD",
  "DT",
  "DL",
]);
const clean = (text: string) => text.replace(/[\s ]+/g, " ").trim();

interface DomNode {
  nodeType: number;
  nodeName: string;
  data?: string;
  childNodes: ArrayLike<DomNode>;
  parentNode: DomNode | null;
  getAttribute?: (name: string) => string | null;
}
function isCentered(node: DomNode | null): boolean {
  for (let el = node; el; el = el.parentNode) {
    if (el.nodeType !== 1) continue;
    if (el.nodeName === "CENTER") return true;
    if (el.getAttribute?.("align")?.toLowerCase() === "center") return true;
    if (/text-align\s*:\s*center/i.test(el.getAttribute?.("style") ?? ""))
      return true;
  }
  return false;
}

/** The page's paragraphs in order: block elements and <br> break them. */
export function pageParagraphs(html: string): Paragraph[] {
  const document = parseDocument(html);
  for (const el of document.querySelectorAll(
    "script, style, noscript, header, map, #encabezado_norma",
  ))
    el.remove();
  const out: Paragraph[] = [];
  let buffer = "";
  let first: DomNode | null = null;
  const flush = () => {
    const text = clean(buffer);
    if (text) out.push({ text, centered: isCentered(first) });
    buffer = "";
    first = null;
  };
  const walk = (node: DomNode) => {
    if (node.nodeType === 3) {
      if (!first && (node.data ?? "").trim()) first = node.parentNode;
      buffer += node.data ?? "";
      return;
    }
    if (node.nodeType !== 1) return;
    if (node.nodeName === "BR") return flush();
    const block = BLOCKS.has(node.nodeName);
    if (block) flush();
    for (const child of Array.from(node.childNodes)) walk(child);
    if (block) flush();
  };
  walk(document.body as unknown as DomNode);
  flush();
  return out;
}

// ---------------------------------------------------------------- articles

const SUFFIXES = [
  "bis",
  "ter",
  "quáter",
  "quinquies",
  "sexies",
  "septies",
  "octies",
  "nonies",
  "decies",
];
const ARTICLE =
  /^(?:ART[ÍI]CULO|Art\.)\s*([l\d]\d{0,3})\s*[º°ª]?\s*\.?\s*(bis|ter|qu[áa]ter|quinquies|sexies|septies|octies|nonies|novies|decies)?\s*\.?\s*(?:[—–-]+|:|\.)\s*/i;

/** Canonical suffix spelling ('quater' → 'quáter', 'novies' → 'nonies'). */
export function canonicalSuffix(value: string): string {
  const lower = value.toLowerCase();
  if (lower === "quater") return "quáter";
  if (lower === "novies") return "nonies";
  return lower;
}

/** The article a paragraph opens, or null. "l5" (Ley 24.766's typo for 15) reads as 15. */
export function articleStart(
  text: string,
): { base: number; suffix: string | null; rest: string } | null {
  const match = ARTICLE.exec(text);
  if (!match?.[1] || !/\d/.test(match[1])) return null;
  return {
    base: Number(match[1].replace(/l/g, "1")),
    suffix: match[2] ? canonicalSuffix(match[2]) : null,
    rest: text.slice(match[0].length).trim(),
  };
}

const NOTE_START =
  /^(?:Nota\s+Infoleg|Por\s+arts?\b|Ver\b|Texto\b|Art[íi]culos?\b|Arts?\.|Incisos?\b|P[áa]rrafos?\b|Apartados?\b|Puntos?\b|[ÚU]ltim[oa]s?\b|Primer[oa]?\b|Segund[oa]\b|Tercer[oa]?\b|Cuart[oa]\b|Quint[oa]\b|Sext[oa]\b|Expresi[óo]n\b|Denominaci[óo]n\b|Montos?\b|Vigencia\b|Observad|Vetad|Derogad|Sustituid|Incorporad|Restituid)/i;
const NOTE_REF = /\b(?:Ley|Decreto|Resoluci[óo]n|Disposici[óo]n)\b|B\.\s?O\./;
/** Whether the inside of a parenthesis is one of Infoleg's amendment notes. */
export function isNote(inner: string): boolean {
  return NOTE_START.test(inner.trim()) && NOTE_REF.test(inner);
}

/**
 * Whether the ")" at `index` closes an inciso marker ("incisos b), d) e i)")
 * rather than a parenthesis: one to three letters or digits after a space,
 * comma or the start of the text.
 */
function markerClose(text: string, index: number): boolean {
  const run = /(?:^|[\s,;])[a-zñ0-9]{1,3}$/i.exec(text.slice(0, index));
  return run !== null;
}

/** Index of the "(" matching the ")" at `close`, skipping inciso markers, or -1. */
function opening(text: string, close: number): number {
  let depth = 0;
  for (let i = close; i >= 0; i--) {
    if (text[i] === ")" && !markerClose(text, i)) depth++;
    else if (text[i] === "(" && --depth === 0) return i;
  }
  return -1;
}

/** Whether a paragraph ends a parenthesis: ")" or ")." at its end. */
const closesParen = (text: string) => /\)\.?$/.test(text);

/**
 * Split trailing notes off a paragraph: "c) … del registro. (Inciso
 * sustituido por art. 72 de la Ley N° 27.444 B.O. 18/6/2018)".
 */
export function splitTrailingNotes(text: string): {
  body: string;
  notes: string[];
} {
  const notes: string[] = [];
  let body = text.trim();
  for (;;) {
    const end = body.endsWith(").") ? body.length - 2 : body.length - 1;
    if (body[end] !== ")") break;
    const open = opening(body, end);
    if (open < 0 || !isNote(body.slice(open + 1, end))) break;
    notes.unshift(body.slice(open).trim());
    body = body.slice(0, open).trim();
  }
  return { body, notes };
}

const LABEL = /^(T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\s+\S+/i;
const ROMAN = /^[IVXL]+\.?$/;
const LEVELS: Record<string, number> = {
  titulo: 1,
  capitulo: 2,
  seccion: 3,
};
const fold = (text: string) =>
  text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

export interface ParsedArticle {
  section_number: string;
  base: number;
  suffix: string | null;
  /** Título / Capítulo / Sección headings in effect, outermost first. */
  title: string | null;
  /** Article paragraphs, one per line. */
  body: string[];
  /** Infoleg's amendment notes for the article, in page order. */
  notes: string[];
}

/** The row text: the article's paragraphs, then a blank line and its notes. */
export function articleText(article: ParsedArticle): string {
  const body = article.body.join("\n");
  const notes = article.notes.join("\n");
  return body && notes ? `${body}\n\n${notes}` : body || notes;
}

/** Split one statute's page paragraphs into articles. */
export function parseStatute(
  source: Pick<StatuteSource, "statute" | "start" | "stop" | "last_article">,
  paragraphs: Paragraph[],
): ParsedArticle[] {
  const articles: ParsedArticle[] = [];
  let index = 0;
  if (source.start) {
    const start = paragraphs.findIndex((p) => source.start?.test(p.text));
    if (start < 0) throw new Error(`${source.statute}: start not found.`);
    index = start + 1;
  }
  // Heading stack by level; a label heading takes the following line as its name.
  let headings: { level: number; text: string }[] = [];
  let awaitingName = false;
  let headingSinceContent = false;
  let pendingNotes: string[] = [];
  let current: ParsedArticle | null = null;
  let stopped = false;
  const titleNow = () =>
    headings.length ? headings.map((h) => h.text).join(" / ") : null;
  const addNote = (note: string) => {
    if (!current || headingSinceContent) pendingNotes.push(note);
    else current.notes.push(note);
  };
  const pushHeading = (level: number, text: string) => {
    headings = headings.filter((h) => h.level < level);
    headings.push({ level, text });
    headingSinceContent = true;
  };

  for (; index < paragraphs.length; index++) {
    const paragraph = paragraphs[index] as Paragraph;
    const text = paragraph.text;
    if (source.stop.test(text) || /^Antecedentes Normativos$/i.test(text)) {
      stopped = true;
      break;
    }
    // Whole-paragraph notes, possibly continuing over a few paragraphs.
    if (text.startsWith("(") && isNote(text.slice(1))) {
      let note = text;
      for (
        let more = 0;
        !closesParen(note) &&
        more < 3 &&
        index + 1 < paragraphs.length &&
        !articleStart((paragraphs[index + 1] as Paragraph).text);
        more++
      )
        note += ` ${(paragraphs[++index] as Paragraph).text}`;
      if (closesParen(note)) {
        addNote(note);
        continue;
      }
      throw new Error(
        `${source.statute}: unterminated note '${text.slice(0, 60)}'.`,
      );
    }
    const start = articleStart(text);
    if (start) {
      const previous = articles.at(-1);
      const suffixIndex = start.suffix ? SUFFIXES.indexOf(start.suffix) : -1;
      const follows = previous
        ? start.base === previous.base
          ? start.suffix !== null &&
            suffixIndex >
              (previous.suffix ? SUFFIXES.indexOf(previous.suffix) : -1)
          : start.base > previous.base &&
            start.base <= previous.base + 3 &&
            start.suffix === null
        : start.base === 1 && start.suffix === null;
      if (follows) {
        current = {
          section_number: start.suffix
            ? `${start.base} ${start.suffix}`
            : String(start.base),
          base: start.base,
          suffix: start.suffix,
          title: titleNow(),
          body: [],
          notes: pendingNotes,
        };
        pendingNotes = [];
        articles.push(current);
        headingSinceContent = false;
        awaitingName = false;
        const split = splitTrailingNotes(start.rest);
        if (
          split.body.startsWith("(") &&
          closesParen(split.body) &&
          isNote(split.body.slice(1))
        ) {
          split.notes.unshift(split.body);
          split.body = "";
        }
        if (split.body) current.body.push(split.body);
        current.notes.push(...split.notes);
        continue;
      }
    }
    // Headings.
    const label = LABEL.exec(text);
    const isShortName =
      text.length <= 200 && !/[.;:,]$/.test(text) && !articleStart(text);
    if (label?.[1] && text.length <= 200) {
      pushHeading(LEVELS[fold(label[1])] ?? 2, text);
      awaitingName = !/[.—–-]\s*\S/.test(text.slice(label[0].length));
      continue;
    }
    if (ROMAN.test(text)) {
      pushHeading(2, text);
      awaitingName = true;
      continue;
    }
    if (awaitingName && (paragraph.centered || isShortName)) {
      const last = headings.at(-1);
      if (last) last.text = `${last.text} — ${text}`;
      awaitingName = false;
      continue;
    }
    awaitingName = false;
    if (paragraph.centered && isShortName) {
      // An unlabeled heading (Ley 11.723's "DE LA EDICION") ranks as a chapter.
      if (current) pushHeading(2, text);
      continue;
    }
    if (!current) continue; // preamble, considerandos
    const split = splitTrailingNotes(text);
    if (split.body) current.body.push(split.body);
    // A note moved off an inciso keeps the inciso's marker: "d) (Inciso sustituido …)".
    const marker = /^(?:[a-zñ]|\d{1,2}|[IVX]{1,4})(?:\)|\.-|\.)(?=\s)/.exec(
      split.body,
    )?.[0];
    current.notes.push(
      ...split.notes.map((note) => (marker ? `${marker} ${note}` : note)),
    );
    headingSinceContent = false;
  }
  if (!stopped) throw new Error(`${source.statute}: end of statute not found.`);
  const bases = [...new Set(articles.map((a) => a.base))];
  if (
    bases.length !== source.last_article ||
    bases.some((base, i) => base !== i + 1)
  )
    throw new Error(
      `${source.statute}: articles run ${bases.join(",")}, not 1-${source.last_article}.`,
    );
  for (const article of articles)
    if (!articleText(article))
      throw new Error(
        `${source.statute}: article ${article.section_number} is empty.`,
      );
  return articles;
}

/** "Artículo 4°", "Artículo 5° bis", "Artículo 36 quáter", "Artículo 105". */
export function articleLabel(base: number, suffix: string | null) {
  return `Artículo ${base}${base < 10 ? "°" : ""}${suffix ? ` ${suffix}` : ""}`;
}

/** Words for the coverage comparison, lowercased with accents folded; numbers count. */
export function words(text: string): string[] {
  // "1º" (ordinal indicator, a letter) and "1°" (degree sign) are the same word.
  return fold(text.replace(/[ºª°]/g, "")).match(/[\p{L}\p{N}]+/gu) ?? [];
}

/** Share of the page's words that appear in the rows (multiset). */
export function wordCoverage(pageText: string, rowText: string): number {
  const counts = new Map<string, number>();
  for (const word of words(rowText))
    counts.set(word, (counts.get(word) ?? 0) + 1);
  const page = words(pageText);
  let kept = 0;
  for (const word of page) {
    const left = counts.get(word) ?? 0;
    if (left > 0) {
      kept++;
      counts.set(word, left - 1);
    }
  }
  return page.length ? kept / page.length : 1;
}

const MONTHS = /(\d{1,2})\/(\d{1,2})\/(\d{2,4})/;
/** The newest Boletín Oficial date cited in the notes ("B.O. 3/09/2025"), as YYYY-MM-DD. */
export function newestNoteDate(notes: string[]): string | null {
  let best: string | null = null;
  for (const note of notes)
    for (const match of note.matchAll(
      /B\.\s?O\.\s*(\d{1,2}\/\d{1,2}\/\d{2,4})/g,
    )) {
      const parts = MONTHS.exec(match[1] as string);
      if (!parts) continue;
      let year = Number(parts[3]);
      if (year < 100) year += year > 30 ? 1900 : 2000;
      const iso = `${year}-${String(parts[2]).padStart(2, "0")}-${String(parts[1]).padStart(2, "0")}`;
      if (!best || iso > best) best = iso;
    }
  return best;
}

// ---------------------------------------------------------------- sources

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

/** What the Infoleg norm page says about the norm. */
export interface NormPage {
  /** The page's norm description as plain text. */
  text: string;
  /** Type and number as Infoleg heads the page, e.g. 'Ley 22362'. */
  heading: string;
  /** The norm's date as Infoleg gives it, e.g. '22-dic-1980'. */
  date: string | null;
  /** 'Publicada en el Boletín Oficial del 02-ene-1981'. */
  published: string | null;
  summary: string | null;
  /** Relative links as the page gives them. */
  norma_href: string | null;
  texact_href: string | null;
}

/** Read an Infoleg verNorma.do page. */
export function parseNormPage(html: string): NormPage {
  const document = parseDocument(html);
  const box = document.querySelector("#Textos_Completos") ?? document.body;
  const text = clean(box?.textContent ?? "");
  const strong = clean(box?.querySelector("strong")?.textContent ?? "");
  const href = (label: RegExp) => {
    for (const a of box?.querySelectorAll("a") ?? [])
      if (label.test(a.textContent ?? "")) return a.getAttribute("href");
    return null;
  };
  const published =
    /Publicada en el Bolet[íi]n Oficial del\s+\d{1,2}-[a-z]{3}-\d{4}/.exec(
      text,
    );
  const summary =
    /Resumen:\s*(.+?)(?:\s+Observaciones:|\s+Texto completo|\s+Esta norma|$)/.exec(
      text,
    );
  const issued = /\d{2}-[a-z]{3}-\d{4}/.exec(text);
  return {
    text,
    heading: /^\D*?\d[\d/.]*/.exec(strong)?.[0] ?? strong,
    date: issued?.[0] ?? null,
    published: published?.[0] ?? null,
    summary: summary?.[1]?.trim() ?? null,
    norma_href: href(/Texto completo de la norma/),
    texact_href: href(/Texto actualizado de la norma/),
  };
}

export interface SourceStatute {
  statute: string;
  short_name: string;
  title: string;
  infoleg_id: string;
  norm_url: string;
  norm_heading: string;
  norm_date: string | null;
  norm_published: string | null;
  norm_summary: string | null;
  /** 'texact' (Infoleg's updated text) or 'norma' (the text as published). */
  text_kind: "texact" | "norma";
  text_url: string;
  /** The text as published, listed for reference (only text_url is parsed). */
  norma_url: string | null;
  charset: string | null;
  retrieved_at: string;
  text_sha256: string;
  text_bytes: number;
  norm_page_sha256: string;
  section_count: number;
  note_count: number;
  /** The newest Boletín Oficial date the article notes cite. */
  newest_note_date: string | null;
  /** Share of the statute's words (Article 1 to the signatures) kept in the rows, to 3 decimals. */
  word_coverage: number;
  /** The same share of the whole page (preamble, annexes and Infoleg's history list included). */
  page_word_coverage: number;
}
interface SourceManifest {
  source: string;
  user_agent: string;
  retrieved_at: string;
  statutes: SourceStatute[];
}

const normUrl = (id: string) =>
  `${INFOLEG_ORIGIN}/infolegInternet/verNorma.do?id=${id}`;
const rawText = (raw: string, id: string, kind: string) =>
  join(raw, `${id}-${kind}.htm`);

async function get(url: string) {
  // Infoleg's load balancer alternates between two nodes. On October 26,
  // 2026 one of them (IDNODO=.cluster2) answered 200 with an empty body for
  // the Ley 22.362 page while the other served it in full, so an empty or
  // non-HTML reply is retried a few times with the same plain request.
  for (let attempt = 1; ; attempt++) {
    const response = await fetch(url, {
      headers: {
        "user-agent": USER_AGENT,
        accept: "text/html",
        "accept-encoding": "identity",
      },
    });
    if (!response.ok)
      throw new Error(`GET ${url} returned ${response.status}.`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.byteLength >= 1024 && /<html/i.test(decodeInfoleg(bytes)))
      return bytes;
    if (attempt >= 5)
      throw new Error(
        `GET ${url} returned ${bytes.byteLength} bytes, not a page, ${attempt} times.`,
      );
    console.error(`${url}: empty reply, retrying.`);
    await Bun.sleep(2000);
  }
}

/**
 * The paragraphs of the statute itself: from the paragraph opening Article 1
 * (after `start`) to the one before `stop`, for the word comparison.
 */
export function statuteRegion(
  source: Pick<StatuteSource, "start" | "stop">,
  paragraphs: Paragraph[],
): Paragraph[] {
  const from = source.start
    ? paragraphs.findIndex((p) => source.start?.test(p.text)) + 1
    : 0;
  const first = paragraphs.findIndex(
    (p, i) => i >= from && articleStart(p.text)?.base === 1,
  );
  const stop = paragraphs.findIndex(
    (p, i) =>
      i > first &&
      (source.stop.test(p.text) || /^Antecedentes Normativos$/i.test(p.text)),
  );
  return paragraphs.slice(first, stop);
}

const ratio = (value: number) => Math.round(value * 1000) / 1000;

/** Parse one archived text page into articles plus the stats the manifest records. */
export function parseSource(source: StatuteSource, bytes: Uint8Array) {
  const html = decodeInfoleg(bytes);
  const paragraphs = pageParagraphs(html);
  const articles = parseStatute(source, paragraphs);
  const rows = articles
    .map(
      (article) =>
        `${articleLabel(article.base, article.suffix)}\n${article.title ?? ""}\n${articleText(article)}`,
    )
    .join("\n");
  const notes = articles.flatMap((article) => article.notes);
  const text = (list: Paragraph[]) => list.map((p) => p.text).join("\n");
  return {
    articles,
    note_count: notes.length,
    newest_note_date: newestNoteDate(notes),
    word_coverage: ratio(
      wordCoverage(text(statuteRegion(source, paragraphs)), rows),
    ),
    page_word_coverage: ratio(wordCoverage(text(paragraphs), rows)),
  };
}

async function fetchAll(raw: string) {
  await mkdir(raw, { recursive: true });
  const statutes: SourceStatute[] = [];
  for (const source of SOURCES) {
    const pageUrl = normUrl(source.infoleg_id);
    const pageBytes = await get(pageUrl);
    const pageHtml = decodeInfoleg(pageBytes);
    const norm = parseNormPage(pageHtml);
    if (!source.expect.test(norm.text))
      throw new Error(
        `${source.statute}: Infoleg ${source.infoleg_id} is '${norm.heading}', not the expected norm.`,
      );
    const kind = norm.texact_href ? "texact" : "norma";
    const href = norm.texact_href ?? norm.norma_href;
    if (!href)
      throw new Error(`${source.statute}: no text link on ${pageUrl}.`);
    const base = `${INFOLEG_ORIGIN}/infolegInternet/`;
    const textUrl = new URL(href, base).href;
    const bytes = await get(textUrl);
    const retrieved = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    const parsed = parseSource(source, bytes);
    await writeFile(join(raw, `${source.infoleg_id}-verNorma.html`), pageBytes);
    await writeFile(rawText(raw, source.infoleg_id, kind), bytes);
    statutes.push({
      statute: source.statute,
      short_name: source.short_name,
      title: source.title,
      infoleg_id: source.infoleg_id,
      norm_url: pageUrl,
      norm_heading: norm.heading,
      norm_date: norm.date,
      norm_published: norm.published,
      norm_summary: norm.summary,
      text_kind: kind,
      text_url: textUrl,
      norma_url: norm.norma_href ? new URL(norm.norma_href, base).href : null,
      charset: declaredCharset(bytes),
      retrieved_at: retrieved,
      text_sha256: sha256(bytes),
      text_bytes: bytes.byteLength,
      norm_page_sha256: sha256(pageBytes),
      section_count: parsed.articles.length,
      note_count: parsed.note_count,
      newest_note_date: parsed.newest_note_date,
      word_coverage: parsed.word_coverage,
      page_word_coverage: parsed.page_word_coverage,
    });
    console.error(
      `${source.statute}: ${parsed.articles.length} articles from ${kind}, ${bytes.byteLength} bytes`,
    );
  }
  const manifest: SourceManifest = {
    source:
      "Infoleg (https://servicios.infoleg.gob.ar/), Ministerio de Justicia de la Nación: updated text (texact.htm) where Infoleg keeps one, else the text as published (norma.htm)",
    user_agent: USER_AGENT,
    retrieved_at: statutes.map((item) => item.retrieved_at).sort()[0] as string,
    statutes,
  };
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}

interface ParsedSource {
  source: StatuteSource;
  manifest: SourceStatute;
  articles: ParsedArticle[];
}

/** Parse the archived pages, checking each against the source manifest. */
export async function loadStatutes(raw: string) {
  const manifest = JSON.parse(
    await readFile(manifestPath, "utf8"),
  ) as SourceManifest;
  const parsed: ParsedSource[] = [];
  for (const source of SOURCES) {
    const entry = manifest.statutes.find(
      (item) => item.statute === source.statute,
    );
    if (!entry) throw new Error(`${source.statute} is not in the manifest.`);
    const bytes = new Uint8Array(
      await readFile(rawText(raw, entry.infoleg_id, entry.text_kind)),
    );
    if (sha256(bytes) !== entry.text_sha256)
      throw new Error(
        `${source.statute}: archived page does not match the manifest; run --fetch.`,
      );
    const result = parseSource(source, bytes);
    if (
      result.articles.length !== entry.section_count ||
      result.note_count !== entry.note_count
    )
      throw new Error(
        `${source.statute}: article or note count differs from manifest.`,
      );
    parsed.push({ source, manifest: entry, articles: result.articles });
  }
  return { manifest, parsed };
}

function writeDatabase(
  output: string,
  manifest: SourceManifest,
  statutes: ParsedSource[],
  pick?: Record<string, string[]>,
) {
  const db = new Database(output, { create: true, strict: true });
  try {
    db.exec("PRAGMA journal_mode = DELETE");
    db.exec(DDL);
    const insert = db.prepare(
      "INSERT INTO sections (statute, section_number, section_label, title, text, source_url) VALUES (?, ?, ?, ?, ?, ?)",
    );
    let count = 0;
    const total = statutes.reduce((sum, item) => sum + item.articles.length, 0);
    const date = manifest.retrieved_at.slice(0, 10);
    db.transaction(() => {
      for (const { source, manifest: entry, articles } of statutes)
        for (const article of articles) {
          if (pick && !pick[source.statute]?.includes(article.section_number))
            continue;
          insert.run(
            source.statute,
            article.section_number,
            `${articleLabel(article.base, article.suffix)} ${source.short_name}`,
            article.title,
            articleText(article),
            entry.text_url,
          );
          count++;
        }
      const statuteMeta = statutes.map(({ source, manifest: entry }) => ({
        statute: source.statute,
        short_name: source.short_name,
        title: source.title,
        infoleg_id: entry.infoleg_id,
        norm_url: entry.norm_url,
        norm_heading: entry.norm_heading,
        norm_published: entry.norm_published,
        text_kind: entry.text_kind,
        text_url: entry.text_url,
        text_sha256: entry.text_sha256,
        retrieved_at: entry.retrieved_at,
        newest_note_date: entry.newest_note_date,
        section_count: entry.section_count,
      }));
      const meta: [string, string][] = [
        ["schema_version", "1"],
        ["snapshot_date", date],
        ["source_version", `Infoleg updated texts, ${date}`],
        ["section_count", String(count)],
        ["retrieved_at", manifest.retrieved_at],
        ["language", "es"],
        [
          "notice",
          "Infoleg's updated texts (texto actualizado), not official Boletín Oficial publications; Ley 24.766 is Infoleg's text as published, since Infoleg keeps no updated text for it.",
        ],
        ["statutes", JSON.stringify(statuteMeta)],
      ];
      if (pick) meta.push(["fixture_subset_of", String(total)]);
      const put = db.prepare("INSERT INTO meta (key, value) VALUES (?, ?)");
      for (const [key, value] of meta) put.run(key, value);
    })();
    db.exec("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')");
    db.exec("VACUUM");
    if (pick && count !== Object.values(pick).flat().length)
      throw new Error("A fixture article is missing from the build.");
    const check = db.query("PRAGMA integrity_check").get() as {
      integrity_check: string;
    };
    if (check.integrity_check !== "ok")
      throw new Error("Integrity check failed.");
    return count;
  } finally {
    db.close();
  }
}

async function exists(path: string) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

/** Build into a temporary file and move it into place, never overwriting. */
async function build(
  output: string,
  manifest: SourceManifest,
  statutes: ParsedSource[],
  pick?: Record<string, string[]>,
) {
  await mkdir(dirname(output), { recursive: true });
  const temporary = `${output}.building`;
  await rm(temporary, { force: true });
  try {
    const count = writeDatabase(temporary, manifest, statutes, pick);
    await rename(temporary, output);
    return count;
  } finally {
    await rm(temporary, { force: true });
  }
}

if (import.meta.main) {
  const args = process.argv.slice(2);
  const option = (name: string) => {
    const index = args.indexOf(name);
    return index >= 0 ? args[index + 1] : undefined;
  };
  const raw = resolve(
    option("--raw") ?? join(root, ".data/inpi_ar_statutes/raw"),
  );
  const output = resolve(
    option("--output") ??
      join(root, ".data/inpi_ar_statutes/inpi_ar_statutes.db"),
  );
  if (await exists(output))
    throw new Error(`${output} exists; choose a new --output.`);
  if (args.includes("--fetch")) await fetchAll(raw);
  const { manifest, parsed } = await loadStatutes(raw);
  const count = await build(output, manifest, parsed);
  const bytes = new Uint8Array(await readFile(output));
  console.log(
    JSON.stringify(
      {
        output,
        sections: count,
        bytes: bytes.byteLength,
        sha256: sha256(bytes),
        statutes: parsed.map((item) => ({
          statute: item.source.statute,
          sections: item.articles.length,
          notes: item.manifest.note_count,
          word_coverage: item.manifest.word_coverage,
          numbers: item.articles
            .map((article) => article.section_number)
            .join(","),
        })),
      },
      null,
      2,
    ),
  );
  if (args.includes("--fixture")) {
    await rm(fixturePath, { force: true });
    const fixtureCount = await build(
      fixturePath,
      manifest,
      parsed,
      FIXTURE_ARTICLES,
    );
    const fixtureBytes = new Uint8Array(await readFile(fixturePath));
    console.log(
      JSON.stringify({
        fixture: fixturePath,
        sections: fixtureCount,
        bytes: fixtureBytes.byteLength,
        sha256: sha256(fixtureBytes),
      }),
    );
  }
}

// Builds the Thailand IP statutes SQLite/FTS5 corpus (schema 1, the same
// statute-shaped schema as the ILPO and DPMA corpora) from the English
// translations WIPO Lex publishes for the Patent Act, Trademark Act,
// Copyright Act and Trade Secrets Act. For each act the WIPO Lex detail page
// is fetched, its English PDF link (signed, valid for a few minutes) is
// followed once, and the PDF is archived. Plain HTTPS GETs with an honest
// user agent; no browser, cookies or challenge handling.
//
// The Office of the Council of State (OCS) publishes official English
// translations of Thai acts, but its English list (146 acts on October 26,
// 2026) has none of these four, so WIPO Lex is the source. The PDFs are the
// Department of Intellectual Property's unofficial translations; the Thai
// text published in the Government Gazette controls.
//
// The acts print each section as "Section 12 ..." (the Patent Act's WIPO
// consolidation prints a bare "12. ...") at the paragraph indent, with no
// section headings. Footnotes record amendments. Sections are split by
// position (pdfjs text items): a section starts at its number at the indent,
// footnote marks are small raised numbers, footnotes sit below a mark at the
// left margin, and each footnote a section cites is kept at the end of its
// text as `[Notes: …]`.
//
// Usage (from typescript/):
//   bun scripts/build-thai-dip-statutes-corpus.ts --fetch   # download the four PDFs, rewrite the source manifest, build
//   bun scripts/build-thai-dip-statutes-corpus.ts           # rebuild from the archived PDFs (sha256-checked)
//   bun scripts/build-thai-dip-statutes-corpus.ts --fixture # also rewrite the test fixture subset
// Options: --output PATH (default .data/thai_dip_statutes/thai_dip_statutes.db,
// must not exist), --raw DIR (default .data/thai_dip_statutes/raw).
// The output is a standalone DELETE-journal database, ready for
// scripts/compress-corpus.ts without a preparation step.
import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import {
  type PdfTextItem,
  pdfPageItems,
} from "../packages/client/src/runtime/pdf.js";
import {
  parseWipoLexLegislation,
  WIPO_LEX_ORIGIN,
} from "../packages/client/src/wipo-lex.js";

const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
const root = join(import.meta.dir, "..");
const manifestPath = join(import.meta.dir, "thai-dip-statutes-sources.json");
const fixturePath = join(
  root,
  "tests/fixtures/thai-dip-statutes/thai_dip_statutes.db",
);

/** Page geometry of one act's PDF, in PDF points. */
export interface Layout {
  /** Wrapped lines start here. */
  marginX: number;
  /** Paragraphs, and section numbers, start here. */
  indentX: number;
  /** Body font height; raised footnote marks are well below it. */
  bodySize: number;
  /** "Section 12 ..." or the WIPO consolidation's bare "12. ...". */
  numbers: "section" | "bare";
  /** The act's text ends at the first line matching this, once a section has started. */
  stop: RegExp;
  /** Running heads, page numbers and translation remarks: not statute text. */
  drop: RegExp;
  /** Footnotes are collected at the end of the PDF instead of each page. */
  endnotes?: boolean;
}

export interface StatuteSource {
  statute: string;
  short_name: string;
  title: string;
  wipolex_id: string;
  layout: Layout;
}

const DIP_FOOTER =
  /^(-\s*\d{1,3}\s*-|Remark\s*:\s*This is an unofficial translation\b.*|Thailand for the informational and comprehensive purposes\b.*|refer to the official Act, in Thai version\b.*)$/;

/** The four acts, their WIPO Lex entries and the layout of each English PDF. */
export const SOURCES: StatuteSource[] = [
  {
    statute: "patent",
    short_name: "Patent Act",
    title: "Patent Act B.E. 2522 (1979)",
    wipolex_id: "3807",
    layout: {
      marginX: 70.9,
      indentX: 99.2,
      bodySize: 12,
      numbers: "bare",
      stop: /^List of the maximum Fees$/,
      drop: /^(YH\b.*|THAILAND|TH007EN\b.*|Baht)$/,
      endnotes: true,
    },
  },
  {
    statute: "trademark",
    short_name: "Trademark Act",
    title: "Trademark Act B.E. 2534 (1991)",
    wipolex_id: "17164",
    layout: {
      marginX: 72,
      indentX: 142.9,
      bodySize: 14,
      numbers: "section",
      stop: /^(Official Fees|Countersigned by)\b/,
      drop: DIP_FOOTER,
    },
  },
  {
    statute: "copyright",
    short_name: "Copyright Act",
    title: "Copyright Act B.E. 2537 (1994)",
    wipolex_id: "23909",
    layout: {
      marginX: 72,
      indentX: 144,
      bodySize: 12,
      numbers: "section",
      stop: /^Countersigned by\b/,
      drop: DIP_FOOTER,
    },
  },
  {
    statute: "trade_secrets",
    short_name: "Trade Secrets Act",
    title: "Trade Secrets Act B.E. 2545 (2002)",
    wipolex_id: "17163",
    layout: {
      marginX: 72,
      indentX: 142.9,
      bodySize: 12,
      numbers: "section",
      stop: /^Countersigned by\b/,
      drop: DIP_FOOTER,
    },
  },
];

/** Sections copied into the committed test fixture. */
const FIXTURE_SECTIONS: Record<string, string[]> = {
  patent: ["3", "5", "36", "36bis", "65bis"],
  trademark: ["4", "6", "28bis", "109/1"],
  copyright: ["4", "15", "32", "32/1"],
  trade_secrets: ["3", "6", "7"],
};

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
    content='sections', content_rowid='rowid', tokenize='porter unicode61'
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

// ---------------------------------------------------------------- numbering

/**
 * Latin insertion suffixes in statutory order. The sources also print
 * "quarter" for "quater" and "novies" for "nonies".
 */
export const LATIN_SUFFIXES = [
  "bis",
  "ter",
  "quater",
  "quinquies",
  "sexies",
  "septies",
  "octies",
  "nonies",
  "decies",
  "undecies",
  "duodecies",
] as const;
const SUFFIX = `(?:${LATIN_SUFFIXES.join("|")}|quarter|novies)`;

/**
 * Canonical section number: "36bis", "28/1", "106quater". Spaces before a
 * suffix are dropped; "quarter" reads as "quater" and "novies" as "nonies".
 */
export function canonicalNumber(value: string): string {
  return value
    .toLowerCase()
    .replace(/\s+/g, "")
    .replace(/quarter$/, "quater")
    .replace(/novies$/, "nonies");
}

/** Sort key: base number, then Latin suffix rank, then the "/n" insertion. */
export function numberKey(value: string): [number, number, number] {
  const match = /^(\d+)([a-z]*)(?:\/(\d+))?$/.exec(canonicalNumber(value));
  if (!match) return [Number.NaN, 0, 0];
  const suffix = match[2]
    ? (LATIN_SUFFIXES as readonly string[]).indexOf(match[2]) + 1
    : 0;
  return [Number(match[1]), suffix, Number(match[3] ?? 0)];
}

export function compareNumbers(a: string, b: string): number {
  const [x, y] = [numberKey(a), numberKey(b)];
  return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
}

/** A section number that can follow `previous` in the act (guards against stray numerals). */
export function follows(previous: string | null, next: string): boolean {
  const key = numberKey(next);
  if (Number.isNaN(key[0]) || key[1] < 0) return false;
  if (previous === null) return key[0] <= 3;
  const gap = key[0] - numberKey(previous)[0];
  return compareNumbers(next, previous) > 0 && gap <= 12;
}

const SECTION_START = new RegExp(
  String.raw`^Section\s+(\d{1,3}(?:\s?${SUFFIX})?(?:\s?\/\s?\d{1,2})?)\s*\.?(?=\s|$|[A-Z(“"])\s*(.*)$`,
);
const BARE_START = new RegExp(
  String.raw`^(\d{1,3}(?:\s?${SUFFIX})?)\s*\.\s+(.*)$`,
);

// ---------------------------------------------------------------- layout

export interface Line {
  page: number;
  y: number;
  /** x of the first item. */
  x: number;
  /** Centred between the margins, as chapter and part headings are. */
  centred: boolean;
  text: string;
  /** Footnote marks raised on this line. */
  marks: string[];
}

export interface PageText {
  lines: Line[];
  /** Footnotes on this page by mark, in order. */
  notes: { mark: string; text: string }[];
  /** Every line with raised marks kept, for endnotes. */
  raw: string[];
}

/** Join a line's items left to right, adding a space only where the PDF leaves a gap. */
export function joinItems(items: PdfTextItem[]): string {
  let out = "";
  let end = 0;
  for (const item of [...items].sort((a, b) => a.x - b.x)) {
    if (out) {
      const spaced = /\s$/.test(out) || /^\s/.test(item.str);
      if (!spaced && item.x - end > Math.max(1, item.height * 0.15)) out += " ";
    }
    out += item.str;
    end = item.x + item.width;
  }
  return out.replace(/\s+/g, " ").trim();
}

const isOrdinal = (value: string) => /^(st|nd|rd|th)$/.test(value.trim());
const MARK = /^(\(\d{1,3}\)|\d{1,3}|\*)$/;

function groupLines(items: PdfTextItem[], page: number) {
  const lines: { page: number; y: number; items: PdfTextItem[] }[] = [];
  for (const item of [...items].sort((a, b) => b.y - a.y || a.x - b.x)) {
    const tolerance = Math.max(2, item.height * 0.4);
    const line = lines.find((entry) => Math.abs(entry.y - item.y) <= tolerance);
    if (line) line.items.push(item);
    else lines.push({ page, y: item.y, items: [item] });
  }
  return lines.sort((a, b) => b.y - a.y);
}

/**
 * One page's statute lines, top to bottom, and its footnotes. Raised
 * footnote marks are taken out of the text and recorded on their line;
 * ordinal superscripts ("28th") stay. A footnote starts at a small mark at
 * the left margin; everything below the first one is footnote text.
 */
export function pageText(
  items: PdfTextItem[],
  page: number,
  layout: Layout,
): PageText {
  const visible = items.filter((item) => item.str.trim());
  const small = (item: PdfTextItem) =>
    item.height > 0 && item.height <= layout.bodySize * 0.8;
  const atMargin = (item: PdfTextItem) => item.x <= layout.marginX + 4;
  let footnoteTop = Number.NEGATIVE_INFINITY;
  if (!layout.endnotes)
    for (const mark of visible) {
      const value = mark.str.trim();
      const starts =
        atMargin(mark) &&
        ((small(mark) && MARK.test(value)) ||
          (/^\*\s*\S/.test(value) && mark.height < layout.bodySize * 0.95));
      if (starts) footnoteTop = Math.max(footnoteTop, mark.y + 1);
    }
  const body = visible.filter((item) => item.y > footnoteTop);
  const lines: Line[] = [];
  const raised: PdfTextItem[] = [];
  const grouped = groupLines(
    body.filter((item) => !small(item) || isOrdinal(item.str)),
    page,
  );
  for (const item of body)
    if (small(item) && !isOrdinal(item.str)) raised.push(item);
  const right = Math.max(
    ...grouped.flatMap((line) => line.items.map((item) => item.x + item.width)),
  );
  const centre = (layout.marginX + right) / 2;
  for (const line of grouped) {
    const text = joinItems(line.items);
    const edge = line.y < 100 || line.y > 740;
    if (layout.drop.test(text) || (edge && /^\d{1,3}$/.test(text))) continue;
    const x = Math.min(...line.items.map((item) => item.x));
    const end = Math.max(...line.items.map((item) => item.x + item.width));
    lines.push({
      page,
      y: line.y,
      x,
      centred:
        x > layout.marginX + 15 &&
        Math.abs(x - layout.indentX) > 8 &&
        Math.abs((x + end) / 2 - centre) <= 12 &&
        !/[.;:,]$/.test(text),
      text,
      marks: [],
    });
  }
  // A raised mark belongs to the line just below its baseline.
  for (const mark of raised) {
    const value = mark.str.trim().replace(/[()]/g, "");
    if (!/^\d{1,3}$/.test(value)) continue;
    const line = lines.find(
      (entry) => mark.y - entry.y >= -1 && mark.y - entry.y <= 8,
    );
    line?.marks.push(value);
  }
  const notes: { mark: string; text: string }[] = [];
  const footLines = groupLines(
    visible.filter((item) => item.y <= footnoteTop),
    page,
  );
  // A mark sits a little above its footnote's first line.
  let pending: string | null = null;
  for (const line of footLines) {
    const sorted = [...line.items].sort((a, b) => a.x - b.x);
    const first = sorted[0];
    let mark: string | null = pending;
    pending = null;
    let rest = sorted;
    if (first && small(first) && MARK.test(first.str.trim())) {
      mark = first.str.trim();
      rest = sorted.slice(1);
      if (!rest.length) {
        pending = mark;
        continue;
      }
    } else if (first && /^\*\s*\S/.test(first.str.trim())) {
      mark = "*";
      rest = [{ ...first, str: first.str.trim().slice(1) }, ...sorted.slice(1)];
    }
    const text = joinItems(rest);
    if (!text || layout.drop.test(text)) continue;
    if (mark !== null) notes.push({ mark, text });
    else {
      const last = notes.at(-1);
      if (last) last.text = `${last.text} ${text}`;
    }
  }
  const raw = layout.endnotes
    ? groupLines(visible, page)
        .map((line) => joinItems(line.items))
        .filter((text) => !layout.drop.test(text))
    : [];
  return { lines, notes, raw };
}

/**
 * The WIPO consolidation's endnotes: a line of raised marks ("(2) (6) (7)
 * (9) (12)") over a line holding the separators between them and the note
 * (", , , to : as revised by …"). Separator i sits between marks i and i+1,
 * so "to" makes a range.
 */
export function parseEndnotes(lines: string[]): Map<string, string> {
  const notes = new Map<string, string>();
  for (let index = 0; index < lines.length - 1; index++) {
    const markLine = lines[index] as string;
    if (!/^(\(\d{1,3}\)\s*)+$/.test(markLine)) continue;
    const text = lines[index + 1] as string;
    index++;
    const marks = [...markLine.matchAll(/\((\d{1,3})\)/g)].map((match) =>
      Number(match[1]),
    );
    const colon = text.indexOf(":");
    const note = (colon >= 0 ? text.slice(colon + 1) : text).trim();
    // "(4), & (32)": a serial comma before "&" is one separator.
    const separators =
      colon >= 0
        ? (text
            .slice(0, colon)
            .replace(/,\s*&/g, "&")
            .match(/,|&|\bto\b/g) ?? [])
        : [];
    if (!note || (marks.length > 1 && separators.length !== marks.length - 1))
      continue;
    marks.forEach((mark, position) => {
      notes.set(String(mark), note);
      const next = marks[position + 1];
      if (separators[position] === "to" && next !== undefined)
        for (let n = mark + 1; n < next; n++) notes.set(String(n), note);
    });
  }
  return notes;
}

// ---------------------------------------------------------------- sections

export interface ParsedSection {
  section_number: string;
  title: string | null;
  text: string;
}

/** Body lines reflowed into paragraphs: a line at the indent starts one. */
export function paragraphs(
  lines: { x: number; text: string }[],
  layout: Layout,
) {
  const out: string[] = [];
  for (const line of lines) {
    const previous = out.at(-1);
    if (previous === undefined || line.x >= layout.indentX - 6) {
      out.push(line.text);
      continue;
    }
    out[out.length - 1] = /\S-$/.test(previous)
      ? `${previous}${line.text}`
      : `${previous} ${line.text}`;
  }
  return out.map((paragraph) =>
    paragraph
      .replace(/\s+([,;:.)\]])/g, "$1")
      .replace(/([([])\s+/g, "$1")
      .replace(/\s+/g, " ")
      .trim(),
  );
}

interface Draft {
  number: string;
  lines: { x: number; text: string }[];
  marks: string[];
}

/** Every numbered section of one act, in order. */
export function parseStatute(
  source: StatuteSource,
  pages: PdfTextItem[][],
): ParsedSection[] {
  const { layout } = source;
  const drafts: Draft[] = [];
  const notes = new Map<string, string>();
  const endLines: string[] = [];
  let stopped = false;
  for (let index = 0; index < pages.length; index++) {
    const page = pageText(pages[index] ?? [], index + 1, layout);
    for (const note of page.notes)
      if (!notes.has(note.mark)) notes.set(note.mark, note.text);
    if (stopped) endLines.push(...page.raw);
    for (const line of page.lines) {
      if (stopped) break;
      if (drafts.length && layout.stop.test(line.text)) {
        stopped = true;
        endLines.push(...page.raw);
        break;
      }
      const atIndent = Math.abs(line.x - layout.indentX) <= 10;
      const pattern = layout.numbers === "section" ? SECTION_START : BARE_START;
      const match = atIndent ? pattern.exec(line.text) : null;
      const candidate = match?.[1] ? canonicalNumber(match[1]) : null;
      if (candidate && follows(drafts.at(-1)?.number ?? null, candidate)) {
        drafts.push({
          number: candidate,
          lines: match?.[2] ? [{ x: line.x, text: match[2] }] : [],
          marks: [...line.marks],
        });
        continue;
      }
      const current = drafts.at(-1);
      if (!current) continue;
      // Chapter, part and transitional headings are centred, well right of the indent.
      if (line.x > layout.indentX + 40 || line.centred) continue;
      current.lines.push({ x: line.x, text: line.text });
      current.marks.push(...line.marks);
    }
  }
  if (layout.endnotes)
    for (const [mark, text] of parseEndnotes(endLines)) notes.set(mark, text);
  const seen = new Set<string>();
  return drafts.map((draft) => {
    if (seen.has(draft.number))
      throw new Error(`${source.statute}: duplicate section ${draft.number}.`);
    seen.add(draft.number);
    const body = paragraphs(draft.lines, layout);
    const cited = [...new Set(draft.marks)]
      .map((mark) => notes.get(mark))
      .filter((text): text is string => Boolean(text));
    if (cited.length)
      body.push(
        `[Notes: ${[...new Set(cited)].join("; ").replace(/\s+/g, " ")}]`,
      );
    return {
      section_number: draft.number,
      title: null,
      text: body.join("\n"),
    };
  });
}

// ---------------------------------------------------------------- sources

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

interface SourceStatute {
  statute: string;
  short_name: string;
  title: string;
  wipolex_id: string;
  details_url: string;
  /** WIPO Lex's own title and description (year of version, dates, type). */
  wipo_title: string;
  wipo_summary: string | null;
  /** The amendments the translation's own title page lists. */
  version_note: string;
  /** The English PDF, without the signature query WIPO adds. */
  pdf_url: string;
  /** WIPO's last-modified stamp for the PDF, from the signed link. */
  pdf_last_modified: string | null;
  retrieved_at: string;
  pdf_sha256: string;
  pdf_bytes: number;
  pages: number;
  section_count: number;
}
interface SourceManifest {
  source: string;
  user_agent: string;
  retrieved_at: string;
  /** Sources looked at and not used, with the reason. */
  not_used: { source: string; url: string; reason: string }[];
  statutes: SourceStatute[];
}

/** The translation's title page: the act and the amendments it lists. */
const VERSION_NOTES: Record<string, string> = {
  patent:
    "As amended by the Patent Act (No. 2) B.E. 2535 (1992) and the Patent Act (No. 3) B.E. 2542 (1999); English consolidation prepared for WIPO Lex (TH007EN), which names no translator",
  trademark:
    "As amended by the Trademark Act (No. 2) B.E. 2543 (2000) and the Trademark Act (No. 3) B.E. 2559 (2016); unofficial translation by the Department of Intellectual Property",
  copyright:
    "As amended by the Copyright Act (No. 2) B.E. 2558 (2015), (No. 3) B.E. 2558 (2015), (No. 4) B.E. 2561 (2018) and (No. 5) B.E. 2565 (2022); unofficial translation by the Department of Intellectual Property",
  trade_secrets:
    "As amended by the Trade Secrets Act (No. 2) B.E. 2558 (2015); unofficial translation by the Department of Intellectual Property",
};

const detailsUrl = (id: string) =>
  `${WIPO_LEX_ORIGIN}/wipolex/en/legislation/details/${id}`;
const rawPath = (raw: string, pdfUrl: string) =>
  join(raw, pdfUrl.split("/").at(-1) as string);

async function get(url: string, accept: string) {
  const response = await fetch(url, {
    headers: { "user-agent": USER_AGENT, accept },
  });
  if (!response.ok) throw new Error(`GET ${url} returned ${response.status}.`);
  return response;
}

async function fetchAll(raw: string) {
  await mkdir(raw, { recursive: true });
  const statutes: SourceStatute[] = [];
  for (const source of SOURCES) {
    const page = detailsUrl(source.wipolex_id);
    const html = await (await get(page, "text/html")).text();
    const legislation = parseWipoLexLegislation(html, source.wipolex_id);
    // The first English PDF is the translation; "-wto" files are TRIPS notifications.
    const file = legislation.files.find(
      (link) =>
        link.mime_type === "application/pdf" &&
        new URL(link.url).pathname.includes("/laws/en/") &&
        !new URL(link.url).pathname.includes("-wto"),
    );
    if (!file) throw new Error(`${source.statute}: no English PDF on ${page}.`);
    const bytes = new Uint8Array(
      await (await get(file.url, "application/pdf")).arrayBuffer(),
    );
    if (new TextDecoder().decode(bytes.slice(0, 5)) !== "%PDF-")
      throw new Error(`${source.statute}: ${file.url} is not a PDF.`);
    const retrieved = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    const url = new URL(file.url);
    const modified = Number(url.searchParams.get("last-modified"));
    const pdfUrl = `${url.origin}${url.pathname}`;
    const pages = await pdfPageItems(bytes);
    const sections = parseStatute(source, pages);
    await writeFile(rawPath(raw, pdfUrl), bytes);
    statutes.push({
      statute: source.statute,
      short_name: source.short_name,
      title: source.title,
      wipolex_id: source.wipolex_id,
      details_url: page,
      wipo_title: legislation.title,
      wipo_summary: legislation.summary,
      version_note: VERSION_NOTES[source.statute] as string,
      pdf_url: pdfUrl,
      pdf_last_modified:
        Number.isSafeInteger(modified) && modified > 0
          ? new Date(modified * 1000).toISOString().replace(/\.\d+Z$/, "Z")
          : null,
      retrieved_at: retrieved,
      pdf_sha256: sha256(bytes),
      pdf_bytes: bytes.byteLength,
      pages: pages.length,
      section_count: sections.length,
    });
    console.error(
      `${source.statute}: ${sections.length} sections, ${pages.length} pages, ${bytes.byteLength} bytes`,
    );
  }
  const manifest: SourceManifest = {
    source:
      "WIPO Lex (https://www.wipo.int/wipolex/) English translations, one PDF per act",
    user_agent: USER_AGENT,
    retrieved_at: statutes.map((item) => item.retrieved_at).sort()[0] as string,
    not_used: [
      {
        source: "Office of the Council of State, English translations",
        url: "https://www.ocs.go.th/searchlaw-law-eng",
        reason:
          "Reachable with plain requests, but its English list (146 acts on 2026-10-26) has no Patent, Trademark, Copyright or Trade Secrets Act translation.",
      },
    ],
    statutes,
  };
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}

interface ParsedStatute {
  source: StatuteSource;
  manifest: SourceStatute;
  sections: ParsedSection[];
}

/** Parse the archived PDFs, checking each against the source manifest. */
export async function loadStatutes(raw: string) {
  const manifest = JSON.parse(
    await readFile(manifestPath, "utf8"),
  ) as SourceManifest;
  const parsed: ParsedStatute[] = [];
  for (const source of SOURCES) {
    const entry = manifest.statutes.find(
      (item) => item.statute === source.statute,
    );
    if (!entry) throw new Error(`${source.statute} is not in the manifest.`);
    const bytes = new Uint8Array(await readFile(rawPath(raw, entry.pdf_url)));
    if (sha256(bytes) !== entry.pdf_sha256)
      throw new Error(
        `${source.statute}: archived PDF does not match the manifest; run --fetch.`,
      );
    const sections = parseStatute(source, await pdfPageItems(bytes));
    if (sections.length !== entry.section_count)
      throw new Error(
        `${source.statute}: section count differs from manifest.`,
      );
    parsed.push({ source, manifest: entry, sections });
  }
  return { manifest, parsed };
}

function writeDatabase(
  output: string,
  manifest: SourceManifest,
  statutes: ParsedStatute[],
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
    const total = statutes.reduce((sum, item) => sum + item.sections.length, 0);
    db.transaction(() => {
      for (const { source, manifest: entry, sections } of statutes)
        for (const section of sections) {
          if (pick && !pick[source.statute]?.includes(section.section_number))
            continue;
          insert.run(
            source.statute,
            section.section_number,
            `Section ${section.section_number} ${source.short_name}`,
            section.title,
            section.text,
            entry.details_url,
          );
          count++;
        }
      const statuteMeta = statutes.map(
        ({ source, manifest: entry, sections }) => ({
          statute: source.statute,
          short_name: source.short_name,
          title: source.title,
          wipo_title: entry.wipo_title,
          wipo_summary: entry.wipo_summary,
          version_note: entry.version_note,
          details_url: entry.details_url,
          pdf_url: entry.pdf_url,
          pdf_last_modified: entry.pdf_last_modified,
          retrieved_at: entry.retrieved_at,
          pdf_sha256: entry.pdf_sha256,
          section_count: sections.length,
        }),
      );
      const meta: [string, string][] = [
        ["schema_version", "1"],
        ["snapshot_date", manifest.retrieved_at.slice(0, 10)],
        [
          "source_version",
          `WIPO Lex English translations, ${manifest.retrieved_at.slice(0, 10)}`,
        ],
        ["section_count", String(count)],
        ["retrieved_at", manifest.retrieved_at],
        [
          "authority",
          "Unofficial English translations. The Thai text published in the Government Gazette is the only authoritative version.",
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
      throw new Error("A fixture section is missing from the build.");
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
  statutes: ParsedStatute[],
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
    option("--raw") ?? join(root, ".data/thai_dip_statutes/raw"),
  );
  const output = resolve(
    option("--output") ??
      join(root, ".data/thai_dip_statutes/thai_dip_statutes.db"),
  );
  if (args.includes("--fetch")) await fetchAll(raw);
  if (await exists(output))
    throw new Error(`${output} exists; choose a new --output.`);
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
          sections: item.sections.length,
          numbers: item.sections
            .map((section) => section.section_number)
            .join(" "),
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
      FIXTURE_SECTIONS,
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

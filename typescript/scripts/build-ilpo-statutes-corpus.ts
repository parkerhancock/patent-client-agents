// Builds the ILPO Israel statutes SQLite/FTS5 corpus (schema 1, as the Python
// connector defines it) from the English translations WIPO Lex publishes for
// the five Israeli IP statutes. For each statute the WIPO Lex detail page is
// fetched, its English PDF link (signed, valid for a few minutes) is followed
// once, and the PDF is archived. Plain HTTPS GETs with an honest user agent;
// no browser, cookies or challenge handling.
//
// The PDFs are laid out as the Israeli gazette prints statutes: a margin
// column carries each section's heading and amendment notes, then the section
// number, then the text. Sections are split by position (pdfjs text items),
// not by guessing from plain text, so headings, amendment notes, footnotes
// and running heads land where they belong.
//
// Usage (from typescript/):
//   bun scripts/build-ilpo-statutes-corpus.ts --fetch   # download the five PDFs, rewrite the source manifest, build
//   bun scripts/build-ilpo-statutes-corpus.ts           # rebuild from the archived PDFs (sha256-checked)
//   bun scripts/build-ilpo-statutes-corpus.ts --fixture # also rewrite the test fixture subset
// Options: --output PATH (default .data/ilpo_statutes/ilpo_statutes.db, must
// not exist), --raw DIR (default .data/ilpo_statutes/raw).
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
const manifestPath = join(import.meta.dir, "ilpo-statutes-sources.json");
const fixturePath = join(root, "tests/fixtures/ilpo-statutes/ilpo_statutes.db");

/** Page geometry of one statute's PDF, in PDF points. */
interface Layout {
  /** First page holding statute text (the Trade Marks Ordinance opens with a table of contents). */
  firstPage: number;
  /** Section numbers sit in this x range. */
  numberMinX: number;
  numberMaxX: number;
  /** Text at or right of this x is statute text; left of it is the margin column. */
  bodyX: number;
  /** Whether section numbers carry a trailing period ("4." rather than "17A"). */
  numberDot: boolean;
  /** Body font height, used to tell footnotes and superscripts apart. */
  bodySize: number;
  /** Section headings in the margin column, or on their own line above the number. */
  headings: "margin" | "above";
  /** The statute text ends at the first line matching this (schedules, signatures). */
  stop: RegExp;
  /** Also end at a `stop` match that starts in the margin column. */
  stopInMargin?: boolean;
  /** Stray lines that are not statute text. */
  drop?: RegExp;
}

export interface StatuteSource {
  statute: string;
  short_name: string;
  title: string;
  wipolex_id: string;
  layout: Layout;
}

/** The five statutes, their WIPO Lex entries and the layout of each English PDF. */
export const SOURCES: StatuteSource[] = [
  {
    statute: "patents",
    short_name: "Patents Law",
    title: "Patents Law, 5727-1967",
    wipolex_id: "15167",
    layout: {
      firstPage: 1,
      numberMinX: 154,
      numberMaxX: 172,
      bodyX: 190,
      numberDot: true,
      bodySize: 12,
      headings: "margin",
      stop: /\bSCHEDULE ONE\b/,
      stopInMargin: true,
    },
  },
  {
    statute: "trademarks",
    short_name: "Trade Marks Ordinance",
    title: "Trade Marks Ordinance [New Version], 5732-1972",
    wipolex_id: "8200",
    layout: {
      firstPage: 5,
      numberMinX: 174,
      numberMaxX: 198,
      bodyX: 200,
      numberDot: false,
      bodySize: 10.7,
      headings: "margin",
      stop: /^Schedule$/,
    },
  },
  {
    statute: "designs",
    short_name: "Designs Law",
    title: "Designs Law, 5777-2017",
    wipolex_id: "19434",
    layout: {
      firstPage: 1,
      // Number and text columns move between pages (149/185, 197/220).
      numberMinX: 144,
      numberMaxX: 205,
      bodyX: 144,
      numberDot: true,
      bodySize: 12,
      headings: "margin",
      stop: /^Benjamin Netanyahu\b/,
      drop: /^The Designs Bill, 5775/,
    },
  },
  {
    statute: "copyright",
    short_name: "Copyright Act",
    title: "Copyright Act, 5768-2007",
    wipolex_id: "11509",
    layout: {
      firstPage: 1,
      numberMinX: 68,
      numberMaxX: 80,
      bodyX: 180,
      numberDot: true,
      bodySize: 9,
      headings: "margin",
      stop: /^end$/,
    },
  },
  {
    statute: "commercial_torts",
    short_name: "Commercial Torts Law",
    title: "Commercial Torts Law, 5759-1999",
    wipolex_id: "2375",
    layout: {
      firstPage: 1,
      numberMinX: 70,
      numberMaxX: 96,
      bodyX: 0,
      numberDot: true,
      bodySize: 11,
      headings: "above",
      stop: /^Benjamin Netanyahu\b/,
    },
  },
];

/** Sections copied into the committed test fixture. */
const FIXTURE_SECTIONS: Record<string, string[]> = {
  patents: ["2", "3", "4", "5", "54A"],
  trademarks: ["8", "11", "46A"],
  designs: ["3", "6"],
  copyright: ["5", "19"],
  commercial_torts: ["5", "6", "13"],
};

// The schema the Python builder writes (corpus/schema.py, version 1), in
// DELETE journal mode instead of WAL.
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

// ---------------------------------------------------------------- layout

interface Line {
  page: number;
  y: number;
  items: PdfTextItem[];
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

/**
 * One page's text lines, top to bottom, without footnotes, running heads,
 * page numbers or footnote reference marks. Ordinal superscripts ("11th")
 * stay with their line.
 */
export function pageLines(
  items: PdfTextItem[],
  page: number,
  bodySize: number,
): Line[] {
  const visible = items.filter((item) => item.str.trim());
  const small = (item: PdfTextItem) =>
    item.height > 0 && item.height <= bodySize * 0.72;
  // A footnote starts with a small number or asterisk followed, just right
  // and a little lower, by text set smaller than the body.
  let footnoteTop = Number.NEGATIVE_INFINITY;
  for (const mark of visible) {
    if (!small(mark) || !/^(\d{1,2}|\*)$/.test(mark.str.trim())) continue;
    if (mark.y > 320) continue;
    const follows = visible.some(
      (text) =>
        text !== mark &&
        !small(text) &&
        text.height < bodySize * 0.95 &&
        text.y <= mark.y + 0.5 &&
        text.y >= mark.y - 7 &&
        text.x > mark.x &&
        text.x <= mark.x + 30,
    );
    if (follows) footnoteTop = Math.max(footnoteTop, mark.y + 1);
  }
  const kept = items.filter((item) => item.y > footnoteTop);
  const lines: Line[] = [];
  const superscripts: PdfTextItem[] = [];
  for (const item of [...kept].sort((a, b) => b.y - a.y || a.x - b.x)) {
    if (!item.str.trim() && !item.height) continue;
    if (small(item)) {
      if (isOrdinal(item.str)) superscripts.push(item);
      continue;
    }
    const tolerance = Math.max(2, item.height * 0.4);
    const line = lines.find((entry) => Math.abs(entry.y - item.y) <= tolerance);
    if (line) line.items.push(item);
    else if (item.str.trim()) lines.push({ page, y: item.y, items: [item] });
  }
  for (const item of superscripts) {
    const line = lines.find(
      (entry) => item.y - entry.y >= 0 && item.y - entry.y <= 7,
    );
    line?.items.push({ ...item, y: line.y });
  }
  return lines
    .sort((a, b) => b.y - a.y)
    .filter((line) => {
      const text = joinItems(line.items);
      const edge = line.y < 95 || line.y > 760;
      return !(
        edge && /^(\d{1,3}|-\s*\d{1,3}\s*-|IP\/N\/1\/ISR\/C\/\d+)$/.test(text)
      );
    });
}

// ---------------------------------------------------------------- sections

export interface ParsedSection {
  section_number: string;
  title: string | null;
  text: string;
}

const NUMBER = /^(\d{1,3}(?:[A-Z]{1,2}\d?)?)(\.?)(?:\s+(.*))?$/;
/**
 * A chapter, part or article heading line ("CHAPTER TWO: PATENTABILITY",
 * "Article 1 : Ownership of a Design"), tested with spaces removed because
 * some PDFs split these words ("Artic le 2").
 */
const DIVISION =
  /^(chapter|part|article|subchapter|sub-chapter|title)[^:]{1,30}:\S/i;
const isDivision = (text: string) =>
  DIVISION.test(text.replace(/\s+/g, "")) ||
  /^(chapter|part)\s+[\w-]+(\s+[–-]\s+\S.*)?$/i.test(text);
/** Margin lines that are amendment notes rather than the section heading. */
const NOTE = /^\(amendment|^amendment\s+no\b|^[\d\s.\-–()]+$|^no\.?\s*\d/i;
const ORDINAL_SUBSECTIONS: Record<string, string> = {
  Two: "b",
  Three: "c",
  Four: "d",
  Five: "e",
  Six: "f",
  Seven: "g",
  Eight: "h",
};

function compareNumbers(a: string, b: string): number {
  const [, baseA = "0", suffixA = ""] = /^(\d+)(.*)$/.exec(a) ?? [];
  const [, baseB = "0", suffixB = ""] = /^(\d+)(.*)$/.exec(b) ?? [];
  const base = Number(baseA) - Number(baseB);
  if (base) return base;
  return suffixA < suffixB ? -1 : suffixA > suffixB ? 1 : 0;
}
/** A section number that can follow `previous` in the statute (guards against stray numerals). */
function follows(previous: string | null, next: string): boolean {
  if (previous === null) return Number.parseInt(next, 10) <= 3;
  const gap = Number.parseInt(next, 10) - Number.parseInt(previous, 10);
  return compareNumbers(next, previous) > 0 && gap <= 12;
}

/** Body lines reflowed into paragraphs: one per subsection, list item or definition. */
export function paragraphs(lines: string[], ordinalSubsections = false) {
  const out: string[] = [];
  for (const raw of lines) {
    let line = raw;
    if (ordinalSubsections)
      line = line.replace(
        /^\((Two|Three|Four|Five|Six|Seven|Eight)\)/,
        (_match, word: string) => `(${ORDINAL_SUBSECTIONS[word]})`,
      );
    const previous = out.at(-1);
    const marker = /^\((?:\d{1,2}[A-Z]?\d?|[a-z]\d?|[ivx]{1,5}|[A-Z])\)/.test(
      line,
    );
    // A quoted term opens a definition only after a finished clause.
    const definition =
      /^["“”']/.test(line) && /[.;:–‒-]$/.test(previous?.trim() ?? ".");
    const leadIn =
      previous !== undefined &&
      (/[:;–‒]$/.test(previous.trim()) || /\s-$/.test(previous));
    if (previous === undefined || marker || definition || leadIn) {
      out.push(line);
      continue;
    }
    out[out.length - 1] = /\S-$/.test(previous)
      ? `${previous}${line}`
      : `${previous} ${line}`;
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
  page: number;
  y: number;
  margin: string[];
  heading: string | null;
  body: string[];
}

/** Every numbered section of one statute, in order. */
export function parseStatute(
  source: StatuteSource,
  pages: PdfTextItem[][],
): ParsedSection[] {
  const { layout } = source;
  const drafts: Draft[] = [];
  let preamble: { page: number; y: number; text: string }[] = [];
  let skipCaps = false;
  let stopped = false;
  for (let index = layout.firstPage - 1; index < pages.length; index++) {
    if (stopped) break;
    const page = index + 1;
    const lines = pageLines(pages[index] ?? [], page, layout.bodySize);
    // Margin text goes to the nearest section number at or below it on the
    // page (headings may sit a line above the number), else to the section
    // carried over from the previous page.
    const pageMargins: { y: number; text: string }[] = [];
    const startsHere: Draft[] = [];
    for (const line of lines) {
      const sorted = [...line.items].sort((a, b) => a.x - b.x);
      let number: string | null = null;
      let tail: string | undefined;
      // The number may be one text item ("84.", "196. As of"), or split
      // into several ("8", "0", ".").
      const column = sorted.filter((item) => item.x >= layout.numberMinX);
      const rest = column.slice(
        Math.max(
          0,
          column.findIndex(
            (item) =>
              item.x <= layout.numberMaxX && /^\d/.test(item.str.trim()),
          ),
        ),
      );
      const leadItems: PdfTextItem[] = [];
      let numberText = "";
      for (const item of rest) {
        if (!leadItems.length && item.x > layout.numberMaxX) break;
        const next = `${numberText}${item.str}`.trim();
        if (!/^\d[\d ]*(?:[A-Z]{1,2}\d?)?\s*\.?$/.test(next)) break;
        numberText = next;
        leadItems.push(item);
        if (next.endsWith(".")) break;
      }
      const first = rest[0];
      if (!leadItems.length && first && first.x <= layout.numberMaxX) {
        leadItems.push(first);
        numberText = first.str.trim();
      }
      const lead = leadItems[0];
      if (lead && (layout.bodyX > 0 || lead === sorted[0])) {
        const match = NUMBER.exec(
          numberText
            .replace(/^(\d[\d ]*)/, (digits) => digits.replace(/ /g, ""))
            .replace(/\s+\./, "."),
        );
        const candidate = match?.[1];
        if (
          match &&
          candidate &&
          (match[2] === "." || !layout.numberDot) &&
          follows(drafts.at(-1)?.number ?? null, candidate)
        ) {
          number = candidate;
          tail = match[3];
        }
      }
      const isNumber = (item: PdfTextItem) =>
        number !== null && leadItems.includes(item);
      const marginItems = sorted.filter(
        (item) => item.x < layout.bodyX && !isNumber(item),
      );
      const bodyItems = sorted.filter(
        (item) => item.x >= layout.bodyX && !isNumber(item),
      );
      if (lead && tail) bodyItems.unshift({ ...lead, str: tail });
      const marginText = joinItems(marginItems);
      const bodyText = joinItems(bodyItems);
      const full = joinItems(sorted);
      if (layout.drop?.test(full)) continue;
      if (
        layout.stop.test(bodyText) ||
        (layout.stopInMargin && layout.stop.test(full))
      ) {
        stopped = true;
        break;
      }
      if (
        number === null &&
        (isDivision(full) || isDivision(bodyText) || (skipCaps && isCaps(full)))
      ) {
        skipCaps = true;
        continue;
      }
      skipCaps = false;
      if (number !== null) {
        let heading: string | null = null;
        if (layout.headings === "above") {
          const previous = drafts.at(-1);
          const last = previous ? previous.body.at(-1) : preamble.at(-1)?.text;
          if (last && looksLikeHeading(last)) {
            heading = last;
            if (previous) previous.body.pop();
            else preamble.pop();
          }
        }
        // A lead-in printed a line or two above the first number ("In this Act -").
        const leadIn = drafts.length
          ? []
          : preamble
              .filter(
                (entry) =>
                  layout.headings === "margin" &&
                  entry.page === page &&
                  entry.y - line.y <= layout.bodySize * 2.5,
              )
              .map((entry) => entry.text);
        const draft: Draft = {
          number,
          page,
          y: line.y,
          margin: [],
          heading,
          body: leadIn,
        };
        drafts.push(draft);
        startsHere.push(draft);
      }
      if (marginText && layout.bodyX > 0)
        pageMargins.push({ y: line.y, text: marginText });
      if (bodyText) {
        const current = drafts.at(-1);
        if (current) current.body.push(bodyText);
        else preamble.push({ page, y: line.y, text: bodyText });
      }
    }
    const carried = drafts.filter((draft) => draft.page < page).at(-1);
    const tolerance = layout.bodySize * 0.6;
    for (const margin of pageMargins) {
      const owner =
        startsHere
          .filter((draft) => draft.y >= margin.y - tolerance)
          .sort((a, b) => a.y - b.y)[0] ??
        carried ??
        // A heading a line or two above the first section ("Definitions").
        startsHere.find((draft) => margin.y - draft.y <= layout.bodySize * 2.5);
      owner?.margin.push(margin.text);
    }
    preamble = drafts.length ? [] : preamble;
  }
  const seen = new Set<string>();
  return drafts.map((draft) => {
    if (seen.has(draft.number))
      throw new Error(`${source.statute}: duplicate section ${draft.number}.`);
    seen.add(draft.number);
    const headingLines: string[] = [];
    const notes: string[] = [];
    for (const line of draft.margin) {
      // "Registrar (Amendment" carries the end of the heading and a note.
      const split = /\(amendment\b|\bamendment\s+no\b/i.exec(line)?.index ?? -1;
      if (split > 0) {
        headingLines.push(line.slice(0, split).trim());
        notes.push(line.slice(split).trim());
      } else (NOTE.test(line) ? notes : headingLines).push(line);
    }
    const title =
      draft.heading ??
      (headingLines.length
        ? headingLines.join(" ").replace(/\s+/g, " ").trim()
        : null);
    const body = paragraphs(draft.body, source.statute === "commercial_torts");
    if (notes.length)
      body.push(`[Margin notes: ${notes.join(" ").replace(/\s+/g, " ")}]`);
    return {
      section_number: draft.number,
      title: title || null,
      text: body.join("\n") || title || "",
    };
  });
}

function isCaps(text: string) {
  return /[A-Z]/.test(text) && !/[a-z]/.test(text);
}
function looksLikeHeading(text: string) {
  return (
    text.length <= 90 &&
    !/[.;:,]$/.test(text) &&
    !/^[(“"]/.test(text) &&
    /^[A-Z]/.test(text)
  );
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
  statutes: SourceStatute[];
}

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
    const file = legislation.files.find(
      (link) =>
        link.mime_type === "application/pdf" &&
        new URL(link.url).pathname.includes("/laws/en/"),
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
      "WIPO Lex (https://www.wipo.int/wipolex/) English translations, one PDF per statute",
    user_agent: USER_AGENT,
    retrieved_at: statutes.map((item) => item.retrieved_at).sort()[0] as string,
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
  const raw = resolve(option("--raw") ?? join(root, ".data/ilpo_statutes/raw"));
  const output = resolve(
    option("--output") ?? join(root, ".data/ilpo_statutes/ilpo_statutes.db"),
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

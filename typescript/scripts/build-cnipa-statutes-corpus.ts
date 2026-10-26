// Builds the CNIPA China statutes SQLite/FTS5 corpus (the statute schema the
// ILPO corpus uses, version 1) from the English translations
// WIPO Lex publishes for six Chinese IP laws and regulations. For each one the
// WIPO Lex detail page is fetched, the named English PDF link (signed, valid
// for a few minutes) is followed once, and the PDF is archived. Plain HTTPS
// GETs with an honest user agent; no browser, cookies or challenge handling.
//
// The PDFs print each provision as "Article N" (or "Rule N" in the 2010
// Implementing Regulations of the Patent Law) at the start of a paragraph,
// with centered chapter and section headings and no per-article headings.
// Lines come from positioned pdfjs text items (the ILPO builder's pageLines),
// so page numbers and the small "for reference only" footer are dropped, and
// paragraphs are rebuilt from indentation or line spacing.
//
// Usage (from typescript/):
//   bun scripts/build-cnipa-statutes-corpus.ts --fetch   # download the six PDFs, rewrite the source manifest, build
//   bun scripts/build-cnipa-statutes-corpus.ts           # rebuild from the archived PDFs (sha256-checked)
//   bun scripts/build-cnipa-statutes-corpus.ts --fixture # also rewrite the test fixture subset
// Options: --output PATH (default .data/cnipa_statutes/cnipa_statutes.db, must
// not exist), --raw DIR (default .data/cnipa_statutes/raw).
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
import { joinItems, pageLines } from "./build-ilpo-statutes-corpus.js";

const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
const root = join(import.meta.dir, "..");
const manifestPath = join(import.meta.dir, "cnipa-statutes-sources.json");
const fixturePath = join(
  root,
  "tests/fixtures/cnipa-statutes/cnipa_statutes.db",
);

/** How one statute's English PDF is laid out. */
interface Layout {
  /** First page holding statute text (the Patent Law PDF opens with the 2020 amending Decision). */
  firstPage: number;
  /** "Article" or "Rule", as the translation numbers its provisions. */
  unit: "Article" | "Rule";
  /** Paragraphs start indented ("indent") or after a wider line gap ("gap"). */
  paragraphs: "indent" | "gap";
  /** Body font height; smaller text (page numbers, footers) is dropped. */
  bodySize: number;
  /** Provisions whose heading the PDF misprints with the other unit ("Article 26" among the Rules). */
  misprinted?: number[];
}

export interface StatuteSource {
  statute: string;
  short_name: string;
  title: string;
  wipolex_id: string;
  /** File name of the English PDF on the WIPO Lex page (the page also links WTO notifications). */
  pdf: string;
  /** What the English text is, read from the PDF itself; WIPO's entry may be newer. */
  translation_version: string;
  /** Numbered provisions the translation holds; the build stops on any other count. */
  provisions: number;
  layout: Layout;
}

/** The six statutes, their WIPO Lex entries and the layout of each English PDF. */
export const SOURCES: StatuteSource[] = [
  {
    statute: "patent_law",
    short_name: "Patent Law",
    title: "Patent Law of the People's Republic of China",
    wipolex_id: "21027",
    pdf: "cn411en_1.pdf",
    translation_version:
      "As amended October 17, 2020 (fourth amendment, in force June 1, 2021)",
    provisions: 82,
    layout: {
      firstPage: 7,
      unit: "Article",
      paragraphs: "indent",
      bodySize: 12.6,
    },
  },
  {
    statute: "patent_regulations",
    short_name: "Patent Implementing Regulations",
    title:
      "Implementing Regulations of the Patent Law of the People's Republic of China",
    wipolex_id: "13395",
    pdf: "cn078en.pdf",
    translation_version:
      "As amended January 9, 2010 (in force February 1, 2010). WIPO Lex's entry is the December 11, 2023 revision (in force January 20, 2024), for which it holds only the Chinese text; the 2023 text renumbers the provisions as Articles",
    provisions: 123,
    layout: {
      firstPage: 1,
      unit: "Rule",
      paragraphs: "gap",
      bodySize: 10,
      misprinted: [26],
    },
  },
  {
    statute: "trademark_law",
    short_name: "Trademark Law",
    title: "Trademark Law of the People's Republic of China",
    wipolex_id: "23875",
    pdf: "cn410en_1.pdf",
    translation_version:
      "As amended April 23, 2019 (fourth amendment). WIPO Lex's entry is the June 26, 2026 revision (87 Articles, in force January 1, 2027), for which it holds only the Chinese text; Article numbers differ between the two",
    provisions: 73,
    layout: {
      firstPage: 1,
      unit: "Article",
      paragraphs: "indent",
      bodySize: 11,
    },
  },
  {
    statute: "trademark_regulations",
    short_name: "Trademark Implementing Regulations",
    title:
      "Regulations for the Implementation of the Trademark Law of the People's Republic of China",
    wipolex_id: "15011",
    pdf: "cn342en_1.pdf",
    translation_version: "As revised April 29, 2014 (in force May 1, 2014)",
    provisions: 98,
    layout: {
      firstPage: 1,
      unit: "Article",
      paragraphs: "indent",
      bodySize: 12,
    },
  },
  {
    statute: "anti_unfair_competition",
    short_name: "Anti-Unfair Competition Law",
    title: "Anti-Unfair Competition Law of the People's Republic of China",
    wipolex_id: "19557",
    pdf: "cn409en.pdf",
    translation_version:
      "As amended April 23, 2019. Revised again June 27, 2025 (in force October 15, 2025, with more Articles); WIPO Lex lists no entry for that revision, so it is not reflected",
    provisions: 33,
    layout: { firstPage: 1, unit: "Article", paragraphs: "gap", bodySize: 14 },
  },
  {
    statute: "copyright_law",
    short_name: "Copyright Law",
    title: "Copyright Law of the People's Republic of China",
    wipolex_id: "21065",
    pdf: "cn413en_1.pdf",
    translation_version:
      "As amended November 11, 2020 (third amendment, in force June 1, 2021)",
    provisions: 67,
    layout: {
      firstPage: 1,
      unit: "Article",
      paragraphs: "gap",
      bodySize: 11.3,
    },
  },
];

/** Provisions copied into the committed test fixture. */
const FIXTURE_SECTIONS: Record<string, string[]> = {
  patent_law: ["2", "22", "26", "82"],
  patent_regulations: ["6", "20"],
  trademark_law: ["13", "57"],
  trademark_regulations: ["3"],
  anti_unfair_competition: ["9", "32"],
  copyright_law: ["3", "24"],
};

// The statute corpus schema (version 1), in DELETE journal mode.
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

// ---------------------------------------------------------------- parsing

export interface ParsedSection {
  section_number: string;
  /** The chapter (and section) the provision sits in; the translations print no article headings. */
  title: string | null;
  text: string;
}

/** A text line with its page, baseline and left edge. */
export interface TextLine {
  page: number;
  y: number;
  x: number;
  text: string;
}

/** Positioned lines of every page from `firstPage` on. */
export function textLines(pages: PdfTextItem[][], layout: Layout): TextLine[] {
  const out: TextLine[] = [];
  for (let index = layout.firstPage - 1; index < pages.length; index++)
    for (const line of pageLines(
      pages[index] ?? [],
      index + 1,
      layout.bodySize,
    )) {
      const text = joinItems(line.items);
      if (!text) continue;
      out.push({
        page: index + 1,
        y: line.y,
        x: Math.min(
          ...line.items.filter((item) => item.str.trim()).map((item) => item.x),
        ),
        text,
      });
    }
  return out;
}

// Two chapter numerals in the Patent Law PDF are Cyrillic look-alikes.
const NUMERALS: Record<string, string> = { П: "II", Ш: "III" };
const DIVISION = /^(Chapter|Section)\s+([IVXLC]+|[ПШ]|\d{1,2})(?=\s|$)\s*(.*)$/;
/** A heading line, not a wrapped cross-reference ("Section 2 of this Chapter"). */
function division(text: string) {
  const match = DIVISION.exec(text);
  if (!match) return null;
  const [, kind = "", numeral = "", name = ""] = match;
  if (name && (!/^[A-Z]/.test(name) || /[.,;:]$/.test(name))) return null;
  return {
    kind: kind as "Chapter" | "Section",
    label: `${kind} ${NUMERALS[numeral] ?? numeral}`,
    name,
  };
}

/** The most frequent value, for the wrapped-line column. */
function mode(values: number[]) {
  const counts = new Map<number, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  return [...counts].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0]?.[0] ?? 0;
}

/** Join wrapped lines, keeping a line-end hyphen in compounds ("anti-" + "unfair"). */
function joinLine(previous: string, line: string) {
  return /\S-$/.test(previous) ? `${previous}${line}` : `${previous} ${line}`;
}
function tidy(paragraph: string) {
  return paragraph
    .replace(/\s+([,;:.)\]])/g, "$1")
    .replace(/([([])\s+/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

interface Draft {
  number: number;
  title: string | null;
  note: string | null;
  paragraphs: string[];
  last: TextLine | null;
}

/** Every numbered provision of one statute, in order. */
export function parseStatute(
  source: StatuteSource,
  pages: PdfTextItem[][],
): ParsedSection[] {
  const { layout } = source;
  const lines = textLines(pages, layout);
  const wrapX = mode(lines.map((line) => Math.round(line.x)));
  // Line pitch: the lower quartile of same-page line gaps (paragraph gaps
  // are about twice as wide).
  const gaps = lines
    .slice(1)
    .map((line, index) => {
      const previous = lines[index] as TextLine;
      return previous.page === line.page ? previous.y - line.y : 0;
    })
    .filter((gap) => gap > 0)
    .sort((a, b) => a - b);
  const pitch = gaps[Math.floor(gaps.length / 4)] ?? 0;
  const start = /^(Article|Rule)\s+(\d{1,3})(?:\.|(?=\s)|$)\s*(.*)$/;
  const drafts: Draft[] = [];
  let chapter: string | null = null;
  let section: string | null = null;
  // While set, lines up to the next provision name the heading just opened.
  let heading: {
    kind: "Chapter" | "Section";
    label: string;
    names: string[];
  } | null = null;
  const closeHeading = () => {
    if (!heading) return;
    const name = heading.names.join(" ").replace(/\s+/g, " ").trim();
    if (heading.names.length > 3 || name.length > 160)
      throw new Error(
        `${source.statute}: runaway heading after ${heading.label}.`,
      );
    const full = name ? `${heading.label} ${name}` : heading.label;
    if (heading.kind === "Chapter") {
      chapter = full;
      section = null;
    } else section = full;
    heading = null;
  };
  for (const line of lines) {
    const match = start.exec(line.text);
    const number = match ? Number(match[2]) : Number.NaN;
    const tail = match?.[3] ?? "";
    const expected = (drafts.at(-1)?.number ?? 0) + 1;
    const unit =
      match?.[1] === layout.unit || layout.misprinted?.includes(number);
    if (
      match &&
      unit &&
      number === expected &&
      (!tail || /^[A-Z“"(]/.test(tail))
    ) {
      closeHeading();
      // "Rule 6 (Incorporating original Rule 7)": the translation's renumbering note.
      const note = /^\(([^()]*)\)$/.exec(tail)?.[1] ?? null;
      drafts.push({
        number,
        title: [chapter, section].filter(Boolean).join(", ") || null,
        note,
        paragraphs: tail && !note ? [tail] : [],
        last: line,
      });
      continue;
    }
    const opened = division(line.text);
    if (opened) {
      closeHeading();
      heading = {
        kind: opened.kind,
        label: opened.label,
        names: opened.name ? [opened.name] : [],
      };
      continue;
    }
    if (heading) {
      heading.names.push(line.text);
      continue;
    }
    const current = drafts.at(-1);
    if (!current) continue; // title, promulgation note, contents
    const previous = current.last;
    const paragraphs = current.paragraphs;
    const last = paragraphs.at(-1);
    // Wrapped cross-references ("Subparagraphs (5) to" / "(6) of …") put a
    // marker at a line start, so only layout decides.
    let starts = last === undefined;
    if (!starts && previous) {
      if (layout.paragraphs === "indent") starts = line.x > wrapX + 6;
      else if (previous.page === line.page)
        starts = previous.y - line.y > pitch * 1.4;
      else starts = /[.;:]$/.test(last ?? "") && /^[A-Z“"(]/.test(line.text);
    }
    if (starts) paragraphs.push(line.text);
    else paragraphs[paragraphs.length - 1] = joinLine(last ?? "", line.text);
    current.last = line;
  }
  if (heading) throw new Error(`${source.statute}: text ends in a heading.`);
  if (drafts.length !== source.provisions)
    throw new Error(
      `${source.statute}: found ${drafts.length} provisions, expected ${source.provisions}.`,
    );
  return drafts.map((draft) => {
    const body = draft.paragraphs.map(tidy).filter(Boolean);
    if (draft.note) body.push(`[Note: ${draft.note}]`);
    if (!body.length)
      throw new Error(
        `${source.statute}: ${layout.unit} ${draft.number} is empty.`,
      );
    return {
      section_number: String(draft.number),
      title: draft.title,
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
  /** What the English text is; WIPO's entry may describe a newer Chinese text. */
  translation_version: string;
  /** The English PDF, without the signature query WIPO adds. */
  pdf_url: string;
  /** The Chinese text WIPO Lex links on the same page (not downloaded), which controls. */
  zh_pdf_url: string | null;
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
        new URL(link.url).pathname.endsWith(`/laws/en/cn/${source.pdf}`),
    );
    if (!file)
      throw new Error(`${source.statute}: no ${source.pdf} on ${page}.`);
    const chinese = legislation.files.find(
      (link) =>
        link.mime_type === "application/pdf" &&
        new URL(link.url).pathname.includes("/laws/zh/cn/"),
    );
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
      translation_version: source.translation_version,
      pdf_url: pdfUrl,
      zh_pdf_url: chinese
        ? `${new URL(chinese.url).origin}${new URL(chinese.url).pathname}`
        : null,
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
      `${source.statute}: ${sections.length} provisions, ${pages.length} pages, ${bytes.byteLength} bytes`,
    );
  }
  const manifest: SourceManifest = {
    source:
      "WIPO Lex (https://www.wipo.int/wipolex/) English translations, one PDF per statute; the Chinese text controls",
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
        `${source.statute}: provision count differs from manifest.`,
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
            `${source.layout.unit} ${section.section_number} ${source.short_name}`,
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
          unit: source.layout.unit,
          wipo_title: entry.wipo_title,
          wipo_summary: entry.wipo_summary,
          translation_version: entry.translation_version,
          details_url: entry.details_url,
          pdf_url: entry.pdf_url,
          zh_pdf_url: entry.zh_pdf_url,
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
          "notice",
          "English translations for reference only; the Chinese text controls.",
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
      throw new Error("A fixture provision is missing from the build.");
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
    option("--raw") ?? join(root, ".data/cnipa_statutes/raw"),
  );
  const output = resolve(
    option("--output") ?? join(root, ".data/cnipa_statutes/cnipa_statutes.db"),
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

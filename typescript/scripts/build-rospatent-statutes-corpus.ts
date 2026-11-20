// Builds the Russian Federation IP statute corpus: Part Four of the Civil
// Code (Section VII, chapters 69 to 77, articles 1225 onward) in the English
// translation WIPO Lex publishes, as one SQLite/FTS5 snapshot (schema 1, the
// row shape of the other statute corpora plus chapter, § and repeal columns).
//
// WIPO Lex holds the English text only on its record of the whole Code
// (Parts One to Four). The builder fetches that record's page, follows its
// English PDF link (signed, valid for a few minutes) once, and archives the
// PDF. It also reads WIPO Lex's latest record for the Code, to check that no
// newer English text exists and to record how far the Russian text has moved
// on. Plain HTTPS GETs with an honest user agent; no browser, cookies or
// challenge handling.
//
// Part Four is set in one 12-point face: paragraphs start indented, lines
// continue at the margin, and chapter, § and sub-§ headings are centered.
// Articles are split by position (pdfjs text items), not from plain text.
//
// Usage (from typescript/):
//   bun scripts/build-rospatent-statutes-corpus.ts --fetch   # download the PDF, rewrite the source manifest, build
//   bun scripts/build-rospatent-statutes-corpus.ts           # rebuild from the archived PDF (sha256-checked)
//   bun scripts/build-rospatent-statutes-corpus.ts --fixture # also rewrite the test fixture subset
// Options: --output PATH (default .data/rospatent_statutes/rospatent_statutes.db,
// must not exist), --raw DIR (default .data/rospatent_statutes/raw).
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
const manifestPath = join(import.meta.dir, "rospatent-statutes-sources.json");
const fixturePath = join(
  root,
  "tests/fixtures/rospatent-statutes/rospatent_statutes.db",
);

/** WIPO Lex record whose English PDF is parsed: the Civil Code, 2024 version. */
export const LEGISLATION_ID = "22547";
/**
 * WIPO Lex's latest record of the Civil Code. Its English entry is the same
 * 2024 PDF "provided for reference"; the fetch stops if that changes, since a
 * newer English consolidation would then exist.
 */
export const LATEST_ID = "23256";
export const STATUTE = "civil_code";
export const SHORT_NAME = "Civil Code";

/** Part Four's page geometry in the 2024 PDF, in PDF points. */
export const LAYOUT = {
  /** Continuation lines start here. */
  margin: 40,
  /** Paragraphs and article headings start here. */
  indent: 76,
  /** Centre of the text block (margin to the 555 pt right edge). */
  center: 297.5,
};

/** Articles copied into the committed test fixture. */
const FIXTURE_ARTICLES = [
  "1225",
  "1229",
  "1231.1",
  "1248",
  "1252",
  "1259",
  "1270",
  "1350",
  "1358.1",
  "1363",
  "1465",
  "1477",
  "1478",
  "1484",
  "1515",
  "1541",
];

// The statute schema the other corpora use (version 1), with Part Four's
// chapter, § and sub-§ headings and a repeal flag, in DELETE journal mode.
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
    chapter        TEXT NOT NULL,
    paragraph      TEXT,
    subparagraph   TEXT,
    repealed       INTEGER NOT NULL DEFAULT 0,
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

export interface Line {
  page: number;
  y: number;
  /** Left edge of the first visible item and right edge of the last. */
  x: number;
  right: number;
  text: string;
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

/** One page's text lines, top to bottom. Part Four has no footnotes or running heads. */
export function pageLines(items: PdfTextItem[], page: number): Line[] {
  const lines: { y: number; items: PdfTextItem[] }[] = [];
  for (const item of [...items].sort((a, b) => b.y - a.y || a.x - b.x)) {
    if (!item.str.trim() && !item.height) continue;
    const tolerance = Math.max(2, item.height * 0.4);
    const line = lines.find((entry) => Math.abs(entry.y - item.y) <= tolerance);
    if (line) line.items.push(item);
    else if (item.str.trim()) lines.push({ y: item.y, items: [item] });
  }
  return lines
    .sort((a, b) => b.y - a.y)
    .map((line) => {
      const visible = line.items.filter((item) => item.str.trim());
      return {
        page,
        y: line.y,
        x: Math.min(...visible.map((item) => item.x)),
        right: Math.max(...visible.map((item) => item.x + item.width)),
        text: joinItems(line.items),
      };
    })
    .filter((line) => line.text);
}

// ---------------------------------------------------------------- articles

export interface ParsedArticle {
  section_number: string;
  /** The heading after "Article N."; null for a repealed article. */
  title: string | null;
  /** One paragraph per line, as the translation indents them. */
  text: string;
  /** "Chapter 72. The Patent Law" */
  chapter: string;
  /** "§ 5. Obtaining a Patent", when the chapter is divided into §s. */
  paragraph: string | null;
  /** "1. The Patent Application, Its Amendment and Revocation", inside a few §s. */
  subparagraph: string | null;
  repealed: boolean;
}

export interface ParsedPartFour {
  /** "Section VII. Rights to the Results of …" */
  section: string;
  articles: ParsedArticle[];
  /** Chapters printed only as repealed, without their articles (Chapter 77). */
  repealed_chapters: { chapter: string; note: string }[];
}

// Headings start with a capital; "Article 1229. of this Code" in running text does not.
const ARTICLE = /^Article (\d{4}(?:\.\d{1,2})?)\.\s+([A-Z].*)$/;
const REPEAL = /^(invalid|lost force|has lost force|repealed|abrogated)\b/i;

const numberParts = (value: string) =>
  value.split(".").map((part) => Number(part)) as [number, number?];
export function compareArticles(a: string, b: string): number {
  const [baseA, subA = 0] = numberParts(a);
  const [baseB, subB = 0] = numberParts(b);
  return baseA - baseB || subA - subB;
}
/**
 * An article number that can follow `previous` (guards against stray
 * references). A gap is allowed so a lost heading fails the completeness
 * check below instead of folding later articles into one.
 */
function follows(previous: string | null, next: string): boolean {
  if (previous === null) return next === "1225";
  const gap = numberParts(next)[0] - numberParts(previous)[0];
  return compareArticles(next, previous) > 0 && gap <= 12;
}

const tidy = (paragraph: string) =>
  paragraph
    .replace(/\s+([,;:.)\]])/g, "$1")
    .replace(/([([])\s+/g, "$1")
    .replace(/\s+/g, " ")
    .trim();

interface Draft {
  number: string;
  heading: string[];
  body: string[];
  chapter: string;
  paragraph: string | null;
  subparagraph: string | null;
}

/** Every article of Part Four, in order, with the headings above it. */
export function parsePartFour(pages: PdfTextItem[][]): ParsedPartFour {
  const near = (a: number, b: number) => Math.abs(a - b) <= 1.5;
  let started = false;
  let section: string[] = [];
  let chapter: string[] = [];
  let paragraph: string[] = [];
  let subparagraph: string[] = [];
  /** Which heading a centered line without its own number continues. */
  let heading: "section" | "chapter" | "paragraph" | "subparagraph" | null =
    null;
  let articleHeading = false;
  const drafts: Draft[] = [];
  const repealedChapters: { chapter: string; note: string }[] = [];
  const join = (parts: string[]) => tidy(parts.join(" "));
  outer: for (const [index, items] of pages.entries()) {
    for (const line of pageLines(items, index + 1)) {
      const text = line.text;
      if (!started) {
        if (text === "Section VII" && !near(line.x, LAYOUT.margin)) {
          started = true;
          section = [text];
          heading = "section";
        }
        continue;
      }
      if (/^President of the Russian Federation\b/.test(text)) break outer;
      const current = drafts.at(-1);
      const article = ARTICLE.exec(text);
      if (
        near(line.x, LAYOUT.indent) &&
        article?.[1] &&
        follows(current?.number ?? null, article[1])
      ) {
        drafts.push({
          number: article[1],
          heading: [article[2] as string],
          body: [],
          chapter: join(chapter),
          paragraph: paragraph.length ? join(paragraph) : null,
          subparagraph: subparagraph.length ? join(subparagraph) : null,
        });
        heading = null;
        articleHeading = true;
        continue;
      }
      // A long article heading wraps to a line indented past the paragraph indent.
      if (
        articleHeading &&
        current &&
        line.x > LAYOUT.indent + 20 &&
        !/^(Chapter \d+\.|§ \d+\.|\d+\.)\s/.test(text)
      ) {
        current.heading.push(text);
        continue;
      }
      articleHeading = false;
      const centered =
        !near(line.x, LAYOUT.margin) &&
        !near(line.x, LAYOUT.indent) &&
        Math.abs((line.x + line.right) / 2 - LAYOUT.center) <= 4;
      if (centered) {
        if (/^Chapter \d+\.\s/.test(text)) {
          chapter = [text];
          paragraph = [];
          subparagraph = [];
          heading = "chapter";
        } else if (/^§ \d+\.\s/.test(text)) {
          paragraph = [text];
          subparagraph = [];
          heading = "paragraph";
        } else if (/^\d+\.\s/.test(text) && paragraph.length) {
          subparagraph = [text];
          heading = "subparagraph";
        } else if (heading === "section") section.push(text);
        else if (heading === "chapter") chapter.push(text);
        else if (heading === "paragraph") paragraph.push(text);
        else if (heading === "subparagraph") subparagraph.push(text);
        else
          throw new Error(
            `Page ${line.page}: centered line outside a heading: ${text}`,
          );
        continue;
      }
      // Body text right after a chapter heading: Chapter 77 is printed only as repealed.
      if (heading === "chapter" && near(line.x, LAYOUT.indent)) {
        if (!REPEAL.test(text))
          throw new Error(
            `Page ${line.page}: text under ${join(chapter)} before any article: ${text}`,
          );
        repealedChapters.push({ chapter: join(chapter), note: tidy(text) });
        continue;
      }
      heading = null;
      if (!current)
        throw new Error(`Page ${line.page}: text before Article 1225.`);
      if (near(line.x, LAYOUT.indent) || !current.body.length)
        current.body.push(text);
      else if (near(line.x, LAYOUT.margin)) {
        const last = current.body.length - 1;
        const previous = current.body[last] as string;
        current.body[last] = /\S-$/.test(previous)
          ? `${previous}${text}`
          : `${previous} ${text}`;
      } else
        throw new Error(
          `Page ${line.page}: line at x=${line.x.toFixed(1)}: ${text}`,
        );
    }
  }
  if (!started) throw new Error("Part Four (Section VII) was not found.");
  const articles = drafts.map((draft) => {
    const title = join(draft.heading);
    const repealed = REPEAL.test(title) && !draft.body.length;
    return {
      section_number: draft.number,
      title: repealed ? null : title,
      text: repealed ? title : draft.body.map(tidy).join("\n"),
      chapter: draft.chapter,
      paragraph: draft.paragraph,
      subparagraph: draft.subparagraph,
      repealed,
    };
  });
  // Every whole number from 1225 to the last article must be present.
  const bases = new Set(
    articles.map((item) => numberParts(item.section_number)[0]),
  );
  const last = Math.max(...bases);
  for (let number = 1225; number <= last; number++)
    if (!bases.has(number)) throw new Error(`Article ${number} is missing.`);
  for (const item of articles)
    if (!item.text) throw new Error(`Article ${item.section_number} is empty.`);
  const [number, ...name] = section;
  return {
    section: name.length ? `${number}. ${join(name)}` : join(section),
    articles,
    repealed_chapters: repealedChapters,
  };
}

// ---------------------------------------------------------------- sources

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

interface LegislationSource {
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
  article_count: number;
  repealed_article_count: number;
}
interface LatestRecord {
  wipolex_id: string;
  details_url: string;
  wipo_summary: string | null;
  /** The English PDF the latest record links, without its signature. */
  english_pdf_url: string;
  retrieved_at: string;
}
interface SourceManifest {
  source: string;
  user_agent: string;
  retrieved_at: string;
  legislation: LegislationSource;
  latest_record: LatestRecord;
}

const detailsUrl = (id: string) =>
  `${WIPO_LEX_ORIGIN}/wipolex/en/legislation/details/${id}`;
const rawPath = (raw: string, pdfUrl: string) =>
  join(raw, pdfUrl.split("/").at(-1) as string);
const now = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");

async function get(url: string, accept: string) {
  const response = await fetch(url, {
    headers: { "user-agent": USER_AGENT, accept },
  });
  if (!response.ok) throw new Error(`GET ${url} returned ${response.status}.`);
  return response;
}

/** The record's English PDF link (signed) from its WIPO Lex page. */
async function englishPdf(id: string) {
  const page = detailsUrl(id);
  const html = await (await get(page, "text/html")).text();
  const legislation = parseWipoLexLegislation(html, id);
  const file = legislation.files.find(
    (link) =>
      link.mime_type === "application/pdf" &&
      new URL(link.url).pathname.includes("/laws/en/"),
  );
  if (!file) throw new Error(`No English PDF on ${page}.`);
  const url = new URL(file.url);
  return {
    page,
    legislation,
    signed: file.url,
    unsigned: `${url.origin}${url.pathname}`,
    modified: Number(url.searchParams.get("last-modified")),
  };
}

async function fetchAll(raw: string) {
  await mkdir(raw, { recursive: true });
  const latest = await englishPdf(LATEST_ID);
  const latestRetrieved = now();
  const record = await englishPdf(LEGISLATION_ID);
  if (latest.unsigned !== record.unsigned)
    throw new Error(
      `WIPO Lex ${LATEST_ID} now links ${latest.unsigned}, not ${record.unsigned}; a newer English text may exist.`,
    );
  const bytes = new Uint8Array(
    await (await get(record.signed, "application/pdf")).arrayBuffer(),
  );
  if (new TextDecoder().decode(bytes.slice(0, 5)) !== "%PDF-")
    throw new Error(`${record.unsigned} is not a PDF.`);
  const retrieved = now();
  const pages = await pdfPageItems(bytes);
  const parsed = parsePartFour(pages);
  await writeFile(rawPath(raw, record.unsigned), bytes);
  const manifest: SourceManifest = {
    source:
      "WIPO Lex (https://www.wipo.int/wipolex/) English translation of the Civil Code of the Russian Federation; Part Four (Section VII) is parsed",
    user_agent: USER_AGENT,
    retrieved_at: retrieved,
    legislation: {
      wipolex_id: LEGISLATION_ID,
      details_url: record.page,
      wipo_title: record.legislation.title,
      wipo_summary: record.legislation.summary,
      pdf_url: record.unsigned,
      pdf_last_modified:
        Number.isSafeInteger(record.modified) && record.modified > 0
          ? new Date(record.modified * 1000)
              .toISOString()
              .replace(/\.\d+Z$/, "Z")
          : null,
      retrieved_at: retrieved,
      pdf_sha256: sha256(bytes),
      pdf_bytes: bytes.byteLength,
      pages: pages.length,
      article_count: parsed.articles.length,
      repealed_article_count: parsed.articles.filter((item) => item.repealed)
        .length,
    },
    latest_record: {
      wipolex_id: LATEST_ID,
      details_url: latest.page,
      wipo_summary: latest.legislation.summary,
      english_pdf_url: latest.unsigned,
      retrieved_at: latestRetrieved,
    },
  };
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.error(
    `${parsed.articles.length} articles, ${pages.length} pages, ${bytes.byteLength} bytes`,
  );
}

/** Parse the archived PDF, checking it against the source manifest. */
export async function loadPartFour(raw: string) {
  const manifest = JSON.parse(
    await readFile(manifestPath, "utf8"),
  ) as SourceManifest;
  const entry = manifest.legislation;
  const bytes = new Uint8Array(await readFile(rawPath(raw, entry.pdf_url)));
  if (sha256(bytes) !== entry.pdf_sha256)
    throw new Error(
      "The archived PDF does not match the manifest; run --fetch.",
    );
  const parsed = parsePartFour(await pdfPageItems(bytes));
  if (parsed.articles.length !== entry.article_count)
    throw new Error("The article count differs from the manifest.");
  return { manifest, parsed };
}

const MONTHS = [
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
];
/** "Amended up to: March 22, 2024" in a WIPO Lex summary, as 2024-03-22. */
export function amendedUpTo(summary: string | null): string | null {
  const match = /Amended up to:\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})/.exec(
    summary ?? "",
  );
  const month = match ? MONTHS.indexOf((match[1] as string).toLowerCase()) : -1;
  if (!match || month < 0) return null;
  return `${match[3]}-${String(month + 1).padStart(2, "0")}-${(match[2] as string).padStart(2, "0")}`;
}

function writeDatabase(
  output: string,
  manifest: SourceManifest,
  parsed: ParsedPartFour,
  pick?: string[],
) {
  const db = new Database(output, { create: true, strict: true });
  try {
    db.exec("PRAGMA journal_mode = DELETE");
    db.exec(DDL);
    const insert = db.prepare(
      "INSERT INTO sections (statute, section_number, section_label, title, text, source_url, chapter, paragraph, subparagraph, repealed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    );
    const entry = manifest.legislation;
    const translation = amendedUpTo(entry.wipo_summary);
    const russian = amendedUpTo(manifest.latest_record.wipo_summary);
    let count = 0;
    db.transaction(() => {
      for (const article of parsed.articles) {
        if (pick && !pick.includes(article.section_number)) continue;
        insert.run(
          STATUTE,
          article.section_number,
          `Article ${article.section_number} ${SHORT_NAME}`,
          article.title,
          article.text,
          entry.details_url,
          article.chapter,
          article.paragraph,
          article.subparagraph,
          article.repealed ? 1 : 0,
        );
        count++;
      }
      const meta: [string, string][] = [
        ["schema_version", "1"],
        ["snapshot_date", manifest.retrieved_at.slice(0, 10)],
        [
          "source_version",
          `WIPO Lex ${entry.wipolex_id} English translation, amended up to ${translation ?? "unknown"}`,
        ],
        ["section_count", String(count)],
        ["retrieved_at", manifest.retrieved_at],
        ["translation_amended_up_to", translation ?? "unknown"],
        ["russian_amended_up_to", russian ?? "unknown"],
        [
          "version_note",
          `English translation as amended up to ${translation ?? "an unknown date"} (WIPO Lex ${entry.wipolex_id}). WIPO Lex's latest record (${manifest.latest_record.wipolex_id}) carries the Russian text amended up to ${russian ?? "an unknown date"} and no newer English text, so later amendments are not reflected. The Russian text controls.`,
        ],
        ["section_heading", parsed.section],
        ["repealed_chapters", JSON.stringify(parsed.repealed_chapters)],
        [
          "legislation",
          JSON.stringify({
            wipolex_id: entry.wipolex_id,
            details_url: entry.details_url,
            wipo_title: entry.wipo_title,
            wipo_summary: entry.wipo_summary,
            pdf_url: entry.pdf_url,
            pdf_last_modified: entry.pdf_last_modified,
            pdf_sha256: entry.pdf_sha256,
            retrieved_at: entry.retrieved_at,
            latest_record_url: manifest.latest_record.details_url,
            latest_record_summary: manifest.latest_record.wipo_summary,
          }),
        ],
      ];
      if (pick)
        meta.push(["fixture_subset_of", String(parsed.articles.length)]);
      const put = db.prepare("INSERT INTO meta (key, value) VALUES (?, ?)");
      for (const [key, value] of meta) put.run(key, value);
    })();
    db.exec("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')");
    db.exec("VACUUM");
    if (pick && count !== pick.length)
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
  parsed: ParsedPartFour,
  pick?: string[],
) {
  await mkdir(dirname(output), { recursive: true });
  const temporary = `${output}.building`;
  await rm(temporary, { force: true });
  try {
    const count = writeDatabase(temporary, manifest, parsed, pick);
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
    option("--raw") ?? join(root, ".data/rospatent_statutes/raw"),
  );
  const output = resolve(
    option("--output") ??
      join(root, ".data/rospatent_statutes/rospatent_statutes.db"),
  );
  if (args.includes("--fetch")) await fetchAll(raw);
  if (await exists(output))
    throw new Error(`${output} exists; choose a new --output.`);
  const { manifest, parsed } = await loadPartFour(raw);
  const count = await build(output, manifest, parsed);
  const bytes = new Uint8Array(await readFile(output));
  console.log(
    JSON.stringify(
      {
        output,
        articles: count,
        repealed: parsed.articles
          .filter((item) => item.repealed)
          .map((item) => item.section_number),
        repealed_chapters: parsed.repealed_chapters,
        bytes: bytes.byteLength,
        sha256: sha256(bytes),
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
        articles: fixtureCount,
        bytes: fixtureBytes.byteLength,
        sha256: sha256(fixtureBytes),
      }),
    );
  }
}

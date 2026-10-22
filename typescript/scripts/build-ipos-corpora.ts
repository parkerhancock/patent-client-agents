// Builds the two IPOS Singapore corpora (the IP statutes and the IPOS
// examination manuals) from official sources. Plain HTTP GETs with an honest
// user agent; no browser, cookies or challenge handling. Raw sources are
// archived under the ignored .data/ipos/sources/ and recorded (URL, retrieval
// time, SHA-256) in the committed references/ipos/sources.json.
//
// Usage (from typescript/):
//   bun scripts/build-ipos-corpora.ts --fetch      # download and archive, then build
//   bun scripts/build-ipos-corpora.ts              # build from the archive
//   bun scripts/build-ipos-corpora.ts --fixtures   # also rewrite the test fixtures
// Output: .data/ipos/build/ipos_statutes.db and ipos_manuals.db (schema
// version 1, DELETE journal mode). Package them with scripts/compress-corpus.ts.
//
// PDF text comes from pdfjs-dist (pinned in package.json), which reports font
// names, sizes and positions, so running headers, footnotes, headings and
// paragraph numbers can be told apart from body text.
import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { gunzipSync, gzipSync } from "node:zlib";
import {
  getDocument,
  version as pdfjsVersion,
} from "pdfjs-dist/legacy/build/pdf.mjs";

export const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
const root = join(import.meta.dir, "..");
const dataDir = join(root, ".data/ipos");
const sourcesDir = join(dataDir, "sources");
const buildDir = join(dataDir, "build");
const manifestPath = join(root, "references/ipos/sources.json");
const fixturesDir = join(root, "tests/fixtures/ipos");

const IPOS = "https://www.ipos.gov.sg";
const SSO = "https://sso.agc.gov.sg";
const WIPO_LEX = "https://www.wipo.int/wipolex/en/legislation/details";

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

/** One archived file. `path` is relative to .data/ipos/sources/. */
export interface SourceFile {
  path: string;
  url: string;
  retrieved_at: string;
  sha256: string;
  bytes: number;
  /** The link as the listing page gives it, when it redirected elsewhere. */
  listed_url?: string;
  /** For a manual split into chapter files: the chapter number, 0 for front matter. */
  chapter?: number;
}
export interface SourceDocument {
  id: string;
  title: string;
  /** What the text reflects, as the publisher states it. */
  version: string;
  publisher: string;
  /** The page that lists the document and states its version. */
  listing_url: string;
  files: SourceFile[];
}
export interface SourceManifest {
  description: string;
  access_notes: string[];
  user_agent: string;
  extractor: { pdf: string };
  documents: SourceDocument[];
}

// ---------------------------------------------------------------- fetching

const pause = (ms: number) => new Promise((done) => setTimeout(done, ms));

async function get(url: string): Promise<{ bytes: Uint8Array; url: string }> {
  let last: unknown;
  for (let attempt = 1; attempt <= 4; attempt++) {
    try {
      const response = await fetch(url, {
        headers: { "user-agent": USER_AGENT },
        redirect: "follow",
        signal: AbortSignal.timeout(120_000),
      });
      if (!response.ok)
        throw new Error(`GET ${url} returned ${response.status}.`);
      const bytes = new Uint8Array(await response.arrayBuffer());
      await pause(750);
      return { bytes, url: response.url || url };
    } catch (error) {
      last = error;
      console.warn(`attempt ${attempt} for ${url} failed: ${String(error)}`);
      await pause(5_000 * attempt);
    }
  }
  throw last;
}

const now = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
const utf8 = (bytes: Uint8Array) => new TextDecoder().decode(bytes);

async function archive(
  path: string,
  url: string,
  bytes: Uint8Array,
  extra: Partial<SourceFile> = {},
): Promise<SourceFile> {
  const target = join(sourcesDir, `${path}.gz`);
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, gzipSync(bytes, { level: 9 }));
  return {
    path,
    url,
    retrieved_at: now(),
    sha256: sha256(bytes),
    bytes: bytes.byteLength,
    ...extra,
  };
}

async function fetchFile(
  path: string,
  url: string,
  extra: Partial<SourceFile> = {},
) {
  console.log(`GET ${url}`);
  const response = await get(url);
  if (!/^%PDF-/.test(utf8(response.bytes.slice(0, 5))))
    throw new Error(`${url} did not return a PDF.`);
  return archive(path, response.url, response.bytes, {
    ...(response.url !== url ? { listed_url: url } : {}),
    ...extra,
  });
}

/** A listing page as text, after checking it still names the document. */
async function listing(url: string, needles: string[]) {
  const page = utf8((await get(url)).bytes);
  const flat = decode(page).replace(/\s+/g, " ");
  for (const needle of needles)
    if (!flat.includes(needle))
      throw new Error(
        `${url} no longer contains '${needle}'; review the source before rebuilding.`,
      );
  return page;
}

/** Anchors (href, text) of an HTML page, in document order. */
export function anchors(html: string) {
  return [
    ...html.matchAll(/<a\s[^>]*?href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g),
  ].map((match) => ({
    href: decode(match[1] as string),
    text: clean(decode((match[2] as string).replace(/<[^>]+>/g, " "))),
  }));
}

/** WIPO Lex serves its PDFs through short-lived signed links on the entry page. */
async function fetchWipoLex(path: string, id: string, pdfName: string) {
  const details = utf8((await get(`${WIPO_LEX}/${id}`)).bytes)
    .replace(/&#x3D;/g, "=")
    .replace(/&amp;/g, "&");
  const signed = new RegExp(
    `https://wipolex-res\\.wipo\\.int/edocs/lexdocs/laws/en/sg/${pdfName}\\?[^"' ]+Signature=[^"' ]+`,
  ).exec(details)?.[0];
  if (!signed) throw new Error(`WIPO Lex ${id} no longer links ${pdfName}.`);
  console.log(`GET ${signed.split("?")[0]} (signed)`);
  const { bytes } = await get(signed);
  return archive(
    path,
    `https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/sg/${pdfName}`,
    bytes,
  );
}

/** The four Acts: key, short name, SSO Act code, WIPO Lex entry and PDF. */
export const STATUTES = [
  {
    id: "patents",
    short_name: "Patents Act",
    title: "Patents Act 1994 (2020 Revised Edition)",
    sso: "PA1994",
    wipo: "23204",
    pdf: "sg198en_1.pdf",
  },
  {
    id: "tm",
    short_name: "Trade Marks Act",
    title: "Trade Marks Act 1998 (2020 Revised Edition)",
    sso: "TMA1998",
    wipo: "23203",
    pdf: "sg197en_1.pdf",
  },
  {
    id: "designs",
    short_name: "Registered Designs Act",
    title: "Registered Designs Act 2000 (2020 Revised Edition)",
    sso: "RDA2000",
    wipo: "23205",
    pdf: "sg199en_1.pdf",
  },
  {
    id: "copyright",
    short_name: "Copyright Act",
    title: "Copyright Act 2021",
    sso: "CA2021",
    wipo: "23201",
    pdf: "sg195en_1.pdf",
  },
] as const;

export const MANUALS = {
  peg: {
    short_name: "PEG",
    title: "IPOS Examination Guidelines for Patent Applications",
    listing_url: `${IPOS}/about-ip/patents/guides/`,
    link_text: "Examination Guidelines for Patent Applications",
    version: "Version Oct 2023 (released 11 October 2023)",
    needle: "Version: Oct 2023",
  },
  tm: {
    short_name: "TM Work Manual",
    title: "IPOS Trade Marks Work Manual",
    listing_url: `${IPOS}/about-ip/trade-marks/tm-guides/`,
    link_text: "Cover Page and Contents",
    version:
      "Chapters as published on the IPOS Trade Marks guides page; each chapter carries its own version (recorded per row)",
    needle: "",
  },
  designs: {
    short_name: "Designs Guidelines",
    title: "IPOS Registered Designs — Guidelines for Non-Physical Products",
    listing_url: `${IPOS}/about-ip/designs/guides/`,
    link_text: "Registered Designs - Guidelines for Non-Physical Products",
    version: "Version Jun 2022 (released 2 June 2022)",
    needle: "Jun 2022",
  },
} as const;
export type ManualId = keyof typeof MANUALS;

/** What happened with the sources Python used when this builder was written. */
const ACCESS_NOTES = [
  "2026-10-22: sso.agc.gov.sg (Singapore Statutes Online, CloudFront) answered HTTP 403 'Request blocked' to plain GETs with this user agent for /Act/PA1994, /Act/PA1994?WholeDoc=1, the site root and robots.txt, and to curl's default user agent. No other access method was tried. The Acts therefore come from WIPO Lex, which republishes the SSO PDF of each Act ('Informal Consolidation – version in force from 9/3/2025').",
  "2026-10-22: the three www.ipos.gov.sg /docs/default-source/... manual PDF paths that Python's builder used answer HTTP 404; IPOS now serves its documents from isomer-user-content.by.gov.sg and file.go.gov.sg, linked from the guides pages recorded as listing_url.",
  "The Trade Marks Work Manual is published as a cover file and 22 chapter PDFs, not one PDF.",
  "IPOS no longer publishes a Registered Designs (Industrial Designs) Work Manual: the Designs guides page lists an infopack, information notes and 'Registered Designs - Guidelines for Non-Physical Products', the only examination guidance with numbered paragraphs, which is used as the designs manual.",
];

async function fetchAll(): Promise<SourceManifest> {
  const documents: SourceDocument[] = [];
  // WIPO Lex's Singapore profile names each entry with its edition and amendment date.
  const profile = anchors(
    await listing("https://www.wipo.int/wipolex/en/members/profile/SG", [
      "Patents Act 1994",
    ]),
  );
  for (const act of STATUTES) {
    const entry = profile.find((a) =>
      a.href.endsWith(`/legislation/details/${act.wipo}`),
    );
    const name = act.title.replace(/ \(2020 Revised Edition\)$/, "");
    if (!entry?.text.startsWith(name))
      throw new Error(`WIPO Lex no longer lists ${name} as entry ${act.wipo}.`);
    documents.push({
      id: `act_${act.id}`,
      title: act.title,
      version: entry.text.replace(/,\s*\(/, " ("),
      publisher:
        "Attorney-General's Chambers, Singapore (Singapore Statutes Online PDF), republished by WIPO Lex",
      listing_url: `${WIPO_LEX}/${act.wipo}`,
      files: [await fetchWipoLex(`statutes/${act.id}.pdf`, act.wipo, act.pdf)],
    });
  }

  for (const [id, manual] of Object.entries(MANUALS) as [
    ManualId,
    (typeof MANUALS)[ManualId],
  ][]) {
    const page = await listing(manual.listing_url, [manual.link_text]);
    const links = anchors(page).filter((a) =>
      /\.pdf$|go\.gov\.sg/.test(a.href),
    );
    const files: SourceFile[] = [];
    if (id === "tm") {
      const start = links.findIndex((a) => a.text.startsWith(manual.link_text));
      for (const link of links.slice(start)) {
        const chapter = /^Chapter (\d+)\b/.exec(link.text)?.[1];
        if (!chapter && files.length) break;
        const number = chapter ? Number(chapter) : 0;
        files.push(
          await fetchFile(
            `manuals/tm/${String(number).padStart(2, "0")}.pdf`,
            link.href,
            { chapter: number },
          ),
        );
      }
      if (files.length !== 23)
        throw new Error(
          `TM Work Manual: expected the cover and 22 chapters, found ${files.length} files.`,
        );
    } else {
      const link = links.find((a) => a.text.startsWith(manual.link_text));
      if (!link)
        throw new Error(
          `${manual.listing_url}: no '${manual.link_text}' link.`,
        );
      files.push(await fetchFile(`manuals/${id}.pdf`, link.href));
    }
    documents.push({
      id: `manual_${id}`,
      title: manual.title,
      version: manual.version,
      publisher: "Intellectual Property Office of Singapore (ipos.gov.sg)",
      listing_url: manual.listing_url,
      files,
    });
  }

  return {
    description:
      "Official sources of the IPOS Singapore statutes and manuals corpora. Raw files are archived gzipped under typescript/.data/ipos/sources/<path>.gz (not committed); sha256 and bytes are of the raw file.",
    access_notes: ACCESS_NOTES,
    user_agent: USER_AGENT,
    extractor: { pdf: `pdfjs-dist ${pdfjsVersion}` },
    documents,
  };
}

async function readSource(file: SourceFile): Promise<Uint8Array> {
  const bytes = new Uint8Array(
    gunzipSync(await readFile(join(sourcesDir, `${file.path}.gz`))),
  );
  if (sha256(bytes) !== file.sha256)
    throw new Error(
      `Archived ${file.path} does not match its manifest SHA-256.`,
    );
  return bytes;
}

// ---------------------------------------------------------------- text helpers

const ENTITIES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
  ndash: "–",
  mdash: "—",
};
export function decode(value: string): string {
  return value.replace(
    /&(#x[\da-f]+|#\d+|[a-z]+);/gi,
    (match, name: string) => {
      if (name[0] === "#")
        return String.fromCodePoint(
          name[1] === "x" || name[1] === "X"
            ? Number.parseInt(name.slice(2), 16)
            : Number.parseInt(name.slice(1), 10),
        );
      return ENTITIES[name.toLowerCase()] ?? match;
    },
  );
}
/** Collapse whitespace (including NBSP) to single spaces; non-breaking hyphens become hyphens. */
export const clean = (value: string) =>
  value
    .replace(/­/g, "")
    .replace(/‑/g, "-")
    .replace(/[\s ]+/g, " ")
    .trim();
/** Upper-case letters and digits only, for matching headings across layouts. */
const key = (value: string) => value.toUpperCase().replace(/[^A-Z0-9]/g, "");

// ---------------------------------------------------------------- PDF lines

interface Item {
  str: string;
  x: number;
  end: number;
  y: number;
  size: number;
  font: string;
}
export interface Line {
  page: number;
  y: number;
  x: number;
  size: number;
  text: string;
  items: Item[];
}

/** Text lines per page, top to bottom, with each item's font name and size. */
export async function pdfLines(bytes: Uint8Array): Promise<Line[][]> {
  const doc = await getDocument({
    data: bytes.slice(),
    verbosity: 0,
    isEvalSupported: false,
    useSystemFonts: false,
  }).promise;
  const pages: Line[][] = [];
  try {
    for (let number = 1; number <= doc.numPages; number++) {
      const page = await doc.getPage(number);
      const content = await page.getTextContent();
      const items: Item[] = [];
      for (const raw of content.items) {
        if (!("str" in raw) || !raw.str) continue;
        const [, , c, d, x, y] = raw.transform as number[];
        items.push({
          str: raw.str,
          x: x as number,
          end: (x as number) + raw.width,
          y: y as number,
          size: Math.round(Math.hypot(c as number, d as number) * 10) / 10,
          font: raw.fontName,
        });
      }
      items.sort((a, b) => b.y - a.y || a.x - b.x);
      const lines: Line[] = [];
      for (const item of items) {
        const line = lines.at(-1);
        if (line && Math.abs(line.y - item.y) <= 2.5) line.items.push(item);
        else
          lines.push({
            page: number,
            y: item.y,
            x: 0,
            size: 0,
            text: "",
            items: [item],
          });
      }
      for (const line of lines) {
        line.items.sort((a, b) => a.x - b.x);
        line.items = line.items.filter((item) => item.str.trim());
        line.x = line.items[0]?.x ?? 0;
        line.size = Math.max(0, ...line.items.map((item) => item.size));
        line.text = joinItems(line.items);
      }
      pages.push(lines.filter((line) => line.text));
      page.cleanup();
    }
  } finally {
    await doc.destroy();
  }
  return pages;
}

function joinItems(items: Item[]): string {
  let out = "";
  let prevEnd = Number.NEGATIVE_INFINITY;
  for (const item of items) {
    if (
      out &&
      item.x - prevEnd > 1.5 &&
      !/\s$/.test(out) &&
      !/^\s/.test(item.str)
    )
      out += " ";
    out += item.str;
    prevEnd = item.end;
  }
  return clean(out);
}

/**
 * Drop running headers and footers: lines in the top or bottom band whose
 * text, digits removed, repeats on at least a third of the pages.
 */
function stripRunning(pages: Line[][]): Line[][] {
  const shape = (line: Line) =>
    line.text.replace(/\d+/g, "#").replace(/\s+/g, "");
  const counts = new Map<string, number>();
  for (const lines of pages) {
    const seen = new Set<string>();
    for (const line of [...lines.slice(0, 3), ...lines.slice(-3)])
      seen.add(shape(line));
    for (const value of seen) counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  const limit = Math.max(3, pages.length / 3);
  return pages.map((lines) =>
    lines.filter((line, index) => {
      const edge = index < 3 || index >= lines.length - 3;
      return !(edge && (counts.get(shape(line)) ?? 0) >= limit);
    }),
  );
}

/** The most frequent value (by item count) of a per-item property. */
function mode<T>(lines: Line[], pick: (item: Item) => T): T {
  const counts = new Map<T, number>();
  for (const line of lines)
    for (const item of line.items)
      counts.set(pick(item), (counts.get(pick(item)) ?? 0) + item.str.length);
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] as T;
}

/** Join wrapped lines into paragraphs; `starts` decides which lines open a paragraph. */
function paragraphs(
  lines: Line[],
  starts: (line: Line, prev: Line | undefined) => boolean,
): string {
  const out: string[] = [];
  let prev: Line | undefined;
  for (const line of lines) {
    const last = out.at(-1);
    if (last === undefined || starts(line, prev)) out.push(line.text);
    else if (/[A-Za-z]-$/.test(last) && /^[a-z]/.test(line.text))
      out[out.length - 1] = last + line.text;
    else out[out.length - 1] = `${last} ${line.text}`;
    prev = line;
  }
  return out.join("\n");
}

const sentence = (value: string) =>
  /[a-z]/.test(value) ? value : value.charAt(0) + value.slice(1).toLowerCase();

// ---------------------------------------------------------------- statutes

export interface StatuteRow {
  statute: string;
  short_name: string;
  statute_title: string;
  section_label: string;
  title: string | null;
  breadcrumb: string;
  source_url: string;
  source_version: string | null;
  sso_url: string;
  text: string;
}

interface TocEntry {
  label: string;
  title: string;
  part: string | null;
  division: string | null;
}

const SECTION_NUMBER = /^(\d+[A-Z]{0,3})\.$/;
const PART = /^PART (\d+[A-Z]*|\?\?)$/;
const SCHEDULE_HEAD =
  /^(THE|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH) SCHEDULE$/;
const isCaps = (text: string) => /[A-Z]/.test(text) && !/[a-z]/.test(text);

/**
 * The arrangement of sections: label, title, and the Part and Division each
 * section sits in. Section entries are in the entry font at the left; wrapped
 * titles continue in that font; Division and other group headings use
 * another font and are centred.
 */
function parseArrangement(lines: Line[]): {
  entries: TocEntry[];
  schedules: string[];
  headings: string[];
} {
  const entries: TocEntry[] = [];
  const schedules: string[] = [];
  const headings: string[] = [];
  const numbered = lines.filter((line) =>
    SECTION_NUMBER.test(line.items[0]?.str.trim() ?? ""),
  );
  const entryFont = mode(numbered, (item) => item.font);
  const entrySize = mode(numbered, (item) => item.size);
  let part: string | null = null;
  let partTitle: string[] = [];
  let division: string[] = [];
  let subdivision: string[] = [];
  let titleX = 0;
  let state: "part" | "entry" | "division" | "subdivision" | "other" = "other";
  const partName = () => {
    if (!part) return null;
    const title = partTitle.length ? partTitle.join(" ") : "";
    // The Registered Designs Act's arrangement and body both print "PART ??".
    return part === "??"
      ? title || null
      : `Part ${part}${title ? ` ${title}` : ""}`;
  };
  const flush = () => {
    if (state === "part" && partTitle.length)
      headings.push(partTitle.join(" "));
    if (state === "division") headings.push(division.join(" "));
    if (state === "subdivision") headings.push(subdivision.join(" "));
  };
  for (const line of lines) {
    const first = line.items[0]?.str.trim() ?? "";
    const partMatch = PART.exec(line.text);
    if (partMatch) {
      flush();
      part = partMatch[1] as string;
      partTitle = [];
      division = [];
      subdivision = [];
      state = "part";
    } else if (line.text === "Section") {
      flush();
      state = "other";
    } else if (
      SECTION_NUMBER.test(first) &&
      line.items[0]?.font === entryFont
    ) {
      flush();
      entries.push({
        label: (SECTION_NUMBER.exec(first) as RegExpExecArray)[1] as string,
        title: clean(
          line.items
            .slice(1)
            .map((item) => item.str)
            .join(" "),
        ),
        part: partName(),
        division:
          [division.join(" "), subdivision.join(" ")]
            .filter(Boolean)
            .join(" › ") || null,
      });
      titleX = line.items[1]?.x ?? line.x;
      state = "entry";
    } else if (/^Subdivision\b/.test(line.text)) {
      flush();
      subdivision = [line.text];
      state = "subdivision";
    } else if (
      /Schedule\b/.test(line.text) &&
      line.items[0]?.font === entryFont &&
      !isCaps(line.text)
    ) {
      flush();
      schedules.push(line.text);
      state = "other";
    } else if (state === "part" && isCaps(line.text)) {
      partTitle.push(line.text);
    } else if (
      state === "entry" &&
      line.items.every((item) => item.font === entryFont) &&
      Math.abs(line.x - titleX) < 15 &&
      line.size >= entrySize - 0.5
    ) {
      const last = entries.at(-1) as TocEntry;
      last.title = clean(`${last.title} ${line.text}`);
    } else if (
      (state === "subdivision" || state === "division") &&
      line.size >= entrySize - 0.5 &&
      !/^\d+$/.test(line.text)
    ) {
      // A wrapped Division or Subdivision heading.
      (state === "division" ? division : subdivision).push(line.text);
    } else if (line.items.every((item) => item.font !== entryFont)) {
      flush();
      division = [line.text];
      subdivision = [];
      state = "division";
    }
  }
  flush();
  return { entries, schedules, headings: headings.map(key) };
}

/** "Short title.—(1)" paragraphs: subsections, items, definitions, notes and amendment references. */
const STATUTE_PARAGRAPH =
  /^(?:\((?:[a-zA-Z]{1,5}|\d+[A-Z]{0,3})\)|\[|“|"|—|Explanation|Illustration|Provided)/;

/**
 * Sections (and Schedules) of an Act from the SSO PDF of the 2020 Revised
 * Edition consolidation. The arrangement of sections gives the expected
 * order, titles, Parts and Divisions; each section starts at a line whose
 * first item is its number in the heading font. Running headers, the
 * Part/Division/section headings that precede the next section, and the
 * legislative history after the Schedules are dropped.
 */
export async function parseSsoPdf(
  bytes: Uint8Array,
  act: (typeof STATUTES)[number],
  sourceUrl: string,
): Promise<{ rows: StatuteRow[]; version: string }> {
  const raw = await pdfLines(bytes);
  const footer = raw
    .flat()
    .map((line) =>
      /version in force from (\d+)\/(\d+)\/(\d{4})/.exec(line.text),
    )
    .find(Boolean);
  if (!footer)
    throw new Error(`${act.short_name}: no 'version in force from' footer.`);
  const inForce = `${footer[3]}-${(footer[2] as string).padStart(2, "0")}-${(footer[1] as string).padStart(2, "0")}`;
  const lines = stripRunning(raw).flat();
  const start = lines.findIndex((line) => /^An Act to /.test(line.text));
  if (start < 0) throw new Error(`${act.short_name}: no long title.`);
  const { entries, schedules, headings } = parseArrangement(
    lines.slice(0, start),
  );
  const end = lines.findIndex(
    (line, index) =>
      index > start &&
      (SCHEDULE_HEAD.test(line.text) || line.text === "LEGISLATIVE HISTORY"),
  );
  const body = lines.slice(start, end < 0 ? undefined : end);
  const bodyFont = mode(body, (item) => item.font);
  const bodySize = mode(body, (item) => item.size);
  const left = Math.min(...body.map((line) => line.x));
  const pageLeft = new Map<number, number>();
  for (const line of body)
    pageLeft.set(
      line.page,
      Math.min(pageLeft.get(line.page) ?? line.x, line.x),
    );

  // Section starts, in arrangement order.
  const starts: number[] = [];
  let cursor = 0;
  for (const entry of entries) {
    let found = -1;
    for (let i = cursor; i < body.length; i++) {
      const line = body[i] as Line;
      const first = line.items[0];
      if (
        first &&
        first.str.trim() === `${entry.label}.` &&
        first.font !== bodyFont &&
        line.x <= left + 20
      ) {
        found = i;
        break;
      }
    }
    if (found < 0)
      throw new Error(
        `${act.short_name}: section ${entry.label} not found in the body.`,
      );
    starts.push(found);
    cursor = found + 1;
  }
  const headingFont = mode(
    starts.map((index) => ({
      ...(body[index] as Line),
      items: (body[index] as Line).items.slice(0, 1),
    })),
    (item) => item.font,
  );

  const isReference = (line: Line) => /^\[[^\]]*\]$/.test(line.text);
  /** Headings belong to what follows them, so trailing ones are cut from a section. */
  const isHeading = (line: Line) =>
    PART.test(line.text) ||
    (isCaps(line.text) && line.text.length > 3) ||
    (/^(?:Sub)?[Dd]ivision \S+ — /.test(line.text) &&
      (line.x > left + 20 || headings.includes(key(line.text)))) ||
    // The wrapped remainder of a centred Division or Subdivision heading.
    (line.x > (pageLeft.get(line.page) ?? left) + 12 &&
      key(line.text).length >= 6 &&
      headings.some((heading) => heading.includes(key(line.text)))) ||
    (line.items.every((item) => item.font !== bodyFont) &&
      line.size >= bodySize - 0.5 &&
      !/^\[[^\]]*\]$/.test(line.text)) ||
    line.items.every((item) => item.font === headingFont);

  const rows: StatuteRow[] = [];
  const base = {
    statute: act.id,
    short_name: act.short_name,
    statute_title: act.title,
    source_url: sourceUrl,
  };
  const sso = `${SSO}/Act/${act.sso}`;
  entries.forEach((entry, index) => {
    const from = starts[index] as number;
    let to =
      index + 1 < starts.length ? (starts[index + 1] as number) : body.length;
    // A Part or Division heading may carry its own amendment reference ("[34/2018]").
    for (;;) {
      let k = to;
      while (k > from + 1 && isReference(body[k - 1] as Line)) k--;
      if (k > from + 1 && isHeading(body[k - 1] as Line)) to = k - 1;
      else break;
    }
    const text = paragraphs(
      body.slice(from, to),
      (line, prev) =>
        prev === undefined ||
        STATUTE_PARAGRAPH.test(line.text) ||
        line.size < bodySize - 1,
    );
    rows.push({
      ...base,
      section_label: entry.label,
      title: entry.title.replace(/^\[\s*(.*?)\s*\]$/, "[$1]") || null,
      breadcrumb: [
        act.short_name,
        entry.part,
        entry.division,
        `Section ${entry.label}`,
      ]
        .filter(Boolean)
        .join(" › "),
      source_version: `2020 Revised Edition, informal consolidation in force from ${inForce}`,
      sso_url: `${sso}?ProvIds=pr${entry.label}-#pr${entry.label}-`,
      text,
    });
  });

  // Schedules, up to the legislative history.
  if (end >= 0) {
    const rest = lines.slice(end);
    const stop = rest.findIndex((line) => line.text === "LEGISLATIVE HISTORY");
    const tail = rest.slice(0, stop < 0 ? undefined : stop);
    const heads = tail
      .map((line, index) => (SCHEDULE_HEAD.test(line.text) ? index : -1))
      .filter((index) => index >= 0);
    heads.forEach((head, index) => {
      const name = (tail[head] as Line).text;
      const label =
        name === "THE SCHEDULE"
          ? "Schedule"
          : `${sentence(name.split(" ")[0] as string)} Schedule`;
      const chunk = tail
        .slice(head + 1, heads[index + 1] ?? tail.length)
        .filter(
          (line) => !/^[A-Z ]+SCHEDULE\s*—\s*continued$/i.test(line.text),
        );
      const listed = schedules.find((value) =>
        key(value).startsWith(key(label)),
      );
      const fromToc = listed?.split(/\s+—\s+/)[1];
      const caps = chunk.find(
        (line) => isCaps(line.text) && line.size >= bodySize - 2.5,
      );
      rows.push({
        ...base,
        section_label: label,
        title: fromToc ? clean(fromToc) : caps ? caps.text : null,
        breadcrumb: `${act.short_name} › ${label}`,
        source_version: `2020 Revised Edition, informal consolidation in force from ${inForce}`,
        sso_url: sso,
        text: paragraphs(chunk, (line, prev) => {
          const heading = (value: Line) =>
            isCaps(value.text) ||
            value.items.every((item) => item.font === headingFont);
          return (
            prev === undefined ||
            heading(line) ||
            heading(prev) ||
            STATUTE_PARAGRAPH.test(line.text) ||
            /^\d+[A-Z]?\.(?:\s|—)/.test(line.text)
          );
        }),
      });
    });
  }
  return { rows, version: inForce };
}

// ---------------------------------------------------------------- manuals

export interface ManualRow {
  manual: string;
  short_name: string;
  manual_title: string;
  section_label: string;
  title: string | null;
  breadcrumb: string;
  source_url: string;
  source_version: string | null;
  text: string;
}

/** Remove superscript markers and footnote lines (items below `min` points). */
function dropSmall(lines: Line[], min: number): Line[] {
  const out: Line[] = [];
  for (const line of lines) {
    const items = line.items.filter((item) => item.size >= min);
    if (!items.length) continue;
    out.push({
      ...line,
      items,
      x: items[0]?.x ?? line.x,
      text: joinItems(items),
    });
  }
  return out;
}

/** Typical baseline distance between consecutive body lines. */
function lineGap(lines: Line[], size: number): number {
  const counts = new Map<number, number>();
  for (let i = 1; i < lines.length; i++) {
    const a = lines[i - 1] as Line;
    const b = lines[i] as Line;
    if (
      a.page !== b.page ||
      Math.abs(a.size - size) > 0.6 ||
      Math.abs(b.size - size) > 0.6
    )
      continue;
    const gap = Math.round(a.y - b.y);
    if (gap > 0) counts.set(gap, (counts.get(gap) ?? 0) + 1);
  }
  return (
    [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? size * 1.2
  );
}

/** Paragraph breaks at larger vertical gaps, page starts and list markers. */
function manualText(lines: Line[], gap: number): string {
  return paragraphs(lines, (line, prev) => {
    if (!prev) return true;
    if (prev.page !== line.page)
      return /^(?:\(?[a-z\divx]{1,4}\)|•|▪|-)\s/.test(line.text);
    return (
      prev.y - line.y > gap * 1.35 ||
      /^(?:\(?[a-z\divx]{1,4}\)|•|▪|–)\s/.test(line.text)
    );
  });
}

const LEADER = /(?:\s*\.){4,}|…{2,}/;
const tocTitle = (value: string) =>
  clean(value.split(LEADER)[0] as string).replace(/\s+\d+$/, "");

/**
 * A manual whose cite-bearing unit is the numbered paragraph ("8.12"): the
 * IPOS Examination Guidelines and the Registered Designs guidelines. Chapter
 * titles come from the table of contents; headings (lines set larger than
 * the body) give each paragraph its title and breadcrumb; footnotes and
 * superscript markers (below 85% of the body size) are dropped.
 */
export async function parseParagraphManual(
  bytes: Uint8Array,
  manual: ManualId,
  sourceUrl: string,
): Promise<ManualRow[]> {
  const info = MANUALS[manual];
  const all = stripRunning(await pdfLines(bytes)).flat();
  const bodySize = mode(all, (item) => item.size);
  const lines = dropSmall(all, bodySize * 0.85).filter(
    (line) => !/^Version:\s*\w+\s*\d{4}\s+Page/.test(line.text),
  );
  const chapters = new Map<string, string>();
  for (const line of lines) {
    if (!LEADER.test(line.text)) continue;
    const match = /^(\d+)\.\s+(.+)$/.exec(line.text);
    if (match && !chapters.has(match[1] as string))
      chapters.set(match[1] as string, tocTitle(match[2] as string));
  }
  const gap = lineGap(lines, bodySize);
  const isPara = /^(\d+)\.(\d+)$/;
  const rows: ManualRow[] = [];
  let chapter = 0;
  let number = 0;
  let current: {
    label: string;
    lines: Line[];
    title: string | null;
    trail: string[];
  } | null = null;
  const headings: { size: number; text: string }[] = [];
  let lastHeading: Line | undefined;
  const finish = () => {
    if (!current) return;
    const text = manualText(current.lines, gap);
    const chapterTitle = chapters.get(current.label.split(".")[0] as string);
    rows.push({
      manual,
      short_name: info.short_name,
      manual_title: info.title,
      section_label: current.label,
      title: current.title,
      breadcrumb: [
        info.short_name,
        `Chapter ${current.label.split(".")[0]}${chapterTitle ? ` ${chapterTitle}` : ""}`,
        ...current.trail,
        current.label,
      ].join(" › "),
      source_url: `${sourceUrl}#page=${current.lines[0]?.page ?? 1}`,
      source_version: info.version,
      text,
    });
  };
  for (const line of lines) {
    const first = line.items[0]?.str.trim() ?? "";
    const para = isPara.exec(first);
    if (
      para &&
      line.size <= bodySize + 0.5 &&
      ((Number(para[1]) === chapter && Number(para[2]) === number + 1) ||
        (Number(para[1]) > chapter && Number(para[2]) === 1))
    ) {
      finish();
      chapter = Number(para[1]);
      number = Number(para[2]);
      const trail = headings
        .filter((heading) => !/^\d+\.\s/.test(heading.text))
        .map((heading) => heading.text);
      current = {
        label: `${chapter}.${number}`,
        title: trail.at(-1) ?? chapters.get(String(chapter)) ?? null,
        trail,
        lines: [
          {
            ...line,
            items: line.items.slice(1),
            text: joinItems(line.items.slice(1)),
          },
        ],
      };
      lastHeading = undefined;
      continue;
    }
    if (
      line.size >= bodySize + 1.5 &&
      line.size <= 20 &&
      !LEADER.test(line.text)
    ) {
      // A heading; consecutive lines of one heading are joined. A numbered
      // chapter heading ("8. PATENTABLE SUBJECT MATTER AND …") names its chapter.
      if (
        lastHeading &&
        lastHeading.size === line.size &&
        lastHeading.page === line.page
      ) {
        const top = headings.at(-1) as { size: number; text: string };
        top.text = clean(`${top.text} ${line.text}`);
        const numbered = /^(\d+)\.\s+(.+)$/.exec(top.text);
        if (numbered)
          chapters.set(numbered[1] as string, numbered[2] as string);
      } else {
        const numbered = /^(\d+)\.\s+(.+)$/.exec(line.text);
        if (numbered)
          chapters.set(numbered[1] as string, numbered[2] as string);
        while (
          headings.length &&
          (headings.at(-1) as { size: number }).size <= line.size
        )
          headings.pop();
        headings.push({ size: line.size, text: line.text });
      }
      lastHeading = line;
      continue;
    }
    lastHeading = undefined;
    current?.lines.push(line);
  }
  finish();
  return rows;
}

/** "Chapter N: Title" lines of the TM Work Manual's cover and contents file. */
export async function parseTmCover(
  bytes: Uint8Array,
): Promise<Map<number, string>> {
  const titles = new Map<number, string>();
  let last: number | undefined;
  for (const line of (await pdfLines(bytes)).flat()) {
    const match = /^Chapter (\d+):\s*(.+)$/.exec(line.text);
    if (match) {
      last = Number(match[1]);
      titles.set(last, clean(match[2] as string));
    } else if (last !== undefined && line.x > 80 && /^[a-z]/.test(line.text)) {
      titles.set(last, `${titles.get(last)} ${line.text}`);
    } else last = undefined;
  }
  return titles;
}

interface TmEntry {
  number: string;
  title: string;
}

/**
 * One TM Work Manual chapter. Its own contents list gives the numbered
 * headings ("5", "5.2", "5.2.5.3.1") in order; each is found in the body by
 * number and the start of its title, and owns the text up to the next one.
 * Rows are labelled chapter.heading ("7.5.2").
 */
export async function parseTmChapter(
  bytes: Uint8Array,
  chapter: number,
  chapterTitle: string,
  sourceUrl: string,
): Promise<{ rows: ManualRow[]; version: string; missing: string[] }> {
  const info = MANUALS.tm;
  const raw = await pdfLines(bytes);
  const version = raw
    .flat()
    .map((line) =>
      /Version\s*([\d.]+)\s*\(\s*([A-Za-z]+\s*\/?\s*\d{4})\s*\)/.exec(
        line.text.replace(/\s+/g, " "),
      ),
    )
    .find(Boolean);
  if (!version)
    throw new Error(`TM Work Manual chapter ${chapter}: no version line.`);
  const versionLabel = `Version ${version[1]} (${clean((version[2] as string).replace(/\s*\/\s*/, " "))})`;
  const all = stripRunning(raw)
    .flat()
    .filter(
      (line) =>
        !/^V\s?ersion\b.*Intellectual Property Office of Singapore$/.test(
          line.text,
        ),
    );
  const bodySize = mode(all, (item) => item.size);
  // The contents list keeps small capitals (set below the body size).
  const contents = all.findIndex((line) => /^Contents\b/.test(line.text));
  if (contents < 0)
    throw new Error(`TM Work Manual chapter ${chapter}: no contents list.`);
  const entries: TmEntry[] = [];
  const number = /^(\d+(?:\s*\.\s*\d+)*)\s*\.?\s+(\S.*)$/;
  let index = contents + 1;
  for (; index < all.length; index++) {
    const line = all[index] as Line;
    const match = number.exec(line.text);
    const firstKey = entries[0]
      ? key(`${entries[0].number}${entries[0].title}`).slice(0, 14)
      : "";
    if (
      firstKey &&
      key(line.text).startsWith(firstKey) &&
      !LEADER.test(line.text) &&
      !/\s\d+$/.test(line.text)
    )
      break;
    if (match && !/^\d+$/.test(line.text)) {
      entries.push({
        number: (match[1] as string).replace(/\s+/g, ""),
        title: tocTitle(match[2] as string),
      });
    } else if (
      entries.length &&
      !/^\d+$/.test(line.text) &&
      !/^\(/.test(line.text)
    ) {
      const last = entries.at(-1) as TmEntry;
      last.title = clean(`${last.title} ${tocTitle(line.text)}`);
    }
  }
  const body = dropSmall(all.slice(index), bodySize * 0.85);
  const gap = lineGap(body, bodySize);
  const found: { entry: TmEntry; start: number; skip: number }[] = [];
  const missing: string[] = [];
  let cursor = 0;
  for (const entry of entries) {
    const want = key(entry.number) + key(entry.title).slice(0, 12);
    let hit = -1;
    for (let i = cursor; i < body.length; i++)
      if (key((body[i] as Line).text).startsWith(want)) {
        hit = i;
        break;
      }
    if (hit < 0) {
      missing.push(entry.number);
      continue;
    }
    // Skip the wrapped remainder of a long heading.
    const full = key(entry.number + entry.title);
    let seen = key((body[hit] as Line).text);
    let skip = 1;
    while (hit + skip < body.length && seen.length < full.length) {
      const next = key((body[hit + skip] as Line).text);
      if (!full.startsWith(seen + next)) break;
      seen += next;
      skip++;
    }
    found.push({ entry, start: hit, skip });
    cursor = hit + skip;
  }
  // Body headings keep acronyms ("IR") that small-capital contents lines lose.
  const titles = new Map(
    found.map(({ entry, start, skip }) => {
      const heading = clean(
        body
          .slice(start, start + skip)
          .map((line) => line.text)
          .join(" "),
      ).replace(/^\d+(?:\s*\.\s*\d+)*\s*\.?\s*/, "");
      return [entry.number, heading || entry.title];
    }),
  );
  const rows: ManualRow[] = [];
  found.forEach(({ entry, start, skip }, i) => {
    const end = found[i + 1]?.start ?? body.length;
    const chunk = body.slice(start + skip, end);
    const text = manualText(chunk, gap);
    if (!text) return;
    const parts = entry.number.split(".");
    const trail = parts.map((_, depth) => {
      const n = parts.slice(0, depth + 1).join(".");
      return `${chapter}.${n} ${titles.get(n) ?? ""}`.trim();
    });
    rows.push({
      manual: "tm",
      short_name: info.short_name,
      manual_title: info.title,
      section_label: `${chapter}.${entry.number}`,
      title: titles.get(entry.number) ?? null,
      breadcrumb: [
        info.short_name,
        `Chapter ${chapter} ${chapterTitle}`,
        ...trail,
      ].join(" › "),
      source_url: `${sourceUrl}#page=${(body[start] as Line).page}`,
      source_version: versionLabel,
      text,
    });
  });
  return { rows, version: versionLabel, missing };
}

// ---------------------------------------------------------------- database

const STATUTES_DDL = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections (
    rowid          INTEGER PRIMARY KEY,
    statute        TEXT NOT NULL,
    short_name     TEXT NOT NULL,
    statute_title  TEXT NOT NULL,
    section_label  TEXT NOT NULL,
    title          TEXT,
    breadcrumb     TEXT,
    source_url     TEXT NOT NULL,
    source_version TEXT,
    text           TEXT NOT NULL,
    sso_url        TEXT,
    UNIQUE(statute, section_label)
);
CREATE INDEX idx_sections_statute ON sections(statute);
CREATE INDEX idx_sections_short_name ON sections(short_name);
CREATE VIRTUAL TABLE sections_fts USING fts5(
    section_label, title, text,
    content='sections', content_rowid='rowid', tokenize='porter unicode61'
);
`;
const MANUALS_DDL = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections (
    rowid          INTEGER PRIMARY KEY,
    manual         TEXT NOT NULL,
    short_name     TEXT NOT NULL,
    manual_title   TEXT NOT NULL,
    section_label  TEXT NOT NULL,
    title          TEXT,
    breadcrumb     TEXT,
    source_url     TEXT NOT NULL,
    source_version TEXT,
    text           TEXT NOT NULL,
    UNIQUE(manual, section_label)
);
CREATE INDEX idx_sections_manual ON sections(manual);
CREATE INDEX idx_sections_short_name ON sections(short_name);
CREATE VIRTUAL TABLE sections_fts USING fts5(
    section_label, title, text,
    content='sections', content_rowid='rowid', tokenize='porter unicode61'
);
`;
const STATUTE_COLUMNS = [
  "statute",
  "short_name",
  "statute_title",
  "section_label",
  "title",
  "breadcrumb",
  "source_url",
  "source_version",
  "text",
  "sso_url",
];
const MANUAL_COLUMNS = [
  "manual",
  "short_name",
  "manual_title",
  "section_label",
  "title",
  "breadcrumb",
  "source_url",
  "source_version",
  "text",
];

/** A fresh DELETE-journal SQLite file with Python's schema version 1. */
async function writeDatabase(
  path: string,
  ddl: string,
  columns: string[],
  rows: Record<string, string | null>[],
  meta: Record<string, string>,
) {
  await mkdir(dirname(path), { recursive: true });
  await rm(path, { force: true });
  const db = new Database(path, { create: true });
  try {
    db.exec("PRAGMA journal_mode = DELETE");
    db.exec(ddl);
    const insert = db.prepare(
      `INSERT INTO sections (${columns.join(", ")}) VALUES (${columns.map(() => "?").join(", ")})`,
    );
    db.transaction(() => {
      for (const row of rows)
        insert.run(...columns.map((column) => row[column] ?? null));
      db.exec(
        "INSERT INTO sections_fts(rowid, section_label, title, text) SELECT rowid, section_label, title, text FROM sections",
      );
      const metaInsert = db.prepare(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
      );
      for (const [name, value] of Object.entries({
        ...meta,
        section_count: String(rows.length),
      }))
        metaInsert.run(name, value);
    })();
    db.exec("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')");
    db.exec("VACUUM");
    const check = db
      .query<{ quick_check: string }, []>("PRAGMA quick_check")
      .get();
    if (check?.quick_check !== "ok")
      throw new Error(`${path}: integrity check failed.`);
  } finally {
    db.close();
  }
}

/** Sanity checks that fail the build if a parser lost or invented provisions. */
function checkStatutes(rows: StatuteRow[]) {
  const expect = (statute: string, labels: string[], minimum: number) => {
    const have = new Set(
      rows
        .filter((row) => row.statute === statute)
        .map((row) => row.section_label),
    );
    const missing = labels.filter((label) => !have.has(label));
    if (missing.length || have.size < minimum)
      throw new Error(
        `${statute}: ${have.size} provisions; missing ${missing.join(", ") || "none"}.`,
      );
  };
  // parseSsoPdf also finds every section of each arrangement, in order.
  expect(
    "patents",
    ["1", "2", "13", "14", "15", "29A", "36A", "66", "117", "Schedule"],
    120,
  );
  expect(
    "tm",
    ["2", "7", "8", "27", "55", "109", "First Schedule", "Third Schedule"],
    125,
  );
  expect("designs", ["2", "5", "30", "68A", "77", "Schedule"], 100);
  expect("copyright", ["1", "9", "107", "190", "244", "541"], 541);
  for (const row of rows) {
    if (row.text.length < 15)
      throw new Error(`${row.statute} ${row.section_label}: text too short.`);
    if (/Informal Consolidation|version in force from/.test(row.text))
      throw new Error(
        `${row.statute} ${row.section_label}: running footer leaked into the text.`,
      );
  }
}

function checkManuals(rows: ManualRow[], missing: string[]) {
  const have = new Map(
    rows.map((row) => [`${row.manual} ${row.section_label}`, row]),
  );
  for (const [label, needle] of [
    ["peg 1.1", "Section 29"],
    ["peg 4.1", "inventive step"],
    ["peg 8.12", "discovery"],
    ["tm 1.1", "trade mark"],
    ["tm 7.5.2.5.2", "Visual similarity"],
    ["designs 1.1", "Virtual designs"],
  ] as const) {
    const row = have.get(label);
    if (!row?.text.toLowerCase().includes(needle.toLowerCase()))
      throw new Error(`Manual ${label}: missing or without '${needle}'.`);
  }
  const count = (manual: string) =>
    rows.filter((row) => row.manual === manual).length;
  if (count("peg") < 1000 || count("tm") < 300 || count("designs") < 40)
    throw new Error(
      `Manual row counts too low: peg ${count("peg")}, tm ${count("tm")}, designs ${count("designs")}.`,
    );
  if (missing.length > 15)
    throw new Error(
      `TM Work Manual: ${missing.length} contents headings not found: ${missing.join(", ")}.`,
    );
}

// ---------------------------------------------------------------- main

async function loadManifest(): Promise<SourceManifest> {
  return JSON.parse(await readFile(manifestPath, "utf8")) as SourceManifest;
}

export async function build(manifest: SourceManifest) {
  const doc = (id: string) => {
    const found = manifest.documents.find((entry) => entry.id === id);
    if (!found) throw new Error(`Manifest has no ${id}.`);
    return found;
  };
  const statutes: StatuteRow[] = [];
  const versions: Record<string, string> = {};
  for (const act of STATUTES) {
    const entry = doc(`act_${act.id}`);
    const file = entry.files[0] as SourceFile;
    const { rows, version } = await parseSsoPdf(
      await readSource(file),
      act,
      entry.listing_url,
    );
    versions[act.id] = version;
    statutes.push(...rows);
  }
  checkStatutes(statutes);

  const manuals: ManualRow[] = [];
  const missing: string[] = [];
  for (const id of ["peg", "designs"] as const) {
    const file = doc(`manual_${id}`).files[0] as SourceFile;
    manuals.push(
      ...(await parseParagraphManual(await readSource(file), id, file.url)),
    );
  }
  const tmFiles = doc("manual_tm").files;
  const cover = tmFiles.find((file) => file.chapter === 0) as SourceFile;
  const chapterTitles = await parseTmCover(await readSource(cover));
  const tmVersions: string[] = [];
  for (const file of tmFiles.filter((item) => item.chapter)) {
    const chapter = file.chapter as number;
    const result = await parseTmChapter(
      await readSource(file),
      chapter,
      chapterTitles.get(chapter) ?? "",
      file.url,
    );
    manuals.push(...result.rows);
    missing.push(...result.missing.map((number) => `${chapter}.${number}`));
    tmVersions.push(`${chapter}: ${result.version}`);
  }
  checkManuals(manuals, missing);
  // Document order: PEG, TM Work Manual, designs guidelines.
  const order = ["peg", "tm", "designs"];
  manuals.sort((a, b) => order.indexOf(a.manual) - order.indexOf(b.manual));

  const manifestSha = sha256(await readFile(manifestPath));
  const retrieved = (ids: string[]) =>
    ids
      .flatMap((id) => doc(id).files.map((file) => file.retrieved_at))
      .sort()
      .at(-1)
      ?.slice(0, 10) as string;
  const inForce = [...new Set(Object.values(versions))];
  const statutesMeta: Record<string, string> = {
    schema_version: "1",
    snapshot_date: retrieved(STATUTES.map((act) => `act_${act.id}`)),
    statute_count: String(STATUTES.length),
    source_manifest_sha256: manifestSha,
    extractor: manifest.extractor.pdf,
    ...(inForce.length === 1
      ? { source_version: `2020 Revised Edition, in force from ${inForce[0]}` }
      : {}),
    ...Object.fromEntries(
      STATUTES.map((act) => [
        `source_${act.id}`,
        `${doc(`act_${act.id}`).version} — ${doc(`act_${act.id}`).listing_url} (SSO PDF of the consolidation in force from ${versions[act.id]})`,
      ]),
    ),
  };
  const manualsMeta: Record<string, string> = {
    schema_version: "1",
    snapshot_date: retrieved(["manual_peg", "manual_tm", "manual_designs"]),
    manual_count: "3",
    source_manifest_sha256: manifestSha,
    extractor: manifest.extractor.pdf,
    source_peg: `${doc("manual_peg").title} — ${doc("manual_peg").version}`,
    source_tm: `${doc("manual_tm").title} — chapter versions ${tmVersions.join("; ")}`,
    source_designs: `${doc("manual_designs").title} — ${doc("manual_designs").version}`,
  };
  return { statutes, manuals, statutesMeta, manualsMeta, missing };
}

/** Rows kept in the committed test fixtures. */
const FIXTURE_STATUTES: Record<string, string[]> = {
  patents: ["2", "13", "14", "15", "29A", "66", "109", "Schedule"],
  tm: ["2", "7", "8", "27", "First Schedule"],
  designs: ["2", "5", "68A"],
  copyright: ["9", "190", "191"],
};
const FIXTURE_MANUALS: Record<string, string[]> = {
  peg: ["1.1", "1.3", "4.1", "4.2", "8.12"],
  tm: ["1.1", "7.5.2.5.2", "7.5.2.5.3", "17.3.1"],
  designs: ["1.1", "2.1"],
};

if (import.meta.main) {
  const args = new Set(process.argv.slice(2));
  if (args.has("--fetch")) {
    const manifest = await fetchAll();
    await mkdir(dirname(manifestPath), { recursive: true });
    await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  }
  const manifest = await loadManifest();
  const { statutes, manuals, statutesMeta, manualsMeta, missing } =
    await build(manifest);
  await writeDatabase(
    join(buildDir, "ipos_statutes.db"),
    STATUTES_DDL,
    STATUTE_COLUMNS,
    statutes as unknown as Record<string, string | null>[],
    statutesMeta,
  );
  await writeDatabase(
    join(buildDir, "ipos_manuals.db"),
    MANUALS_DDL,
    MANUAL_COLUMNS,
    manuals as unknown as Record<string, string | null>[],
    manualsMeta,
  );
  const tally = (values: string[]) =>
    values.reduce<Record<string, number>>((acc, value) => {
      acc[value] = (acc[value] ?? 0) + 1;
      return acc;
    }, {});
  console.log(
    JSON.stringify({
      statutes: tally(statutes.map((row) => row.statute)),
      manuals: tally(manuals.map((row) => row.manual)),
      tm_headings_not_found: missing,
    }),
  );
  if (args.has("--dump")) {
    await writeFile(
      join(buildDir, "statutes.json"),
      JSON.stringify(statutes, null, 1),
    );
    await writeFile(
      join(buildDir, "manuals.json"),
      JSON.stringify(manuals, null, 1),
    );
  }
  if (args.has("--fixtures")) {
    const keep = statutes.filter((row) =>
      FIXTURE_STATUTES[row.statute]?.includes(row.section_label),
    );
    const keepManuals = manuals.filter((row) =>
      FIXTURE_MANUALS[row.manual]?.includes(row.section_label),
    );
    if (
      keep.length !== Object.values(FIXTURE_STATUTES).flat().length ||
      keepManuals.length !== Object.values(FIXTURE_MANUALS).flat().length
    )
      throw new Error("A fixture row is missing from the build.");
    await writeDatabase(
      join(fixturesDir, "ipos_statutes.db"),
      STATUTES_DDL,
      STATUTE_COLUMNS,
      keep as unknown as Record<string, string | null>[],
      statutesMeta,
    );
    await writeDatabase(
      join(fixturesDir, "ipos_manuals.db"),
      MANUALS_DDL,
      MANUAL_COLUMNS,
      keepManuals as unknown as Record<string, string | null>[],
      manualsMeta,
    );
    console.log(
      `fixtures: ${keep.length} statute rows, ${keepManuals.length} manual rows`,
    );
  }
}

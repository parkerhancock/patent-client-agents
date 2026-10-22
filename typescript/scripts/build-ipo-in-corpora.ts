// Builds the two IPO India corpora (IP statutes and the MPPP) from official
// sources. Plain HTTP GETs with an honest user agent; no browser, cookies or
// challenge handling. Raw sources are archived under the ignored
// .data/ipo-in/sources/ and recorded (URL, retrieval time, SHA-256) in the
// committed references/ipo-in/sources.json.
//
// Usage (from typescript/):
//   bun scripts/build-ipo-in-corpora.ts --fetch      # download and archive, then build
//   bun scripts/build-ipo-in-corpora.ts              # build from the archive
//   bun scripts/build-ipo-in-corpora.ts --fixtures   # also rewrite the test fixtures
// Output: .data/ipo-in/build/ipo_in_statutes.db and ipo_in_mppp.db (schema
// version 1, DELETE journal mode). Package them with scripts/compress-corpus.ts.
//
// PDF text comes from pdfjs-dist (pinned in package.json), which reports font
// sizes and positions, so superscript amendment markers, footnotes, running
// page numbers and the MPPP's marginal references can be told apart from the
// body text.
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
const dataDir = join(root, ".data/ipo-in");
const sourcesDir = join(dataDir, "sources");
const buildDir = join(dataDir, "build");
const manifestPath = join(root, "references/ipo-in/sources.json");
const fixturesDir = join(root, "tests/fixtures/ipo-in");

const IPINDIA = "https://ipindia.gov.in";
const DOCS = `${IPINDIA}/storage/uploads/docs-operator`;
const WIPO_LEX = "https://www.wipo.int/wipolex/en/legislation/details";

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

/** One archived file. `path` is relative to .data/ipo-in/sources/. */
interface SourceFile {
  path: string;
  url: string;
  retrieved_at: string;
  sha256: string;
  bytes: number;
}
interface SourceDocument {
  id: string;
  title: string;
  /** What the text reflects, as the publisher states it. */
  version: string;
  publisher: string;
  /** The page that lists the document and states its version. */
  listing_url: string;
  files: SourceFile[];
}
interface SourceManifest {
  description: string;
  access_notes: string[];
  user_agent: string;
  extractor: { pdf: string };
  documents: SourceDocument[];
}

// ---------------------------------------------------------------- fetching

const pause = (ms: number) => new Promise((done) => setTimeout(done, ms));

async function get(url: string): Promise<Uint8Array> {
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
      return bytes;
    } catch (error) {
      last = error;
      console.warn(`attempt ${attempt} for ${url} failed: ${String(error)}`);
      await pause(5_000 * attempt);
    }
  }
  throw last;
}

const now = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
const text = (bytes: Uint8Array) => new TextDecoder().decode(bytes);

async function archive(
  path: string,
  url: string,
  bytes: Uint8Array,
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
  };
}

async function fetchFile(path: string, url: string) {
  console.log(`GET ${url}`);
  return archive(path, url, await get(url));
}

/** A listing page must still name the document and its stated version. */
async function checkListing(url: string, needles: string[]) {
  const page = text(await get(url)).replace(/\s+/g, " ");
  for (const needle of needles)
    if (!page.includes(needle))
      throw new Error(
        `${url} no longer contains '${needle}'; review the source before rebuilding.`,
      );
}

/** The TOC rows of an ipindia.gov.in e-Version act page. */
export function parseIpindiaToc(html: string) {
  return [
    ...html.matchAll(
      /section-left">\s*(.*?)\s*<\/div>\s*<div class="col section-text[^"]*">\s*<a\s+href="([^"]+)">\s*(.*?)\s*<\/a>/gs,
    ),
  ].map((match) => ({
    label: clean(decode(match[1] as string)),
    url: match[2] as string,
    title: clean(decode((match[3] as string).replace(/<[^>]+>/g, " "))),
  }));
}

async function fetchIpindiaAct(
  id: string,
  indexUrl: string,
  kind: "Rule" | "Section",
) {
  const index = await fetchFile(`${id}/index.html`, indexUrl);
  const toc = parseIpindiaToc(text(await readSource(index)));
  const files = [index];
  for (const row of toc) {
    if (!new RegExp(`^${kind} \\d+[A-Z]*$`).test(row.label)) continue;
    const slug = row.url.split("/").pop() as string;
    files.push(await fetchFile(`${id}/${slug}.html`, row.url));
  }
  return files;
}

/** WIPO Lex serves its PDFs through short-lived signed links on the details page. */
async function fetchWipoLex(path: string, id: string, pdfName: string) {
  const details = text(await get(`${WIPO_LEX}/${id}`))
    .replace(/&#x3D;/g, "=")
    .replace(/&amp;/g, "&");
  const signed = new RegExp(
    `https://wipolex-res\\.wipo\\.int/edocs/lexdocs/laws/en/in/${pdfName}\\?[^"' ]+Signature=[^"' ]+`,
  ).exec(details)?.[0];
  if (!signed) throw new Error(`WIPO Lex ${id} no longer links ${pdfName}.`);
  console.log(`GET ${signed.split("?")[0]} (signed)`);
  return archive(
    path,
    `https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/in/${pdfName}`,
    await get(signed),
  );
}

const DOCUMENTS = {
  patents_act: {
    title:
      "The Patents Act, 1970 (incorporating all amendments till 01-08-2024)",
    version:
      "Consolidated text incorporating all amendments till 01-08-2024 (through the Jan Vishwas (Amendment of Provisions) Act, 2023, w.e.f. 01-08-2024)",
    publisher:
      "Office of the Controller General of Patents, Designs and Trade Marks (ipindia.gov.in)",
    listing_url: `${IPINDIA}/resource/patents-resources-act`,
  },
  patent_rules: {
    title:
      "The Patents Rules, 2003 (e-Version) with Chapter XIV-A as substituted by the Patents (Amendment) Rules, 2025",
    version:
      "ipindia.gov.in e-Version (HTML) 'updated till 01-08-2024' for rules 1-139; Chapter XIV-A (rules 107A-107G) from the Patents (Amendment) Rules, 2025, G.S.R. 865(E), Gazette of India Extraordinary, 25 November 2025, which substituted the whole chapter",
    publisher:
      "Office of the Controller General of Patents, Designs and Trade Marks (ipindia.gov.in)",
    listing_url: `${IPINDIA}/resource/patents-resources-rules`,
  },
  designs_act: {
    title: "The Designs Act, 2000 (e-Version)",
    version:
      "ipindia.gov.in e-Version (HTML); the page states no amendment date, and the ipindia Designs Act listing names no amending Act. Not cross-checked against India Code, which refused plain requests (HTTP 403).",
    publisher:
      "Office of the Controller General of Patents, Designs and Trade Marks (ipindia.gov.in)",
    listing_url: `${IPINDIA}/designs-resources-act`,
  },
  trade_marks_act: {
    title:
      "The Trade Marks Act, 1999 (Act No. 47 of 1999, amended up to Act No. 18 of 2023)",
    version:
      "Consolidated India Code text amended up to the Jan Vishwas (Amendment of Provisions) Act, 2023 (Act No. 18 of 2023), as republished by WIPO Lex (entry 22958, version year 2023). ipindia.gov.in publishes only the 1999 text and the 2010 amending Act; India Code refused plain requests (HTTP 403).",
    publisher: "Government of India (India Code), via WIPO Lex",
    listing_url: `${WIPO_LEX}/22958`,
  },
  copyright_act: {
    title:
      "The Copyright Act, 1957 (Act No. 14 of 1957, amended up to Act No. 18 of 2023)",
    version:
      "Consolidated India Code text amended up to the Jan Vishwas (Amendment of Provisions) Act, 2023 (Act No. 18 of 2023), as republished by WIPO Lex (entry 22949, version year 2023). India Code refused plain requests (HTTP 403).",
    publisher: "Government of India (India Code), via WIPO Lex",
    listing_url: `${WIPO_LEX}/22949`,
  },
  mppp: {
    title:
      "Manual of Patent Office Practice and Procedure, Version 3.0, 26th November, 2019",
    version:
      "Version 3.0, 26th November, 2019 (in force; the August 2026 draft revision is not adopted)",
    publisher:
      "Office of the Controller General of Patents, Designs and Trade Marks (ipindia.gov.in)",
    listing_url: `${IPINDIA}/resource/patents-resources-manuals`,
  },
} as const;
type DocumentId = keyof typeof DOCUMENTS;

/** What happened with the preferred sources when this builder was written. */
const ACCESS_NOTES = [
  "2026-10-22: www.indiacode.nic.in (Akamai) answered HTTP 403 Access Denied to plain GETs with this user agent for the handle page, the site root and a bitstream PDF; www.legislative.gov.in answered 403 too. No other access method was tried.",
  "ipindia.gov.in publishes consolidated text for the Patents Act (PDF, amendments till 01-08-2024) and an e-Version of the Patents Rules and the Designs Act, but for the Trade Marks Act only the 1999 text and the 2010 amending Act, so the Trade Marks and Copyright Acts come from WIPO Lex's republication of the India Code consolidations.",
  "The ipindia Patents Act e-Version (HTML) was not used: it lacks sections 124A/124B and still shows section 121, which the Jan Vishwas Act changed with effect from 01-08-2024.",
];

async function fetchAll(): Promise<SourceManifest> {
  const documents: SourceDocument[] = [];
  const add = (id: DocumentId, files: SourceFile[]) =>
    documents.push({ id, ...DOCUMENTS[id], files });

  await checkListing(DOCUMENTS.patents_act.listing_url, [
    "The Patents Act, 1970 (incorporating all amendments till 01-08-2024)",
    "73b5bf10-b04e-4f45-abef-87ff117315dc.pdf",
  ]);
  add("patents_act", [
    await fetchFile(
      "patents-act-1970.pdf",
      `${DOCS}/73b5bf10-b04e-4f45-abef-87ff117315dc.pdf`,
    ),
  ]);

  await checkListing(DOCUMENTS.patent_rules.listing_url, [
    "Patent Amendment Rules, 2025",
    "0cd91608-5e17-4c91-accb-84f81b05fe9b.pdf",
  ]);
  const rules = await fetchIpindiaAct(
    "patent-rules-2003",
    `${IPINDIA}/acts/patent-rules-2003`,
    "Rule",
  );
  if (
    !text(await readSource(rules[0] as SourceFile)).includes(
      "is updated till 01-08-2024",
    )
  )
    throw new Error(
      "The Patent Rules e-Version no longer states 'updated till 01-08-2024'.",
    );
  rules.push(
    await fetchFile(
      "patents-amendment-rules-2025.pdf",
      `${DOCS}/0cd91608-5e17-4c91-accb-84f81b05fe9b.pdf`,
    ),
  );
  add("patent_rules", rules);

  await checkListing(DOCUMENTS.designs_act.listing_url, [
    "The Designs Act 2000",
    `${IPINDIA}/acts/designs-act-2000`,
  ]);
  add(
    "designs_act",
    await fetchIpindiaAct(
      "designs-act-2000",
      `${IPINDIA}/acts/designs-act-2000`,
      "Section",
    ),
  );

  add("trade_marks_act", [
    await fetchWipoLex("trade-marks-act-1999.pdf", "22958", "in154en_1.pdf"),
  ]);
  add("copyright_act", [
    await fetchWipoLex("copyright-act-1957.pdf", "22949", "in153en_1.pdf"),
  ]);

  await checkListing(DOCUMENTS.mppp.listing_url, [
    "Manual of Patent Office Practice and Procedure -2019",
    "e1adfe40-7af3-4180-ba04-2e0099c6dca5.pdf",
  ]);
  add("mppp", [
    await fetchFile(
      "mppp-v3.0-2019.pdf",
      `${DOCS}/e1adfe40-7af3-4180-ba04-2e0099c6dca5.pdf`,
    ),
  ]);

  return {
    description:
      "Official sources of the IPO India statutes and MPPP corpora. Raw files are archived gzipped under typescript/.data/ipo-in/sources/<path>.gz (not committed); sha256 and bytes are of the raw file.",
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
  lsquo: "‘",
  rsquo: "’",
  ldquo: "“",
  rdquo: "”",
  hellip: "…",
  shy: "",
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
/** Collapse whitespace (including soft hyphens and NBSP) to single spaces. */
export const clean = (value: string) =>
  value
    .replace(/­/g, "")
    .replace(/[\s ]+/g, " ")
    .trim();

/** Paragraph text of an HTML fragment: block elements and <br> become line breaks. */
export function htmlText(fragment: string): string {
  const flat = fragment
    .replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|tr|h\d|table|ul|ol)>/gi, "\n")
    .replace(/<(td|th)[^>]*>/gi, " ")
    .replace(/<[^>]+>/g, "");
  return decode(flat).split("\n").map(clean).filter(Boolean).join("\n");
}

// ---------------------------------------------------------------- PDF lines

interface Item {
  str: string;
  x: number;
  end: number;
  y: number;
  size: number;
}
export interface Line {
  page: number;
  y: number;
  x: number;
  end: number;
  size: number;
  text: string;
  items: Item[];
}

/** Text lines per page, top to bottom; items smaller than `minSize` are dropped. */
async function pdfLines(bytes: Uint8Array, minSize: number): Promise<Line[][]> {
  const doc = await getDocument({
    data: bytes.slice(),
    verbosity: 0,
    isEvalSupported: false,
    useSystemFonts: false,
  }).promise;
  const pages: Line[][] = [];
  for (let number = 1; number <= doc.numPages; number++) {
    const page = await doc.getPage(number);
    const content = await page.getTextContent();
    const items: Item[] = [];
    for (const raw of content.items) {
      if (!("str" in raw) || !raw.str) continue;
      const [, , c, d, x, y] = raw.transform as number[];
      const size = Math.hypot(c as number, d as number);
      if (size < minSize) continue;
      items.push({
        str: raw.str,
        x: x as number,
        end: (x as number) + raw.width,
        y: y as number,
        size,
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
          end: 0,
          size: 0,
          text: "",
          items: [item],
        });
    }
    for (const line of lines) {
      line.items.sort((a, b) => a.x - b.x);
      const visible = line.items.filter((item) => item.str.trim());
      line.x = visible[0]?.x ?? line.items[0]?.x ?? 0;
      line.end = Math.max(...line.items.map((item) => item.end));
      line.size = Math.max(0, ...visible.map((item) => item.size));
      line.text = joinItems(line.items);
    }
    pages.push(lines.filter((line) => line.text));
    page.cleanup();
  }
  await doc.destroy();
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

/** Join wrapped lines into paragraphs; `starts` decides which lines open a paragraph. */
function paragraphs(
  lines: string[],
  starts: (line: string) => boolean,
): string {
  const out: string[] = [];
  for (const line of lines) {
    const last = out.at(-1);
    if (last === undefined || starts(line)) out.push(line);
    else if (/[A-Za-z]-$/.test(last) && /^[a-z]/.test(line))
      out[out.length - 1] = last + line;
    else out[out.length - 1] = `${last} ${line}`;
  }
  return out.join("\n");
}

// ---------------------------------------------------------------- statutes

export interface StatuteRow {
  statute_name: string;
  section_number: string;
  title: string | null;
  text: string;
  source_url: string;
}

const STATUTE_PARAGRAPH =
  /^(?:\[|\*\s*\[)?\s*(?:\((?:[a-z]{1,4}|[ivxlc]+|\d+[A-Z]{0,2}|[A-Z]{1,2})\)|Explanation|Provided|Illustration|\*\s\*|\d+[A-Z]{0,3}\.\s)/;
/** "3. What are not inventions.—…" or "5. [Title.] Omitted by …". */
const SECTION_HEAD =
  /^\[?\s*(\d+[A-Z]{0,3})\.\s*(?:(\[[^\]]+\])\s*(Omitted|Repealed)\b|([A-Z[“"‘][^—]{1,300}?)[.,:;]?\s*[—–]+)/;

/**
 * Sections of a consolidated India Code-style PDF (the ipindia Patents Act and
 * the WIPO Lex republications). Superscript footnote markers (< 7.75 pt),
 * page-foot amendment footnotes (a trailing run of sub-10 pt lines), running
 * page numbers, the arrangement of sections and chapter headings are dropped.
 */
export async function parseIndiaCodePdf(
  bytes: Uint8Array,
  statute: string,
  sourceUrl: string,
): Promise<StatuteRow[]> {
  const pages = await pdfLines(bytes, 7.75);
  const body: Line[] = [];
  for (const lines of pages) {
    const kept = lines.filter(
      (line) => !(line.y < 60 && /^\d{1,3}$/.test(line.text)),
    );
    let lastBody = -1;
    kept.forEach((line, index) => {
      if (line.size >= 10) lastBody = index;
    });
    body.push(...kept.slice(0, lastBody + 1));
  }
  const start = body.findIndex((line) =>
    /enacted by Parliament/i.test(line.text),
  );
  if (start < 0) throw new Error(`${statute}: no enacting formula found.`);
  const rows: {
    number: string;
    title: string;
    page: number;
    lines: string[];
  }[] = [];
  let inChapterHeading = false;
  for (let index = start + 1; index < body.length; index++) {
    const line = body[index] as Line;
    const value = line.text;
    if (/^THE (?:FIRST |SECOND |THIRD |FOURTH )?SCHEDULE\b/.test(value)) break;
    if (
      /^(?:\[)?CHAPTER [IVXLC]+[A-Z]?\]?$/.test(value) ||
      /^\[?CHAPTER [IVXLC]+[A-Z]?\s*$/.test(value)
    ) {
      inChapterHeading = true;
      continue;
    }
    if (
      inChapterHeading &&
      value === value.toUpperCase() &&
      /[A-Z]{3}/.test(value)
    )
      continue;
    inChapterHeading = false;
    const joined = `${value} ${body[index + 1]?.text ?? ""}`;
    const head = SECTION_HEAD.exec(value) ?? SECTION_HEAD.exec(joined);
    const previous = rows.at(-1);
    if (
      head &&
      line.x < 140 &&
      (!previous || compareNumbers(head[1] as string, previous.number) > 0)
    ) {
      const number = head[1] as string;
      const title = clean(
        head[2]
          ? (head[2] as string).replace(/^\[|\]$/g, "").replace(/\.$/, "")
          : (head[4] as string),
      ).replace(/^[[“"‘]+/, "");
      rows.push({ number, title, page: line.page, lines: [value] });
      continue;
    }
    previous?.lines.push(value);
  }
  // The parsed sections must be exactly those of the Act's own arrangement of sections.
  const arrangement = [
    ...new Set(
      body
        .slice(0, start)
        .map((line) => /^(\d+[A-Z]{0,3})\.\s/.exec(line.text)?.[1])
        .filter((value): value is string => Boolean(value)),
    ),
  ];
  const parsed = rows.map((row) => row.number);
  if (arrangement.join() !== parsed.join())
    throw new Error(
      `${statute}: sections differ from the arrangement of sections (missing ${arrangement.filter((n) => !parsed.includes(n)).join(", ") || "none"}; extra ${parsed.filter((n) => !arrangement.includes(n)).join(", ") || "none"}).`,
    );
  return rows.map((row) => ({
    statute_name: statute,
    section_number: row.number,
    title: row.title || null,
    text: paragraphs(row.lines, (line) => STATUTE_PARAGRAPH.test(line))
      .replace(/(?:\*\s*){3,}/g, "* * * ")
      .replace(/\* \* \* (?=\[?\()/g, "* * *\n")
      .replace(/ +\n/g, "\n")
      .trim(),
    source_url: `${sourceUrl}#page=${row.page}`,
  }));
}

/** Natural order of section numbers: 3 < 3A < 4 < 10 < 107A. */
export function compareNumbers(a: string, b: string): number {
  const [, an = "0", as = ""] = /^(\d+)([A-Z]*)$/i.exec(a) ?? [];
  const [, bn = "0", bs = ""] = /^(\d+)([A-Z]*)$/i.exec(b) ?? [];
  return (
    Number(an) - Number(bn) || as.length - bs.length || as.localeCompare(bs)
  );
}

/** Rules or sections of an ipindia.gov.in e-Version act (one page per provision). */
function parseIpindiaAct(
  statute: string,
  kind: "Rule" | "Section",
  files: Map<string, Uint8Array>,
): StatuteRow[] {
  const index = files.get("index.html");
  if (!index) throw new Error(`${statute}: archived index missing.`);
  const rows: StatuteRow[] = [];
  for (const entry of parseIpindiaToc(text(index))) {
    const label = new RegExp(`^${kind} (\\d+[A-Z]*)$`).exec(entry.label);
    if (!label) continue;
    const slug = entry.url.split("/").pop() as string;
    const page = files.get(`${slug}.html`);
    if (!page) throw new Error(`${statute}: archived ${slug}.html missing.`);
    const html = text(page);
    const start = html.indexOf('class="chapterDetailsAreaBox"');
    const end = html.indexOf(
      '<div class="d-flex align-items-center justify-content-between mt-4">',
      start,
    );
    if (start < 0 || end < 0)
      throw new Error(`${statute} ${entry.label}: no section body.`);
    const bodyHtml = html.slice(html.indexOf(">", start) + 1, end);
    let body = htmlText(bodyHtml).replace(/\s*--\s*/g, "—");
    if (
      /^\[?Omitted\]?$/i.test(entry.title) &&
      /^(?:No content available\.?|Omitted)$/i.test(body)
    )
      body = "[Omitted]";
    rows.push({
      statute_name: statute,
      section_number: (label[1] as string).toUpperCase(),
      title: entry.title || null,
      text: body,
      source_url: entry.url,
    });
  }
  return rows;
}

/** Chapter XIV-A (rules 107A-107G) as substituted by G.S.R. 865(E), 25 November 2025. */
async function parseChapterXIVA(
  bytes: Uint8Array,
  sourceUrl: string,
): Promise<StatuteRow[]> {
  const pages = await pdfLines(bytes, 7.75);
  const lines = pages
    .flat()
    .filter((line) => !/THE GAZETTE OF INDIA|^\[PART II|^\d+$/.test(line.text))
    .map((line) => line.text);
  const start = lines.findIndex((line) => /^107A\. Definitions/.test(line));
  const end = lines.findIndex(
    (line, index) => index > start && /^3\. In the principal rules/.test(line),
  );
  if (start < 0 || end < 0)
    throw new Error(
      "Patents (Amendment) Rules, 2025: Chapter XIV-A not found.",
    );
  const rows: { number: string; title: string; lines: string[] }[] = [];
  for (const line of lines.slice(start, end)) {
    const head = /^(107)\s?([A-G])\.\s*([^.—-]+?)\.?\s*[—-]+\s*(.*)$/.exec(
      line,
    );
    if (head) {
      rows.push({
        number: `107${head[2]}`,
        title: clean(head[3] as string),
        lines: [line.replace(/^107\s([A-G])/, "107$1")],
      });
      continue;
    }
    rows.at(-1)?.lines.push(line);
  }
  if (
    rows.map((row) => row.number).join() !==
    "107A,107B,107C,107D,107E,107F,107G"
  )
    throw new Error(
      `Chapter XIV-A parsed as ${rows.map((row) => row.number).join()}.`,
    );
  return rows.map((row) => ({
    statute_name: "Patent Rules",
    section_number: row.number,
    title: row.title,
    text: paragraphs(row.lines, (line) => STATUTE_PARAGRAPH.test(line))
      .replace(/[’']\.\s*$/, "")
      .replace(/’\.’\.$/, "")
      .trim(),
    source_url: sourceUrl,
  }));
}

// ---------------------------------------------------------------- MPPP

export interface MpppRow {
  section_number: string;
  chapter: string;
  title: string | null;
  text: string;
  source_url: string;
}

/** Bullets set in a symbol font, and curly quotes the manual's fonts map to ―, ‖ and ‗. */
const mpppGlyphs = (value: string) =>
  value
    .replace(/\uf0b7/g, "•")
    .replace(/\uf0d8/g, "➢")
    .replace(/\uf0fc/g, "✓")
    .replace(/―/g, "“")
    .replace(/‖/g, "”")
    .replace(/‗/g, "‘");
const DUPLICATE_MPPP_NUMBERS = ["14.02.01.04"];
const MPPP_HEAD = /^(\d{2})\.(\d{2})((?:\.\d{2})*)\.?(?=\s|$)\s*(.*)$/;
const MPPP_PARAGRAPH =
  /^(?:\d{2}\.\d{2}(?:\.\d{2})+\s|\d{1,2}\.\s|\(?[a-z]\)\s|\(?[ivx]+[.)]\s|[A-Z]\)\s|\([A-Z]\)\s|•||Explanation|Provided|Note|In the matter of|Illustration|Example)/;

/**
 * MPPP v3.0 paragraphs. Numbered headings at the left margin ("09.03.05.04")
 * open a row; text before a chapter's first heading becomes the chapter row
 * ("09"). Marginal references (Section/Rule citations set in the right
 * margin, x >= 468 pt) are kept apart and appended as a last line.
 */
export async function parseMpppPdf(
  bytes: Uint8Array,
  sourceUrl: string,
): Promise<MpppRow[]> {
  const pages = await pdfLines(bytes, 7.75);
  const rows: (MpppRow & { lines: string[]; margin: string[] })[] = [];
  let chapter: { number: string; title: string } | null = null;
  const titles = new Map<string, string>();
  let pendingIndex: string | null = null;
  let afterChapterHead = false;
  for (const lines of pages) {
    for (const line of lines) {
      if (line.y < 60 && /^\d{1,3}$/.test(line.text)) continue;
      // Pages 1-3 are the cover, preface and index; the index gives chapter
      // titles, some wrapped onto a second line.
      if (line.page <= 3) {
        const index = /^Chapter (\d{2}): (.+)$/.exec(line.text);
        const entry: string | null = index
          ? (index[1] as string)
          : pendingIndex;
        if (entry && (index || pendingIndex)) {
          const part = clean(
            (index ? (index[2] as string) : line.text).replace(
              /\s*[….][….\s\d]*$/,
              "",
            ),
          );
          titles.set(
            entry,
            clean(`${index ? "" : (titles.get(entry) ?? "")} ${part}`),
          );
          pendingIndex = /[…]|\.{2}|\d$/.test(line.text) ? null : entry;
        }
        continue;
      }
      const chapterHead = /^Chapter\s*[-–]?\s*(\d{1,2})\s*:\s*(.+)$/i.exec(
        line.text,
      );
      if (chapterHead && line.size >= 13.5) {
        const number = (chapterHead[1] as string).padStart(2, "0");
        chapter = {
          number,
          title: titles.get(number) ?? clean(chapterHead[2] as string),
        };
        rows.push({
          section_number: number,
          chapter: `Chapter ${number}: ${chapter.title}`,
          title: chapter.title,
          text: "",
          source_url: `${sourceUrl}#page=${line.page}`,
          lines: [],
          margin: [],
        });
        afterChapterHead = true;
        continue;
      }
      // The second line of a wrapped chapter heading.
      if (afterChapterHead && line.size >= 13.5 && !/^\d/.test(line.text))
        continue;
      afterChapterHead = false;
      if (!chapter) continue;
      // Margin references start after a gap from the last visible body glyph
      // (blank items can span the gap, so they do not count).
      const visible = line.items.filter((item) => item.str.trim());
      const gapBefore = (i: number) =>
        (visible[i]?.x ?? 0) -
        (visible[i - 1]?.end ?? Number.NEGATIVE_INFINITY);
      const firstMargin = visible.findIndex(
        (item, i) =>
          (item.x >= 468 && gapBefore(i) > 4) ||
          (item.x >= 400 &&
            /^(?:Sections?|Rules?)\b/.test(item.str.trim()) &&
            gapBefore(i) > 25),
      );
      const marginStart =
        firstMargin < 0 ? -1 : line.items.indexOf(visible[firstMargin] as Item);
      const bodyItems =
        marginStart < 0 ? line.items : line.items.slice(0, marginStart);
      const marginItems = marginStart < 0 ? [] : line.items.slice(marginStart);
      const margin = marginItems.length ? joinItems(marginItems) : "";
      if (!bodyItems.length) {
        if (margin) rows.at(-1)?.margin.push(margin);
        continue;
      }
      const value = joinItems(bodyItems);
      const head =
        line.x < 100
          ? MPPP_HEAD.exec(value.replace(/^(\d{2}\.\d{2})(\d{2})\b/, "$1.$2"))
          : null;
      if (head && head[1] === chapter.number) {
        const number = `${head[1]}.${head[2]}${head[3]}`;
        const earlier = rows.find((row) => row.section_number === number);
        if (earlier) {
          // The manual numbers two paragraphs 14.02.01.04; keep both under the
          // first, with the second heading as a line of text.
          if (!DUPLICATE_MPPP_NUMBERS.includes(number))
            throw new Error(
              `MPPP ${number} appears twice (page ${line.page}).`,
            );
          earlier.lines.push(value);
          if (margin) earlier.margin.push(margin);
          rows.push(earlier);
          continue;
        }
        rows.push({
          section_number: number,
          chapter: `Chapter ${chapter.number}: ${chapter.title}`,
          title:
            mpppGlyphs(
              clean((head[4] as string).replace(/^[ivx]+\.\s+/, "")),
            ) || null,
          text: "",
          source_url: `${sourceUrl}#page=${line.page}`,
          lines: [],
          margin: margin ? [margin] : [],
        });
        continue;
      }
      const current = rows.at(-1);
      current?.lines.push(value);
      if (margin) current?.margin.push(margin);
    }
  }
  return [...new Set(rows)].map(({ lines, margin, ...row }) => {
    // A sentence-style heading ("The mere discovery of … which") runs on into
    // the first body line; keep the whole sentence in the text.
    if (
      row.title &&
      !/[.:;,\-–—]$/.test(row.title) &&
      /^[a-z]/.test(lines[0] ?? "")
    )
      lines[0] = `${row.title} ${lines[0]}`;
    const body = mpppGlyphs(
      paragraphs(lines, (line) => MPPP_PARAGRAPH.test(line)),
    );
    const refs = clean(margin.join(" "));
    // A heading with nothing before its first sub-heading keeps the heading as text.
    const heading = `${row.section_number} ${row.title ?? ""}`.trim();
    return {
      ...row,
      text: [body || heading, refs ? `[Marginal references: ${refs}]` : ""]
        .filter(Boolean)
        .join("\n"),
    };
  });
}

// ---------------------------------------------------------------- database

const STATUTES_DDL = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections (
    rowid          INTEGER PRIMARY KEY,
    statute_name   TEXT NOT NULL,
    section_number TEXT NOT NULL,
    title          TEXT,
    text           TEXT NOT NULL,
    source_url     TEXT,
    UNIQUE(statute_name, section_number)
);
CREATE INDEX idx_sections_statute ON sections(statute_name);
CREATE INDEX idx_sections_section_number ON sections(section_number);
CREATE VIRTUAL TABLE sections_fts USING fts5(
    statute_name, section_number, title, text,
    content='sections', content_rowid='rowid', tokenize='porter unicode61'
);
`;
const MPPP_DDL = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections (
    rowid          INTEGER PRIMARY KEY,
    section_number TEXT UNIQUE NOT NULL,
    chapter        TEXT,
    title          TEXT,
    text           TEXT NOT NULL,
    source_url     TEXT
);
CREATE INDEX idx_sections_chapter ON sections(chapter);
CREATE VIRTUAL TABLE sections_fts USING fts5(
    section_number, title, text,
    content='sections', content_rowid='rowid', tokenize='porter unicode61'
);
`;

/** A fresh DELETE-journal SQLite file with the readers' schema version 1. */
async function writeDatabase(
  path: string,
  ddl: string,
  columns: string[],
  ftsColumns: string[],
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
        `INSERT INTO sections_fts(rowid, ${ftsColumns.join(", ")}) SELECT rowid, ${ftsColumns.join(", ")} FROM sections`,
      );
      const metaInsert = db.prepare(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
      );
      for (const [key, value] of Object.entries({
        ...meta,
        section_count: String(rows.length),
      }))
        metaInsert.run(key, value);
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

const STATUTE_COLUMNS = [
  "statute_name",
  "section_number",
  "title",
  "text",
  "source_url",
];
const MPPP_COLUMNS = [
  "section_number",
  "chapter",
  "title",
  "text",
  "source_url",
];

/** Sanity checks that fail the build if a parser lost or invented provisions. */
function checkStatutes(rows: StatuteRow[]) {
  const by = (statute: string) =>
    rows.filter((row) => row.statute_name === statute);
  const expect = (statute: string, numbers: string[], minimum: number) => {
    const have = new Set(by(statute).map((row) => row.section_number));
    const missing = numbers.filter((number) => !have.has(number));
    if (missing.length || have.size < minimum)
      throw new Error(
        `${statute}: ${have.size} provisions; missing ${missing.join(", ") || "none"}.`,
      );
  };
  // The PDF parsers also check their sections against each Act's arrangement of sections.
  expect(
    "Patents Act",
    ["1", "2", "3", "25", "48", "84", "107A", "124A", "124B", "146", "163"],
    175,
  );
  expect(
    "Patent Rules",
    ["1", "13", "24B", "71", "107A", "107G", "131", "138", "139"],
    155,
  );
  expect("Designs Act", ["1", "2", "11", "22", "48"], 48);
  expect(
    "Trade Marks Act",
    ["1", "2", "9", "11", "29", "36A", "36G", "47", "159"],
    169,
  );
  expect("Copyright Act", ["1", "2", "13", "14", "22", "52", "63", "79"], 105);
  for (const row of rows) {
    if (row.text.length < 20 && !/omitted|repealed/i.test(row.text))
      throw new Error(
        `${row.statute_name} ${row.section_number}: text too short.`,
      );
    // Omitted provisions legitimately carry their "Omitted by … (w.e.f. …)" note.
    if (
      !/Omitted by/.test(row.text) &&
      /\bw\.e\.f\.|Subs\. by Act|Ins\. by Act/.test(row.text)
    )
      throw new Error(
        `${row.statute_name} ${row.section_number}: footnote text leaked into the section.`,
      );
  }
}

function checkMppp(rows: MpppRow[]) {
  const have = new Map(rows.map((row) => [row.section_number, row]));
  for (const [number, title] of [
    ["07.02", "International Application under PCT"],
    ["09.03", "Examination of application"],
    ["09.03.05.04", "The mere discovery of a new form of a known substance"],
    ["04.01", "Publication of Patent Application"],
  ] as const)
    if (!have.get(number)?.title?.startsWith(title))
      throw new Error(
        `MPPP ${number}: expected '${title}', got '${have.get(number)?.title}'.`,
      );
  if (rows.length < 200) throw new Error(`MPPP: only ${rows.length} rows.`);
}

// ---------------------------------------------------------------- main

async function loadManifest(): Promise<SourceManifest> {
  return JSON.parse(await readFile(manifestPath, "utf8")) as SourceManifest;
}

async function filesOf(document: SourceDocument, prefix = "") {
  const map = new Map<string, Uint8Array>();
  for (const file of document.files)
    map.set(file.path.slice(prefix.length), await readSource(file));
  return map;
}

export async function build(manifest: SourceManifest) {
  const doc = (id: DocumentId) => {
    const found = manifest.documents.find((entry) => entry.id === id);
    if (!found) throw new Error(`Manifest has no ${id}.`);
    return found;
  };
  const single = async (id: DocumentId) => {
    const file = doc(id).files[0] as SourceFile;
    return { file, bytes: await readSource(file) };
  };
  const statutes: StatuteRow[] = [];
  const patents = await single("patents_act");
  statutes.push(
    ...(await parseIndiaCodePdf(
      patents.bytes,
      "Patents Act",
      patents.file.url,
    )),
  );

  const rulesDoc = doc("patent_rules");
  const ruleFiles = await filesOf(rulesDoc, "patent-rules-2003/");
  const amendment = rulesDoc.files.find((file) =>
    file.path.endsWith(".pdf"),
  ) as SourceFile;
  const rules = parseIpindiaAct("Patent Rules", "Rule", ruleFiles).filter(
    (row) => !/^107[A-Z]$/.test(row.section_number),
  );
  rules.push(
    ...(await parseChapterXIVA(await readSource(amendment), amendment.url)),
  );
  rules.sort((a, b) => compareNumbers(a.section_number, b.section_number));
  statutes.push(...rules);

  statutes.push(
    ...parseIpindiaAct(
      "Designs Act",
      "Section",
      await filesOf(doc("designs_act"), "designs-act-2000/"),
    ),
  );
  const tm = await single("trade_marks_act");
  statutes.push(
    ...(await parseIndiaCodePdf(
      tm.bytes,
      "Trade Marks Act",
      doc("trade_marks_act").listing_url,
    )),
  );
  const copyright = await single("copyright_act");
  statutes.push(
    ...(await parseIndiaCodePdf(
      copyright.bytes,
      "Copyright Act",
      doc("copyright_act").listing_url,
    )),
  );
  checkStatutes(statutes);

  const mpppSource = await single("mppp");
  const mppp = await parseMpppPdf(mpppSource.bytes, mpppSource.file.url);
  checkMppp(mppp);

  const manifestSha = sha256(await readFile(manifestPath));
  const retrieved = (ids: DocumentId[]) =>
    ids
      .flatMap((id) => doc(id).files.map((file) => file.retrieved_at))
      .sort()
      .at(-1)
      ?.slice(0, 10) as string;
  const statuteIds: DocumentId[] = [
    "patents_act",
    "patent_rules",
    "designs_act",
    "trade_marks_act",
    "copyright_act",
  ];
  const statutesMeta = {
    schema_version: "1",
    snapshot_date: retrieved(statuteIds),
    source_manifest_sha256: manifestSha,
    extractor: manifest.extractor.pdf,
    ...Object.fromEntries(
      statuteIds.map((id) => [
        `source_${id}`,
        `${doc(id).title} — ${doc(id).version}`,
      ]),
    ),
  };
  const mpppMeta = {
    schema_version: "1",
    snapshot_date: retrieved(["mppp"]),
    source_version: "v3.0 (2019-11-26)",
    source_title: doc("mppp").title,
    source_sha256: mpppSource.file.sha256,
    source_manifest_sha256: manifestSha,
    extractor: manifest.extractor.pdf,
  };
  return { statutes, mppp, statutesMeta, mpppMeta };
}

/** Rows kept in the committed test fixtures. */
const FIXTURE_STATUTES: Record<string, string[]> = {
  "Patents Act": [
    "1",
    "2",
    "3",
    "5",
    "8",
    "11A",
    "25",
    "48",
    "53",
    "84",
    "107A",
    "122",
    "124A",
    "146",
  ],
  "Patent Rules": ["2", "13", "24B", "55", "71", "107A", "131", "138"],
  "Designs Act": ["2", "4", "11", "22"],
  "Trade Marks Act": ["2", "9", "11", "29", "36A"],
  "Copyright Act": ["2", "13", "14", "22", "52", "63"],
};
const FIXTURE_MPPP = [
  "01",
  "04.01",
  "04.02",
  "07.02",
  "07.02.01",
  "09",
  "09.01",
  "09.03",
  "09.03.01",
  "09.03.05",
  "09.03.05.04",
  "09.03.05.10",
  "09.04",
  "14.01",
];

if (import.meta.main) {
  const args = new Set(process.argv.slice(2));
  if (args.has("--fetch")) {
    const manifest = await fetchAll();
    await mkdir(dirname(manifestPath), { recursive: true });
    await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  }
  const manifest = await loadManifest();
  const { statutes, mppp, statutesMeta, mpppMeta } = await build(manifest);
  await writeDatabase(
    join(buildDir, "ipo_in_statutes.db"),
    STATUTES_DDL,
    STATUTE_COLUMNS,
    ["statute_name", "section_number", "title", "text"],
    statutes as unknown as Record<string, string | null>[],
    statutesMeta,
  );
  await writeDatabase(
    join(buildDir, "ipo_in_mppp.db"),
    MPPP_DDL,
    MPPP_COLUMNS,
    ["section_number", "title", "text"],
    mppp as unknown as Record<string, string | null>[],
    mpppMeta,
  );
  const counts: Record<string, number> = {};
  for (const row of statutes)
    counts[row.statute_name] = (counts[row.statute_name] ?? 0) + 1;
  console.log(
    JSON.stringify({
      statutes: counts,
      statutes_total: statutes.length,
      mppp: mppp.length,
    }),
  );
  if (args.has("--dump")) {
    await writeFile(
      join(buildDir, "statutes.json"),
      JSON.stringify(statutes, null, 1),
    );
    await writeFile(join(buildDir, "mppp.json"), JSON.stringify(mppp, null, 1));
  }
  if (args.has("--fixtures")) {
    const keep = statutes.filter((row) =>
      FIXTURE_STATUTES[row.statute_name]?.includes(row.section_number),
    );
    const keepMppp = mppp.filter((row) =>
      FIXTURE_MPPP.includes(row.section_number),
    );
    if (
      keep.length !== Object.values(FIXTURE_STATUTES).flat().length ||
      keepMppp.length !== FIXTURE_MPPP.length
    )
      throw new Error("A fixture row is missing from the build.");
    await writeDatabase(
      join(fixturesDir, "ipo_in_statutes.db"),
      STATUTES_DDL,
      STATUTE_COLUMNS,
      ["statute_name", "section_number", "title", "text"],
      keep as unknown as Record<string, string | null>[],
      statutesMeta,
    );
    await writeDatabase(
      join(fixturesDir, "ipo_in_mppp.db"),
      MPPP_DDL,
      MPPP_COLUMNS,
      ["section_number", "title", "text"],
      keepMppp as unknown as Record<string, string | null>[],
      mpppMeta,
    );
    console.log(
      `fixtures: ${keep.length} statute rows, ${keepMppp.length} MPPP rows`,
    );
  }
}

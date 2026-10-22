// Builds the INPI Brazil statutes corpus (Lei nº 9.279/1996, the LPI) as the
// Python connector's schema 1 SQLite/FTS5 database, from official sources:
//
// - Portuguese (authoritative): the consolidated text ("norma atualizada")
//   published by the Câmara dos Deputados legislative information service.
//   Python reads planalto.gov.br, which resets every plain HTTPS connection
//   from here (see the source manifest's access notes).
// - English: the WIPO Lex translation of the 1996 text (br003en.pdf), linked
//   from WIPO Lex legislation record 515 with a signed, expiring URL.
//
// Plain HTTPS GETs with an honest user agent; no browser, cookies or
// challenge handling.
//
// Usage (from typescript/):
//   bun scripts/build-inpi-br-statutes-corpus.ts --fetch     # download, rewrite the source manifest, build
//   bun scripts/build-inpi-br-statutes-corpus.ts             # rebuild from the archived sources (sha256-checked)
//   bun scripts/build-inpi-br-statutes-corpus.ts --fixture   # also rewrite the test fixture subset
// Options: --output PATH (default .data/inpi_br_statutes/inpi_br_statutes.db,
// must not exist), --raw DIR (default .data/inpi_br_statutes/raw).
import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import {
  getDocument,
  version as pdfjsVersion,
} from "pdfjs-dist/legacy/build/pdf.mjs";

const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
const root = join(import.meta.dir, "..");
const manifestPath = join(import.meta.dir, "inpi-br-statutes-sources.json");
const fixturePath = join(
  root,
  "tests/fixtures/inpi-br-statutes/inpi_br_statutes.db",
);

export const PT_URL =
  "https://www2.camara.leg.br/legin/fed/lei/1996/lei-9279-14-maio-1996-374644-normaatualizada-pl.html";
export const PLANALTO_URL =
  "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm";
export const WIPO_LEX_URL =
  "https://www.wipo.int/wipolex/en/legislation/details/515";
/** The unsigned location of the English PDF; WIPO Lex links it with a signature. */
export const EN_PDF_URL =
  "https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/br/br003en.pdf";

/** Articles copied into the committed test fixture. */
const FIXTURE_ARTICLES = [
  "art1",
  "art6",
  "art10",
  "art40",
  "art43",
  "art125",
  "art195",
  "art229-c",
  "art244",
];

// The schema the Python builder writes (corpus/schema.py, version 1), in
// DELETE journal mode instead of WAL.
const DDL = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections (
    rowid          INTEGER PRIMARY KEY,
    href           TEXT UNIQUE NOT NULL,
    article_number TEXT,
    title_pt       TEXT,
    title_en       TEXT,
    title_section  TEXT,
    text_pt        TEXT NOT NULL,
    text_en        TEXT,
    html_pt        TEXT NOT NULL,
    html_en        TEXT
);
CREATE INDEX idx_sections_article_number ON sections(article_number);
CREATE INDEX idx_sections_title_section ON sections(title_section);
CREATE VIRTUAL TABLE sections_fts USING fts5(
    article_number, title_pt, title_en, text_pt, text_en,
    content='sections', content_rowid='rowid', tokenize='porter unicode61'
);
CREATE TRIGGER sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, article_number, title_pt, title_en, text_pt, text_en)
    VALUES (new.rowid, new.article_number, new.title_pt, new.title_en, new.text_pt, new.text_en);
END;
CREATE TRIGGER sections_ad AFTER DELETE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, article_number, title_pt, title_en, text_pt, text_en)
    VALUES ('delete', old.rowid, old.article_number, old.title_pt, old.title_en, old.text_pt, old.text_en);
END;
CREATE TRIGGER sections_au AFTER UPDATE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, article_number, title_pt, title_en, text_pt, text_en)
    VALUES ('delete', old.rowid, old.article_number, old.title_pt, old.title_en, old.text_pt, old.text_en);
    INSERT INTO sections_fts(rowid, article_number, title_pt, title_en, text_pt, text_en)
    VALUES (new.rowid, new.article_number, new.title_pt, new.title_en, new.text_pt, new.text_en);
END;
`;

const squash = (value: string) => value.replace(/\s+/g, " ").trim();
const escapeHtml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const paragraphsHtml = (lines: string[]) =>
  lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("\n");

/**
 * First sentence of the caput, without the article label, capped at 120
 * characters. A period ends it only before a capital letter and not after an
 * abbreviation ("art.", "arts.", "No."); a semicolon or colon always does.
 */
export function titleFromCaput(caput: string): string {
  let end = caput.length;
  for (const match of caput.matchAll(/[.;:](?=\s|$)/g)) {
    const at = match.index;
    if (match[0] === ".") {
      const before = /(\S+)$/.exec(caput.slice(0, at))?.[1] ?? "";
      const after = caput.slice(at + 1).trimStart();
      if (/^(?:arts?|Arts?|No|Nos|n|nº|inc|§)$/.test(before)) continue;
      if (after && !/^[A-ZÀ-Ý(]/.test(after)) continue;
    }
    end = at + 1;
    break;
  }
  const first = caput.slice(0, end).trim();
  return first.length > 120 ? `${first.slice(0, 119).trimEnd()}…` : first;
}

// ---------------------------------------------------------------- Portuguese

export interface PtArticle {
  /** '6', '229-C'. */
  number: string;
  /** Python's slug: 'art6', 'art229-c'. */
  href: string;
  /** 'Art. 6', 'Art. 229-C'. */
  label: string;
  /** 'TÍTULO I — DAS PATENTES'; null for the preliminary provisions. */
  title_section: string | null;
  /** One entry per paragraph; the first starts with the article label. */
  paragraphs: string[];
  /** The caput without its label. */
  caput: string;
}

const ARTICLE_PT =
  /^Art\.\s*(\d{1,3})\s*(?:º|°|o(?=[\s.]))?\s*(?:-\s*([A-Z])\b)?\s*\.?\s*/;
const TITLE_LABEL = /^TÍTULO\s+([IVX]+)$/;
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"];

const ENTITIES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
};
/** Decode the character references the source pages use; unknown names fail. */
export function decodeEntities(value: string): string {
  return value.replace(
    /&(#x[\da-f]+|#\d+|[a-z]+);/gi,
    (_match, name: string) => {
      if (name[0] === "#")
        return String.fromCodePoint(
          name[1] === "x" || name[1] === "X"
            ? Number.parseInt(name.slice(2), 16)
            : Number.parseInt(name.slice(1), 10),
        );
      const known = ENTITIES[name];
      if (known === undefined) throw new Error(`Unknown HTML entity &${name};`);
      return known;
    },
  );
}
const plain = (fragment: string) =>
  squash(
    decodeEntities(
      fragment.replace(/<br\s*\/?>/gi, " ").replace(/<[^>]*>/g, ""),
    ),
  );

/** Paragraphs and headings of a page, in order; headings are h1-h6 or centred paragraphs. */
export function blocks(html: string): { center: boolean; text: string }[] {
  const body = html.slice(html.search(/<body\b/i));
  return [...body.matchAll(/<(p|h[1-6])\b([^>]*)>([\s\S]*?)<\/\1>/gi)]
    .map((match) => ({
      center:
        (match[1] as string).toLowerCase() !== "p" ||
        /\balign\s*=\s*"center"/i.test(match[2] as string),
      text: plain(match[3] as string),
    }))
    .filter((block) => block.text);
}

/** Articles of the Câmara consolidated page, in order, with their Title. */
export function parsePortuguese(html: string): {
  heading: string;
  articles: PtArticle[];
} {
  const paragraphs = blocks(html);
  const heading = paragraphs.find((p) =>
    /^LEI Nº 9\.279, DE 14 DE MAIO DE 1996$/.test(p.text),
  )?.text;
  if (!heading) throw new Error("PT: not the Lei nº 9.279/1996 page.");
  const articles: PtArticle[] = [];
  const titles: string[] = [];
  let title: string | null = null;
  let pendingTitle: string | null = null;
  let current: PtArticle | undefined;
  let ended = false;
  for (const p of paragraphs) {
    if (ended) break;
    if (p.center) {
      current = undefined;
      const label = TITLE_LABEL.exec(p.text);
      if (label) {
        pendingTitle = label[1] as string;
        continue;
      }
      if (pendingTitle) {
        title = `TÍTULO ${pendingTitle} — ${p.text}`;
        titles.push(pendingTitle);
      }
      pendingTitle = null;
      continue;
    }
    pendingTitle = null;
    const match = ARTICLE_PT.exec(p.text);
    if (match) {
      const number = match[2]
        ? `${match[1]}-${match[2]}`
        : (match[1] as string);
      const caput = p.text.slice(match[0].length).trim();
      current = {
        number,
        href: `art${number.toLowerCase()}`,
        label: `Art. ${number}`,
        title_section: title,
        paragraphs: [p.text],
        caput,
      };
      articles.push(current);
      continue;
    }
    if (/^Brasília,/.test(p.text)) {
      ended = true;
      continue;
    }
    // Text before Art. 1 (ementa, enacting formula) belongs to no article.
    if (current) current.paragraphs.push(p.text);
  }
  if (JSON.stringify(titles) !== JSON.stringify(ROMAN))
    throw new Error(`PT: unexpected Title sequence ${titles.join(", ")}.`);
  // Articles run in order: 1 … 244, a lettered article after its number.
  const seen = new Set<string>();
  let last = 0;
  for (const article of articles) {
    if (seen.has(article.href))
      throw new Error(`PT: duplicate ${article.label}.`);
    seen.add(article.href);
    const base = Number.parseInt(article.number, 10);
    const lettered = article.number.includes("-");
    if (base !== (lettered ? last : last + 1))
      throw new Error(`PT: ${article.label} out of order after Art. ${last}.`);
    last = base;
  }
  if (last !== 244) throw new Error(`PT: last article is ${last}, not 244.`);
  return { heading, articles };
}

/** Amending laws named in the consolidated text, latest by date. */
export function latestAmendment(articles: PtArticle[]): string | null {
  let best: { iso: string; text: string } | null = null;
  for (const article of articles)
    for (const line of article.paragraphs)
      for (const match of line.matchAll(
        /Lei (?:Complementar )?nº ([\d.]+), de (\d{1,2})\/(\d{1,2})\/(\d{4})/g,
      )) {
        const iso = `${match[4]}-${(match[3] as string).padStart(2, "0")}-${(match[2] as string).padStart(2, "0")}`;
        if (!best || iso > best.iso)
          best = {
            iso,
            text: `Lei nº ${match[1]}, de ${match[2]}/${match[3]}/${match[4]}`,
          };
      }
  return best ? `${best.text} (${best.iso})` : null;
}

// ---------------------------------------------------------------- English

interface Item {
  str: string;
  x: number;
  y: number;
  width: number;
  height: number;
  font: string;
}
export interface EnArticle {
  number: string;
  paragraphs: string[];
}

// Italic and heading fonts in the WIPO PDF report spaces as "f". Only these
// italic phrases occur inside article text; any other such item fails the build.
const ITALIC_FIXES: Record<string, string> = {
  exfofficiof: "ex officio",
  exfofficio: "ex officio",
  exf: "ex",
  officiof: "officio",
  perfse: "per se",
  forcefmajeure: "force majeure",
  infcamera: "in camera",
};

async function pdfItems(bytes: Uint8Array): Promise<Item[][]> {
  const document = await getDocument({
    data: bytes.slice(),
    isEvalSupported: false,
    disableFontFace: true,
    useSystemFonts: false,
    verbosity: 0,
  }).promise;
  try {
    const pages: Item[][] = [];
    for (let number = 1; number <= document.numPages; number++) {
      const page = await document.getPage(number);
      const content = await page.getTextContent();
      const items: Item[] = [];
      for (const item of content.items)
        if ("str" in item && item.str.trim())
          items.push({
            str: item.str,
            x: item.transform[4],
            y: item.transform[5],
            width: item.width,
            height: item.height,
            font: item.fontName,
          });
      pages.push(items);
      page.cleanup();
    }
    return pages;
  } finally {
    await document.destroy();
  }
}

/** Articles 1-244 of the WIPO Lex English translation (1996 text). */
export async function parseEnglish(pdf: Uint8Array): Promise<EnArticle[]> {
  const pages = await pdfItems(pdf);
  const articles: EnArticle[] = [];
  let current: EnArticle | undefined;
  let done = false;
  for (const items of pages) {
    if (done) break;
    const fonts = new Map<string, number>();
    for (const item of items)
      fonts.set(item.font, (fonts.get(item.font) ?? 0) + 1);
    const body = [...fonts].sort((a, b) => b[1] - a[1])[0]?.[0];
    // Group items into lines by baseline; superscripts sit a few points higher.
    const lines: Item[][] = [];
    for (const item of [...items].sort((a, b) => b.y - a.y || a.x - b.x)) {
      const line =
        lines.find(
          (l) => Math.abs((l[0] as Item).y - item.y) <= 7 && item.height < 10,
        ) ?? lines.find((l) => Math.abs((l[0] as Item).y - item.y) <= 2);
      if (line) line.push(item);
      else lines.push([item]);
    }
    for (const line of lines) {
      line.sort((a, b) => a.x - b.x);
      const first = line[0] as Item;
      // Headings, running page numbers and the title block are centred.
      if (first.x >= 150) continue;
      const head = /^(\d{1,3})\.$/.exec(first.str.trim());
      const expected = articles.length + 1;
      const indented = Math.abs(first.x - 99) < 6;
      if (head && indented && Number(head[1]) === expected) {
        current = { number: head[1] as string, paragraphs: [] };
        articles.push(current);
        line.shift();
        if (!line.length) continue;
      }
      if (!current) continue;
      if (/^Brasília,/.test(first.str)) {
        done = true;
        break;
      }
      let text = "";
      let end = Number.NEGATIVE_INFINITY;
      for (const item of line) {
        let str = item.str;
        if (item.font !== body && /f/.test(str) && !/\s/.test(str.trim())) {
          const fixed = ITALIC_FIXES[str.trim()];
          if (fixed === undefined && /[a-z]f[a-zA-Z]|[a-z]f$/.test(str))
            throw new Error(`EN: unexpected italic item '${str}'.`);
          if (fixed !== undefined) str = fixed + (str.endsWith("f") ? " " : "");
        }
        const gap = item.x - end;
        text += text && gap > 1.5 && !/\s$/.test(text) ? ` ${str}` : str;
        end = item.x + item.width;
      }
      text = squash(text);
      if (!text) continue;
      // A line starting at the paragraph indent opens a new paragraph.
      if (indented || !current.paragraphs.length) current.paragraphs.push(text);
      else current.paragraphs[current.paragraphs.length - 1] += ` ${text}`;
    }
  }
  if (articles.length !== 244)
    throw new Error(`EN: found ${articles.length} articles, not 244.`);
  for (const article of articles)
    if (!article.paragraphs.length)
      throw new Error(`EN: Article ${article.number} is empty.`);
  return articles;
}

// ---------------------------------------------------------------- rows

export interface Row {
  href: string;
  article_number: string;
  title_pt: string;
  title_en: string | null;
  title_section: string | null;
  text_pt: string;
  text_en: string | null;
  html_pt: string;
  html_en: string | null;
}

export function joinRows(pt: PtArticle[], en: EnArticle[]): Row[] {
  const english = new Map(en.map((article) => [article.number, article]));
  return pt.map((article) => {
    const translation = english.get(article.number);
    const enLines = translation
      ? [
          `Article ${article.number}. ${translation.paragraphs[0]}`,
          ...translation.paragraphs.slice(1),
        ]
      : null;
    return {
      href: article.href,
      article_number: article.label,
      title_pt: titleFromCaput(article.caput),
      title_en: translation
        ? titleFromCaput(translation.paragraphs[0] as string)
        : null,
      title_section: article.title_section,
      text_pt: article.paragraphs.join("\n"),
      text_en: enLines ? enLines.join("\n") : null,
      html_pt: paragraphsHtml(article.paragraphs),
      html_en: enLines ? paragraphsHtml(enLines) : null,
    };
  });
}

// ---------------------------------------------------------------- sources

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");
const now = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");

interface SourceFile {
  role: "pt" | "en_record" | "en_pdf";
  file: string;
  url: string;
  retrieved_at: string;
  last_modified: string | null;
  sha256: string;
  bytes: number;
}
interface SourceManifest {
  description: string;
  access_notes: string[];
  user_agent: string;
  extractor: { html: string; pdf: string };
  retrieved_at: string;
  pt: {
    publisher: string;
    heading: string;
    article_count: number;
    latest_amendment: string | null;
  };
  en: {
    publisher: string;
    version: string;
    pdf_modified: string | null;
    article_count: number;
  };
  files: SourceFile[];
}

async function get(url: string, accept: string) {
  const response = await fetch(url, {
    headers: { "user-agent": USER_AGENT, accept },
    redirect: "follow",
    signal: AbortSignal.timeout(120_000),
  });
  if (!response.ok) throw new Error(`GET ${url} returned ${response.status}.`);
  return {
    bytes: new Uint8Array(await response.arrayBuffer()),
    lastModified: response.headers.get("last-modified"),
    type: response.headers.get("content-type") ?? "",
  };
}

/** The signed English PDF link on the WIPO Lex record page. */
export function signedPdfLink(recordHtml: string): string {
  const match = recordHtml.match(
    /\bhref="(https:\/\/wipolex-res\.wipo\.int\/edocs\/lexdocs\/laws\/en\/br\/br003en\.pdf\?[^"]+)"/,
  );
  if (!match) throw new Error("WIPO Lex record has no English PDF link.");
  return decodeEntities(match[1] as string);
}

async function fetchAll(raw: string) {
  await mkdir(raw, { recursive: true });
  const files: SourceFile[] = [];
  const save = async (
    role: SourceFile["role"],
    file: string,
    url: string,
    got: Awaited<ReturnType<typeof get>>,
  ) => {
    await writeFile(join(raw, file), got.bytes);
    files.push({
      role,
      file,
      url,
      retrieved_at: now(),
      last_modified: got.lastModified,
      sha256: sha256(got.bytes),
      bytes: got.bytes.byteLength,
    });
    console.error(`${role}: ${got.bytes.byteLength} bytes from ${url}`);
  };
  const pt = await get(PT_URL, "text/html");
  if (!pt.type.includes("html")) throw new Error(`PT returned ${pt.type}.`);
  await save("pt", "camara-l9279-normaatualizada.html", PT_URL, pt);
  const record = await get(WIPO_LEX_URL, "text/html");
  await save("en_record", "wipolex-515.html", WIPO_LEX_URL, record);
  const signed = signedPdfLink(new TextDecoder().decode(record.bytes));
  const pdf = await get(signed, "application/pdf");
  if (!pdf.type.includes("pdf")) throw new Error(`EN returned ${pdf.type}.`);
  // Record the unsigned location; the signature expires.
  await save("en_pdf", "br003en.pdf", EN_PDF_URL, pdf);
  const ptParsed = parsePortuguese(new TextDecoder().decode(pt.bytes));
  const enParsed = await parseEnglish(pdf.bytes);
  const modified = /last-modified=(\d+)/.exec(signed)?.[1];
  const manifest: SourceManifest = {
    description:
      "Lei nº 9.279/1996 (Lei da Propriedade Industrial): the Portuguese consolidated text and the WIPO Lex English translation of the 1996 text.",
    access_notes: [
      `${PLANALTO_URL} (Python's source) reset the connection after the TLS handshake for every plain HTTPS request on October 22, 2026, including requests for the site's home page, so the Câmara dos Deputados consolidated text ("norma atualizada") is used instead.`,
      "The English PDF is linked from the WIPO Lex record with a CloudFront signature that expires; the manifest records the unsigned URL.",
      "The English translation is of the law as enacted in 1996. It does not include later amendments, so for amended articles it differs from the Portuguese text, which is authoritative.",
    ],
    user_agent: USER_AGENT,
    extractor: {
      html: "regular expressions over <p> and <h1>-<h6> blocks",
      pdf: `pdfjs-dist ${pdfjsVersion}`,
    },
    retrieved_at: files.map((file) => file.retrieved_at).sort()[0] as string,
    pt: {
      publisher:
        "Câmara dos Deputados, Centro de Documentação e Informação (Legislação Informatizada)",
      heading: ptParsed.heading,
      article_count: ptParsed.articles.length,
      latest_amendment: latestAmendment(ptParsed.articles),
    },
    en: {
      publisher: "WIPO Lex (World Intellectual Property Organization)",
      version:
        "Law No. 9.279 of May 14, 1996, as enacted (WIPO Lex record 515)",
      pdf_modified: modified
        ? new Date(Number(modified) * 1000)
            .toISOString()
            .replace(/\.\d+Z$/, "Z")
        : null,
      article_count: enParsed.length,
    },
    files,
  };
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}

/** Parse the archived sources, checking each against the source manifest. */
async function loadSources(raw: string) {
  const manifest = JSON.parse(
    await readFile(manifestPath, "utf8"),
  ) as SourceManifest;
  const read = async (role: SourceFile["role"]) => {
    const entry = manifest.files.find((file) => file.role === role);
    if (!entry) throw new Error(`${role} is not in the manifest.`);
    const bytes = new Uint8Array(await readFile(join(raw, entry.file)));
    if (sha256(bytes) !== entry.sha256)
      throw new Error(
        `${entry.file} does not match the manifest; run --fetch.`,
      );
    return bytes;
  };
  const pt = parsePortuguese(new TextDecoder().decode(await read("pt")));
  const en = await parseEnglish(await read("en_pdf"));
  if (pt.articles.length !== manifest.pt.article_count)
    throw new Error("PT article count differs from the manifest.");
  return { manifest, rows: joinRows(pt.articles, en) };
}

function writeDatabase(
  output: string,
  manifest: SourceManifest,
  rows: Row[],
  pick?: string[],
) {
  const db = new Database(output, { create: true, strict: true });
  try {
    db.exec("PRAGMA journal_mode = DELETE");
    db.exec(DDL);
    const insert = db.prepare(
      "INSERT INTO sections (href, article_number, title_pt, title_en, title_section, text_pt, text_en, html_pt, html_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    );
    let count = 0;
    db.transaction(() => {
      for (const row of rows) {
        if (pick && !pick.includes(row.href)) continue;
        insert.run(
          row.href,
          row.article_number,
          row.title_pt,
          row.title_en,
          row.title_section,
          row.text_pt,
          row.text_en,
          row.html_pt,
          row.html_en,
        );
        count++;
      }
      const source = (role: SourceFile["role"]) =>
        manifest.files.find((file) => file.role === role) as SourceFile;
      const meta: [string, string][] = [
        ["schema_version", "1"],
        ["source_pt", PT_URL],
        ["source_en", EN_PDF_URL],
        ["snapshot_date", manifest.retrieved_at.slice(0, 10)],
        ["lpi_year", "1996"],
        ["section_count", String(count)],
        [
          "source_version",
          manifest.pt.latest_amendment
            ? `consolidated through ${manifest.pt.latest_amendment.replace(/ \(.*\)$/, "")}`
            : "consolidated",
        ],
        ["latest_amendment", manifest.pt.latest_amendment ?? ""],
        ["source_en_version", manifest.en.version],
        ["source_en_record", WIPO_LEX_URL],
        ["retrieved_at", manifest.retrieved_at],
        ["source_pt_sha256", source("pt").sha256],
        ["source_en_sha256", source("en_pdf").sha256],
      ];
      if (pick) meta.push(["fixture_subset_of", String(rows.length)]);
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
  rows: Row[],
  pick?: string[],
) {
  await mkdir(dirname(output), { recursive: true });
  const temporary = `${output}.building`;
  await rm(temporary, { force: true });
  try {
    const count = writeDatabase(temporary, manifest, rows, pick);
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
    option("--raw") ?? join(root, ".data/inpi_br_statutes/raw"),
  );
  const output = resolve(
    option("--output") ??
      join(root, ".data/inpi_br_statutes/inpi_br_statutes.db"),
  );
  if (args.includes("--fetch")) await fetchAll(raw);
  if (await exists(output))
    throw new Error(`${output} exists; choose a new --output.`);
  const { manifest, rows } = await loadSources(raw);
  const count = await build(output, manifest, rows);
  const bytes = new Uint8Array(await readFile(output));
  console.log(
    JSON.stringify(
      {
        output,
        articles: count,
        with_english: rows.filter((row) => row.text_en).length,
        bytes: bytes.byteLength,
        sha256: sha256(bytes),
        latest_amendment: manifest.pt.latest_amendment,
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
      rows,
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

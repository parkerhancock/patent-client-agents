// Builds the KIPO Korea statutes SQLite/FTS5 corpus (the statute schema 1 the
// other statute corpora share) from the English translations of Korea's IP
// statutes by the Korea Legislation Research Institute (KLRI), as KLRI's
// elaw.klri.re.kr service publishes them. The translations have no legal
// effect; the Korean text controls.
//
// For each statute, --fetch looks the act up by its English name in elaw's
// statute-title list (the site's own search form, a form-encoded POST), takes
// the entry whose English name matches exactly (elaw lists the current
// translation only), and downloads that translation's full text with a plain
// GET of lawViewContent.do. An honest user agent; no browser, cookies or
// challenge handling. law.go.kr's English service carries the same KLRI
// translations, but serves bodies only by POST, drops large ones after 180
// seconds (the Copyright Act never loads) and lags elaw for the Design
// Protection and Trademark Acts.
//
// Each article is a `div.JO` after an anchor (`JO0029020` is Article 29-2);
// chapters and sections are `div.CT`/`div.ST`/`div.UT` and the addenda
// `div.addenda`, which are not stored. Every numbered article becomes a row,
// deleted ones included.
//
// Usage (from typescript/):
//   bun scripts/build-kipo-statutes-corpus.ts --fetch   # download the translations, rewrite the source manifest, build
//   bun scripts/build-kipo-statutes-corpus.ts           # rebuild from the archived HTML (sha256-checked)
//   bun scripts/build-kipo-statutes-corpus.ts --fixture # also rewrite the test fixture subset
// Options: --output PATH (default .data/kipo_statutes/kipo_statutes.db, must
// not exist), --raw DIR (default .data/kipo_statutes/raw).
// The output is a standalone DELETE-journal database, ready for
// scripts/compress-corpus.ts without a preparation step.
import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { DOMParser } from "linkedom";

const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
const ORIGIN = "https://elaw.klri.re.kr";
const LIST_URL = `${ORIGIN}/eng_service/lawNameList.do`;
const root = join(import.meta.dir, "..");
const manifestPath = join(import.meta.dir, "kipo-statutes-sources.json");
const fixturePath = join(root, "tests/fixtures/kipo-statutes/kipo_statutes.db");

export interface StatuteSource {
  statute: string;
  /** Citation name, as in 'Article 29 Patent Act'. */
  short_name: string;
  /** The English name elaw lists, upper case. */
  english_name: string;
}

/** The seven statutes, in the order the corpus lists them. */
export const SOURCES: StatuteSource[] = [
  { statute: "patent", short_name: "Patent Act", english_name: "PATENT ACT" },
  {
    statute: "utility_model",
    short_name: "Utility Model Act",
    english_name: "UTILITY MODEL ACT",
  },
  {
    statute: "design",
    short_name: "Design Protection Act",
    english_name: "DESIGN PROTECTION ACT",
  },
  {
    statute: "trademark",
    short_name: "Trademark Act",
    english_name: "TRADEMARK ACT",
  },
  {
    statute: "unfair_competition",
    short_name: "Unfair Competition Prevention and Trade Secret Protection Act",
    english_name:
      "UNFAIR COMPETITION PREVENTION AND TRADE SECRET PROTECTION ACT",
  },
  {
    statute: "invention_promotion",
    short_name: "Invention Promotion Act",
    english_name: "INVENTION PROMOTION ACT",
  },
  {
    statute: "copyright",
    short_name: "Copyright Act",
    english_name: "COPYRIGHT ACT",
  },
];

/** Articles copied into the committed test fixture. */
const FIXTURE_ARTICLES: Record<string, string[]> = {
  patent: ["2", "7-2", "26", "29", "94"],
  utility_model: ["4"],
  design: ["33", "76"],
  trademark: ["33", "34"],
  unfair_competition: ["2", "10"],
  invention_promotion: ["10"],
  copyright: ["35-5"],
};

// The statute schema (version 1) the ILPO, DPMA and other statute corpora
// use, in DELETE journal mode.
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

interface Node {
  tagName: string;
  id: string;
  textContent: string | null;
  getAttribute(name: string): string | null;
  querySelector(selector: string): Node | null;
  querySelectorAll(selector: string): Iterable<Node>;
  previousElementSibling: Node | null;
  children: Iterable<Node>;
}

const parseDocument = (html: string) =>
  new DOMParser().parseFromString(html, "text/html") as unknown as Node;

/** Collapse whitespace (including no-break spaces) to single spaces. */
export const clean = (value: string | null | undefined) =>
  (value ?? "").replace(/[\s 　]+/g, " ").trim();

export interface ParsedArticle {
  section_number: string;
  title: string | null;
  text: string;
}

/** The version the translation reflects, from elaw's current-history line. */
export interface TranslationInfo {
  english_title: string;
  /** e.g. "Act No. 20322, Feb. 20, 2024": the latest amendment translated. */
  version: string;
  act_number: string | null;
  /** Promulgation date of that amendment (ISO). */
  promulgation_date: string | null;
}

const MONTHS: Record<string, string> = {
  Jan: "01",
  Feb: "02",
  Mar: "03",
  Apr: "04",
  May: "05",
  Jun: "06",
  Jul: "07",
  Aug: "08",
  Sep: "09",
  Oct: "10",
  Nov: "11",
  Dec: "12",
};
/** "Feb. 20, 2024" to "2024-02-20". */
function isoDate(value: string | undefined) {
  const match = /^([A-Z][a-z]{2})[a-z]*\.?\s+(\d{1,2}),\s*(\d{4})$/.exec(
    value?.trim() ?? "",
  );
  const month = match ? MONTHS[match[1] as string] : undefined;
  return match && month
    ? `${match[3]}-${month}-${(match[2] as string).padStart(2, "0")}`
    : null;
}

/** The translation's English title and the amendment it reflects. */
export function parseTranslationInfo(html: string): TranslationInfo {
  const doc = parseDocument(html);
  const english = clean(
    doc.querySelector("#lawcontent div.lawname")?.textContent,
  );
  const version = clean(
    doc.querySelector("#lawcontent p.cur_history")?.textContent,
  );
  if (!english || !version)
    throw new Error("The translation has no title or version line.");
  const act = /Act No\.\s*([\d-]+),\s*(.+)$/.exec(version);
  return {
    english_title: english,
    version,
    act_number: act?.[1] ?? null,
    promulgation_date: isoDate(act?.[2]),
  };
}

/** One body line: a "(1)" / "1." / "(a)" marker cell and its text, or a plain run. */
function lineText(block: Node) {
  const cells = [...block.querySelectorAll("td")];
  return clean(
    cells.length
      ? cells.map((cell) => clean(cell.textContent)).join(" ")
      : block.textContent,
  );
}

const HEAD =
  /^Article\s+(?<num>\d{1,4}(?:-\d{1,3})?)(?:\s+\((?<title>.*)\)|\s+(?<deleted>Deleted\b.*))?$/s;

/** "JO0029020" to "29-2". */
function anchorNumber(id: string) {
  const match = /^JO(\d{4})(\d{2})(\d)$/.exec(id);
  if (!match || match[3] !== "0") return null;
  const base = String(Number(match[1]));
  return match[2] === "00" ? base : `${base}-${Number(match[2])}`;
}

/** [base, branch] for ordering checks. */
const order = (number: string) =>
  number.split("-").map(Number).concat([0]).slice(0, 2) as [number, number];

/**
 * Every numbered article in the body, in source order. The anchor
 * (`JO0029020`) and the printed heading (`Article 29-2 (…)`) must agree and
 * numbers are unique; `out_of_order` lists any the source prints before a
 * lower number (the Design Protection Act prints Article 141-2 after 142). A `div.JO` whose heading is not an article heading is
 * a continuation the source split off the previous article (the Design
 * Protection Act's Article 76) and is appended to it; `continuations` lists
 * them.
 */
export function parseArticles(html: string) {
  const doc = parseDocument(html);
  const articles: ParsedArticle[] = [];
  const continuations: string[] = [];
  const outOfOrder: string[] = [];
  let lines: string[] = [];
  const flush = () => {
    const last = articles.at(-1);
    if (last) last.text = [last.text, ...lines].filter(Boolean).join("\n");
    lines = [];
  };
  for (const jo of doc.querySelectorAll("#lawcontent div.JO")) {
    const anchor = jo.previousElementSibling;
    const expected = anchorNumber(anchor?.getAttribute("id") ?? "");
    if (!expected) throw new Error(`div.JO ${jo.id}: no article anchor.`);
    const head = clean(jo.querySelector("div.articletitle td")?.textContent);
    const body = [...jo.children]
      .filter((child) => child.getAttribute("class") !== "articletitle")
      .map(lineText)
      .filter(Boolean);
    const match = HEAD.exec(head);
    if (!match) {
      const previous = articles.at(-1);
      if (!previous) throw new Error(`'${head}' precedes every article.`);
      lines.push(head, ...body);
      continuations.push(previous.section_number);
      continue;
    }
    const number = match.groups?.num as string;
    if (number !== expected)
      throw new Error(
        `${anchor?.getAttribute("id")}: heading '${head}' does not match.`,
      );
    if (articles.some((item) => item.section_number === number))
      throw new Error(`Article ${number} appears twice.`);
    const previous = articles.at(-1);
    if (previous) {
      const [a, b] = order(previous.section_number);
      const [c, d] = order(number);
      if (!(c > a || (c === a && d > b))) outOfOrder.push(number);
    }
    flush();
    const deleted = match.groups?.deleted;
    const title = deleted ? null : clean(match.groups?.title) || null;
    const text = [deleted ? clean(deleted) : "", ...body].filter(Boolean);
    articles.push({ section_number: number, title, text: text.join("\n") });
  }
  flush();
  for (const article of articles)
    if (!article.text)
      throw new Error(`Article ${article.section_number} has no text.`);
  return { articles, continuations, out_of_order: outOfOrder };
}

/** elaw statute-title list rows: hseq, English and Korean names. */
export function parseLawList(html: string) {
  const doc = parseDocument(html);
  const entries: { hseq: string; name: string; korean_name: string | null }[] =
    [];
  for (const row of doc.querySelectorAll("table tbody tr")) {
    const links = [...row.querySelectorAll("a[href]")].filter((link) =>
      /lawView\.do\?hseq=\d+/.test(link.getAttribute("href") ?? ""),
    );
    const hseq = /hseq=(\d+)/.exec(links[0]?.getAttribute("href") ?? "")?.[1];
    const name = clean(links[0]?.textContent);
    if (hseq && name)
      entries.push({
        hseq,
        name,
        korean_name: clean(links[1]?.textContent) || null,
      });
  }
  return entries;
}

// ---------------------------------------------------------------- sources

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

interface SourceStatute extends TranslationInfo {
  statute: string;
  short_name: string;
  korean_title: string | null;
  hseq: string;
  /** elaw's page for this translation. */
  page_url: string;
  /** The translation's full text, the archived file. */
  content_url: string;
  retrieved_at: string;
  sha256: string;
  bytes: number;
  section_count: number;
  deleted_count: number;
  branch_count: number;
  /** Articles whose text the source split into a second block (joined back). */
  continuations: string[];
  /** Articles the source prints after a higher number. */
  out_of_order: string[];
}
interface SourceManifest {
  source: string;
  translator: string;
  authority_note: string;
  user_agent: string;
  access_note: string;
  retrieved_at: string;
  statutes: SourceStatute[];
}

export const pageUrl = (hseq: string) =>
  `${ORIGIN}/eng_service/lawView.do?hseq=${hseq}&lang=ENG`;
export const contentUrl = (hseq: string) =>
  `${ORIGIN}/eng_service/lawViewContent.do?hseq=${hseq}&lang=ENG`;
const rawPath = (raw: string, statute: string) => join(raw, `${statute}.html`);

async function request(url: string, init: RequestInit = {}) {
  const response = await fetch(url, {
    ...init,
    headers: {
      "user-agent": USER_AGENT,
      accept: "text/html",
      ...(init.headers ?? {}),
    },
    signal: AbortSignal.timeout(120_000),
  });
  if (!response.ok)
    throw new Error(
      `${init.method ?? "GET"} ${url} returned ${response.status}.`,
    );
  return new Uint8Array(await response.arrayBuffer());
}

async function fetchAll(raw: string) {
  await mkdir(raw, { recursive: true });
  const statutes: SourceStatute[] = [];
  for (const source of SOURCES) {
    const list = new TextDecoder().decode(
      await request(LIST_URL, {
        method: "POST",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          page: "1",
          searchType1: "english",
          searchValue: source.english_name,
        }).toString(),
      }),
    );
    const entry = parseLawList(list).find(
      (item) => item.name.toUpperCase() === source.english_name,
    );
    if (!entry)
      throw new Error(
        `${source.statute}: '${source.english_name}' is not listed.`,
      );
    const url = contentUrl(entry.hseq);
    const bytes = await request(url);
    const retrieved = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    const html = new TextDecoder().decode(bytes);
    const info = parseTranslationInfo(html);
    if (info.english_title.toUpperCase() !== source.english_name)
      throw new Error(`${source.statute}: ${url} is '${info.english_title}'.`);
    const parsed = parseArticles(html);
    await writeFile(rawPath(raw, source.statute), bytes);
    statutes.push({
      statute: source.statute,
      short_name: source.short_name,
      ...info,
      korean_title: entry.korean_name,
      hseq: entry.hseq,
      page_url: pageUrl(entry.hseq),
      content_url: url,
      retrieved_at: retrieved,
      sha256: sha256(bytes),
      bytes: bytes.byteLength,
      ...counts(parsed.articles),
      continuations: parsed.continuations,
      out_of_order: parsed.out_of_order,
    });
    console.error(
      `${source.statute}: ${parsed.articles.length} articles, ${bytes.byteLength} bytes (${info.version})`,
    );
  }
  const manifest: SourceManifest = {
    source:
      "KLRI Statutes of the Republic of Korea (https://elaw.klri.re.kr/eng_service/main.do), one HTML translation per statute",
    translator: "Korea Legislation Research Institute (KLRI)",
    authority_note:
      "The English translations are provided for reference, have no legal authority or official effect, and may not reflect the most recent amendments; the Korean text controls.",
    user_agent: USER_AGENT,
    access_note:
      "Each statute is found with elaw's statute-title search form (a form-encoded POST to lawNameList.do, as the site sends it); the translation is a plain GET of lawViewContent.do.",
    retrieved_at: statutes.map((item) => item.retrieved_at).sort()[0] as string,
    statutes,
  };
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}

function counts(articles: ParsedArticle[]) {
  return {
    section_count: articles.length,
    deleted_count: articles.filter((item) => /^Deleted\b/.test(item.text))
      .length,
    branch_count: articles.filter((item) => item.section_number.includes("-"))
      .length,
  };
}

interface ParsedStatute {
  source: StatuteSource;
  manifest: SourceStatute;
  articles: ParsedArticle[];
}

/** Parse the archived HTML, checking each file against the source manifest. */
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
    const bytes = new Uint8Array(await readFile(rawPath(raw, source.statute)));
    if (sha256(bytes) !== entry.sha256)
      throw new Error(
        `${source.statute}: archived HTML does not match the manifest; run --fetch.`,
      );
    const { articles } = parseArticles(new TextDecoder().decode(bytes));
    if (articles.length !== entry.section_count)
      throw new Error(
        `${source.statute}: article count differs from manifest.`,
      );
    parsed.push({ source, manifest: entry, articles });
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
    const total = statutes.reduce((sum, item) => sum + item.articles.length, 0);
    db.transaction(() => {
      for (const { source, manifest: entry, articles } of statutes)
        for (const article of articles) {
          if (pick && !pick[source.statute]?.includes(article.section_number))
            continue;
          insert.run(
            source.statute,
            article.section_number,
            `Article ${article.section_number} ${source.short_name}`,
            article.title,
            article.text,
            entry.page_url,
          );
          count++;
        }
      const statuteMeta = statutes.map(
        ({ source, manifest: entry, articles }) => ({
          statute: source.statute,
          short_name: source.short_name,
          english_title: entry.english_title,
          korean_title: entry.korean_title,
          version: entry.version,
          act_number: entry.act_number,
          promulgation_date: entry.promulgation_date,
          hseq: entry.hseq,
          page_url: entry.page_url,
          content_url: entry.content_url,
          retrieved_at: entry.retrieved_at,
          sha256: entry.sha256,
          section_count: articles.length,
        }),
      );
      const date = manifest.retrieved_at.slice(0, 10);
      const meta: [string, string][] = [
        ["schema_version", "1"],
        ["snapshot_date", date],
        [
          "source_version",
          `KLRI English translations (elaw.klri.re.kr), ${date}`,
        ],
        ["section_count", String(count)],
        ["retrieved_at", manifest.retrieved_at],
        ["authority_note", manifest.authority_note],
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
  const raw = resolve(option("--raw") ?? join(root, ".data/kipo_statutes/raw"));
  const output = resolve(
    option("--output") ?? join(root, ".data/kipo_statutes/kipo_statutes.db"),
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
          ...counts(item.articles),
          version: item.manifest.version,
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

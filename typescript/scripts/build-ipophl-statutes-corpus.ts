// Builds the IPOPHL Philippines statutes SQLite/FTS5 corpus (schema 1, the
// statute-row schema the ILPO corpus uses) from the LawPhil Project's HTML
// pages of the Intellectual Property Code (Republic Act No. 8293, 1997) and
// the three Acts that amend it: RA 9150 (2001, layout-designs), RA 9502
// (2008, cheaper medicines) and RA 10372 (2013). Each Act is stored as
// enacted, as its own statute; the amendments are not consolidated into the
// Code. Plain HTTPS GETs with an honest user agent; no browser, cookies or
// challenge handling.
//
// LawPhil prints each section as a paragraph that opens "Section N." (or
// "SEC. N.") with the heading in italics, followed by its subsections and
// list items as further paragraphs. Text an amending Act inserts into the
// Code is quoted, so a quoted "SEC. 22." never starts a section.
//
// Usage (from typescript/):
//   bun scripts/build-ipophl-statutes-corpus.ts --fetch   # download the four pages, rewrite the source manifest, build
//   bun scripts/build-ipophl-statutes-corpus.ts           # rebuild from the archived pages (sha256-checked)
//   bun scripts/build-ipophl-statutes-corpus.ts --fixture # also rewrite the test fixture subset
// Options: --output PATH (default .data/ipophl_statutes/ipophl_statutes.db,
// must not exist), --raw DIR (default .data/ipophl_statutes/raw).
// The output is a standalone DELETE-journal database, ready for
// scripts/compress-corpus.ts without a preparation step.
import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { parseHTML } from "linkedom";

const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
const root = join(import.meta.dir, "..");
const manifestPath = join(import.meta.dir, "ipophl-statutes-sources.json");
const fixturePath = join(
  root,
  "tests/fixtures/ipophl-statutes/ipophl_statutes.db",
);

export interface ActSource {
  statute: string;
  /** Used in labels: "Section 21 RA 8293". */
  short_name: string;
  title: string;
  /** "code" for RA 8293 itself, "amendment" for an Act amending it. */
  role: "code" | "amendment";
  /** Date of approval, as the page prints it. */
  approved: string;
  url: string;
  /** Drop centred paragraphs (Part and Chapter headings) between sections. */
  dropCentered?: boolean;
  /** Section numbers the page does not carry, so the sequence may skip them. */
  missing?: string[];
  /** Notes about the page's text, appended to a section as "[Source note: …]". */
  notes?: Record<string, string>;
  /** Code sections an Act amends in a section the page does not carry. */
  extraAmends?: Record<string, string>;
}

const LAWPHIL = "https://lawphil.net/statutes/repacts";

/** The Code and its three amending Acts, in the order the corpus lists them. */
export const SOURCES: ActSource[] = [
  {
    statute: "ra8293",
    short_name: "RA 8293",
    title:
      "Intellectual Property Code of the Philippines (Republic Act No. 8293)",
    role: "code",
    approved: "1997-06-06",
    url: `${LAWPHIL}/ra1997/ra_8293_1997.html`,
    dropCentered: true,
  },
  {
    statute: "ra9150",
    short_name: "RA 9150",
    title:
      "Republic Act No. 9150 (protection of layout-designs of integrated circuits)",
    role: "amendment",
    approved: "2001-08-06",
    url: `${LAWPHIL}/ra2001/ra_9150_2001.html`,
  },
  {
    statute: "ra9502",
    short_name: "RA 9502",
    title:
      "Universally Accessible Cheaper and Quality Medicines Act of 2008 (Republic Act No. 9502)",
    role: "amendment",
    approved: "2008-06-06",
    url: `${LAWPHIL}/ra2008/ra_9502_2008.html`,
    missing: ["8"],
    notes: {
      "7": "LawPhil's page repeats part of the new Section 72 and lacks the rest of this section and the start of Section 8, which amends Section 74 (Use of Invention by Government) of RA 8293. The quoted subsections 74.3 and 74.4 above belong to Section 8. The page has no Section 8, and LawPhil's PDF of this Act is a scanned image.",
    },
    extraAmends: { "74": "Section 8 RA 9502 (not on the source page)" },
  },
  {
    statute: "ra10372",
    short_name: "RA 10372",
    title:
      "Republic Act No. 10372 (amending certain provisions of the Intellectual Property Code)",
    role: "amendment",
    approved: "2013-02-28",
    url: `${LAWPHIL}/ra2013/ra_10372_2013.html`,
    // Section 28 renumbers Section 230 "and all succeeding sections".
    extraAmends: Object.fromEntries(
      Array.from({ length: 11 }, (_, index) => [
        String(231 + index),
        "Section 28 RA 10372",
      ]),
    ),
  },
];

/** Sections copied into the committed test fixture. */
const FIXTURE_SECTIONS: Record<string, string[]> = {
  ra8293: ["1", "4", "21", "22", "26", "72", "74", "123", "171", "172"],
  ra9150: ["1", "3"],
  ra9502: ["5", "7"],
  ra10372: ["3", "28"],
};

// The statute-row schema (version 1) the ILPO and other statute corpora
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

export interface ParsedSection {
  section_number: string;
  title: string | null;
  text: string;
}

/** The page's declared charset; LawPhil serves windows-1252. */
export function decodePage(bytes: Uint8Array): string {
  const head = new TextDecoder("latin1").decode(bytes.slice(0, 2048));
  const charset = /charset=["']?([\w-]+)/i.exec(head)?.[1] ?? "windows-1252";
  return new TextDecoder(charset).decode(bytes);
}

const clean = (value: string) =>
  value
    .replace(/[ \s]+/g, " ")
    .replace(/\s+([,;:])/g, "$1")
    .trim();

/** A paragraph's lines: <br> breaks a line, everything else is inline text. */
function paragraphLines(element: Element): string[] {
  let out = "";
  const walk = (node: Node) => {
    if (node.nodeType === 3) out += node.textContent ?? "";
    else if (node.nodeType === 1) {
      if ((node as Element).tagName === "BR") out += "\n";
      else for (const child of node.childNodes) walk(child);
    }
  };
  walk(element);
  return out.split("\n").map(clean).filter(Boolean);
}

const START =
  /^(?:SECTION|Section|SEC\.|Sec\.)\s*(\d{1,3})\s*[.,]\s*(?<rest>[\s\S]*)$/;
const QUOTED = /^["“”'‘]/;
/** A heading set in roman type: "Implementing Rules … Philippines. - Unless". */
const ROMAN_HEADING = /^([A-Z][^"“]{2,200}?)\.\s*[-–—]\s+([\s\S]*)$/;

/** The Act's long title: the "AN ACT …" paragraph, else LawPhil's subject line. */
export function pageTitle(html: string): string | null {
  const { document } = parseHTML(html);
  for (const paragraph of document.querySelectorAll("p")) {
    const text = clean(paragraph.textContent ?? "");
    if (/^AN ACT\b/.test(text)) return text;
  }
  const subject = document
    .querySelector('meta[name="subject"]')
    ?.getAttribute("content");
  return subject ? clean(subject.replace(/^[\w ]+ - /, "")) : null;
}

/**
 * Every numbered section of one Act, in order. A section starts at an
 * unquoted paragraph "Section N." whose number follows the previous one; the
 * Act ends at the "Approved" line after its last section.
 */
export function parseAct(source: ActSource, html: string): ParsedSection[] {
  const { document } = parseHTML(html);
  const missing = new Set(source.missing ?? []);
  const nextNumber = (previous: number) => {
    let next = previous + 1;
    while (missing.has(String(next))) next++;
    return next;
  };
  const sections: { number: string; title: string | null; lines: string[] }[] =
    [];
  for (const paragraph of document.querySelectorAll("p, tr")) {
    // Table rows (RA 8293 Section 119's list of applicable sections) are
    // one line each; layout rows that hold paragraphs are skipped.
    if (paragraph.tagName === "TR" && paragraph.querySelector("p")) continue;
    const lines =
      paragraph.tagName === "TR"
        ? [
            clean(
              [...paragraph.querySelectorAll("td, th")]
                .map((cell) => cell.textContent ?? "")
                .join(" "),
            ),
          ].filter(Boolean)
        : paragraphLines(paragraph);
    const first = lines[0];
    if (!first) continue;
    const current = sections.at(-1);
    if (current && /^Approved\b/.test(first)) break;
    const match = QUOTED.test(first) ? null : START.exec(first);
    const expected = nextNumber(current ? Number(current.number) : 0);
    if (match && Number(match[1]) === expected) {
      let rest = match.groups?.rest ?? "";
      let title: string | null = null;
      const italic = paragraph.querySelector("i");
      const italicText = italic ? clean(italic.textContent ?? "") : "";
      if (italicText && rest.startsWith(italicText)) {
        title = italicText.replace(/[\s.:]+$/, "");
        rest = rest.slice(italicText.length).replace(/^[\s.:]*[-–—]+\s*/, "");
      } else {
        const roman = ROMAN_HEADING.exec(rest);
        if (roman?.[1] && !/\bhereby\b/i.test(roman[1])) {
          title = roman[1].trim();
          rest = roman[2] ?? "";
        }
      }
      sections.push({
        number: String(expected),
        title: title || null,
        lines: [rest, ...lines.slice(1)].map(clean).filter(Boolean),
      });
      continue;
    }
    if (!current) continue;
    if (
      source.dropCentered &&
      paragraph.getAttribute("align")?.toLowerCase() === "center"
    )
      continue;
    current.lines.push(...lines);
  }
  const last = sections.at(-1);
  if (!last) throw new Error(`${source.statute}: no sections found.`);
  for (const number of missing)
    if (Number(number) > Number(last.number))
      throw new Error(
        `${source.statute}: missing section ${number} is past the end.`,
      );
  return sections.map((section) => {
    const lines = [...section.lines];
    const note = source.notes?.[section.number];
    if (note) lines.push(`[Source note: ${note}]`);
    return {
      section_number: section.number,
      title: section.title,
      text: lines.join("\n") || section.title || "",
    };
  });
}

/**
 * Sections of RA 8293 that each amending-Act section names in its opening
 * clause ("Section 22 of Republic Act No. 8293 … is hereby amended", "A new
 * Section 9A is hereby inserted after Section 9 …"). A pointer to where to
 * look, not a consolidation. Clauses that name another Act (the Generics Act,
 * the Pharmacy Law) are skipped.
 */
export function amendmentIndex(
  acts: { source: ActSource; sections: ParsedSection[] }[],
): Record<string, string[]> {
  const index = new Map<string, string[]>();
  const add = (number: string, label: string) => {
    const list = index.get(number) ?? [];
    if (!list.includes(label)) list.push(label);
    index.set(number, list);
  };
  for (const { source, sections } of acts) {
    if (source.role !== "amendment") continue;
    for (const section of sections) {
      const lead = section.text.split("\n")[0] ?? "";
      const clause = lead.split(/\bto read as follows\b/i)[0] ?? lead;
      if (!/\b(amended|inserted|renumbered|deleted|added)\b/i.test(clause))
        continue;
      const acts = [
        ...clause.matchAll(/\b(?:Republic Act|R\.A\.)\s*No\.?\s*(\d+)/gi),
      ];
      if (acts.some((found) => found[1] !== "8293")) continue;
      const label = `Section ${section.section_number} ${source.short_name}`;
      for (const group of clause.matchAll(
        /\bSections?\s+((?:\d{1,3}(?:-?[A-Z])?(?:\.\d+)*\.?(?:\s*(?:,|and)\s*)?)+)/g,
      ))
        for (const number of (group[1] ?? "").matchAll(
          /(\d{1,3})(?:-?([A-Z]))?(?:\.\d+)*/g,
        ))
          add(`${number[1]}${number[2] ?? ""}`, label);
    }
    for (const [number, label] of Object.entries(source.extraAmends ?? {}))
      add(number, label);
  }
  return Object.fromEntries(
    [...index.entries()].sort(
      ([a], [b]) =>
        Number.parseInt(a, 10) - Number.parseInt(b, 10) || (a < b ? -1 : 1),
    ),
  );
}

// ---------------------------------------------------------------- sources

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

interface SourceAct {
  statute: string;
  short_name: string;
  title: string;
  role: "code" | "amendment";
  approved: string;
  url: string;
  /** LawPhil's subject line for the page. */
  page_title: string | null;
  /** The server's Last-Modified header for the page. */
  last_modified: string | null;
  retrieved_at: string;
  encoding: string;
  sha256: string;
  bytes: number;
  section_count: number;
  missing_sections: string[];
}
interface SourceManifest {
  source: string;
  user_agent: string;
  retrieved_at: string;
  acts: SourceAct[];
}

const rawPath = (raw: string, url: string) =>
  join(raw, url.split("/").at(-1) as string);

async function fetchAll(raw: string) {
  await mkdir(raw, { recursive: true });
  const acts: SourceAct[] = [];
  for (const source of SOURCES) {
    const response = await fetch(source.url, {
      headers: { "user-agent": USER_AGENT, accept: "text/html" },
    });
    if (!response.ok)
      throw new Error(`GET ${source.url} returned ${response.status}.`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    const retrieved = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    const html = decodePage(bytes);
    const sections = parseAct(source, html);
    await writeFile(rawPath(raw, source.url), bytes);
    const modified = response.headers.get("last-modified");
    acts.push({
      statute: source.statute,
      short_name: source.short_name,
      title: source.title,
      role: source.role,
      approved: source.approved,
      url: source.url,
      page_title: pageTitle(html),
      last_modified: modified
        ? new Date(modified).toISOString().replace(/\.\d+Z$/, "Z")
        : null,
      retrieved_at: retrieved,
      encoding:
        /charset=["']?([\w-]+)/i
          .exec(html.slice(0, 2048))?.[1]
          ?.toLowerCase() ?? "windows-1252",
      sha256: sha256(bytes),
      bytes: bytes.byteLength,
      section_count: sections.length,
      missing_sections: source.missing ?? [],
    });
    console.error(
      `${source.statute}: ${sections.length} sections, ${bytes.byteLength} bytes`,
    );
    await Bun.sleep(1000);
  }
  const manifest: SourceManifest = {
    source:
      "The LawPhil Project (https://lawphil.net/), Arellano Law Foundation: one HTML page per Act, as enacted",
    user_agent: USER_AGENT,
    retrieved_at: acts.map((item) => item.retrieved_at).sort()[0] as string,
    acts,
  };
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}

interface ParsedAct {
  source: ActSource;
  manifest: SourceAct;
  sections: ParsedSection[];
}

/** Parse the archived pages, checking each against the source manifest. */
export async function loadActs(raw: string) {
  const manifest = JSON.parse(
    await readFile(manifestPath, "utf8"),
  ) as SourceManifest;
  const parsed: ParsedAct[] = [];
  for (const source of SOURCES) {
    const entry = manifest.acts.find((item) => item.statute === source.statute);
    if (!entry) throw new Error(`${source.statute} is not in the manifest.`);
    const bytes = new Uint8Array(await readFile(rawPath(raw, entry.url)));
    if (sha256(bytes) !== entry.sha256)
      throw new Error(
        `${source.statute}: archived page does not match the manifest; run --fetch.`,
      );
    const sections = parseAct(source, decodePage(bytes));
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
  acts: ParsedAct[],
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
    const total = acts.reduce((sum, item) => sum + item.sections.length, 0);
    db.transaction(() => {
      for (const { source, sections } of acts)
        for (const section of sections) {
          if (pick && !pick[source.statute]?.includes(section.section_number))
            continue;
          insert.run(
            source.statute,
            section.section_number,
            `Section ${section.section_number} ${source.short_name}`,
            section.title,
            section.text,
            source.url,
          );
          count++;
        }
      const statuteMeta = acts.map(({ source, manifest: entry, sections }) => ({
        statute: source.statute,
        short_name: source.short_name,
        title: source.title,
        role: source.role,
        approved: source.approved,
        page_title: entry.page_title,
        page_url: entry.url,
        last_modified: entry.last_modified,
        retrieved_at: entry.retrieved_at,
        sha256: entry.sha256,
        section_count: sections.length,
        missing_sections: entry.missing_sections,
      }));
      const date = manifest.retrieved_at.slice(0, 10);
      const meta: [string, string][] = [
        ["schema_version", "1"],
        ["snapshot_date", date],
        ["source_version", `LawPhil, Acts as enacted, ${date}`],
        ["section_count", String(count)],
        ["retrieved_at", manifest.retrieved_at],
        ["statutes", JSON.stringify(statuteMeta)],
        ["amendments", JSON.stringify(amendmentIndex(acts))],
        [
          "text_status",
          "Each Act is stored as enacted. RA 8293's sections are its 1997 text; the amendments made by RA 9150, RA 9502 and RA 10372 are separate statutes in this corpus and are not consolidated into it. RA 10372 Section 28 renumbered RA 8293 Section 230 and the sections after it (so 1997 Sections 230 to 241 are now 231 to 242).",
        ],
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
  acts: ParsedAct[],
  pick?: Record<string, string[]>,
) {
  await mkdir(dirname(output), { recursive: true });
  const temporary = `${output}.building`;
  await rm(temporary, { force: true });
  try {
    const count = writeDatabase(temporary, manifest, acts, pick);
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
    option("--raw") ?? join(root, ".data/ipophl_statutes/raw"),
  );
  const output = resolve(
    option("--output") ??
      join(root, ".data/ipophl_statutes/ipophl_statutes.db"),
  );
  if (args.includes("--fetch")) await fetchAll(raw);
  if (await exists(output))
    throw new Error(`${output} exists; choose a new --output.`);
  const { manifest, parsed } = await loadActs(raw);
  const count = await build(output, manifest, parsed);
  const bytes = new Uint8Array(await readFile(output));
  console.log(
    JSON.stringify(
      {
        output,
        sections: count,
        bytes: bytes.byteLength,
        sha256: sha256(bytes),
        acts: parsed.map((item) => ({
          statute: item.source.statute,
          sections: item.sections.length,
          untitled: item.sections
            .filter((section) => !section.title)
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

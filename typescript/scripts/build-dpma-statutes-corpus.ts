// Builds the DPMA statutes SQLite/FTS5 corpus (schema 1, as the Python
// connector defines it) from the official consolidated XML published by
// gesetze-im-internet.de (DTD gii-norm 1.01). One plain HTTPS GET per Act,
// with an honest user agent; no browser, cookies or challenge handling.
//
// Usage (from typescript/):
//   bun scripts/build-dpma-statutes-corpus.ts --fetch   # download the six zips, rewrite the source manifest, build
//   bun scripts/build-dpma-statutes-corpus.ts           # rebuild from the archived zips (sha256-checked)
//   bun scripts/build-dpma-statutes-corpus.ts --fixture # also rewrite the test fixture subset
// Options: --output PATH (default .data/dpma_statutes/dpma_statutes.db, must
// not exist), --raw DIR (default .data/dpma_statutes/raw), --connect-ip IP
// (with --fetch: connect to this address when the local resolver cannot
// resolve the host; TLS is still verified against the host name).
// The output is a standalone DELETE-journal database, ready for
// scripts/compress-corpus.ts without a preparation step.
import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { unzipSync } from "fflate";

const HOST = "www.gesetze-im-internet.de";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
const root = join(import.meta.dir, "..");
const manifestPath = join(import.meta.dir, "dpma-statutes-sources.json");
const fixturePath = join(root, "tests/fixtures/dpma-statutes/dpma_statutes.db");

/** The six Acts the connector covers and their gesetze-im-internet.de slugs. */
export const ACTS = [
  { statute: "PatG", slug: "patg" },
  { statute: "MarkenG", slug: "markeng" },
  { statute: "GebrMG", slug: "gebrmg" },
  // The Designgesetz keeps its pre-2014 slug (Geschmacksmustergesetz 2004).
  { statute: "DesignG", slug: "geschmmg_2004" },
  { statute: "UrhG", slug: "urhg" },
  { statute: "GeschGehG", slug: "geschgehg" },
] as const;

/** Sections copied into the committed test fixture. */
const FIXTURE_SECTIONS: Record<string, string[]> = {
  PatG: ["1", "3", "9", "16a", "18", "139"],
  MarkenG: ["14", "32"],
  GebrMG: ["1", "11"],
  DesignG: ["1"],
  UrhG: ["1", "97", "Anlage"],
  GeschGehG: ["1", "2"],
};

// The schema the Python builder writes (corpus/schema.py, version 1), in
// DELETE journal mode instead of WAL.
const DDL = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections (
    rowid    INTEGER PRIMARY KEY,
    statute  TEXT NOT NULL,
    section  TEXT NOT NULL,
    title    TEXT,
    text     TEXT NOT NULL,
    UNIQUE(statute, section)
);
CREATE INDEX idx_sections_statute ON sections(statute);
CREATE INDEX idx_sections_section ON sections(section);
CREATE VIRTUAL TABLE sections_fts USING fts5(
    statute, section, title, text,
    content='sections', content_rowid='rowid', tokenize='porter unicode61'
);
CREATE TRIGGER sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, statute, section, title, text)
    VALUES (new.rowid, new.statute, new.section, new.title, new.text);
END;
CREATE TRIGGER sections_ad AFTER DELETE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, statute, section, title, text)
    VALUES ('delete', old.rowid, old.statute, old.section, old.title, old.text);
END;
CREATE TRIGGER sections_au AFTER UPDATE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, statute, section, title, text)
    VALUES ('delete', old.rowid, old.statute, old.section, old.title, old.text);
    INSERT INTO sections_fts(rowid, statute, section, title, text)
    VALUES (new.rowid, new.statute, new.section, new.title, new.text);
END;
`;

// ---------------------------------------------------------------- XML

export interface XmlElement {
  name: string;
  attrs: Record<string, string>;
  children: XmlNode[];
}
export type XmlNode = XmlElement | string;

const ENTITIES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
};
function decode(value: string): string {
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
      if (known === undefined) throw new Error(`Unknown XML entity &${name};`);
      return known;
    },
  );
}

/** A minimal, strict parser for the gii-norm documents (no CDATA or DTD subset). */
export function parseXml(xml: string): XmlElement {
  const top: XmlElement = { name: "#document", attrs: {}, children: [] };
  const stack: XmlElement[] = [top];
  const tag =
    /<(\/?)([A-Za-z][\w.:-]*)((?:\s+[\w.:-]+\s*=\s*(?:"[^"]*"|'[^']*'))*)\s*(\/?)>|<\?[\s\S]*?\?>|<!DOCTYPE[^>]*>|<!--[\s\S]*?-->/g;
  let last = 0;
  for (const match of xml.matchAll(tag)) {
    const between = xml.slice(last, match.index);
    if (between.includes("<")) throw new Error("Malformed XML markup.");
    const parent = stack.at(-1) as XmlElement;
    if (between) parent.children.push(decode(between));
    last = match.index + match[0].length;
    const name = match[2];
    if (!name) continue;
    if (match[1]) {
      const open = stack.pop();
      if (!open || open.name !== name || stack.length === 0)
        throw new Error(`Mismatched </${name}>.`);
      continue;
    }
    const attrs: Record<string, string> = {};
    for (const attr of (match[3] ?? "").matchAll(
      /([\w.:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g,
    ))
      attrs[attr[1] as string] = decode(attr[2] ?? attr[3] ?? "");
    const element: XmlElement = { name, attrs, children: [] };
    parent.children.push(element);
    if (!match[4]) stack.push(element);
  }
  if (xml.slice(last).trim() || stack.length !== 1)
    throw new Error("Unterminated XML document.");
  const roots = top.children.filter(
    (node): node is XmlElement => typeof node !== "string",
  );
  if (roots.length !== 1) throw new Error("Expected one root element.");
  return roots[0] as XmlElement;
}

const elements = (node: XmlElement, name?: string) =>
  node.children.filter(
    (child): child is XmlElement =>
      typeof child !== "string" && (!name || child.name === name),
  );
const child = (node: XmlElement | undefined, name: string) =>
  node ? elements(node, name)[0] : undefined;

// ---------------------------------------------------------------- text

/** Annotations that are not statute text (Fundstelle notes, layout markers). */
const SKIP = new Set(["noindex", "kommentar", "ABWFORMAT", "FnR"]);
/** Elements that start their own line(s). */
const BLOCK = new Set([
  "P",
  "DL",
  "table",
  "Title",
  "pre",
  "LA",
  "TOC",
  "Ident",
]);

/** Inline text of a node with whitespace collapsed (BR as a space). */
export function inlineText(node: XmlNode): string {
  if (typeof node === "string") return node;
  if (SKIP.has(node.name)) return "";
  if (node.name === "BR") return " ";
  return node.children.map(inlineText).join("");
}
const squash = (value: string) => value.replace(/\s+/g, " ").trim();

/**
 * Plain-text lines for a content node: one line per paragraph (Abs.), one per
 * list item (Nr., Buchst.) with its label and two spaces of indent per list
 * level, one per table row (cells joined by " | ").
 */
function blockLines(nodes: XmlNode[], indent: string, lines: string[]) {
  let buffer = "";
  const flush = () => {
    const line = squash(buffer);
    if (line) lines.push(indent + line);
    buffer = "";
  };
  for (const node of nodes) {
    if (typeof node === "string") {
      buffer += node;
      continue;
    }
    if (SKIP.has(node.name)) continue;
    if (node.name === "BR") {
      flush();
      continue;
    }
    if (!BLOCK.has(node.name)) {
      if (elements(node).some((inner) => BLOCK.has(inner.name))) {
        flush();
        blockLines(node.children, indent, lines);
      } else buffer += inlineText(node);
      continue;
    }
    flush();
    if (node.name === "DL") {
      let label = "";
      for (const item of elements(node)) {
        if (item.name === "DT") {
          label = squash(inlineText(item));
          continue;
        }
        if (item.name !== "DD") continue;
        const inner: string[] = [];
        blockLines(item.children, `${indent}  `, inner);
        const [first, ...rest] = inner;
        lines.push(
          `${indent}${label}${first ? ` ${first.trimStart()}` : ""}`.trimEnd(),
          ...rest,
        );
        label = "";
      }
    } else if (node.name === "table") {
      for (const row of collect(node, "row")) {
        const cells = elements(row, "entry").map((entry) =>
          squash(inlineText(entry)),
        );
        if (cells.some(Boolean)) lines.push(indent + cells.join(" | "));
      }
    } else if (node.name === "pre") {
      for (const line of node.children
        .map((part) =>
          typeof part === "string"
            ? part
            : part.name === "BR"
              ? "\n"
              : inlineText(part),
        )
        .join("")
        .split("\n"))
        if (line.trim()) lines.push(indent + line.trimEnd());
    } else blockLines(node.children, indent, lines);
  }
  flush();
}
function collect(node: XmlElement, name: string): XmlElement[] {
  return elements(node).flatMap((inner) =>
    inner.name === name ? [inner] : collect(inner, name),
  );
}

export function contentText(content: XmlElement | undefined): string {
  if (!content) return "";
  const lines: string[] = [];
  blockLines(content.children, "", lines);
  return lines.join("\n");
}

// ---------------------------------------------------------------- laws

export interface ParsedSection {
  section: string;
  title: string | null;
  text: string;
}
export interface ParsedAct {
  statute: string;
  doknr: string;
  builddate: string;
  long_title: string;
  enacted_on: string | null;
  /** Official promulgation reference, e.g. 'BGBl I 2019, 466'. */
  fundstelle: string | null;
  stand: string | null;
  amended_on: string | null;
  stand_notes: { type: string; text: string }[];
  sections: ParsedSection[];
}

/** '20.5.2026' in a Stand note to '2026-05-20' (the last date mentioned). */
function standDate(note: string | null): string | null {
  const dates = [
    ...(note ?? "").matchAll(/\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b/g),
  ];
  const last = dates.at(-1);
  return last
    ? `${last[3]}-${(last[2] as string).padStart(2, "0")}-${(last[1] as string).padStart(2, "0")}`
    : null;
}

/** '§§ 18 und 19' → ['18', '19']; '§§ 161 bis 163' → ['161', '162', '163']. */
export function sectionNumbers(enbez: string): string[] | null {
  const cleaned = enbez.replace(/^\(XXXX\)\s*/, "").trim();
  const single = /^§\s*(\d+[a-z]?)$/i.exec(cleaned);
  if (single) return [(single[1] as string).toLowerCase()];
  const range = /^§§\s*(\d+)\s+bis\s+(\d+)$/.exec(cleaned);
  if (range) {
    const [from, to] = [Number(range[1]), Number(range[2])];
    if (to <= from || to - from > 50) return null;
    return Array.from({ length: to - from + 1 }, (_, index) =>
      String(from + index),
    );
  }
  const list =
    /^§§\s*(\d+[a-z]?(?:\s*,\s*\d+[a-z]?)*\s+und\s+\d+[a-z]?)$/i.exec(cleaned);
  if (list)
    return (list[1] as string)
      .split(/\s*,\s*|\s+und\s+/)
      .map((part) => part.toLowerCase());
  return null;
}

/** Every § of one Act (and its Anlage), in document order, with Act metadata. */
export function parseAct(statute: string, xml: string): ParsedAct {
  const doc = parseXml(xml);
  if (doc.name !== "dokumente") throw new Error("Not a gii-norm document.");
  const norms = elements(doc, "norm");
  const head = norms[0];
  const meta = child(head, "metadaten");
  if (!head || !meta) throw new Error(`${statute}: no head norm.`);
  const abbreviations = [
    ...elements(meta, "jurabk"),
    ...elements(meta, "amtabk"),
  ].map((node) => squash(inlineText(node)));
  if (!abbreviations.includes(statute))
    throw new Error(`${statute}: document is ${abbreviations.join("/")}.`);
  const notes = elements(meta, "standangabe").map((note) => ({
    type: squash(inlineText(child(note, "standtyp") ?? "")),
    text: squash(inlineText(child(note, "standkommentar") ?? "")),
  }));
  const stand = notes.find((note) => note.type === "Stand")?.text ?? null;
  const sections: ParsedSection[] = [];
  const seen = new Set<string>();
  for (const norm of norms.slice(1)) {
    const metadata = child(norm, "metadaten");
    const enbez = squash(inlineText(child(metadata, "enbez") ?? ""));
    if (!enbez || enbez === "Inhaltsübersicht") continue;
    const titleNode = child(metadata, "titel");
    const title = titleNode ? squash(inlineText(titleNode)) || null : null;
    const content = child(child(child(norm, "textdaten"), "text"), "Content");
    const text = contentText(content);
    let numbers = sectionNumbers(enbez);
    let rowTitle = title;
    if (!numbers && /^Anlage\b/.test(enbez)) {
      numbers = ["Anlage"];
      rowTitle = title ? `${enbez}: ${title}` : enbez;
    }
    if (!numbers) throw new Error(`${statute}: unexpected enbez '${enbez}'.`);
    for (const section of numbers) {
      if (seen.has(section))
        throw new Error(`${statute}: duplicate § ${section}.`);
      seen.add(section);
      // Grouped repealed sections ("§§ 18 und 19 (weggefallen)") have no
      // text of their own; each gets a row so its citation still resolves.
      sections.push({
        section,
        title: rowTitle,
        text: text || rowTitle || "(weggefallen)",
      });
    }
  }
  return {
    statute,
    doknr: head.attrs.doknr ?? "",
    builddate: head.attrs.builddate ?? doc.attrs.builddate ?? "",
    long_title: squash(inlineText(child(meta, "langue") ?? "")),
    enacted_on:
      squash(inlineText(child(meta, "ausfertigung-datum") ?? "")) || null,
    fundstelle: (() => {
      const node = child(meta, "fundstelle");
      const parts = [
        inlineText(child(node, "periodikum") ?? ""),
        inlineText(child(node, "zitstelle") ?? ""),
      ].map(squash);
      return parts.every(Boolean) ? parts.join(" ") : null;
    })(),
    stand,
    amended_on: standDate(stand),
    stand_notes: notes,
    sections,
  };
}

// ---------------------------------------------------------------- build

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

interface SourceAct {
  statute: string;
  url: string;
  retrieved_at: string;
  last_modified: string | null;
  zip_sha256: string;
  zip_bytes: number;
  xml_file: string;
  xml_sha256: string;
  doknr: string;
  builddate: string;
  long_title: string;
  enacted_on: string | null;
  stand: string | null;
  amended_on: string | null;
  section_count: number;
}
interface SourceManifest {
  source: string;
  dtd: string;
  user_agent: string;
  retrieved_at: string;
  acts: SourceAct[];
}

function unzipXml(zip: Uint8Array): { name: string; bytes: Uint8Array } {
  const entries = Object.entries(unzipSync(zip)).filter(([name]) =>
    name.toLowerCase().endsWith(".xml"),
  );
  if (entries.length !== 1)
    throw new Error(`Expected one XML file, found ${entries.length}.`);
  const [name, bytes] = entries[0] as [string, Uint8Array];
  return { name, bytes };
}
const urlFor = (slug: string) => `https://${HOST}/${slug}/xml.zip`;
const rawPath = (raw: string, slug: string) => join(raw, `${slug}.xml.zip`);

async function download(url: string, connectIp: string | undefined) {
  const target = connectIp ? url.replace(HOST, connectIp) : url;
  const response = await fetch(target, {
    headers: { "user-agent": USER_AGENT, ...(connectIp ? { host: HOST } : {}) },
    redirect: "error",
    ...(connectIp ? { tls: { serverName: HOST } } : {}),
  });
  if (!response.ok) throw new Error(`GET ${url} returned ${response.status}.`);
  const type = response.headers.get("content-type") ?? "";
  if (!type.includes("zip"))
    throw new Error(`GET ${url} returned ${type || "no content type"}.`);
  return {
    bytes: new Uint8Array(await response.arrayBuffer()),
    lastModified: response.headers.get("last-modified"),
  };
}

async function fetchAll(raw: string, connectIp: string | undefined) {
  await mkdir(raw, { recursive: true });
  const acts: SourceAct[] = [];
  for (const act of ACTS) {
    const url = urlFor(act.slug);
    const { bytes, lastModified } = await download(url, connectIp);
    const retrieved = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    const xml = unzipXml(bytes);
    const parsed = parseAct(act.statute, new TextDecoder().decode(xml.bytes));
    await writeFile(rawPath(raw, act.slug), bytes);
    acts.push({
      statute: act.statute,
      url,
      retrieved_at: retrieved,
      last_modified: lastModified,
      zip_sha256: sha256(bytes),
      zip_bytes: bytes.byteLength,
      xml_file: xml.name,
      xml_sha256: sha256(xml.bytes),
      doknr: parsed.doknr,
      builddate: parsed.builddate,
      long_title: parsed.long_title,
      enacted_on: parsed.enacted_on,
      stand: parsed.stand,
      amended_on: parsed.amended_on,
      section_count: parsed.sections.length,
    });
    console.error(
      `${act.statute}: ${parsed.sections.length} sections, ${bytes.byteLength} bytes`,
    );
  }
  const manifest: SourceManifest = {
    source: `https://${HOST}/ (consolidated XML, one zip per Act)`,
    dtd: `https://${HOST}/dtd/1.01/gii-norm.dtd`,
    user_agent: USER_AGENT,
    retrieved_at: acts.map((act) => act.retrieved_at).sort()[0] as string,
    acts,
  };
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}

/** Parse the archived zips, checking each against the source manifest. */
async function loadActs(raw: string) {
  const manifest = JSON.parse(
    await readFile(manifestPath, "utf8"),
  ) as SourceManifest;
  const parsed: ParsedAct[] = [];
  for (const act of ACTS) {
    const source = manifest.acts.find((item) => item.statute === act.statute);
    if (!source) throw new Error(`${act.statute} is not in the manifest.`);
    const bytes = new Uint8Array(await readFile(rawPath(raw, act.slug)));
    if (sha256(bytes) !== source.zip_sha256)
      throw new Error(
        `${act.statute}: archived zip does not match the manifest; run --fetch.`,
      );
    const law = parseAct(
      act.statute,
      new TextDecoder().decode(unzipXml(bytes).bytes),
    );
    if (law.sections.length !== source.section_count)
      throw new Error(`${act.statute}: section count differs from manifest.`);
    parsed.push(law);
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
      "INSERT INTO sections (statute, section, title, text) VALUES (?, ?, ?, ?)",
    );
    let count = 0;
    const total = acts.reduce((sum, act) => sum + act.sections.length, 0);
    db.transaction(() => {
      for (const act of acts)
        for (const section of act.sections) {
          if (pick && !pick[act.statute]?.includes(section.section)) continue;
          insert.run(act.statute, section.section, section.title, section.text);
          count++;
        }
      const actMeta = acts.map((act) => {
        const source = manifest.acts.find(
          (item) => item.statute === act.statute,
        ) as SourceAct;
        return {
          statute: act.statute,
          title: act.long_title,
          stand: act.stand,
          amended_on: act.amended_on,
          enacted_on: act.enacted_on,
          fundstelle: act.fundstelle,
          // Last amendment, or enactment for an Act never amended.
          version_date: act.amended_on ?? act.enacted_on,
          builddate: act.builddate,
          source_url: source.url,
          retrieved_at: source.retrieved_at,
          zip_sha256: source.zip_sha256,
          section_count: act.sections.length,
        };
      });
      const meta: [string, string][] = [
        ["schema_version", "1"],
        ["snapshot_date", manifest.retrieved_at.slice(0, 10)],
        ["section_count", String(count)],
        ["source", "gesetze-im-internet.de XML (gii-norm 1.01)"],
        ["retrieved_at", manifest.retrieved_at],
        ["acts", JSON.stringify(actMeta)],
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
  const raw = resolve(option("--raw") ?? join(root, ".data/dpma_statutes/raw"));
  const output = resolve(
    option("--output") ?? join(root, ".data/dpma_statutes/dpma_statutes.db"),
  );
  if (args.includes("--fetch")) await fetchAll(raw, option("--connect-ip"));
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
        acts: parsed.map((act) => ({
          statute: act.statute,
          sections: act.sections.length,
          stand: act.stand,
          amended_on: act.amended_on,
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

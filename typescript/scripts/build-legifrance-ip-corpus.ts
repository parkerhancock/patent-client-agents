// Builds the Légifrance IP corpus (the Python connector's schema 1, plus three
// provenance columns) from DILA's LEGI open-data exports, the database behind
// Légifrance: the legislative part of the Code de la propriété intellectuelle
// (every article "L…" in force) and Title V of Book I of the Code de commerce
// (trade secrets, L151-1 to L154-1).
//
// legifrance.gouv.fr answers plain requests with a Cloudflare challenge, so the
// pages are not read. DILA publishes the same data at
// https://echanges.dila.gouv.fr/OPENDATA/LEGI/ as one full export
// (Freemium_legi_global_*.tar.gz) plus daily increments (LEGI_*.tar.gz). The
// builder streams the latest full export and every later increment through
// gunzip and a tar reader, keeps the article files of the two codes, applies
// the increments' updates and deletion lists in order, and selects each
// article's version in force. Plain HTTPS GETs with an honest user agent.
//
// Usage (from typescript/):
//   bun scripts/build-legifrance-ip-corpus.ts --fetch     # read the archives, rewrite the source manifest, build
//   bun scripts/build-legifrance-ip-corpus.ts             # rebuild from the extracted layers (sha256-checked)
//   bun scripts/build-legifrance-ip-corpus.ts --fixture   # also rewrite the test fixture subset
// Options: --output PATH (default .data/legifrance_ip/legifrance_ip.db, must
// not exist), --raw DIR (default .data/legifrance_ip/raw), --archives DIR
// (with --fetch: read archives already downloaded there under their published
// names instead of downloading them; they are hashed all the same).
//
// The raw store keeps, per archive, only the extracted entries of the two codes
// (raw/layers/<stamp>.json.gz); the manifest records each archive's URL,
// retrieval time, size and SHA-256 and each layer's SHA-256.
import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { Readable } from "node:stream";
import { createGunzip, gunzipSync, gzipSync } from "node:zlib";

const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
export const LISTING_URL = "https://echanges.dila.gouv.fr/OPENDATA/LEGI/";
const root = join(import.meta.dir, "..");
const manifestPath = join(import.meta.dir, "legifrance-ip-sources.json");
const fixturePath = join(root, "tests/fixtures/legifrance-ip/legifrance_ip.db");

/** The two codes and the articles kept from each. */
export const CODES = [
  {
    statute: "CPI",
    id: "LEGITEXT000006069414",
    title: "Code de la propriété intellectuelle",
    keep: /^L\d/,
  },
  {
    statute: "Code de commerce",
    id: "LEGITEXT000005634379",
    title: "Code de commerce",
    keep: /^L15[1-4]-/,
  },
] as const;

/** Articles copied into the committed test fixture. */
const FIXTURE: Record<string, string[]> = {
  CPI: [
    "L111-1",
    "L122-5",
    "L511-1",
    "L611-1",
    "L611-10",
    "L611-11",
    "L613-3",
    "L615-1",
    "L711-1",
    "L713-2",
  ],
  "Code de commerce": ["L151-1", "L151-4", "L152-1"],
};

// The Python builder's schema (corpus/schema.py, version 1) in DELETE journal
// mode, with three added columns the Python reader ignores: the Légifrance
// article id, the date the version took effect and the heading path.
const DDL = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections (
    rowid          INTEGER PRIMARY KEY,
    statute        TEXT NOT NULL,
    section        TEXT NOT NULL,
    title          TEXT,
    text           TEXT NOT NULL,
    article_id     TEXT,
    in_force_since TEXT,
    breadcrumb     TEXT,
    UNIQUE(statute, section)
);
CREATE INDEX idx_sections_section ON sections(section);
CREATE INDEX idx_sections_statute ON sections(statute);
CREATE VIRTUAL TABLE sections_fts USING fts5(
    title, text,
    content='sections', content_rowid='rowid',
    tokenize="unicode61 remove_diacritics 2"
);
CREATE TRIGGER sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, title, text) VALUES (new.rowid, new.title, new.text);
END;
CREATE TRIGGER sections_ad AFTER DELETE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, title, text) VALUES ('delete', old.rowid, old.title, old.text);
END;
CREATE TRIGGER sections_au AFTER UPDATE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, title, text) VALUES ('delete', old.rowid, old.title, old.text);
    INSERT INTO sections_fts(rowid, title, text) VALUES (new.rowid, new.title, new.text);
END;
`;

export const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");
const now = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
const squash = (value: string) => value.replace(/\s+/g, " ").trim();

// ---------------------------------------------------------------- tar

/** Entries of the code article directories, keyed 'legi/global/…/LEGIARTI….xml'. */
const ARTICLE_PATH = new RegExp(
  String.raw`(legi/global/code_et_TNC_en_vigueur/code_en_vigueur/LEGI/TEXT/(?:\d\d/){5}(${CODES.map((code) => code.id).join("|")})/article/LEGI/ARTI/(?:\d\d/){5}LEGIARTI\d{12}\.xml)$`,
);
const DELETIONS = /(?:^|\/)liste_suppression_legi(?:_dossier)?\.dat$/;

const field = (header: Uint8Array, start: number, length: number) => {
  const slice = header.subarray(start, start + length);
  const end = slice.indexOf(0);
  return new TextDecoder().decode(end >= 0 ? slice.subarray(0, end) : slice);
};
const octal = (header: Uint8Array, start: number, length: number) =>
  Number.parseInt(field(header, start, length).trim() || "0", 8);

/**
 * Stream a .tar.gz, hashing the compressed bytes, and call `keep` for each
 * regular file whose path `wanted` accepts. Handles ustar prefixes, GNU long
 * names and pax path records.
 */
export async function readTarGz(
  source: Readable,
  wanted: (path: string) => boolean,
  keep: (path: string, bytes: Uint8Array) => void,
): Promise<{ sha256: string; bytes: number }> {
  const hash = createHash("sha256");
  let compressed = 0;
  source.on("data", (chunk: Buffer) => {
    hash.update(chunk);
    compressed += chunk.byteLength;
  });
  const gunzip = source.pipe(createGunzip());
  let buffer = new Uint8Array(0);
  let state:
    | { kind: "header" }
    | {
        kind: "data";
        path: string;
        remaining: number;
        padding: number;
        collect: Uint8Array[] | null;
        type: string;
      } = { kind: "header" };
  let longName: string | null = null;
  let paxPath: string | null = null;
  let ended = false;
  const finishEntry = (path: string, type: string, data: Uint8Array) => {
    if (type === "L")
      longName = new TextDecoder().decode(data).replace(/\0+$/, "");
    else if (type === "x") {
      const text = new TextDecoder().decode(data);
      const match = /(?:^|\n)\d+ path=([^\n]*)\n/.exec(text);
      if (match) paxPath = match[1] as string;
    } else if (type === "0" || type === "" || type === "7") keep(path, data);
  };
  for await (const chunk of gunzip as AsyncIterable<Buffer>) {
    if (ended) continue;
    const merged = new Uint8Array(buffer.byteLength + chunk.byteLength);
    merged.set(buffer);
    merged.set(chunk, buffer.byteLength);
    buffer = merged;
    let offset = 0;
    while (!ended) {
      if (state.kind === "header") {
        if (buffer.byteLength - offset < 512) break;
        const header = buffer.subarray(offset, offset + 512);
        offset += 512;
        if (header.every((byte) => byte === 0)) {
          ended = true;
          break;
        }
        const name = field(header, 0, 100);
        const prefix = field(header, 345, 155);
        const type = field(header, 156, 1);
        const size = octal(header, 124, 12);
        let path = prefix ? `${prefix}/${name}` : name;
        if (type !== "L" && type !== "x") {
          if (longName !== null) path = longName;
          if (paxPath !== null) path = paxPath;
          longName = null;
          paxPath = null;
        }
        const meta = type === "L" || type === "x";
        const collect =
          meta ||
          ((type === "0" || type === "" || type === "7") && wanted(path))
            ? []
            : null;
        state = {
          kind: "data",
          path,
          remaining: size,
          padding: (512 - (size % 512)) % 512,
          collect,
          type,
        };
        if (size === 0) {
          finishEntry(path, type, new Uint8Array(0));
          state = { kind: "header" };
        }
        continue;
      }
      const available = buffer.byteLength - offset;
      if (state.remaining > 0) {
        if (!available) break;
        const take = Math.min(available, state.remaining);
        state.collect?.push(buffer.slice(offset, offset + take));
        offset += take;
        state.remaining -= take;
        if (state.remaining > 0) break;
        if (state.collect) {
          const total = state.collect.reduce(
            (sum, part) => sum + part.byteLength,
            0,
          );
          const data = new Uint8Array(total);
          let at = 0;
          for (const part of state.collect) {
            data.set(part, at);
            at += part.byteLength;
          }
          finishEntry(state.path, state.type, data);
        }
      }
      if (buffer.byteLength - offset < state.padding) break;
      offset += state.padding;
      state = { kind: "header" };
    }
    buffer = buffer.slice(offset);
  }
  return { sha256: hash.digest("hex"), bytes: compressed };
}

// ---------------------------------------------------------------- articles

export interface ParsedArticle {
  code: string;
  id: string;
  num: string;
  etat: string;
  date_debut: string;
  date_fin: string;
  /** Headings below the code, outermost first. */
  headings: string[];
  text: string;
}

const ENTITIES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
};
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
      if (known === undefined) throw new Error(`Unknown entity &${name};`);
      return known;
    },
  );
}

/**
 * Plain text of an article's CONTENU: one line per paragraph or <br/>, table
 * cells joined by " | ", whitespace collapsed within lines, empty lines dropped.
 */
export function contentText(html: string): string {
  const marked = html
    .replace(/<(?:td|th)\b[^>]*>/gi, "\uE000")
    .replace(
      /<\/?(?:br|p|div|tr|li|ul|ol|table|h\d|blockquote)\b[^>]*\/?>/gi,
      "\n",
    )
    .replace(/<[^>]*>/g, "");
  return decodeEntities(marked)
    .split("\n")
    .map((line) =>
      squash(line)
        .replace(/^\uE000\s*/, "")
        .replace(/\s*\uE000\s*/g, " | "),
    )
    .filter((line) => line && line !== "|")
    .join("\n");
}

const tag = (xml: string, name: string) =>
  new RegExp(`<${name}>([\\s\\S]*?)</${name}>`).exec(xml)?.[1]?.trim() ?? "";

/** One LEGIARTI file. Headings are the TITRE_TM chain in force on `asOf`. */
export function parseArticle(xml: string, asOf: string): ParsedArticle {
  const id = tag(xml, "ID");
  const num = squash(decodeEntities(tag(xml, "NUM")));
  const code = /<TITRE_TXT\b[^>]*\bid_txt="([^"]+)"/.exec(xml)?.[1] ?? "";
  const headings: string[] = [];
  const context = tag(xml, "CONTEXTE");
  let depth = 0;
  for (const match of context.matchAll(
    /<TM>|<\/TM>|<TITRE_TM\b([^>]*)>([\s\S]*?)<\/TITRE_TM>/g,
  )) {
    if (match[0] === "<TM>") depth++;
    else if (match[0] === "</TM>") depth--;
    else {
      const attrs = match[1] as string;
      const start = /\bdebut="([^"]*)"/.exec(attrs)?.[1] ?? "";
      const end = /\bfin="([^"]*)"/.exec(attrs)?.[1] ?? "2999-01-01";
      if (start <= asOf && asOf < end) {
        headings.length = depth - 1;
        headings[depth - 1] = squash(decodeEntities(match[2] as string));
      }
    }
  }
  const content = /<BLOC_TEXTUEL>\s*<CONTENU>([\s\S]*?)<\/CONTENU>/.exec(xml);
  return {
    code,
    id,
    num,
    etat: tag(xml, "ETAT"),
    date_debut: tag(xml, "DATE_DEBUT"),
    date_fin: tag(xml, "DATE_FIN"),
    headings: headings.filter(Boolean),
    text: content ? contentText(content[1] as string) : "",
  };
}

// ---------------------------------------------------------------- sources

interface ArchiveRecord {
  name: string;
  url: string;
  stamp: string;
  retrieved_at: string;
  last_modified: string | null;
  sha256: string;
  bytes: number;
  /** Article files of the two codes the archive carries. */
  entries: number;
  /** Deletion-list lines that touch the two codes. */
  deletions: number;
  layer_sha256: string;
}
interface SourceManifest {
  description: string;
  access_notes: string[];
  listing_url: string;
  user_agent: string;
  retrieved_at: string;
  codes: { statute: string; id: string; title: string; kept: string }[];
  archives: ArchiveRecord[];
}
interface Layer {
  name: string;
  entries: Record<string, string>;
  deletions: string[];
}

const stampOf = (name: string) =>
  /(\d{8}-\d{6})\.tar\.gz$/.exec(name)?.[1] as string;
const layerPath = (raw: string, stamp: string) =>
  join(raw, "layers", `${stamp}.json.gz`);

/** Archive names on the listing page: the latest full export and every later increment. */
export function archivesFromListing(html: string): string[] {
  const names = [
    ...new Set(
      [
        ...html.matchAll(
          /href="((?:Freemium_legi_global|LEGI)_\d{8}-\d{6}\.tar\.gz)"/g,
        ),
      ].map((match) => match[1] as string),
    ),
  ];
  const full = names
    .filter((name) => name.startsWith("Freemium_legi_global_"))
    .sort()
    .at(-1);
  if (!full) throw new Error("No full LEGI export on the listing page.");
  const from = stampOf(full);
  return [
    full,
    ...names
      .filter((name) => name.startsWith("LEGI_") && stampOf(name) > from)
      .sort((a, b) => stampOf(a).localeCompare(stampOf(b))),
  ];
}

const keepNum = (code: string, xml: string) => {
  const rule = CODES.find((item) => item.id === code);
  const num = squash(decodeEntities(tag(xml, "NUM")));
  return Boolean(rule?.keep.test(num));
};

async function extract(
  name: string,
  raw: string,
  archives: string | undefined,
): Promise<ArchiveRecord> {
  const url = `${LISTING_URL}${name}`;
  let source: Readable;
  let lastModified: string | null = null;
  const local = archives ? join(archives, name) : undefined;
  let retrieved = now();
  if (local && (await exists(local))) {
    // An archive downloaded earlier: its modification time is when it arrived.
    retrieved = (await stat(local)).mtime.toISOString().replace(/\.\d+Z$/, "Z");
    source = createReadStream(local);
  } else {
    const response = await fetch(url, {
      headers: { "user-agent": USER_AGENT },
      redirect: "error",
    });
    if (!response.ok || !response.body)
      throw new Error(`GET ${url} returned ${response.status}.`);
    lastModified = response.headers.get("last-modified");
    source = Readable.fromWeb(response.body as never);
  }
  const entries: Record<string, string> = {};
  const deletions: string[] = [];
  const ids = CODES.map((code) => code.id);
  const result = await readTarGz(
    source,
    (path) => ARTICLE_PATH.test(path) || DELETIONS.test(path),
    (path, bytes) => {
      const text = new TextDecoder().decode(bytes);
      if (DELETIONS.test(path)) {
        for (const line of text.split("\n"))
          if (ids.some((id) => line.includes(`/${id}`)))
            deletions.push(line.trim());
        return;
      }
      const match = ARTICLE_PATH.exec(path);
      if (match && keepNum(match[2] as string, text))
        entries[match[1] as string] = text;
    },
  );
  const layer: Layer = { name, entries, deletions };
  const gz = gzipSync(new TextEncoder().encode(JSON.stringify(layer)), {
    level: 9,
  });
  await mkdir(join(raw, "layers"), { recursive: true });
  await writeFile(layerPath(raw, stampOf(name)), gz);
  console.error(
    `${name}: ${result.bytes} bytes, ${Object.keys(entries).length} articles, ${deletions.length} deletions`,
  );
  return {
    name,
    url,
    stamp: stampOf(name),
    retrieved_at: retrieved,
    last_modified: lastModified,
    sha256: result.sha256,
    bytes: result.bytes,
    entries: Object.keys(entries).length,
    deletions: deletions.length,
    layer_sha256: sha256(gz),
  };
}

async function fetchAll(raw: string, archives: string | undefined) {
  const listing = await fetch(LISTING_URL, {
    headers: { "user-agent": USER_AGENT },
  });
  if (!listing.ok)
    throw new Error(`GET ${LISTING_URL} returned ${listing.status}.`);
  const names = archivesFromListing(await listing.text());
  const records: ArchiveRecord[] = new Array(names.length);
  let next = 0;
  // Four archives at a time; layers are applied in archive order at build time.
  await Promise.all(
    Array.from({ length: 4 }, async () => {
      while (next < names.length) {
        const index = next++;
        let last: unknown;
        for (let attempt = 1; attempt <= 3; attempt++) {
          try {
            records[index] = await extract(
              names[index] as string,
              raw,
              archives,
            );
            last = undefined;
            break;
          } catch (error) {
            last = error;
            console.error(
              `${names[index]} attempt ${attempt}: ${String(error)}`,
            );
          }
        }
        if (last) throw last;
      }
    }),
  );
  const manifest: SourceManifest = {
    description:
      "DILA LEGI open-data exports (the Légifrance database): the latest full export and every later daily increment, reduced to the article files of the Code de la propriété intellectuelle and the Code de commerce.",
    access_notes: [
      "www.legifrance.gouv.fr answered a plain GET for the CPI page with HTTP 403 and a Cloudflare managed challenge on October 22, 2026, so the site's pages are not read; the PISTE Légifrance API needs registered OAuth credentials.",
      "Kept: CPI articles numbered L… (the legislative part) and Code de commerce articles L151-1 to L154-1 (Book I, Title V, trade secrets). Each article's version in force on the snapshot date is selected.",
    ],
    listing_url: LISTING_URL,
    user_agent: USER_AGENT,
    retrieved_at: records
      .map((record) => record.retrieved_at)
      .sort()[0] as string,
    codes: CODES.map((code) => ({
      statute: code.statute,
      id: code.id,
      title: code.title,
      kept: code.keep.source,
    })),
    archives: records,
  };
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}

// ---------------------------------------------------------------- build

export interface Row {
  statute: string;
  section: string;
  title: string | null;
  text: string;
  article_id: string;
  in_force_since: string;
  breadcrumb: string;
}

/** Apply the layers in order and select each kept article's version in force on `asOf`. */
export function selectRows(layers: Layer[], asOf: string): Row[] {
  const files = new Map<string, string>();
  for (const layer of layers) {
    for (const line of layer.deletions) {
      const target = line.replace(/\s+D$/, "").replace(/\.xml$/, "");
      for (const key of [...files.keys()])
        if (key === `${target}.xml` || key.startsWith(`${target}/`))
          files.delete(key);
    }
    for (const [key, xml] of Object.entries(layer.entries)) files.set(key, xml);
  }
  const chosen = new Map<string, ParsedArticle>();
  for (const xml of files.values()) {
    const article = parseArticle(xml, asOf);
    if (!article.etat.startsWith("VIGUEUR")) continue;
    if (!(article.date_debut <= asOf && asOf < article.date_fin)) continue;
    const key = `${article.code}|${article.num}`;
    const previous = chosen.get(key);
    if (previous)
      throw new Error(
        `Two versions of ${article.num} in force: ${previous.id} and ${article.id}.`,
      );
    chosen.set(key, article);
  }
  const rows: Row[] = [];
  for (const article of chosen.values()) {
    const code = CODES.find((item) => item.id === article.code);
    if (!code) throw new Error(`${article.id}: unknown code ${article.code}.`);
    if (!article.text)
      throw new Error(`${article.id} (${article.num}) has no text.`);
    if (!/^L\d+(?:-\d+)+$/.test(article.num))
      throw new Error(`${article.id}: unexpected number '${article.num}'.`);
    rows.push({
      statute: code.statute,
      section: article.num,
      title: article.headings.at(-1) ?? null,
      text: article.text,
      article_id: article.id,
      in_force_since: article.date_debut,
      breadcrumb: article.headings.join(" > "),
    });
  }
  // Code order: statute, then each number part numerically (L611-2 before L611-10).
  const parts = (section: string) => section.slice(1).split("-").map(Number);
  return rows.sort((a, b) => {
    if (a.statute !== b.statute) return a.statute === "CPI" ? -1 : 1;
    const [x, y] = [parts(a.section), parts(b.section)];
    for (let i = 0; i < Math.max(x.length, y.length); i++)
      if ((x[i] ?? -1) !== (y[i] ?? -1)) return (x[i] ?? -1) - (y[i] ?? -1);
    return 0;
  });
}

/** Read the layers, checking each against the source manifest. */
async function loadRows(raw: string) {
  const manifest = JSON.parse(
    await readFile(manifestPath, "utf8"),
  ) as SourceManifest;
  const layers: Layer[] = [];
  for (const record of manifest.archives) {
    const gz = new Uint8Array(await readFile(layerPath(raw, record.stamp)));
    if (sha256(gz) !== record.layer_sha256)
      throw new Error(
        `${record.name}: layer does not match the manifest; run --fetch.`,
      );
    layers.push(JSON.parse(new TextDecoder().decode(gunzipSync(gz))) as Layer);
  }
  const last = manifest.archives.at(-1) as ArchiveRecord;
  // The data are as of the newest export applied.
  const asOf = `${last.stamp.slice(0, 4)}-${last.stamp.slice(4, 6)}-${last.stamp.slice(6, 8)}`;
  return { manifest, asOf, rows: selectRows(layers, asOf) };
}

function writeDatabase(
  output: string,
  manifest: SourceManifest,
  asOf: string,
  rows: Row[],
  pick?: Record<string, string[]>,
) {
  const db = new Database(output, { create: true, strict: true });
  try {
    db.exec("PRAGMA journal_mode = DELETE");
    db.exec(DDL);
    const insert = db.prepare(
      "INSERT INTO sections (statute, section, title, text, article_id, in_force_since, breadcrumb) VALUES (?, ?, ?, ?, ?, ?, ?)",
    );
    let count = 0;
    db.transaction(() => {
      for (const row of rows) {
        if (pick && !pick[row.statute]?.includes(row.section)) continue;
        insert.run(
          row.statute,
          row.section,
          row.title,
          row.text,
          row.article_id,
          row.in_force_since,
          row.breadcrumb,
        );
        count++;
      }
      const last = manifest.archives.at(-1) as ArchiveRecord;
      const counts = Object.fromEntries(
        CODES.map((code) => [
          code.statute,
          rows.filter((row) => row.statute === code.statute).length,
        ]),
      );
      const meta: [string, string][] = [
        ["schema_version", "1"],
        ["snapshot_date", asOf],
        ["source_version", `LEGI ${last.stamp}`],
        ["section_count", String(count)],
        ["source", `DILA LEGI open data (${LISTING_URL})`],
        ["full_export", manifest.archives[0]?.name ?? ""],
        ["last_increment", last.name],
        ["archive_count", String(manifest.archives.length)],
        ["retrieved_at", manifest.retrieved_at],
        [
          "codes",
          JSON.stringify(
            CODES.map((code) => ({
              statute: code.statute,
              id: code.id,
              title: code.title,
              kept: code.keep.source,
              articles: counts[code.statute],
            })),
          ),
        ],
      ];
      if (pick) meta.push(["fixture_subset_of", String(rows.length)]);
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

async function build(
  output: string,
  manifest: SourceManifest,
  asOf: string,
  rows: Row[],
  pick?: Record<string, string[]>,
) {
  await mkdir(dirname(output), { recursive: true });
  const temporary = `${output}.building`;
  await rm(temporary, { force: true });
  try {
    const count = writeDatabase(temporary, manifest, asOf, rows, pick);
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
  const raw = resolve(option("--raw") ?? join(root, ".data/legifrance_ip/raw"));
  const output = resolve(
    option("--output") ?? join(root, ".data/legifrance_ip/legifrance_ip.db"),
  );
  const archives = option("--archives");
  if (args.includes("--fetch"))
    await fetchAll(raw, archives ? resolve(archives) : undefined);
  if (await exists(output))
    throw new Error(`${output} exists; choose a new --output.`);
  const { manifest, asOf, rows } = await loadRows(raw);
  const count = await build(output, manifest, asOf, rows);
  const bytes = new Uint8Array(await readFile(output));
  console.log(
    JSON.stringify(
      {
        output,
        as_of: asOf,
        articles: count,
        by_statute: Object.fromEntries(
          CODES.map((code) => [
            code.statute,
            rows.filter((row) => row.statute === code.statute).length,
          ]),
        ),
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
      asOf,
      rows,
      FIXTURE,
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

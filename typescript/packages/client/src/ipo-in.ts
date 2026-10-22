import { z } from "zod";
import { defaultCorpusPath } from "#files";
import {
  CorpusError,
  checkCorpusSignal,
  corpusTimestamp,
  openCorpusSnapshot,
  outlineFtsQuery,
} from "./corpus/outline.js";
import type { CorpusProvenance } from "./models.js";
import { byteLength, env, sha256Hex } from "./runtime/env.js";
import type { SnapshotDatabase } from "./runtime/sqlite.js";

/**
 * Readers for the two Indian Patent Office corpora: the IP statutes (Patents,
 * Designs, Trade Marks and Copyright Acts plus the Patent Rules) and the
 * Manual of Patent Office Practice and Procedure (MPPP). Both are SQLite/FTS5
 * snapshots built by scripts/build-ipo-in-corpora.ts from the official texts
 * (references/ipo-in/sources.json lists each source, version and hash).
 */
export const IPO_IN_STATUTES_SOURCE_URL =
  "https://ipindia.gov.in/pages/home/acts-rules-ipr";
export const IPO_IN_MPPP_PDF_URL =
  "https://ipindia.gov.in/storage/uploads/docs-operator/e1adfe40-7af3-4180-ba04-2e0099c6dca5.pdf";
export const IPO_IN_STATUTES_SOURCE_NAME = "IPO India — IP statutes";
export const IPO_IN_MPPP_SOURCE_NAME =
  "IPO India Manual of Patent Practice & Procedure (MPPP)";

/** Python's alias table, plus singular and year-suffixed spellings it missed. */
export const IPO_IN_STATUTE_ALIASES: Readonly<Record<string, string>> = {
  patents: "Patents Act",
  patent: "Patents Act",
  "patents act": "Patents Act",
  "patent act": "Patents Act",
  "patent rules": "Patent Rules",
  "patents rules": "Patent Rules",
  rules: "Patent Rules",
  designs: "Designs Act",
  design: "Designs Act",
  "designs act": "Designs Act",
  "design act": "Designs Act",
  "trade marks": "Trade Marks Act",
  trademarks: "Trade Marks Act",
  "trade mark": "Trade Marks Act",
  trademark: "Trade Marks Act",
  "trade marks act": "Trade Marks Act",
  "trade mark act": "Trade Marks Act",
  "trademarks act": "Trade Marks Act",
  "trademark act": "Trade Marks Act",
  copyright: "Copyright Act",
  "copyright act": "Copyright Act",
};

/**
 * Canonical statute name for a label. Case, punctuation, a leading "the" and
 * a trailing year ("Patents Act, 1970") are ignored. Unknown names pass
 * through trimmed, as in Python, and then match only an exact stored name.
 */
export function resolveIpoInStatute(name: string): string {
  const key = name
    .toLowerCase()
    .replace(/[,.()]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^the /, "")
    .replace(/ (?:19|20)\d\d$/, "");
  return IPO_IN_STATUTE_ALIASES[key] ?? name.trim();
}

/** A citation that cannot be parsed, or a bare number held by several Acts. */
export class IpoInCitationError extends Error {
  override name = "IpoInCitationError";
}

const SECTION_NUMBER = String.raw`\d+[A-Za-z]{0,2}(?:\s*\(\s*[0-9A-Za-z]+\s*\))*(?:\.\d+)*`;
const CITATION = new RegExp(
  String.raw`^\s*(?:(?<kind>section|sec\.?|s\.|s|rule|r\.|r)\s+|§+\s*)?(?<num>${SECTION_NUMBER})(?:\s*,?\s+(?:of\s+)?(?:the\s+)?(?<statute>\S.*?))?\s*$`,
  "i",
);
/** Act-first form: "Patents Act, section 3(d)", "Patent Rules rule 71". */
const ACT_FIRST = new RegExp(
  String.raw`^\s*(?:the\s+)?(?<statute>\S.*?)\s*,?\s+(?<kind>section|sec\.?|s\.|rule|r\.|§)\s*(?<num>${SECTION_NUMBER})\s*$`,
  "i",
);

/**
 * Parse a free-text statute citation into a section number and an optional
 * canonical statute. Accepts "Section 3(d) Patents Act", "Rule 71 Patent
 * Rules", "S. 84", "§107A", "Section 25(2) of the Patents Act, 1970",
 * "Patents Act, section 3(d)" and a bare "3(d)". A "Rule" citation without an Act means the Patent Rules.
 */
export function parseIpoInCitation(citation: string): {
  section_number: string;
  statute_name: string | null;
} {
  const match = CITATION.exec(citation) ?? ACT_FIRST.exec(citation);
  const num = match?.groups?.num;
  if (!match || !num)
    throw new IpoInCitationError(
      `Could not parse citation '${citation}'; expected e.g. 'Section 3(d) Patents Act'.`,
    );
  const statute = match.groups?.statute;
  const kind = match.groups?.kind?.toLowerCase();
  return {
    section_number: num.replace(/\s+/g, ""),
    statute_name: statute
      ? resolveIpoInStatute(statute)
      : kind?.startsWith("r")
        ? "Patent Rules"
        : null,
  };
}

const MPPP_REFERENCE =
  /^\s*(?:MPPP\s+)?(?:(?:Chapter|Ch\.?|Section|Sec\.?|Para(?:graph)?\.?)\s*|§+\s*)?(?<num>\d+(?:\.\d+)*)\.?\s*$/i;

/** Bare dotted MPPP number for "04.05.01", "Chapter 04.05.01" or "MPPP Chapter 4.5.1". */
export function normalizeMpppReference(value: string): string {
  const num = MPPP_REFERENCE.exec(value)?.groups?.num;
  if (!num)
    throw new IpoInCitationError(
      `Could not parse MPPP reference '${value}'; expected e.g. '04.05.01' or 'MPPP Chapter 04.05.01'.`,
    );
  return num;
}

/** Natural order for section numbers: "2" < "3" < "3(d)" < "25(1)" < "107A". */
export function compareSectionNumbers(a: string, b: string): number {
  const parts = (value: string) =>
    value.toLowerCase().match(/\d+|[a-z]+/g) ?? [];
  const left = parts(a);
  const right = parts(b);
  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    const x = left[i] as string;
    const y = right[i] as string;
    const xn = /^\d/.test(x);
    const yn = /^\d/.test(y);
    if (xn && yn) {
      const diff = Number(x) - Number(y);
      if (diff) return diff;
    } else if (xn !== yn) return xn ? -1 : 1;
    else if (x !== y) return x < y ? -1 : 1;
  }
  return left.length - right.length || (a < b ? -1 : a > b ? 1 : 0);
}

const text = (max: number) =>
  z
    .string()
    .trim()
    .min(1)
    .max(max)
    .refine((value) => !value.includes("\0"), "Values must not contain NUL.");
const query = z
  .string()
  .max(8192)
  .refine((value) => !value.includes("\0"), "Queries must not contain NUL.");
const common = {
  query,
  syntax: z.enum(["adj", "exact", "and", "or"]).default("and"),
  sort: z.enum(["relevance", "outline"]).default("relevance"),
  limit: z.number().int().min(1).max(100).default(10),
  offset: z.number().int().min(0).safe().default(0),
};
const statutesSearchOptions = z.object({
  ...common,
  statute: text(200).nullish(),
});
const mpppSearchOptions = z.object(common);
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);

export interface IpoInClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also <PREFIX>_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also <PREFIX>_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
  /** Largest section text returned, in UTF-8 bytes (default 16 MiB). */
  maxTextBytes?: number;
}

export interface IpoInCorpusStatus {
  available: boolean;
  label: string;
  /** The stored source_version, else `snapshot-<date>`, as Python reports it. */
  corpus_version: string;
  schema_version: number | null;
  section_count: number | null;
  snapshot_date: string | null;
  source_version: string | null;
  corpus_synced_at: string | null;
  artifact_sha256: string | null;
  file_sha256: string | null;
  compression: "none" | "zstd" | null;
  source_url: string;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
interface SectionBody {
  title: string | null;
  text: string;
  source_url: string | null;
  content_sha256: string;
  corpus_version: string;
  provenance: CorpusProvenance;
}
export interface IpoInSection extends SectionBody {
  statute_name: string;
  section_number: string;
  /**
   * Set when the citation named a sub-section or clause ("3(d)" gives "(d)").
   * The corpus stores whole sections, so the returned text is the enclosing
   * section and the cited subdivision lies within it.
   */
  subdivision?: string;
}
export interface IpoInMpppSection extends SectionBody {
  section_number: string;
  chapter: string | null;
}
export interface IpoInStatuteHit {
  statute_name: string;
  section_number: string;
  title: string | null;
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: string;
  /** BM25 rank (lower is more relevant). */
  rank: number | null;
}
export interface IpoInMpppHit {
  section_number: string;
  chapter: string | null;
  title: string | null;
  snippet: string;
  rank: number | null;
}
interface SearchResponse<Hit> {
  query: string;
  hits: Hit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: IpoInCorpusStatus;
}
export interface IpoInStatutesSearchResponse
  extends SearchResponse<IpoInStatuteHit> {
  /** Canonical statute the search was limited to, or null for every Act. */
  statute_name: string | null;
}
export type IpoInMpppSearchResponse = SearchResponse<IpoInMpppHit>;
export type IpoInStatutesSearchOptions = z.input<
  typeof statutesSearchOptions
> & { signal?: AbortSignal };
export type IpoInMpppSearchOptions = z.input<typeof mpppSearchOptions> & {
  signal?: AbortSignal;
};

interface Schema {
  label: string;
  envPrefix: string;
  filename: string;
  sourceUrl: string;
  sourceName: string;
  /** Leading columns of `sections` and `sections_fts` (before title/text). */
  keys: string[];
  ftsColumns: string[];
}

function validator(schema: Schema) {
  return (db: SnapshotDatabase) => {
    const rows = db.all<{ key: unknown; value: unknown }>(
      "SELECT key, value FROM meta",
    );
    if (
      rows.some(
        (row) => typeof row.key !== "string" || typeof row.value !== "string",
      )
    )
      throw new Error();
    const metadata = Object.fromEntries(
      rows.map((row) => [row.key as string, row.value as string]),
    );
    if (metadata.schema_version !== "1")
      throw new CorpusError(
        "UNSUPPORTED_SCHEMA",
        `Unsupported ${schema.label} corpus schema; the supported version is 1.`,
      );
    db.all(
      `SELECT rowid, ${schema.keys.join(", ")}, title, text, source_url FROM sections LIMIT 0`,
    );
    const fts = db.get<{ sql: string }>(
      "SELECT sql FROM sqlite_master WHERE name = ? AND type = 'table'",
      ["sections_fts"],
    );
    const columns = db
      .all<{ name: string }>("PRAGMA table_info(sections_fts)")
      .map((row) => row.name);
    const count = db.get<{ count: number }>(
      "SELECT count(*) AS count FROM sections",
    )?.count;
    if (
      !fts ||
      !/\bUSING\s+fts5\s*\(/i.test(fts.sql) ||
      !/\bcontent\s*=\s*['"]sections['"]/i.test(fts.sql) ||
      !/\bcontent_rowid\s*=\s*['"]rowid['"]/i.test(fts.sql) ||
      JSON.stringify(columns) !== JSON.stringify(schema.ftsColumns) ||
      count === undefined
    )
      throw new Error();
    return { metadata, count };
  };
}

/** Shared artifact lifecycle, status and row access for both IPO India corpora. */
abstract class IpoInCorpusReader {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private metadata: Record<string, string> = {};
  private count: number | null = null;
  private sha256: string | null = null;
  private fileSha256: string | null = null;
  private compression: "none" | "zstd" | null = null;
  private readonly path: string;
  private readonly source: IpoInClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;
  private readonly maxTextBytes: number;

  protected constructor(
    protected readonly schema: Schema,
    options: IpoInClientOptions,
  ) {
    this.path =
      options.corpusPath ??
      env(`${schema.envPrefix}_CORPUS_PATH`) ??
      defaultCorpusPath(schema.filename) ??
      "";
    this.source = options.source;
    if (!options.source) text(2048).parse(this.path);
    const pin = (value: string | undefined) =>
      value === undefined ? undefined : sha256Pin.parse(value);
    this.expectedSha256 = pin(
      options.expectedSha256 ?? env(`${schema.envPrefix}_CORPUS_SHA256`),
    );
    this.expectedFileSha256 = pin(
      options.expectedFileSha256 ??
        env(`${schema.envPrefix}_CORPUS_FILE_SHA256`),
    );
    this.maxTextBytes = z
      .number()
      .int()
      .positive()
      .safe()
      .parse(options.maxTextBytes ?? 16 * 1024 * 1024);
  }

  private async open() {
    if (this.db) return;
    this.opening ??= (async (generation: number) => {
      const snapshot = await openCorpusSnapshot(
        {
          path: this.path,
          source: this.source,
          label: this.schema.label,
          envVar: `${this.schema.envPrefix}_CORPUS_PATH`,
          ...(this.expectedSha256
            ? { expectedSha256: this.expectedSha256 }
            : {}),
          ...(this.expectedFileSha256
            ? { expectedFileSha256: this.expectedFileSha256 }
            : {}),
        },
        validator(this.schema),
        this.schema.label,
      );
      if (generation !== this.generation) {
        snapshot.db.close();
        throw new CorpusError(
          "ABORTED",
          "The corpus was closed while opening.",
        );
      }
      this.db = snapshot.db;
      this.metadata = snapshot.value.metadata;
      this.count = snapshot.value.count;
      this.sha256 = snapshot.sha256;
      this.fileSha256 = snapshot.fileSha256;
      this.compression = snapshot.compression;
    })(this.generation).finally(() => {
      this.opening = undefined;
    });
    await this.opening;
  }

  protected query<T>(
    sql: string,
    bind: (string | number)[],
    what: string,
  ): T[] {
    if (!this.db) throw new CorpusError("ABORTED", "The corpus was closed.");
    try {
      return this.db.all<T>(sql, bind);
    } catch {
      throw new CorpusError(
        "INVALID_CORPUS",
        `The ${this.schema.label} ${what} is not readable.`,
      );
    }
  }

  private status(available: boolean, error?: CorpusError): IpoInCorpusStatus {
    const metadata = { ...this.metadata };
    const source = metadata.source_version || null;
    const synced = corpusTimestamp(metadata.snapshot_date);
    return {
      available,
      label: this.schema.label,
      corpus_version:
        source && source !== "current"
          ? source
          : metadata.snapshot_date
            ? `snapshot-${metadata.snapshot_date}`
            : "unknown",
      schema_version: metadata.schema_version
        ? Number(metadata.schema_version)
        : null,
      section_count: this.count,
      snapshot_date: metadata.snapshot_date ?? null,
      source_version: source,
      corpus_synced_at: synced,
      artifact_sha256: this.sha256,
      file_sha256: this.fileSha256,
      compression: this.compression,
      source_url: this.schema.sourceUrl,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  protected provenance(
    corpus: IpoInCorpusStatus,
    sourceUrl = this.schema.sourceUrl,
  ): CorpusProvenance {
    return {
      source_url: sourceUrl,
      source_name: this.schema.sourceName,
      retrieved_at: corpus.corpus_synced_at,
      accessed_at: new Date().toISOString(),
      cache_hit: true,
      corpus_synced_at: corpus.corpus_synced_at,
      corpus_version: corpus.corpus_version,
    };
  }

  protected async ready(signal?: AbortSignal) {
    checkCorpusSignal(signal);
    await this.open();
    checkCorpusSignal(signal);
    return this.status(true);
  }

  /** Snapshot identity and freshness; never throws for an unusable artifact. */
  async getCorpusStatus(): Promise<IpoInCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  /** Text, hash and provenance for one stored row. */
  protected async body(
    row: { title: string | null; text: unknown; source_url: string | null },
    corpus: IpoInCorpusStatus,
    signal?: AbortSignal,
  ): Promise<SectionBody> {
    if (typeof row.text !== "string")
      throw new CorpusError(
        "INVALID_CORPUS",
        `The ${this.schema.label} section text is not readable.`,
      );
    if (byteLength(row.text) > this.maxTextBytes)
      throw new CorpusError(
        "SECTION_TOO_LARGE",
        `${this.schema.label} section text exceeds the configured decoded-byte limit.`,
      );
    checkCorpusSignal(signal);
    return {
      title: row.title,
      text: row.text,
      source_url: row.source_url,
      content_sha256: await sha256Hex(new TextEncoder().encode(row.text)),
      corpus_version: corpus.corpus_version,
      provenance: this.provenance(corpus, row.source_url ?? undefined),
    };
  }

  /**
   * Ranked FTS5 rows. Every term is quoted, so caller input never runs as
   * MATCH syntax. Outline order is natural section order, applied before
   * paging; relevance ties fall back to row order.
   */
  protected match<T extends { section_number: string }>(
    columns: string,
    snippetColumn: number,
    match: string,
    filters: [string, string][],
    sort: "relevance" | "outline",
    limit: number,
    offset: number,
    group?: (row: T) => string,
  ): T[] {
    if (!match) return [];
    const where = filters.map(([column]) => ` AND s.${column} = ?`).join("");
    const select = `SELECT ${columns}, snippet(sections_fts, ${snippetColumn}, '<mark>', '</mark>', '…', 40) AS snippet, rank FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ?${where}`;
    const bind = [match, ...filters.map(([, value]) => value)];
    if (sort === "relevance")
      return this.query<T>(
        `${select} ORDER BY rank, s.rowid LIMIT ? OFFSET ?`,
        [...bind, limit, offset],
        "full-text index",
      );
    const rows = this.query<T>(
      `${select} ORDER BY s.rowid`,
      bind,
      "full-text index",
    );
    rows.sort(
      (a, b) =>
        (group ? group(a).localeCompare(group(b)) : 0) ||
        compareSectionNumbers(a.section_number, b.section_number),
    );
    return rows.slice(offset, offset + limit);
  }

  close() {
    this.generation++;
    this.db?.close();
    this.db = undefined;
    this.metadata = {};
    this.count = null;
    this.sha256 = null;
    this.fileSha256 = null;
    this.compression = null;
  }
}

interface StatuteRow {
  statute_name: string;
  section_number: string;
  title: string | null;
  text: unknown;
  source_url: string | null;
}

/**
 * Read-only reader for the IPO India statutes snapshot. It never downloads
 * or rebuilds the corpus; the path comes from IPO_IN_STATUTES_CORPUS_PATH or
 * ~/.cache/patent_client_agents/ipo_in_statutes.db.
 */
export class IpoInStatutesClient extends IpoInCorpusReader {
  constructor(options: IpoInClientOptions = {}) {
    super(
      {
        label: "IPO India statutes",
        envPrefix: "IPO_IN_STATUTES",
        filename: "ipo_in_statutes.db",
        sourceUrl: IPO_IN_STATUTES_SOURCE_URL,
        sourceName: IPO_IN_STATUTES_SOURCE_NAME,
        keys: ["statute_name", "section_number"],
        ftsColumns: ["statute_name", "section_number", "title", "text"],
      },
      options,
    );
  }

  /** Installed statute names, alphabetically. */
  async listStatutes(options: { signal?: AbortSignal } = {}) {
    await this.ready(options.signal);
    return this.query<{ statute_name: string }>(
      "SELECT DISTINCT statute_name FROM sections ORDER BY statute_name",
      [],
      "section table",
    ).map((row) => row.statute_name);
  }

  /**
   * One section by number. With a statute, that Act only; without one, the
   * number must exist in exactly one Act (IpoInCitationError lists the Acts
   * otherwise). Section numbers match case-insensitively. A sub-section or
   * clause citation ("3(d)") returns its enclosing section with `subdivision`.
   */
  async getSection(
    sectionNumber: string,
    options: {
      statute?: string | null;
      /** Without a statute, look only in the Acts (a "section" is never a rule). */
      actsOnly?: boolean;
      signal?: AbortSignal;
    } = {},
  ): Promise<IpoInSection> {
    const number = text(200).parse(sectionNumber).replace(/\s+/g, "");
    const statute = options.statute
      ? resolveIpoInStatute(text(200).parse(options.statute))
      : null;
    const corpus = await this.ready(options.signal);
    const filter = statute
      ? " AND statute_name = ?"
      : options.actsOnly
        ? " AND statute_name <> 'Patent Rules'"
        : "";
    const lookup = (value: string) =>
      this.query<StatuteRow>(
        `SELECT statute_name, section_number, title, text, source_url FROM sections WHERE section_number = ? COLLATE NOCASE${filter} ORDER BY statute_name`,
        statute ? [value, statute] : [value],
        "section table",
      );
    let rows = lookup(number);
    // "3(d)" or "25(2)": whole sections are stored, so fall back to "3" / "25".
    const parent = /^(\d+[A-Za-z]{0,3})(\(.+)$/.exec(number);
    let subdivision: string | undefined;
    if (!rows.length && parent) {
      rows = lookup(parent[1] as string);
      subdivision = parent[2] as string;
    }
    const row = rows[0];
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        statute
          ? `Section '${number}' not found in '${statute}'.`
          : `Section '${number}' not found in any bundled statute.`,
      );
    if (rows.length > 1)
      throw new IpoInCitationError(
        `Section '${number}' is ambiguous — exists in: ${rows.map((r) => r.statute_name).join(", ")}. Name the Act to disambiguate.`,
      );
    return {
      statute_name: row.statute_name,
      section_number: row.section_number,
      ...(subdivision ? { subdivision } : {}),
      ...(await this.body(row, corpus, options.signal)),
    };
  }

  /**
   * One section by free-text citation, e.g. 'Section 3(d) Patents Act'. A
   * "Section"/"§"/"S." citation without an Act never matches a Patent Rule.
   */
  async getSectionByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<IpoInSection> {
    const value = text(500).parse(citation);
    const parsed = parseIpoInCitation(value);
    return this.getSection(parsed.section_number, {
      statute: parsed.statute_name,
      actsOnly: /^\s*(?:section\b|sec\.|s\.|s\s|§)/i.test(value),
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** Full-text search over every Act, or one with `statute`. */
  async search(
    options: IpoInStatutesSearchOptions,
  ): Promise<IpoInStatutesSearchResponse> {
    const input = statutesSearchOptions.parse(options);
    const statute = input.statute ? resolveIpoInStatute(input.statute) : null;
    const corpus = await this.ready(options.signal);
    const rows = this.match<IpoInStatuteHit>(
      "s.statute_name, s.section_number, s.title",
      3,
      outlineFtsQuery(input.query, input.syntax),
      statute ? [["statute_name", statute]] : [],
      input.sort,
      input.limit + 1,
      input.offset,
      (row) => row.statute_name,
    );
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      statute_name: statute,
      hits: rows.slice(0, input.limit).map((row) => ({
        statute_name: row.statute_name,
        section_number: row.section_number,
        title: row.title,
        snippet: row.snippet ?? "",
        rank: row.rank ?? null,
      })),
      has_more: rows.length > input.limit,
      offset: input.offset,
      limit: input.limit,
      provenance: this.provenance(corpus),
      corpus,
    };
  }
}

interface MpppRow {
  section_number: string;
  chapter: string | null;
  title: string | null;
  text: unknown;
  source_url: string | null;
}

/**
 * Read-only reader for the IPO India MPPP snapshot. The path comes from
 * IPO_IN_MPPP_CORPUS_PATH or ~/.cache/patent_client_agents/ipo_in_mppp.db.
 */
export class IpoInMpppClient extends IpoInCorpusReader {
  constructor(options: IpoInClientOptions = {}) {
    super(
      {
        label: "IPO India MPPP",
        envPrefix: "IPO_IN_MPPP",
        filename: "ipo_in_mppp.db",
        sourceUrl: IPO_IN_MPPP_PDF_URL,
        sourceName: IPO_IN_MPPP_SOURCE_NAME,
        keys: ["section_number", "chapter"],
        ftsColumns: ["section_number", "title", "text"],
      },
      options,
    );
  }

  /**
   * One MPPP section by reference ('04.05.01', 'Chapter 04.05.01', 'MPPP
   * Chapter 4.5.1'). Unpadded components also match the stored two-digit form.
   */
  async getSection(
    reference: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<IpoInMpppSection> {
    const number = normalizeMpppReference(text(500).parse(reference));
    const padded = number
      .split(".")
      .map((part) => part.padStart(2, "0"))
      .join(".");
    const corpus = await this.ready(options.signal);
    const row = this.query<MpppRow>(
      "SELECT section_number, chapter, title, text, source_url FROM sections WHERE section_number IN (?, ?) ORDER BY section_number = ? DESC LIMIT 1",
      [number, padded, number],
      "section table",
    )[0];
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `MPPP section '${reference}' not found.`,
      );
    return {
      section_number: row.section_number,
      chapter: row.chapter,
      ...(await this.body(row, corpus, options.signal)),
    };
  }

  /** Full-text search over the manual. */
  async search(
    options: IpoInMpppSearchOptions,
  ): Promise<IpoInMpppSearchResponse> {
    const input = mpppSearchOptions.parse(options);
    const corpus = await this.ready(options.signal);
    const rows = this.match<IpoInMpppHit>(
      "s.section_number, s.chapter, s.title",
      2,
      outlineFtsQuery(input.query, input.syntax),
      [],
      input.sort,
      input.limit + 1,
      input.offset,
    );
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      hits: rows.slice(0, input.limit).map((row) => ({
        section_number: row.section_number,
        chapter: row.chapter,
        title: row.title,
        snippet: row.snippet ?? "",
        rank: row.rank ?? null,
      })),
      has_more: rows.length > input.limit,
      offset: input.offset,
      limit: input.limit,
      provenance: this.provenance(corpus),
      corpus,
    };
  }
}

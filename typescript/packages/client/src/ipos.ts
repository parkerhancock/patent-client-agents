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
import { byteLength, env } from "./runtime/env.js";
import type { SnapshotDatabase } from "./runtime/sqlite.js";

/**
 * Readers for the two IPOS Singapore corpora: the IP statutes (Patents Act
 * 1994, Trade Marks Act 1998, Registered Designs Act 2000, Copyright Act
 * 2021) and the IPOS examination manuals (Examination Guidelines for Patent
 * Applications, Trade Marks Work Manual, Registered Designs guidelines). Both
 * are SQLite/FTS5 snapshots in Python's schema, built by
 * scripts/build-ipos-corpora.ts from the official texts
 * (references/ipos/sources.json lists each source, version and hash).
 */
export const IPOS_STATUTES_SOURCE_URL =
  "https://www.wipo.int/wipolex/en/members/profile/SG";
export const IPOS_SSO_URL = "https://sso.agc.gov.sg";
export const IPOS_MANUALS_SOURCE_URL = "https://www.ipos.gov.sg/about-ip/";
export const IPOS_STATUTES_SOURCE_NAME = "IPOS Singapore — IP statutes";
export const IPOS_MANUALS_SOURCE_NAME = "IPOS Singapore — examination manuals";

/** Python's STATUTE_ALIASES (lowercased name or abbreviation to statute key). */
export const IPOS_STATUTE_ALIASES: Readonly<Record<string, string>> = {
  patents: "patents",
  patent: "patents",
  "patents act": "patents",
  "patent act": "patents",
  "patents act 1994": "patents",
  pa: "patents",
  pa1994: "patents",
  tm: "tm",
  "trade marks": "tm",
  "trade marks act": "tm",
  "trade marks act 1998": "tm",
  "trade mark act": "tm",
  trademarks: "tm",
  "trademarks act": "tm",
  "trademark act": "tm",
  tma: "tm",
  tma1998: "tm",
  designs: "designs",
  design: "designs",
  "registered designs": "designs",
  "registered designs act": "designs",
  "registered designs act 2000": "designs",
  "designs act": "designs",
  rda: "designs",
  rda2000: "designs",
  copyright: "copyright",
  "copyright act": "copyright",
  "copyright act 2021": "copyright",
  ca: "copyright",
  ca2021: "copyright",
};

/** Python's MANUAL_ALIASES, plus the designs guidelines' own name. */
export const IPOS_MANUAL_ALIASES: Readonly<Record<string, string>> = {
  peg: "peg",
  "patent examination guidelines": "peg",
  "patent guidelines": "peg",
  "patents examination guidelines": "peg",
  "examination guidelines": "peg",
  "examination guidelines for patent applications": "peg",
  tm: "tm",
  "tm work manual": "tm",
  "trade marks work manual": "tm",
  "trade mark work manual": "tm",
  "trademarks work manual": "tm",
  tmwm: "tm",
  designs: "designs",
  "designs work manual": "designs",
  "industrial designs work manual": "designs",
  "registered designs work manual": "designs",
  "designs guidelines": "designs",
  "registered designs guidelines": "designs",
  dwm: "designs",
};

const normalizeName = (name: string) =>
  name
    .toLowerCase()
    .replace(/[,.()]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^the /, "")
    .replace(/^ipos /, "")
    .replace(/ 2020 rev(?:ised)? ed(?:ition)?$/, "");

/**
 * Statute key for a name or alias, ignoring case, punctuation, a leading
 * "the" and a "2020 Rev. Ed." suffix. Unknown names pass through lowercased,
 * as in Python, and then match nothing.
 */
export function resolveIposStatute(name: string): string {
  const key = normalizeName(name);
  return IPOS_STATUTE_ALIASES[key] ?? key;
}

/** Manual key for a name or alias ('PEG', 'TM Work Manual'); unknown names pass through lowercased. */
export function resolveIposManual(name: string): string {
  const key = normalizeName(name);
  return IPOS_MANUAL_ALIASES[key] ?? key;
}

const LABEL = String.raw`\d+[A-Z]{0,3}(?:\s*\(\s*[0-9A-Za-z]+\s*\))*`;
const ORDINAL =
  "first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth";
const SECTION_FIRST = new RegExp(
  String.raw`^\s*(?:section|sec\.?|s\.?|ss\.?|§+)\s*(?<label>${LABEL})(?:\s*,?\s+(?:of\s+)?(?:the\s+)?(?<statute>\S.*?))?\s*$`,
  "i",
);
const STATUTE_FIRST = new RegExp(
  String.raw`^\s*(?:the\s+)?(?<statute>\S.*?)\s*,?\s+(?:section|sec\.?|s\.?|§+)\s*(?<label>${LABEL})\s*$`,
  "i",
);
const BARE_FIRST = new RegExp(
  String.raw`^\s*(?<label>${LABEL})(?:\s+(?:of\s+)?(?:the\s+)?(?<statute>\S.*?))?\s*$`,
  "i",
);
const BARE_LAST = new RegExp(
  String.raw`^\s*(?:the\s+)?(?<statute>\S.*?)\s+(?<label>${LABEL})\s*$`,
  "i",
);
const SCHEDULE = new RegExp(
  String.raw`^\s*(?:the\s+)?(?:(?<ordinal>${ORDINAL})\s+)?schedule(?:\s+(?<number>\d+))?(?:\s*,?\s+(?:to\s+|of\s+)?(?:the\s+)?(?<statute>\S.*?))?\s*$`,
  "i",
);
const ORDINALS = ORDINAL.split("|");

/**
 * Parse a free-text citation into a statute key (null when the citation names
 * no Act) and a section label. Accepts Python's forms ('Section 13 Patents
 * Act', 'Patents Act s. 13', 's 27(1) Trade Marks Act', '13 Patents Act',
 * 'Patents Act 13') and also '§13', 'Section 13 of the Patents Act 1994' and
 * Schedules ('First Schedule Trade Marks Act', 'Schedule to the Patents Act').
 * Subsection suffixes are kept ('27(1)'); the stored row is the whole section.
 */
export function parseIposCitation(
  citation: string,
): { statute: string | null; section_label: string } | null {
  const schedule = SCHEDULE.exec(citation);
  if (schedule?.groups) {
    const { ordinal, number, statute } = schedule.groups;
    const ordinalName = ordinal
      ? ordinal.toLowerCase()
      : number
        ? ORDINALS[Number(number) - 1]
        : undefined;
    const label = ordinalName
      ? `${ordinalName[0]?.toUpperCase()}${ordinalName.slice(1)} Schedule`
      : "Schedule";
    return {
      statute: statute ? resolveIposStatute(statute) : null,
      section_label: label,
    };
  }
  const known = (statute: string | undefined) =>
    statute !== undefined &&
    Object.hasOwn(IPOS_STATUTE_ALIASES, normalizeName(statute));
  // An Act's name alone ('Copyright Act 2021') cites no section.
  if (known(citation)) return null;
  for (const pattern of [SECTION_FIRST, STATUTE_FIRST, BARE_FIRST, BARE_LAST]) {
    const match = pattern.exec(citation);
    const label = match?.groups?.label;
    const statute = match?.groups?.statute;
    if (!match || !label) continue;
    // Bare forms need a recognised Act, so 'Copyright Act 2021' is not section 2021.
    if (
      (pattern === BARE_LAST || (pattern === BARE_FIRST && statute)) &&
      !known(statute)
    )
      continue;
    return {
      statute: statute ? resolveIposStatute(statute) : null,
      section_label: label
        .replace(/\s+/g, "")
        .toUpperCase()
        .replace(/\(([A-Z]+)\)/g, (m) => m.toLowerCase()),
    };
  }
  return null;
}

const MANUAL_REFERENCE =
  /^\s*(?:ipos\s+)?(?:(?<manual>[a-z][a-z .]*?)\s*,?\s+)?(?:(?:chapter|ch\.?|para(?:graph)?\.?|section|§)\s*)?(?<label>\d+(?:\.\d+)*)\.?(?:\s+(?:of\s+)?(?:the\s+)?(?:ipos\s+)?(?<after>[a-z][a-z .]*?))?\s*$/i;

/**
 * Parse a manual citation into a manual key and a dotted label: 'IPOS PEG
 * 1.5', 'PEG 8.12', 'TM Work Manual 7.5.2', '7.5.2 TM Work Manual',
 * 'Designs Guidelines 2.1'. Returns null without a recognised manual.
 */
export function parseIposManualCitation(
  citation: string,
): { manual: string; section_label: string } | null {
  const match = MANUAL_REFERENCE.exec(citation);
  const name = match?.groups?.manual ?? match?.groups?.after;
  const label = match?.groups?.label;
  if (!name || !label) return null;
  const manual = resolveIposManual(name);
  if (!Object.values(IPOS_MANUAL_ALIASES).includes(manual)) return null;
  return { manual, section_label: label };
}

/** Natural order for labels: "2" < "13" < "13A" < "14"; "1.2" < "1.10". */
export function compareIposLabels(a: string, b: string): number {
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
  return left.length - right.length;
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
const paging = {
  query,
  syntax: z.enum(["and", "or", "adj", "exact"]).default("and"),
  per_page: z.number().int().min(1).max(100).default(10),
  page: z.number().int().min(1).max(100_000).default(1),
};
const statutesSearchOptions = z.object({
  ...paging,
  statute: text(200).nullish(),
  sort: z.enum(["relevance", "statute"]).default("relevance"),
});
const manualsSearchOptions = z.object({
  ...paging,
  manual: text(200).nullish(),
  sort: z.enum(["relevance", "manual"]).default("relevance"),
});
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);

export interface IposClientOptions {
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

export interface IposCorpusStatus {
  available: boolean;
  label: string;
  /** source_version when recorded, else `snapshot <date>`, as Python reports it. */
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

/** Python's IposCorpusMeta / IposManualsCorpusMeta. */
export interface IposCorpusMeta {
  schema_version: number;
  snapshot_date: string | null;
  section_count: number;
  /** statute_count or manual_count. */
  document_count: number;
  source_version: string | null;
}

/** Python's IposStatute: one Act carried by the corpus. */
export interface IposStatute {
  statute: string;
  short_name: string;
  title: string;
  /** The text this row was built from (the WIPO Lex entry for the SSO PDF). */
  source_url: string;
  source_version: string | null;
  /** The Act on Singapore Statutes Online. */
  sso_url: string;
}
/** Python's IposSection: one section or Schedule of an Act, with full text. */
export interface IposSection {
  statute: string;
  short_name: string;
  statute_title: string;
  section_label: string;
  title: string | null;
  breadcrumb: string | null;
  source_url: string;
  source_version: string | null;
  /** The provision on Singapore Statutes Online, when the corpus records it. */
  sso_url: string | null;
  /** Set when the citation named a subsection ("27(1)" gives "(1)"); the text is the whole section. */
  subdivision?: string;
  text: string;
  provenance: CorpusProvenance;
}
export interface IposStatuteSearchHit {
  statute: string;
  short_name: string;
  section_label: string;
  title: string | null;
  breadcrumb: string | null;
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: string;
  /** BM25 rank (lower is more relevant). */
  rank: number | null;
}
interface SearchResponse<Hit> {
  query: string;
  hits: Hit[];
  page: number;
  per_page: number;
  has_more: boolean;
  provenance: CorpusProvenance;
  corpus: IposCorpusStatus;
}
export interface IposStatuteSearchResponse
  extends SearchResponse<IposStatuteSearchHit> {
  /** The resolved statute filter, or null for all four Acts. */
  statute: string | null;
}
/** Python's IposManual. */
export interface IposManual {
  manual: string;
  short_name: string;
  title: string;
  source_url: string;
  source_version: string | null;
}
/** Python's IposManualSection: one numbered paragraph or heading of a manual. */
export interface IposManualSection {
  manual: string;
  short_name: string;
  manual_title: string;
  section_label: string;
  title: string | null;
  breadcrumb: string | null;
  /** The source PDF with its page, e.g. '…pdf#page=12'. */
  source_url: string;
  source_version: string | null;
  text: string;
  provenance: CorpusProvenance;
}
export interface IposManualSearchHit {
  manual: string;
  short_name: string;
  section_label: string;
  title: string | null;
  breadcrumb: string | null;
  snippet: string;
  rank: number | null;
}
export interface IposManualSearchResponse
  extends SearchResponse<IposManualSearchHit> {
  manual: string | null;
}
export type IposStatutesSearchOptions = z.input<
  typeof statutesSearchOptions
> & { signal?: AbortSignal };
export type IposManualsSearchOptions = z.input<typeof manualsSearchOptions> & {
  signal?: AbortSignal;
};

interface Schema {
  label: string;
  envPrefix: string;
  filename: string;
  sourceUrl: string;
  sourceName: string;
  /** 'statute' or 'manual': the document key column. */
  key: "statute" | "manual";
  countKey: string;
  columns: string[];
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
    db.all(`SELECT ${schema.columns.join(", ")} FROM sections LIMIT 0`);
    const columns = db
      .all<{ name: string }>("PRAGMA table_info(sections)")
      .map((row) => row.name);
    const fts = db.get<{ sql: string }>(
      "SELECT sql FROM sqlite_master WHERE name = ? AND type = 'table'",
      ["sections_fts"],
    );
    const ftsColumns = db
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
      JSON.stringify(ftsColumns) !==
        JSON.stringify(["section_label", "title", "text"]) ||
      count === undefined
    )
      throw new Error();
    return { metadata, count, ssoUrl: columns.includes("sso_url") };
  };
}

/** Shared artifact lifecycle, status and row access for both IPOS corpora. */
abstract class IposCorpusReader {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private metadata: Record<string, string> = {};
  private count: number | null = null;
  private sha256: string | null = null;
  private fileSha256: string | null = null;
  private compression: "none" | "zstd" | null = null;
  /** Whether the corpus has the sso_url column (Python-built files do not). */
  protected ssoUrl = false;
  private readonly path: string;
  private readonly source: IposClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;
  private readonly maxTextBytes: number;

  protected constructor(
    protected readonly schema: Schema,
    options: IposClientOptions,
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
      this.ssoUrl = snapshot.value.ssoUrl;
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

  private status(available: boolean, error?: CorpusError): IposCorpusStatus {
    const metadata = { ...this.metadata };
    const source = metadata.source_version || null;
    return {
      available,
      label: this.schema.label,
      corpus_version:
        source && source !== "current"
          ? source
          : metadata.snapshot_date
            ? `snapshot ${metadata.snapshot_date}`
            : "unknown",
      schema_version: metadata.schema_version
        ? Number(metadata.schema_version)
        : null,
      section_count: this.count,
      snapshot_date: metadata.snapshot_date ?? null,
      source_version: source,
      corpus_synced_at: corpusTimestamp(metadata.snapshot_date),
      artifact_sha256: this.sha256,
      file_sha256: this.fileSha256,
      compression: this.compression,
      source_url: this.schema.sourceUrl,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  protected provenance(
    corpus: IposCorpusStatus,
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
  async getCorpusStatus(): Promise<IposCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  /** Python's meta(): schema version, snapshot date and row counts. */
  async meta(options: { signal?: AbortSignal } = {}): Promise<IposCorpusMeta> {
    const corpus = await this.ready(options.signal);
    return {
      schema_version: corpus.schema_version ?? 0,
      snapshot_date: corpus.snapshot_date,
      section_count: Number(
        corpus.metadata.section_count ?? corpus.section_count ?? 0,
      ),
      document_count: Number(corpus.metadata[this.schema.countKey] ?? 0),
      source_version: corpus.source_version,
    };
  }

  /** The stored text, checked against the size limit. */
  protected checkText(value: unknown, signal?: AbortSignal): string {
    if (typeof value !== "string")
      throw new CorpusError(
        "INVALID_CORPUS",
        `The ${this.schema.label} section text is not readable.`,
      );
    if (byteLength(value) > this.maxTextBytes)
      throw new CorpusError(
        "SECTION_TOO_LARGE",
        `${this.schema.label} section text exceeds the configured decoded-byte limit.`,
      );
    checkCorpusSignal(signal);
    return value;
  }

  /**
   * Ranked FTS5 rows (one extra for has_more). Every term is quoted, so
   * caller input never runs as MATCH syntax. Document order keeps each Act
   * or manual in its own order; relevance ties fall back to it too.
   */
  protected match<T>(
    query: string,
    syntax: "and" | "or" | "adj" | "exact",
    filter: string | null,
    sort: "relevance" | "document",
    perPage: number,
    page: number,
  ): T[] {
    const match = outlineFtsQuery(query, syntax);
    if (!match) return [];
    const column = this.schema.key;
    const order =
      sort === "relevance" ? "rank, s.rowid" : `s.${column}, s.rowid`;
    return this.query<T>(
      `SELECT s.${column}, s.short_name, s.section_label, s.title, s.breadcrumb, snippet(sections_fts, 2, '<mark>', '</mark>', '…', 40) AS snippet, rank FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ?${filter ? ` AND s.${column} = ?` : ""} ORDER BY ${order} LIMIT ? OFFSET ?`,
      [match, ...(filter ? [filter] : []), perPage + 1, (page - 1) * perPage],
      "full-text index",
    );
  }

  close() {
    this.generation++;
    this.db?.close();
    this.db = undefined;
    this.metadata = {};
    this.count = null;
    this.ssoUrl = false;
    this.sha256 = null;
    this.fileSha256 = null;
    this.compression = null;
  }
}

interface StatuteRow {
  statute: string;
  short_name: string;
  statute_title: string;
  section_label: string;
  title: string | null;
  breadcrumb: string | null;
  source_url: string;
  source_version: string | null;
  sso_url?: string | null;
  text: unknown;
}
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
];
/** SSO Act codes, for Python-built corpora without the sso_url column. */
const SSO_ACTS: Record<string, string> = {
  patents: "PA1994",
  tm: "TMA1998",
  designs: "RDA2000",
  copyright: "CA2021",
};

/**
 * Read-only reader for the IPOS statutes snapshot. It never downloads or
 * rebuilds the corpus; the path comes from IPOS_STATUTES_CORPUS_PATH or
 * ~/.cache/patent_client_agents/ipos_statutes.db, as in Python.
 */
export class IposStatutesClient extends IposCorpusReader {
  constructor(options: IposClientOptions = {}) {
    super(
      {
        label: "IPOS statutes",
        envPrefix: "IPOS_STATUTES",
        filename: "ipos_statutes.db",
        sourceUrl: IPOS_STATUTES_SOURCE_URL,
        sourceName: IPOS_STATUTES_SOURCE_NAME,
        key: "statute",
        countKey: "statute_count",
        columns: STATUTE_COLUMNS,
      },
      options,
    );
  }

  private columns() {
    return `${STATUTE_COLUMNS.join(", ")}${this.ssoUrl ? ", sso_url" : ""}`;
  }

  /** The Acts in the snapshot, one row each in document order (Python's list_statutes). */
  async listStatutes(
    options: { signal?: AbortSignal } = {},
  ): Promise<IposStatute[]> {
    await this.ready(options.signal);
    return this.query<StatuteRow>(
      `SELECT ${this.columns()} FROM sections WHERE rowid IN (SELECT MIN(rowid) FROM sections GROUP BY statute) ORDER BY rowid`,
      [],
      "section table",
    ).map((row) => ({
      statute: row.statute,
      short_name: row.short_name,
      title: row.statute_title,
      source_url: row.source_url,
      source_version: row.source_version,
      sso_url: `${IPOS_SSO_URL}/Act/${SSO_ACTS[row.statute] ?? row.statute.toUpperCase()}`,
    }));
  }

  /**
   * One section or Schedule by statute and label. The statute may be a key
   * or alias; without one, the label must exist in exactly one Act
   * (AMBIGUOUS_SECTION lists them otherwise). A subsection label ("27(1)")
   * returns its enclosing section with `subdivision` set.
   */
  async getSection(
    sectionLabel: string,
    options: { statute?: string | null; signal?: AbortSignal } = {},
  ): Promise<IposSection> {
    const raw = text(100).parse(sectionLabel);
    const label = /^\d/.test(raw) ? raw.replace(/\s+/g, "") : raw;
    const statute = options.statute
      ? resolveIposStatute(text(200).parse(options.statute))
      : null;
    const corpus = await this.ready(options.signal);
    const lookup = (value: string) =>
      this.query<StatuteRow>(
        `SELECT ${this.columns()} FROM sections WHERE section_label = ? COLLATE NOCASE${statute ? " AND statute = ?" : ""} ORDER BY rowid`,
        statute ? [value, statute] : [value],
        "section table",
      );
    let rows = lookup(label);
    const parent = /^(\d+[A-Za-z]{0,3})(\(.+)$/.exec(label);
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
          ? `Section '${label}' not found in '${statute}'.`
          : `Section '${label}' not found in any bundled Act.`,
      );
    if (rows.length > 1)
      throw new CorpusError(
        "AMBIGUOUS_SECTION",
        `Section '${label}' is ambiguous — exists in: ${rows.map((item) => item.short_name).join(", ")}. Name the Act to disambiguate.`,
      );
    const body = this.checkText(row.text, options.signal);
    const ssoUrl =
      row.sso_url ??
      (SSO_ACTS[row.statute]
        ? `${IPOS_SSO_URL}/Act/${SSO_ACTS[row.statute]}`
        : null);
    return {
      statute: row.statute,
      short_name: row.short_name,
      statute_title: row.statute_title,
      section_label: row.section_label,
      title: row.title,
      breadcrumb: row.breadcrumb,
      source_url: row.source_url,
      source_version: row.source_version,
      sso_url: ssoUrl,
      ...(subdivision ? { subdivision } : {}),
      text: body,
      provenance: this.provenance(corpus, ssoUrl ?? row.source_url),
    };
  }

  /**
   * One section by free-text citation (see parseIposCitation). An
   * unparseable citation is SECTION_NOT_FOUND, as Python returns None.
   */
  async getByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<IposSection> {
    const value = text(500).parse(citation);
    const parsed = parseIposCitation(value);
    if (!parsed)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `Could not parse citation '${value}'; expected e.g. 'Section 13 Patents Act'.`,
      );
    return this.getSection(parsed.section_label, {
      statute: parsed.statute,
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** Full-text search over every Act, or one with `statute` (Python's search). */
  async search(
    options: IposStatutesSearchOptions,
  ): Promise<IposStatuteSearchResponse> {
    const input = statutesSearchOptions.parse(options);
    const statute = input.statute ? resolveIposStatute(input.statute) : null;
    const corpus = await this.ready(options.signal);
    const rows = this.match<IposStatuteSearchHit>(
      input.query,
      input.syntax,
      statute,
      input.sort === "statute" ? "document" : "relevance",
      input.per_page,
      input.page,
    );
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      statute,
      hits: rows.slice(0, input.per_page).map((row) => ({
        statute: row.statute,
        short_name: row.short_name,
        section_label: row.section_label,
        title: row.title,
        breadcrumb: row.breadcrumb,
        snippet: row.snippet ?? "",
        rank: row.rank ?? null,
      })),
      page: input.page,
      per_page: input.per_page,
      has_more: rows.length > input.per_page,
      provenance: this.provenance(corpus),
      corpus,
    };
  }
}

interface ManualRow {
  manual: string;
  short_name: string;
  manual_title: string;
  section_label: string;
  title: string | null;
  breadcrumb: string | null;
  source_url: string;
  source_version: string | null;
  text: unknown;
}
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
/** Where each manual is listed on ipos.gov.sg. */
const MANUAL_PAGES: Record<string, string> = {
  peg: "https://www.ipos.gov.sg/about-ip/patents/guides/",
  tm: "https://www.ipos.gov.sg/about-ip/trade-marks/tm-guides/",
  designs: "https://www.ipos.gov.sg/about-ip/designs/guides/",
};

/**
 * Read-only reader for the IPOS manuals snapshot. The path comes from
 * IPOS_MANUALS_CORPUS_PATH or ~/.cache/patent_client_agents/ipos_manuals.db.
 */
export class IposManualsClient extends IposCorpusReader {
  constructor(options: IposClientOptions = {}) {
    super(
      {
        label: "IPOS manuals",
        envPrefix: "IPOS_MANUALS",
        filename: "ipos_manuals.db",
        sourceUrl: IPOS_MANUALS_SOURCE_URL,
        sourceName: IPOS_MANUALS_SOURCE_NAME,
        key: "manual",
        countKey: "manual_count",
        columns: MANUAL_COLUMNS,
      },
      options,
    );
  }

  /** The manuals in the snapshot, in document order (Python's list_manuals). */
  async listManuals(
    options: { signal?: AbortSignal } = {},
  ): Promise<IposManual[]> {
    await this.ready(options.signal);
    return this.query<ManualRow>(
      `SELECT ${MANUAL_COLUMNS.join(", ")} FROM sections WHERE rowid IN (SELECT MIN(rowid) FROM sections GROUP BY manual) ORDER BY rowid`,
      [],
      "section table",
    ).map((row) => ({
      manual: row.manual,
      short_name: row.short_name,
      title: row.manual_title,
      source_url:
        MANUAL_PAGES[row.manual] ?? row.source_url.replace(/#.*$/, ""),
      source_version: row.manual === "tm" ? null : row.source_version,
    }));
  }

  /** One manual paragraph or heading by manual key (or alias) and dotted label. */
  async getSection(
    manual: string,
    sectionLabel: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<IposManualSection> {
    const key = resolveIposManual(text(200).parse(manual));
    const label = text(100).parse(sectionLabel).replace(/\.$/, "");
    const corpus = await this.ready(options.signal);
    const row = this.query<ManualRow>(
      `SELECT ${MANUAL_COLUMNS.join(", ")} FROM sections WHERE manual = ? AND section_label = ?`,
      [key, label],
      "section table",
    )[0];
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `Section '${label}' not found in IPOS manual '${key}'.`,
      );
    return {
      manual: row.manual,
      short_name: row.short_name,
      manual_title: row.manual_title,
      section_label: row.section_label,
      title: row.title,
      breadcrumb: row.breadcrumb,
      source_url: row.source_url,
      source_version: row.source_version,
      text: this.checkText(row.text, options.signal),
      provenance: this.provenance(corpus, row.source_url),
    };
  }

  /** One section by citation ('IPOS PEG 8.12', 'TM Work Manual 7.5.2'); unparseable is SECTION_NOT_FOUND. */
  async getByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<IposManualSection> {
    const value = text(500).parse(citation);
    const parsed = parseIposManualCitation(value);
    if (!parsed)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `Could not parse citation '${value}'; expected e.g. 'IPOS PEG 8.12' or 'TM Work Manual 7.5.2'.`,
      );
    return this.getSection(parsed.manual, parsed.section_label, options);
  }

  /** Full-text search over every manual, or one with `manual` (Python's search). */
  async search(
    options: IposManualsSearchOptions,
  ): Promise<IposManualSearchResponse> {
    const input = manualsSearchOptions.parse(options);
    const manual = input.manual ? resolveIposManual(input.manual) : null;
    const corpus = await this.ready(options.signal);
    const rows = this.match<IposManualSearchHit>(
      input.query,
      input.syntax,
      manual,
      input.sort === "manual" ? "document" : "relevance",
      input.per_page,
      input.page,
    );
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      manual,
      hits: rows.slice(0, input.per_page).map((row) => ({
        manual: row.manual,
        short_name: row.short_name,
        section_label: row.section_label,
        title: row.title,
        breadcrumb: row.breadcrumb,
        snippet: row.snippet ?? "",
        rank: row.rank ?? null,
      })),
      page: input.page,
      per_page: input.per_page,
      has_more: rows.length > input.per_page,
      provenance: this.provenance(corpus),
      corpus,
    };
  }
}

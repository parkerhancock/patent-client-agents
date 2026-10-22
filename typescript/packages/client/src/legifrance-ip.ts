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
import { env } from "./runtime/env.js";
import type { SnapshotDatabase } from "./runtime/sqlite.js";

/** DILA's LEGI open data, the database behind Légifrance, which the corpus is built from. */
export const LEGIFRANCE_IP_SOURCE_URL =
  "https://echanges.dila.gouv.fr/OPENDATA/LEGI/";
export const LEGIFRANCE_IP_SOURCE_NAME =
  "Légifrance — French IP statutes (CPI + Code de commerce L.151 trade secrets)";
const LABEL = "Légifrance IP";
const ENV_PREFIX = "LEGIFRANCE_IP";

/** Python's closed vocabulary for the `statute` column and filter. */
export const LEGIFRANCE_STATUTES = ["CPI", "Code de commerce"] as const;
export type LegifranceStatute = (typeof LEGIFRANCE_STATUTES)[number];

const STATUTE_NAMES: [RegExp, LegifranceStatute][] = [
  [
    /^(?:du\s+)?(?:cpi|code\s+de\s+la\s+propri[ée]t[ée]\s+intellectuelle)$/i,
    "CPI",
  ],
  [/^(?:du\s+)?(?:code\s+de\s+commerce|c\.?\s*com\.?)$/i, "Code de commerce"],
];
const CITATION =
  /^\s*(?:art(?:icle)?\.?\s*)?L\.?\s*(\d+(?:\s*[-.]\s*\d+)+)\s*(?:,?\s+(.+?))?\s*$/i;

/**
 * Parse a French statutory citation into its statute (null when the citation
 * names none) and canonical article number: 'L. 611-10 CPI', 'Art. L. 611-10
 * CPI', 'L611-10 CPI', 'L. 151-1 Code de commerce', 'article L. 613-3 du code
 * de la propriété intellectuelle', 'L. 151-1 C. com.' or a bare 'L. 611-10'.
 */
export function parseLegifranceCitation(citation: string): {
  statute: LegifranceStatute | null;
  section: string;
} {
  const match = CITATION.exec(citation);
  const statuteText = match?.[2]?.trim();
  const statute = statuteText
    ? (STATUTE_NAMES.find(([pattern]) => pattern.test(statuteText))?.[1] ??
      undefined)
    : null;
  if (!match || statute === undefined)
    throw new CorpusError(
      "INVALID_CITATION",
      `could not parse citation '${citation}'; expected forms like 'L. 611-10 CPI' or 'Art. L. 151-1 Code de commerce'`,
    );
  return {
    statute,
    section: `L${(match[1] as string).replace(/\s+/g, "").replace(/\./g, "-")}`,
  };
}

/** Python's `_normalize_section`: 'L. 611-10', 'L 611.10' → 'L611-10'. */
export function normalizeLegifranceSection(value: string): string {
  let cleaned = value.replace(/\s+/g, "").toUpperCase().replace(/\./g, "-");
  if (cleaned.startsWith("L-")) cleaned = `L${cleaned.slice(2)}`;
  return cleaned;
}

/** The Légifrance page of one article version. */
export const legifranceArticleUrl = (articleId: string) =>
  `https://www.legifrance.gouv.fr/codes/article_lc/${articleId}`;

const text = (max: number) =>
  z
    .string()
    .trim()
    .min(1)
    .max(max)
    .refine((value) => !value.includes("\0"), "Values must not contain NUL.");
const searchOptions = z.object({
  query: z
    .string()
    .max(8192)
    .refine((value) => !value.includes("\0"), "Queries must not contain NUL."),
  statute: z.enum(LEGIFRANCE_STATUTES).nullish(),
  syntax: z.enum(["adj", "exact", "and", "or"]).default("and"),
  limit: z.number().int().min(1).max(100).default(10),
  offset: z.number().int().min(0).safe().default(0),
});
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);

export interface LegifranceIpClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also LEGIFRANCE_IP_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also LEGIFRANCE_IP_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type LegifranceSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

/** One code as the LEGI build records it in meta `codes`. */
export interface LegifranceCodeInfo {
  statute: string;
  id: string;
  title: string;
  /** Which article numbers were kept, as a regular expression. */
  kept: string;
  articles: number;
}
const codeInfo = z.object({
  statute: z.string(),
  id: z.string(),
  title: z.string(),
  kept: z.string(),
  articles: z.number(),
});
function parseCodes(value: string | undefined): LegifranceCodeInfo[] | null {
  if (!value) return null;
  try {
    return z.array(codeInfo).parse(JSON.parse(value));
  } catch {
    return null;
  }
}

export interface LegifranceIpCorpusStatus {
  available: boolean;
  label: string;
  /** source_version, e.g. 'LEGI 20261021-213023' (the last DILA export applied), or 'unknown'. */
  corpus_version: string;
  schema_version: number | null;
  section_count: number | null;
  /** The date the selected versions are in force on. */
  snapshot_date: string | null;
  corpus_synced_at: string | null;
  artifact_sha256: string | null;
  file_sha256: string | null;
  compression: "none" | "zstd" | null;
  source_url: string;
  /** Per-code identity and article counts, or null for a corpus built without them. */
  codes: LegifranceCodeInfo[] | null;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
/** One French statutory article. */
export interface LegifranceSection {
  /** 'CPI' or 'Code de commerce'. */
  statute: string;
  /** 'L611-10'. */
  section: string;
  /** The heading of the code division containing the article (French articles have none of their own). */
  title: string | null;
  text: string;
  /** Légifrance article id (LEGIARTI…), when the corpus records it. */
  article_id: string | null;
  /** Date this version took effect, when recorded. */
  in_force_since: string | null;
  /** Code headings from the Partie down, joined with ' > ', when recorded. */
  breadcrumb: string | null;
  /** The article's Légifrance page, when the id is recorded. */
  url: string | null;
  provenance: CorpusProvenance;
}
export interface LegifranceSearchHit {
  statute: string;
  section: string;
  title: string | null;
  /** FTS5 snippet of the text with <mark>…</mark> around matches. */
  snippet: string;
  /** BM25 rank (lower is more relevant). */
  rank: number | null;
}
export interface LegifranceSearchResponse {
  query: string;
  statute: string | null;
  hits: LegifranceSearchHit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: LegifranceIpCorpusStatus;
}

interface Row {
  statute: string;
  section: string;
  title: string | null;
  text: unknown;
  article_id?: string | null;
  in_force_since?: string | null;
  breadcrumb?: string | null;
}

const EXTRA_COLUMNS = ["article_id", "in_force_since", "breadcrumb"];

function validate(db: SnapshotDatabase) {
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
      "Unsupported Légifrance IP corpus schema; the supported version is 1.",
    );
  db.all("SELECT statute, section, title, text FROM sections LIMIT 0");
  const sectionColumns = db
    .all<{ name: string }>("PRAGMA table_info(sections)")
    .map((row) => row.name);
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
    JSON.stringify(columns) !== JSON.stringify(["title", "text"]) ||
    count === undefined
  )
    throw new Error();
  return {
    metadata,
    count,
    extras: EXTRA_COLUMNS.every((name) => sectionColumns.includes(name)),
  };
}

/**
 * Read-only reader for the Légifrance IP snapshot: the legislative part of
 * the Code de la propriété intellectuelle and the trade-secret articles of the
 * Code de commerce (L151-1 to L154-1), in force on the snapshot date. It never
 * downloads or rebuilds the corpus.
 */
export class LegifranceIpClient {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private metadata: Record<string, string> = {};
  private codes: LegifranceCodeInfo[] | null = null;
  private extras = false;
  private count: number | null = null;
  private sha256: string | null = null;
  private fileSha256: string | null = null;
  private compression: "none" | "zstd" | null = null;
  private readonly path: string;
  private readonly source: LegifranceIpClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: LegifranceIpClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("legifrance_ip.db") ??
      "";
    this.source = options.source;
    if (!options.source) text(2048).parse(this.path);
    const pin = (value: string | undefined) =>
      value === undefined ? undefined : sha256Pin.parse(value);
    this.expectedSha256 = pin(
      options.expectedSha256 ?? env(`${ENV_PREFIX}_CORPUS_SHA256`),
    );
    this.expectedFileSha256 = pin(
      options.expectedFileSha256 ?? env(`${ENV_PREFIX}_CORPUS_FILE_SHA256`),
    );
  }

  private async open() {
    if (this.db) return;
    this.opening ??= (async (generation: number) => {
      const snapshot = await openCorpusSnapshot(
        {
          path: this.path,
          source: this.source,
          label: LABEL,
          envVar: `${ENV_PREFIX}_CORPUS_PATH`,
          ...(this.expectedSha256
            ? { expectedSha256: this.expectedSha256 }
            : {}),
          ...(this.expectedFileSha256
            ? { expectedFileSha256: this.expectedFileSha256 }
            : {}),
        },
        validate,
        LABEL,
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
      this.codes = parseCodes(snapshot.value.metadata.codes);
      this.extras = snapshot.value.extras;
      this.count = snapshot.value.count;
      this.sha256 = snapshot.sha256;
      this.fileSha256 = snapshot.fileSha256;
      this.compression = snapshot.compression;
    })(this.generation).finally(() => {
      this.opening = undefined;
    });
    await this.opening;
  }

  private query<T>(sql: string, bind: (string | number)[], what: string): T[] {
    if (!this.db) throw new CorpusError("ABORTED", "The corpus was closed.");
    try {
      return this.db.all<T>(sql, bind);
    } catch {
      throw new CorpusError(
        "INVALID_CORPUS",
        `The Légifrance IP ${what} is not readable.`,
      );
    }
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): LegifranceIpCorpusStatus {
    const metadata = { ...this.metadata };
    const snapshot = metadata.snapshot_date;
    const version = metadata.source_version;
    return {
      available,
      label: LABEL,
      corpus_version: version && version !== "current" ? version : "unknown",
      schema_version: metadata.schema_version
        ? Number(metadata.schema_version)
        : null,
      section_count: this.count,
      snapshot_date: snapshot ?? null,
      corpus_synced_at: corpusTimestamp(snapshot),
      artifact_sha256: this.sha256,
      file_sha256: this.fileSha256,
      compression: this.compression,
      source_url: LEGIFRANCE_IP_SOURCE_URL,
      codes: this.codes,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: LegifranceIpCorpusStatus): CorpusProvenance {
    return {
      source_url: LEGIFRANCE_IP_SOURCE_URL,
      source_name: LEGIFRANCE_IP_SOURCE_NAME,
      retrieved_at: corpus.corpus_synced_at,
      accessed_at: new Date().toISOString(),
      cache_hit: true,
      corpus_synced_at: corpus.corpus_synced_at,
      corpus_version: corpus.corpus_version,
    };
  }

  private async ready(signal?: AbortSignal) {
    checkCorpusSignal(signal);
    await this.open();
    checkCorpusSignal(signal);
    return this.status(true);
  }

  /** Snapshot identity and freshness; never throws for an unusable artifact. */
  async getCorpusStatus(): Promise<LegifranceIpCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  private toSection(row: Row, corpus: LegifranceIpCorpusStatus) {
    if (typeof row.text !== "string")
      throw new CorpusError(
        "INVALID_CORPUS",
        "The Légifrance IP article text is not readable.",
      );
    const articleId = row.article_id ?? null;
    return {
      statute: row.statute,
      section: row.section,
      title: row.title,
      text: row.text,
      article_id: articleId,
      in_force_since: row.in_force_since ?? null,
      breadcrumb: row.breadcrumb ?? null,
      url: articleId ? legifranceArticleUrl(articleId) : null,
      provenance: this.provenance(corpus),
    };
  }

  /**
   * One article by statute and number, as Python's get_by_section_number
   * ('L. 611-10' and 'L 611.10' normalize to 'L611-10').
   */
  async getBySectionNumber(
    statute: string,
    section: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<LegifranceSection> {
    const name = text(200).parse(statute);
    const number = normalizeLegifranceSection(text(100).parse(section));
    const corpus = await this.ready(options.signal);
    const columns = `statute, section, title, text${this.extras ? `, ${EXTRA_COLUMNS.join(", ")}` : ""}`;
    const row = this.query<Row>(
      `SELECT ${columns} FROM sections WHERE statute = ? AND section = ? LIMIT 1`,
      [name, number],
      "section table",
    )[0];
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `could not find Légifrance article ${number} in '${name}'`,
      );
    checkCorpusSignal(options.signal);
    return this.toSection(row, corpus);
  }

  /**
   * One article by citation (see parseLegifranceCitation). A citation without
   * a statute resolves when the number exists in one code only.
   */
  async getSection(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<LegifranceSection> {
    const { statute, section } = parseLegifranceCitation(
      text(500).parse(citation),
    );
    if (statute) return this.getBySectionNumber(statute, section, options);
    const corpus = await this.ready(options.signal);
    const columns = `statute, section, title, text${this.extras ? `, ${EXTRA_COLUMNS.join(", ")}` : ""}`;
    const rows = this.query<Row>(
      `SELECT ${columns} FROM sections WHERE section = ? ORDER BY statute`,
      [section],
      "section table",
    );
    const row = rows[0];
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `could not find Légifrance article ${section} in any bundled code`,
      );
    if (rows.length > 1)
      throw new CorpusError(
        "AMBIGUOUS_SECTION",
        `Article ${section} exists in: ${rows.map((item) => item.statute).join(", ")}. Name the code, e.g. '${section} CPI'.`,
      );
    checkCorpusSignal(options.signal);
    return this.toSection(row, corpus);
  }

  /**
   * Full-text search over article text and headings, optionally within one
   * code. Diacritics fold ('brevetabilite' matches 'brevetabilité'). Terms are
   * always quoted as FTS5 text; the default 'and' syntax requires every term.
   */
  async search(
    options: LegifranceSearchOptions,
  ): Promise<LegifranceSearchResponse> {
    const input = searchOptions.parse(options);
    const statute = input.statute ?? null;
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const bind: (string | number)[] = [match];
    if (statute) bind.push(statute);
    const rows = match
      ? this.query<LegifranceSearchHit>(
          `SELECT s.statute, s.section, s.title, snippet(sections_fts, 1, '<mark>', '</mark>', '…', 40) AS snippet, rank FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ?${statute ? " AND s.statute = ?" : ""} ORDER BY rank, s.rowid LIMIT ? OFFSET ?`,
          [...bind, input.limit + 1, input.offset],
          "full-text index",
        )
      : [];
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      statute,
      hits: rows.slice(0, input.limit).map((row) => ({
        statute: row.statute,
        section: row.section,
        title: row.title ?? null,
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

  close() {
    this.generation++;
    this.db?.close();
    this.db = undefined;
    this.metadata = {};
    this.codes = null;
    this.extras = false;
    this.count = null;
    this.sha256 = null;
    this.fileSha256 = null;
    this.compression = null;
  }
}

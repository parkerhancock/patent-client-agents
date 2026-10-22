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

/** The consolidated Portuguese text the corpus is built from (Câmara dos Deputados). */
export const INPI_BR_STATUTES_SOURCE_URL =
  "https://www2.camara.leg.br/legin/fed/lei/1996/lei-9279-14-maio-1996-374644-normaatualizada-pl.html";
export const INPI_BR_STATUTES_SOURCE_NAME =
  "INPI Brazil — LPI (Lei 9.279/1996)";
/** The official Planalto publication; Python's base for per-Article links. */
export const INPI_BR_STATUTES_PLANALTO_URL =
  "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm";
const LABEL = "INPI Brazil statutes";
const ENV_PREFIX = "INPI_BR_STATUTES";

// "Art. 6", "Art 6º", "Article 6", "Artigo 6", "Art. 229-C", "Art. 195(XI) LPI",
// "Art. 195 da LPI". A parenthesised subdivision rolls up to the Article.
const CITATION =
  /^\s*(?:art\.?|article|artigo|a)\s*(\d{1,3})([a-z])?\s*(?:º|°)?\s*(?:-\s*([a-z])\b)?\s*(?:\([^)]*\)\s*)*(?:(?:da\s+)?lpi)?\s*$/i;

/** True when `value` is an Article citation or slug ('Art. 6', 'art195', 'art229-c'). */
export function isInpiBrCitation(value: string): boolean {
  return CITATION.test(value);
}

/**
 * The Article slug for a citation, slug or Planalto URL with an '#Art6'
 * anchor ('Art. 6' → 'art6', 'Art. 229-C' → 'art229-c'), or null.
 */
export function inpiBrSlug(value: string): string | null {
  let candidate = value.trim();
  if (/^https?:\/\//i.test(candidate)) {
    const hash = candidate.indexOf("#");
    if (hash < 0) return null;
    candidate = candidate.slice(hash + 1);
  }
  candidate = candidate.replace(/^[#/]+/, "");
  const match = CITATION.exec(candidate);
  if (!match) return null;
  const letter = match[2] ?? match[3];
  return `art${Number(match[1])}${letter ? `-${letter.toLowerCase()}` : ""}`;
}

/** Per-Article link on the official Planalto page, as Python builds it. */
export function inpiBrResultUrl(href: string): string {
  return href.startsWith("art")
    ? `${INPI_BR_STATUTES_PLANALTO_URL}#Art${href.slice(3).toUpperCase()}`
    : `${INPI_BR_STATUTES_PLANALTO_URL}#${href}`;
}

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
  syntax: z.enum(["adj", "exact", "and", "or"]).default("adj"),
  sort: z.enum(["relevance", "outline"]).default("relevance"),
  limit: z.number().int().min(1).max(100).default(10),
  offset: z.number().int().min(0).safe().default(0),
  version: z.literal("current").default("current"),
});
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);

export interface InpiBrStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also INPI_BR_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also INPI_BR_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type InpiBrSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

export interface InpiBrStatutesCorpusStatus {
  available: boolean;
  label: string;
  /** source_version when recorded (e.g. 'consolidated through Lei nº 14.852, de 3/5/2024'), else lpi_year, else 'unknown'. */
  corpus_version: string;
  schema_version: number | null;
  section_count: number | null;
  snapshot_date: string | null;
  corpus_synced_at: string | null;
  /** The newest amending law the consolidated text cites, with its date. */
  latest_amendment: string | null;
  /** What the English translation reflects; null when not recorded. */
  english_version: string | null;
  artifact_sha256: string | null;
  file_sha256: string | null;
  compression: "none" | "zstd" | null;
  source_url: string;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
/** One LPI Article: Portuguese (authoritative) and the English translation when there is one. */
export interface InpiBrSection {
  /** Slug, e.g. 'art6', 'art229-c'. */
  href: string;
  /** 'Art. 6'. */
  article_number: string | null;
  title_pt: string | null;
  title_en: string | null;
  /** The Title (Título) the Article sits in, e.g. 'TÍTULO V — DOS CRIMES CONTRA A PROPRIEDADE INDUSTRIAL'. */
  title_section: string | null;
  text_pt: string;
  text_en: string | null;
  html_pt: string;
  html_en: string | null;
  version: string;
  /** Link to the Article on the official Planalto page. */
  result_url: string;
  provenance: CorpusProvenance;
}
export interface InpiBrSearchHit {
  /** 'Art. 195 — Comete crime de concorrência desleal quem:'. */
  title: string;
  href: string;
  article_number: string | null;
  /** [Title, Article], as Python's breadcrumb. */
  path: string[];
  result_url: string;
  /** FTS5 snippet of the Portuguese text with <mark>…</mark> around matches. */
  snippet: string;
  /** BM25 rank (lower is more relevant). */
  rank: number | null;
}
export interface InpiBrSearchResponse {
  query: string;
  hits: InpiBrSearchHit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: InpiBrStatutesCorpusStatus;
}
export interface InpiBrVersion {
  label: string;
  value: string;
  current: boolean;
}

interface Row {
  href: string;
  article_number: string | null;
  title_pt: string | null;
  title_en: string | null;
  title_section: string | null;
  text_pt: unknown;
  text_en: unknown;
  html_pt: unknown;
  html_en: unknown;
}

const COLUMNS = [
  "article_number",
  "title_pt",
  "title_en",
  "text_pt",
  "text_en",
] as const;

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
      "Unsupported INPI Brazil statutes corpus schema; the supported version is 1.",
    );
  db.all(
    "SELECT href, article_number, title_pt, title_en, title_section, text_pt, text_en, html_pt, html_en FROM sections LIMIT 0",
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
    JSON.stringify(columns) !== JSON.stringify(COLUMNS) ||
    count === undefined
  )
    throw new Error();
  return { metadata, count };
}

/**
 * Read-only reader for the LPI (Lei nº 9.279/1996) snapshot: one row per
 * Article with the consolidated Portuguese text and the English translation
 * of the 1996 text. It never downloads or rebuilds the corpus.
 */
export class InpiBrStatutesClient {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private metadata: Record<string, string> = {};
  private count: number | null = null;
  private sha256: string | null = null;
  private fileSha256: string | null = null;
  private compression: "none" | "zstd" | null = null;
  private readonly path: string;
  private readonly source: InpiBrStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: InpiBrStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("inpi_br_statutes.db") ??
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
        `The INPI Brazil statutes ${what} is not readable.`,
      );
    }
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): InpiBrStatutesCorpusStatus {
    const metadata = { ...this.metadata };
    const snapshot = metadata.snapshot_date;
    const version = [metadata.source_version, metadata.lpi_year].find(
      (value) => value && value !== "current",
    );
    return {
      available,
      label: LABEL,
      corpus_version: version ?? "unknown",
      schema_version: metadata.schema_version
        ? Number(metadata.schema_version)
        : null,
      section_count: this.count,
      snapshot_date: snapshot ?? null,
      corpus_synced_at: corpusTimestamp(snapshot),
      latest_amendment: metadata.latest_amendment || null,
      english_version: metadata.source_en_version || null,
      artifact_sha256: this.sha256,
      file_sha256: this.fileSha256,
      compression: this.compression,
      source_url: metadata.source_pt || INPI_BR_STATUTES_SOURCE_URL,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: InpiBrStatutesCorpusStatus): CorpusProvenance {
    return {
      source_url: corpus.source_url,
      source_name: INPI_BR_STATUTES_SOURCE_NAME,
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
  async getCorpusStatus(): Promise<InpiBrStatutesCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  /** The installed snapshot as Python's single 'current' version entry. */
  async listVersions(
    options: { signal?: AbortSignal } = {},
  ): Promise<InpiBrVersion[]> {
    const corpus = await this.ready(options.signal);
    return [
      {
        label: `LPI (Lei 9.279/1996) ${corpus.corpus_version} (snapshot ${corpus.snapshot_date ?? "unknown"})`,
        value: "current",
        current: true,
      },
    ];
  }

  private rowFor(slug: string): Row | undefined {
    return this.query<Row>(
      "SELECT href, article_number, title_pt, title_en, title_section, text_pt, text_en, html_pt, html_en FROM sections WHERE href = ? LIMIT 1",
      [slug],
      "section table",
    )[0];
  }

  /** The slug for an Article citation when the snapshot has it ('Art. 6' → 'art6'), else null. */
  async resolveSectionHref(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<string | null> {
    const slug = inpiBrSlug(text(500).parse(citation));
    await this.ready(options.signal);
    return slug && this.rowFor(slug) ? slug : null;
  }

  /**
   * One Article by citation ('Art. 6', 'Article 195', 'Artigo 6', 'Art. 195(XI)
   * LPI', 'Art. 229-C'), slug ('art195') or Planalto URL with an '#Art6'
   * anchor. Anything else, or an Article not in the snapshot, raises
   * SECTION_NOT_FOUND, as Python does.
   */
  async getSection(
    citation: string,
    options: { version?: "current"; signal?: AbortSignal } = {},
  ): Promise<InpiBrSection> {
    const value = text(500).parse(citation);
    const version = options.version ?? "current";
    if (version !== "current")
      throw new CorpusError(
        "VERSION_UNAVAILABLE",
        "Only the installed 'current' LPI snapshot is available.",
      );
    const corpus = await this.ready(options.signal);
    const slug = inpiBrSlug(value);
    const row = slug ? this.rowFor(slug) : undefined;
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `Could not find LPI section '${value}'.`,
      );
    if (
      typeof row.text_pt !== "string" ||
      typeof row.html_pt !== "string" ||
      (row.text_en !== null && typeof row.text_en !== "string") ||
      (row.html_en !== null && typeof row.html_en !== "string")
    )
      throw new CorpusError(
        "INVALID_CORPUS",
        "The INPI Brazil statutes section text is not readable.",
      );
    checkCorpusSignal(options.signal);
    return {
      href: row.href,
      article_number: row.article_number,
      title_pt: row.title_pt,
      title_en: row.title_en,
      title_section: row.title_section,
      text_pt: row.text_pt,
      text_en: row.text_en as string | null,
      html_pt: row.html_pt,
      html_en: row.html_en as string | null,
      version,
      result_url: inpiBrResultUrl(row.href),
      provenance: this.provenance(corpus),
    };
  }

  /**
   * Full-text search over the Portuguese and English text and titles. Terms
   * are always quoted as FTS5 text. The default syntax is Python's 'adj'
   * (phrase); 'outline' sorts by Article number.
   */
  async search(options: InpiBrSearchOptions): Promise<InpiBrSearchResponse> {
    const input = searchOptions.parse(options);
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const order =
      input.sort === "outline"
        ? "CAST(substr(s.href, 4) AS INTEGER), s.href"
        : "rank, s.rowid";
    const rows = match
      ? this.query<{
          href: string;
          article_number: string | null;
          title_pt: string | null;
          title_section: string | null;
          snippet: string | null;
          rank: number | null;
        }>(
          `SELECT s.href, s.article_number, s.title_pt, s.title_section, snippet(sections_fts, 3, '<mark>', '</mark>', '…', 40) AS snippet, rank FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ? ORDER BY ${order} LIMIT ? OFFSET ?`,
          [match, input.limit + 1, input.offset],
          "full-text index",
        )
      : [];
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      hits: rows.slice(0, input.limit).map((row) => {
        const label = row.article_number ?? "";
        const title = row.title_pt ?? "";
        return {
          title: label && title ? `${label} — ${title}` : title || label,
          href: row.href,
          article_number: row.article_number,
          path: [row.title_section, row.article_number].filter(
            (part): part is string => Boolean(part),
          ),
          result_url: inpiBrResultUrl(row.href),
          snippet: row.snippet ?? "",
          rank: row.rank ?? null,
        };
      }),
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
    this.count = null;
    this.sha256 = null;
    this.fileSha256 = null;
    this.compression = null;
  }
}

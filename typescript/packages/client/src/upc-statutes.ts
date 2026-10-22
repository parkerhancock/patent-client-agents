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

/** The UPC page that links every consolidated instrument PDF. */
export const UPC_LEGAL_DOCUMENTS_URL =
  "https://www.unifiedpatentcourt.org/en/court/legal-documents";
const SOURCE_NAME = "Unified Patent Court";
const LABEL = "UPC statutes";
const ENV_PREFIX = "UPC_STATUTES";

/** Python's alias table: short names and common phrases to the stored key. */
export const UPC_INSTRUMENT_ALIASES: Readonly<Record<string, string>> = {
  upca: "upca",
  agreement: "upca",
  // The Statute is Annex I to the UPCA, in the same source PDF.
  statute: "upca",
  "annex i": "upca",
  rop: "rop",
  rules: "rop",
  "rules of procedure": "rop",
  fees: "fees",
  "court fees": "fees",
  "table of court fees": "fees",
  coc: "coc",
  "code of conduct": "coc",
};

/** Stored instrument key for a key or alias; unknown names pass through lowercased. */
export function resolveUpcInstrument(name: string): string {
  const key = name.trim().toLowerCase();
  return UPC_INSTRUMENT_ALIASES[key] ?? key;
}

const text = (max: number) =>
  z
    .string()
    .trim()
    .min(1)
    .max(max)
    .refine((value) => !value.includes("\0"), "Values must not contain NUL.");
const language = z
  .string()
  .trim()
  .toLowerCase()
  .regex(/^[a-z]{2}$/, "Use an ISO 639-1 code such as 'en', 'fr' or 'de'.");
const searchOptions = z.object({
  query: z
    .string()
    .max(8192)
    .refine((value) => !value.includes("\0"), "Queries must not contain NUL."),
  instrument: text(200).nullish(),
  /** null searches every language. */
  language: language.nullable().default("en"),
  syntax: z.enum(["adj", "exact", "and", "or"]).default("and"),
  sort: z.enum(["relevance", "instrument"]).default("relevance"),
  limit: z.number().int().min(1).max(100).default(10),
  offset: z.number().int().min(0).safe().default(0),
});
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);

export interface UpcStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also UPC_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also UPC_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
  /** Largest instrument text returned, in UTF-8 bytes (default 16 MiB). */
  maxTextBytes?: number;
}
export type UpcStatutesSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};
export interface UpcInstrumentOptions {
  language?: string;
  signal?: AbortSignal;
}

export interface UpcStatutesCorpusStatus {
  available: boolean;
  label: string;
  /** `snapshot <date>`, as Python reports it: the consolidated PDFs carry no version. */
  corpus_version: string;
  schema_version: number | null;
  instrument_count: number | null;
  snapshot_date: string | null;
  corpus_synced_at: string | null;
  artifact_sha256: string | null;
  file_sha256: string | null;
  compression: "none" | "zstd" | null;
  source_url: string;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
/** One (instrument, language) row of the corpus. */
export interface UpcInstrument {
  /** Stored key: 'upca', 'rop', 'fees' or 'coc'. 'statute' is an alias of 'upca'. */
  instrument: string;
  short_name: string;
  title: string;
  language: string;
  /** The official PDF the text was extracted from. */
  source_url: string;
  source_version: string | null;
  pdf_pages: number | null;
}
export interface UpcInstrumentText extends UpcInstrument {
  text: string;
  content_sha256: string;
  corpus_version: string;
  provenance: CorpusProvenance;
}
export interface UpcStatuteSearchHit {
  instrument: string;
  short_name: string;
  language: string;
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: string;
  /** BM25 rank (lower is more relevant). */
  rank: number | null;
}
export interface UpcStatuteSearchResponse {
  query: string;
  hits: UpcStatuteSearchHit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: UpcStatutesCorpusStatus;
}

interface Row {
  instrument: string;
  language: string;
  short_name: string;
  title: string;
  source_url: string;
  source_version: string | null;
  pdf_pages: number | null;
}
const COLUMNS =
  "instrument, language, short_name, title, source_url, source_version, pdf_pages";

/** Only official UPC URLs are reported; spaces in stored PDF names are percent-encoded. */
function officialUrl(value: string): string {
  try {
    const url = new URL(value);
    if (
      url.protocol === "https:" &&
      url.hostname === "www.unifiedpatentcourt.org"
    )
      return url.href;
  } catch {}
  return UPC_LEGAL_DOCUMENTS_URL;
}

function instrument(row: Row): UpcInstrument {
  return {
    instrument: row.instrument,
    short_name: row.short_name,
    title: row.title,
    language: row.language,
    source_url: officialUrl(row.source_url),
    source_version: row.source_version,
    pdf_pages: row.pdf_pages,
  };
}

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
      "Unsupported UPC statutes corpus schema; the supported version is 1.",
    );
  db.all(`SELECT ${COLUMNS}, text FROM instruments LIMIT 0`);
  const fts = db.get<{ sql: string }>(
    "SELECT sql FROM sqlite_master WHERE name = ? AND type = 'table'",
    ["instruments_fts"],
  );
  const columns = db
    .all<{ name: string }>("PRAGMA table_info(instruments_fts)")
    .map((row) => row.name);
  const count = db.get<{ count: number }>(
    "SELECT count(*) AS count FROM instruments",
  )?.count;
  if (
    !fts ||
    !/\bUSING\s+fts5\s*\(/i.test(fts.sql) ||
    !/\bcontent\s*=\s*['"]instruments['"]/i.test(fts.sql) ||
    !/\bcontent_rowid\s*=\s*['"]rowid['"]/i.test(fts.sql) ||
    JSON.stringify(columns) !==
      JSON.stringify(["short_name", "title", "text"]) ||
    count === undefined
  )
    throw new Error();
  return { metadata, count };
}

/**
 * Read-only reader for the UPC statutes snapshot (UPCA with the Statute as
 * Annex I, Rules of Procedure, Table of Court Fees) in English, French and
 * German. It never downloads or rebuilds the corpus.
 */
export class UpcStatutesClient {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private metadata: Record<string, string> = {};
  private count: number | null = null;
  private sha256: string | null = null;
  private fileSha256: string | null = null;
  private compression: "none" | "zstd" | null = null;
  private readonly path: string;
  private readonly source: UpcStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;
  private readonly maxTextBytes: number;

  constructor(options: UpcStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("upc_statutes.db") ??
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
        `The UPC statutes ${what} is not readable.`,
      );
    }
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): UpcStatutesCorpusStatus {
    const metadata = { ...this.metadata };
    const synced = corpusTimestamp(metadata.snapshot_date);
    return {
      available,
      label: LABEL,
      corpus_version: synced ? `snapshot ${metadata.snapshot_date}` : "unknown",
      schema_version: metadata.schema_version
        ? Number(metadata.schema_version)
        : null,
      instrument_count: this.count,
      snapshot_date: metadata.snapshot_date ?? null,
      corpus_synced_at: synced,
      artifact_sha256: this.sha256,
      file_sha256: this.fileSha256,
      compression: this.compression,
      source_url: UPC_LEGAL_DOCUMENTS_URL,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(
    corpus: UpcStatutesCorpusStatus,
    sourceUrl: string,
  ): CorpusProvenance {
    return {
      source_url: sourceUrl,
      source_name: SOURCE_NAME,
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
  async getCorpusStatus(): Promise<UpcStatutesCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  /** Installed instruments, optionally for one language, ordered by key. */
  async listInstruments(
    options: { language?: string | null; signal?: AbortSignal } = {},
  ): Promise<{
    instruments: UpcInstrument[];
    provenance: CorpusProvenance;
    corpus: UpcStatutesCorpusStatus;
  }> {
    const lang =
      options.language == null ? null : language.parse(options.language);
    const corpus = await this.ready(options.signal);
    const rows = lang
      ? this.query<Row>(
          `SELECT ${COLUMNS} FROM instruments WHERE language = ? ORDER BY instrument`,
          [lang],
          "instrument table",
        )
      : this.query<Row>(
          `SELECT ${COLUMNS} FROM instruments ORDER BY instrument, language`,
          [],
          "instrument table",
        );
    return {
      instruments: rows.map(instrument),
      provenance: this.provenance(corpus, UPC_LEGAL_DOCUMENTS_URL),
      corpus,
    };
  }

  /** Full plain text of one instrument, or null when that key/language is not installed. */
  async getInstrument(
    name: string,
    options: UpcInstrumentOptions = {},
  ): Promise<UpcInstrumentText | null> {
    const key = resolveUpcInstrument(text(200).parse(name));
    const lang = language.parse(options.language ?? "en");
    const corpus = await this.ready(options.signal);
    const row = this.query<Row & { text: unknown }>(
      `SELECT ${COLUMNS}, text FROM instruments WHERE instrument = ? AND language = ? LIMIT 1`,
      [key, lang],
      "instrument table",
    )[0];
    if (!row) return null;
    const body = row.text;
    if (typeof body !== "string")
      throw new CorpusError(
        "INVALID_CORPUS",
        "The UPC statutes instrument text is not readable.",
      );
    if (byteLength(body) > this.maxTextBytes)
      throw new CorpusError(
        "SECTION_TOO_LARGE",
        "UPC instrument text exceeds the configured decoded-byte limit.",
      );
    checkCorpusSignal(options.signal);
    const meta = instrument(row);
    return {
      ...meta,
      text: body,
      content_sha256: await sha256Hex(new TextEncoder().encode(body)),
      corpus_version: corpus.corpus_version,
      provenance: this.provenance(corpus, meta.source_url),
    };
  }

  /**
   * Full-text search over every installed instrument. Terms are always
   * quoted as FTS5 text, so caller input never runs as MATCH syntax.
   */
  async search(
    options: UpcStatutesSearchOptions,
  ): Promise<UpcStatuteSearchResponse> {
    const input = searchOptions.parse(options);
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const filters: string[] = [];
    const bind: (string | number)[] = [match];
    if (input.instrument) {
      filters.push("i.instrument = ?");
      bind.push(resolveUpcInstrument(input.instrument));
    }
    if (input.language) {
      filters.push("i.language = ?");
      bind.push(input.language);
    }
    const order =
      input.sort === "instrument"
        ? "i.instrument, i.language"
        : "rank, i.rowid";
    const rows = match
      ? this.query<UpcStatuteSearchHit>(
          `SELECT i.instrument, i.language, i.short_name, snippet(instruments_fts, 2, '<mark>', '</mark>', '…', 40) AS snippet, rank FROM instruments_fts JOIN instruments i ON i.rowid = instruments_fts.rowid WHERE instruments_fts MATCH ?${filters.map((filter) => ` AND ${filter}`).join("")} ORDER BY ${order} LIMIT ? OFFSET ?`,
          [...bind, input.limit + 1, input.offset],
          "full-text index",
        )
      : [];
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      hits: rows.slice(0, input.limit).map((row) => ({
        instrument: row.instrument,
        short_name: row.short_name,
        language: row.language,
        snippet: row.snippet ?? "",
        rank: row.rank ?? null,
      })),
      has_more: rows.length > input.limit,
      offset: input.offset,
      limit: input.limit,
      provenance: this.provenance(corpus, UPC_LEGAL_DOCUMENTS_URL),
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

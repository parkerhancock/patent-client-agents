import { z } from "zod";
import {
  CorpusError,
  checkCorpusSignal,
  corpusTimestamp,
  outlineFtsQuery,
} from "./corpus/outline.js";
import type { CorpusProvenance } from "./models.js";
import { openBuiltDatabase, type SnapshotDatabase } from "./runtime/sqlite.js";
import {
  TW_TRADE_SECRETS_ARTICLES,
  TW_TRADE_SECRETS_SOURCE,
} from "./tw-trade-secrets-data.js";

export { TW_TRADE_SECRETS_ARTICLES, TW_TRADE_SECRETS_SOURCE };
/** The official English translation the bundled text was taken from. */
export const TW_TRADE_SECRETS_URL = TW_TRADE_SECRETS_SOURCE.source_url;
const SOURCE_NAME = "Taiwan — Trade Secrets Act (EN translation)";
const LABEL = "TW Trade Secrets";
const SNAPSHOT_DATE = TW_TRADE_SECRETS_SOURCE.retrieved_at.slice(0, 10);
/** Python's label format, `snapshot-<date>`; the date is the retrieval date of the bundled text. */
const CORPUS_VERSION = `snapshot-${SNAPSHOT_DATE}`;

const STATUTE = String.raw`(?:the\s+)?(?:taiwan(?:ese)?\s+|r\.?o\.?c\.?\s+)?(?:trade\s+secrets?\s+act|act|tsa)`;
const CITATION = new RegExp(
  String.raw`^(?:${STATUTE}\s*,?\s*)?(?:(?:art(?:icle)?|sec(?:tion)?|s|§)\s*\.?\s*)?([0-9]+(?:-[0-9]+)?)(?:\s*,?\s*(?:of\s+)?${STATUTE})?$`,
  "i",
);

/**
 * Article number for a free-text citation: 'Art. 2 Trade Secrets Act',
 * 'Article 13-1', 'Section 13 of the Trade Secrets Act', 'Art.13', '§ 13',
 * 'Trade Secrets Act Art. 10' or a bare '13-1'. Throws on anything else.
 */
export function parseTwTradeSecretsCitation(citation: string): string {
  const clean = citation
    .trim()
    .replace(/\s+/g, " ")
    .replace(/(\d)\s*[-\u2010-\u2015\u2212]\s*(\d)/g, "$1-$2");
  const match = CITATION.exec(clean);
  if (!match?.[1])
    throw new CorpusError(
      "SECTION_NOT_FOUND",
      `Could not parse citation '${citation}'; expected e.g. 'Art. 2 Trade Secrets Act'.`,
    );
  return match[1];
}

const searchOptions = z.object({
  query: z
    .string()
    .max(8192)
    .refine((value) => !value.includes("\0"), "Queries must not contain NUL."),
  syntax: z.enum(["adj", "exact", "and", "or"]).default("and"),
  sort: z.enum(["relevance", "outline"]).default("relevance"),
  limit: z.number().int().min(1).max(100).default(10),
  offset: z.number().int().min(0).safe().default(0),
});
export type TwTradeSecretsSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

export interface TwTradeSecretsCorpusStatus {
  available: boolean;
  label: string;
  corpus_version: string;
  schema_version: number;
  section_count: number;
  snapshot_date: string;
  corpus_synced_at: string | null;
  /** Latest amendment date the official page reports for the Act. */
  amended_date: string;
  /** The database's own "last update" date on the page at retrieval. */
  source_last_updated: string | null;
  source_url: string;
  /** SHA-256 of the retrieved page the text was parsed from. */
  html_sha256: string;
  /** The text ships inside the package; there is no artifact file. */
  bundled: true;
  error?: { code: string; message: string };
}
export interface TwTradeSecretsSection {
  /** Article number as published: '2', '13', '13-1'. */
  section: string;
  /** Always null: the official translation has no article captions. Kept for Python's shape. */
  title: null;
  text: string;
  amended_date: string;
  source_url: string;
  corpus_version: string;
  provenance: CorpusProvenance;
}
export interface TwTradeSecretsSearchHit {
  section: string;
  title: null;
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: string;
  /** BM25 rank (lower is more relevant). */
  rank: number | null;
}
export interface TwTradeSecretsSearchResponse {
  query: string;
  hits: TwTradeSecretsSearchHit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: TwTradeSecretsCorpusStatus;
}

/** Python's schema, without the always-null title column. */
const DDL = [
  "CREATE TABLE sections (rowid INTEGER PRIMARY KEY, section TEXT UNIQUE NOT NULL, text TEXT NOT NULL)",
  "CREATE VIRTUAL TABLE sections_fts USING fts5(section, text, content='sections', content_rowid='rowid', tokenize='porter unicode61')",
];

/**
 * Read-only reader for the Taiwan Trade Secrets Act (營業秘密法) in the
 * official English translation. The 25 Articles ship inside the package and
 * are indexed into an in-memory SQLite/FTS5 database on first use, so no
 * corpus file, download or environment variable is involved.
 */
export class TwTradeSecretsClient {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;

  private async open() {
    if (this.db) return;
    this.opening ??= (async (generation: number) => {
      const db = await openBuiltDatabase([
        ...DDL.map((sql) => ({ sql })),
        ...TW_TRADE_SECRETS_ARTICLES.map((article, index) => ({
          sql: "INSERT INTO sections (rowid, section, text) VALUES (?, ?, ?)",
          bind: [index + 1, article.section, article.text],
        })),
        {
          sql: "INSERT INTO sections_fts (sections_fts) VALUES ('rebuild')",
        },
      ]);
      if (generation !== this.generation) {
        db.close();
        throw new CorpusError(
          "ABORTED",
          "The corpus was closed while opening.",
        );
      }
      this.db = db;
    })(this.generation).finally(() => {
      this.opening = undefined;
    });
    await this.opening;
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): TwTradeSecretsCorpusStatus {
    return {
      available,
      label: LABEL,
      corpus_version: CORPUS_VERSION,
      schema_version: 1,
      section_count: TW_TRADE_SECRETS_ARTICLES.length,
      snapshot_date: SNAPSHOT_DATE,
      corpus_synced_at: corpusTimestamp(TW_TRADE_SECRETS_SOURCE.retrieved_at),
      amended_date: TW_TRADE_SECRETS_SOURCE.amended_date,
      source_last_updated: TW_TRADE_SECRETS_SOURCE.source_last_updated,
      source_url: TW_TRADE_SECRETS_URL,
      html_sha256: TW_TRADE_SECRETS_SOURCE.html_sha256,
      bundled: true,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(): CorpusProvenance {
    const synced = corpusTimestamp(TW_TRADE_SECRETS_SOURCE.retrieved_at);
    return {
      source_url: TW_TRADE_SECRETS_URL,
      source_name: SOURCE_NAME,
      retrieved_at: synced,
      accessed_at: new Date().toISOString(),
      cache_hit: true,
      corpus_synced_at: synced,
      corpus_version: CORPUS_VERSION,
    };
  }

  private async ready(signal?: AbortSignal): Promise<SnapshotDatabase> {
    checkCorpusSignal(signal);
    await this.open();
    checkCorpusSignal(signal);
    if (!this.db) throw new CorpusError("ABORTED", "The corpus was closed.");
    return this.db;
  }

  /** Snapshot identity and freshness; reports rather than throws when the index cannot be built. */
  async getCorpusStatus(): Promise<TwTradeSecretsCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (error instanceof CorpusError) return this.status(false, error);
      return this.status(
        false,
        new CorpusError(
          "CORPUS_UNAVAILABLE",
          "The bundled TW Trade Secrets index could not be built.",
        ),
      );
    }
  }

  /**
   * One Article by number or citation ('13-1', 'Art. 2 Trade Secrets Act').
   * Returns null for a well-formed citation of an Article that does not exist;
   * throws CorpusError SECTION_NOT_FOUND for an unparseable citation.
   */
  async getSection(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<TwTradeSecretsSection | null> {
    const section = parseTwTradeSecretsCitation(citation);
    checkCorpusSignal(options.signal);
    const article = TW_TRADE_SECRETS_ARTICLES.find(
      (row) => row.section === section,
    );
    if (!article) return null;
    return {
      section: article.section,
      title: null,
      text: article.text,
      amended_date: TW_TRADE_SECRETS_SOURCE.amended_date,
      source_url: TW_TRADE_SECRETS_URL,
      corpus_version: CORPUS_VERSION,
      provenance: this.provenance(),
    };
  }

  /**
   * Full-text search (porter-stemmed, BM25-ranked). Every term is quoted as
   * FTS5 text, so caller input never runs as MATCH syntax. 'outline' sort is
   * statutory order (2 before 10, 13 before 13-1 before 14).
   */
  async search(
    options: TwTradeSecretsSearchOptions,
  ): Promise<TwTradeSecretsSearchResponse> {
    const input = searchOptions.parse(options);
    const db = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const order = input.sort === "outline" ? "s.rowid" : "rank, s.rowid";
    const rows = match
      ? db.all<{ section: string; snippet: string | null; rank: number }>(
          `SELECT s.section, snippet(sections_fts, 1, '<mark>', '</mark>', '…', 40) AS snippet, rank FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ? ORDER BY ${order} LIMIT ? OFFSET ?`,
          [match, input.limit + 1, input.offset],
        )
      : [];
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      hits: rows.slice(0, input.limit).map((row) => ({
        section: row.section,
        title: null,
        snippet: row.snippet ?? "",
        rank: row.rank ?? null,
      })),
      has_more: rows.length > input.limit,
      offset: input.offset,
      limit: input.limit,
      provenance: this.provenance(),
      corpus: this.status(true),
    };
  }

  close() {
    this.generation++;
    this.db?.close();
    this.db = undefined;
  }
}

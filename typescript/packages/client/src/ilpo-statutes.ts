import { z } from "zod";
import { defaultCorpusPath } from "#files";
import {
  CorpusError,
  checkCorpusSignal,
  corpusTimestamp,
  openCorpusSnapshot,
  outlineFtsQuery,
} from "./corpus/outline.js";
import { type CorpusProvenance, CorpusProvenanceSchema } from "./models.js";
import { env } from "./runtime/env.js";
import type { SnapshotDatabase } from "./runtime/sqlite.js";

/**
 * Reader for the ILPO Israel statutes corpus: the English translations of the
 * Patents Law 5727-1967, Trade Marks Ordinance [New Version] 5732-1972,
 * Designs Law 5777-2017, Copyright Act 5768-2007 and Commercial Torts Law
 * 5759-1999 (Israel's standalone trade-secret statute) that WIPO Lex
 * publishes. The SQLite/FTS5 snapshot is built by
 * scripts/build-ilpo-statutes-corpus.ts; scripts/ilpo-statutes-sources.json
 * lists each PDF, its retrieval time and hash.
 */
export const ILPO_STATUTES_SOURCE_URL =
  "https://www.wipo.int/wipolex/en/profile.jsp?code=IL";
export const ILPO_STATUTES_SOURCE_NAME = "ILPO Israel — Statutes (WIPO Lex)";
const LABEL = "ILPO statutes";
const ENV_PREFIX = "ILPO_STATUTES";

/** The five statute keys, in the order the corpus lists them. */
export const ILPO_STATUTE_KEYS = [
  "patents",
  "trademarks",
  "designs",
  "copyright",
  "commercial_torts",
] as const;
export type IlpoStatuteKey = (typeof ILPO_STATUTE_KEYS)[number];

/**
 * Python's alias table: names lawyers type, to the statute key. "Trade
 * secret(s)" maps to the Commercial Torts Law, which governs them.
 */
export const ILPO_STATUTE_ALIASES: Readonly<Record<string, string>> = {
  patents: "patents",
  "patents law": "patents",
  patent: "patents",
  "patent law": "patents",
  trademarks: "trademarks",
  trademark: "trademarks",
  "trade marks": "trademarks",
  "trade mark": "trademarks",
  tm: "trademarks",
  "trade marks ordinance": "trademarks",
  "trademarks ordinance": "trademarks",
  designs: "designs",
  design: "designs",
  "designs law": "designs",
  copyright: "copyright",
  "copyright act": "copyright",
  "copyright law": "copyright",
  "commercial torts": "commercial_torts",
  commercial_torts: "commercial_torts",
  "commercial torts law": "commercial_torts",
  "trade secret": "commercial_torts",
  "trade secrets": "commercial_torts",
};

/** Statute key for a name or alias; unknown names pass through lowercased, as in Python. */
export function resolveIlpoStatute(name: string): string {
  const key = name.trim().toLowerCase().replace(/\s+/g, " ");
  return ILPO_STATUTE_ALIASES[key] ?? key;
}

const NUMBER = String.raw`\d{1,4}(?:[A-Za-z]{1,2}\d?)?`;
const UNIT = String.raw`(?:section|sec\.?|s\.|article|art\.?|§+)`;
const FORWARD = new RegExp(
  String.raw`^\s*(?:${UNIT}\s*)?(?<num>${NUMBER})(?:\s*\([0-9a-zA-Z]+\))*\s+(?:of\s+(?:the\s+)?)?(?<statute>.+?)\s*$`,
  "i",
);
const REVERSE = new RegExp(
  String.raw`^\s*(?:the\s+)?(?<statute>.+?)\s*,?\s+${UNIT}\s*(?<num>${NUMBER})(?:\s*\([0-9a-zA-Z]+\))*\s*$`,
  "i",
);

/**
 * Parse a citation into a statute key and section number: 'Section 3 Patents
 * Law', 'Article 6 Commercial Torts Law', 'Patents Law §3', 'Section 6(b)
 * Commercial Torts Law', 'Section 56D1 Trade Marks Ordinance'. Subsection
 * markers are dropped (the whole section is returned) and letter suffixes
 * uppercased. Null when the shape or the statute name is not recognized, as
 * in Python.
 */
export function parseIlpoCitation(
  citation: string,
): { statute: IlpoStatuteKey; section_number: string } | null {
  const cleaned = citation.trim();
  if (!cleaned) return null;
  for (const pattern of [FORWARD, REVERSE]) {
    const match = pattern.exec(cleaned);
    const num = match?.groups?.num;
    const name = match?.groups?.statute;
    if (!num || !name) continue;
    const statute = resolveIlpoStatute(
      name.replace(/,?\s*\d{4}(-\d{4})?$/, ""),
    );
    if ((ILPO_STATUTE_KEYS as readonly string[]).includes(statute))
      return {
        statute: statute as IlpoStatuteKey,
        section_number: num.toUpperCase(),
      };
  }
  return null;
}

/** One statute as the corpus carries it, with the WIPO Lex source it was built from. */
export const IlpoStatuteSchema = z.object({
  statute: z.string(),
  section_count: z.number().int(),
  /** The WIPO Lex legislation page. */
  source_url: z.string().nullable(),
  short_name: z.string().nullable(),
  title: z.string().nullable(),
  /** WIPO Lex's description: year of version, dates, type. */
  version: z.string().nullable(),
  /** The English PDF the sections were parsed from. */
  pdf_url: z.string().nullable(),
  pdf_sha256: z.string().nullable(),
  retrieved_at: z.string().nullable(),
});
export type IlpoStatute = z.infer<typeof IlpoStatuteSchema>;

/** One section of an Israeli IP statute. */
export const IlpoSectionSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  /** Citation-ready label, e.g. 'Section 6 Commercial Torts Law'. */
  section_label: z.string(),
  /** The heading printed beside the section, when there is one. */
  title: z.string().nullable(),
  /** One paragraph per line; amendment notes from the margin close the text in brackets. */
  text: z.string(),
  source_url: z.string().nullable(),
  provenance: CorpusProvenanceSchema,
});
export type IlpoSection = z.infer<typeof IlpoSectionSchema>;

export const IlpoSearchHitSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  section_label: z.string(),
  title: z.string().nullable(),
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: z.string(),
  /** BM25 rank (lower is more relevant) with sort='relevance'. */
  rank: z.number().nullable(),
});
export type IlpoSearchHit = z.infer<typeof IlpoSearchHitSchema>;

export interface IlpoStatutesCorpusStatus {
  available: boolean;
  label: string;
  /** source_version when recorded, else `snapshot-<date>`. */
  corpus_version: string;
  schema_version: number | null;
  section_count: number | null;
  snapshot_date: string | null;
  corpus_synced_at: string | null;
  artifact_sha256: string | null;
  file_sha256: string | null;
  compression: "none" | "zstd" | null;
  source_url: string;
  /** Per-statute source and version, or null for a corpus built without them. */
  statutes: IlpoStatute[] | null;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
export interface IlpoSearchResponse {
  query: string;
  /** The resolved statute filter, or null for all five. */
  statute: string | null;
  hits: IlpoSearchHit[];
  page: number;
  per_page: number;
  has_more: boolean;
  provenance: CorpusProvenance;
  corpus: IlpoStatutesCorpusStatus;
}
export interface IlpoCorpusMeta {
  schema_version: number;
  snapshot_date: string | null;
  source_version: string | null;
  section_count: number;
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
  statute: text(200).nullish(),
  syntax: z.enum(["adj", "exact", "and", "or"]).default("and"),
  sort: z.enum(["relevance", "outline"]).default("relevance"),
  per_page: z.number().int().min(1).max(100).default(10),
  page: z.number().int().min(1).max(100_000).default(1),
});
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);

export interface IlpoStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also ILPO_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also ILPO_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type IlpoStatutesSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

const statuteMeta = z.object({
  statute: z.string(),
  short_name: z.string(),
  title: z.string(),
  wipo_summary: z.string().nullable(),
  details_url: z.string(),
  pdf_url: z.string(),
  pdf_sha256: z.string(),
  retrieved_at: z.string(),
});
/** Meta `statutes` when present and well formed; seed builds have none. */
function parseStatutes(value: string | undefined) {
  if (!value) return null;
  try {
    return z.array(statuteMeta).parse(JSON.parse(value));
  } catch {
    return null;
  }
}

interface Row {
  statute: string;
  section_number: string;
  section_label: string;
  title: string | null;
  text: unknown;
  source_url: string | null;
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
      "Unsupported ILPO statutes corpus schema; the supported version is 1.",
    );
  db.all(
    "SELECT statute, section_number, section_label, title, text, source_url FROM sections LIMIT 0",
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
    JSON.stringify(columns) !==
      JSON.stringify(["statute", "section_label", "title", "text"]) ||
    count === undefined
  )
    throw new Error();
  return { metadata, count };
}

/** Outline order: statute, then numeric section with its letter suffix ("2" < "10" < "10A"). */
const OUTLINE_ORDER =
  "s.statute, CAST(s.section_number AS INTEGER), length(s.section_number), s.section_number";

/**
 * Read-only reader for the ILPO Israel statutes snapshot. It never downloads
 * or rebuilds the corpus. Lookups that find nothing return null, as Python's
 * do.
 */
export class IlpoStatutesClient {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private metadata: Record<string, string> = {};
  private statuteInfo: z.infer<typeof statuteMeta>[] | null = null;
  private count: number | null = null;
  private sha256: string | null = null;
  private fileSha256: string | null = null;
  private compression: "none" | "zstd" | null = null;
  private readonly path: string;
  private readonly source: IlpoStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: IlpoStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("ilpo_statutes.db") ??
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
      this.statuteInfo = parseStatutes(snapshot.value.metadata.statutes);
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
        `The ILPO statutes ${what} is not readable.`,
      );
    }
  }

  private statuteList(): IlpoStatute[] {
    const counts = this.db
      ? this.query<{
          statute: string;
          section_count: number;
          source_url: string | null;
        }>(
          "SELECT statute, COUNT(*) AS section_count, MIN(source_url) AS source_url FROM sections GROUP BY statute",
          [],
          "section table",
        )
      : [];
    const order = (key: string) => {
      const index = (ILPO_STATUTE_KEYS as readonly string[]).indexOf(key);
      return index < 0 ? ILPO_STATUTE_KEYS.length : index;
    };
    return counts
      .sort((a, b) => order(a.statute) - order(b.statute))
      .map((row) => {
        const info = this.statuteInfo?.find(
          (item) => item.statute === row.statute,
        );
        return {
          statute: row.statute,
          section_count: row.section_count,
          source_url: info?.details_url ?? row.source_url,
          short_name: info?.short_name ?? null,
          title: info?.title ?? null,
          version: info?.wipo_summary ?? null,
          pdf_url: info?.pdf_url ?? null,
          pdf_sha256: info?.pdf_sha256 ?? null,
          retrieved_at: info?.retrieved_at ?? null,
        };
      });
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): IlpoStatutesCorpusStatus {
    const metadata = { ...this.metadata };
    const snapshot = metadata.snapshot_date;
    const explicit = metadata.source_version;
    return {
      available,
      label: LABEL,
      corpus_version:
        explicit && explicit !== "current"
          ? explicit
          : snapshot
            ? `snapshot-${snapshot}`
            : "unknown",
      schema_version: metadata.schema_version
        ? Number(metadata.schema_version)
        : null,
      section_count: this.count,
      snapshot_date: snapshot ?? null,
      corpus_synced_at: corpusTimestamp(snapshot),
      artifact_sha256: this.sha256,
      file_sha256: this.fileSha256,
      compression: this.compression,
      source_url: ILPO_STATUTES_SOURCE_URL,
      statutes: available && this.statuteInfo ? this.statuteList() : null,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: IlpoStatutesCorpusStatus): CorpusProvenance {
    return {
      source_url: ILPO_STATUTES_SOURCE_URL,
      source_name: ILPO_STATUTES_SOURCE_NAME,
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
  async getCorpusStatus(): Promise<IlpoStatutesCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  /** Python's meta(): schema version, snapshot date, source version and row count. */
  async meta(options: { signal?: AbortSignal } = {}): Promise<IlpoCorpusMeta> {
    await this.ready(options.signal);
    return {
      schema_version: Number(this.metadata.schema_version ?? 0),
      snapshot_date: this.metadata.snapshot_date ?? null,
      source_version: this.metadata.source_version ?? null,
      section_count: Number(this.metadata.section_count ?? 0),
    };
  }

  /** The statutes in the snapshot with their section counts and sources. */
  async listStatutes(
    options: { signal?: AbortSignal } = {},
  ): Promise<IlpoStatute[]> {
    await this.ready(options.signal);
    return this.statuteList();
  }

  /** One section by statute (key or alias) and number; null when absent. */
  async getSection(
    statute: string,
    sectionNumber: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<IlpoSection | null> {
    const key = resolveIlpoStatute(text(200).parse(statute));
    const number = text(20).parse(sectionNumber).toUpperCase();
    const corpus = await this.ready(options.signal);
    const row = this.query<Row>(
      "SELECT statute, section_number, section_label, title, text, source_url FROM sections WHERE statute = ? AND section_number = ? LIMIT 1",
      [key, number],
      "section table",
    )[0];
    checkCorpusSignal(options.signal);
    if (!row) return null;
    if (typeof row.text !== "string")
      throw new CorpusError(
        "INVALID_CORPUS",
        "The ILPO statutes section text is not readable.",
      );
    return {
      statute: row.statute,
      section_number: row.section_number,
      section_label: row.section_label,
      title: row.title,
      text: row.text,
      source_url: row.source_url,
      provenance: this.provenance(corpus),
    };
  }

  /** One section by citation ('Section 6 Commercial Torts Law'); null when unparseable or absent. */
  async getSectionByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<IlpoSection | null> {
    const parsed = parseIlpoCitation(text(500).parse(citation));
    if (!parsed) return null;
    return this.getSection(parsed.statute, parsed.section_number, options);
  }

  /**
   * Full-text search over all five statutes, or one with `statute`. Terms are
   * always quoted as FTS5 text, so caller input never runs as MATCH syntax.
   */
  async search(
    options: IlpoStatutesSearchOptions,
  ): Promise<IlpoSearchResponse> {
    const input = searchOptions.parse(options);
    const statute = input.statute ? resolveIlpoStatute(input.statute) : null;
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const bind: (string | number)[] = [match];
    if (statute) bind.push(statute);
    // BM25 ties fall back to row order so pages are stable.
    const order = input.sort === "outline" ? OUTLINE_ORDER : "rank, s.rowid";
    const rows = match
      ? this.query<IlpoSearchHit>(
          `SELECT s.statute, s.section_number, s.section_label, s.title, snippet(sections_fts, 3, '<mark>', '</mark>', '…', 40) AS snippet, rank FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ?${statute ? " AND s.statute = ?" : ""} ORDER BY ${order} LIMIT ? OFFSET ?`,
          [...bind, input.per_page + 1, (input.page - 1) * input.per_page],
          "full-text index",
        )
      : [];
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      statute,
      hits: rows.slice(0, input.per_page).map((row) => ({
        statute: row.statute,
        section_number: row.section_number,
        section_label: row.section_label,
        title: row.title ?? null,
        snippet: row.snippet ?? "",
        rank: input.sort === "relevance" ? (row.rank ?? null) : null,
      })),
      page: input.page,
      per_page: input.per_page,
      has_more: rows.length > input.per_page,
      provenance: this.provenance(corpus),
      corpus,
    };
  }

  close() {
    this.generation++;
    this.db?.close();
    this.db = undefined;
    this.metadata = {};
    this.statuteInfo = null;
    this.count = null;
    this.sha256 = null;
    this.fileSha256 = null;
    this.compression = null;
  }
}

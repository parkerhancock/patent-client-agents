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
 * Reader for the Thailand IP statutes corpus: the English translations of
 * the Patent Act B.E. 2522 (1979), Trademark Act B.E. 2534 (1991), Copyright
 * Act B.E. 2537 (1994) and Trade Secrets Act B.E. 2545 (2002), each as
 * amended, that WIPO Lex publishes. They are unofficial translations; the
 * Thai text in the Government Gazette controls. The SQLite/FTS5 snapshot is
 * built by scripts/build-thai-dip-statutes-corpus.ts;
 * scripts/thai-dip-statutes-sources.json lists each PDF, its version,
 * retrieval time and hash.
 */
export const THAI_DIP_STATUTES_SOURCE_URL =
  "https://www.wipo.int/wipolex/en/members/profile/TH";
export const THAI_DIP_STATUTES_SOURCE_NAME =
  "Thailand DIP — IP statutes in English (WIPO Lex)";
/** Every row and status carries this; the translations have no legal force. */
export const THAI_DIP_STATUTES_AUTHORITY =
  "Unofficial English translations. The Thai text published in the Government Gazette is the only authoritative version.";
const LABEL = "Thailand IP statutes";
const ENV_PREFIX = "THAI_DIP_STATUTES";

/** The four statute keys, in the order the corpus lists them. */
export const THAI_DIP_STATUTE_KEYS = [
  "patent",
  "trademark",
  "copyright",
  "trade_secrets",
] as const;
export type ThaiDipStatuteKey = (typeof THAI_DIP_STATUTE_KEYS)[number];

/** Names lawyers type, to the statute key. */
export const THAI_DIP_STATUTE_ALIASES: Readonly<Record<string, string>> = {
  patent: "patent",
  patents: "patent",
  "patent act": "patent",
  "patents act": "patent",
  "patent law": "patent",
  "petty patent": "patent",
  trademark: "trademark",
  trademarks: "trademark",
  "trade mark": "trademark",
  "trade marks": "trademark",
  tm: "trademark",
  "trademark act": "trademark",
  "trade mark act": "trademark",
  "trademarks act": "trademark",
  copyright: "copyright",
  "copyright act": "copyright",
  "copyright law": "copyright",
  trade_secrets: "trade_secrets",
  "trade secret": "trade_secrets",
  "trade secrets": "trade_secrets",
  "trade secrets act": "trade_secrets",
  "trade secret act": "trade_secrets",
};

/** Statute key for a name or alias; unknown names pass through lowercased and find nothing. */
export function resolveThaiDipStatute(name: string): string {
  const key = name.trim().toLowerCase().replace(/\s+/g, " ");
  return THAI_DIP_STATUTE_ALIASES[key] ?? key;
}

const LATIN = [
  "bis",
  "ter",
  "quater",
  "quinquies",
  "sexies",
  "septies",
  "octies",
  "nonies",
  "decies",
  "undecies",
  "duodecies",
  "quarter",
  "novies",
].join("|");
const NUMBER = String.raw`\d{1,3}(?:\s*(?:${LATIN})\b)?(?:\s*\/\s*\d{1,2})?`;
const UNIT = String.raw`(?:sections?|sec\.?|ss?\.|§+|article|art\.?)`;
const SUBSECTION = String.raw`(?:\s*\([0-9a-zA-Z]{1,4}\))*(?:\s*,?\s*paragraph\s+\w+)?`;
const FORWARD = new RegExp(
  String.raw`^\s*(?:${UNIT}\s*)?(?<num>${NUMBER})${SUBSECTION}\s*,?\s+(?:of\s+(?:the\s+)?)?(?<statute>.+?)\s*$`,
  "i",
);
const REVERSE = new RegExp(
  String.raw`^\s*(?:the\s+)?(?<statute>.+?)\s*,?\s+${UNIT}\s*(?<num>${NUMBER})${SUBSECTION}\s*$`,
  "i",
);

/**
 * Canonical section number as the corpus stores it: "36bis", "28/1",
 * "106quater". Spaces are dropped, the suffix lowercased, and the sources'
 * spellings "quarter" and "novies" read as "quater" and "nonies".
 */
export function normalizeThaiDipSectionNumber(value: string): string {
  return value
    .toLowerCase()
    .replace(/\s+/g, "")
    .replace(/quarter$/, "quater")
    .replace(/novies$/, "nonies");
}

/**
 * Parse a citation into a statute key and section number: 'Section 36
 * Patent Act', 'Patent Act s. 36', 'Section 36 bis Patent Act', 'Section
 * 109/1 Trademark Act', 'Section 6 Trade Secrets Act', 's. 15(5) of the
 * Copyright Act B.E. 2537'. Subsection and paragraph markers are dropped
 * (the whole section is returned). Null when the shape or the act is not
 * recognized.
 */
export function parseThaiDipCitation(
  citation: string,
): { statute: ThaiDipStatuteKey; section_number: string } | null {
  const cleaned = citation.trim();
  if (!cleaned) return null;
  for (const pattern of [FORWARD, REVERSE]) {
    const match = pattern.exec(cleaned);
    const num = match?.groups?.num;
    const name = match?.groups?.statute;
    if (!num || !name) continue;
    const statute = resolveThaiDipStatute(
      name
        .replace(/\s*\(\d{4}\)\s*$/, "")
        .replace(/,?\s*(?:B\.\s?E\.\s*)?\d{4}\s*$/i, ""),
    );
    if ((THAI_DIP_STATUTE_KEYS as readonly string[]).includes(statute))
      return {
        statute: statute as ThaiDipStatuteKey,
        section_number: normalizeThaiDipSectionNumber(num),
      };
  }
  return null;
}

/** One statute as the corpus carries it, with the WIPO Lex source it was built from. */
export const ThaiDipStatuteSchema = z.object({
  statute: z.string(),
  section_count: z.number().int(),
  /** The WIPO Lex legislation page. */
  source_url: z.string().nullable(),
  short_name: z.string().nullable(),
  title: z.string().nullable(),
  /** The amendments the translation covers and who translated it. */
  version: z.string().nullable(),
  /** WIPO Lex's own description: year of version, dates, type. */
  wipo_summary: z.string().nullable(),
  /** The English PDF the sections were parsed from. */
  pdf_url: z.string().nullable(),
  pdf_sha256: z.string().nullable(),
  retrieved_at: z.string().nullable(),
});
export type ThaiDipStatute = z.infer<typeof ThaiDipStatuteSchema>;

/** One section of a Thai IP act. */
export const ThaiDipSectionSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  /** Citation-ready label, e.g. 'Section 36bis Patent Act'. */
  section_label: z.string(),
  /** Always null: the acts print no section headings. */
  title: z.string().nullable(),
  /** One paragraph per line; the amendment footnotes the section cites close the text in brackets. */
  text: z.string(),
  source_url: z.string().nullable(),
  /** The translations are unofficial; the Thai text controls. */
  authority: z.string(),
  provenance: CorpusProvenanceSchema,
});
export type ThaiDipSection = z.infer<typeof ThaiDipSectionSchema>;

export const ThaiDipSearchHitSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  section_label: z.string(),
  title: z.string().nullable(),
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: z.string(),
  /** BM25 rank (lower is more relevant) with sort='relevance'. */
  rank: z.number().nullable(),
});
export type ThaiDipSearchHit = z.infer<typeof ThaiDipSearchHitSchema>;

export interface ThaiDipStatutesCorpusStatus {
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
  statutes: ThaiDipStatute[] | null;
  /** The translations are unofficial; the Thai text controls. */
  authority: string;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
export interface ThaiDipSearchResponse {
  query: string;
  /** The resolved statute filter, or null for all four. */
  statute: string | null;
  hits: ThaiDipSearchHit[];
  page: number;
  per_page: number;
  has_more: boolean;
  provenance: CorpusProvenance;
  corpus: ThaiDipStatutesCorpusStatus;
}
export interface ThaiDipCorpusMeta {
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

export interface ThaiDipStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also THAI_DIP_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also THAI_DIP_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type ThaiDipStatutesSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

const statuteMeta = z.object({
  statute: z.string(),
  short_name: z.string(),
  title: z.string(),
  wipo_summary: z.string().nullable(),
  version_note: z.string(),
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
      "Unsupported Thailand IP statutes corpus schema; the supported version is 1.",
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

/**
 * Outline order: the builder inserts the acts in key order and each act's
 * sections as printed ("36" < "36bis" < "37", "28" < "28/1" < "29"), so
 * row order is outline order.
 */
const OUTLINE_ORDER = "s.rowid";

/**
 * Read-only reader for the Thailand IP statutes snapshot. It never downloads
 * or rebuilds the corpus. Lookups that find nothing return null.
 */
export class ThaiDipStatutesClient {
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
  private readonly source: ThaiDipStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: ThaiDipStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("thai_dip_statutes.db") ??
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
        `The Thailand IP statutes ${what} is not readable.`,
      );
    }
  }

  private statuteList(): ThaiDipStatute[] {
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
      const index = (THAI_DIP_STATUTE_KEYS as readonly string[]).indexOf(key);
      return index < 0 ? THAI_DIP_STATUTE_KEYS.length : index;
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
          version: info?.version_note ?? null,
          wipo_summary: info?.wipo_summary ?? null,
          pdf_url: info?.pdf_url ?? null,
          pdf_sha256: info?.pdf_sha256 ?? null,
          retrieved_at: info?.retrieved_at ?? null,
        };
      });
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): ThaiDipStatutesCorpusStatus {
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
      source_url: THAI_DIP_STATUTES_SOURCE_URL,
      statutes: available && this.statuteInfo ? this.statuteList() : null,
      authority: metadata.authority ?? THAI_DIP_STATUTES_AUTHORITY,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: ThaiDipStatutesCorpusStatus): CorpusProvenance {
    return {
      source_url: THAI_DIP_STATUTES_SOURCE_URL,
      source_name: THAI_DIP_STATUTES_SOURCE_NAME,
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
  async getCorpusStatus(): Promise<ThaiDipStatutesCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  /** Schema version, snapshot date, source version and row count. */
  async meta(
    options: { signal?: AbortSignal } = {},
  ): Promise<ThaiDipCorpusMeta> {
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
  ): Promise<ThaiDipStatute[]> {
    await this.ready(options.signal);
    return this.statuteList();
  }

  /** One section by statute (key or alias) and number; null when absent. */
  async getSection(
    statute: string,
    sectionNumber: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<ThaiDipSection | null> {
    const key = resolveThaiDipStatute(text(200).parse(statute));
    const number = normalizeThaiDipSectionNumber(text(20).parse(sectionNumber));
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
        "The Thailand IP statutes section text is not readable.",
      );
    return {
      statute: row.statute,
      section_number: row.section_number,
      section_label: row.section_label,
      title: row.title,
      text: row.text,
      source_url: row.source_url,
      authority: corpus.authority,
      provenance: this.provenance(corpus),
    };
  }

  /** One section by citation ('Section 36bis Patent Act'); null when unparseable or absent. */
  async getSectionByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<ThaiDipSection | null> {
    const parsed = parseThaiDipCitation(text(500).parse(citation));
    if (!parsed) return null;
    return this.getSection(parsed.statute, parsed.section_number, options);
  }

  /**
   * Full-text search over all four acts, or one with `statute`. Terms are
   * always quoted as FTS5 text, so caller input never runs as MATCH syntax.
   */
  async search(
    options: ThaiDipStatutesSearchOptions,
  ): Promise<ThaiDipSearchResponse> {
    const input = searchOptions.parse(options);
    const statute = input.statute ? resolveThaiDipStatute(input.statute) : null;
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const bind: (string | number)[] = [match];
    if (statute) bind.push(statute);
    // BM25 ties fall back to row order so pages are stable.
    const order = input.sort === "outline" ? OUTLINE_ORDER : "rank, s.rowid";
    const rows = match
      ? this.query<ThaiDipSearchHit>(
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

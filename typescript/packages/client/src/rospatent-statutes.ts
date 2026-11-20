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
 * Reader for the Russian Federation IP statute corpus: Part Four of the Civil
 * Code (Section VII, chapters 69 to 77, articles 1225 onward) in the English
 * translation WIPO Lex publishes. The translation is WIPO's, not an official
 * text; the Russian text controls and the translation may lag later
 * amendments (the status reports both dates). The SQLite/FTS5 snapshot is
 * built by scripts/build-rospatent-statutes-corpus.ts;
 * scripts/rospatent-statutes-sources.json records the PDF, its retrieval time
 * and hash.
 */
export const ROSPATENT_STATUTES_SOURCE_URL =
  "https://www.wipo.int/wipolex/en/legislation/details/22547";
export const ROSPATENT_STATUTES_SOURCE_NAME =
  "Russian Federation — Civil Code, Part Four (WIPO Lex English translation)";
const LABEL = "Rospatent statutes";
const ENV_PREFIX = "ROSPATENT_STATUTES";
/** The one statute key in the corpus. */
export const ROSPATENT_STATUTE = "civil_code";

/** Names for the Civil Code, after punctuation and "Part Four" are removed. */
const CODE_NAMES = new Set([
  "civil code",
  "civil code of russian federation",
  "civil code of russia",
  "russian civil code",
  "russian federation civil code",
  "civil code rf",
  "rf civil code",
  "cc",
  "cc rf",
  "rf cc",
  "ccrf",
  "gk",
  "gk rf",
  "гк",
  "гк рф",
  "гражданский кодекс",
  "гражданский кодекс рф",
  "гражданский кодекс российской федерации",
  "гражданского кодекса",
  "гражданского кодекса рф",
  "гражданского кодекса российской федерации",
]);

/** Whether a name refers to the Civil Code (or its Part Four). */
export function isRospatentCode(name: string): boolean {
  const key = name
    .toLowerCase()
    .replace(/[.,;:()[\]]/g, " ")
    .replace(/\b(?:part|pt)\s+(?:four|4|iv)\b/g, " ")
    .replace(/част[ьи]\s+(?:четвертая|четвертой|4|iv)/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^(?:(?:of|the)\s+)+/, "")
    .replace(/\s+of\s+the\s+/g, " of ");
  return CODE_NAMES.has(key);
}

const NUMBER = String.raw`\d{1,4}(?:\.\d{1,2})?`;
const UNIT = String.raw`(?:articles?|arts?\.?|статья|статьи|ст\.?)`;
/** Item, paragraph or subparagraph markers after the number; the whole article is returned. */
const TAIL = String.raw`(?:\s*\(\s*[0-9a-zа-я.]+\s*\))*(?:\s*,?\s*(?:items?|para(?:graph)?s?\.?|p\.|пп?\.|пункт)\s*\d+(?:\.\d+)?)*`;
/** A leading item reference: "Item 1 of Article 1350", "п. 1 ст. 1350". */
const LEAD = String.raw`(?:(?:items?|para(?:graph)?\.?|p\.|пп?\.|пункт)\s*\d+(?:\.\d+)?\s*,?\s+(?:of\s+)?)?`;
const FORWARD = new RegExp(
  String.raw`^\s*${LEAD}(?:${UNIT}\s*)?(?<num>${NUMBER})${TAIL}(?:\s*,?\s+(?<code>.+?))?\s*$`,
  "iu",
);
const REVERSE = new RegExp(
  String.raw`^\s*(?<code>.+?)\s*,?\s+${UNIT}\s*(?<num>${NUMBER})${TAIL}\s*$`,
  "iu",
);

/**
 * Parse a citation into an article number: 'Article 1350 Civil Code',
 * 'Civil Code Art. 1350(1)', 'Art. 1484 CC RF', 'Article 1231.1', 'Item 1 of
 * Article 1350 of the Civil Code', 'ст. 1484 ГК РФ'. Item and paragraph
 * markers are dropped (the whole article is returned); a dotted number
 * (1231.1) is an inserted article. Null when the shape is not recognized or
 * another statute is named.
 */
export function parseRospatentCitation(
  citation: string,
): { statute: typeof ROSPATENT_STATUTE; section_number: string } | null {
  const cleaned = citation.trim();
  if (!cleaned) return null;
  for (const pattern of [FORWARD, REVERSE]) {
    const match = pattern.exec(cleaned);
    const num = match?.groups?.num;
    if (!num) continue;
    const code = match?.groups?.code;
    // A bare number needs "Article" in front of it.
    if (
      code === undefined &&
      !new RegExp(`^\\s*${LEAD}${UNIT}`, "iu").test(cleaned)
    )
      continue;
    if (code !== undefined && !isRospatentCode(code)) continue;
    return { statute: ROSPATENT_STATUTE, section_number: num };
  }
  return null;
}

/** The WIPO Lex record the corpus was built from. */
export const RospatentLegislationSchema = z.object({
  wipolex_id: z.string(),
  details_url: z.string(),
  wipo_title: z.string(),
  /** WIPO Lex's description: year of version, "Amended up to" date, type. */
  wipo_summary: z.string().nullable(),
  pdf_url: z.string(),
  pdf_last_modified: z.string().nullable(),
  pdf_sha256: z.string(),
  retrieved_at: z.string(),
  /** WIPO Lex's latest record of the Code, whose Russian text may be newer. */
  latest_record_url: z.string(),
  latest_record_summary: z.string().nullable(),
});
export type RospatentLegislation = z.infer<typeof RospatentLegislationSchema>;

/** One article of Part Four of the Civil Code. */
export const RospatentArticleSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  /** Citation-ready label, e.g. 'Article 1350 Civil Code'. */
  section_label: z.string(),
  /** The article heading; null for a repealed article. */
  title: z.string().nullable(),
  /** One paragraph per line; for a repealed article, the repeal note. */
  text: z.string(),
  /** 'Chapter 72. The Patent Law' */
  chapter: z.string(),
  /** The § heading, e.g. '§ 5. Obtaining a Patent', when the chapter has §s. */
  paragraph: z.string().nullable(),
  /** The numbered heading inside a few §s, e.g. '1. The Patent Application, Its Amendment and Revocation'. */
  subparagraph: z.string().nullable(),
  repealed: z.boolean(),
  source_url: z.string().nullable(),
  provenance: CorpusProvenanceSchema,
});
export type RospatentArticle = z.infer<typeof RospatentArticleSchema>;

export const RospatentSearchHitSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  section_label: z.string(),
  title: z.string().nullable(),
  chapter: z.string(),
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: z.string(),
  /** BM25 rank (lower is more relevant) with sort='relevance'. */
  rank: z.number().nullable(),
});
export type RospatentSearchHit = z.infer<typeof RospatentSearchHitSchema>;

export interface RospatentStatutesCorpusStatus {
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
  /** Date the English translation is amended up to, per WIPO Lex. */
  translation_amended_up_to: string | null;
  /** Date WIPO Lex's latest (Russian) text is amended up to. */
  russian_amended_up_to: string | null;
  /** Plain statement of the translation's currency; the Russian text controls. */
  version_note: string | null;
  legislation: RospatentLegislation | null;
  /** Chapters the translation prints only as repealed, without articles. */
  repealed_chapters: { chapter: string; note: string }[];
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
export interface RospatentSearchResponse {
  query: string;
  /** The chapter filter (69 to 77), or null for all of Part Four. */
  chapter: number | null;
  hits: RospatentSearchHit[];
  page: number;
  per_page: number;
  has_more: boolean;
  provenance: CorpusProvenance;
  corpus: RospatentStatutesCorpusStatus;
}
export interface RospatentCorpusMeta {
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
  chapter: z.number().int().min(69).max(77).nullish(),
  syntax: z.enum(["adj", "exact", "and", "or"]).default("and"),
  sort: z.enum(["relevance", "outline"]).default("relevance"),
  per_page: z.number().int().min(1).max(100).default(10),
  page: z.number().int().min(1).max(100_000).default(1),
});
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);

export interface RospatentStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also ROSPATENT_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also ROSPATENT_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type RospatentStatutesSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

function parseJson<T>(value: string | undefined, schema: z.ZodType<T>) {
  if (!value) return null;
  try {
    return schema.parse(JSON.parse(value));
  } catch {
    return null;
  }
}
const repealedChapters = z.array(
  z.object({ chapter: z.string(), note: z.string() }),
);

interface Row {
  statute: string;
  section_number: string;
  section_label: string;
  title: string | null;
  text: unknown;
  source_url: string | null;
  chapter: string;
  paragraph: string | null;
  subparagraph: string | null;
  repealed: number;
}
const COLUMNS =
  "statute, section_number, section_label, title, text, source_url, chapter, paragraph, subparagraph, repealed";

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
      "Unsupported Rospatent statutes corpus schema; the supported version is 1.",
    );
  db.all(`SELECT ${COLUMNS} FROM sections LIMIT 0`);
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

/** Outline order: numeric article, inserted articles after their base ("1231" < "1231.1" < "1232"). */
const OUTLINE_ORDER =
  "CAST(s.section_number AS INTEGER), CAST(substr(s.section_number, instr(s.section_number || '.', '.') + 1) AS INTEGER)";

/**
 * Read-only reader for the Part Four snapshot. It never downloads or rebuilds
 * the corpus. Lookups that find nothing return null.
 */
export class RospatentStatutesClient {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private metadata: Record<string, string> = {};
  private count: number | null = null;
  private sha256: string | null = null;
  private fileSha256: string | null = null;
  private compression: "none" | "zstd" | null = null;
  private readonly path: string;
  private readonly source: RospatentStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: RospatentStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("rospatent_statutes.db") ??
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
        `The Rospatent statutes ${what} is not readable.`,
      );
    }
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): RospatentStatutesCorpusStatus {
    const metadata = { ...this.metadata };
    const snapshot = metadata.snapshot_date;
    const explicit = metadata.source_version;
    const date = (value: string | undefined) =>
      value && value !== "unknown" ? value : null;
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
      source_url: ROSPATENT_STATUTES_SOURCE_URL,
      translation_amended_up_to: date(metadata.translation_amended_up_to),
      russian_amended_up_to: date(metadata.russian_amended_up_to),
      version_note: metadata.version_note ?? null,
      legislation: parseJson(metadata.legislation, RospatentLegislationSchema),
      repealed_chapters:
        parseJson(metadata.repealed_chapters, repealedChapters) ?? [],
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: RospatentStatutesCorpusStatus): CorpusProvenance {
    return {
      source_url: ROSPATENT_STATUTES_SOURCE_URL,
      source_name: ROSPATENT_STATUTES_SOURCE_NAME,
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

  /** Snapshot identity, freshness and translation currency; never throws for an unusable artifact. */
  async getCorpusStatus(): Promise<RospatentStatutesCorpusStatus> {
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
  ): Promise<RospatentCorpusMeta> {
    await this.ready(options.signal);
    return {
      schema_version: Number(this.metadata.schema_version ?? 0),
      snapshot_date: this.metadata.snapshot_date ?? null,
      source_version: this.metadata.source_version ?? null,
      section_count: Number(this.metadata.section_count ?? 0),
    };
  }

  /** One article by number ('1350', '1231.1'); null when absent. */
  async getArticle(
    articleNumber: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<RospatentArticle | null> {
    const number = text(20).parse(articleNumber);
    const corpus = await this.ready(options.signal);
    const row = this.query<Row>(
      `SELECT ${COLUMNS} FROM sections WHERE statute = ? AND section_number = ? LIMIT 1`,
      [ROSPATENT_STATUTE, number],
      "section table",
    )[0];
    checkCorpusSignal(options.signal);
    if (!row) return null;
    if (typeof row.text !== "string")
      throw new CorpusError(
        "INVALID_CORPUS",
        "The Rospatent statutes article text is not readable.",
      );
    return {
      statute: row.statute,
      section_number: row.section_number,
      section_label: row.section_label,
      title: row.title,
      text: row.text,
      chapter: row.chapter,
      paragraph: row.paragraph,
      subparagraph: row.subparagraph,
      repealed: row.repealed === 1,
      source_url: row.source_url,
      provenance: this.provenance(corpus),
    };
  }

  /** One article by citation ('Article 1350 Civil Code'); null when unparseable or absent. */
  async getArticleByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<RospatentArticle | null> {
    const parsed = parseRospatentCitation(text(500).parse(citation));
    if (!parsed) return null;
    return this.getArticle(parsed.section_number, options);
  }

  /**
   * Full-text search over Part Four, or one chapter (69 to 77). Terms are
   * always quoted as FTS5 text, so caller input never runs as MATCH syntax.
   */
  async search(
    options: RospatentStatutesSearchOptions,
  ): Promise<RospatentSearchResponse> {
    const input = searchOptions.parse(options);
    const chapter = input.chapter ?? null;
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const bind: (string | number)[] = [match];
    if (chapter !== null) bind.push(`Chapter ${chapter}. %`);
    // BM25 ties fall back to row order so pages are stable.
    const order = input.sort === "outline" ? OUTLINE_ORDER : "rank, s.rowid";
    const rows = match
      ? this.query<RospatentSearchHit>(
          `SELECT s.statute, s.section_number, s.section_label, s.title, s.chapter, snippet(sections_fts, 3, '<mark>', '</mark>', '…', 40) AS snippet, rank FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ?${chapter !== null ? " AND s.chapter LIKE ?" : ""} ORDER BY ${order} LIMIT ? OFFSET ?`,
          [...bind, input.per_page + 1, (input.page - 1) * input.per_page],
          "full-text index",
        )
      : [];
    checkCorpusSignal(options.signal);
    return {
      query: input.query,
      chapter,
      hits: rows.slice(0, input.per_page).map((row) => ({
        statute: row.statute,
        section_number: row.section_number,
        section_label: row.section_label,
        title: row.title ?? null,
        chapter: row.chapter,
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
    this.count = null;
    this.sha256 = null;
    this.fileSha256 = null;
    this.compression = null;
  }
}

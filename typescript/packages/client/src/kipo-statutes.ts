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
 * Reader for the KIPO Korea statutes corpus: the English translations by the
 * Korea Legislation Research Institute of the Patent Act, Utility Model Act,
 * Design Protection Act, Trademark Act, Unfair Competition Prevention and
 * Trade Secret Protection Act, Invention Promotion Act and Copyright Act, as
 * KLRI's elaw.klri.re.kr service publishes them. The translations have no legal
 * effect; the Korean text controls. The SQLite/FTS5 snapshot is built by
 * scripts/build-kipo-statutes-corpus.ts; scripts/kipo-statutes-sources.json
 * lists each translation, its version, retrieval time and hash.
 */
export const KIPO_STATUTES_SOURCE_URL =
  "https://elaw.klri.re.kr/eng_service/main.do";
export const KIPO_STATUTES_SOURCE_NAME =
  "KIPO Korea — Statutes (KLRI English translations)";
/** Carried in status and the MCP descriptions: the translations are unofficial. */
export const KIPO_STATUTES_AUTHORITY_NOTE =
  "English translations by the Korea Legislation Research Institute; they have no legal effect and may not reflect the latest amendments. The Korean text controls.";
const LABEL = "KIPO statutes";
const ENV_PREFIX = "KIPO_STATUTES";

/** The seven statute keys, in the order the corpus lists them. */
export const KIPO_STATUTE_KEYS = [
  "patent",
  "utility_model",
  "design",
  "trademark",
  "unfair_competition",
  "invention_promotion",
  "copyright",
] as const;
export type KipoStatuteKey = (typeof KIPO_STATUTE_KEYS)[number];

/**
 * Names lawyers type, to the statute key, including the Korean short names.
 * "Trade secret(s)" maps to the Unfair Competition Prevention and Trade
 * Secret Protection Act, which governs them.
 */
export const KIPO_STATUTE_ALIASES: Readonly<Record<string, string>> = {
  patent: "patent",
  patents: "patent",
  "patent act": "patent",
  "patent law": "patent",
  특허법: "patent",
  utility_model: "utility_model",
  "utility model": "utility_model",
  "utility models": "utility_model",
  "utility model act": "utility_model",
  실용신안법: "utility_model",
  design: "design",
  designs: "design",
  "design act": "design",
  "design protection act": "design",
  "design protection": "design",
  디자인보호법: "design",
  trademark: "trademark",
  trademarks: "trademark",
  "trade mark": "trademark",
  "trade marks": "trademark",
  tm: "trademark",
  "trademark act": "trademark",
  "trade mark act": "trademark",
  상표법: "trademark",
  unfair_competition: "unfair_competition",
  "unfair competition": "unfair_competition",
  "unfair competition act": "unfair_competition",
  "unfair competition prevention act": "unfair_competition",
  "unfair competition prevention and trade secret protection act":
    "unfair_competition",
  ucpa: "unfair_competition",
  "trade secret": "unfair_competition",
  "trade secrets": "unfair_competition",
  "trade secret protection act": "unfair_competition",
  부정경쟁방지법: "unfair_competition",
  "부정경쟁방지 및 영업비밀보호에 관한 법률": "unfair_competition",
  invention_promotion: "invention_promotion",
  "invention promotion": "invention_promotion",
  "invention promotion act": "invention_promotion",
  발명진흥법: "invention_promotion",
  copyright: "copyright",
  "copyright act": "copyright",
  "copyright law": "copyright",
  저작권법: "copyright",
};

/** Statute key for a name or alias; unknown names pass through lowercased. */
export function resolveKipoStatute(name: string): string {
  const key = name
    .trim()
    .toLowerCase()
    .replace(/^the\s+/, "")
    .replace(/\s+/g, " ");
  return KIPO_STATUTE_ALIASES[key] ?? key;
}

const NUMBER = String.raw`\d{1,4}(?:\s*-\s*\d{1,3})?`;
const UNIT = String.raw`(?:article|art\.?|arts\.?|§+|제)`;
// Paragraph, subparagraph and item markers after the number: "(1)", "(1) 2",
// "(1)(ii)", "조" in Korean citations.
const TAIL = String.raw`(?:\s*조)?(?:\s*\([0-9a-zA-Z]+\))*(?:\s*\d{1,2}(?=\s|$))?`;
const FORWARD = new RegExp(
  String.raw`^\s*${UNIT}\s*(?<num>${NUMBER})${TAIL}\s*,?\s+(?:of\s+(?:the\s+)?)?(?<statute>.+?)\s*$`,
  "i",
);
const REVERSE = new RegExp(
  String.raw`^\s*(?:the\s+)?(?<statute>.+?)\s*,?\s+${UNIT}\s*(?<num>${NUMBER})${TAIL}\s*$`,
  "i",
);

/**
 * Parse a citation into a statute key and article number: 'Article 29 Patent
 * Act', 'Patent Act Art. 29(1)', 'Article 29-2 of the Patent Act', 'Art.
 * 2(1) 3 Trademark Act', '특허법 제29조'. Paragraph and subparagraph markers
 * are dropped (the whole article is returned). Null when the shape or the
 * statute name is not recognized.
 */
export function parseKipoCitation(
  citation: string,
): { statute: KipoStatuteKey; section_number: string } | null {
  const cleaned = citation.trim();
  if (!cleaned) return null;
  for (const pattern of [FORWARD, REVERSE]) {
    const match = pattern.exec(cleaned);
    const num = match?.groups?.num;
    const name = match?.groups?.statute;
    if (!num || !name) continue;
    const statute = resolveKipoStatute(
      name.replace(/\s*\((?:Act|Law) No\.?\s*[\d,]+\)$/i, ""),
    );
    if ((KIPO_STATUTE_KEYS as readonly string[]).includes(statute))
      return {
        statute: statute as KipoStatuteKey,
        section_number: num.replace(/\s+/g, ""),
      };
  }
  return null;
}

/** One statute as the corpus carries it, with the translation it was built from. */
export const KipoStatuteSchema = z.object({
  statute: z.string(),
  section_count: z.number().int(),
  /** elaw's page for the translation. */
  source_url: z.string().nullable(),
  short_name: z.string().nullable(),
  title: z.string().nullable(),
  korean_title: z.string().nullable(),
  /** The latest amendment the translation reflects, as elaw states it: "Act No. 20322, Feb. 20, 2024". */
  version: z.string().nullable(),
  act_number: z.string().nullable(),
  /** Promulgation date of that amendment. */
  promulgation_date: z.string().nullable(),
  /** The HTML the articles were parsed from. */
  content_url: z.string().nullable(),
  sha256: z.string().nullable(),
  retrieved_at: z.string().nullable(),
});
export type KipoStatute = z.infer<typeof KipoStatuteSchema>;

/** One article of a Korean IP statute. */
export const KipoSectionSchema = z.object({
  statute: z.string(),
  /** "29" or a branch article such as "29-2". */
  section_number: z.string(),
  /** Citation-ready label, e.g. 'Article 29-2 Patent Act'. */
  section_label: z.string(),
  /** The heading in parentheses after the number; null for deleted articles. */
  title: z.string().nullable(),
  /** One paragraph per line, with the translation's amendment notes in place. */
  text: z.string(),
  source_url: z.string().nullable(),
  provenance: CorpusProvenanceSchema,
});
export type KipoSection = z.infer<typeof KipoSectionSchema>;

export const KipoSearchHitSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  section_label: z.string(),
  title: z.string().nullable(),
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: z.string(),
  /** BM25 rank (lower is more relevant) with sort='relevance'. */
  rank: z.number().nullable(),
});
export type KipoSearchHit = z.infer<typeof KipoSearchHitSchema>;

export interface KipoStatutesCorpusStatus {
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
  /** The translations are unofficial; the Korean text controls. */
  authority_note: string;
  /** Per-statute source and version, or null for a corpus built without them. */
  statutes: KipoStatute[] | null;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
export interface KipoSearchResponse {
  query: string;
  /** The resolved statute filter, or null for all seven. */
  statute: string | null;
  hits: KipoSearchHit[];
  page: number;
  per_page: number;
  has_more: boolean;
  provenance: CorpusProvenance;
  corpus: KipoStatutesCorpusStatus;
}
export interface KipoCorpusMeta {
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

export interface KipoStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also KIPO_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also KIPO_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type KipoStatutesSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

const statuteMeta = z.object({
  statute: z.string(),
  short_name: z.string(),
  english_title: z.string(),
  korean_title: z.string().nullable(),
  version: z.string(),
  act_number: z.string().nullable(),
  promulgation_date: z.string().nullable(),
  page_url: z.string(),
  content_url: z.string(),
  sha256: z.string(),
  retrieved_at: z.string(),
});
/** Meta `statutes` when present and well formed. */
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
      "Unsupported KIPO statutes corpus schema; the supported version is 1.",
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

/** Outline order: corpus statute order, then article number, then branch ("29" < "29-2" < "29-10" < "30"). */
const OUTLINE_ORDER = `CASE s.statute ${KIPO_STATUTE_KEYS.map((key, index) => `WHEN '${key}' THEN ${index}`).join(" ")} ELSE ${KIPO_STATUTE_KEYS.length} END, s.statute, CAST(s.section_number AS INTEGER), CASE WHEN instr(s.section_number, '-') > 0 THEN CAST(substr(s.section_number, instr(s.section_number, '-') + 1) AS INTEGER) ELSE 0 END, s.section_number`;

/**
 * Read-only reader for the KIPO Korea statutes snapshot. It never downloads
 * or rebuilds the corpus. Lookups that find nothing return null.
 */
export class KipoStatutesClient {
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
  private readonly source: KipoStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: KipoStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("kipo_statutes.db") ??
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
        `The KIPO statutes ${what} is not readable.`,
      );
    }
  }

  private statuteList(): KipoStatute[] {
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
      const index = (KIPO_STATUTE_KEYS as readonly string[]).indexOf(key);
      return index < 0 ? KIPO_STATUTE_KEYS.length : index;
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
          source_url: info?.page_url ?? row.source_url,
          short_name: info?.short_name ?? null,
          title: info?.english_title ?? null,
          korean_title: info?.korean_title ?? null,
          version: info?.version ?? null,
          act_number: info?.act_number ?? null,
          promulgation_date: info?.promulgation_date ?? null,
          content_url: info?.content_url ?? null,
          sha256: info?.sha256 ?? null,
          retrieved_at: info?.retrieved_at ?? null,
        };
      });
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): KipoStatutesCorpusStatus {
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
      source_url: KIPO_STATUTES_SOURCE_URL,
      authority_note: KIPO_STATUTES_AUTHORITY_NOTE,
      statutes: available && this.statuteInfo ? this.statuteList() : null,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: KipoStatutesCorpusStatus): CorpusProvenance {
    return {
      source_url: KIPO_STATUTES_SOURCE_URL,
      source_name: KIPO_STATUTES_SOURCE_NAME,
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
  async getCorpusStatus(): Promise<KipoStatutesCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  /** Schema version, snapshot date, source version and row count. */
  async meta(options: { signal?: AbortSignal } = {}): Promise<KipoCorpusMeta> {
    await this.ready(options.signal);
    return {
      schema_version: Number(this.metadata.schema_version ?? 0),
      snapshot_date: this.metadata.snapshot_date ?? null,
      source_version: this.metadata.source_version ?? null,
      section_count: Number(this.metadata.section_count ?? 0),
    };
  }

  /** The statutes in the snapshot with their article counts, versions and sources. */
  async listStatutes(
    options: { signal?: AbortSignal } = {},
  ): Promise<KipoStatute[]> {
    await this.ready(options.signal);
    return this.statuteList();
  }

  /** One article by statute (key or alias) and number ("29", "29-2"); null when absent. */
  async getSection(
    statute: string,
    sectionNumber: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<KipoSection | null> {
    const key = resolveKipoStatute(text(200).parse(statute));
    const number = text(20)
      .parse(sectionNumber)
      .replace(/^(?:article|art\.?)\s*/i, "")
      .replace(/\s+/g, "");
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
        "The KIPO statutes article text is not readable.",
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

  /** One article by citation ('Article 29-2 Patent Act'); null when unparseable or absent. */
  async getSectionByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<KipoSection | null> {
    const parsed = parseKipoCitation(text(500).parse(citation));
    if (!parsed) return null;
    return this.getSection(parsed.statute, parsed.section_number, options);
  }

  /**
   * Full-text search over all seven statutes, or one with `statute`. Terms
   * are always quoted as FTS5 text, so caller input never runs as MATCH
   * syntax.
   */
  async search(
    options: KipoStatutesSearchOptions,
  ): Promise<KipoSearchResponse> {
    const input = searchOptions.parse(options);
    const statute = input.statute ? resolveKipoStatute(input.statute) : null;
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const bind: (string | number)[] = [match];
    if (statute) bind.push(statute);
    // BM25 ties fall back to row order so pages are stable.
    const order = input.sort === "outline" ? OUTLINE_ORDER : "rank, s.rowid";
    const rows = match
      ? this.query<KipoSearchHit>(
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

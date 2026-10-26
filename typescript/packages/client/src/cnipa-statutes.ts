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
 * Reader for the CNIPA China statutes corpus: the English translations WIPO
 * Lex publishes of the Patent Law, the Implementing Regulations of the Patent
 * Law, the Trademark Law, the Regulations for the Implementation of the
 * Trademark Law, the Anti-Unfair Competition Law (China's trade-secret
 * provisions) and the Copyright Law. The translations are for reference; the
 * Chinese text controls, and several are older than the Chinese text WIPO
 * lists (see each statute's `translation_version`). The SQLite/FTS5 snapshot
 * is built by scripts/build-cnipa-statutes-corpus.ts;
 * scripts/cnipa-statutes-sources.json lists each PDF, its retrieval time and
 * hash.
 */
export const CNIPA_STATUTES_SOURCE_URL =
  "https://www.wipo.int/wipolex/en/members/profile/CN";
export const CNIPA_STATUTES_SOURCE_NAME = "CNIPA China — Statutes (WIPO Lex)";
/** Shown with every status: the translations do not control. */
export const CNIPA_STATUTES_NOTICE =
  "English translations for reference only; the Chinese text controls.";
const LABEL = "CNIPA statutes";
const ENV_PREFIX = "CNIPA_STATUTES";

/** The six statute keys, in the order the corpus lists them. */
export const CNIPA_STATUTE_KEYS = [
  "patent_law",
  "patent_regulations",
  "trademark_law",
  "trademark_regulations",
  "anti_unfair_competition",
  "copyright_law",
] as const;
export type CnipaStatuteKey = (typeof CNIPA_STATUTE_KEYS)[number];

/**
 * How each statute numbers its provisions in the translation. The 2010
 * Patent Implementing Regulations number by Rule; the 2023 Chinese text
 * renumbers them as Articles, so an "Article N" citation to the regulations
 * is not resolved to Rule N.
 */
export const CNIPA_STATUTE_UNITS: Readonly<
  Record<CnipaStatuteKey, "Article" | "Rule">
> = {
  patent_law: "Article",
  patent_regulations: "Rule",
  trademark_law: "Article",
  trademark_regulations: "Article",
  anti_unfair_competition: "Article",
  copyright_law: "Article",
};

/**
 * Names lawyers type, to the statute key. "Implementing Regulations" alone
 * means the patent regulations (cited by Rule); "trade secret(s)" maps to the
 * Anti-Unfair Competition Law, which carries China's trade-secret rules.
 */
export const CNIPA_STATUTE_ALIASES: Readonly<Record<string, CnipaStatuteKey>> =
  {
    patent_law: "patent_law",
    "patent law": "patent_law",
    patent: "patent_law",
    patents: "patent_law",
    pl: "patent_law",
    patent_regulations: "patent_regulations",
    "patent implementing regulations": "patent_regulations",
    "implementing regulations of the patent law": "patent_regulations",
    "patent law implementing regulations": "patent_regulations",
    "implementing regulations": "patent_regulations",
    "implementing rules": "patent_regulations",
    "implementing rules of the patent law": "patent_regulations",
    "patent regulations": "patent_regulations",
    "patent rules": "patent_regulations",
    trademark_law: "trademark_law",
    "trademark law": "trademark_law",
    "trade mark law": "trademark_law",
    trademark: "trademark_law",
    trademarks: "trademark_law",
    tm: "trademark_law",
    trademark_regulations: "trademark_regulations",
    "trademark implementing regulations": "trademark_regulations",
    "regulations for the implementation of the trademark law":
      "trademark_regulations",
    "implementing regulations of the trademark law": "trademark_regulations",
    "trademark law implementing regulations": "trademark_regulations",
    "trademark regulations": "trademark_regulations",
    "tm regulations": "trademark_regulations",
    anti_unfair_competition: "anti_unfair_competition",
    "anti-unfair competition law": "anti_unfair_competition",
    "anti unfair competition law": "anti_unfair_competition",
    "law against unfair competition": "anti_unfair_competition",
    "unfair competition law": "anti_unfair_competition",
    "unfair competition": "anti_unfair_competition",
    aucl: "anti_unfair_competition",
    "trade secret": "anti_unfair_competition",
    "trade secrets": "anti_unfair_competition",
    copyright_law: "copyright_law",
    "copyright law": "copyright_law",
    copyright: "copyright_law",
  };

/**
 * Statute key for a name or alias, ignoring case, "of the People's Republic
 * of China" / "PRC" / "Chinese" and a trailing year; unknown names pass
 * through normalized and find nothing.
 */
export function resolveCnipaStatute(name: string): string {
  const key = name
    .trim()
    .toLowerCase()
    .replace(/[’‘]/g, "'")
    .replace(/\s+/g, " ")
    .replace(/^the /, "")
    .replace(/[,(]?\s*\(?\b(?:19|20)\d{2}\)?$/, "")
    .replace(/\s+of (?:the )?(?:people's republic of china|prc|china)$/, "")
    .replace(/^(?:prc|china|chinese|china's) /, "")
    .trim();
  return CNIPA_STATUTE_ALIASES[key] ?? key;
}

const UNIT = String.raw`(?<unit>article|art\.?|rule|r\.)`;
const NUMBER = String.raw`(?<num>\d{1,3})`;
// Paragraph or item markers after the number: "(3)", "(3)(2)", ", paragraph 2".
const PARTS = String.raw`(?:\s*\(\d{1,2}\))*(?:\s*,?\s*(?:paragraph|para\.?)\s*\d{1,2})?`;
const FORWARD = new RegExp(
  String.raw`^\s*(?:${UNIT}\s*)?${NUMBER}${PARTS}\s+(?:of\s+(?:the\s+)?)?(?<statute>.+?)\s*$`,
  "i",
);
const REVERSE = new RegExp(
  String.raw`^\s*(?<statute>.+?)\s*,?\s+${UNIT}\s*${NUMBER}${PARTS}\s*$`,
  "i",
);

/**
 * Parse a citation into a statute key and provision number: 'Article 22
 * Patent Law', 'Patent Law Art. 22(3)', 'Article 22 of the Patent Law of the
 * People's Republic of China', 'Rule 20 Implementing Regulations', 'Article 9
 * AUCL'. Paragraph markers are dropped (the whole provision is returned).
 * Null when the shape or the statute is not recognized, or when the unit does
 * not match how the translation numbers that statute ("Article 20
 * Implementing Regulations" names a 2023 Article, not 2010 Rule 20).
 */
export function parseCnipaCitation(
  citation: string,
): { statute: CnipaStatuteKey; section_number: string } | null {
  const cleaned = citation.trim();
  if (!cleaned) return null;
  for (const pattern of [FORWARD, REVERSE]) {
    const match = pattern.exec(cleaned);
    const num = match?.groups?.num;
    const name = match?.groups?.statute;
    if (!num || !name) continue;
    const statute = resolveCnipaStatute(name);
    if (!(CNIPA_STATUTE_KEYS as readonly string[]).includes(statute)) continue;
    const key = statute as CnipaStatuteKey;
    const unit = match?.groups?.unit?.toLowerCase();
    if (unit) {
      const written = unit.startsWith("r") ? "Rule" : "Article";
      if (written !== CNIPA_STATUTE_UNITS[key]) return null;
    }
    return { statute: key, section_number: String(Number(num)) };
  }
  return null;
}

/** One statute as the corpus carries it, with the WIPO Lex source it was built from. */
export const CnipaStatuteSchema = z.object({
  statute: z.string(),
  section_count: z.number().int(),
  /** The WIPO Lex legislation page. */
  source_url: z.string().nullable(),
  short_name: z.string().nullable(),
  title: z.string().nullable(),
  /** "Article" or "Rule", as the translation numbers the provisions. */
  unit: z.string().nullable(),
  /** WIPO Lex's description of its entry: year of version, dates, type. */
  version: z.string().nullable(),
  /** What the English text is; it can be older than the Chinese text WIPO lists. */
  translation_version: z.string().nullable(),
  /** The English PDF the provisions were parsed from. */
  pdf_url: z.string().nullable(),
  /** The Chinese text on the same WIPO Lex page, which controls. */
  zh_pdf_url: z.string().nullable(),
  pdf_sha256: z.string().nullable(),
  retrieved_at: z.string().nullable(),
});
export type CnipaStatute = z.infer<typeof CnipaStatuteSchema>;

/** One numbered provision (Article or Rule) of a Chinese IP statute, in English translation. */
export const CnipaSectionSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  /** Citation-ready label, e.g. 'Article 22 Patent Law' or 'Rule 20 Patent Implementing Regulations'. */
  section_label: z.string(),
  /** The chapter (and section) the provision sits in; the translations print no article headings. */
  title: z.string().nullable(),
  /** One paragraph per line; a renumbering note in the translation closes the text in brackets. */
  text: z.string(),
  source_url: z.string().nullable(),
  provenance: CorpusProvenanceSchema,
});
export type CnipaSection = z.infer<typeof CnipaSectionSchema>;

export const CnipaSearchHitSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  section_label: z.string(),
  title: z.string().nullable(),
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: z.string(),
  /** BM25 rank (lower is more relevant) with sort='relevance'. */
  rank: z.number().nullable(),
});
export type CnipaSearchHit = z.infer<typeof CnipaSearchHitSchema>;

export interface CnipaStatutesCorpusStatus {
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
  /** The translations do not control; the Chinese text does. */
  notice: string;
  /** Per-statute source and version, or null for a corpus built without them. */
  statutes: CnipaStatute[] | null;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
export interface CnipaSearchResponse {
  query: string;
  /** The resolved statute filter, or null for all six. */
  statute: string | null;
  hits: CnipaSearchHit[];
  page: number;
  per_page: number;
  has_more: boolean;
  provenance: CorpusProvenance;
  corpus: CnipaStatutesCorpusStatus;
}
export interface CnipaCorpusMeta {
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

export interface CnipaStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also CNIPA_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also CNIPA_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type CnipaStatutesSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

const statuteMeta = z.object({
  statute: z.string(),
  short_name: z.string(),
  title: z.string(),
  unit: z.string(),
  wipo_summary: z.string().nullable(),
  translation_version: z.string(),
  details_url: z.string(),
  pdf_url: z.string(),
  zh_pdf_url: z.string().nullable(),
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
      "Unsupported CNIPA statutes corpus schema; the supported version is 1.",
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

/** Outline order: the statutes in key order, then numeric provision ("2" < "10"). */
const OUTLINE_ORDER = `CASE s.statute ${CNIPA_STATUTE_KEYS.map((key, index) => `WHEN '${key}' THEN ${index}`).join(" ")} ELSE ${CNIPA_STATUTE_KEYS.length} END, s.statute, CAST(s.section_number AS INTEGER), s.section_number`;

/**
 * Read-only reader for the CNIPA China statutes snapshot. It never downloads
 * or rebuilds the corpus. Lookups that find nothing return null, as the
 * other statute readers' do.
 */
export class CnipaStatutesClient {
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
  private readonly source: CnipaStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: CnipaStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("cnipa_statutes.db") ??
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
        `The CNIPA statutes ${what} is not readable.`,
      );
    }
  }

  private statuteList(): CnipaStatute[] {
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
      const index = (CNIPA_STATUTE_KEYS as readonly string[]).indexOf(key);
      return index < 0 ? CNIPA_STATUTE_KEYS.length : index;
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
          unit: info?.unit ?? null,
          version: info?.wipo_summary ?? null,
          translation_version: info?.translation_version ?? null,
          pdf_url: info?.pdf_url ?? null,
          zh_pdf_url: info?.zh_pdf_url ?? null,
          pdf_sha256: info?.pdf_sha256 ?? null,
          retrieved_at: info?.retrieved_at ?? null,
        };
      });
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): CnipaStatutesCorpusStatus {
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
      source_url: CNIPA_STATUTES_SOURCE_URL,
      notice: CNIPA_STATUTES_NOTICE,
      statutes: available && this.statuteInfo ? this.statuteList() : null,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: CnipaStatutesCorpusStatus): CorpusProvenance {
    return {
      source_url: CNIPA_STATUTES_SOURCE_URL,
      source_name: CNIPA_STATUTES_SOURCE_NAME,
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
  async getCorpusStatus(): Promise<CnipaStatutesCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  /** Schema version, snapshot date, source version and row count. */
  async meta(options: { signal?: AbortSignal } = {}): Promise<CnipaCorpusMeta> {
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
  ): Promise<CnipaStatute[]> {
    await this.ready(options.signal);
    return this.statuteList();
  }

  /** One provision by statute (key or alias) and number; null when absent. */
  async getSection(
    statute: string,
    sectionNumber: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<CnipaSection | null> {
    const key = resolveCnipaStatute(text(200).parse(statute));
    // "22", "022" and "Article 22" all name Article 22.
    const raw = text(20)
      .parse(sectionNumber)
      .replace(/^(?:article|art\.?|rule|r\.)\s*/i, "");
    const number = /^\d{1,4}$/.test(raw) ? String(Number(raw)) : raw;
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
        "The CNIPA statutes section text is not readable.",
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

  /** One provision by citation ('Article 22 Patent Law', 'Rule 20 Implementing Regulations'); null when unparseable or absent. */
  async getSectionByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<CnipaSection | null> {
    const parsed = parseCnipaCitation(text(500).parse(citation));
    if (!parsed) return null;
    return this.getSection(parsed.statute, parsed.section_number, options);
  }

  /**
   * Full-text search over all six statutes, or one with `statute`. Terms are
   * always quoted as FTS5 text, so caller input never runs as MATCH syntax.
   */
  async search(
    options: CnipaStatutesSearchOptions,
  ): Promise<CnipaSearchResponse> {
    const input = searchOptions.parse(options);
    const statute = input.statute ? resolveCnipaStatute(input.statute) : null;
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const bind: (string | number)[] = [match];
    if (statute) bind.push(statute);
    // BM25 ties fall back to row order so pages are stable.
    const order = input.sort === "outline" ? OUTLINE_ORDER : "rank, s.rowid";
    const rows = match
      ? this.query<CnipaSearchHit>(
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

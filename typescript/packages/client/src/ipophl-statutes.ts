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
 * Reader for the IPOPHL Philippines statutes corpus: the Intellectual
 * Property Code of the Philippines (Republic Act No. 8293, 1997) and the
 * three Acts that amend it, RA 9150 (2001), RA 9502 (2008) and RA 10372
 * (2013), each as enacted and each its own statute. The Code's text is its
 * 1997 text; the amendments are not consolidated into it. The SQLite/FTS5
 * snapshot is built by scripts/build-ipophl-statutes-corpus.ts from the
 * LawPhil Project's pages; scripts/ipophl-statutes-sources.json lists each
 * page, its retrieval time and hash.
 */
export const IPOPHL_STATUTES_SOURCE_URL =
  "https://lawphil.net/statutes/repacts/ra1997/ra_8293_1997.html";
export const IPOPHL_STATUTES_SOURCE_NAME =
  "IPOPHL Philippines — IP Code and amending Acts (LawPhil)";
const LABEL = "IPOPHL statutes";
const ENV_PREFIX = "IPOPHL_STATUTES";

/** The four statute keys, in the order the corpus lists them. */
export const IPOPHL_STATUTE_KEYS = [
  "ra8293",
  "ra9150",
  "ra9502",
  "ra10372",
] as const;
export type IpophlStatuteKey = (typeof IPOPHL_STATUTE_KEYS)[number];

/** Names lawyers type, to the statute key. Republic Act numbers resolve on their own. */
export const IPOPHL_STATUTE_ALIASES: Readonly<Record<string, string>> = {
  "ip code": "ra8293",
  "intellectual property code": "ra8293",
  "intellectual property code of the philippines": "ra8293",
  "philippine ip code": "ra8293",
  "cheaper medicines act": "ra9502",
  "universally accessible cheaper and quality medicines act": "ra9502",
  "universally accessible cheaper and quality medicines act of 2008": "ra9502",
};

const ACT_NUMBER =
  /\b(?:republic\s+act|rep\.?\s*act|r\.?\s*a\.?)\s*(?:no\.?\s*)?(\d{3,5})\b/;

/**
 * Statute key for a name, alias or Republic Act number ('IP Code', 'R.A. No.
 * 8293', 'Republic Act 10372', 'ra9502'). Unknown names pass through
 * lowercased and find nothing.
 */
export function resolveIpophlStatute(name: string): string {
  const key = name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/^the /, "")
    .replace(/[,\s]*(?:of )?\(?1997\)?$/, "");
  const alias = IPOPHL_STATUTE_ALIASES[key];
  if (alias) return alias;
  const act = ACT_NUMBER.exec(key)?.[1];
  return act ? `ra${act}` : key;
}

const NUMBER = String.raw`\d{1,3}(?:-?[A-Za-z])?`;
const SUBDIVISIONS = String.raw`(?:\.\d+)*\.?(?:\s*\([0-9a-zA-Z]+\))*`;
const UNIT = String.raw`(?:sections?|secs?\.?|s\.|§+)`;
const FORWARD = new RegExp(
  String.raw`^\s*(?:${UNIT}\s*)?(?<num>${NUMBER})${SUBDIVISIONS}\s*,?\s+(?:of\s+(?:the\s+)?)?(?<statute>.+?)\s*$`,
  "i",
);
const REVERSE = new RegExp(
  String.raw`^\s*(?:the\s+)?(?<statute>.+?)\s*,?\s+${UNIT}\s*(?<num>${NUMBER})${SUBDIVISIONS}\s*$`,
  "i",
);

/**
 * Parse a citation into a statute key and section number: 'Section 21 IP
 * Code', 'Sec. 123.1(d) RA 8293', 'Section 3 RA 10372', 'RA 8293 Sec. 22',
 * 'Section 22 of the Intellectual Property Code of the Philippines'.
 * Subsections and paragraphs are dropped (the whole section is returned);
 * letter suffixes are uppercased without a hyphen ('93-A' becomes '93A').
 * Null when the shape or the statute name is not recognized.
 */
export function parseIpophlCitation(
  citation: string,
): { statute: IpophlStatuteKey; section_number: string } | null {
  const cleaned = citation.trim();
  if (!cleaned) return null;
  for (const pattern of [FORWARD, REVERSE]) {
    const match = pattern.exec(cleaned);
    const num = match?.groups?.num;
    const name = match?.groups?.statute;
    if (!num || !name) continue;
    const statute = resolveIpophlStatute(name);
    if ((IPOPHL_STATUTE_KEYS as readonly string[]).includes(statute))
      return {
        statute: statute as IpophlStatuteKey,
        section_number: num.replace("-", "").toUpperCase(),
      };
  }
  return null;
}

/** One Act as the corpus carries it, with the LawPhil page it was built from. */
export const IpophlStatuteSchema = z.object({
  statute: z.string(),
  section_count: z.number().int(),
  /** The LawPhil page. */
  source_url: z.string().nullable(),
  short_name: z.string().nullable(),
  title: z.string().nullable(),
  /** 'code' for RA 8293, 'amendment' for an Act amending it. */
  role: z.string().nullable(),
  /** Date of approval (YYYY-MM-DD). */
  approved: z.string().nullable(),
  /** The Act's long title as LawPhil gives it. */
  page_title: z.string().nullable(),
  page_sha256: z.string().nullable(),
  retrieved_at: z.string().nullable(),
  /** Section numbers the source page does not carry. */
  missing_sections: z.array(z.string()),
});
export type IpophlStatute = z.infer<typeof IpophlStatuteSchema>;

/** One section of the IP Code or an amending Act, as enacted. */
export const IpophlSectionSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  /** Citation-ready label, e.g. 'Section 21 RA 8293'. */
  section_label: z.string(),
  /** The section's heading, when the Act gives one (most amending clauses have none). */
  title: z.string().nullable(),
  /** One paragraph per line; notes about the source close the text in brackets. */
  text: z.string(),
  source_url: z.string().nullable(),
  /**
   * For RA 8293 sections, the amending-Act sections whose opening clause
   * names this section (amends, inserts after, renumbers or deletes it).
   * A pointer to where the change is, not a consolidation; empty otherwise.
   */
  amended_by: z.array(z.string()),
  provenance: CorpusProvenanceSchema,
});
export type IpophlSection = z.infer<typeof IpophlSectionSchema>;

export const IpophlSearchHitSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  section_label: z.string(),
  title: z.string().nullable(),
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: z.string(),
  /** BM25 rank (lower is more relevant) with sort='relevance'. */
  rank: z.number().nullable(),
});
export type IpophlSearchHit = z.infer<typeof IpophlSearchHitSchema>;

export interface IpophlStatutesCorpusStatus {
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
  /** How current the text is: each Act as enacted, amendments not consolidated. */
  text_status: string | null;
  /** Per-Act source and approval date, or null for a corpus built without them. */
  statutes: IpophlStatute[] | null;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
export interface IpophlSearchResponse {
  query: string;
  /** The resolved statute filter, or null for all four. */
  statute: string | null;
  hits: IpophlSearchHit[];
  page: number;
  per_page: number;
  has_more: boolean;
  provenance: CorpusProvenance;
  corpus: IpophlStatutesCorpusStatus;
}
export interface IpophlCorpusMeta {
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

export interface IpophlStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also IPOPHL_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also IPOPHL_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type IpophlStatutesSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

const statuteMeta = z.object({
  statute: z.string(),
  short_name: z.string(),
  title: z.string(),
  role: z.string(),
  approved: z.string(),
  page_title: z.string().nullable(),
  page_url: z.string(),
  retrieved_at: z.string(),
  sha256: z.string(),
  missing_sections: z.array(z.string()),
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
/** Meta `amendments`: RA 8293 section number to amending-Act section labels. */
function parseAmendments(value: string | undefined) {
  if (!value) return {};
  try {
    return z.record(z.string(), z.array(z.string())).parse(JSON.parse(value));
  } catch {
    return {};
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
      "Unsupported IPOPHL statutes corpus schema; the supported version is 1.",
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

const STATUTE_ORDER = `CASE s.statute ${IPOPHL_STATUTE_KEYS.map((key, index) => `WHEN '${key}' THEN ${index}`).join(" ")} ELSE ${IPOPHL_STATUTE_KEYS.length} END`;
/** Outline order: Act, then numeric section with its letter suffix ("2" < "10" < "10A"). */
const OUTLINE_ORDER = `${STATUTE_ORDER}, s.statute, CAST(s.section_number AS INTEGER), length(s.section_number), s.section_number`;

/**
 * Read-only reader for the IPOPHL Philippines statutes snapshot. It never
 * downloads or rebuilds the corpus. Lookups that find nothing return null.
 */
export class IpophlStatutesClient {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private metadata: Record<string, string> = {};
  private statuteInfo: z.infer<typeof statuteMeta>[] | null = null;
  private amendments: Record<string, string[]> = {};
  private count: number | null = null;
  private sha256: string | null = null;
  private fileSha256: string | null = null;
  private compression: "none" | "zstd" | null = null;
  private readonly path: string;
  private readonly source: IpophlStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: IpophlStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("ipophl_statutes.db") ??
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
      this.amendments = parseAmendments(snapshot.value.metadata.amendments);
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
        `The IPOPHL statutes ${what} is not readable.`,
      );
    }
  }

  private statuteList(): IpophlStatute[] {
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
      const index = (IPOPHL_STATUTE_KEYS as readonly string[]).indexOf(key);
      return index < 0 ? IPOPHL_STATUTE_KEYS.length : index;
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
          title: info?.title ?? null,
          role: info?.role ?? null,
          approved: info?.approved ?? null,
          page_title: info?.page_title ?? null,
          page_sha256: info?.sha256 ?? null,
          retrieved_at: info?.retrieved_at ?? null,
          missing_sections: info?.missing_sections ?? [],
        };
      });
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): IpophlStatutesCorpusStatus {
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
      source_url: IPOPHL_STATUTES_SOURCE_URL,
      text_status: metadata.text_status ?? null,
      statutes: available && this.statuteInfo ? this.statuteList() : null,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: IpophlStatutesCorpusStatus): CorpusProvenance {
    return {
      source_url: IPOPHL_STATUTES_SOURCE_URL,
      source_name: IPOPHL_STATUTES_SOURCE_NAME,
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
  async getCorpusStatus(): Promise<IpophlStatutesCorpusStatus> {
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
  ): Promise<IpophlCorpusMeta> {
    await this.ready(options.signal);
    return {
      schema_version: Number(this.metadata.schema_version ?? 0),
      snapshot_date: this.metadata.snapshot_date ?? null,
      source_version: this.metadata.source_version ?? null,
      section_count: Number(this.metadata.section_count ?? 0),
    };
  }

  /** The Acts in the snapshot with their section counts and sources. */
  async listStatutes(
    options: { signal?: AbortSignal } = {},
  ): Promise<IpophlStatute[]> {
    await this.ready(options.signal);
    return this.statuteList();
  }

  /** One section by statute (key, alias or RA number) and number; null when absent. */
  async getSection(
    statute: string,
    sectionNumber: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<IpophlSection | null> {
    const key = resolveIpophlStatute(text(200).parse(statute));
    const number = text(20).parse(sectionNumber).replace("-", "").toUpperCase();
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
        "The IPOPHL statutes section text is not readable.",
      );
    return {
      statute: row.statute,
      section_number: row.section_number,
      section_label: row.section_label,
      title: row.title,
      text: row.text,
      source_url: row.source_url,
      amended_by:
        row.statute === "ra8293"
          ? [...(this.amendments[row.section_number] ?? [])]
          : [],
      provenance: this.provenance(corpus),
    };
  }

  /** One section by citation ('Section 21 IP Code'); null when unparseable or absent. */
  async getSectionByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<IpophlSection | null> {
    const parsed = parseIpophlCitation(text(500).parse(citation));
    if (!parsed) return null;
    return this.getSection(parsed.statute, parsed.section_number, options);
  }

  /**
   * Full-text search over all four Acts, or one with `statute`. Terms are
   * always quoted as FTS5 text, so caller input never runs as MATCH syntax.
   */
  async search(
    options: IpophlStatutesSearchOptions,
  ): Promise<IpophlSearchResponse> {
    const input = searchOptions.parse(options);
    const statute = input.statute ? resolveIpophlStatute(input.statute) : null;
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const bind: (string | number)[] = [match];
    if (statute) bind.push(statute);
    // BM25 ties fall back to row order so pages are stable.
    const order = input.sort === "outline" ? OUTLINE_ORDER : "rank, s.rowid";
    const rows = match
      ? this.query<IpophlSearchHit>(
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
    this.amendments = {};
    this.count = null;
    this.sha256 = null;
    this.fileSha256 = null;
    this.compression = null;
  }
}

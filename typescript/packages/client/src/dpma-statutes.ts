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

/** The official consolidated texts the bundled sections come from. */
export const DPMA_STATUTES_SOURCE_URL = "https://www.gesetze-im-internet.de/";
export const DPMA_STATUTES_SOURCE_NAME = "DPMA Germany — IP statutes";
const LABEL = "DPMA statutes";
const ENV_PREFIX = "DPMA_STATUTES";

/** Python's STATUTE_KEYS: lowercased names and aliases to the stored short name. */
export const DPMA_STATUTE_ALIASES: Readonly<Record<string, string>> = {
  patg: "PatG",
  patentgesetz: "PatG",
  "patent act": "PatG",
  markeng: "MarkenG",
  markengesetz: "MarkenG",
  "trade mark act": "MarkenG",
  "trademark act": "MarkenG",
  gebrmg: "GebrMG",
  gebrauchsmustergesetz: "GebrMG",
  "utility model act": "GebrMG",
  designg: "DesignG",
  designgesetz: "DesignG",
  "design act": "DesignG",
  urhg: "UrhG",
  urheberrechtsgesetz: "UrhG",
  "copyright act": "UrhG",
  geschgehg: "GeschGehG",
  geschäftsgeheimnisgesetz: "GeschGehG",
  geschaeftsgeheimnisgesetz: "GeschGehG",
  "trade secrets act": "GeschGehG",
};

/** Stored short name for an Act name or alias; unknown names pass through trimmed, as in Python. */
export function resolveDpmaStatute(name: string): string {
  const trimmed = name.trim();
  return DPMA_STATUTE_ALIASES[trimmed.toLowerCase()] ?? trimmed;
}

const NUMBER = String.raw`[0-9]+[A-Za-z]?(?:\([0-9a-zA-Z]+\))*(?:\.[0-9]+)*`;
// German subdivisions ("Abs. 2", "Satz 1", "Nr. 3") name part of a section;
// the whole section is returned, so they are dropped before the Act name.
const SUBDIVISION = String.raw`(?:\s*(?:Abs\.?|Absatz|S\.|Satz|Nr\.?|Nummer)\s*[0-9]+[a-z]?)*`;
const CITATION = new RegExp(
  String.raw`^\s*(?:(?:§|section|sec\.?|s\.?)\s*)?(${NUMBER})${SUBDIVISION}(?:\s+(?:of\s+the\s+)?(.+?))?\s*$`,
  "i",
);

/**
 * Parse a free-text citation into a section number and an optional stored
 * Act name: '§ 139 PatG', '§ 139 Abs. 1 PatG', 'Section 14 MarkenG',
 * 'S. 139 PatG', '139 PatG' or a bare '139'. Letter suffixes are lowercased
 * ('16A' → '16a'), as gesetze-im-internet.de numbers them.
 */
export function parseDpmaCitation(citation: string): {
  section: string;
  statute: string | null;
} {
  const match = CITATION.exec(citation);
  if (!match?.[1])
    throw new CorpusError(
      "INVALID_CITATION",
      `Could not parse citation '${citation}'; expected e.g. '§ 1 PatG' or 'Section 14 MarkenG'.`,
    );
  return {
    section: match[1].toLowerCase(),
    statute: match[2] ? resolveDpmaStatute(match[2]) : null,
  };
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
  limit: z.number().int().min(1).max(100).default(10),
  offset: z.number().int().min(0).safe().default(0),
});
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);

export interface DpmaStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also DPMA_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also DPMA_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type DpmaStatutesSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};
export interface DpmaSectionOptions {
  /** Act short name or alias; required when the number exists in several Acts. */
  statute?: string | null;
  signal?: AbortSignal;
}

/** One Act's version and source, as the gesetze-im-internet.de build records it in meta `acts`. */
export interface DpmaActInfo {
  statute: string;
  /** Official long title, e.g. 'Patentgesetz'. */
  title: string;
  /** The Act's Stand note, e.g. 'zuletzt geändert durch Art. 13 G v. 20.5.2026 I Nr. 152'; null if never amended. */
  stand: string | null;
  /** Date of the amending Act in the Stand note (ISO). */
  amended_on: string | null;
  /** Ausfertigungsdatum (ISO). */
  enacted_on: string | null;
  /** Promulgation reference, e.g. 'BGBl I 2019, 466'. */
  fundstelle: string | null;
  /** amended_on, or enacted_on for an Act never amended. */
  version_date: string | null;
  /** Publisher build stamp of the XML (YYYYMMDDhhmmss). */
  builddate: string;
  source_url: string;
  retrieved_at: string;
  zip_sha256: string;
  section_count: number;
}

const actInfo = z.object({
  statute: z.string(),
  title: z.string(),
  stand: z.string().nullable(),
  amended_on: z.string().nullable(),
  enacted_on: z.string().nullable(),
  fundstelle: z.string().nullable(),
  version_date: z.string().nullable(),
  builddate: z.string(),
  source_url: z.string(),
  retrieved_at: z.string(),
  zip_sha256: z.string(),
  section_count: z.number(),
});
/** Meta `acts` when present and well formed; seed builds have none. */
function parseActs(value: string | undefined): DpmaActInfo[] | null {
  if (!value) return null;
  try {
    return z.array(actInfo).parse(JSON.parse(value));
  } catch {
    return null;
  }
}

export interface DpmaStatutesCorpusStatus {
  available: boolean;
  label: string;
  /** source_version when recorded, else `snapshot-<date>`, as Python reports it. */
  corpus_version: string;
  schema_version: number | null;
  section_count: number | null;
  snapshot_date: string | null;
  corpus_synced_at: string | null;
  artifact_sha256: string | null;
  file_sha256: string | null;
  compression: "none" | "zstd" | null;
  source_url: string;
  /** Per-Act version and source, or null for a corpus built without them. */
  acts: DpmaActInfo[] | null;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
/** One section (§) of a bundled German IP Act. */
export interface DpmaSection {
  statute: string;
  section: string;
  title: string | null;
  text: string;
  /** The Act's Stand note at build time, when the corpus records it. */
  stand: string | null;
  /** The Act's last amendment (or enactment) date, when recorded. */
  version_date: string | null;
  provenance: CorpusProvenance;
}
export interface DpmaSearchHit {
  statute: string;
  section: string;
  title: string | null;
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: string;
  /** BM25 rank (lower is more relevant). */
  rank: number | null;
}
export interface DpmaSearchResponse {
  query: string;
  /** The resolved Act filter, or null for all Acts. */
  statute: string | null;
  hits: DpmaSearchHit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: DpmaStatutesCorpusStatus;
}

interface Row {
  statute: string;
  section: string;
  title: string | null;
  text: unknown;
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
      "Unsupported DPMA statutes corpus schema; the supported version is 1.",
    );
  db.all("SELECT statute, section, title, text FROM sections LIMIT 0");
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
      JSON.stringify(["statute", "section", "title", "text"]) ||
    count === undefined
  )
    throw new Error();
  return { metadata, count };
}

/**
 * Read-only reader for the DPMA statutes snapshot: sections of PatG, MarkenG,
 * GebrMG, DesignG, UrhG and GeschGehG in one SQLite/FTS5 database. It never
 * downloads or rebuilds the corpus.
 */
export class DpmaStatutesClient {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private metadata: Record<string, string> = {};
  private acts: DpmaActInfo[] | null = null;
  private count: number | null = null;
  private sha256: string | null = null;
  private fileSha256: string | null = null;
  private compression: "none" | "zstd" | null = null;
  private readonly path: string;
  private readonly source: DpmaStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: DpmaStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("dpma_statutes.db") ??
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
      this.acts = parseActs(snapshot.value.metadata.acts);
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
        `The DPMA statutes ${what} is not readable.`,
      );
    }
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): DpmaStatutesCorpusStatus {
    const metadata = { ...this.metadata };
    const snapshot = metadata.snapshot_date;
    const synced = corpusTimestamp(snapshot);
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
      corpus_synced_at: synced,
      artifact_sha256: this.sha256,
      file_sha256: this.fileSha256,
      compression: this.compression,
      source_url: DPMA_STATUTES_SOURCE_URL,
      acts: this.acts,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: DpmaStatutesCorpusStatus): CorpusProvenance {
    return {
      source_url: DPMA_STATUTES_SOURCE_URL,
      source_name: DPMA_STATUTES_SOURCE_NAME,
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
  async getCorpusStatus(): Promise<DpmaStatutesCorpusStatus> {
    try {
      await this.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  /** Short names of the Acts present in the snapshot, alphabetically. */
  async listStatutes(options: { signal?: AbortSignal } = {}) {
    await this.ready(options.signal);
    return this.query<{ statute: string }>(
      "SELECT DISTINCT statute FROM sections ORDER BY statute",
      [],
      "section table",
    ).map((row) => row.statute);
  }

  /**
   * One section by number. Without `statute`, a number found in exactly one
   * Act resolves; one found in several raises AMBIGUOUS_SECTION.
   */
  async getSection(
    section: string,
    options: DpmaSectionOptions = {},
  ): Promise<DpmaSection> {
    const number = text(100).parse(section);
    const statute =
      options.statute == null
        ? null
        : resolveDpmaStatute(text(200).parse(options.statute));
    const corpus = await this.ready(options.signal);
    const rows = statute
      ? this.query<Row>(
          "SELECT statute, section, title, text FROM sections WHERE statute = ? AND section = ? LIMIT 1",
          [statute, number],
          "section table",
        )
      : this.query<Row>(
          "SELECT statute, section, title, text FROM sections WHERE section = ? ORDER BY statute",
          [number],
          "section table",
        );
    const row = rows[0];
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        statute
          ? `Section '${number}' not found in '${statute}'.`
          : `Section '${number}' not found in any bundled statute.`,
      );
    if (rows.length > 1)
      throw new CorpusError(
        "AMBIGUOUS_SECTION",
        `Section '${number}' is ambiguous — exists in: ${rows.map((item) => item.statute).join(", ")}. Pass statute= to disambiguate.`,
      );
    if (typeof row.text !== "string")
      throw new CorpusError(
        "INVALID_CORPUS",
        "The DPMA statutes section text is not readable.",
      );
    checkCorpusSignal(options.signal);
    const act = this.acts?.find((item) => item.statute === row.statute);
    return {
      statute: row.statute,
      section: row.section,
      title: row.title,
      text: row.text,
      stand: act?.stand ?? null,
      version_date: act?.version_date ?? null,
      provenance: this.provenance(corpus),
    };
  }

  /** One section by free-text citation, e.g. '§ 139 PatG'; see parseDpmaCitation. */
  async getSectionByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<DpmaSection> {
    const { section, statute } = parseDpmaCitation(text(500).parse(citation));
    return this.getSection(section, { statute, ...options });
  }

  /**
   * Full-text search over every bundled Act, or one with `statute`. Terms are
   * always quoted as FTS5 text, so caller input never runs as MATCH syntax.
   */
  async search(
    options: DpmaStatutesSearchOptions,
  ): Promise<DpmaSearchResponse> {
    const input = searchOptions.parse(options);
    const statute = input.statute ? resolveDpmaStatute(input.statute) : null;
    const corpus = await this.ready(options.signal);
    const match = outlineFtsQuery(input.query, input.syntax);
    const bind: (string | number)[] = [match];
    if (statute) bind.push(statute);
    // Outline order is numeric by section ("3" before "139"), with an
    // unnumbered Anlage after the sections; BM25 ties fall back to row order
    // so pages are stable.
    const order =
      input.sort === "outline"
        ? "s.statute, s.section NOT GLOB '[0-9]*', CAST(s.section AS INTEGER), s.section"
        : "rank, s.rowid";
    const rows = match
      ? this.query<DpmaSearchHit>(
          `SELECT s.statute, s.section, s.title, snippet(sections_fts, 3, '<mark>', '</mark>', '…', 40) AS snippet, rank FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ?${statute ? " AND s.statute = ?" : ""} ORDER BY ${order} LIMIT ? OFFSET ?`,
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
    this.acts = null;
    this.count = null;
    this.sha256 = null;
    this.fileSha256 = null;
    this.compression = null;
  }
}

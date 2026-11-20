import { z } from "zod";
import { defaultCorpusPath } from "#files";
import {
  CorpusError,
  checkCorpusSignal,
  corpusTimestamp,
  openCorpusSnapshot,
} from "./corpus/outline.js";
import { type CorpusProvenance, CorpusProvenanceSchema } from "./models.js";
import { env } from "./runtime/env.js";
import type { SnapshotDatabase } from "./runtime/sqlite.js";

/**
 * Reader for the INPI Argentina statutes corpus: Argentina's five IP statutes
 * in Spanish as Infoleg (the Ministry of Justice's legislative information
 * service) keeps them. Ley 24.481 de Patentes de Invención y Modelos de
 * Utilidad (t.o. Decreto 260/96), Ley 22.362 de Marcas y Designaciones,
 * Decreto-Ley 6673/63 de Modelos y Diseños Industriales, Ley 11.723 de
 * Propiedad Intelectual and Ley 24.766 de Confidencialidad. The texts are
 * Infoleg's updated texts (texto actualizado), not official Boletín Oficial
 * publications; Ley 24.766 is Infoleg's text as published. The SQLite/FTS5
 * snapshot is built by scripts/build-inpi-ar-statutes-corpus.ts;
 * scripts/inpi-ar-statutes-sources.json lists each page, its retrieval time
 * and hash.
 */
export const INPI_AR_STATUTES_SOURCE_URL = "https://www.infoleg.gob.ar/";
export const INPI_AR_STATUTES_SOURCE_NAME =
  "INPI Argentina — Statutes (Infoleg)";
/** Said wherever the texts are served, so callers do not take them for the gazette. */
export const INPI_AR_STATUTES_NOTICE =
  "Infoleg's updated texts (texto actualizado), not official Boletín Oficial publications; Ley 24.766 is Infoleg's text as published, since Infoleg keeps no updated text for it.";
const LABEL = "INPI Argentina statutes";
const ENV_PREFIX = "INPI_AR_STATUTES";

/** The five statute keys, in the order the corpus lists them. */
export const INPI_AR_STATUTE_KEYS = [
  "patents",
  "trademarks",
  "designs",
  "copyright",
  "trade_secrets",
] as const;
export type InpiArStatuteKey = (typeof INPI_AR_STATUTE_KEYS)[number];

/** Lowercase, accents folded, "Nº"/"N°" dropped, dots inside numbers removed, "-" and "/" as spaces. */
function normalizeName(name: string): string {
  return name
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/\(.*?\)/g, " ")
    .replace(/\bn(?:ro|um)?\s*[ºo°.]\s*/g, " ")
    .replace(/(\d)\.(?=\d{3}\b)/g, "$1")
    .replace(/[-/_,]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const ALIASES: Record<InpiArStatuteKey, string[]> = {
  patents: [
    "patents",
    "patent",
    "patent law",
    "patents law",
    "patentes",
    "ley de patentes",
    "ley de patentes de invencion y modelos de utilidad",
    "ley 24.481",
    "24.481",
    "lp",
  ],
  trademarks: [
    "trademarks",
    "trademark",
    "trade marks",
    "trade mark",
    "trademark law",
    "tm",
    "marcas",
    "ley de marcas",
    "ley de marcas y designaciones",
    "ley 22.362",
    "22.362",
  ],
  designs: [
    "designs",
    "design",
    "design law",
    "designs law",
    "industrial designs",
    "disenos",
    "disenos industriales",
    "modelos y disenos industriales",
    "decreto-ley 6673/63",
    "decreto ley 6673/63",
    "decreto-ley 6673",
    "dl 6673/63",
    "dto. ley 6673/63",
    "6673/63",
    "6673",
    "ley 16.478",
  ],
  copyright: [
    "copyright",
    "copyright law",
    "copyright act",
    "propiedad intelectual",
    "ley de propiedad intelectual",
    "derecho de autor",
    "ley 11.723",
    "11.723",
    "lpi",
  ],
  trade_secrets: [
    "trade_secrets",
    "trade secrets",
    "trade secret",
    "trade secrets law",
    "confidential information",
    "undisclosed information",
    "confidencialidad",
    "ley de confidencialidad",
    "informacion confidencial",
    "secretos comerciales",
    "ley 24.766",
    "24.766",
  ],
};

/** Names lawyers type, normalized, to the statute key. */
export const INPI_AR_STATUTE_ALIASES: Readonly<Record<string, string>> =
  Object.fromEntries(
    Object.entries(ALIASES).flatMap(([key, names]) =>
      names.map((name) => [normalizeName(name), key]),
    ),
  );

/** Statute key for a name, alias or law number; unknown names pass through normalized. */
export function resolveInpiArStatute(name: string): string {
  const key = normalizeName(name);
  return (
    INPI_AR_STATUTE_ALIASES[key] ??
    INPI_AR_STATUTE_ALIASES[key.replace(/^(?:la|el)\s+/, "")] ??
    key
  );
}

const SUFFIX =
  "bis|ter|qu[áa]ter|quinquies|sexies|septies|octies|nonies|novies|decies";

/**
 * Canonical article number: "4", "5 bis", "36 quáter". Accepts "4°", "4º",
 * "5bis", "5-bis", "36 quater"; null for anything else.
 */
export function normalizeInpiArArticle(value: string): string | null {
  const match = new RegExp(
    String.raw`^\s*(\d{1,3})\s*[º°ª]?\s*[-\s]?\s*(${SUFFIX})?\s*\.?\s*$`,
    "i",
  ).exec(value);
  if (!match?.[1]) return null;
  const suffix = match[2]?.toLowerCase();
  const canonical =
    suffix === "quater" ? "quáter" : suffix === "novies" ? "nonies" : suffix;
  return canonical
    ? `${Number(match[1])} ${canonical}`
    : String(Number(match[1]));
}

const NUMBER = String.raw`\d{1,3}\s*[º°ª]?(?:\s*[-\s]?\s*(?:${SUFFIX})\b)?`;
const UNIT = String.raw`(?:art[íi]culos?|arts?\.?|article|section|sec\.?|§+)`;
// Subdivisions after the number are dropped: "inc. a)", "inciso b", "(a)", "párrafo 2", "apartado II".
const SUBDIVISION = String.raw`(?:\s*,?\s*(?:inc(?:iso)?s?\.?\s*[a-zñ0-9]+\)?|\([a-zñ0-9]+\)|[a-zñ]\)|p[áa]rr(?:afo)?\.?\s*\w+|ap(?:artado)?\.?\s*[ivx\d]+))*`;
const FORWARD = new RegExp(
  String.raw`^\s*${UNIT}\s*(?<num>${NUMBER})${SUBDIVISION}\s*,?\s*(?:(?:de\s+la|del|de)\s+|of\s+(?:the\s+)?)?(?<statute>.+?)\s*$`,
  "i",
);
const REVERSE = new RegExp(
  String.raw`^\s*(?:the\s+|la\s+)?(?<statute>.+?)\s*,?\s+${UNIT}\s*(?<num>${NUMBER})${SUBDIVISION}\s*$`,
  "i",
);

/**
 * Parse a citation into a statute key and article number: 'Artículo 4 Ley
 * 24.481', 'art. 4 ley 24481', 'Ley 22.362 art. 3', 'Article 4 Patent Law',
 * 'Art. 5° bis de la Ley 11.723', 'art. 3 inc. a) Ley 22.362'. Subdivisions
 * are dropped (the whole article is returned). Null when the shape or the
 * statute is not recognized.
 */
export function parseInpiArCitation(
  citation: string,
): { statute: InpiArStatuteKey; section_number: string } | null {
  const cleaned = citation.trim();
  if (!cleaned) return null;
  for (const pattern of [FORWARD, REVERSE]) {
    const match = pattern.exec(cleaned);
    const num = match?.groups?.num;
    const name = match?.groups?.statute;
    if (!num || !name) continue;
    const statute = resolveInpiArStatute(name);
    const number = normalizeInpiArArticle(num);
    if (number && (INPI_AR_STATUTE_KEYS as readonly string[]).includes(statute))
      return { statute: statute as InpiArStatuteKey, section_number: number };
  }
  return null;
}

/**
 * FTS5 query with every term quoted, so caller input never runs as MATCH
 * syntax. With 'and' or 'or', a term ending in `*` is a prefix
 * (`patent*` finds patente, patentes, patentable), since the Spanish text
 * is not stemmed.
 */
export function inpiArFtsQuery(
  query: string,
  syntax: "adj" | "exact" | "and" | "or",
): string {
  const clean = query.trim();
  if (!clean) return "";
  const quote = (value: string) => `"${value.replaceAll('"', '""')}"`;
  if (syntax === "adj" || syntax === "exact") return quote(clean);
  return clean
    .split(/\s+/)
    .map((term) => {
      const stem = term.replace(/\*+$/, "");
      return stem && stem !== term ? `${quote(stem)}*` : quote(term);
    })
    .join(syntax === "or" ? " OR " : " ");
}

/** One statute as the corpus carries it, with the Infoleg source it was built from. */
export const InpiArStatuteSchema = z.object({
  statute: z.string(),
  section_count: z.number().int(),
  /** The Infoleg text page the articles were parsed from. */
  source_url: z.string().nullable(),
  /** Citation name, e.g. 'Ley 24.481'. */
  short_name: z.string().nullable(),
  title: z.string().nullable(),
  /** Infoleg's norm page (verNorma.do). */
  norm_url: z.string().nullable(),
  /** 'texact' (Infoleg's updated text) or 'norma' (the text as published). */
  text_kind: z.enum(["texact", "norma"]).nullable(),
  /** The norm and its Boletín Oficial publication, as Infoleg describes it. */
  version: z.string().nullable(),
  /** The newest Boletín Oficial date cited in the statute's amendment notes. */
  newest_note_date: z.string().nullable(),
  text_sha256: z.string().nullable(),
  retrieved_at: z.string().nullable(),
});
export type InpiArStatute = z.infer<typeof InpiArStatuteSchema>;

/** One article of an Argentine IP statute. */
export const InpiArSectionSchema = z.object({
  statute: z.string(),
  /** '4', '5 bis', '36 quáter'. */
  section_number: z.string(),
  /** Citation-ready label, e.g. 'Artículo 4° Ley 24.481'. */
  section_label: z.string(),
  /** The Título / Capítulo / Sección headings the article sits under. */
  title: z.string().nullable(),
  /** One paragraph per line; Infoleg's amendment notes follow a blank line. */
  text: z.string(),
  source_url: z.string().nullable(),
  provenance: CorpusProvenanceSchema,
});
export type InpiArSection = z.infer<typeof InpiArSectionSchema>;

export const InpiArSearchHitSchema = z.object({
  statute: z.string(),
  section_number: z.string(),
  section_label: z.string(),
  title: z.string().nullable(),
  /** FTS5 snippet with <mark>…</mark> around matched terms. */
  snippet: z.string(),
  /** BM25 rank (lower is more relevant) with sort='relevance'. */
  rank: z.number().nullable(),
});
export type InpiArSearchHit = z.infer<typeof InpiArSearchHitSchema>;

export interface InpiArStatutesCorpusStatus {
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
  /** What the texts are: Infoleg's updated texts, not the official gazette. */
  notice: string;
  /** Per-statute source and version, or null for a corpus built without them. */
  statutes: InpiArStatute[] | null;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
export interface InpiArSearchResponse {
  query: string;
  /** The resolved statute filter, or null for all five. */
  statute: string | null;
  hits: InpiArSearchHit[];
  page: number;
  per_page: number;
  has_more: boolean;
  provenance: CorpusProvenance;
  corpus: InpiArStatutesCorpusStatus;
}
export interface InpiArCorpusMeta {
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

export interface InpiArStatutesClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also INPI_AR_STATUTES_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed; also INPI_AR_STATUTES_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
}
export type InpiArStatutesSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};

const statuteMeta = z.object({
  statute: z.string(),
  short_name: z.string(),
  title: z.string(),
  infoleg_id: z.string(),
  norm_url: z.string(),
  norm_heading: z.string(),
  norm_published: z.string().nullable(),
  text_kind: z.enum(["texact", "norma"]),
  text_url: z.string(),
  text_sha256: z.string(),
  retrieved_at: z.string(),
  newest_note_date: z.string().nullable(),
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
      "Unsupported INPI Argentina statutes corpus schema; the supported version is 1.",
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
    !/\bremove_diacritics\s+2\b/i.test(fts.sql) ||
    JSON.stringify(columns) !==
      JSON.stringify(["statute", "section_label", "title", "text"]) ||
    count === undefined
  )
    throw new Error();
  return { metadata, count };
}

/**
 * Outline order: statutes as listed, then article number, then the Latin
 * insertion suffix in sequence ("5" < "5 bis" < "5 ter" < "5 quáter" < "6" < "10").
 */
const OUTLINE_ORDER = `CASE s.statute ${INPI_AR_STATUTE_KEYS.map((key, i) => `WHEN '${key}' THEN ${i}`).join(" ")} ELSE ${INPI_AR_STATUTE_KEYS.length} END, CAST(s.section_number AS INTEGER), CASE WHEN instr(s.section_number, ' ') = 0 THEN 0 ELSE instr('|bis|ter|quáter|quinquies|sexies|septies|octies|nonies|decies|', '|' || substr(s.section_number, instr(s.section_number, ' ') + 1) || '|') END, s.section_number`;

/**
 * Read-only reader for the INPI Argentina statutes snapshot. It never
 * downloads or rebuilds the corpus. Lookups that find nothing return null.
 */
export class InpiArStatutesClient {
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
  private readonly source: InpiArStatutesClientOptions["source"];
  private readonly expectedSha256: string | undefined;
  private readonly expectedFileSha256: string | undefined;

  constructor(options: InpiArStatutesClientOptions = {}) {
    this.path =
      options.corpusPath ??
      env(`${ENV_PREFIX}_CORPUS_PATH`) ??
      defaultCorpusPath("inpi_ar_statutes.db") ??
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
        `The INPI Argentina statutes ${what} is not readable.`,
      );
    }
  }

  private statuteList(): InpiArStatute[] {
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
      const index = (INPI_AR_STATUTE_KEYS as readonly string[]).indexOf(key);
      return index < 0 ? INPI_AR_STATUTE_KEYS.length : index;
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
          source_url: info?.text_url ?? row.source_url,
          short_name: info?.short_name ?? null,
          title: info?.title ?? null,
          norm_url: info?.norm_url ?? null,
          text_kind: info?.text_kind ?? null,
          version: info
            ? `${info.norm_heading}${info.norm_published ? `, ${info.norm_published}` : ""}; ${info.text_kind === "texact" ? "Infoleg updated text (texto actualizado)" : "Infoleg text as published (no updated text kept)"}`
            : null,
          newest_note_date: info?.newest_note_date ?? null,
          text_sha256: info?.text_sha256 ?? null,
          retrieved_at: info?.retrieved_at ?? null,
        };
      });
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): InpiArStatutesCorpusStatus {
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
      source_url: INPI_AR_STATUTES_SOURCE_URL,
      notice: metadata.notice ?? INPI_AR_STATUTES_NOTICE,
      statutes: available && this.statuteInfo ? this.statuteList() : null,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(corpus: InpiArStatutesCorpusStatus): CorpusProvenance {
    return {
      source_url: INPI_AR_STATUTES_SOURCE_URL,
      source_name: INPI_AR_STATUTES_SOURCE_NAME,
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
  async getCorpusStatus(): Promise<InpiArStatutesCorpusStatus> {
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
  ): Promise<InpiArCorpusMeta> {
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
  ): Promise<InpiArStatute[]> {
    await this.ready(options.signal);
    return this.statuteList();
  }

  /** One article by statute (key, alias or law number) and number ('4', '5 bis'); null when absent. */
  async getSection(
    statute: string,
    sectionNumber: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<InpiArSection | null> {
    const key = resolveInpiArStatute(text(200).parse(statute));
    const number = normalizeInpiArArticle(text(30).parse(sectionNumber));
    const corpus = await this.ready(options.signal);
    if (!number) return null;
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
        "The INPI Argentina statutes section text is not readable.",
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

  /** One article by citation ('Artículo 4 Ley 24.481', 'Ley 22.362 art. 3'); null when unparseable or absent. */
  async getSectionByCitation(
    citation: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<InpiArSection | null> {
    const parsed = parseInpiArCitation(text(500).parse(citation));
    if (!parsed) return null;
    return this.getSection(parsed.statute, parsed.section_number, options);
  }

  /**
   * Full-text search over all five statutes, or one with `statute`. Terms are
   * always quoted as FTS5 text, so caller input never runs as MATCH syntax.
   */
  async search(
    options: InpiArStatutesSearchOptions,
  ): Promise<InpiArSearchResponse> {
    const input = searchOptions.parse(options);
    const statute = input.statute ? resolveInpiArStatute(input.statute) : null;
    const corpus = await this.ready(options.signal);
    const match = inpiArFtsQuery(input.query, input.syntax);
    const bind: (string | number)[] = [match];
    if (statute) bind.push(statute);
    // BM25 ties fall back to row order so pages are stable.
    const order = input.sort === "outline" ? OUTLINE_ORDER : "rank, s.rowid";
    const rows = match
      ? this.query<InpiArSearchHit>(
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

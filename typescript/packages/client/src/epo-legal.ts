import { createHash } from "node:crypto";
import { homedir } from "node:os";
import { join } from "node:path";
import { z } from "zod";
import {
  CorpusError,
  checkCorpusSignal,
  corpusTimestamp,
  OutlineCorpus,
  type OutlineHit,
  outlineFtsQuery,
} from "./corpus/outline.js";
import type { CorpusProvenance } from "./models.js";

const origin = "https://www.epo.org";
const reference = z
  .string()
  .trim()
  .min(1)
  .max(2048)
  .refine((value) => !value.includes("\0"), "References must not contain NUL.");
const versionOption = z.string().min(1).max(100);
const searchOptions = z.object({
  query: z
    .string()
    .max(8192)
    .refine((value) => !value.includes("\0"), "Queries must not contain NUL."),
  version: versionOption.default("current"),
  syntax: z.enum(["adj", "exact", "and", "or"]).default("adj"),
  sort: z.enum(["relevance", "outline"]).default("relevance"),
  limit: z.number().int().min(1).max(100).default(10),
  offset: z.number().int().min(0).safe().default(0),
});
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);

/** Article/Rule identity for an EPC slug such as `a54` or `r71`. */
export interface EpcCitation {
  kind: "article" | "rule";
  number: string;
}
/** Case Law Book position for a slug such as `clr_i_a_1`; unnumbered front/back matter has none. */
export interface CaseLawCitation {
  part: string;
  subpart: string | null;
  section: string | null;
}
/** Guidelines position for a slug such as `g_ii_3_1` (Part G, Chapter II, section 3.1). */
export interface GuidelinesCitation {
  part: string;
  chapter: string | null;
  section: string | null;
}
/** Unitary Patent Guidelines position for a slug such as `section_1_2_1`. */
export interface UpGuidelinesCitation {
  section: string;
}

interface Lookup {
  column: "href" | "section_number";
  value: string;
}
/** One epo.org/en/legal book; the five books differ in citation syntax and slug shape. */
export interface EpoLegalBook<C> {
  label: string;
  sourceName: string;
  /** URL segment under https://www.epo.org/en/legal/. */
  book: string;
  /** Meta key in which the Python builder records the crawled edition year. */
  editionKey: string;
  envPrefix: string;
  filename: string;
  /** Hit URLs end in .html except in the UP Guidelines. */
  resultSuffix: string;
  pathLabel(chapter: string): string;
  /** Citation-derived lookups tried before the normalized href. */
  lookups(reference: string): Lookup[];
  citation(href: string): C | null;
}

export interface EpoLegalClientOptions {
  corpusPath?: string;
  /** SHA-256 of the decoded standalone SQLite bytes; also <PREFIX>_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed on disk; also <PREFIX>_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
  maxSectionBytes?: number;
}
export type EpoLegalSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};
export interface EpoLegalSectionOptions {
  version?: string;
  signal?: AbortSignal;
}
export interface EpoLegalCorpusStatus {
  available: boolean;
  label: string;
  book: string;
  /** Edition year the build recorded for its crawl path, or null. */
  edition: string | null;
  corpus_version: string;
  /** No release check exists for these books; the edition label is unverified. */
  release_verified: false;
  schema_version: number | null;
  section_count: number | null;
  snapshot_date: string | null;
  corpus_synced_at: string | null;
  artifact_sha256: string | null;
  file_sha256: string | null;
  compression: "none" | "zstd" | null;
  source_url: string;
  metadata: Record<string, string>;
  error?: { code: string; message: string };
}
export interface EpoLegalSearchHit {
  title: string;
  section_number: string | null;
  chapter: string | null;
  href: string;
  path: string[];
  result_url: string;
  snippet: string;
}
export interface EpoLegalSearchResponse {
  hits: EpoLegalSearchHit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: EpoLegalCorpusStatus;
}
export interface EpoLegalSection<C> {
  href: string;
  section_number: string | null;
  title: string | null;
  chapter: string | null;
  citation: C | null;
  html: string;
  text: string;
  version: string;
  edition: string | null;
  source_url: string;
  content_sha256: string;
  corpus_metadata: Record<string, string>;
  provenance: CorpusProvenance;
}
export interface EpoLegalVersion {
  label: string;
  value: string;
  /** This entry is installed, not a claim that it is the latest EPO edition. */
  current: boolean;
}

/** Reduce a slug, `/en/legal/<book>/<year>/<slug>.html` path, or URL to the slug. */
export function normalizeEpoHref(value: string, book: string): string {
  let href = value.trim();
  const url = /^https?:\/\/[^/]+\/?(.*)$/i.exec(href);
  if (url) href = url[1] ?? "";
  href = href.replace(/^\/+/, "");
  const escaped = book.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  href = href.replace(new RegExp(`^(?:en/)?legal/${escaped}/\\d{4}/`), "");
  return href.replace(/\.html$/, "").toLowerCase();
}

const epcCitation = /^\s*(article|art\.?|a|rule|r\.?)\s*(\d+[a-z]?)\s*$/i;
const caseLawCitation =
  /^\s*([IVX]+)(?:[-_\s.,]+([A-Z])(?:[-_\s.,]+([\dA-Z]+(?:[-_\s.,]+[\dA-Z]+)*))?)?\s*$/i;
const guidelinesCitation =
  /^\s*([A-H])(?:[-_\s.,]+([IVX]+)(?:[-_\s.,]+(\d+(?:[._-]\d+)*))?)?\s*$/i;
const upCitation = /^\s*(?:section\s+|§\s*)?(\d+(?:[._\s-]\d+)*)\s*$/i;

function epcSlug(value: string): string | null {
  const match = epcCitation.exec(value);
  if (!match) return null;
  const kind = (match[1] ?? "").toLowerCase().replace(/\.$/, "");
  return `${["article", "art", "a"].includes(kind) ? "a" : "r"}${(match[2] ?? "").toLowerCase()}`;
}
function epcCitationFor(href: string): EpcCitation | null {
  const match = /^([ar])(\d+[a-z]?)$/i.exec(href);
  if (!match) return null;
  return {
    kind: match[1]?.toLowerCase() === "a" ? "article" : "rule",
    number: match[2] ?? "",
  };
}
function caseLawSlug(value: string): string | null {
  const match = caseLawCitation.exec(value);
  if (!match) return null;
  let slug = `clr_${(match[1] ?? "").toLowerCase()}`;
  if (match[2]) slug += `_${match[2].toLowerCase()}`;
  if (match[3]) slug += `_${match[3].replace(/[-\s.,]+/g, "_").toLowerCase()}`;
  return slug;
}
function caseLawCitationFor(href: string): CaseLawCitation | null {
  const match = /^clr_([ivx]+)(?:_([a-z]))?((?:_[a-z\d]+)*)$/i.exec(href);
  if (!match) return null;
  const chain = (match[3] ?? "").split("_").filter(Boolean);
  return {
    part: (match[1] ?? "").toUpperCase(),
    subpart: match[2]?.toUpperCase() ?? null,
    section: chain.length ? chain.join(".").toUpperCase() : null,
  };
}
function caseLawNumber(href: string): string | null {
  const citation = caseLawCitationFor(href);
  if (!citation) return null;
  return [citation.part, citation.subpart, citation.section]
    .filter(Boolean)
    .join(".");
}
function guidelinesSlug(value: string): string | null {
  const match = guidelinesCitation.exec(value);
  if (!match) return null;
  let slug = (match[1] ?? "").toLowerCase();
  if (match[2]) slug += `_${match[2].toLowerCase()}`;
  if (match[3]) slug += `_${match[3].replace(/[.,-]/g, "_")}`;
  return slug;
}
function guidelinesCitationFor(href: string): GuidelinesCitation | null {
  const match = /^([a-h])(?:_([ivx]+)((?:_\d+)*))?$/i.exec(href);
  if (!match) return null;
  const chain = (match[3] ?? "").split("_").filter(Boolean);
  return {
    part: (match[1] ?? "").toUpperCase(),
    chapter: match[2]?.toUpperCase() ?? null,
    section: chain.length ? chain.join(".") : null,
  };
}
/** `g_ii_3_1` → `G-II, 3.1`, the form the corpus stores as section_number. */
function guidelinesNumber(href: string): string | null {
  const citation = guidelinesCitationFor(href);
  if (!citation) return null;
  if (!citation.chapter) return citation.part;
  const head = `${citation.part}-${citation.chapter}`;
  return citation.section ? `${head}, ${citation.section}` : head;
}
function upSlug(value: string): string | null {
  const match = upCitation.exec(value);
  return match ? `section_${(match[1] ?? "").replace(/[._\s-]+/g, "_")}` : null;
}
function upCitationFor(href: string): UpGuidelinesCitation | null {
  const match = /^section((?:_\d+)+)$/i.exec(href);
  return match
    ? { section: (match[1] ?? "").split("_").filter(Boolean).join(".") }
    : null;
}

function lookups(
  slug: string | null,
  number: (slug: string) => string | null,
): Lookup[] {
  if (!slug) return [];
  const sectionNumber = number(slug);
  return [
    { column: "href", value: slug },
    ...(sectionNumber
      ? [{ column: "section_number" as const, value: sectionNumber }]
      : []),
  ];
}
function guidelinesBook(
  label: string,
  sourceName: string,
  book: string,
  envPrefix: string,
  filename: string,
): EpoLegalBook<GuidelinesCitation> {
  return {
    label,
    sourceName,
    book,
    editionKey: "guidelines_year",
    envPrefix,
    filename,
    resultSuffix: ".html",
    pathLabel: (chapter) => `Part ${chapter}`,
    lookups: (value) => lookups(guidelinesSlug(value), guidelinesNumber),
    citation: guidelinesCitationFor,
  };
}

export const EPC_BOOK: EpoLegalBook<EpcCitation> = {
  label: "EPC",
  sourceName: "European Patent Convention",
  book: "epc",
  editionKey: "epc_year",
  envPrefix: "EPC",
  filename: "epc.db",
  resultSuffix: ".html",
  pathLabel: (chapter) => chapter,
  lookups: (value) =>
    lookups(epcSlug(value), (slug) => {
      const citation = epcCitationFor(slug);
      return citation
        ? `${citation.kind === "article" ? "Article" : "Rule"} ${citation.number}`
        : null;
    }),
  citation: epcCitationFor,
};
export const EPO_CASE_LAW_BOOK: EpoLegalBook<CaseLawCitation> = {
  label: "EPO Case Law",
  sourceName: "EPO Boards of Appeal Case Law Compendium",
  book: "case-law",
  editionKey: "caselaw_year",
  envPrefix: "CASELAW",
  filename: "caselaw.db",
  resultSuffix: ".html",
  pathLabel: (chapter) => chapter,
  lookups: (value) => lookups(caseLawSlug(value), caseLawNumber),
  citation: caseLawCitationFor,
};
export const EPO_GUIDELINES_BOOK = guidelinesBook(
  "EPO Guidelines",
  "EPO Guidelines for Examination",
  "guidelines-epc",
  "GUIDELINES",
  "guidelines.db",
);
export const EPO_PCT_GUIDELINES_BOOK = guidelinesBook(
  "PCT-EPO Guidelines",
  "PCT-EPO Guidelines for Examination",
  "guidelines-pct",
  "PCT_GUIDELINES",
  "pct_guidelines.db",
);
export const EPO_UP_GUIDELINES_BOOK: EpoLegalBook<UpGuidelinesCitation> = {
  label: "UP Guidelines",
  sourceName: "Unitary Patent Guidelines",
  book: "guidelines-up",
  editionKey: "up_guidelines_year",
  envPrefix: "UP_GUIDELINES",
  filename: "up_guidelines.db",
  resultSuffix: "",
  pathLabel: (chapter) => `Section ${chapter}`,
  lookups: (value) =>
    lookups(upSlug(value), (slug) => upCitationFor(slug)?.section ?? null),
  citation: upCitationFor,
};

/** Read-only reader for one epo.org/en/legal book snapshot; never crawls or refreshes. */
export class EpoLegalCorpusClient<C> {
  private readonly corpus: OutlineCorpus;
  private readonly maxSectionBytes: number;
  constructor(
    readonly book: EpoLegalBook<C>,
    options: EpoLegalClientOptions = {},
  ) {
    const prefix = book.envPrefix;
    const path =
      options.corpusPath ??
      process.env[`${prefix}_CORPUS_PATH`] ??
      join(homedir(), ".cache", "patent_client_agents", book.filename);
    reference.parse(path);
    const pin = (value: string | undefined) =>
      value === undefined ? undefined : sha256Pin.parse(value);
    const expectedSha256 = pin(
      options.expectedSha256 ?? process.env[`${prefix}_CORPUS_SHA256`],
    );
    const expectedFileSha256 = pin(
      options.expectedFileSha256 ?? process.env[`${prefix}_CORPUS_FILE_SHA256`],
    );
    this.maxSectionBytes = z
      .number()
      .int()
      .positive()
      .safe()
      .parse(options.maxSectionBytes ?? 16 * 1024 * 1024);
    this.corpus = new OutlineCorpus({
      path,
      label: book.label,
      envVar: `${prefix}_CORPUS_PATH`,
      maxSectionBytes: this.maxSectionBytes,
      ...(expectedSha256 ? { expectedSha256 } : {}),
      ...(expectedFileSha256 ? { expectedFileSha256 } : {}),
    });
  }

  private root() {
    return `${origin}/en/legal/${this.book.book}`;
  }

  /** Edition from the recorded year, else from the build's exact epo.org source path. */
  private edition(metadata: Record<string, string>): string | null {
    const recorded = metadata[this.book.editionKey];
    if (recorded && /^\d{4}$/.test(recorded)) return recorded;
    const source = metadata.source ?? "";
    return source.startsWith(`${this.root()}/`)
      ? (/^(\d{4})$/.exec(source.slice(this.root().length + 1))?.[1] ?? null)
      : null;
  }

  private url(edition: string | null, href?: string) {
    if (!edition) return this.root();
    return href
      ? `${this.root()}/${edition}/${encodeURIComponent(href)}${this.book.resultSuffix}`
      : `${this.root()}/${edition}`;
  }

  private status(
    available: boolean,
    error?: CorpusError,
  ): EpoLegalCorpusStatus {
    const metadata = { ...this.corpus.metadata };
    const edition = this.edition(metadata);
    return {
      available,
      label: this.book.label,
      book: this.book.book,
      edition,
      corpus_version: edition ?? "unknown",
      release_verified: false,
      schema_version: metadata.schema_version
        ? Number(metadata.schema_version)
        : null,
      section_count: this.corpus.sectionCount,
      snapshot_date: metadata.snapshot_date ?? null,
      corpus_synced_at:
        corpusTimestamp(metadata.synced_at) ??
        corpusTimestamp(metadata.snapshot_date),
      artifact_sha256: this.corpus.sha256,
      file_sha256: this.corpus.fileSha256,
      compression: this.corpus.compression,
      source_url: this.url(edition),
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(
    corpus: EpoLegalCorpusStatus,
    sourceUrl: string,
  ): CorpusProvenance {
    return {
      source_url: sourceUrl,
      source_name: this.book.sourceName,
      retrieved_at: corpus.corpus_synced_at,
      accessed_at: new Date().toISOString(),
      cache_hit: true,
      corpus_synced_at: corpus.corpus_synced_at,
      corpus_version: corpus.corpus_version,
    };
  }

  private async ready(version = "current", signal?: AbortSignal) {
    checkCorpusSignal(signal);
    versionOption.parse(version);
    await this.corpus.open();
    checkCorpusSignal(signal);
    const status = this.status(true);
    if (
      version !== "current" &&
      (status.edition === null || version !== status.edition)
    )
      throw new CorpusError(
        "VERSION_UNAVAILABLE",
        `The requested ${this.book.label} edition is not installed. current selects the installed snapshot only.`,
      );
    return status;
  }

  async getCorpusStatus(): Promise<EpoLegalCorpusStatus> {
    try {
      await this.corpus.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  async search(
    options: EpoLegalSearchOptions,
  ): Promise<EpoLegalSearchResponse> {
    const input = searchOptions.parse(options);
    const corpus = await this.ready(input.version, options.signal);
    const query = outlineFtsQuery(input.query, input.syntax);
    const rows = query
      ? this.corpus.search(query, input.limit + 1, input.offset, input.sort)
      : [];
    checkCorpusSignal(options.signal);
    const hits = rows.slice(0, input.limit).map(
      (row: OutlineHit): EpoLegalSearchHit => ({
        title:
          row.section_number && row.title
            ? `${row.section_number} - ${row.title}`
            : (row.title ?? row.section_number ?? ""),
        section_number: row.section_number,
        chapter: row.chapter,
        href: row.href,
        path: [
          ...(row.chapter ? [this.book.pathLabel(row.chapter)] : []),
          ...(row.section_number ? [row.section_number] : []),
        ],
        result_url: this.url(corpus.edition, row.href),
        snippet: row.snippet,
      }),
    );
    return {
      hits,
      has_more: rows.length > input.limit,
      offset: input.offset,
      limit: input.limit,
      provenance: this.provenance(corpus, this.url(corpus.edition)),
      corpus,
    };
  }

  async getSection(
    section: string,
    options: EpoLegalSectionOptions = {},
  ): Promise<EpoLegalSection<C>> {
    const value = reference.parse(section);
    const corpus = await this.ready(options.version, options.signal);
    const attempts = [
      ...this.book.lookups(value),
      {
        column: "href" as const,
        value: normalizeEpoHref(value, this.book.book),
      },
    ];
    let row = null;
    for (const lookup of attempts) {
      row = this.corpus.section(
        lookup.value,
        lookup.column === "section_number",
      );
      if (row) break;
    }
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `The requested ${this.book.label} section was not found in the installed corpus.`,
      );
    const html = await this.corpus.text(row.html, "html");
    const text = await this.corpus.text(row.text, "text");
    if (
      Buffer.byteLength(html) + Buffer.byteLength(text) >
      this.maxSectionBytes
    )
      throw new CorpusError(
        "SECTION_TOO_LARGE",
        "Corpus section exceeds the configured decoded-byte limit.",
      );
    checkCorpusSignal(options.signal);
    const sourceUrl = this.url(corpus.edition, row.href);
    return {
      href: row.href,
      section_number: row.section_number,
      title: row.title,
      chapter: row.chapter,
      citation: this.book.citation(row.href),
      html,
      text,
      version: corpus.corpus_version,
      edition: corpus.edition,
      source_url: sourceUrl,
      content_sha256: createHash("sha256").update(html).digest("hex"),
      corpus_metadata: corpus.metadata,
      provenance: this.provenance(corpus, sourceUrl),
    };
  }

  async resolveSectionHref(
    section: string,
    options: EpoLegalSectionOptions = {},
  ): Promise<string | null> {
    const value = reference.parse(section);
    await this.ready(options.version, options.signal);
    return this.corpus.section(value, true)?.href ?? null;
  }

  async listVersions(): Promise<EpoLegalVersion[]> {
    const status = await this.ready();
    return [
      {
        label: `${this.book.label} ${status.edition ?? "unknown"} edition (installed snapshot ${status.snapshot_date ?? "unknown"})`,
        value: status.edition ?? "current",
        current: true,
      },
    ];
  }

  close() {
    this.corpus.close();
  }
}

export class EpcClient extends EpoLegalCorpusClient<EpcCitation> {
  constructor(options: EpoLegalClientOptions = {}) {
    super(EPC_BOOK, options);
  }
}
export class EpoCaseLawClient extends EpoLegalCorpusClient<CaseLawCitation> {
  constructor(options: EpoLegalClientOptions = {}) {
    super(EPO_CASE_LAW_BOOK, options);
  }
}
export class EpoGuidelinesClient extends EpoLegalCorpusClient<GuidelinesCitation> {
  constructor(options: EpoLegalClientOptions = {}) {
    super(EPO_GUIDELINES_BOOK, options);
  }
}
export class EpoPctGuidelinesClient extends EpoLegalCorpusClient<GuidelinesCitation> {
  constructor(options: EpoLegalClientOptions = {}) {
    super(EPO_PCT_GUIDELINES_BOOK, options);
  }
}
export class EpoUpGuidelinesClient extends EpoLegalCorpusClient<UpGuidelinesCitation> {
  constructor(options: EpoLegalClientOptions = {}) {
    super(EPO_UP_GUIDELINES_BOOK, options);
  }
}

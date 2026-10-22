import { z } from "zod";
import { defaultCorpusPath } from "#files";
import {
  CorpusError,
  checkCorpusSignal,
  OutlineCorpus,
  type OutlineHit,
  type OutlineRow,
  outlineFtsQuery,
  corpusTimestamp as timestamp,
} from "./corpus/outline.js";
import type { CorpusProvenance } from "./models.js";
import { byteLength, env, sha256Hex } from "./runtime/env.js";

const source = "https://www.gov.uk";
export const MOPP_INDEX_URL = `${source}/guidance/manual-of-patent-practice-mopp`;
const sourceName = "UKIPO Manual of Patent Practice (MoPP)";
/** Python's MoPP SECTION_NUMBER_PATTERN: 1, 4A, 102A, 1.07, 14.99(a). */
export const MOPP_SECTION_NUMBER =
  /^\d+[a-z]?(?:\.\d+)?(?:\.\d+)?(?:\([a-z]\))?(?:\(\d+\))?$/i;
/** Section number in a gov.uk slug: `section-14-...`, `-section-4a-...`, `sections-11-...`. */
const SLUG_NUMBER = /^-?sections?-(\d+[a-z]?)(?:-|$)/i;
const reference = z
  .string()
  .trim()
  .min(1)
  .max(2048)
  .refine((value) => !value.includes("\0"), "References must not contain NUL.");
const versionOption = z.string().min(1).max(100);
const sha256Pin = z.string().regex(/^[a-f\d]{64}$/i);
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

export interface MoppClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also MOPP_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed on disk; also MOPP_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
  maxSectionBytes?: number;
}
export type MoppSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};
export interface MoppSectionOptions {
  /** Only `current` (the installed snapshot) is accepted. */
  version?: string;
  signal?: AbortSignal;
}
export interface MoppCorpusStatus {
  available: boolean;
  /** A recorded release label, else Python's `snapshot-<date>`, else `unknown`. */
  corpus_version: string;
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
export interface MoppSearchHit {
  title: string;
  section_number: string | null;
  href: string;
  path: string[];
  result_url: string;
  snippet: string;
}
export interface MoppSearchResponse {
  hits: MoppSearchHit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: MoppCorpusStatus;
}
export interface MoppSection {
  href: string;
  section_number: string | null;
  title: string | null;
  html: string;
  text: string;
  version: string;
  source_url: string;
  content_sha256: string;
  corpus_metadata: Record<string, string>;
  provenance: CorpusProvenance;
}
export interface MoppVersion {
  label: string;
  value: string;
  /** This entry is installed, not a claim that it is the latest UKIPO text. */
  current: boolean;
}

function corpusVersion(metadata: Record<string, string>): string {
  const value = metadata.source_version;
  if (value && value !== "current" && value !== "unknown") return value;
  // gov.uk publishes no MoPP revision tag; Python labels by snapshot date.
  return metadata.snapshot_date
    ? `snapshot-${metadata.snapshot_date}`
    : "unknown";
}
/** The stored gov.uk slug, kept as is: `-section-4a-...` is the live URL. */
export const moppResultUrl = (href?: string) =>
  href ? `${MOPP_INDEX_URL}/${encodeURI(href)}` : MOPP_INDEX_URL;
/** The stored section number, else one read from the slug (`sections-11-...`). */
function sectionNumber(row: Pick<OutlineRow, "href" | "section_number">) {
  return (
    row.section_number ??
    row.href.match(SLUG_NUMBER)?.[1]?.toUpperCase() ??
    null
  );
}
/** A bare slug from a slug, a gov.uk path or a gov.uk URL (query and fragment dropped). */
export function normalizeMoppHref(value: string): string {
  let href = value.trim();
  if (/^https?:\/\//i.test(href)) {
    try {
      href = new URL(href).pathname;
    } catch {
      // Left as given; the lookup reports it as not found.
    }
  }
  href = href.replace(/[?#].*$/s, "").replace(/^\/+|\/+$/g, "");
  const prefix = "guidance/manual-of-patent-practice-mopp/";
  if (href.startsWith(prefix)) href = href.slice(prefix.length);
  return href.replace(/\.html$/, "");
}

/** Read-only MoPP snapshot reader; never acquires or refreshes an artifact. */
export class MoppClient {
  private readonly corpus: OutlineCorpus;
  private readonly maxSectionBytes: number;
  constructor(options: MoppClientOptions = {}) {
    const path =
      options.corpusPath ??
      env("MOPP_CORPUS_PATH") ??
      defaultCorpusPath("mopp.db") ??
      "";
    if (!options.source) reference.parse(path);
    const pin = (value: string | undefined) =>
      value === undefined ? undefined : sha256Pin.parse(value);
    const expectedSha256 = pin(
      options.expectedSha256 ?? env("MOPP_CORPUS_SHA256"),
    );
    const expectedFileSha256 = pin(
      options.expectedFileSha256 ?? env("MOPP_CORPUS_FILE_SHA256"),
    );
    this.maxSectionBytes = z
      .number()
      .int()
      .positive()
      .safe()
      .parse(options.maxSectionBytes ?? 16 * 1024 * 1024);
    this.corpus = new OutlineCorpus({
      path,
      source: options.source,
      label: "MoPP",
      envVar: "MOPP_CORPUS_PATH",
      maxSectionBytes: this.maxSectionBytes,
      ...(expectedSha256 ? { expectedSha256 } : {}),
      ...(expectedFileSha256 ? { expectedFileSha256 } : {}),
    });
  }

  private status(available: boolean, error?: CorpusError): MoppCorpusStatus {
    const metadata = { ...this.corpus.metadata };
    return {
      available,
      corpus_version: available ? corpusVersion(metadata) : "unknown",
      schema_version: metadata.schema_version
        ? Number(metadata.schema_version)
        : null,
      section_count: this.corpus.sectionCount,
      snapshot_date: metadata.snapshot_date ?? null,
      corpus_synced_at:
        timestamp(metadata.synced_at) ?? timestamp(metadata.snapshot_date),
      artifact_sha256: this.corpus.sha256,
      file_sha256: this.corpus.fileSha256,
      compression: this.corpus.compression,
      source_url: MOPP_INDEX_URL,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(
    corpus: MoppCorpusStatus,
    sourceUrl: string,
  ): CorpusProvenance {
    return {
      source_url: sourceUrl,
      source_name: sourceName,
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
    // Python echoes any version back; only the installed snapshot exists.
    if (version !== "current")
      throw new CorpusError(
        "VERSION_UNAVAILABLE",
        "Only the installed MoPP snapshot (current) is available.",
      );
    await this.corpus.open();
    checkCorpusSignal(signal);
    return this.status(true);
  }

  async getCorpusStatus(): Promise<MoppCorpusStatus> {
    try {
      await this.corpus.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  async search(options: MoppSearchOptions): Promise<MoppSearchResponse> {
    const input = searchOptions.parse(options);
    const corpus = await this.ready(input.version, options.signal);
    const query = outlineFtsQuery(input.query, input.syntax);
    const rows = query
      ? this.corpus.search(query, input.limit + 1, input.offset, input.sort)
      : [];
    checkCorpusSignal(options.signal);
    const hits = rows.slice(0, input.limit).map((row: OutlineHit) => {
      const number = sectionNumber(row);
      return {
        title:
          number && row.title
            ? `${number} - ${row.title}`
            : (row.title ?? number ?? ""),
        section_number: number,
        href: row.href,
        path: number ? [number] : [],
        result_url: moppResultUrl(row.href),
        snippet: row.snippet,
      } satisfies MoppSearchHit;
    });
    return {
      hits,
      has_more: rows.length > input.limit,
      offset: input.offset,
      limit: input.limit,
      provenance: this.provenance(corpus, MOPP_INDEX_URL),
      corpus,
    };
  }

  /** The row for a section number, falling back to its page for a paragraph citation. */
  private byNumber(value: string): OutlineRow | null {
    const exact = value.toUpperCase();
    const page = exact.match(/^\d+[A-Z]?/)?.[0] ?? exact;
    for (const candidate of new Set([exact, page])) {
      const row = this.corpus.section(candidate, true);
      if (row) return row;
    }
    // A page whose builder slug did not yield a number (`sections-11-...`).
    const href = this.corpus
      .hrefs()
      .find((h) => h.match(SLUG_NUMBER)?.[1]?.toUpperCase() === page);
    return href ? this.corpus.section(href, false) : null;
  }

  private byHref(value: string): OutlineRow | null {
    const href = normalizeMoppHref(value);
    if (!href) return null;
    // gov.uk serves section 4A at `-section-4a-...`; accept it with or without the dash.
    const alternate = href.startsWith("-") ? href.slice(1) : `-${href}`;
    return (
      this.corpus.section(href, false) ?? this.corpus.section(alternate, false)
    );
  }

  /**
   * One MoPP page by Patents Act 1977 section number (`1`, `4A`, `4a`, or a
   * paragraph such as `1.07`, which returns its section page) or by gov.uk
   * slug, path or URL.
   */
  async getSection(
    section: string,
    options: MoppSectionOptions = {},
  ): Promise<MoppSection> {
    const value = reference.parse(section);
    const corpus = await this.ready(options.version, options.signal);
    const isNumber = MOPP_SECTION_NUMBER.test(value);
    const row = isNumber ? this.byNumber(value) : this.byHref(value);
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `Could not find MoPP ${isNumber ? "section" : "href"} '${value}' in the installed corpus.`,
      );
    const html = await this.corpus.text(row.html, "html");
    const text = await this.corpus.text(row.text, "text");
    if (byteLength(html) + byteLength(text) > this.maxSectionBytes)
      throw new CorpusError(
        "SECTION_TOO_LARGE",
        "Corpus section exceeds the configured decoded-byte limit.",
      );
    checkCorpusSignal(options.signal);
    const sourceUrl = moppResultUrl(row.href);
    return {
      href: row.href,
      section_number: sectionNumber(row),
      title: row.title,
      html,
      text,
      version: "current",
      source_url: sourceUrl,
      content_sha256: await sha256Hex(new TextEncoder().encode(html)),
      corpus_metadata: corpus.metadata,
      provenance: this.provenance(corpus, sourceUrl),
    };
  }

  async resolveSectionHref(
    section: string,
    options: MoppSectionOptions = {},
  ): Promise<string | null> {
    const value = reference.parse(section);
    await this.ready(options.version, options.signal);
    return this.byNumber(value)?.href ?? null;
  }

  /** The installed snapshot, as Python's single `current` entry. */
  async listVersions(): Promise<MoppVersion[]> {
    const status = await this.ready();
    return [
      {
        label: `current (snapshot ${status.snapshot_date ?? "unknown"})`,
        value: "current",
        current: true,
      },
    ];
  }

  close() {
    this.corpus.close();
  }
}

export async function getMoppCorpusStatus(options: MoppClientOptions = {}) {
  const client = new MoppClient(options);
  try {
    return await client.getCorpusStatus();
  } finally {
    client.close();
  }
}

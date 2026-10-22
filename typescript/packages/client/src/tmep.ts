import { z } from "zod";
import { defaultCorpusPath } from "#files";
import {
  CorpusError,
  checkCorpusSignal,
  OutlineCorpus,
  type OutlineHit,
  outlineFtsQuery,
  corpusTimestamp as timestamp,
} from "./corpus/outline.js";
import type { CorpusProvenance } from "./models.js";
import { byteLength, env, sha256Hex } from "./runtime/env.js";

const source = "https://tmep.uspto.gov";
const sourceName = "USPTO TMEP (Trademark Manual of Examining Procedure)";
/** Python's TMEP SECTION_NUMBER_PATTERN: 1207, 1207.01, 1207.01(a), 710.01(c)(1). */
export const TMEP_SECTION_NUMBER = /^\d+(?:\.\d+)?(?:\([a-z]\))?(?:\(\d+\))?$/i;
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

export interface TmepClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also TMEP_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed on disk; also TMEP_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
  maxSectionBytes?: number;
}
export type TmepSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};
export interface TmepSectionOptions {
  /** Only `current` (the installed snapshot) is accepted. */
  version?: string;
  signal?: AbortSignal;
}
export interface TmepCorpusStatus {
  available: boolean;
  /** The build's version label when it names a release; `current` and missing values are `unknown`. */
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
export interface TmepSearchHit {
  title: string;
  section_number: string | null;
  href: string;
  path: string[];
  result_url: string;
  snippet: string;
}
export interface TmepSearchResponse {
  hits: TmepSearchHit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: TmepCorpusStatus;
}
export interface TmepSection {
  href: string;
  section_number: string | null;
  title: string | null;
  chapter: string | null;
  html: string;
  text: string;
  version: string;
  source_url: string;
  content_sha256: string;
  corpus_metadata: Record<string, string>;
  provenance: CorpusProvenance;
}
export interface TmepVersion {
  label: string;
  value: string;
  /** This entry is installed, not a claim that it is the latest USPTO edition. */
  current: boolean;
}

function corpusVersion(metadata: Record<string, string>): string {
  const value = metadata.source_version;
  return value && value !== "current" && value !== "unknown"
    ? value
    : "unknown";
}
const resultUrl = (href?: string) => {
  const url = new URL(href ? "/RDMS/TMEP/result" : "/RDMS/TMEP/search", source);
  if (href) url.searchParams.set("href", href);
  return url.href;
};

/** Read-only TMEP snapshot reader; never acquires or refreshes an artifact. */
export class TmepClient {
  private readonly corpus: OutlineCorpus;
  private readonly maxSectionBytes: number;
  constructor(options: TmepClientOptions = {}) {
    const path =
      options.corpusPath ??
      env("TMEP_CORPUS_PATH") ??
      defaultCorpusPath("tmep.db") ??
      "";
    if (!options.source) reference.parse(path);
    const pin = (value: string | undefined) =>
      value === undefined ? undefined : sha256Pin.parse(value);
    const expectedSha256 = pin(
      options.expectedSha256 ?? env("TMEP_CORPUS_SHA256"),
    );
    const expectedFileSha256 = pin(
      options.expectedFileSha256 ?? env("TMEP_CORPUS_FILE_SHA256"),
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
      label: "TMEP",
      envVar: "TMEP_CORPUS_PATH",
      maxSectionBytes: this.maxSectionBytes,
      ...(expectedSha256 ? { expectedSha256 } : {}),
      ...(expectedFileSha256 ? { expectedFileSha256 } : {}),
    });
  }

  private status(available: boolean, error?: CorpusError): TmepCorpusStatus {
    const metadata = { ...this.corpus.metadata };
    return {
      available,
      corpus_version: corpusVersion(metadata),
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
      source_url: source,
      metadata,
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(
    corpus: TmepCorpusStatus,
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
        "Only the installed TMEP snapshot (current) is available.",
      );
    await this.corpus.open();
    checkCorpusSignal(signal);
    return this.status(true);
  }

  async getCorpusStatus(): Promise<TmepCorpusStatus> {
    try {
      await this.corpus.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  async search(options: TmepSearchOptions): Promise<TmepSearchResponse> {
    const input = searchOptions.parse(options);
    const corpus = await this.ready(input.version, options.signal);
    const query = outlineFtsQuery(input.query, input.syntax);
    const rows = query
      ? this.corpus.search(query, input.limit + 1, input.offset, input.sort)
      : [];
    checkCorpusSignal(options.signal);
    const hits = rows.slice(0, input.limit).map(
      (row: OutlineHit): TmepSearchHit => ({
        title:
          row.section_number && row.title
            ? `${row.section_number} - ${row.title}`
            : (row.title ?? row.section_number ?? ""),
        section_number: row.section_number,
        href: row.href,
        path: [
          ...(row.chapter ? [`Chapter ${row.chapter}`] : []),
          ...(row.section_number ? [row.section_number] : []),
        ],
        result_url: resultUrl(row.href),
        snippet: row.snippet,
      }),
    );
    return {
      hits,
      has_more: rows.length > input.limit,
      offset: input.offset,
      limit: input.limit,
      provenance: this.provenance(corpus, resultUrl()),
      corpus,
    };
  }

  /** One section by number (`1207.01(a)`) or eTMEP href (`TMEP-1200d1e8145.html`). */
  async getSection(
    section: string,
    options: TmepSectionOptions = {},
  ): Promise<TmepSection> {
    const value = reference.parse(section);
    const corpus = await this.ready(options.version, options.signal);
    const isNumber = TMEP_SECTION_NUMBER.test(value);
    let href = value.replace(/^\/+/, "").replace(/^current\//, "");
    if (!href.endsWith(".html")) href += ".html";
    const row = this.corpus.section(isNumber ? value : href, isNumber);
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        `Could not find TMEP ${isNumber ? "section" : "href"} '${value}' in the installed corpus.`,
      );
    const html = await this.corpus.text(row.html, "html");
    const text = await this.corpus.text(row.text, "text");
    if (byteLength(html) + byteLength(text) > this.maxSectionBytes)
      throw new CorpusError(
        "SECTION_TOO_LARGE",
        "Corpus section exceeds the configured decoded-byte limit.",
      );
    checkCorpusSignal(options.signal);
    const sourceUrl = resultUrl(row.href);
    return {
      href: row.href,
      section_number: row.section_number,
      title: row.title,
      chapter: row.chapter,
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
    options: TmepSectionOptions = {},
  ): Promise<string | null> {
    const value = reference.parse(section);
    await this.ready(options.version, options.signal);
    return this.corpus.section(value, true)?.href ?? null;
  }

  /** The installed snapshot, as Python's single `current` entry. */
  async listVersions(): Promise<TmepVersion[]> {
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

export async function getTmepCorpusStatus(options: TmepClientOptions = {}) {
  const client = new TmepClient(options);
  try {
    return await client.getCorpusStatus();
  } finally {
    client.close();
  }
}

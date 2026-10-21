import { z } from "zod";
import { defaultCorpusPath } from "#files";
import {
  CorpusError,
  checkCorpusSignal,
  outlineFtsQuery as fts,
  OutlineCorpus,
  type OutlineHit,
  corpusTimestamp as timestamp,
} from "./corpus/outline.js";
import type { CorpusProvenance } from "./models.js";
import { MPEP_RELEASE_CHECK } from "./mpep-release.js";
import { byteLength, env, sha256Hex } from "./runtime/env.js";

export { CorpusError, type CorpusErrorCode } from "./corpus/outline.js";

const source = "https://mpep.uspto.gov";
const sourceName = "USPTO MPEP (Manual of Patent Examining Procedure)";
const sectionNumber = /^\d+(?:\.\d+)?(?:\([a-z]\))?(?:\(\d+\))?$/i;
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

export interface MpepClientOptions {
  corpusPath?: string;
  /** Artifact bytes or a loader for them, used instead of a path; required in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>);
  /** SHA-256 of the decoded standalone SQLite bytes; also MPEP_CORPUS_SHA256. */
  expectedSha256?: string;
  /** SHA-256 of the file as distributed on disk; also MPEP_CORPUS_FILE_SHA256. */
  expectedFileSha256?: string;
  maxSectionBytes?: number;
}
export type MpepSearchOptions = z.input<typeof searchOptions> & {
  signal?: AbortSignal;
};
export interface MpepSectionOptions {
  version?: string;
  signal?: AbortSignal;
}
export interface MpepCorpusStatus {
  available: boolean;
  source_version: string;
  corpus_version: string;
  schema_version: number | null;
  section_count: number | null;
  snapshot_date: string | null;
  corpus_synced_at: string | null;
  edition: string | null;
  revision: string | null;
  publication_date: string | null;
  substantive_cutoff_date: string | null;
  build_id: string | null;
  interim_updates_coverage: string;
  artifact_sha256: string | null;
  file_sha256: string | null;
  compression: "none" | "zstd" | null;
  source_url: string;
  metadata: Record<string, string>;
  release_check: typeof MPEP_RELEASE_CHECK & {
    comparison: "matches_latest_checked" | "different_release" | "unknown";
  };
  error?: { code: string; message: string };
}
export interface MpepSearchHit {
  title: string;
  section_number: string | null;
  href: string;
  path: string[];
  result_url: string;
  snippet: string;
}
export interface MpepSearchResponse {
  hits: MpepSearchHit[];
  has_more: boolean;
  offset: number;
  limit: number;
  provenance: CorpusProvenance;
  corpus: MpepCorpusStatus;
}
export interface MpepSection {
  href: string;
  section_number: string | null;
  title: string | null;
  html: string;
  text: string;
  version: string;
  source_url: string;
  content_sha256: string;
  section_revision: string | null;
  corpus_metadata: Record<string, string>;
  provenance: CorpusProvenance;
}
export interface MpepVersion {
  label: string;
  value: string;
  /** This entry is installed, not a claim that it is the latest USPTO release. */
  current: boolean;
}

function sourceVersion(metadata: Record<string, string>): string {
  const value = metadata.source_version;
  return value && value !== "current" && value !== "unknown"
    ? value
    : "unknown";
}
function url(href?: string, version?: string) {
  const result = new URL(
    href ? "/RDMS/MPEP/result" : "/RDMS/MPEP/search",
    source,
  );
  if (href) result.searchParams.set("href", href);
  if (version && version !== "unknown")
    result.searchParams.set("version", version);
  return result.href;
}
/** Read-only MPEP snapshot reader; never acquires or refreshes an artifact. */
export class MpepClient {
  private readonly corpus: OutlineCorpus;
  private readonly maxSectionBytes: number;
  constructor(options: MpepClientOptions = {}) {
    const path =
      options.corpusPath ??
      env("MPEP_CORPUS_PATH") ??
      defaultCorpusPath("mpep.db") ??
      "";
    if (!options.source) reference.parse(path);
    const configuredSha256 =
      options.expectedSha256 ?? env("MPEP_CORPUS_SHA256");
    const expectedSha256 =
      configuredSha256 === undefined
        ? undefined
        : z
            .string()
            .regex(/^[a-f\d]{64}$/i)
            .parse(configuredSha256);
    const configuredFileSha256 =
      options.expectedFileSha256 ?? env("MPEP_CORPUS_FILE_SHA256");
    const expectedFileSha256 =
      configuredFileSha256 === undefined
        ? undefined
        : z
            .string()
            .regex(/^[a-f\d]{64}$/i)
            .parse(configuredFileSha256);
    const maxSectionBytes = z
      .number()
      .int()
      .positive()
      .safe()
      .parse(options.maxSectionBytes ?? 16 * 1024 * 1024);
    this.maxSectionBytes = maxSectionBytes;
    this.corpus = new OutlineCorpus({
      path,
      source: options.source,
      maxSectionBytes,
      ...(expectedSha256 ? { expectedSha256 } : {}),
      ...(expectedFileSha256 ? { expectedFileSha256 } : {}),
    });
  }

  private status(available: boolean, error?: CorpusError): MpepCorpusStatus {
    const metadata = { ...this.corpus.metadata };
    return {
      available,
      source_version: sourceVersion(metadata),
      corpus_version: sourceVersion(metadata),
      schema_version: metadata.schema_version
        ? Number(metadata.schema_version)
        : null,
      section_count: this.corpus.sectionCount,
      snapshot_date: metadata.snapshot_date ?? null,
      corpus_synced_at:
        timestamp(metadata.synced_at) ?? timestamp(metadata.snapshot_date),
      edition: metadata.edition ?? null,
      revision: metadata.revision ?? null,
      publication_date: metadata.publication_date ?? null,
      substantive_cutoff_date: metadata.substantive_cutoff_date ?? null,
      build_id: metadata.build_id ?? null,
      interim_updates_coverage: metadata.interim_updates_coverage ?? "unknown",
      artifact_sha256: this.corpus.sha256,
      file_sha256: this.corpus.fileSha256,
      compression: this.corpus.compression,
      source_url: source,
      metadata,
      release_check: {
        ...MPEP_RELEASE_CHECK,
        comparison:
          sourceVersion(metadata) === "unknown"
            ? "unknown"
            : sourceVersion(metadata) === MPEP_RELEASE_CHECK.source_version
              ? "matches_latest_checked"
              : "different_release",
      },
      ...(error ? { error: { code: error.code, message: error.message } } : {}),
    };
  }

  private provenance(
    corpus: MpepCorpusStatus,
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
    await this.corpus.open();
    checkCorpusSignal(signal);
    const status = this.status(true);
    if (
      version !== "current" &&
      (status.source_version === "unknown" || version !== status.source_version)
    )
      throw new CorpusError(
        "VERSION_UNAVAILABLE",
        "The requested MPEP release is not installed. current selects the installed snapshot only.",
      );
    return status;
  }

  async getCorpusStatus(): Promise<MpepCorpusStatus> {
    try {
      await this.corpus.open();
      return this.status(true);
    } catch (error) {
      if (!(error instanceof CorpusError)) throw error;
      return this.status(false, error);
    }
  }

  async search(options: MpepSearchOptions): Promise<MpepSearchResponse> {
    const input = searchOptions.parse(options);
    const corpus = await this.ready(input.version, options.signal);
    const query = fts(input.query, input.syntax);
    const rows = query
      ? this.corpus.search(query, input.limit + 1, input.offset, input.sort)
      : [];
    checkCorpusSignal(options.signal);
    const hits = rows.slice(0, input.limit).map(
      (row: OutlineHit): MpepSearchHit => ({
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
        result_url: url(row.href, corpus.source_version),
        snippet: row.snippet,
      }),
    );
    return {
      hits,
      has_more: rows.length > input.limit,
      offset: input.offset,
      limit: input.limit,
      provenance: this.provenance(
        corpus,
        url(undefined, corpus.source_version),
      ),
      corpus,
    };
  }

  async getSection(
    section: string,
    options: MpepSectionOptions = {},
  ): Promise<MpepSection> {
    const value = reference.parse(section);
    const corpus = await this.ready(options.version, options.signal);
    const isNumber = sectionNumber.test(value);
    let href = value.replace(/^\/+/, "").replace(/^current\//, "");
    if (!href.endsWith(".html")) href += ".html";
    const row = this.corpus.section(isNumber ? value : href, isNumber);
    if (!row)
      throw new CorpusError(
        "SECTION_NOT_FOUND",
        "The requested MPEP section was not found in the installed corpus.",
      );
    const html = await this.corpus.text(row.html, "html");
    const text = await this.corpus.text(row.text, "text");
    if (byteLength(html) + byteLength(text) > this.maxSectionBytes)
      throw new CorpusError(
        "SECTION_TOO_LARGE",
        "Corpus section exceeds the configured decoded-byte limit.",
      );
    checkCorpusSignal(options.signal);
    const sourceUrl = url(row.href, corpus.source_version);
    return {
      href: row.href,
      section_number: row.section_number,
      title: row.title,
      html,
      text,
      version: corpus.source_version,
      source_url: sourceUrl,
      content_sha256: await sha256Hex(new TextEncoder().encode(html)),
      section_revision:
        /\[R-[^\]]+\]/.exec(`${row.title ?? ""} ${text.slice(0, 500)}`)?.[0] ??
        null,
      corpus_metadata: corpus.metadata,
      provenance: this.provenance(corpus, sourceUrl),
    };
  }

  async resolveSectionHref(
    section: string,
    options: MpepSectionOptions = {},
  ): Promise<string | null> {
    const value = reference.parse(section);
    await this.ready(options.version, options.signal);
    return this.corpus.section(value, true)?.href ?? null;
  }

  async listVersions(): Promise<MpepVersion[]> {
    const status = await this.ready();
    return [
      {
        label: `${status.source_version} (installed snapshot ${status.snapshot_date ?? "unknown"})`,
        value:
          status.source_version === "unknown"
            ? "current"
            : status.source_version,
        current: true,
      },
    ];
  }

  close() {
    this.corpus.close();
  }
}

export async function getMpepCorpusStatus(options: MpepClientOptions = {}) {
  const client = new MpepClient(options);
  try {
    return await client.getCorpusStatus();
  } finally {
    client.close();
  }
}

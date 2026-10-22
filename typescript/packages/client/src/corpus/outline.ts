import { z } from "zod";
import { readArtifact } from "#files";
import { byteLength, sha256Hex } from "../runtime/env.js";
import { openSnapshot, type SnapshotDatabase } from "../runtime/sqlite.js";
import { ZstdOutputTooLarge, zstd } from "../runtime/zstd.js";

export type CorpusErrorCode =
  | "CORPUS_UNAVAILABLE"
  | "CORPUS_TOO_LARGE"
  | "CORPUS_WAL_UNSUPPORTED"
  | "INVALID_CORPUS"
  | "UNSUPPORTED_SCHEMA"
  | "CHECKSUM_MISMATCH"
  | "DECOMPRESSION_FAILED"
  | "SECTION_TOO_LARGE"
  | "SECTION_NOT_FOUND"
  | "VERSION_UNAVAILABLE"
  | "ABORTED";

export class CorpusError extends Error {
  override name = "CorpusError";
  constructor(
    readonly code: CorpusErrorCode,
    message: string,
  ) {
    super(message);
  }
}

export function checkCorpusSignal(signal?: AbortSignal) {
  if (signal?.aborted)
    throw new CorpusError("ABORTED", "The corpus request was cancelled.");
}

export interface OutlineRow {
  href: string;
  section_number: string | null;
  title: string | null;
  breadcrumb: string | null;
  chapter: string | null;
  html: string | Uint8Array;
  text: string | Uint8Array;
}
export interface OutlineHit extends Omit<OutlineRow, "html" | "text"> {
  snippet: string;
}
/** Where a corpus artifact comes from and how it is pinned. */
export interface CorpusArtifactOptions {
  /** Artifact path in server runtimes. */
  path: string;
  /** Artifact bytes, or a loader for them; takes precedence over path and is the only option in browsers. */
  source?: Uint8Array | (() => Promise<Uint8Array>) | undefined;
  /** Names the corpus and its path variable in unavailable-artifact errors. */
  label?: string;
  envVar?: string;
  expectedSha256?: string;
  expectedFileSha256?: string;
}
export interface OutlineOptions extends CorpusArtifactOptions {
  maxSectionBytes: number;
}

const readLE = (bytes: Uint8Array, offset: number, count: number) => {
  let value = 0n;
  for (let i = count - 1; i >= 0; i--)
    value = (value << 8n) | BigInt(bytes[offset + i] ?? 0);
  return value;
};

/** Validate one complete standard frame before decoding.
 * Frame layout: https://github.com/facebook/zstd/blob/dev/doc/zstd_compression_format.md
 */
function zstdEnvelope(bytes: Uint8Array, maxBytes: number) {
  const invalid = () =>
    new CorpusError(
      "DECOMPRESSION_FAILED",
      "The corpus must contain one complete standard Zstandard frame.",
    );
  const requireBytes = (offset: number, count: number) => {
    if (offset + count > bytes.length) throw invalid();
  };
  requireBytes(4, 1);
  const descriptor = bytes[4] ?? 0;
  if (descriptor & 8) throw invalid();
  const single = Boolean(descriptor & 32);
  let offset = 5;
  let windowSize = 0;
  if (!single) {
    requireBytes(offset, 1);
    const window = bytes[offset++] ?? 0;
    const base = 2 ** (10 + (window >> 3));
    windowSize = base + (base / 8) * (window & 7);
  }
  const dictionarySize = [0, 1, 2, 4][descriptor & 3] ?? 0;
  requireBytes(offset, dictionarySize);
  if (dictionarySize && readLE(bytes, offset, dictionarySize) !== 0n)
    throw invalid();
  offset += dictionarySize;
  const sizeFlag = descriptor >> 6;
  const sizeBytes = sizeFlag ? 2 ** sizeFlag : single ? 1 : 0;
  requireBytes(offset, sizeBytes);
  const contentSize = sizeBytes
    ? readLE(bytes, offset, sizeBytes) + (sizeBytes === 2 ? 256n : 0n)
    : null;
  offset += sizeBytes;
  if (single) windowSize = Number(contentSize);
  if (
    (contentSize !== null && contentSize > BigInt(maxBytes)) ||
    windowSize > maxBytes
  )
    throw new CorpusError(
      "CORPUS_TOO_LARGE",
      "Decoded corpus artifacts and Zstandard windows must not exceed 256 MiB.",
    );
  const maxBlockSize = Math.min(windowSize, 128 * 1024);
  while (true) {
    requireBytes(offset, 3);
    const block = Number(readLE(bytes, offset, 3));
    offset += 3;
    const type = (block >> 1) & 3;
    const length = block >>> 3;
    if (type === 3 || length > maxBlockSize) throw invalid();
    requireBytes(offset, type === 1 ? 1 : length);
    offset += type === 1 ? 1 : length;
    if (block & 1) break;
  }
  if (descriptor & 4) {
    requireBytes(offset, 4);
    offset += 4;
  }
  if (offset !== bytes.length) throw invalid();
  return { contentSize: contentSize === null ? null : Number(contentSize) };
}

/** Declared content size of a dictionary-compressed cell frame, or null when absent or malformed. */
function cellContentSize(bytes: Uint8Array): number | null {
  if (bytes.length < 6 || readLE(bytes, 0, 4) !== 0xfd2fb528n) return null;
  const descriptor = bytes[4] ?? 0;
  const single = Boolean(descriptor & 32);
  const offset = 5 + (single ? 0 : 1) + ([0, 1, 2, 4][descriptor & 3] ?? 0);
  const sizeFlag = descriptor >> 6;
  const sizeBytes = sizeFlag ? 2 ** sizeFlag : single ? 1 : 0;
  if (!sizeBytes || offset + sizeBytes > bytes.length) return null;
  return Number(
    readLE(bytes, offset, sizeBytes) + (sizeBytes === 2 ? 256n : 0n),
  );
}

export interface CorpusSnapshot<T> {
  db: SnapshotDatabase;
  sha256: string;
  fileSha256: string;
  compression: "none" | "zstd";
  /** What the schema check returned. */
  value: T;
}

/**
 * Read one artifact, check its file pin, decode a Zstandard frame, check the
 * decoded pin, reject WAL headers and open the bytes read-only, then run the
 * schema-specific check `validate`. Known failures are CorpusErrors; any
 * other error from `validate` reports INVALID_CORPUS.
 */
export async function openCorpusSnapshot<T>(
  options: CorpusArtifactOptions,
  validate: (db: SnapshotDatabase) => T,
  kind = "outline",
): Promise<CorpusSnapshot<T>> {
  let db: SnapshotDatabase | undefined;
  try {
    const maxArtifactBytes = 256 * 1024 * 1024;
    const source = options.source;
    const encoded =
      source instanceof Uint8Array
        ? source
        : source
          ? await source()
          : await readArtifact(options.path, maxArtifactBytes);
    if (encoded.byteLength > maxArtifactBytes)
      throw new CorpusError(
        "CORPUS_TOO_LARGE",
        "Corpus artifacts must not exceed 256 MiB.",
      );
    const fileSha256 = await sha256Hex(encoded);
    if (
      options.expectedFileSha256 &&
      fileSha256 !== options.expectedFileSha256.toLowerCase()
    )
      throw new CorpusError(
        "CHECKSUM_MISMATCH",
        "Corpus file SHA-256 does not match its pin.",
      );
    const fileCompression =
      readLE(encoded, 0, 4) === 0xfd2fb528n && encoded.length >= 4
        ? "zstd"
        : "none";
    let snapshot = encoded;
    if (fileCompression === "zstd") {
      const frame = zstdEnvelope(encoded, maxArtifactBytes);
      // libzstd verifies the frame checksum when one is present.
      try {
        snapshot = (await zstd()).decompress(
          encoded,
          maxArtifactBytes,
          frame.contentSize,
        );
      } catch (error) {
        if (error instanceof ZstdOutputTooLarge)
          throw new CorpusError(
            "CORPUS_TOO_LARGE",
            "Decoded corpus artifacts must not exceed 256 MiB.",
          );
        throw new CorpusError(
          "DECOMPRESSION_FAILED",
          "The Zstandard corpus file could not be decoded.",
        );
      }
      if (snapshot.length > maxArtifactBytes)
        throw new CorpusError(
          "CORPUS_TOO_LARGE",
          "Decoded corpus artifacts must not exceed 256 MiB.",
        );
      if (frame.contentSize !== null && snapshot.length !== frame.contentSize)
        throw new CorpusError(
          "DECOMPRESSION_FAILED",
          "The Zstandard corpus file size or checksum is invalid.",
        );
    }
    const sha256 = await sha256Hex(snapshot);
    if (
      options.expectedSha256 &&
      sha256 !== options.expectedSha256.toLowerCase()
    )
      throw new CorpusError(
        "CHECKSUM_MISMATCH",
        "Corpus SHA-256 does not match its pin.",
      );
    if (snapshot[18] === 2 || snapshot[19] === 2)
      throw new CorpusError(
        "CORPUS_WAL_UNSUPPORTED",
        "Prepare a standalone SQLite artifact in DELETE journal mode outside runtime. WAL-mode files and sidecars are not accepted.",
      );
    db = await openSnapshot(snapshot);
    return {
      db,
      sha256,
      fileSha256,
      compression: fileCompression,
      value: validate(db),
    };
  } catch (error) {
    db?.close();
    if (error instanceof CorpusError) throw error;
    if (
      error &&
      typeof error === "object" &&
      "code" in error &&
      error.code === "TOO_LARGE"
    )
      throw new CorpusError(
        "CORPUS_TOO_LARGE",
        "Corpus artifacts must not exceed 256 MiB.",
      );
    if (
      error &&
      typeof error === "object" &&
      "code" in error &&
      (error.code === "ENOENT" || error.code === "NO_FILES")
    )
      throw new CorpusError(
        "CORPUS_UNAVAILABLE",
        `${options.label ?? "MPEP"} corpus is unavailable. Set ${options.envVar ?? "MPEP_CORPUS_PATH"} to an existing verified artifact; acquisition never runs during a request.`,
      );
    throw new CorpusError(
      "INVALID_CORPUS",
      `The ${kind} corpus is not a supported readable SQLite/FTS5 artifact.`,
    );
  }
}

/** Shared read-only outline artifact lifecycle; acquisition stays outside runtime. */
export class OutlineCorpus {
  private db: SnapshotDatabase | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private dictionaries = new Map<string, Uint8Array>();
  metadata: Record<string, string> = {};
  sha256: string | null = null;
  fileSha256: string | null = null;
  compression: "none" | "zstd" | null = null;
  sectionCount: number | null = null;
  constructor(private readonly options: OutlineOptions) {}

  async open() {
    if (this.db) return;
    this.opening ??= this.load(this.generation).finally(() => {
      this.opening = undefined;
    });
    await this.opening;
  }

  private async load(generation: number) {
    const snapshot = await openCorpusSnapshot(this.options, (db) => {
      const metadata = Object.fromEntries(
        db
          .all<{ key: string; value: string }>("SELECT key, value FROM meta")
          .map((row) => [row.key, row.value]),
      );
      if (
        Object.entries(metadata).some(
          ([key, value]) =>
            typeof key !== "string" || typeof value !== "string",
        )
      )
        throw new Error();
      if (!["1", "2"].includes(metadata.schema_version ?? ""))
        throw new CorpusError(
          "UNSUPPORTED_SCHEMA",
          "Unsupported outline corpus schema; supported versions are 1 and 2.",
        );
      const count = db.get<{ count: number }>(
        "SELECT count(*) AS count FROM sections",
      )?.count;
      db.all(
        "SELECT href, section_number, title, breadcrumb, chapter, html, text FROM sections LIMIT 0",
      );
      const fts = db.get<{ sql: string }>(
        "SELECT sql FROM sqlite_master WHERE name = ? AND type = 'table'",
        ["sections_fts"],
      );
      const ftsColumns = db
        .all<{ name: string }>("PRAGMA table_info(sections_fts)")
        .map((row) => row.name);
      if (
        !fts ||
        !/\bUSING\s+fts5\s*\(/i.test(fts.sql) ||
        !/\bcontent\s*=\s*['"]sections['"]/i.test(fts.sql) ||
        !/\bcontent_rowid\s*=\s*['"]rowid['"]/i.test(fts.sql) ||
        JSON.stringify(ftsColumns) !==
          JSON.stringify(["section_number", "title", "text"]) ||
        count === undefined ||
        (metadata.section_count !== undefined &&
          Number(metadata.section_count) !== count)
      )
        throw new Error();
      const compression = db.get(
        "SELECT 1 FROM sqlite_master WHERE name = 'compression_dict' AND type = 'table'",
      );
      const dictionaries = new Map<string, Uint8Array>();
      if (compression)
        for (const row of db.all<{
          column_name: string;
          dict_bytes: Uint8Array;
        }>("SELECT column_name, dict_bytes FROM compression_dict")) {
          if (
            !["html", "text"].includes(row.column_name) ||
            !(row.dict_bytes instanceof Uint8Array) ||
            row.dict_bytes.length > 1024 * 1024 ||
            dictionaries.has(row.column_name)
          )
            throw new Error();
          dictionaries.set(row.column_name, row.dict_bytes);
        }
      return { metadata, count, dictionaries };
    });
    if (generation !== this.generation) {
      snapshot.db.close();
      throw new CorpusError("ABORTED", "The corpus was closed while opening.");
    }
    this.db = snapshot.db;
    this.metadata = snapshot.value.metadata;
    this.sha256 = snapshot.sha256;
    this.fileSha256 = snapshot.fileSha256;
    this.compression = snapshot.compression;
    this.sectionCount = snapshot.value.count;
    this.dictionaries = snapshot.value.dictionaries;
  }

  section(value: string, byNumber: boolean): OutlineRow | null {
    const column = byNumber ? "section_number" : "href";
    if (!this.db) throw new CorpusError("ABORTED", "The corpus was closed.");
    try {
      return (
        this.db.get<OutlineRow>(
          `SELECT href, section_number, title, breadcrumb, chapter, html, text FROM sections WHERE ${column} = ? LIMIT 1`,
          [value],
        ) ?? null
      );
    } catch {
      throw new CorpusError(
        "INVALID_CORPUS",
        "The corpus section index is not readable.",
      );
    }
  }

  search(
    query: string,
    limit: number,
    offset: number,
    sort: "relevance" | "outline",
  ): OutlineHit[] {
    const order =
      sort === "outline" ? "s.section_number, s.href" : "rank, s.href";
    if (!this.db) throw new CorpusError("ABORTED", "The corpus was closed.");
    try {
      return this.db.all<OutlineHit>(
        `SELECT s.href, s.section_number, s.title, s.breadcrumb, s.chapter, snippet(sections_fts, 2, '<mark>', '</mark>', '…', 40) AS snippet FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ? ORDER BY ${order} LIMIT ? OFFSET ?`,
        [query, limit, offset],
      );
    } catch {
      throw new CorpusError(
        "INVALID_CORPUS",
        "The corpus full-text index is not readable.",
      );
    }
  }

  async text(
    value: string | Uint8Array,
    column: "html" | "text",
  ): Promise<string> {
    if (typeof value === "string") {
      if (byteLength(value) > this.options.maxSectionBytes)
        throw new CorpusError(
          "SECTION_TOO_LARGE",
          "Corpus section exceeds the configured decoded-byte limit.",
        );
      return value;
    }
    const dictionary = this.dictionaries.get(column);
    if (!dictionary)
      throw new CorpusError(
        "DECOMPRESSION_FAILED",
        "Compressed corpus content has no decoding dictionary.",
      );
    const size = cellContentSize(value);
    if (size === null)
      throw new CorpusError(
        "DECOMPRESSION_FAILED",
        "Corpus dictionary-compressed content must declare its decoded size.",
      );
    if (size > this.options.maxSectionBytes)
      throw new CorpusError(
        "SECTION_TOO_LARGE",
        "Corpus section exceeds the configured decoded-byte limit.",
      );
    try {
      const bytes = (await zstd()).decompressWithDictionary(value, dictionary);
      if (bytes.length !== size) throw new Error();
      return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch {
      throw new CorpusError(
        "DECOMPRESSION_FAILED",
        "Corpus dictionary-compressed content could not be decoded.",
      );
    }
  }

  close() {
    this.generation++;
    this.db?.close();
    this.db = undefined;
    this.metadata = {};
    this.sha256 = null;
    this.fileSha256 = null;
    this.compression = null;
    this.sectionCount = null;
    this.dictionaries.clear();
  }
}

/** Quote user terms as FTS5 text; never execute caller input as MATCH syntax. */
export function outlineFtsQuery(
  query: string,
  syntax: "adj" | "exact" | "and" | "or",
) {
  const clean = query.trim();
  if (!clean) return "";
  const quote = (text: string) => `"${text.replaceAll('"', '""')}"`;
  return syntax === "adj" || syntax === "exact"
    ? quote(clean)
    : clean
        .split(/\s+/)
        .map(quote)
        .join(syntax === "or" ? " OR " : " ");
}

/** A metadata date or timestamp as ISO UTC; malformed values become null. */
export function corpusTimestamp(value?: string): string | null {
  if (!value) return null;
  const full = /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00Z` : value;
  const parsed = z.iso.datetime({ offset: true }).safeParse(full);
  if (!parsed.success) return null;
  const date = new Date(parsed.data);
  return Number.isNaN(date.valueOf()) ? null : date.toISOString();
}

import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { zstdDecompressSync } from "node:zlib";

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
export interface OutlineOptions {
  path: string;
  expectedSha256?: string;
  maxSectionBytes: number;
}

/** Shared read-only outline artifact lifecycle; acquisition stays outside runtime. */
export class OutlineCorpus {
  private db: Database | undefined;
  private opening: Promise<void> | undefined;
  private generation = 0;
  private dictionaries = new Map<string, Uint8Array>();
  metadata: Record<string, string> = {};
  sha256: string | null = null;
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
    let db: Database | undefined;
    try {
      const info = await stat(this.options.path);
      if (!info.isFile()) throw new Error();
      const maxArtifactBytes = 256 * 1024 * 1024;
      if (info.size > maxArtifactBytes)
        throw new CorpusError(
          "CORPUS_TOO_LARGE",
          "Corpus artifacts must not exceed 256 MiB.",
        );
      const digest = createHash("sha256");
      const chunks: Buffer[] = [];
      let bytes = 0;
      for await (const chunk of createReadStream(this.options.path)) {
        bytes += chunk.length;
        if (bytes > maxArtifactBytes)
          throw new CorpusError(
            "CORPUS_TOO_LARGE",
            "Corpus artifacts must not exceed 256 MiB.",
          );
        digest.update(chunk);
        chunks.push(chunk);
      }
      const snapshot = Buffer.concat(chunks, bytes);
      const sha256 = digest.digest("hex");
      if (
        this.options.expectedSha256 &&
        sha256 !== this.options.expectedSha256.toLowerCase()
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
      // Deserializing the hashed bytes prevents WAL replay and path-replacement races.
      db = Database.deserialize(snapshot, true);
      db.exec("PRAGMA query_only = ON");
      const metadata = Object.fromEntries(
        db
          .query<{ key: string; value: string }, []>(
            "SELECT key, value FROM meta",
          )
          .all()
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
      const count = db
        .query<{ count: number }, []>("SELECT count(*) AS count FROM sections")
        .get()?.count;
      db.query(
        "SELECT href, section_number, title, breadcrumb, chapter, html, text FROM sections LIMIT 0",
      ).all();
      const fts = db
        .query<{ sql: string }, [string]>(
          "SELECT sql FROM sqlite_master WHERE name = ? AND type = 'table'",
        )
        .get("sections_fts");
      const ftsColumns = db
        .query<{ name: string }, []>("PRAGMA table_info(sections_fts)")
        .all()
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
      const compression = db
        .query(
          "SELECT 1 FROM sqlite_master WHERE name = 'compression_dict' AND type = 'table'",
        )
        .get();
      const dictionaries = new Map<string, Uint8Array>();
      if (compression)
        for (const row of db
          .query<{ column_name: string; dict_bytes: Uint8Array }, []>(
            "SELECT column_name, dict_bytes FROM compression_dict",
          )
          .all()) {
          if (
            !["html", "text"].includes(row.column_name) ||
            !(row.dict_bytes instanceof Uint8Array) ||
            row.dict_bytes.length > 1024 * 1024 ||
            dictionaries.has(row.column_name)
          )
            throw new Error();
          dictionaries.set(row.column_name, row.dict_bytes);
        }
      if (generation !== this.generation)
        throw new CorpusError(
          "ABORTED",
          "The corpus was closed while opening.",
        );
      this.db = db;
      this.metadata = metadata;
      this.sha256 = sha256;
      this.sectionCount = count;
      this.dictionaries = dictionaries;
    } catch (error) {
      db?.close();
      if (error instanceof CorpusError) throw error;
      if (
        error &&
        typeof error === "object" &&
        "code" in error &&
        error.code === "ENOENT"
      )
        throw new CorpusError(
          "CORPUS_UNAVAILABLE",
          "MPEP corpus is unavailable. Set MPEP_CORPUS_PATH to an existing verified artifact; acquisition never runs during a request.",
        );
      throw new CorpusError(
        "INVALID_CORPUS",
        "The outline corpus is not a supported readable SQLite/FTS5 artifact.",
      );
    }
  }

  section(value: string, byNumber: boolean): OutlineRow | null {
    const column = byNumber ? "section_number" : "href";
    if (!this.db) throw new CorpusError("ABORTED", "The corpus was closed.");
    try {
      return (
        this.db
          .query<OutlineRow, [string]>(
            `SELECT href, section_number, title, breadcrumb, chapter, html, text FROM sections WHERE ${column} = ? LIMIT 1`,
          )
          .get(value) ?? null
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
      return (
        this.db
          .query<OutlineHit, [string, number, number]>(
            `SELECT s.href, s.section_number, s.title, s.breadcrumb, s.chapter, snippet(sections_fts, 2, '<mark>', '</mark>', '…', 40) AS snippet FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid WHERE sections_fts MATCH ? ORDER BY ${order} LIMIT ? OFFSET ?`,
          )
          .all(query, limit, offset) ?? []
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
      if (Buffer.byteLength(value) > this.options.maxSectionBytes)
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
    try {
      const options = {
        dictionary,
        maxOutputLength: this.options.maxSectionBytes,
      };
      const bytes = zstdDecompressSync(value, options);
      return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch (error) {
      if (
        error &&
        typeof error === "object" &&
        "code" in error &&
        error.code === "ERR_BUFFER_TOO_LARGE"
      )
        throw new CorpusError(
          "SECTION_TOO_LARGE",
          "Corpus section exceeds the configured decoded-byte limit.",
        );
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
    this.sectionCount = null;
    this.dictionaries.clear();
  }
}

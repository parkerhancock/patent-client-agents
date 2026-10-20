import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import {
  link,
  lstat,
  mkdtemp,
  rmdir,
  unlink,
  writeFile,
} from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";
import { constants, zstdCompressSync, zstdDecompressSync } from "node:zlib";

const maxBytes = 256 * 1024 * 1024;
const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

class PackagingError extends Error {}

export interface CorpusPackageManifest extends Record<string, unknown> {
  file: string;
  compression: "zstd";
  sha256: string;
  bytes: number;
  decoded_sha256: string;
  decoded_bytes: number;
  file_sha256: string;
  file_bytes: number;
}

async function exists(path: string): Promise<boolean> {
  try {
    await lstat(path);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

async function boundedRead(path: string, limit: number): Promise<Buffer> {
  const info = await lstat(path);
  if (!info.isFile()) throw new PackagingError("Input must be a regular file.");
  if (info.size > limit)
    throw new PackagingError("Input exceeds its size limit.");
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of createReadStream(path)) {
    size += chunk.length;
    if (size > limit) throw new PackagingError("Input exceeds its size limit.");
    chunks.push(chunk);
  }
  return Buffer.concat(chunks, size);
}

function validateSqlite(bytes: Buffer) {
  if (bytes.subarray(0, 16).toString("ascii") !== "SQLite format 3\0")
    throw new PackagingError("Input must be a standalone SQLite corpus.");
  if (bytes[18] !== 1 || bytes[19] !== 1)
    throw new PackagingError(
      "Prepare a standalone DELETE-mode corpus before packaging.",
    );
  let db: Database | undefined;
  try {
    db = Database.deserialize(bytes, true);
    db.exec("PRAGMA query_only = ON");
    const result = db
      .query<{ integrity_check: string }, []>("PRAGMA integrity_check")
      .all();
    if (result.length !== 1 || result[0]?.integrity_check !== "ok")
      throw new Error();
  } catch {
    throw new PackagingError("SQLite integrity verification failed.");
  } finally {
    db?.close();
  }
}

export async function packageCorpus(options: {
  input: string;
  output: string;
  manifest?: string;
}): Promise<CorpusPackageManifest> {
  const input = resolve(options.input);
  const output = resolve(options.output);
  const manifestPath = `${output}.manifest.json`;
  if (
    input === output ||
    (await exists(output)) ||
    (await exists(manifestPath))
  )
    throw new PackagingError("Output or output manifest already exists.");
  const bytes = await boundedRead(input, maxBytes);
  const decodedHash = sha256(bytes);
  validateSqlite(bytes);
  let source: Record<string, unknown> = {};
  if (options.manifest) {
    try {
      const value: unknown = JSON.parse(
        (await boundedRead(options.manifest, 1024 * 1024)).toString("utf8"),
      );
      if (!value || typeof value !== "object" || Array.isArray(value))
        throw new Error();
      source = value as Record<string, unknown>;
      if (source.sha256 !== decodedHash || source.bytes !== bytes.length)
        throw new Error();
    } catch {
      throw new PackagingError(
        "Source manifest hash/size does not match the SQLite input.",
      );
    }
  }
  const compressed = zstdCompressSync(bytes, {
    params: { [constants.ZSTD_c_compressionLevel]: 9 },
    maxOutputLength: maxBytes,
  });
  if (compressed.length > maxBytes)
    throw new PackagingError("Compressed corpus exceeds its size limit.");
  const decoded = zstdDecompressSync(compressed, { maxOutputLength: maxBytes });
  if (decoded.length !== bytes.length || sha256(decoded) !== decodedHash)
    throw new PackagingError(
      "Compressed corpus round-trip verification failed.",
    );
  const manifest: CorpusPackageManifest = {
    ...source,
    file: basename(output),
    compression: "zstd",
    sha256: decodedHash,
    bytes: bytes.length,
    decoded_sha256: decodedHash,
    decoded_bytes: bytes.length,
    file_sha256: sha256(compressed),
    file_bytes: compressed.length,
  };
  const temporary = await mkdtemp(join(dirname(output), ".corpus-package-"));
  const stagedFile = join(temporary, "corpus.zst");
  const stagedManifest = join(temporary, "manifest.json");
  let published = false;
  try {
    await writeFile(stagedFile, compressed, { flag: "wx" });
    await writeFile(stagedManifest, `${JSON.stringify(manifest, null, 2)}\n`, {
      flag: "wx",
    });
    await link(stagedFile, output);
    published = true;
    await link(stagedManifest, manifestPath);
  } catch (error) {
    if (published) {
      const own = await lstat(stagedFile);
      const current = await lstat(output).catch(() => undefined);
      if (current?.ino === own.ino && current.dev === own.dev)
        await unlink(output);
    }
    throw error;
  } finally {
    await unlink(stagedFile).catch((error: NodeJS.ErrnoException) => {
      if (error.code !== "ENOENT") throw error;
    });
    await unlink(stagedManifest).catch((error: NodeJS.ErrnoException) => {
      if (error.code !== "ENOENT") throw error;
    });
    await rmdir(temporary);
  }
  return manifest;
}

if (import.meta.main) {
  try {
    const args = Bun.argv.slice(2);
    const values: Record<string, string> = {};
    for (let index = 0; index < args.length; index += 2) {
      const flag = args[index];
      const value = args[index + 1];
      if (
        !flag ||
        !["--input", "--output", "--manifest"].includes(flag) ||
        values[flag] ||
        !value ||
        value.startsWith("--")
      )
        throw new PackagingError(
          "Use --input PATH --output PATH [--manifest SOURCE_MANIFEST].",
        );
      values[flag] = value;
    }
    if (!values["--input"] || !values["--output"])
      throw new PackagingError(
        "Use --input PATH --output PATH [--manifest SOURCE_MANIFEST].",
      );
    const result = await packageCorpus({
      input: values["--input"],
      output: values["--output"],
      ...(values["--manifest"] ? { manifest: values["--manifest"] } : {}),
    });
    console.log(
      JSON.stringify({
        packaged: true,
        file: result.file,
        decoded_sha256: result.decoded_sha256,
        decoded_bytes: result.decoded_bytes,
        file_sha256: result.file_sha256,
        file_bytes: result.file_bytes,
      }),
    );
  } catch (error) {
    console.error(
      JSON.stringify({
        packaged: false,
        error:
          error instanceof PackagingError
            ? error.message
            : "Corpus packaging failed.",
      }),
    );
    process.exitCode = 1;
  }
}

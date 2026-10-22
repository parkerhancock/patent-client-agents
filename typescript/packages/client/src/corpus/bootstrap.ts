/**
 * Server-only corpus bootstrap for hosted deployments.
 *
 * Reads the TypeScript corpus manifest from Google Cloud Storage, downloads
 * each packaged `.zst` artifact through the JSON API, verifies the file and
 * decoded SHA-256 pins, and returns the environment variables the corpus
 * readers consume. Any failure throws, so a container stops instead of serving
 * stale or unverified data. Not exported from the package index: import it
 * from `@patent-client-agents/client/corpus-bootstrap`.
 */
import { createHash, randomUUID } from "node:crypto";
import { createReadStream, createWriteStream } from "node:fs";
import { mkdir, readFile, rename, stat, unlink } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { Readable, Transform, Writable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { createZstdDecompress } from "node:zlib";
import { z } from "zod";

/** Corpus id in the manifest, and the reader environment prefix it configures. */
export const CORPUS_ENV_PREFIXES = {
  mpep: "MPEP",
  tmep: "TMEP",
  ukipo_mopp: "MOPP",
  epc: "EPC",
  epo_case_law: "CASELAW",
  epo_guidelines: "GUIDELINES",
  epo_pct_guidelines: "PCT_GUIDELINES",
  epo_up_guidelines: "UP_GUIDELINES",
  upc_statutes: "UPC_STATUTES",
  dpma_statutes: "DPMA_STATUTES",
  ipo_in_statutes: "IPO_IN_STATUTES",
  ipo_in_mppp: "IPO_IN_MPPP",
} as const;
export type CorpusId = keyof typeof CORPUS_ENV_PREFIXES;
export const CORPUS_IDS = Object.keys(CORPUS_ENV_PREFIXES) as CorpusId[];

export const MANIFEST_SCHEMA = "patent-client-agents.ts-corpora";
export const MANIFEST_SCHEMA_VERSION = 1;
/** The readers refuse encoded or decoded artifacts above this size. */
export const MAX_CORPUS_BYTES = 256 * 1024 * 1024;
const MAX_MANIFEST_BYTES = 1024 * 1024;

const sha256 = z.string().regex(/^[a-f\d]{64}$/);
const size = z.number().int().positive().max(MAX_CORPUS_BYTES);
const manifestEntry = z.strictObject({
  snapshot: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/),
  uri: z.string().regex(/^gs:\/\/[a-z0-9][a-z0-9._-]*\/[^\s]+$/),
  file: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._-]*\.zst$/),
  compression: z.literal("zstd"),
  file_sha256: sha256,
  file_bytes: size,
  decoded_sha256: sha256,
  decoded_bytes: size,
  metadata: z.record(z.string(), z.string()).optional(),
});
export const corpusManifestSchema = z.strictObject({
  schema: z.literal(MANIFEST_SCHEMA),
  schema_version: z.literal(MANIFEST_SCHEMA_VERSION),
  generated_at: z.iso.datetime({ offset: true }),
  corpora: z.record(z.string(), manifestEntry),
});
export type CorpusManifest = z.infer<typeof corpusManifestSchema>;
export type CorpusManifestEntry = z.infer<typeof manifestEntry>;

export type CorpusBootstrapErrorCode =
  | "MANIFEST_INVALID"
  | "CORPUS_MISSING"
  | "AUTH_FAILED"
  | "DOWNLOAD_FAILED"
  | "VERIFICATION_FAILED";

export class CorpusBootstrapError extends Error {
  override name = "CorpusBootstrapError";
  constructor(
    readonly code: CorpusBootstrapErrorCode,
    message: string,
  ) {
    super(message);
  }
}

export interface BootstrapCorporaOptions {
  /** Corpora the manifest must list. Defaults to every known corpus. */
  corpora?: readonly CorpusId[];
  /**
   * How to get a GCS access token: `auto` (default) uses
   * GOOGLE_APPLICATION_CREDENTIALS or gcloud's application-default
   * credentials file when present, otherwise the GCE metadata server.
   * A function supplies the token directly.
   */
  auth?: "auto" | "metadata" | "adc" | (() => Promise<string>);
  /** Metadata server host. Defaults to GCE_METADATA_HOST or metadata.google.internal. */
  metadataHost?: string;
  /** OAuth token endpoint used to refresh application-default user credentials. */
  oauthTokenUrl?: string;
  /** GCS JSON API origin. Defaults to https://storage.googleapis.com. */
  storageBaseUrl?: string;
  fetch?: typeof fetch;
  /** Progress messages (never credentials). */
  log?: (message: string) => void;
}

/** Reader environment variables: `<PREFIX>_CORPUS_PATH`, `_SHA256`, `_FILE_SHA256`. */
export type CorpusEnvironment = Record<string, string>;

function parseGsUri(uri: string): { bucket: string; object: string } {
  const match = /^gs:\/\/([a-z0-9][a-z0-9._-]*)\/(.+)$/.exec(uri);
  if (!match?.[1] || !match[2])
    throw new CorpusBootstrapError(
      "MANIFEST_INVALID",
      `Not a gs:// object URI: ${uri}`,
    );
  return { bucket: match[1], object: match[2] };
}

const objectUrl = (base: string, uri: string) => {
  const { bucket, object } = parseGsUri(uri);
  return `${base}/storage/v1/b/${encodeURIComponent(bucket)}/o/${encodeURIComponent(object)}?alt=media`;
};

const adcPath = () =>
  process.env.GOOGLE_APPLICATION_CREDENTIALS ||
  join(homedir(), ".config", "gcloud", "application_default_credentials.json");

async function fileExists(path: string) {
  try {
    return (await stat(path)).isFile();
  } catch {
    return false;
  }
}

async function tokenResponse(response: Response, source: string) {
  if (!response.ok)
    throw new CorpusBootstrapError(
      "AUTH_FAILED",
      `${source} token request failed with HTTP ${response.status}.`,
    );
  const body = (await response.json().catch(() => undefined)) as
    | { access_token?: unknown }
    | undefined;
  if (typeof body?.access_token !== "string" || !body.access_token)
    throw new CorpusBootstrapError(
      "AUTH_FAILED",
      `${source} returned no access token.`,
    );
  return body.access_token;
}

async function metadataToken(fetcher: typeof fetch, host: string) {
  let response: Response;
  try {
    response = await fetcher(
      `http://${host}/computeMetadata/v1/instance/service-accounts/default/token`,
      { headers: { "metadata-flavor": "Google" } },
    );
  } catch (error) {
    throw new CorpusBootstrapError(
      "AUTH_FAILED",
      `Metadata server unreachable at ${host}: ${(error as Error).message}`,
    );
  }
  return tokenResponse(response, "Metadata server");
}

async function adcToken(fetcher: typeof fetch, path: string, tokenUrl: string) {
  let credentials: Record<string, unknown>;
  try {
    credentials = JSON.parse(await readFile(path, "utf8"));
  } catch {
    throw new CorpusBootstrapError(
      "AUTH_FAILED",
      `Application-default credentials at ${path} are unreadable.`,
    );
  }
  if (
    credentials.type !== "authorized_user" ||
    typeof credentials.client_id !== "string" ||
    typeof credentials.client_secret !== "string" ||
    typeof credentials.refresh_token !== "string"
  )
    throw new CorpusBootstrapError(
      "AUTH_FAILED",
      "Only authorized_user application-default credentials are supported; on Cloud Run the metadata server is used.",
    );
  const response = await fetcher(tokenUrl, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: credentials.client_id,
      client_secret: credentials.client_secret,
      refresh_token: credentials.refresh_token,
    }),
  });
  return tokenResponse(response, "OAuth");
}

/** Resolve a GCS access token the same way bootstrapCorpora does. */
export async function getAccessToken(
  options: Pick<
    BootstrapCorporaOptions,
    "auth" | "metadataHost" | "oauthTokenUrl" | "fetch"
  > = {},
): Promise<string> {
  const auth = options.auth ?? "auto";
  if (typeof auth === "function") return auth();
  const fetcher = options.fetch ?? fetch;
  const credentials = adcPath();
  const tokenUrl =
    options.oauthTokenUrl ?? "https://oauth2.googleapis.com/token";
  if (auth === "adc" || (auth === "auto" && (await fileExists(credentials))))
    return adcToken(fetcher, credentials, tokenUrl);
  return metadataToken(
    fetcher,
    options.metadataHost ||
      process.env.GCE_METADATA_HOST ||
      "metadata.google.internal",
  );
}

/** Parse and validate a manifest; throws MANIFEST_INVALID with every issue. */
export function parseCorpusManifest(value: unknown): CorpusManifest {
  const parsed = corpusManifestSchema.safeParse(value);
  if (!parsed.success)
    throw new CorpusBootstrapError(
      "MANIFEST_INVALID",
      `Corpus manifest is invalid: ${parsed.error.issues
        .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
        .join("; ")}`,
    );
  const unknown = Object.keys(parsed.data.corpora).filter(
    (id) => !(id in CORPUS_ENV_PREFIXES),
  );
  if (unknown.length)
    throw new CorpusBootstrapError(
      "MANIFEST_INVALID",
      `Corpus manifest lists unknown corpora: ${unknown.join(", ")}`,
    );
  for (const [id, entry] of Object.entries(parsed.data.corpora))
    if (!entry.uri.endsWith(`/${entry.file}`))
      throw new CorpusBootstrapError(
        "MANIFEST_INVALID",
        `Corpus manifest entry ${id}: uri does not end with its file name.`,
      );
  return parsed.data;
}

/**
 * Check a local artifact against its manifest entry. Returns null when both
 * the file and decoded SHA-256 (and sizes) match, otherwise the reason.
 */
export async function verifyCorpusFile(
  path: string,
  entry: Pick<
    CorpusManifestEntry,
    "file_sha256" | "file_bytes" | "decoded_sha256" | "decoded_bytes"
  >,
): Promise<string | null> {
  const info = await stat(path).catch(() => undefined);
  if (!info?.isFile()) return "file is missing";
  if (info.size !== entry.file_bytes)
    return `file is ${info.size} bytes, expected ${entry.file_bytes}`;
  const fileHash = createHash("sha256");
  const decodedHash = createHash("sha256");
  let decodedBytes = 0;
  try {
    await pipeline(
      createReadStream(path),
      new Transform({
        transform(chunk: Buffer, _encoding, callback) {
          fileHash.update(chunk);
          callback(null, chunk);
        },
      }),
      createZstdDecompress(),
      new Writable({
        write(chunk: Buffer, _encoding, callback) {
          decodedBytes += chunk.length;
          if (decodedBytes > entry.decoded_bytes)
            return callback(new Error("decoded output exceeds manifest size"));
          decodedHash.update(chunk);
          callback();
        },
      }),
    );
  } catch (error) {
    return `zstd decoding failed: ${(error as Error).message}`;
  }
  const file = fileHash.digest("hex");
  if (file !== entry.file_sha256)
    return `file sha256 ${file} does not match ${entry.file_sha256}`;
  if (decodedBytes !== entry.decoded_bytes)
    return `decoded size ${decodedBytes} does not match ${entry.decoded_bytes}`;
  const decoded = decodedHash.digest("hex");
  if (decoded !== entry.decoded_sha256)
    return `decoded sha256 ${decoded} does not match ${entry.decoded_sha256}`;
  return null;
}

async function get(
  fetcher: typeof fetch,
  url: string,
  token: string,
  what: string,
): Promise<Response> {
  let response: Response;
  try {
    response = await fetcher(url, {
      headers: { authorization: `Bearer ${token}` },
    });
  } catch (error) {
    throw new CorpusBootstrapError(
      "DOWNLOAD_FAILED",
      `${what}: request failed: ${(error as Error).message}`,
    );
  }
  if (!response.ok || !response.body) {
    await response.body?.cancel();
    throw new CorpusBootstrapError(
      "DOWNLOAD_FAILED",
      `${what}: HTTP ${response.status}`,
    );
  }
  return response;
}

async function readBounded(response: Response, limit: number, what: string) {
  const declared = Number(response.headers.get("content-length") ?? "0");
  if (declared > limit)
    throw new CorpusBootstrapError("DOWNLOAD_FAILED", `${what} is too large.`);
  const chunks: Uint8Array[] = [];
  let total = 0;
  for await (const chunk of response.body as unknown as AsyncIterable<Uint8Array>) {
    total += chunk.byteLength;
    if (total > limit)
      throw new CorpusBootstrapError(
        "DOWNLOAD_FAILED",
        `${what} is too large.`,
      );
    chunks.push(chunk);
  }
  return Buffer.concat(chunks, total);
}

async function downloadTo(
  response: Response,
  path: string,
  limit: number,
  what: string,
) {
  let total = 0;
  try {
    await pipeline(
      Readable.fromWeb(response.body as never),
      new Transform({
        transform(chunk: Buffer, _encoding, callback) {
          total += chunk.length;
          if (total > limit)
            return callback(new Error("download exceeds manifest size"));
          callback(null, chunk);
        },
      }),
      createWriteStream(path, { flags: "wx", mode: 0o644 }),
    );
  } catch (error) {
    throw new CorpusBootstrapError(
      "DOWNLOAD_FAILED",
      `${what}: ${(error as Error).message}`,
    );
  }
}

/**
 * Download and verify every corpus in a TypeScript corpus manifest.
 *
 * Files land at `<cacheDir>/<corpus>/<snapshot>/<file>`. A file already there
 * is rehashed (file and decoded SHA-256) and reused when it matches; otherwise
 * it is downloaded to a temporary name, verified, and renamed into place.
 * Throws CorpusBootstrapError on any failure; nothing unverified is returned.
 */
export async function bootstrapCorpora(
  manifestUri: string,
  cacheDir: string,
  options: BootstrapCorporaOptions = {},
): Promise<CorpusEnvironment> {
  const fetcher = options.fetch ?? fetch;
  const base = (
    options.storageBaseUrl ?? "https://storage.googleapis.com"
  ).replace(/\/+$/, "");
  const log = options.log ?? (() => {});
  const token = await getAccessToken(options);
  const manifestResponse = await get(
    fetcher,
    objectUrl(base, manifestUri),
    token,
    `Corpus manifest ${manifestUri}`,
  );
  let value: unknown;
  try {
    value = JSON.parse(
      (
        await readBounded(manifestResponse, MAX_MANIFEST_BYTES, "Manifest")
      ).toString("utf8"),
    );
  } catch (error) {
    if (error instanceof CorpusBootstrapError) throw error;
    throw new CorpusBootstrapError(
      "MANIFEST_INVALID",
      "Corpus manifest is not JSON.",
    );
  }
  const manifest = parseCorpusManifest(value);
  const wanted = options.corpora ?? CORPUS_IDS;
  const missing = wanted.filter((id) => !manifest.corpora[id]);
  if (missing.length)
    throw new CorpusBootstrapError(
      "CORPUS_MISSING",
      `Corpus manifest has no entry for: ${missing.join(", ")}`,
    );
  // Settle every download before reporting, so no temporary file outlives the call.
  const results = await Promise.allSettled(
    wanted.map(async (id) => {
      const entry = manifest.corpora[id] as CorpusManifestEntry;
      const directory = join(cacheDir, id, entry.snapshot);
      const target = join(directory, entry.file);
      await mkdir(directory, { recursive: true });
      const existing = await verifyCorpusFile(target, entry);
      if (existing === null) log(`${id}: verified cached ${target}`);
      else {
        const temporary = `${target}.${randomUUID()}.tmp`;
        try {
          const response = await get(
            fetcher,
            objectUrl(base, entry.uri),
            token,
            `${id} (${entry.uri})`,
          );
          await downloadTo(response, temporary, entry.file_bytes, id);
          const reason = await verifyCorpusFile(temporary, entry);
          if (reason)
            throw new CorpusBootstrapError(
              "VERIFICATION_FAILED",
              `${id} (${entry.uri}): ${reason}`,
            );
          await rename(temporary, target);
          log(`${id}: downloaded ${entry.file_bytes} bytes to ${target}`);
        } finally {
          await unlink(temporary).catch(() => {});
        }
      }
      return { id, target, entry };
    }),
  );
  const environment: CorpusEnvironment = {};
  for (const result of results) {
    if (result.status === "rejected") throw result.reason;
    const { id, target, entry } = result.value;
    const prefix = CORPUS_ENV_PREFIXES[id];
    environment[`${prefix}_CORPUS_PATH`] = target;
    environment[`${prefix}_CORPUS_SHA256`] = entry.decoded_sha256;
    environment[`${prefix}_CORPUS_FILE_SHA256`] = entry.file_sha256;
  }
  return environment;
}

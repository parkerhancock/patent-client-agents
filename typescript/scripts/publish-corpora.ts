/**
 * Build the TypeScript corpus manifest from local packaged artifacts and,
 * with --execute, upload them to gs://<bucket>/<prefix>/<corpus>/<snapshot>/<file>
 * and write gs://<bucket>/<prefix>/manifest.json.
 *
 * Dry run is the default: it verifies every local artifact and prints the
 * uploads and the manifest without touching the network. With --execute,
 * objects are created with If-Generation-Match: 0 (an existing object with the
 * same bytes is skipped, different bytes fail), and the manifest write is
 * conditioned on the generation read just before it, so a concurrent writer
 * makes the publish fail instead of being overwritten.
 *
 * Usage (from typescript/):
 *   bun scripts/publish-corpora.ts [--data-dir .data] [--bucket NAME] [--prefix ts]
 *   bun scripts/publish-corpora.ts --execute [--gcloud-account EMAIL]
 */
import { Database } from "bun:sqlite";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { zstdDecompressSync } from "node:zlib";
import {
  CORPUS_IDS,
  type CorpusId,
  type CorpusManifest,
  type CorpusManifestEntry,
  getAccessToken,
  MANIFEST_SCHEMA,
  MANIFEST_SCHEMA_VERSION,
  MAX_CORPUS_BYTES,
  parseCorpusManifest,
} from "../packages/client/src/corpus/bootstrap.js";

/** Local packaged artifact per corpus, relative to the data directory. */
export const LOCAL_ARTIFACTS: Record<CorpusId, string> = {
  mpep: "mpep/mpep.db.zst",
  tmep: "tmep/tmep.db.zst",
  ukipo_mopp: "ukipo_mopp/mopp.db.zst",
  epc: "epo-legal/epc.db.zst",
  epo_case_law: "epo-legal/caselaw.db.zst",
  epo_guidelines: "epo-legal/guidelines.db.zst",
  epo_pct_guidelines: "epo-legal/pct_guidelines.db.zst",
  epo_up_guidelines: "epo-legal/up_guidelines.db.zst",
  upc_statutes: "upc/upc_statutes.db.zst",
  dpma_statutes: "dpma_statutes/dpma_statutes.db.zst",
  ipo_in_statutes: "ipo-in/ipo_in_statutes.db.zst",
  ipo_in_mppp: "ipo-in/ipo_in_mppp.db.zst",
  ilpo_statutes: "ilpo_statutes/ilpo_statutes.db.zst",
  ipos_statutes: "ipos/ipos_statutes.db.zst",
  ipos_manuals: "ipos/ipos_manuals.db.zst",
  inpi_br_statutes: "inpi_br_statutes/inpi_br_statutes.db.zst",
  legifrance_ip: "legifrance_ip/legifrance_ip.db.zst",
};

class PublishError extends Error {}

const sha256 = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");

export interface PlannedUpload {
  corpus: CorpusId;
  local_path: string;
  uri: string;
  bytes: number;
  file_sha256: string;
  md5_base64: string;
}
export interface PublishPlan {
  bucket: string;
  manifest_uri: string;
  uploads: PlannedUpload[];
  manifest: CorpusManifest;
}

const metadataKeys = /^(schema_version|snapshot_date|source_version|.*_year)$/;

async function inspect(path: string) {
  const file = await readFile(path);
  if (file.length > MAX_CORPUS_BYTES)
    throw new PublishError(`${path} exceeds the reader size limit.`);
  const packaging = JSON.parse(
    await readFile(`${path}.manifest.json`, "utf8"),
  ) as Record<string, unknown>;
  const fileSha = sha256(file);
  if (
    packaging.file_sha256 !== fileSha ||
    packaging.file_bytes !== file.length ||
    packaging.compression !== "zstd"
  )
    throw new PublishError(
      `${path} does not match its packaging manifest (file).`,
    );
  const decoded = zstdDecompressSync(file, {
    maxOutputLength: MAX_CORPUS_BYTES,
  });
  const decodedSha = sha256(decoded);
  if (
    packaging.decoded_sha256 !== decodedSha ||
    packaging.decoded_bytes !== decoded.length
  )
    throw new PublishError(
      `${path} does not match its packaging manifest (decoded).`,
    );
  if (decoded[18] !== 1 || decoded[19] !== 1)
    throw new PublishError(`${path} is not a DELETE-journal SQLite corpus.`);
  const db = Database.deserialize(decoded, true);
  let meta: Record<string, string>;
  try {
    meta = Object.fromEntries(
      db
        .query<{ key: string; value: string }, []>(
          "SELECT key, value FROM meta",
        )
        .all()
        .filter((row) => metadataKeys.test(row.key) && row.value != null)
        .map((row) => [row.key, String(row.value)]),
    );
  } finally {
    db.close();
  }
  const snapshot = meta.snapshot_date;
  if (!snapshot || !/^\d{4}-\d{2}-\d{2}$/.test(snapshot))
    throw new PublishError(`${path} has no meta.snapshot_date.`);
  return {
    file,
    fileSha,
    decodedSha,
    decodedBytes: decoded.length,
    snapshot,
    meta,
    md5: createHash("md5").update(file).digest("base64"),
  };
}

/** Verify local artifacts and build the uploads and manifest. Offline. */
export async function planPublish(options: {
  dataDir: string;
  bucket: string;
  prefix: string;
  now?: Date;
}): Promise<PublishPlan> {
  const uploads: PlannedUpload[] = [];
  const corpora: Record<string, CorpusManifestEntry> = {};
  for (const id of CORPUS_IDS) {
    const localPath = resolve(options.dataDir, LOCAL_ARTIFACTS[id]);
    const info = await inspect(localPath);
    const file = localPath.split("/").at(-1) as string;
    const uri = `gs://${options.bucket}/${options.prefix}/${id}/${info.snapshot}/${file}`;
    uploads.push({
      corpus: id,
      local_path: localPath,
      uri,
      bytes: info.file.length,
      file_sha256: info.fileSha,
      md5_base64: info.md5,
    });
    corpora[id] = {
      snapshot: info.snapshot,
      uri,
      file,
      compression: "zstd",
      file_sha256: info.fileSha,
      file_bytes: info.file.length,
      decoded_sha256: info.decodedSha,
      decoded_bytes: info.decodedBytes,
      metadata: info.meta,
    };
  }
  const manifest = parseCorpusManifest({
    schema: MANIFEST_SCHEMA,
    schema_version: MANIFEST_SCHEMA_VERSION,
    generated_at: (options.now ?? new Date()).toISOString(),
    corpora,
  });
  return {
    bucket: options.bucket,
    manifest_uri: `gs://${options.bucket}/${options.prefix}/manifest.json`,
    uploads,
    manifest,
  };
}

const api = "https://storage.googleapis.com";
const objectPath = (uri: string) => uri.replace(/^gs:\/\/[^/]+\//, "");

async function objectInfo(bucket: string, name: string, token: string) {
  const response = await fetch(
    `${api}/storage/v1/b/${bucket}/o/${encodeURIComponent(name)}`,
    { headers: { authorization: `Bearer ${token}` } },
  );
  if (response.status === 404) return undefined;
  if (!response.ok)
    throw new PublishError(`Reading ${name} failed: HTTP ${response.status}`);
  return (await response.json()) as {
    generation: string;
    md5Hash?: string;
    size: string;
  };
}

async function upload(
  bucket: string,
  name: string,
  body: Uint8Array,
  contentType: string,
  generation: string,
  token: string,
  metadata: Record<string, string> = {},
) {
  const boundary = `corpus-${crypto.randomUUID()}`;
  const head = `--${boundary}\r\ncontent-type: application/json; charset=utf-8\r\n\r\n${JSON.stringify(
    { name, contentType, cacheControl: "no-store", metadata },
  )}\r\n--${boundary}\r\ncontent-type: ${contentType}\r\n\r\n`;
  const response = await fetch(
    `${api}/upload/storage/v1/b/${bucket}/o?uploadType=multipart&ifGenerationMatch=${generation}`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        "content-type": `multipart/related; boundary=${boundary}`,
      },
      body: Buffer.concat([
        Buffer.from(head),
        body,
        Buffer.from(`\r\n--${boundary}--\r\n`),
      ]),
    },
  );
  if (response.status === 412)
    throw new PublishError(
      `${name} changed since it was read (If-Generation-Match ${generation}); nothing was overwritten. Rerun.`,
    );
  if (!response.ok)
    throw new PublishError(`Uploading ${name} failed: HTTP ${response.status}`);
}

async function execute(plan: PublishPlan, token: string) {
  for (const item of plan.uploads) {
    const name = objectPath(item.uri);
    const existing = await objectInfo(plan.bucket, name, token);
    if (existing) {
      if (
        existing.md5Hash !== item.md5_base64 ||
        Number(existing.size) !== item.bytes
      )
        throw new PublishError(
          `${item.uri} already exists with different bytes; publish a new snapshot instead.`,
        );
      console.log(JSON.stringify({ skipped: item.uri, reason: "identical" }));
      continue;
    }
    await upload(
      plan.bucket,
      name,
      await readFile(item.local_path),
      "application/zstd",
      "0",
      token,
      { file_sha256: item.file_sha256 },
    );
    console.log(JSON.stringify({ uploaded: item.uri, bytes: item.bytes }));
  }
  const manifestName = objectPath(plan.manifest_uri);
  const current = await objectInfo(plan.bucket, manifestName, token);
  await upload(
    plan.bucket,
    manifestName,
    Buffer.from(`${JSON.stringify(plan.manifest, null, 2)}\n`),
    "application/json",
    current?.generation ?? "0",
    token,
  );
  console.log(
    JSON.stringify({
      wrote: plan.manifest_uri,
      if_generation_match: current?.generation ?? "0",
    }),
  );
}

async function gcloudToken(account: string) {
  const child = Bun.spawn(
    ["gcloud", "auth", "print-access-token", `--account=${account}`],
    { stdout: "pipe", stderr: "ignore" },
  );
  const token = (await new Response(child.stdout).text()).trim();
  if ((await child.exited) !== 0 || !token)
    throw new PublishError("gcloud could not issue an access token.");
  return token;
}

if (import.meta.main) {
  try {
    const args = Bun.argv.slice(2);
    const values: Record<string, string> = {};
    let executeFlag = false;
    for (let index = 0; index < args.length; index++) {
      const flag = args[index] as string;
      if (flag === "--execute") executeFlag = true;
      else if (flag === "--dry-run") executeFlag = false;
      else if (
        ["--data-dir", "--bucket", "--prefix", "--gcloud-account"].includes(
          flag,
        ) &&
        args[index + 1] &&
        !args[index + 1]?.startsWith("--")
      )
        values[flag] = args[++index] as string;
      else
        throw new PublishError(
          "Use [--dry-run | --execute] [--data-dir DIR] [--bucket NAME] [--prefix PREFIX] [--gcloud-account EMAIL].",
        );
    }
    const plan = await planPublish({
      dataDir: values["--data-dir"] ?? join(import.meta.dir, "..", ".data"),
      bucket: values["--bucket"] ?? "patentclient-mcp-corpora",
      prefix: values["--prefix"] ?? "ts",
    });
    const total = plan.uploads.reduce((sum, item) => sum + item.bytes, 0);
    console.log(
      JSON.stringify(
        {
          mode: executeFlag ? "execute" : "dry-run",
          uploads: plan.uploads.map((item) => ({
            from: item.local_path,
            to: item.uri,
            bytes: item.bytes,
            file_sha256: item.file_sha256,
            precondition: "ifGenerationMatch=0 (skip if identical)",
          })),
          total_bytes: total,
          manifest_uri: plan.manifest_uri,
          manifest_precondition:
            "ifGenerationMatch=<generation read at execute time, 0 if absent>",
          manifest: plan.manifest,
        },
        null,
        2,
      ),
    );
    if (executeFlag)
      await execute(
        plan,
        values["--gcloud-account"]
          ? await gcloudToken(values["--gcloud-account"])
          : await getAccessToken(),
      );
  } catch (error) {
    console.error(
      JSON.stringify({
        published: false,
        error: error instanceof Error ? error.message : String(error),
      }),
    );
    process.exitCode = 1;
  }
}

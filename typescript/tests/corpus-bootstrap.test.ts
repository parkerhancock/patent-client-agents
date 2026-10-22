import { Database } from "bun:sqlite";
import { afterAll, beforeAll, beforeEach, expect, test } from "bun:test";
import { createHash } from "node:crypto";
import {
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { EpcClient } from "@patent-client-agents/client";
import {
  bootstrapCorpora,
  CORPUS_IDS,
  CorpusBootstrapError,
  type CorpusId,
  MANIFEST_SCHEMA,
  parseCorpusManifest,
} from "@patent-client-agents/client/corpus-bootstrap";
import { LOCAL_ARTIFACTS, planPublish } from "../scripts/publish-corpora.js";

const hash = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");
const BUCKET = "test-corpora";
const TOKEN = "fake-access-token";

interface Fake {
  objects: Map<string, Uint8Array>;
  /** Replace an object's served bytes without changing the manifest. */
  override: Map<string, Uint8Array>;
  status: Map<string, number>;
  objectRequests: string[];
  metadataRequests: number;
  metadataStatus: number;
  oauthRequests: number;
}
const fake: Fake = {
  objects: new Map(),
  override: new Map(),
  status: new Map(),
  objectRequests: [],
  metadataRequests: 0,
  metadataStatus: 200,
  oauthRequests: 0,
};
let server: ReturnType<typeof Bun.serve>;
let base: string;
let host: string;
let work: string;

beforeAll(async () => {
  work = await mkdtemp(join(tmpdir(), "pca-corpus-bootstrap-"));
  server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      const url = new URL(request.url);
      if (
        url.pathname ===
        "/computeMetadata/v1/instance/service-accounts/default/token"
      ) {
        fake.metadataRequests++;
        if (request.headers.get("metadata-flavor") !== "Google")
          return new Response("missing header", { status: 403 });
        if (fake.metadataStatus !== 200)
          return new Response("no", { status: fake.metadataStatus });
        return Response.json({ access_token: TOKEN, expires_in: 3600 });
      }
      if (url.pathname === "/oauth/token") {
        fake.oauthRequests++;
        const form = new URLSearchParams(await request.text());
        if (form.get("refresh_token") !== "fake-refresh")
          return new Response("bad", { status: 400 });
        return Response.json({ access_token: TOKEN });
      }
      const match = /^\/storage\/v1\/b\/([^/]+)\/o\/(.+)$/.exec(url.pathname);
      if (match && url.searchParams.get("alt") === "media") {
        if (request.headers.get("authorization") !== `Bearer ${TOKEN}`)
          return new Response("unauthorized", { status: 401 });
        const name = decodeURIComponent(match[2] as string);
        fake.objectRequests.push(name);
        const status = fake.status.get(name);
        if (status) return new Response("error", { status });
        const body =
          fake.override.get(name) ??
          (match[1] === BUCKET ? fake.objects.get(name) : undefined);
        if (!body) return new Response("not found", { status: 404 });
        return new Response(body.slice());
      }
      return new Response("unexpected", { status: 500 });
    },
  });
  host = `127.0.0.1:${server.port}`;
  base = `http://${host}`;
});
afterAll(async () => {
  server.stop(true);
  await rm(work, { recursive: true, force: true });
});
beforeEach(() => {
  fake.objects.clear();
  fake.override.clear();
  fake.status.clear();
  fake.objectRequests = [];
  fake.metadataRequests = 0;
  fake.metadataStatus = 200;
  fake.oauthRequests = 0;
});

function corpusBytes(label: string) {
  const db = new Database(":memory:");
  try {
    db.exec(
      "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT); CREATE TABLE sample(text TEXT)",
    );
    db.query("INSERT INTO meta VALUES ('schema_version', '1')").run();
    db.query("INSERT INTO meta VALUES ('snapshot_date', '2026-05-14')").run();
    db.query("INSERT INTO sample VALUES (?)").run(`${label} `.repeat(500));
    const bytes = db.serialize();
    // Mark as DELETE journal mode, like a prepared artifact.
    bytes[18] = 1;
    bytes[19] = 1;
    return new Uint8Array(bytes);
  } finally {
    db.close();
  }
}

function entry(id: CorpusId, decoded: Uint8Array, snapshot = "2026-05-14") {
  const file = zstdCompressSync(decoded);
  const name = `ts/${id}/${snapshot}/${id}.db.zst`;
  fake.objects.set(name, file);
  return {
    snapshot,
    uri: `gs://${BUCKET}/${name}`,
    file: `${id}.db.zst`,
    compression: "zstd" as const,
    file_sha256: hash(file),
    file_bytes: file.length,
    decoded_sha256: hash(decoded),
    decoded_bytes: decoded.length,
  };
}

function publishManifest(
  corpora: Record<string, unknown>,
  extra: Record<string, unknown> = {},
) {
  const manifest = {
    schema: MANIFEST_SCHEMA,
    schema_version: 1,
    generated_at: "2026-10-22T12:00:00.000Z",
    corpora,
    ...extra,
  };
  fake.objects.set(
    "ts/manifest.json",
    new TextEncoder().encode(JSON.stringify(manifest)),
  );
  return manifest;
}

const options = {
  auth: "metadata" as const,
  storageBaseUrl: "",
  metadataHost: "",
};
const run = (cacheDir: string, corpora: CorpusId[] = ["epc", "mpep"]) =>
  bootstrapCorpora(`gs://${BUCKET}/ts/manifest.json`, cacheDir, {
    ...options,
    storageBaseUrl: base,
    metadataHost: host,
    corpora,
  });

async function newCache() {
  return mkdtemp(join(work, "cache-"));
}
async function listFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, {
    recursive: true,
    withFileTypes: true,
  });
  return entries
    .filter((item) => item.isFile())
    .map((item) => join(item.parentPath, item.name));
}
async function expectCode(promise: Promise<unknown>, code: string) {
  const error = await promise.then(
    () => undefined,
    (reason: unknown) => reason,
  );
  expect(error).toBeInstanceOf(CorpusBootstrapError);
  expect((error as CorpusBootstrapError).code).toBe(code as never);
  return error as CorpusBootstrapError;
}

test("downloads, verifies and returns reader environment for a real corpus", async () => {
  const epc = new Uint8Array(
    await readFile(join(import.meta.dir, "fixtures/epo-legal/epc.db")),
  );
  const mpep = corpusBytes("mpep");
  const epcEntry = entry("epc", epc);
  const mpepEntry = entry("mpep", mpep, "2026-10-20");
  publishManifest({ epc: epcEntry, mpep: mpepEntry });
  const cache = await newCache();
  const env = await run(cache);
  expect(fake.metadataRequests).toBe(1);
  expect(fake.objectRequests.sort()).toEqual([
    "ts/epc/2026-05-14/epc.db.zst",
    "ts/manifest.json",
    "ts/mpep/2026-10-20/mpep.db.zst",
  ]);
  expect(env).toEqual({
    EPC_CORPUS_PATH: join(cache, "epc/2026-05-14/epc.db.zst"),
    EPC_CORPUS_SHA256: hash(epc),
    EPC_CORPUS_FILE_SHA256: epcEntry.file_sha256,
    MPEP_CORPUS_PATH: join(cache, "mpep/2026-10-20/mpep.db.zst"),
    MPEP_CORPUS_SHA256: hash(mpep),
    MPEP_CORPUS_FILE_SHA256: mpepEntry.file_sha256,
  });
  expect(await listFiles(cache)).toHaveLength(2);
  // The reader accepts the path and both pins the bootstrap returned.
  const client = new EpcClient({
    corpusPath: env.EPC_CORPUS_PATH as string,
    expectedSha256: env.EPC_CORPUS_SHA256 as string,
    expectedFileSha256: env.EPC_CORPUS_FILE_SHA256 as string,
  });
  try {
    const status = await client.getCorpusStatus();
    expect(status.available).toBe(true);
    expect(status.artifact_sha256).toBe(hash(epc));
    expect((await client.getSection("Article 54")).href).toBe("a54");
  } finally {
    client.close();
  }
});

test("a rerun reuses verified files and replaces a corrupted one", async () => {
  publishManifest({
    epc: entry("epc", corpusBytes("epc")),
    mpep: entry("mpep", corpusBytes("mpep")),
  });
  const cache = await newCache();
  const first = await run(cache);
  fake.objectRequests = [];
  const second = await run(cache);
  expect(second).toEqual(first);
  expect(fake.objectRequests).toEqual(["ts/manifest.json"]);

  // Same size, different bytes: re-downloaded rather than trusted.
  const path = first.MPEP_CORPUS_PATH as string;
  const bytes = await readFile(path);
  bytes[bytes.length - 1] = (bytes.at(-1) ?? 0) ^ 0xff;
  await writeFile(path, bytes);
  fake.objectRequests = [];
  await run(cache);
  expect(fake.objectRequests.sort()).toEqual([
    "ts/manifest.json",
    "ts/mpep/2026-05-14/mpep.db.zst",
  ]);
  expect(hash(await readFile(path))).toBe(
    first.MPEP_CORPUS_FILE_SHA256 as string,
  );
});

test("a decoded sha256 mismatch throws and leaves nothing behind", async () => {
  const bad = entry("mpep", corpusBytes("mpep"));
  publishManifest({
    epc: entry("epc", corpusBytes("epc")),
    mpep: { ...bad, decoded_sha256: "0".repeat(64) },
  });
  const cache = await newCache();
  const error = await expectCode(run(cache), "VERIFICATION_FAILED");
  expect(error.message).toContain("decoded sha256");
  expect(
    (await listFiles(cache)).filter((path) => path.includes("/mpep/")),
  ).toEqual([]);
});

test("served bytes that differ from the file pin throw", async () => {
  const good = entry("mpep", corpusBytes("mpep"));
  publishManifest({ epc: entry("epc", corpusBytes("epc")), mpep: good });
  // Same length, different content.
  const other = new Uint8Array(
    fake.objects.get("ts/mpep/2026-05-14/mpep.db.zst") as Uint8Array,
  );
  other[other.length - 1] = (other.at(-1) ?? 0) ^ 0xff;
  fake.override.set("ts/mpep/2026-05-14/mpep.db.zst", other);
  const cache = await newCache();
  await expectCode(run(cache), "VERIFICATION_FAILED");
  expect(
    (await listFiles(cache)).filter((path) => path.includes("/mpep/")),
  ).toEqual([]);
});

test("a truncated download throws", async () => {
  const good = entry("mpep", corpusBytes("mpep"));
  publishManifest({ epc: entry("epc", corpusBytes("epc")), mpep: good });
  const full = fake.objects.get("ts/mpep/2026-05-14/mpep.db.zst") as Uint8Array;
  fake.override.set(
    "ts/mpep/2026-05-14/mpep.db.zst",
    full.subarray(0, Math.floor(full.length / 2)),
  );
  const cache = await newCache();
  const error = await expectCode(run(cache), "VERIFICATION_FAILED");
  expect(error.message).toContain("bytes, expected");
  expect(
    (await listFiles(cache)).filter((path) => path.includes("/mpep/")),
  ).toEqual([]);
});

test("an oversized download stops at the manifest size", async () => {
  const good = entry("mpep", corpusBytes("mpep"));
  publishManifest({ epc: entry("epc", corpusBytes("epc")), mpep: good });
  const full = fake.objects.get("ts/mpep/2026-05-14/mpep.db.zst") as Uint8Array;
  fake.override.set(
    "ts/mpep/2026-05-14/mpep.db.zst",
    new Uint8Array([...full, ...full]),
  );
  await expectCode(run(await newCache()), "DOWNLOAD_FAILED");
});

test("a required corpus missing from the manifest throws", async () => {
  publishManifest({ epc: entry("epc", corpusBytes("epc")) });
  const error = await expectCode(
    run(await newCache(), ["epc", "tmep"]),
    "CORPUS_MISSING",
  );
  expect(error.message).toContain("tmep");
  expect(fake.objectRequests).toEqual(["ts/manifest.json"]);
});

test("object and manifest HTTP errors throw", async () => {
  publishManifest({
    epc: entry("epc", corpusBytes("epc")),
    mpep: entry("mpep", corpusBytes("mpep")),
  });
  fake.status.set("ts/mpep/2026-05-14/mpep.db.zst", 503);
  await expectCode(run(await newCache()), "DOWNLOAD_FAILED");
  fake.objects.delete("ts/manifest.json");
  const error = await expectCode(run(await newCache()), "DOWNLOAD_FAILED");
  expect(error.message).toContain("404");
});

test.each([
  ["wrong schema version", { schema_version: 2 }, "schema_version"],
  ["Python manifest shape", { schema: undefined }, "schema"],
  ["unknown top-level key", { updated_at: "x" }, "updated_at"],
])("manifest schema error: %s", async (_label, extra, needle) => {
  publishManifest({ epc: entry("epc", corpusBytes("epc")) }, extra);
  const error = await expectCode(
    run(await newCache(), ["epc"]),
    "MANIFEST_INVALID",
  );
  expect(error.message).toContain(needle);
});

test("manifest entry errors are rejected before any download", async () => {
  const good = entry("epc", corpusBytes("epc"));
  for (const [corpora, needle] of [
    [{ epc: { ...good, file_sha256: "XYZ" } }, "file_sha256"],
    [{ epc: { ...good, compression: "gzip" } }, "compression"],
    [{ epc: { ...good, uri: "https://example.com/epc.db.zst" } }, "uri"],
    [{ epc: { ...good, file: "other.db.zst" } }, "file name"],
    [{ epc: { ...good, decoded_bytes: 2 ** 40 } }, "decoded_bytes"],
    [{ epc: good, nonsense: good }, "unknown corpora"],
  ] as const) {
    fake.objectRequests = [];
    publishManifest(corpora as Record<string, unknown>);
    const error = await expectCode(
      run(await newCache(), ["epc"]),
      "MANIFEST_INVALID",
    );
    expect(error.message).toContain(needle);
    expect(fake.objectRequests).toEqual(["ts/manifest.json"]);
  }
  fake.objects.set("ts/manifest.json", new TextEncoder().encode("{not json"));
  await expectCode(run(await newCache(), ["epc"]), "MANIFEST_INVALID");
});

test("authentication failures throw before any download", async () => {
  publishManifest({ epc: entry("epc", corpusBytes("epc")) });
  fake.metadataStatus = 500;
  await expectCode(run(await newCache(), ["epc"]), "AUTH_FAILED");
  expect(fake.objectRequests).toEqual([]);
  await expectCode(
    bootstrapCorpora(`gs://${BUCKET}/ts/manifest.json`, await newCache(), {
      storageBaseUrl: base,
      auth: "metadata",
      metadataHost: "127.0.0.1:1",
    }),
    "AUTH_FAILED",
  );
});

test("application-default user credentials are refreshed for a token", async () => {
  publishManifest({ epc: entry("epc", corpusBytes("epc")) });
  const credentials = join(work, "adc.json");
  await writeFile(
    credentials,
    JSON.stringify({
      type: "authorized_user",
      client_id: "fake-client",
      client_secret: "fake-secret",
      refresh_token: "fake-refresh",
    }),
  );
  const previous = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  process.env.GOOGLE_APPLICATION_CREDENTIALS = credentials;
  try {
    const env = await bootstrapCorpora(
      `gs://${BUCKET}/ts/manifest.json`,
      await newCache(),
      {
        storageBaseUrl: base,
        oauthTokenUrl: `${base}/oauth/token`,
        corpora: ["epc"],
      },
    );
    expect(fake.oauthRequests).toBe(1);
    expect(fake.metadataRequests).toBe(0);
    expect(env.EPC_CORPUS_PATH).toBeDefined();
  } finally {
    if (previous === undefined)
      delete process.env.GOOGLE_APPLICATION_CREDENTIALS;
    else process.env.GOOGLE_APPLICATION_CREDENTIALS = previous;
  }
});

// Publish dry run: build a data directory in the published layout.
async function dataDir() {
  const directory = await mkdtemp(join(work, "data-"));
  for (const id of CORPUS_IDS) {
    const path = join(directory, LOCAL_ARTIFACTS[id]);
    await mkdir(dirname(path), { recursive: true });
    const decoded = corpusBytes(id);
    const file = zstdCompressSync(decoded);
    await writeFile(path, file);
    await writeFile(
      `${path}.manifest.json`,
      JSON.stringify({
        file: path.split("/").at(-1),
        compression: "zstd",
        sha256: hash(decoded),
        bytes: decoded.length,
        decoded_sha256: hash(decoded),
        decoded_bytes: decoded.length,
        file_sha256: hash(file),
        file_bytes: file.length,
      }),
    );
  }
  return directory;
}

test("publish dry run prints every upload and a manifest the bootstrap accepts", async () => {
  const directory = await dataDir();
  const child = Bun.spawn(
    [
      process.execPath,
      join(import.meta.dir, "../scripts/publish-corpora.ts"),
      "--data-dir",
      directory,
      "--bucket",
      BUCKET,
    ],
    { stdout: "pipe", stderr: "pipe", env: { ...process.env, PATH: "" } },
  );
  const [stdout, code] = await Promise.all([
    new Response(child.stdout).text(),
    child.exited,
  ]);
  expect(code).toBe(0);
  const output = JSON.parse(stdout);
  expect(output.mode).toBe("dry-run");
  expect(output.manifest_uri).toBe(`gs://${BUCKET}/ts/manifest.json`);
  expect(output.uploads).toHaveLength(CORPUS_IDS.length);
  expect(output.uploads[0]).toMatchObject({
    from: join(directory, "mpep/mpep.db.zst"),
    to: `gs://${BUCKET}/ts/mpep/2026-05-14/mpep.db.zst`,
    precondition: "ifGenerationMatch=0 (skip if identical)",
  });
  expect(output.total_bytes).toBe(
    output.uploads.reduce(
      (sum: number, item: { bytes: number }) => sum + item.bytes,
      0,
    ),
  );
  const manifest = parseCorpusManifest(output.manifest);
  expect(Object.keys(manifest.corpora).sort()).toEqual([...CORPUS_IDS].sort());
  expect(manifest.corpora.epc?.metadata).toEqual({
    schema_version: "1",
    snapshot_date: "2026-05-14",
  });

  // Serve exactly what the dry run says it would upload; the bootstrap accepts it.
  for (const item of output.uploads)
    fake.objects.set(
      item.to.replace(`gs://${BUCKET}/`, ""),
      new Uint8Array(await readFile(item.from)),
    );
  fake.objects.set(
    "ts/manifest.json",
    new TextEncoder().encode(JSON.stringify(output.manifest)),
  );
  const env = await run(await newCache(), [...CORPUS_IDS]);
  expect(Object.keys(env)).toHaveLength(CORPUS_IDS.length * 3);
  expect(env.IPO_IN_MPPP_CORPUS_SHA256).toBe(
    manifest.corpora.ipo_in_mppp?.decoded_sha256 as string,
  );
});

test("publish refuses an artifact that disagrees with its packaging manifest", async () => {
  const directory = await dataDir();
  const path = join(directory, LOCAL_ARTIFACTS.tmep);
  await writeFile(path, zstdCompressSync(corpusBytes("different")));
  await expect(
    planPublish({ dataDir: directory, bucket: BUCKET, prefix: "ts" }),
  ).rejects.toThrow("packaging manifest");
});

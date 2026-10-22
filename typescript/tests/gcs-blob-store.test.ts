import { expect, test } from "bun:test";
import { generateKeyPairSync, sign, verify } from "node:crypto";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { configurationFromEnv } from "../packages/mcp/src/cli.js";
import {
  type BlobStore,
  DownloadStore,
  downloadResult,
} from "../packages/mcp/src/downloads.js";
import {
  contentDisposition,
  GcsBlobStore,
  gcsBlobStoreOptionsFromEnv,
  v4SigningParts,
} from "../packages/mcp/src/gcs-blob-store.js";
import { createServer } from "../packages/mcp/src/index.js";
import { detailToolOptions } from "../packages/mcp/src/shared.js";

const provenance = {
  source_url: "https://api.uspto.gov/document",
  source_name: "USPTO Open Data Portal",
  retrieved_at: "2026-10-22T12:00:00.000Z",
  cache_hit: false as const,
};
const bytes = new TextEncoder().encode("%PDF-1.7 synthetic document");
const signer = "pca-run@proj.iam.gserviceaccount.com";
const objectName =
  "downloads/0b6c0f3e-1111-4222-8333-444455556666/US 7,654,321 (B2).pdf";
const date = new Date("2026-10-22T12:00:00Z");

// Hand-written from Google's documented V4 canonical request format; the hash
// was computed independently. The same inputs and key give a URL identical to
// google-cloud-storage's generate_signed_url_v4.
const expectedCanonicalRequest = [
  "GET",
  "/pca-downloads/downloads/0b6c0f3e-1111-4222-8333-444455556666/US%207%2C654%2C321%20%28B2%29.pdf",
  "X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=pca-run%40proj.iam.gserviceaccount.com%2F20261022%2Fauto%2Fstorage%2Fgoog4_request&X-Goog-Date=20261022T120000Z&X-Goog-Expires=86400&X-Goog-SignedHeaders=host",
  "host:storage.googleapis.com",
  "",
  "host",
  "UNSIGNED-PAYLOAD",
].join("\n");
const expectedStringToSign = [
  "GOOG4-RSA-SHA256",
  "20261022T120000Z",
  "20261022/auto/storage/goog4_request",
  "80b187e372a4548337f9c53ef6f95767e26d726cdb9f4d30e2d905d50c83ef00",
].join("\n");

type Call = { url: string; init: RequestInit };
function fakeGoogle(
  options: { upload?: Response; signBlob?: Response; metadata?: boolean } = {},
) {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
  });
  const calls: Call[] = [];
  const fetcher = (async (input: string | URL, init: RequestInit = {}) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.startsWith("http://metadata.google.internal/")) {
      if (!options.metadata) throw new TypeError("fetch failed");
      const headers = { "Metadata-Flavor": "Google" };
      return url.endsWith("/email")
        ? new Response(signer, { headers })
        : Response.json(
            {
              access_token: "metadata-token",
              expires_in: 3599,
              token_type: "Bearer",
            },
            { headers },
          );
    }
    if (url.startsWith("https://storage.googleapis.com/upload/"))
      return options.upload ?? Response.json({ name: "ok" });
    if (url.includes(":signBlob")) {
      if (options.signBlob) return options.signBlob;
      const payload = Buffer.from(
        JSON.parse(String(init.body)).payload,
        "base64",
      );
      return Response.json({
        keyId: "k",
        signedBlob: sign("sha256", payload, privateKey).toString("base64"),
      });
    }
    throw new Error(`Unexpected request ${url}`);
  }) as typeof fetch;
  return { fetcher, calls, publicKey };
}

test("V4 signing matches the documented canonical request and verifies with the signer's key", async () => {
  const parts = v4SigningParts({
    bucket: "pca-downloads",
    objectName,
    signerEmail: signer,
    date,
    ttlSeconds: 86400,
  });
  expect(parts.canonicalRequest).toBe(expectedCanonicalRequest);
  expect(parts.stringToSign).toBe(expectedStringToSign);

  const google = fakeGoogle();
  const store = new GcsBlobStore({
    bucket: "pca-downloads",
    signerEmail: signer,
    accessToken: async () => "token",
    fetch: google.fetcher,
    now: () => date,
  });
  const signed = await store.sign(objectName);
  expect(signed.expiresAt.toISOString()).toBe("2026-10-23T12:00:00.000Z");
  const url = new URL(signed.url);
  expect(url.origin + url.pathname).toBe(
    "https://storage.googleapis.com/pca-downloads/downloads/0b6c0f3e-1111-4222-8333-444455556666/US%207%2C654%2C321%20%28B2%29.pdf",
  );
  const signature = url.searchParams.get("X-Goog-Signature") ?? "";
  expect(signature).toMatch(/^[0-9a-f]{512}$/);
  expect(
    verify(
      "sha256",
      Buffer.from(expectedStringToSign),
      google.publicKey,
      Buffer.from(signature, "hex"),
    ),
  ).toBe(true);
  const signCall = google.calls.find((call) => call.url.includes(":signBlob"));
  expect(signCall?.url).toBe(
    "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/pca-run%40proj.iam.gserviceaccount.com:signBlob",
  );
  expect(new Headers(signCall?.init.headers).get("authorization")).toBe(
    "Bearer token",
  );
});

test("put uploads a create-only multipart object under downloads/ with disposition metadata", async () => {
  const google = fakeGoogle({ metadata: true });
  const store = new GcsBlobStore({
    bucket: "pca-downloads",
    fetch: google.fetcher,
    env: { CLOUDSDK_CONFIG: await mkdtemp(join(tmpdir(), "pca-no-adc-")) },
  });
  const stored = await store.put({
    bytes,
    filename: "US 7654321.pdf",
    contentType: "application/pdf",
  });
  const upload = google.calls.find((call) => call.url.includes("/upload/"));
  if (!upload) throw new Error("No upload request");
  expect(upload.url).toBe(
    "https://storage.googleapis.com/upload/storage/v1/b/pca-downloads/o?uploadType=multipart&ifGenerationMatch=0",
  );
  expect(upload.init.method).toBe("POST");
  const headers = new Headers(upload.init.headers);
  expect(headers.get("authorization")).toBe("Bearer metadata-token");
  const boundary = /^multipart\/related; boundary=(.+)$/.exec(
    headers.get("content-type") ?? "",
  )?.[1];
  expect(boundary).toBeString();
  const body = Buffer.from(upload.init.body as Uint8Array).toString("latin1");
  const [, metaPart, filePart] = body.split(`--${boundary}`);
  const metadata = JSON.parse(metaPart?.split("\r\n\r\n")[1] ?? "");
  expect(metadata.name).toMatch(/^downloads\/[0-9a-f-]{36}\/US 7654321\.pdf$/);
  expect(metadata).toMatchObject({
    contentType: "application/pdf",
    contentDisposition: 'attachment; filename="US 7654321.pdf"',
    cacheControl: "private, no-store",
  });
  expect(filePart).toBe(
    "\r\nContent-Type: application/pdf\r\n\r\n%PDF-1.7 synthetic document\r\n",
  );
  expect(body.endsWith(`--${boundary}--\r\n`)).toBe(true);
  // The signer comes from the metadata server and the URL names the uploaded object.
  expect(new URL(stored.url).pathname).toBe(
    `/pca-downloads/${metadata.name.split("/").map(encodeURIComponent).join("/")}`,
  );
  expect(new URL(stored.url).searchParams.get("X-Goog-Credential")).toStartWith(
    `${signer}/`,
  );
});

test("signBlob and upload failures raise clear errors", async () => {
  const options = {
    bucket: "pca-downloads",
    signerEmail: signer,
    accessToken: async () => "token",
  };
  const object = { bytes, filename: "a.pdf", contentType: "application/pdf" };
  const denied = new GcsBlobStore({
    ...options,
    fetch: fakeGoogle({
      signBlob: Response.json(
        {
          error: {
            message: "Permission 'iam.serviceAccounts.signBlob' denied",
          },
        },
        { status: 403 },
      ),
    }).fetcher,
  });
  await expect(denied.put(object)).rejects.toThrow(
    /signBlob for pca-run@proj\.iam\.gserviceaccount\.com failed \(HTTP 403\).*roles\/iam\.serviceAccountTokenCreator/,
  );
  const failed = new GcsBlobStore({
    ...options,
    fetch: fakeGoogle({
      upload: Response.json(
        { error: { message: "Backend unavailable" } },
        { status: 503 },
      ),
    }).fetcher,
  });
  await expect(failed.put(object)).rejects.toThrow(
    "GCS upload to bucket pca-downloads failed (HTTP 503): Backend unavailable",
  );
  const noCredentials = new GcsBlobStore({
    bucket: "pca-downloads",
    fetch: fakeGoogle().fetcher,
    env: { CLOUDSDK_CONFIG: await mkdtemp(join(tmpdir(), "pca-no-adc-")) },
  });
  await expect(noCredentials.put(object)).rejects.toThrow(
    "No Google credentials",
  );
  expect(() => new GcsBlobStore({ bucket: "Bad/Bucket" })).toThrow("bucket");
  expect(
    () => new GcsBlobStore({ bucket: "ok-bucket", ttlSeconds: 604801 }),
  ).toThrow("TTL");
});

test("content disposition quotes safe names and adds an RFC 5987 form otherwise", () => {
  expect(contentDisposition("file.pdf")).toBe(
    'attachment; filename="file.pdf"',
  );
  expect(contentDisposition('a"b\\c%.pdf')).toBe(
    "attachment; filename=\"a_b_c_.pdf\"; filename*=UTF-8''a%22b%5Cc%25.pdf",
  );
  expect(contentDisposition("Größe\r\n.pdf")).toBe(
    "attachment; filename=\"Gr__e__.pdf\"; filename*=UTF-8''Gr%C3%B6%C3%9Fe%0D%0A.pdf",
  );
});

test("download tools return blob store URLs when configured and process URLs otherwise", async () => {
  const puts: unknown[] = [];
  const blobStore: BlobStore = {
    async put(object) {
      puts.push(object);
      return {
        url: "https://storage.googleapis.com/pca-downloads/downloads/x/file.pdf?X-Goog-Signature=ab",
        expiresAt: new Date("2026-10-23T12:00:00Z"),
      };
    },
  };
  const stub = async () => {
    throw new Error("unused");
  };
  for (const downloads of [
    { blobStore },
    { publicBaseUrl: "https://files.example.test", blobStore },
    { publicBaseUrl: "https://files.example.test" },
  ]) {
    const server = createServer({
      client: { search: stub, get: stub, getDocuments: stub },
      downloads,
    });
    server.tool(
      {
        ...detailToolOptions(),
        name: "download_fixture",
        description: "Retrieve synthetic document for transport verification.",
        input: z.object({}),
      },
      () =>
        downloadResult(bytes, 'bad/"name.pdf', "application/pdf", provenance),
    );
    const client = await Client.connect(server, {
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const result = await client.callTool<{
        download_url: string;
        expires_at: string;
        filename: string;
      }>("download_fixture", {});
      const content = result.structuredContent;
      if (downloads.blobStore) {
        expect(content?.download_url).toStartWith(
          "https://storage.googleapis.com/",
        );
        expect(content?.expires_at).toBe("2026-10-23T12:00:00.000Z");
      } else
        expect(content?.download_url).toStartWith(
          "https://files.example.test/downloads?id=",
        );
      expect(content?.filename).toBe("bad__name.pdf");
    } finally {
      await client.close();
      await server.close();
    }
  }
  expect(puts).toEqual([
    { bytes, filename: "bad__name.pdf", contentType: "application/pdf" },
    { bytes, filename: "bad__name.pdf", contentType: "application/pdf" },
  ]);
  expect(
    () =>
      new DownloadStore({
        publicBaseUrl: "https://files.example.test",
        mode: "authenticated",
        blobStore,
      }),
  ).toThrow("authenticated");
  await expect(
    new DownloadStore({ blobStore, maxBytes: 4 }).put(
      bytes,
      "a.pdf",
      "application/pdf",
      provenance,
    ),
  ).rejects.toThrow("size limit");
});

test("CLI configures GCS downloads from DOWNLOAD_* or Python's variable names", () => {
  const http = {
    MCP_TRANSPORT: "http",
    MCP_JWKS_URL: "https://identity.test/jwks",
    MCP_ISSUER: "https://identity.test",
    MCP_AUDIENCE: "patent-client-agents",
  };
  const configured = configurationFromEnv({
    ...http,
    DOWNLOAD_BUCKET: "pca-downloads",
  });
  const store = configured.downloads.blobStore;
  expect(store).toBeInstanceOf(GcsBlobStore);
  expect((store as GcsBlobStore).ttlSeconds).toBe(86400);
  expect((store as GcsBlobStore).prefix).toBe("downloads/");
  expect(configured.downloads).not.toHaveProperty("publicBaseUrl");
  expect(configurationFromEnv({}).downloads).toEqual({});
  expect(
    gcsBlobStoreOptionsFromEnv({
      LAW_TOOLS_CORE_GCS_BUCKET: "py-bucket",
      LAW_TOOLS_CORE_DOWNLOAD_TTL_SECONDS: "3600",
      DOWNLOAD_SIGNER_EMAIL: signer,
    }),
  ).toEqual({ bucket: "py-bucket", ttlSeconds: 3600, signerEmail: signer });
  expect(
    gcsBlobStoreOptionsFromEnv({
      DOWNLOAD_BUCKET: "ts-bucket",
      LAW_TOOLS_CORE_GCS_BUCKET: "py-bucket",
      DOWNLOAD_PREFIX: "ts-downloads",
    }),
  ).toEqual({ bucket: "ts-bucket", prefix: "ts-downloads" });
  expect(() =>
    configurationFromEnv({
      ...http,
      DOWNLOAD_BUCKET: "pca-downloads",
      MCP_PUBLIC_BASE_URL: "https://patents.example",
      MCP_DOWNLOAD_MODE: "authenticated",
    }),
  ).toThrow("authenticated");
});

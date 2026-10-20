import { expect, spyOn, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import {
  DownloadStore,
  downloadResult,
} from "../packages/mcp/src/downloads.js";
import { createServer } from "../packages/mcp/src/index.js";
import { detailToolOptions } from "../packages/mcp/src/shared.js";

const provenance = {
  source_url: "https://api.uspto.gov/document",
  source_name: "USPTO Open Data Portal",
  retrieved_at: new Date().toISOString(),
  cache_hit: false as const,
};
const bytes = new TextEncoder().encode("%PDF-1.7 synthetic document");
test("signed URLs retrieve exact bytes, support HEAD, and reject tampering", async () => {
  const store = new DownloadStore({
    publicBaseUrl: "https://files.example.test/patents",
    mode: "signed",
  });
  const result = await store.put(
    bytes,
    'unsafe/"document.pdf',
    "application/pdf",
    provenance,
  );
  if (!("download_url" in result)) throw new Error("Expected HTTP download");
  expect(result.download_url).toBeString();
  const url = result.download_url;
  const head = await store.handle(new Request(url, { method: "HEAD" }));
  expect(head.headers.get("content-length")).toBe(String(bytes.length));
  expect(await head.text()).toBe("");
  const response = await store.handle(new Request(url));
  expect(response.status).toBe(200);
  expect(new Uint8Array(await response.arrayBuffer())).toEqual(bytes);
  expect(response.headers.get("content-disposition")).toBe(
    'attachment; filename="unsafe__document.pdf"',
  );
  expect(response.headers.get("content-type")).toBe("application/pdf");
  expect(response.headers.get("cache-control")).toContain("no-store");
  for (const parameter of ["id", "expires", "signature"]) {
    const bad = new URL(url);
    bad.searchParams.set(parameter, `${bad.searchParams.get(parameter)}0`);
    expect((await store.handle(new Request(bad))).status).toBe(403);
  }
  const expired = new URL(url);
  expired.searchParams.set("expires", "1");
  expect((await store.handle(new Request(expired))).status).toBe(403);
  expect(
    (await store.handle(new Request(url, { method: "POST" }))).status,
  ).toBe(405);
  const other = new DownloadStore({
    publicBaseUrl: "https://files.example.test",
    mode: "signed",
  });
  expect((await other.handle(new Request(url))).status).toBe(403);
});
test("stdio downloads return a local file and enforce cache capacity", async () => {
  const store = new DownloadStore({ maxBytes: bytes.length });
  const result = await store.put(
    bytes,
    "file.pdf",
    "application/pdf",
    provenance,
  );
  if (!("file_path" in result)) throw new Error("Expected local download");
  expect(result.file_path).toBeString();
  expect(result).not.toHaveProperty("download_url");
  expect(new Uint8Array(await readFile(result.file_path as string))).toEqual(
    bytes,
  );
  await expect(
    store.put(bytes, "file.pdf", "application/pdf", provenance),
  ).rejects.toThrow("capacity");
});
test("actual FastMCP listener serves downloads without MCP bearer tokens and scopes signatures to its own store", async () => {
  const server = createServer({
    client: {
      search: async () => {
        throw new Error("unused");
      },
      get: async () => {
        throw new Error("unused");
      },
      getDocuments: async () => {
        throw new Error("unused");
      },
    },
    downloads: { publicBaseUrl: "http://127.0.0.1", mode: "signed" },
  });
  server.tool(
    {
      ...detailToolOptions(),
      name: "download_fixture",
      description: "Retrieve synthetic document for transport verification.",
      input: z.object({}),
    },
    () => downloadResult(bytes, "file.pdf", "application/pdf", provenance),
  );
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  await server.run({
    transport: "http",
    host: "127.0.0.1",
    port: 0,
    stateless: true,
  });
  try {
    const result = await client.callTool<{ download_url: string }>(
      "download_fixture",
      {},
    );
    const link = new URL(result.structuredContent?.download_url as string);
    const base = new URL(`http://127.0.0.1:${server.address?.port}`);
    link.host = base.host;
    const response = await fetch(link);
    expect(response.status).toBe(200);
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(bytes);
    link.searchParams.delete("signature");
    expect((await fetch(link)).status).toBe(403);
    expect(result.structuredContent).not.toHaveProperty("data");
  } finally {
    await client.close();
    await server.close();
  }
});

test("default one-time links coexist with authenticated REST issuer, audience, expiry, scope and ownership checks", async () => {
  const { generateKeyPairSync, sign } = await import("node:crypto");
  const { BearerAuth } = await import("@prefecthq/fastmcp-ts/client");
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
  });
  const identity = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch: () =>
      Response.json({
        keys: [
          {
            ...publicKey.export({ format: "jwk" }),
            kid: "download-key",
            alg: "RS256",
            use: "sig",
          },
        ],
      }),
  });
  const issuer = "https://identity.test",
    audience = "patent-client-agents";
  const token = (claims: Record<string, unknown> = {}) => {
    const encode = (value: object) =>
      Buffer.from(JSON.stringify(value)).toString("base64url");
    const input = `${encode({ alg: "RS256", kid: "download-key" })}.${encode({ iss: issuer, aud: audience, sub: "alice", exp: Math.floor(Date.now() / 1000) + 120, scope: "odp:read documents:read", ...claims })}`;
    return `${input}.${sign("RSA-SHA256", Buffer.from(input), privateKey).toString("base64url")}`;
  };
  const server = createServer({
    client: {
      search: async () => {
        throw new Error("unused");
      },
      get: async () => {
        throw new Error("unused");
      },
      getDocuments: async () => {
        throw new Error("unused");
      },
    },
    auth: {
      jwksUri: `http://127.0.0.1:${identity.port}/jwks`,
      issuer,
      audience,
    },
    downloads: { publicBaseUrl: "http://127.0.0.1" },
  });
  server.tool(
    {
      ...detailToolOptions(),
      name: "download_fixture",
      description: "Retrieve synthetic document for transport verification.",
      input: z.object({}),
    },
    () => downloadResult(bytes, "file.pdf", "application/pdf", provenance),
  );
  await server.run({
    transport: "http",
    host: "127.0.0.1",
    port: 0,
    stateless: true,
  });
  const client = await Client.connect(
    `http://127.0.0.1:${server.address?.port}/mcp`,
    { auth: new BearerAuth(token()), versionNegotiation: { mode: "legacy" } },
  );
  try {
    const result = await client.callTool<{ download_url: string }>(
      "download_fixture",
      {},
    );
    const url = new URL(result.structuredContent?.download_url as string);
    url.port = String(server.address?.port);
    expect(url.searchParams.has("signature")).toBe(true);
    const first = await fetch(url);
    expect(first.status).toBe(200);
    expect(new Uint8Array(await first.arrayBuffer())).toEqual(bytes);
    expect((await fetch(url)).status).toBe(410);
    // OAuth retrieval remains available for this artifact after its capability is spent.
    url.searchParams.delete("signature");
    url.searchParams.delete("expires");
    const get = (auth?: string) =>
      fetch(url, { headers: auth ? { Authorization: `Bearer ${auth}` } : {} });
    expect((await get()).status).toBe(401);
    for (const claims of [
      { aud: "wrong" },
      { iss: "wrong" },
      { exp: 1 },
      { exp: undefined },
    ])
      expect((await get(token(claims))).status).toBe(401);
    expect((await get(token({ scope: "odp:read" }))).status).toBe(403);
    expect((await get(token({ sub: "bob" }))).status).toBe(404);
    const response = await get(token());
    expect(response.status).toBe(200);
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(bytes);
    const queryToken = new URL(url);
    queryToken.searchParams.set("access_token", token());
    expect((await fetch(queryToken)).status).toBe(401);
  } finally {
    await client.close();
    await server.close();
    await identity.stop(true);
  }
});

test("valid MIME parameters normalize without blocking document publication", async () => {
  const store = new DownloadStore();
  try {
    const result = await store.put(
      bytes,
      "text.txt",
      "text/plain; charset=utf-8",
      provenance,
    );
    expect(result.content_type).toBe("text/plain");
  } finally {
    await store.close();
  }
});

test("one-time links allow HEAD and reject ranges without consuming, and only one concurrent GET wins", async () => {
  const store = new DownloadStore({
    publicBaseUrl: "https://files.example.test",
  });
  try {
    const result = await store.put(
      bytes,
      "file.pdf",
      "application/pdf",
      provenance,
    );
    if (!("download_url" in result)) throw new Error("Expected URL");
    const url = result.download_url;
    expect(
      (await store.handle(new Request(url, { method: "HEAD" }))).status,
    ).toBe(200);
    expect(
      (
        await store.handle(
          new Request(url, { headers: { Range: "bytes=0-3" } }),
        )
      ).status,
    ).toBe(416);
    const responses = await Promise.all(
      Array.from({ length: 8 }, () => store.handle(new Request(url))),
    );
    expect(
      responses.filter((response) => response.status === 200),
    ).toHaveLength(1);
    expect(
      responses.filter((response) => response.status === 410),
    ).toHaveLength(7);
    const success = responses.find((response) => response.status === 200);
    expect(await success?.text()).toBe(new TextDecoder().decode(bytes));
    expect(
      (await store.handle(new Request(url, { method: "HEAD" }))).status,
    ).toBe(410);
    const fresh = await store.put(
      bytes,
      "file.pdf",
      "application/pdf",
      provenance,
    );
    if (!("download_url" in fresh)) throw new Error("Expected URL");
    const discarded = await store.handle(new Request(fresh.download_url));
    expect(discarded.status).toBe(200);
    await discarded.body?.cancel();
    expect((await store.handle(new Request(fresh.download_url))).status).toBe(
      410,
    );
  } finally {
    await store.close();
  }
});

test("authenticated-only issuance remains available and does not consume retrievals", async () => {
  const store = new DownloadStore({
    publicBaseUrl: "https://files.example.test",
    mode: "authenticated",
  });
  try {
    const result = await store.put(
      bytes,
      "file.pdf",
      "application/pdf",
      provenance,
      "alice",
    );
    if (!("download_url" in result)) throw new Error("Expected URL");
    expect(new URL(result.download_url).searchParams.has("signature")).toBe(
      false,
    );
    expect((await store.handle(new Request(result.download_url))).status).toBe(
      404,
    );
    for (let attempt = 0; attempt < 2; attempt++)
      expect(
        (await store.handle(new Request(result.download_url), "alice")).status,
      ).toBe(200);
  } finally {
    await store.close();
  }
});

test("an unaltered one-time token expires even before periodic cleanup", async () => {
  const store = new DownloadStore({
    publicBaseUrl: "https://files.example.test",
    ttlSeconds: 1,
  });
  const clock = spyOn(Date, "now");
  try {
    const result = await store.put(
      bytes,
      "file.pdf",
      "application/pdf",
      provenance,
    );
    if (!("download_url" in result)) throw new Error("Expected URL");
    clock.mockReturnValue(Date.now() + 10_000);
    expect((await store.handle(new Request(result.download_url))).status).toBe(
      403,
    );
  } finally {
    clock.mockRestore();
    await store.close();
  }
});

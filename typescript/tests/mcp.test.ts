import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import type { ApplicationsClient } from "@patent-client-agents/client";
import { createServer } from "@patent-client-agents/mcp";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { configurationFromEnv } from "../packages/mcp/src/cli.js";

const provenance = {
  source_url: "https://api.uspto.gov/api/v1/patent/applications/search",
  source_name: "USPTO Open Data Portal" as const,
  retrieved_at: "2026-10-20T12:00:00.000Z",
  cache_hit: false as const,
};

function stubClient(): Pick<
  ApplicationsClient,
  "search" | "get" | "getDocuments"
> {
  return {
    async search(options) {
      return {
        count: 2,
        patentBag: [
          { applicationNumberText: options?.offset ? "16123457" : "16123456" },
        ],
        provenance,
      };
    },
    async get(number) {
      if (number === "missing")
        throw Object.assign(new Error("Missing"), { status: 404 });
      if (number === "forbidden")
        throw Object.assign(new Error("Forbidden"), { status: 403 });
      return {
        count: 1,
        patentBag: [{ applicationNumberText: number }],
        provenance,
      };
    },
    async getDocuments() {
      return {
        documents: [
          { documentIdentifier: "doc1" },
          { documentIdentifier: "doc2" },
        ],
        provenance,
      };
    },
  };
}

test("MCP initializes, advertises schemas, calls the library, and binds cursors to the query", async () => {
  const server = createServer({ client: stubClient() });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    expect(client.getServerInfo()?.name).toBe("patent-client-agents");
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name).sort()).toEqual([
      "get_application",
      "list_file_history",
      "search_applications",
    ]);
    expect(
      tools.every(
        (tool) => tool.annotations?.readOnlyHint && tool.outputSchema,
      ),
    ).toBe(true);
    const first = await client.callTool<{
      next_cursor: string;
      items: unknown[];
    }>("search_applications", { query: "widget", limit: 1 });
    expect(first.structuredContent?.items).toHaveLength(1);
    expect(first.structuredContent?.next_cursor).toBeString();
    const second = await client.callTool<{
      items: { applicationNumberText: string }[];
      more_available: boolean;
    }>("search_applications", {
      query: "widget",
      limit: 1,
      cursor: first.structuredContent?.next_cursor,
    });
    expect(second.structuredContent?.items[0]?.applicationNumberText).toBe(
      "16123457",
    );
    expect(second.structuredContent?.more_available).toBe(false);
    await expect(
      client.callTool("search_applications", {
        query: "different",
        limit: 1,
        cursor: first.structuredContent?.next_cursor,
      }),
    ).rejects.toThrow("different query");
    await expect(
      client.callTool("search_applications", { limit: 0 }),
    ).rejects.toThrow();
    await expect(
      client.callTool("search_applications", { cursor: "not-a-cursor" }),
    ).rejects.toThrow("Invalid pagination cursor");
  } finally {
    await client.close();
    await server.close();
  }
});

test("portfolio retrieval collects only missing records and file history paginates", async () => {
  const server = createServer({ client: stubClient() });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await client.callTool<{
      items: unknown[];
      not_found: string[];
    }>("get_application", { application_numbers: ["16123456", "missing"] });
    expect(result.structuredContent?.items).toHaveLength(1);
    expect(result.structuredContent?.not_found).toEqual(["missing"]);
    await expect(
      client.callTool("get_application", { application_numbers: "missing" }),
    ).rejects.toThrow("Missing");
    await expect(
      client.callTool("get_application", {
        application_numbers: ["16123456", "forbidden"],
      }),
    ).rejects.toThrow("Forbidden");
    const first = await client.callTool<{
      next_cursor: string;
      items: unknown[];
    }>("list_file_history", { application_number: "16123456", limit: 1 });
    expect(first.structuredContent?.items).toHaveLength(1);
    const second = await client.callTool<{
      items: { documentIdentifier: string }[];
    }>("list_file_history", {
      application_number: "16123456",
      limit: 1,
      cursor: first.structuredContent?.next_cursor,
    });
    expect(second.structuredContent?.items[0]?.documentIdentifier).toBe("doc2");
  } finally {
    await client.close();
    await server.close();
  }
});

test("HTTP configuration requires explicit secure identity settings", () => {
  expect(configurationFromEnv({}).transport).toBe("stdio");
  expect(() => configurationFromEnv({ MCP_TRANSPORT: "http" })).toThrow();
  expect(() =>
    configurationFromEnv({
      MCP_TRANSPORT: "http",
      MCP_JWKS_URL: "http://identity.test/jwks",
      MCP_ISSUER: "https://identity.test",
      MCP_AUDIENCE: "patent-client-agents",
    }),
  ).toThrow("HTTPS");
});

test("Bun HTTP rejects missing, wrong-audience, and expired tokens and enforces tool scope", async () => {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
  });
  const jwk = {
    ...publicKey.export({ format: "jwk" }),
    kid: "test-key",
    alg: "RS256",
    use: "sig",
  };
  const identity = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch: () => Response.json({ keys: [jwk] }),
  });
  const issuer = "https://identity.test";
  const audience = "patent-client-agents";
  const server = createServer({
    client: stubClient(),
    auth: {
      jwksUri: `http://127.0.0.1:${identity.port}/jwks`,
      issuer,
      audience,
    },
  });
  await server.run({
    transport: "http",
    host: "127.0.0.1",
    port: 0,
    stateless: true,
  });
  const url = `http://127.0.0.1:${server.address?.port}/mcp`;
  const token = (claims: Record<string, unknown>) => {
    const encode = (value: object) =>
      Buffer.from(JSON.stringify(value)).toString("base64url");
    const unsigned = `${encode({ alg: "RS256", kid: "test-key", typ: "JWT" })}.${encode({ iss: issuer, aud: audience, sub: "test-user", exp: Math.floor(Date.now() / 1000) + 120, scope: "odp:read", ...claims })}`;
    return `${unsigned}.${sign("RSA-SHA256", Buffer.from(unsigned), privateKey).toString("base64url")}`;
  };
  const post = (value?: string) =>
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
        ...(value ? { Authorization: `Bearer ${value}` } : {}),
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocolVersion: "2025-11-25",
          capabilities: {},
          clientInfo: { name: "test", version: "1" },
        },
      }),
    });
  try {
    expect((await post()).status).toBe(401);
    expect((await post(token({ aud: "other-service" }))).status).toBe(401);
    expect(
      (await post(token({ iss: "https://other-issuer.test" }))).status,
    ).toBe(401);
    expect((await post(token({ exp: 1 }))).status).toBe(401);
    expect((await post(token({ exp: undefined }))).status).toBe(401);
    const client = await Client.connect(url, {
      auth: new BearerAuth(token({})),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await client.listTools()).length).toBe(3);
      expect((await client.callTool("search_applications", {})).isError).toBe(
        false,
      );
    } finally {
      await client.close();
    }
    const denied = await Client.connect(url, {
      auth: new BearerAuth(token({ scope: "other:read" })),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect(await denied.listTools()).toEqual([]);
      await expect(
        denied.callTool("search_applications", {}),
      ).rejects.toThrow();
    } finally {
      await denied.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

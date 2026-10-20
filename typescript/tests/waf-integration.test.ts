import { expect, test } from "bun:test";
import { mkdtemp, rmdir, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  createFileWafSessionStore,
  createWafSessionProvider,
  type WafSession,
} from "@patent-client-agents/waf-session";
import { Client } from "@prefecthq/fastmcp-ts/client";
import {
  TrademarkSearchClient,
  WAF_USER_AGENT,
  type WafToken,
} from "../packages/client/src/trademark-search.js";
import { configurationFromEnv } from "../packages/mcp/src/cli.js";
import {
  createServer,
  wafSessionSourceFromEnv,
} from "../packages/mcp/src/index.js";

const session = (token: string): WafSession => ({
  token,
  expires: Date.now() / 1000 + 86400,
  acquired: Date.now() / 1000,
  userAgent: WAF_USER_AGENT,
});
const emptyResult = () => Response.json({ hits: { totalValue: 0, hits: [] } });
const fakeFetch = (
  handler: (request: Request) => Response | Promise<Response>,
): typeof fetch =>
  Object.assign(
    async (input: RequestInfo | URL, init?: RequestInit) =>
      handler(new Request(input, init)),
    { preconnect: fetch.preconnect },
  ) as typeof fetch;

test("WAF source configuration selects one explicit delivery source and rejects ambiguous settings", () => {
  expect(wafSessionSourceFromEnv({})).toBeUndefined();
  expect(
    configurationFromEnv({ PCA_WAF_TOKEN_FILE: "/trusted/session.json" })
      .wafSession,
  ).toEqual({ filePath: "/trusted/session.json" });
  expect(
    wafSessionSourceFromEnv({
      PCA_WAF_SECRET_RESOURCE: "projects/example/secrets/waf-session",
    }),
  ).toEqual({ secretResource: "projects/example/secrets/waf-session" });
  expect(() =>
    configurationFromEnv({
      PCA_WAF_TOKEN_FILE: "/trusted/session.json",
      PCA_WAF_SECRET_RESOURCE: "projects/example/secrets/waf-session",
    }),
  ).toThrow("not both");
  expect(() => configurationFromEnv({ PCA_WAF_TOKEN_FILE: " " })).toThrow(
    "must be nonempty",
  );
});

test("trusted provider supersedes static sessions and warm requests adopt session and UA rotation", async () => {
  let latest = session("trusted-one");
  const seen: { cookie: string | null; ua: string | null }[] = [];
  const api = new TrademarkSearchClient({
    token: session("stale-static"),
    userAgent: "outdated-static-UA",
    sessionProvider: createWafSessionProvider(
      { read: async () => latest },
      { pollIntervalMs: 0 },
    ),
    fetch: fakeFetch((request) => {
      seen.push({
        cookie: request.headers.get("cookie"),
        ua: request.headers.get("user-agent"),
      });
      return emptyResult();
    }),
    retryLimit: 0,
  });
  await api.searchWordmark("sample");
  latest = { ...session("trusted-two"), userAgent: "Rotated browser UA" };
  await api.searchWordmark("sample");
  expect(seen).toEqual([
    { cookie: "aws-waf-token=trusted-one", ua: WAF_USER_AGENT },
    { cookie: "aws-waf-token=trusted-two", ua: "Rotated browser UA" },
  ]);
});

test("early WAF rejection reloads a rotated store once for concurrent searches", async () => {
  let latest = session("old-session");
  let reads = 0;
  let requests = 0;
  const api = new TrademarkSearchClient({
    sessionProvider: createWafSessionProvider({
      read: async () => {
        reads++;
        await Bun.sleep(5);
        return latest;
      },
    }),
    fetch: fakeFetch((request) => {
      requests++;
      if (request.headers.get("cookie") === "aws-waf-token=old-session") {
        latest = session("new-session");
        return new Response("Challenge", { status: 202 });
      }
      expect(request.headers.get("cookie")).toBe("aws-waf-token=new-session");
      return emptyResult();
    }),
    retryLimit: 0,
  });
  const results = await Promise.all([
    api.searchWordmark("one"),
    api.searchWordmark("two"),
    api.searchWordmark("three"),
  ]);
  expect(results).toHaveLength(3);
  expect(reads).toBe(2);
  expect(requests).toBe(6);
});

test("even a custom provider cannot retry a rejected cookie unchanged", async () => {
  const token = session("private-rejected-cookie");
  const refreshes: boolean[] = [];
  let requests = 0;
  const api = new TrademarkSearchClient({
    sessionProvider: {
      load: async ({ forceRefresh, rejectedToken }) => {
        refreshes.push(forceRefresh);
        if (forceRefresh) expect(rejectedToken).toEqual(token);
        return forceRefresh ? { ...token, expires: token.expires + 30 } : token;
      },
    },
    fetch: fakeFetch(() => {
      requests++;
      return new Response("Challenge", { status: 403 });
    }),
    retryLimit: 0,
  });
  try {
    await api.searchWordmark("sample");
    throw new Error("Expected session rejection");
  } catch (error) {
    expect(error).toMatchObject({ code: "AUTHENTICATION", status: 403 });
    expect(String(error)).not.toContain(token.token);
    expect(error).not.toHaveProperty("cause");
  }
  expect(refreshes).toEqual([false, true]);
  expect(requests).toBe(1);
});

test("cancelled provider subscriber does not cancel a shared load for other callers", async () => {
  let release: (token: WafSession) => void = () => {};
  const pending = new Promise<WafSession>((resolve) => {
    release = resolve;
  });
  let reads = 0;
  let requests = 0;
  const api = new TrademarkSearchClient({
    sessionProvider: createWafSessionProvider({
      read: () => {
        reads++;
        return pending;
      },
    }),
    fetch: fakeFetch(() => {
      requests++;
      return emptyResult();
    }),
    retryLimit: 0,
  });
  const controller = new AbortController();
  const cancelled = api.searchWordmark("cancelled", {
    signal: controller.signal,
  });
  const active = api.searchWordmark("active");
  controller.abort();
  await expect(cancelled).rejects.toMatchObject({ code: "ABORTED" });
  release(session("shared-valid"));
  await expect(active).resolves.toMatchObject({ count: 0 });
  expect(reads).toBe(1);
  expect(requests).toBe(1);
});

test("provider deadlines and exceptions are credential-safe and make no upstream request", async () => {
  for (const provider of [
    createWafSessionProvider(
      { read: () => new Promise(() => {}) },
      { timeoutMs: 5 },
    ),
    {
      load: async () => {
        throw new Error("private-provider-cookie");
      },
    },
    { load: async () => null as unknown as WafToken },
  ]) {
    let requests = 0;
    const api = new TrademarkSearchClient({
      sessionProvider: provider,
      fetch: fakeFetch(() => {
        requests++;
        return emptyResult();
      }),
      retryLimit: 0,
    });
    try {
      await api.searchWordmark("sample");
      throw new Error("Expected provider failure");
    } catch (error) {
      expect(error).toMatchObject({ name: "ConfigurationError" });
      expect(String(error)).not.toContain("private-provider-cookie");
      expect(error).not.toHaveProperty("cause");
    }
    expect(requests).toBe(0);
  }
});

test("default MCP wiring reloads the trusted file after rotation without restarting the server", async () => {
  const directory = await mkdtemp(join(tmpdir(), "pca-waf-integration-"));
  const path = join(directory, "session.json");
  const store = createFileWafSessionStore(path);
  await store.write(session("initial-file-cookie"));
  const originalFetch = globalThis.fetch;
  const environment = new Map(
    ["PCA_WAF_TOKEN_FILE", "PCA_WAF_SECRET_RESOURCE", "PCA_WAF_TOKEN_JSON"].map(
      (key) => [key, process.env[key]],
    ),
  );
  process.env.PCA_WAF_TOKEN_FILE = path;
  delete process.env.PCA_WAF_SECRET_RESOURCE;
  process.env.PCA_WAF_TOKEN_JSON = JSON.stringify(
    session("frozen-environment-cookie"),
  );
  const seen: string[] = [];
  globalThis.fetch = fakeFetch((request) => {
    expect(new URL(request.url).origin).toBe("https://tmsearch.uspto.gov");
    const cookie = request.headers.get("cookie") ?? "";
    seen.push(cookie);
    if (seen.length > 1 && cookie === "aws-waf-token=initial-file-cookie")
      return new Response("Challenge", { status: 202 });
    return emptyResult();
  });
  let server: ReturnType<typeof createServer> | undefined;
  let client: Awaited<ReturnType<typeof Client.connect>> | undefined;
  try {
    server = createServer();
    client = await Client.connect(server, {
      versionNegotiation: { mode: "legacy" },
    });
    const first = await client.callTool("search_trademarks", {
      wordmark: "sample",
      limit: 1,
    });
    expect(first.isError).not.toBe(true);
    await store.write(session("rotated-file-cookie"));
    const second = await client.callTool("search_trademarks", {
      wordmark: "sample",
      limit: 1,
    });
    expect(second.isError).not.toBe(true);
    expect(seen).toEqual([
      "aws-waf-token=initial-file-cookie",
      "aws-waf-token=initial-file-cookie",
      "aws-waf-token=rotated-file-cookie",
    ]);
    expect(JSON.stringify([first, second])).not.toContain("file-cookie");
  } finally {
    try {
      await client?.close();
      await server?.close();
    } finally {
      globalThis.fetch = originalFetch;
      for (const [key, value] of environment) {
        if (value === undefined) delete process.env[key];
        else process.env[key] = value;
      }
      await unlink(path);
      await rmdir(directory);
    }
  }
});

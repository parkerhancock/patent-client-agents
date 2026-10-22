import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { createServer } from "../packages/mcp/src/index.js";
import { hostedEnv, type Running, rpc, startHosted } from "./hosted-helpers.js";

/** Every public route, against the real listener, in OAuth and bypass modes. */
let hosted: Running;
let bypass: Running;

beforeAll(async () => {
  hosted = await startHosted(hostedEnv());
  bypass = await startHosted({ AUTH_BYPASS: "true" });
});
afterAll(async () => {
  await hosted.stop();
  await bypass.stop();
});

const get = (
  base: string,
  path: string,
  headers: Record<string, string> = {},
) => fetch(`${base}${path}`, { redirect: "manual", headers });

function expectSecurityHeaders(response: Response) {
  expect(response.headers.get("x-content-type-options")).toBe("nosniff");
  expect(response.headers.get("x-frame-options")).toBe("DENY");
  expect(response.headers.get("referrer-policy")).toBe(
    "strict-origin-when-cross-origin",
  );
}

describe("smoke-test contract (deploy repo .github/workflows/smoke-test.yml)", () => {
  test("1. /-/health returns {status: ok}", async () => {
    const response = await get(hosted.url, "/-/health");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
    expectSecurityHeaders(response);
  });

  test("2. landing page is text/html with the install affordances", async () => {
    const response = await get(hosted.url, "/");
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toStartWith("text/html");
    const body = await response.text();
    expect(body).toContain("Connect your client");
    expect(body).toContain(`${hosted.url}/mcp`);
    expect(body).toContain(`"mcpServers"`);
    expect(body).toContain(
      "/plugin marketplace add parkerhancock/patent-client-agents",
    );
    expect(body).not.toMatch(/{{|{%/);
    expect(response.headers.get("content-security-policy")).toContain(
      "form-action 'self' https://accounts.google.com",
    );
    expectSecurityHeaders(response);
  });

  test("3. robots.txt disallows the OAuth surface", async () => {
    const response = await get(hosted.url, "/robots.txt");
    expect(response.status).toBe(200);
    const body = await response.text();
    for (const path of [
      "/authorize",
      "/token",
      "/register",
      "/consent",
      "/auth/",
      "/mcp",
    ])
      expect(body).toContain(`Disallow: ${path}\n`);
  });

  test("4. /favicon.ico serves image bytes without a redirect", async () => {
    const response = await get(hosted.url, "/favicon.ico");
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toStartWith("image/");
    expect((await response.arrayBuffer()).byteLength).toBe(74682);
  });

  test("5. GET /mcp redirects browsers to the landing page", async () => {
    const browser = await get(hosted.url, "/mcp", {
      accept: "text/html,application/xhtml+xml",
    });
    expect(browser.status).toBe(302);
    expect(browser.headers.get("location")).toBe("/");
    for (const accept of [
      "text/event-stream",
      "*/*",
      "text/html, text/event-stream",
    ]) {
      const client = await get(hosted.url, "/mcp", { accept });
      expect([accept, client.status]).toEqual([accept, 405]);
      expect(client.headers.get("allow")).toBe("POST, DELETE");
    }
  });

  test("6. POST /mcp without auth is 401 with a resource_metadata challenge", async () => {
    const { status, response, body } = await rpc(hosted.url, "tools/list");
    expect(status).toBe(401);
    expect(response.headers.get("www-authenticate")).toMatch(
      /^Bearer .*resource_metadata="[^"]+\/\.well-known\/oauth-protected-resource\/mcp"/,
    );
    expect(body?.error).toBe("invalid_token");
  });

  test("7. authorization-server metadata is well formed", async () => {
    for (const path of [
      "/.well-known/oauth-authorization-server",
      "/.well-known/oauth-authorization-server/mcp",
    ]) {
      const response = await get(hosted.url, path);
      expect(response.status).toBe(200);
      expect(response.headers.get("access-control-allow-origin")).toBe("*");
      const metadata = (await response.json()) as Record<string, unknown>;
      expect(metadata).toMatchObject({
        issuer: hosted.url,
        authorization_endpoint: `${hosted.url}/authorize`,
        token_endpoint: `${hosted.url}/token`,
        registration_endpoint: `${hosted.url}/register`,
        revocation_endpoint: `${hosted.url}/revoke`,
        response_types_supported: ["code"],
        grant_types_supported: ["authorization_code", "refresh_token"],
        code_challenge_methods_supported: ["S256"],
        scopes_supported: [
          "openid",
          "https://www.googleapis.com/auth/userinfo.email",
          "https://www.googleapis.com/auth/userinfo.profile",
        ],
      });
    }
    const preflight = await fetch(`${hosted.url}/token`, { method: "OPTIONS" });
    expect(preflight.status).toBe(204);
    expect(preflight.headers.get("access-control-allow-origin")).toBe("*");
  });

  test("8. protected-resource metadata is well formed", async () => {
    for (const path of [
      "/.well-known/oauth-protected-resource/mcp",
      "/.well-known/oauth-protected-resource",
    ]) {
      const response = await get(hosted.url, path);
      expect(response.status).toBe(200);
      expect(await response.json()).toEqual({
        resource: `${hosted.url}/mcp`,
        authorization_servers: [hosted.url],
        scopes_supported: [
          "openid",
          "https://www.googleapis.com/auth/userinfo.email",
          "https://www.googleapis.com/auth/userinfo.profile",
        ],
        bearer_methods_supported: ["header"],
      });
    }
  });
});

describe("web pages", () => {
  test("terms, privacy and static assets", async () => {
    for (const [path, text] of [
      ["/terms", "Terms of Use"],
      ["/privacy", "Privacy Policy"],
    ] as const) {
      const response = await get(hosted.url, path);
      expect(response.status).toBe(200);
      expect(await response.text()).toContain(text);
    }
    for (const [name, type] of [
      ["icon.png", "image/png"],
      ["icon.svg", "image/svg+xml"],
      ["wordmark.png", "image/png"],
    ] as const) {
      const response = await get(hosted.url, `/static/${name}`);
      expect(response.status).toBe(200);
      expect(response.headers.get("content-type")).toBe(type);
    }
    for (const path of [
      "/static/../src/main.ts",
      "/static/%2e%2e/package.json",
      "/static/nope.png",
    ])
      expect((await get(hosted.url, path)).status).toBe(404);
  });

  test("HEAD returns headers without a body", async () => {
    const response = await fetch(`${hosted.url}/`, { method: "HEAD" });
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toStartWith("text/html");
    expect(await response.text()).toBe("");
  });

  test("unknown paths and wrong methods", async () => {
    const missing = await get(hosted.url, "/nope");
    expect(missing.status).toBe(404);
    expect(await missing.json()).toEqual({ error: "Not Found" });
    const wrong = await fetch(`${hosted.url}/-/health`, { method: "POST" });
    expect(wrong.status).toBe(405);
    expect(wrong.headers.get("allow")).toBe("GET");
  });

  test("HSTS only when the public URL is HTTPS", async () => {
    expect(
      (await get(hosted.url, "/")).headers.get("strict-transport-security"),
    ).toBeNull();
    const { withSecurityHeaders } = await import(
      "../packages/hosted/src/index.js"
    );
    const secured = withSecurityHeaders(
      new Response("x"),
      "https://mcp.example.com",
    );
    expect(secured.headers.get("strict-transport-security")).toBe(
      "max-age=31536000; includeSubDomains",
    );
    expect(secured.headers.get("content-security-policy")).toBeNull();
  });
});

describe("terms gate", () => {
  test("/authorize without the cookie goes to /consent, keeping the query", async () => {
    const response = await get(
      hosted.url,
      "/authorize?client_id=abc&state=x%20y",
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe(
      `/consent?next=${encodeURIComponent("/authorize?client_id=abc&state=x%20y")}`,
    );
  });

  test("an old terms version is gated again", async () => {
    const response = await get(hosted.url, "/authorize?client_id=abc", {
      cookie: "pca_terms_accepted=2025-01-01",
    });
    expect(response.headers.get("location")).toStartWith("/consent?next=");
  });

  test("the consent form only echoes same-origin next URLs", async () => {
    for (const next of [
      "https://evil.example/",
      "//evil.example/x",
      "/\\evil.example",
    ]) {
      const response = await get(
        hosted.url,
        `/consent?next=${encodeURIComponent(next)}`,
      );
      const body = await response.text();
      expect(body).toContain('name="next" value="/"');
      expect(body).not.toContain("evil.example");
    }
    const page = await get(
      hosted.url,
      "/consent?next=%2Fauthorize%3Fa%3D1%26b%3D%3Cx%3E",
    );
    const html = await page.text();
    expect(html).toContain('value="/authorize?a=1&amp;b=&lt;x&gt;"');
    expect(html).toContain("<code>2026-04-23</code>");
  });

  test("accepting requires the checkbox and refuses cross-site posts", async () => {
    const post = (body: Record<string, string>, origin?: string) =>
      fetch(`${hosted.url}/consent/accept`, {
        method: "POST",
        redirect: "manual",
        headers: {
          "content-type": "application/x-www-form-urlencoded",
          ...(origin ? { origin } : {}),
        },
        body: new URLSearchParams(body),
      });
    const unchecked = await post({ next: "/authorize?x=1" });
    expect(unchecked.status).toBe(303);
    expect(unchecked.headers.get("location")).toBe(
      `/consent?next=${encodeURIComponent("/authorize?x=1")}`,
    );
    expect(unchecked.headers.getSetCookie()).toEqual([]);
    const offsite = await post({ next: "https://evil.example", agree: "on" });
    expect(offsite.headers.get("location")).toBe("/");
    const cookie = offsite.headers.getSetCookie()[0] ?? "";
    expect(cookie).toContain("pca_terms_accepted=2026-04-23");
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("SameSite=Lax");
    expect(cookie).toContain("Max-Age=31536000");
    const crossSite = await post(
      { next: "/", agree: "on" },
      "https://evil.example",
    );
    expect(crossSite.status).toBe(403);
  });
});

describe("MCP surface", () => {
  test("serverInfo carries icons, website URL and instructions", async () => {
    const { body } = await rpc(bypass.url, "initialize", {
      protocolVersion: "2025-11-25",
      capabilities: {},
      clientInfo: { name: "test", version: "1" },
    });
    const result = body?.result as {
      serverInfo: {
        name: string;
        websiteUrl: string;
        icons: { src: string }[];
      };
      instructions: string;
    };
    expect(result.serverInfo.name).toBe("patent-client-agents");
    expect(result.serverInfo.websiteUrl).toBe(`${bypass.url}/`);
    expect(result.serverInfo.icons.map((icon) => icon.src)).toEqual([
      `${bypass.url}/static/icon.svg`,
      `${bypass.url}/static/icon.png`,
    ]);
    expect(result.instructions).toContain("Patent and IP data connectors");
  });

  test("tools/list is the curated facade minus hidden tools", async () => {
    const full = createServer({ toolset: "curated" });
    const { Client } = await import("@prefecthq/fastmcp-ts/client");
    const client = await Client.connect(full, {
      versionNegotiation: { mode: "legacy" },
    });
    const curated = (await client.listTools()).map((tool) => tool.name).sort();
    await client.close();
    await full.close();
    const { body } = await rpc(bypass.url, "tools/list");
    const served = (
      (body?.result as { tools: { name: string }[] } | undefined)?.tools ?? []
    )
      .map((tool) => tool.name)
      .sort();
    expect(curated).toContain("search_trademarks");
    expect(served).toEqual(
      curated.filter((name) => name !== "search_trademarks"),
    );
  });

  test("hidden tools cannot be called", async () => {
    const { body } = await rpc(bypass.url, "tools/call", {
      name: "search_trademarks",
      arguments: { query: "apple" },
    });
    expect(JSON.stringify(body)).toContain("Unknown tool");
  });

  test("bypass mode serves tools without auth and logs without Firestore", async () => {
    const { status, body } = await rpc(bypass.url, "tools/call", {
      name: "patent_client_status",
      arguments: {},
    });
    expect(status).toBe(200);
    expect(
      (body?.result as { isError?: boolean } | undefined)?.isError,
    ).not.toBe(true);
    expect(bypass.usage.records).toEqual([]);
    const event = bypass.events.find((entry) => entry.event === "tool_call");
    expect(event).toMatchObject({
      tool: "patent_client_status",
      ok: true,
      actor_id: null,
    });
  });

  test("bypass mode serves no OAuth endpoints and refuses foreign hosts", async () => {
    expect(
      (await get(bypass.url, "/.well-known/oauth-authorization-server")).status,
    ).toBe(404);
    expect((await get(bypass.url, "/authorize")).status).toBe(404);
    const rebound = await bypass.app.fetch(
      new Request(`${bypass.url}/-/health`, {
        headers: { host: "attacker.example" },
      }),
    );
    expect(rebound.status).toBe(403);
  });

  test("routes registered by packages/mcp (downloads) are served", async () => {
    const response = await get(
      bypass.url,
      "/downloads?id=missing&expires=1&signature=x",
    );
    expect(response.status).not.toBe(404);
    expect([400, 401, 403, 410]).toContain(response.status);
  });
});

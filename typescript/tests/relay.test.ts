import { afterAll, beforeAll, expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import {
  createRelayFetch,
  EpoFeesClient,
  EpoOpsClient,
  RELAY_CREDENTIAL,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { createServer } from "../packages/mcp/src/index.js";

const credentials = {
  usptoOdpApiKey: "server-odp-key",
  epoOpsKey: "server-key",
  epoOpsSecret: "server-secret",
};
const seen: { host: string; path: string; headers: Record<string, string> }[] =
  [];
let upstream: ReturnType<typeof Bun.serve>;
let identity: ReturnType<typeof Bun.serve>;
let server: FastMCP;
let relayUrl: string;
let token: (scope: string) => string;

beforeAll(async () => {
  upstream = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      const url = new URL(request.url);
      const host = request.headers.get("x-test-host") ?? "";
      const [hostName, ...rest] = url.pathname.slice(1).split("/");
      const path = `/${rest.join("/")}`;
      seen.push({
        host: hostName ?? host,
        path: path + url.search,
        headers: Object.fromEntries(request.headers),
      });
      if (hostName === "ops.epo.org" && path === "/3.2/auth/accesstoken")
        return request.headers.get("authorization") ===
          `Basic ${btoa("server-key:server-secret")}`
          ? Response.json({ access_token: "server-token", expires_in: 1200 })
          : new Response("bad", { status: 401 });
      if (hostName === "ops.epo.org")
        return request.headers.get("authorization") === "Bearer server-token"
          ? new Response(
              '<ops:world-patent-data xmlns:ops="http://ops.epo.org"><ops:biblio-search total-result-count="7"/></ops:world-patent-data>',
              {
                headers: {
                  "set-cookie": "tracking=1",
                  "x-epo-client-ip": "203.0.113.9",
                  "access-control-allow-origin": "*",
                },
              },
            )
          : new Response("", { status: 401 });
      if (hostName === "fees.apps.epo.org")
        return Response.json([
          {
            data: {
              feeCode: "001",
              feeDescription: "Filing",
              amount: "135,00",
            },
            children: [],
          },
        ]);
      if (hostName === "api.uspto.gov" && path === "/redirect-ok")
        return new Response(null, {
          status: 302,
          headers: { location: "https://data.uspto.gov/file.zip" },
        });
      if (hostName === "api.uspto.gov" && path === "/redirect-evil")
        return new Response(null, {
          status: 302,
          headers: { location: "https://evil.example/steal" },
        });
      return new Response("ok", { headers: { "content-type": "text/plain" } });
    },
  });
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
  });
  const jwk = {
    ...publicKey.export({ format: "jwk" }),
    kid: "k",
    alg: "RS256",
    use: "sig",
  };
  identity = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch: () => Response.json({ keys: [jwk] }),
  });
  const issuer = "https://identity.test";
  const audience = "patent-client-agents";
  token = (scope: string) => {
    const encode = (value: object) =>
      Buffer.from(JSON.stringify(value)).toString("base64url");
    const unsigned = `${encode({ alg: "RS256", kid: "k", typ: "JWT" })}.${encode({ iss: issuer, aud: audience, sub: "u", exp: Math.floor(Date.now() / 1000) + 300, scope })}`;
    return `${unsigned}.${sign("RSA-SHA256", Buffer.from(unsigned), privateKey).toString("base64url")}`;
  };
  // Every allowed host maps to the fake upstream, distinguished by a path prefix.
  const base = `http://127.0.0.1:${upstream.port}`;
  server = createServer({
    auth: {
      jwksUri: `http://127.0.0.1:${identity.port}/jwks`,
      issuer,
      audience,
    },
    relay: {
      origins: ["http://app.test"],
      credentials,
      maxRequestBytes: 1024,
      upstreams: Object.fromEntries(
        [
          "api.uspto.gov",
          "data.uspto.gov",
          "ops.epo.org",
          "fees.apps.epo.org",
        ].map((host) => [host, `${base}/${host}/`]),
      ),
    },
  });
  await server.run({
    transport: "http",
    host: "127.0.0.1",
    port: 0,
    stateless: true,
  });
  relayUrl = `http://127.0.0.1:${server.address?.port}/relay`;
});
afterAll(async () => {
  await server.close();
  upstream.stop(true);
  identity.stop(true);
});

const relay = (target: string, init: RequestInit = {}, scope = "relay:use") =>
  fetch(`${relayUrl}?url=${encodeURIComponent(target)}`, {
    ...init,
    headers: { authorization: `Bearer ${token(scope)}`, ...init.headers },
  });

test("the relay requires a token with relay:use", async () => {
  const anonymous = await fetch(
    `${relayUrl}?url=${encodeURIComponent("https://api.uspto.gov/x")}`,
  );
  expect(anonymous.status).toBe(401);
  const browserAnonymous = await fetch(
    `${relayUrl}?url=${encodeURIComponent("https://api.uspto.gov/x")}`,
    { headers: { origin: "http://app.test" } },
  );
  // Browser apps can read the refusal.
  expect(browserAnonymous.status).toBe(401);
  expect(browserAnonymous.headers.get("access-control-allow-origin")).toBe(
    "http://app.test",
  );
  expect((await relay("https://api.uspto.gov/x", {}, "odp:read")).status).toBe(
    403,
  );
  expect(() =>
    createServer({ relay: { origins: ["http://app.test"] } }),
  ).toThrow("requires server auth");
});

test("only allowed plain HTTPS upstreams are relayed", async () => {
  expect((await relay("https://evil.example/x")).status).toBe(403);
  expect((await relay("http://api.uspto.gov/x")).status).toBe(400);
  expect((await relay("https://user:pw@api.uspto.gov/x")).status).toBe(400);
  expect((await relay("https://api.uspto.gov:8443/x")).status).toBe(400);
  expect((await relay("https://ppubs.uspto.gov/x")).status).toBe(403);
});

test("server keys replace browser placeholders and browser cookies never reach upstream", async () => {
  seen.length = 0;
  const response = await relay("https://api.uspto.gov/api/v1/x?q=1", {
    headers: {
      "x-api-key": RELAY_CREDENTIAL,
      cookie: "session=browser",
      origin: "http://app.test",
    },
  });
  expect(response.status).toBe(200);
  expect(seen[0]?.path).toBe("/api/v1/x?q=1");
  expect(seen[0]?.headers["x-api-key"]).toBe("server-odp-key");
  expect(seen[0]?.headers.cookie).toBeUndefined();
  expect(seen[0]?.headers.origin).toBeUndefined();
  expect(seen[0]?.headers.authorization).toBeUndefined();
});

test("CORS is granted to configured origins only, with relay headers allowed", async () => {
  const preflight = await fetch(relayUrl, {
    method: "OPTIONS",
    headers: {
      origin: "http://app.test",
      "access-control-request-method": "GET",
      "access-control-request-headers":
        "authorization, x-upstream-authorization",
    },
  });
  expect(preflight.headers.get("access-control-allow-origin")).toBe(
    "http://app.test",
  );
  expect(
    preflight.headers.get("access-control-allow-headers")?.toLowerCase(),
  ).toContain("x-upstream-authorization");
  const allowed = await relay("https://fees.apps.epo.org/prod/bff/api/fees", {
    headers: { origin: "http://app.test" },
  });
  expect(allowed.headers.get("access-control-allow-origin")).toBe(
    "http://app.test",
  );
  const other = await relay("https://fees.apps.epo.org/prod/bff/api/fees", {
    headers: { origin: "http://other.test" },
  });
  expect(other.headers.get("access-control-allow-origin")).toBeNull();
});

test("clients work end to end through createRelayFetch", async () => {
  seen.length = 0;
  const relayFetch = createRelayFetch({
    url: relayUrl,
    token: () => token("relay:use"),
  });
  const ops = new EpoOpsClient({
    apiKey: RELAY_CREDENTIAL,
    apiSecret: RELAY_CREDENTIAL,
    retryLimit: 0,
    fetch: relayFetch,
  });
  const search = await ops.search("ta=x");
  expect(search.data.total_results).toBe(7);
  expect(search.provenance.source_url).toStartWith("https://ops.epo.org/");
  const tokenRequest = seen.find(
    (item) => item.path === "/3.2/auth/accesstoken",
  );
  expect(tokenRequest?.headers.authorization).toBe(
    `Basic ${btoa("server-key:server-secret")}`,
  );
  const fees = new EpoFeesClient({ retryLimit: 0, fetch: relayFetch });
  expect((await fees.getEpcSchedule()).fees[0]?.amount).toBe("135.00");
});

test("relay responses drop cookies, upstream CORS and caller IP headers", async () => {
  const response = await relay("https://ops.epo.org/3.2/rest-services/x", {
    headers: { "x-upstream-authorization": "Bearer server-token" },
  });
  expect(response.status).toBe(200);
  expect(response.headers.get("set-cookie")).toBeNull();
  expect(response.headers.get("x-epo-client-ip")).toBeNull();
  expect(response.headers.get("access-control-allow-origin")).not.toBe("*");
});

test("redirects stay on allowed hosts and drop credentials across hosts", async () => {
  seen.length = 0;
  const ok = await relay("https://api.uspto.gov/redirect-ok");
  expect(ok.status).toBe(200);
  expect(seen.map((item) => item.host)).toEqual([
    "api.uspto.gov",
    "data.uspto.gov",
  ]);
  expect(seen[1]?.headers["x-api-key"]).toBeUndefined();
  expect((await relay("https://api.uspto.gov/redirect-evil")).status).toBe(502);
});

test("request bodies are bounded", async () => {
  const response = await relay("https://fees.apps.epo.org/x", {
    method: "POST",
    body: "x".repeat(2048),
  });
  expect(response.status).toBe(413);
});

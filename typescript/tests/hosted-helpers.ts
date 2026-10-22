import { createHash } from "node:crypto";
import {
  createHostedApp,
  type HostedApp,
  type HostedDependencies,
  loadConfig,
  MemoryOAuthStore,
  MemoryRateLimitStore,
  MemoryUsageSink,
} from "../packages/hosted/src/index.js";

export const GOOGLE_CLIENT_ID = "test-client.apps.googleusercontent.com";

export function hostedEnv(
  overrides: Record<string, string> = {},
): Record<string, string> {
  return {
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET: "test-google-secret",
    SESSION_SECRET: "s".repeat(48),
    ACTOR_HASH_KEY: "actor-hash-test-key",
    STATE_BACKEND: "memory",
    ...overrides,
  };
}

function b64url(value: Buffer | string) {
  return Buffer.from(value).toString("base64url");
}

/** An unsigned ID token; the proxy only checks the claims of tokens from Google's token endpoint. */
export function idToken(claims: Record<string, unknown>) {
  return `${b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }))}.${b64url(JSON.stringify(claims))}.sig`;
}

export interface FakeGoogle {
  url: string;
  endpoints: { authorization: string; token: string };
  /** Behavior knobs. */
  user: { sub: string; email: string; email_verified: boolean };
  refreshResult: "ok" | "invalid_grant" | "unavailable";
  issueRefreshToken: boolean;
  tokenRequests: URLSearchParams[];
  stop(): void;
}

/** Google's authorization and token endpoints, enough for the proxy flow. */
export function startFakeGoogle(now: () => number): FakeGoogle {
  const codes = new Map<string, { challenge: string; redirect: string }>();
  const fake: FakeGoogle = {
    url: "",
    endpoints: { authorization: "", token: "" },
    user: {
      sub: "google-sub-1",
      email: "User@Example.com",
      email_verified: true,
    },
    refreshResult: "ok",
    issueRefreshToken: true,
    tokenRequests: [],
    stop: () => server.stop(true),
  };
  const server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      const url = new URL(request.url);
      if (url.pathname === "/o/oauth2/v2/auth") {
        const params = url.searchParams;
        if (
          params.get("client_id") !== GOOGLE_CLIENT_ID ||
          params.get("code_challenge_method") !== "S256" ||
          params.get("access_type") !== "offline" ||
          params.get("prompt") !== "consent" ||
          params.get("scope") !== "openid email profile"
        )
          return new Response("bad authorize request", { status: 400 });
        const code = `google-code-${codes.size + 1}`;
        codes.set(code, {
          challenge: params.get("code_challenge") ?? "",
          redirect: params.get("redirect_uri") ?? "",
        });
        const target = new URL(params.get("redirect_uri") ?? "");
        target.searchParams.set("code", code);
        target.searchParams.set("state", params.get("state") ?? "");
        return Response.redirect(target.href, 302);
      }
      if (url.pathname === "/token" && request.method === "POST") {
        const form = new URLSearchParams(await request.text());
        fake.tokenRequests.push(form);
        if (
          form.get("client_id") !== GOOGLE_CLIENT_ID ||
          form.get("client_secret") !== "test-google-secret"
        )
          return Response.json({ error: "invalid_client" }, { status: 401 });
        const seconds = Math.floor(now() / 1000);
        const identity = idToken({
          iss: "https://accounts.google.com",
          aud: GOOGLE_CLIENT_ID,
          iat: seconds,
          exp: seconds + 3600,
          ...fake.user,
          name: "Test User",
        });
        if (form.get("grant_type") === "authorization_code") {
          const code = codes.get(form.get("code") ?? "");
          codes.delete(form.get("code") ?? "");
          const verifier = form.get("code_verifier") ?? "";
          if (
            !code ||
            code.redirect !== form.get("redirect_uri") ||
            createHash("sha256").update(verifier).digest("base64url") !==
              code.challenge
          )
            return Response.json({ error: "invalid_grant" }, { status: 400 });
          return Response.json({
            access_token: "google-access-1",
            expires_in: 3599,
            ...(fake.issueRefreshToken
              ? { refresh_token: "google-refresh-1" }
              : {}),
            scope: "openid https://www.googleapis.com/auth/userinfo.email",
            token_type: "Bearer",
            id_token: identity,
          });
        }
        if (form.get("grant_type") === "refresh_token") {
          if (fake.refreshResult === "invalid_grant")
            return Response.json({ error: "invalid_grant" }, { status: 400 });
          if (fake.refreshResult === "unavailable")
            return new Response("down", { status: 503 });
          if (form.get("refresh_token") !== "google-refresh-1")
            return Response.json({ error: "invalid_grant" }, { status: 400 });
          return Response.json({
            access_token: `google-access-${fake.tokenRequests.length}`,
            expires_in: 3599,
            token_type: "Bearer",
            id_token: identity,
          });
        }
      }
      return new Response("not found", { status: 404 });
    },
  });
  fake.url = `http://127.0.0.1:${server.port}`;
  fake.endpoints = {
    authorization: `${fake.url}/o/oauth2/v2/auth`,
    token: `${fake.url}/token`,
  };
  return fake;
}

export interface Running {
  app: HostedApp;
  url: string;
  oauthStore: MemoryOAuthStore;
  rateLimits: MemoryRateLimitStore;
  usage: MemoryUsageSink;
  events: Record<string, unknown>[];
  stop(): Promise<void>;
}

/** Start the hosted app on a real listener; tests talk HTTP to it. */
export async function startHosted(
  env: Record<string, string>,
  deps: HostedDependencies = {},
): Promise<Running> {
  const oauthStore = new MemoryOAuthStore(deps.now);
  const rateLimits = new MemoryRateLimitStore();
  const usage = new MemoryUsageSink();
  const events: Record<string, unknown>[] = [];
  let handler: (request: Request) => Promise<Response> = async () =>
    new Response("starting", { status: 503 });
  const listener = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch: (request) => handler(request),
  });
  const url = `http://127.0.0.1:${listener.port}`;
  const app = await createHostedApp(loadConfig({ PUBLIC_URL: url, ...env }), {
    oauthStore,
    rateLimitStore: rateLimits,
    usageSink: usage,
    write: (line) => events.push(JSON.parse(line)),
    ...deps,
  });
  handler = (request) => app.fetch(request);
  return {
    app,
    url,
    oauthStore,
    rateLimits,
    usage,
    events,
    async stop() {
      await listener.stop(true);
      await app.close();
    },
  };
}

/** Send one JSON-RPC request to /mcp and return the parsed message. */
export async function rpc(
  base: string,
  method: string,
  params: Record<string, unknown> = {},
  token?: string,
): Promise<{
  status: number;
  body: Record<string, unknown> | undefined;
  response: Response;
}> {
  const response = await fetch(`${base}/mcp`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      accept: "application/json, text/event-stream",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  const text = await response.text();
  let body: Record<string, unknown> | undefined;
  if (
    (response.headers.get("content-type") ?? "").includes("text/event-stream")
  ) {
    const data = text
      .split("\n")
      .filter((line) => line.startsWith("data: "))
      .map((line) => line.slice(6))
      .find((line) => line.includes('"jsonrpc"'));
    body = data ? JSON.parse(data) : undefined;
  } else if (text) body = JSON.parse(text);
  return { status: response.status, body, response };
}

export function pkcePair() {
  const verifier = Buffer.from(
    crypto.getRandomValues(new Uint8Array(32)),
  ).toString("base64url");
  return {
    verifier,
    challenge: createHash("sha256").update(verifier).digest("base64url"),
  };
}

/** Collect Set-Cookie name=value pairs into a Cookie header value. */
export function cookieHeader(
  response: Response,
  jar: Map<string, string> = new Map(),
) {
  for (const line of response.headers.getSetCookie()) {
    const [pair] = line.split(";");
    const index = pair?.indexOf("=") ?? -1;
    if (!pair || index < 0) continue;
    const name = pair.slice(0, index);
    const value = pair.slice(index + 1);
    if (/Max-Age=0/i.test(line)) jar.delete(name);
    else jar.set(name, value);
  }
  return jar;
}

export function jarHeader(jar: Map<string, string>) {
  return [...jar].map(([name, value]) => `${name}=${value}`).join("; ");
}

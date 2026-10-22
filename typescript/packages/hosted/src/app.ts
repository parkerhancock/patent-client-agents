import { createServer, type ServerOptions } from "@patent-client-agents/mcp";
import { GcsBlobStore } from "@patent-client-agents/mcp/gcs-blob-store";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import type { HostedConfig } from "./config.js";
import { consentAccept, consentForm, termsGate } from "./consent.js";
import {
  FirestoreClient,
  FirestoreOAuthStore,
  FirestoreRateLimitStore,
  FirestoreUsageSink,
} from "./firestore.js";
import { defaultCredentials } from "./google-auth.js";
import { type FetchLike, json, redirect } from "./http.js";
import { GoogleOAuthProxy, InvalidTokenError } from "./oauth/google-proxy.js";
import { errorPage, htmlPage, ROBOTS_TXT, staticFile } from "./pages.js";
import { RateLimiter, rateLimitMiddleware } from "./rate-limit.js";
import {
  type Clock,
  MemoryOAuthStore,
  MemoryRateLimitStore,
  MemoryUsageSink,
  type OAuthStore,
  type RateLimitStore,
  type UsageSink,
} from "./storage.js";
import { type EventWriter, logEvent, usageMiddleware } from "./usage.js";

export const INSTRUCTIONS =
  "Patent and IP data connectors: USPTO (ODP, PPUBS, Assignments, Office Actions, PTAB, Petitions, Bulk Data), EPO OPS, Google Patents, CPC, and the MPEP.";

export interface HostedDependencies {
  oauthStore?: OAuthStore;
  rateLimitStore?: RateLimitStore;
  usageSink?: UsageSink;
  /** Overrides for the MCP server, such as test clients. */
  serverOptions?: Partial<ServerOptions>;
  googleEndpoints?: { authorization: string; token: string };
  fetch?: FetchLike;
  now?: Clock;
  write?: EventWriter;
  accessTokenTtlSeconds?: number;
  refreshTokenTtlSeconds?: number;
}

export interface HostedApp {
  fetch(request: Request): Promise<Response>;
  server: FastMCP;
  oauth?: GoogleOAuthProxy;
  close(): Promise<void>;
}

/**
 * Document downloads: the current per-process signed-URL store. A durable
 * blob store (GCS) is being added to packages/mcp separately; wire its
 * options here when it lands.
 */
export function downloadOptions(
  config: HostedConfig,
): NonNullable<ServerOptions["downloads"]> {
  return {
    publicBaseUrl: config.downloadBaseUrl,
    mode: "signed",
    ...(config.downloadStore
      ? { blobStore: new GcsBlobStore(config.downloadStore) }
      : {}),
  };
}

async function stateFor(config: HostedConfig, deps: HostedDependencies) {
  if (config.stateBackend === "memory")
    return {
      oauth: deps.oauthStore ?? new MemoryOAuthStore(deps.now),
      rateLimits: deps.rateLimitStore ?? new MemoryRateLimitStore(),
      usage: deps.usageSink ?? new MemoryUsageSink(),
    };
  if (deps.oauthStore && deps.rateLimitStore && deps.usageSink)
    return {
      oauth: deps.oauthStore,
      rateLimits: deps.rateLimitStore,
      usage: deps.usageSink,
    };
  const emulatorHost = config.firestore.emulatorHost;
  const credentials = emulatorHost ? undefined : await defaultCredentials();
  const projectId =
    config.firestore.projectId ?? (await credentials?.projectId());
  if (!projectId)
    throw new Error(
      "Set GCP_PROJECT for Firestore; no project could be detected.",
    );
  const client = new FirestoreClient({
    projectId,
    database: config.firestore.database,
    ...(emulatorHost ? { emulatorHost } : {}),
    ...(credentials ? { credentials } : {}),
  });
  return {
    oauth:
      deps.oauthStore ?? new FirestoreOAuthStore(client, undefined, deps.now),
    rateLimits: deps.rateLimitStore ?? new FirestoreRateLimitStore(client),
    usage: deps.usageSink ?? new FirestoreUsageSink(client),
  };
}

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

const OAUTH_CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers":
    "authorization, content-type, mcp-protocol-version",
  "access-control-max-age": "86400",
};

function methodNotAllowed(allow: string) {
  return json({ error: "Method Not Allowed" }, 405, { allow });
}

/** Defense-in-depth headers on every response, as in the Python wrapper. */
export function withSecurityHeaders(
  response: Response,
  publicUrl: string,
): Response {
  const headers = new Headers(response.headers);
  const set = (name: string, value: string) => {
    if (!headers.has(name)) headers.set(name, value);
  };
  set("x-content-type-options", "nosniff");
  set("x-frame-options", "DENY");
  set("referrer-policy", "strict-origin-when-cross-origin");
  if (publicUrl.startsWith("https://"))
    set("strict-transport-security", "max-age=31536000; includeSubDomains");
  if ((headers.get("content-type") ?? "").startsWith("text/html"))
    // form-action must allow Google: CSP applies it to every redirect of a
    // form submission, and /consent/accept -> /authorize -> Google is one.
    set(
      "content-security-policy",
      "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; base-uri 'self'; frame-ancestors 'none'; form-action 'self' https://accounts.google.com",
    );
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

type RouteMatch =
  | {
      kind: "handler";
      handler: (request: Request) => Response | Promise<Response>;
    }
  | { kind: "method-mismatch"; allow: string };

/**
 * Routes packages/mcp registers on the FastMCP server (such as /downloads).
 * FastMCP serves them only from its own listener, so dispatch them here.
 */
function customRoutes(server: FastMCP) {
  const registry = (
    server as unknown as {
      _customRoutes?: {
        match?: (path: string, method: string) => RouteMatch | null;
      };
    }
  )._customRoutes;
  if (typeof registry?.match !== "function")
    throw new Error("FastMCP no longer exposes its custom route registry.");
  return (path: string, method: string) =>
    registry.match?.(path, method) ?? null;
}

export async function createHostedApp(
  config: HostedConfig,
  deps: HostedDependencies = {},
): Promise<HostedApp> {
  const state = await stateFor(config, deps);
  const base = config.publicUrl;
  const server = createServer({
    toolset: "curated",
    downloads: downloadOptions(config),
    hiddenTools: config.hiddenTools,
    serverInfo: {
      websiteUrl: `${base}/`,
      icons: [
        {
          src: `${base}/static/icon.svg`,
          mimeType: "image/svg+xml",
          sizes: ["any"],
        },
        {
          src: `${base}/static/icon.png`,
          mimeType: "image/png",
          sizes: ["512x512"],
        },
      ],
    },
    instructions: INSTRUCTIONS,
    ...deps.serverOptions,
  });
  // Usage wraps rate limiting so rejected calls still appear in the usage log.
  server.use(
    usageMiddleware({
      sink: state.usage,
      ...(config.actorHashKey ? { actorHashKey: config.actorHashKey } : {}),
      ...(deps.write ? { write: deps.write } : {}),
    }),
  );
  if (config.actorHashKey)
    server.use(
      rateLimitMiddleware({
        limiter: new RateLimiter(state.rateLimits, config.limits, deps.now),
        actorHashKey: config.actorHashKey,
        minChargeBytes: config.limits.minChargeBytes,
        ...(deps.write ? { write: deps.write } : {}),
      }),
    );
  const oauth =
    config.authBypass || !config.google || !config.sessionSecret
      ? undefined
      : new GoogleOAuthProxy({
          issuer: config.issuerUrl,
          baseUrl: base,
          resource: `${base}/mcp`,
          clientId: config.google.clientId,
          clientSecret: config.google.clientSecret,
          sessionSecret: config.sessionSecret,
          store: state.oauth,
          errorPage,
          ...(deps.googleEndpoints ? { endpoints: deps.googleEndpoints } : {}),
          ...(deps.fetch ? { fetch: deps.fetch } : {}),
          ...(deps.now ? { now: deps.now } : {}),
          ...(deps.accessTokenTtlSeconds
            ? { accessTokenTtlSeconds: deps.accessTokenTtlSeconds }
            : {}),
          ...(deps.refreshTokenTtlSeconds
            ? { refreshTokenTtlSeconds: deps.refreshTokenTtlSeconds }
            : {}),
        });
  if (!config.authBypass && !oauth)
    throw new Error("Google OAuth is not configured.");
  const matchRoute = customRoutes(server);

  async function serveMcp(request: Request): Promise<Response> {
    if (request.method === "GET") {
      // Browsers pasting the URL get the landing page; MCP clients asking for
      // a server-sent event stream get 405, as stateless serving offers none.
      const accept = request.headers.get("accept") ?? "";
      if (accept.includes("text/event-stream") || !accept.includes("text/html"))
        return new Response("Method Not Allowed", {
          status: 405,
          headers: {
            allow: "POST, DELETE",
            "content-type": "text/plain; charset=utf-8",
          },
        });
      return redirect("/", 302);
    }
    if (request.method !== "POST" && request.method !== "DELETE")
      return methodNotAllowed("GET, POST, DELETE");
    if (!oauth) return server.fetch(request);
    const token = /^Bearer\s+(\S+)$/i.exec(
      request.headers.get("authorization") ?? "",
    )?.[1];
    const unauthorized = (description: string) =>
      json({ error: "invalid_token", error_description: description }, 401, {
        "www-authenticate": oauth.challenge(description),
      });
    if (!token) return unauthorized("Authentication required.");
    let verified: Awaited<ReturnType<GoogleOAuthProxy["verifyAccessToken"]>>;
    try {
      verified = await oauth.verifyAccessToken(token);
    } catch (error) {
      if (error instanceof InvalidTokenError)
        return unauthorized(
          `${error.message} Clear this connector's tokens and reconnect.`,
        );
      logEvent(
        "auth_failed",
        { reason: "token store unavailable" },
        deps.write,
        "ERROR",
      );
      return json({ error: "temporarily_unavailable" }, 503, {
        "retry-after": "5",
      });
    }
    return server.fetch(request, {
      authInfo: {
        token: verified.token,
        clientId: verified.clientId,
        scopes: verified.scopes,
        expiresAt: verified.expiresAt,
        extra: verified.extra,
      },
    });
  }

  async function serveOAuth(request: Request, path: string) {
    if (!oauth) return undefined;
    const method = request.method;
    const oauthPaths = [
      "/.well-known/oauth-authorization-server",
      "/.well-known/oauth-authorization-server/mcp",
      "/.well-known/oauth-protected-resource",
      "/.well-known/oauth-protected-resource/mcp",
      "/register",
      "/token",
      "/revoke",
    ];
    if (method === "OPTIONS" && oauthPaths.includes(path))
      return new Response(null, { status: 204, headers: OAUTH_CORS });
    const cors = (response: Response) => {
      for (const [name, value] of Object.entries(OAUTH_CORS))
        response.headers.set(name, value);
      return response;
    };
    switch (path) {
      case "/.well-known/oauth-authorization-server":
      case "/.well-known/oauth-authorization-server/mcp":
        return method === "GET" || method === "HEAD"
          ? cors(json(oauth.authorizationServerMetadata()))
          : methodNotAllowed("GET");
      case "/.well-known/oauth-protected-resource":
      case "/.well-known/oauth-protected-resource/mcp":
        return method === "GET" || method === "HEAD"
          ? cors(json(oauth.protectedResourceMetadata()))
          : methodNotAllowed("GET");
      case "/register":
        return method === "POST"
          ? cors(await oauth.register(request))
          : methodNotAllowed("POST");
      case "/token":
        return method === "POST"
          ? cors(await oauth.token(request))
          : methodNotAllowed("POST");
      case "/revoke":
        return method === "POST"
          ? cors(await oauth.revoke(request))
          : methodNotAllowed("POST");
      case "/authorize":
        if (method !== "GET" && method !== "HEAD")
          return methodNotAllowed("GET");
        return (
          termsGate(request, config.termsVersion) ?? oauth.authorize(request)
        );
      case "/auth/callback":
        return method === "GET"
          ? oauth.callback(request)
          : methodNotAllowed("GET");
      default:
        return undefined;
    }
  }

  async function route(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;
    const read = method === "GET" || method === "HEAD";
    if (config.authBypass) {
      // Unauthenticated local runs: refuse DNS-rebound requests from web pages.
      const host = (request.headers.get("host") ?? "").replace(/:\d+$/, "");
      if (!LOCAL_HOSTS.has(host) && host !== new URL(base).hostname)
        return json({ error: "Forbidden host" }, 403);
    }
    switch (path) {
      case "/":
        return read
          ? htmlPage("home.html", { public_url: base })
          : methodNotAllowed("GET");
      case "/terms":
        return read ? htmlPage("terms.html") : methodNotAllowed("GET");
      case "/privacy":
        return read ? htmlPage("privacy.html") : methodNotAllowed("GET");
      case "/consent":
        return read
          ? consentForm(request, config.termsVersion)
          : methodNotAllowed("GET");
      case "/consent/accept":
        return method === "POST"
          ? consentAccept(request, {
              termsVersion: config.termsVersion,
              publicUrl: base,
            })
          : methodNotAllowed("POST");
      case "/favicon.ico":
        // Bytes, not a redirect: some favicon fetchers do not follow redirects.
        return read
          ? (staticFile("icon.png") as Response)
          : methodNotAllowed("GET");
      case "/robots.txt":
        return read
          ? new Response(ROBOTS_TXT, {
              headers: { "content-type": "text/plain; charset=utf-8" },
            })
          : methodNotAllowed("GET");
      case "/-/health":
        return read ? json({ status: "ok" }) : methodNotAllowed("GET");
      case "/mcp":
        return serveMcp(request);
    }
    if (path.startsWith("/static/")) {
      if (!read) return methodNotAllowed("GET");
      return (
        staticFile(path.slice("/static/".length)) ??
        json({ error: "Not Found" }, 404)
      );
    }
    const oauthResponse = await serveOAuth(request, path);
    if (oauthResponse) return oauthResponse;
    const match = matchRoute(path, method);
    if (match?.kind === "handler") return match.handler(request);
    if (match?.kind === "method-mismatch") return methodNotAllowed(match.allow);
    return json({ error: "Not Found" }, 404);
  }

  return {
    server,
    ...(oauth ? { oauth } : {}),
    async fetch(request: Request) {
      let response: Response;
      try {
        response = await route(request);
      } catch {
        logEvent(
          "request_failed",
          { path: new URL(request.url).pathname, method: request.method },
          deps.write,
          "ERROR",
        );
        response = json({ error: "Internal Server Error" }, 500);
      }
      if (request.method === "HEAD")
        response = new Response(null, {
          status: response.status,
          headers: response.headers,
        });
      return withSecurityHeaders(response, base);
    },
    async close() {
      await server.close();
    },
  };
}

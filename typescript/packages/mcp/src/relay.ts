import { ConfigurationError } from "@patent-client-agents/client";

/**
 * Upstreams a browser may reach through the relay. Patent Public Search and
 * Trademark Search are excluded: their clients need Cookie and User-Agent
 * headers that browsers never let page code set, so they run server-side.
 */
export const RELAY_HOSTS = [
  "api.uspto.gov",
  "data.uspto.gov",
  "data-documents.uspto.gov",
  "tsdrapi.uspto.gov",
  "assignmentcenter.uspto.gov",
  "ops.epo.org",
  "fees.apps.epo.org",
  "patents.google.com",
  "patentimages.storage.googleapis.com",
  "www.cafc.uscourts.gov",
  "api.publicrecords.copyright.gov",
  "www.wipo.int",
] as const;
/** Request headers forwarded upstream; everything else, including cookies and Origin, is dropped. */
const FORWARD = ["accept", "accept-language", "content-type", "x-ops-range"];
/** Response headers dropped before the browser sees them. */
const STRIP = new Set([
  "set-cookie",
  "set-cookie2",
  "access-control-allow-origin",
  "access-control-allow-credentials",
  "access-control-allow-headers",
  "access-control-allow-methods",
  "access-control-expose-headers",
  "content-encoding",
  "content-length",
  "transfer-encoding",
  "connection",
  "x-epo-client-ip",
  "x-epo-forwarded",
]);
export const RELAY_REQUEST_HEADERS = [
  "x-upstream-authorization",
  "x-api-key",
  "uspto-api-key",
  "x-ops-range",
];
export const RELAY_EXPOSED_HEADERS = [
  "retry-after",
  "x-rejection-reason",
  "x-throttling-control",
  "x-individualquotaperhour-used",
  "x-registeredquotaperweek-used",
];

export interface RelayCredentials {
  usptoOdpApiKey?: string;
  usptoTsdrApiKey?: string;
  epoOpsKey?: string;
  epoOpsSecret?: string;
}
export interface RelayOptions {
  /** Browser origins allowed to call the relay, e.g. https://app.example.com. */
  origins: string[];
  /** Office credentials injected server-side; defaults to the usual environment variables. */
  credentials?: RelayCredentials;
  /** Largest request body forwarded. Defaults to 1 MiB. */
  maxRequestBytes?: number;
  /** Per-request upstream budget, including redirects. Defaults to 60 seconds. */
  timeoutMs?: number;
  /** Test hook: map an allowed host to a different origin. */
  upstreams?: Record<string, string>;
  fetch?: typeof fetch;
}

export function relayCredentialsFromEnv(
  env: Record<string, string | undefined>,
): RelayCredentials {
  const pick = (...names: string[]) =>
    names.map((name) => env[name]?.trim()).find(Boolean);
  const credentials: RelayCredentials = {};
  const odp = pick("USPTO_ODP_API_KEY");
  const tsdr = pick("USPTO_TSDR_API_KEY");
  const key = pick("EPO_OPS_API_KEY", "EPO_API_KEY");
  const secret = pick("EPO_OPS_API_SECRET", "EPO_API_SECRET");
  if (odp) credentials.usptoOdpApiKey = odp;
  if (tsdr) credentials.usptoTsdrApiKey = tsdr;
  if (key) credentials.epoOpsKey = key;
  if (secret) credentials.epoOpsSecret = secret;
  return credentials;
}

const refuse = (status: number, message: string) =>
  new Response(message, {
    status,
    headers: { "content-type": "text/plain", "cache-control": "no-store" },
  });

/** Parse `?url=` and require an allowed HTTPS upstream without credentials or fragments. */
function target(request: Request): URL | Response {
  const raw = new URL(request.url).searchParams.get("url");
  if (!raw) return refuse(400, "Missing url parameter.");
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return refuse(400, "Invalid url parameter.");
  }
  if (
    url.protocol !== "https:" ||
    url.port ||
    url.username ||
    url.password ||
    url.hash
  )
    return refuse(400, "Relay targets must be plain HTTPS URLs.");
  if (!(RELAY_HOSTS as readonly string[]).includes(url.hostname))
    return refuse(403, "Upstream host is not allowed.");
  return url;
}

/**
 * Credentials for one upstream request. The server's office keys replace
 * whatever the browser sent; browser-held upstream tokens (an OPS bearer
 * token minted through the relay) travel as X-Upstream-Authorization.
 */
function upstreamHeaders(
  request: Request,
  url: URL,
  credentials: RelayCredentials,
): Headers | Response {
  const headers = new Headers();
  for (const name of FORWARD) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  const passed = request.headers.get("x-upstream-authorization");
  switch (url.hostname) {
    case "api.uspto.gov":
      if (!credentials.usptoOdpApiKey)
        return refuse(503, "The relay has no USPTO ODP key.");
      headers.set("x-api-key", credentials.usptoOdpApiKey);
      break;
    case "tsdrapi.uspto.gov":
      if (!credentials.usptoTsdrApiKey)
        return refuse(503, "The relay has no TSDR key.");
      headers.set("uspto-api-key", credentials.usptoTsdrApiKey);
      break;
    case "ops.epo.org":
      if (url.pathname === "/3.2/auth/accesstoken") {
        if (!credentials.epoOpsKey || !credentials.epoOpsSecret)
          return refuse(503, "The relay has no EPO OPS credentials.");
        headers.set(
          "authorization",
          `Basic ${btoa(`${credentials.epoOpsKey}:${credentials.epoOpsSecret}`)}`,
        );
      } else if (passed && /^Bearer [\w.~+/=-]+$/.test(passed))
        headers.set("authorization", passed);
      break;
  }
  return headers;
}

async function boundedBody(request: Request, maxBytes: number) {
  if (request.method === "GET") return undefined;
  const reader = request.body?.getReader();
  if (!reader) return undefined;
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBytes) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

/** Handle one authenticated relay request. Authentication happens before this is called. */
/**
 * Build the relay. `authorize` runs first and returns a refusal, or null to
 * proceed; every response, refusals included, gets CORS headers for allowed
 * origins so browser apps can read auth failures.
 */
export function createRelayHandler(
  options: RelayOptions,
  authorize: (request: Request) => Promise<Response | null> = async () => null,
) {
  if (!options.origins.length)
    throw new ConfigurationError(
      "The relay needs at least one allowed origin.",
    );
  for (const origin of options.origins) {
    const url = new URL(origin);
    if (url.origin !== origin || origin === "null")
      throw new ConfigurationError(
        `Relay origins must be bare origins: ${origin}`,
      );
  }
  const credentials = options.credentials ?? {};
  const maxRequestBytes = options.maxRequestBytes ?? 1024 * 1024;
  const timeoutMs = options.timeoutMs ?? 60_000;
  const send =
    options.fetch ?? ((input, init) => globalThis.fetch(input, init));
  const physical = (url: URL) => {
    const override = options.upstreams?.[url.hostname];
    return override
      ? new URL(url.pathname.slice(1) + url.search, override)
      : url;
  };
  const allowed = new Set(options.origins);
  /** FastMCP answers preflight; actual relay responses need their own CORS headers. */
  const withCors = (request: Request, response: Response) => {
    const origin = request.headers.get("origin");
    const headers = new Headers(response.headers);
    headers.append("vary", "Origin");
    if (origin && allowed.has(origin)) {
      headers.set("access-control-allow-origin", origin);
      headers.set(
        "access-control-expose-headers",
        RELAY_EXPOSED_HEADERS.join(", "),
      );
    }
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  };
  return async (request: Request): Promise<Response> =>
    withCors(request, (await authorize(request)) ?? (await forward(request)));
  async function forward(request: Request): Promise<Response> {
    if (request.method !== "GET" && request.method !== "POST")
      return refuse(405, "Only GET and POST are relayed.");
    let url = target(request);
    if (url instanceof Response) return url;
    let headers = upstreamHeaders(request, url, credentials);
    if (headers instanceof Response) return headers;
    const body = await boundedBody(request, maxRequestBytes);
    if (body === null) return refuse(413, "Request body is too large.");
    const signal = AbortSignal.timeout(timeoutMs);
    try {
      for (let redirects = 0; ; redirects++) {
        const response = await send(physical(url), {
          method: request.method,
          headers,
          ...(body ? { body } : {}),
          redirect: "manual",
          signal,
        });
        const location = response.headers.get("location");
        if (response.status >= 300 && response.status < 400 && location) {
          await response.body?.cancel();
          if (request.method !== "GET" || redirects === 5)
            return refuse(502, "Upstream redirect rejected.");
          const next = new URL(location, url);
          const checked = target(
            new Request(
              `https://relay.invalid/?url=${encodeURIComponent(next.href)}`,
            ),
          );
          if (checked instanceof Response)
            return refuse(
              502,
              "Upstream redirected to a host that is not allowed.",
            );
          // Credentials never follow a redirect to another host.
          if (checked.hostname !== url.hostname) {
            const plain = new Headers();
            for (const name of FORWARD) {
              const value = headers.get(name);
              if (value !== null) plain.set(name, value);
            }
            headers = plain;
          }
          url = checked;
          continue;
        }
        const out = new Headers();
        response.headers.forEach((value, name) => {
          if (!STRIP.has(name.toLowerCase())) out.set(name, value);
        });
        out.set("cache-control", "no-store");
        return new Response(response.body, {
          status: response.status,
          headers: out,
        });
      }
    } catch {
      return refuse(signal.aborted ? 504 : 502, "Upstream request failed.");
    }
  }
}

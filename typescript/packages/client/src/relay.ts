/**
 * Browser access to office APIs that send no CORS headers or need
 * server-held keys. Pass the result as a client's `fetch` option and
 * `RELAY_CREDENTIAL` wherever the client requires a key; the relay replaces
 * it with the server's credential.
 *
 *   const fetch = createRelayFetch({ url: "https://mcp.example.com/relay", token });
 *   const ops = new EpoOpsClient({ apiKey: RELAY_CREDENTIAL, apiSecret: RELAY_CREDENTIAL, fetch });
 *
 * Patent Public Search and Trademark Search cannot run in a browser even
 * through the relay; use them through the MCP server.
 */
export const RELAY_CREDENTIAL = "relay";

export interface RelayFetchOptions {
  /** The relay endpoint, e.g. https://mcp.example.com/relay. */
  url: string | URL;
  /** Bearer token with the relay:use scope, or a function returning a fresh one. */
  token: string | (() => string | Promise<string>);
  fetch?: typeof fetch;
}

export function createRelayFetch(options: RelayFetchOptions): typeof fetch {
  const relay = new URL(options.url);
  const send =
    options.fetch ?? ((input, init) => globalThis.fetch(input, init));
  const relayFetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const target = new URL(relay);
    target.searchParams.set("url", request.url);
    const headers = new Headers(request.headers);
    // Upstream bearer tokens (EPO OPS) travel separately from relay auth.
    const upstream = headers.get("authorization");
    headers.delete("authorization");
    if (upstream?.startsWith("Bearer "))
      headers.set("x-upstream-authorization", upstream);
    const token =
      typeof options.token === "string" ? options.token : await options.token();
    headers.set("authorization", `Bearer ${token}`);
    return send(target, {
      method: request.method,
      headers,
      ...(request.method === "GET" || request.method === "HEAD"
        ? {}
        : { body: await request.arrayBuffer() }),
      signal: request.signal,
      redirect: "follow",
    });
  };
  return relayFetch as typeof fetch;
}

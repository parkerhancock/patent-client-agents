// Signs in to a hosted MCP server the way a desktop client does: dynamic
// client registration, PKCE, and a loopback callback on 127.0.0.1. The
// tokens stay in this process; nothing here prints or writes them. The
// returned auth refreshes the access token a minute before it expires.
import { createHash, randomBytes } from "node:crypto";
import type { AsyncHeaderAuth } from "@prefecthq/fastmcp-ts/client";

const PORT = 53682;
const SCOPES =
  "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile";

interface Tokens {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
}

/**
 * `onUrl` receives the authorization URL for the person to open (also served
 * as a redirect from http://127.0.0.1:53682/start); the promise
 * settles when the browser comes back to the loopback callback.
 */
export async function signIn(
  base: string,
  onUrl: (url: string) => void | Promise<void>,
  timeoutMs = 30 * 60_000,
): Promise<AsyncHeaderAuth> {
  const redirect = `http://127.0.0.1:${PORT}/callback`;
  const resource = `${base}/mcp`;
  const b64 = (b: Buffer) => b.toString("base64url");
  const verifier = b64(randomBytes(32));
  const challenge = b64(createHash("sha256").update(verifier).digest());
  const state = b64(randomBytes(16));
  const reg = await fetch(`${base}/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      client_name: "pca-facade-compare",
      redirect_uris: [redirect],
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code"],
      token_endpoint_auth_method: "none",
      scope: SCOPES,
    }),
  });
  if (!reg.ok) throw new Error(`${base}: registration ${reg.status}`);
  const { client_id } = (await reg.json()) as { client_id: string };
  const auth = new URL(`${base}/authorize`);
  for (const [k, v] of Object.entries({
    response_type: "code",
    client_id,
    redirect_uri: redirect,
    code_challenge: challenge,
    code_challenge_method: "S256",
    state,
    scope: SCOPES,
    resource,
  }))
    auth.searchParams.set(k, v);

  const code = await new Promise<string>((resolve, reject) => {
    const server = Bun.serve({
      hostname: "127.0.0.1",
      port: PORT,
      fetch(req) {
        const u = new URL(req.url);
        if (u.pathname === "/start") return Response.redirect(auth.toString());
        if (u.pathname !== "/callback")
          return new Response("not found", { status: 404 });
        if (u.searchParams.get("state") !== state)
          return new Response("state mismatch", { status: 400 });
        clearTimeout(timer);
        setTimeout(() => server.stop(), 100);
        const c = u.searchParams.get("code");
        if (!c) {
          reject(
            new Error(`authorization error: ${u.searchParams.get("error")}`),
          );
          return new Response("Sign-in failed; you can close this tab.");
        }
        resolve(c);
        return new Response(`Signed in to ${base}. You can close this tab.`);
      },
    });
    const timer = setTimeout(() => {
      server.stop();
      reject(new Error(`${base}: timed out waiting for sign-in`));
    }, timeoutMs);
    Promise.resolve(onUrl(auth.toString())).catch(reject);
  });

  const token = async (params: Record<string, string>) => {
    const r = await fetch(`${base}/token`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ ...params, client_id, resource }),
    });
    const t = (await r.json()) as Tokens;
    if (!r.ok || !t.access_token) throw new Error(`${base}: token ${r.status}`);
    return t;
  };
  let current = await token({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirect,
    code_verifier: verifier,
  });
  let expiresAt = Date.now() + (current.expires_in ?? 3600) * 1000;
  return {
    kind: "loopback_oauth",
    async getHeaders() {
      if (Date.now() > expiresAt - 60_000 && current.refresh_token) {
        const next = await token({
          grant_type: "refresh_token",
          refresh_token: current.refresh_token,
        });
        current = {
          ...next,
          refresh_token: next.refresh_token ?? current.refresh_token,
        };
        expiresAt = Date.now() + (current.expires_in ?? 3600) * 1000;
      }
      return { authorization: `Bearer ${current.access_token}` };
    },
  };
}

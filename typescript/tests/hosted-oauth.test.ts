import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
} from "bun:test";
import {
  FirestoreClient,
  FirestoreOAuthStore,
} from "../packages/hosted/src/index.js";
import {
  cookieHeader,
  type FakeGoogle,
  hostedEnv,
  jarHeader,
  pkcePair,
  type Running,
  rpc,
  startFakeGoogle,
  startHosted,
} from "./hosted-helpers.js";

/**
 * The OAuth flow end to end over real listeners: dynamic registration, the
 * terms gate, Google sign-in (a fake Google), the callback, the token
 * endpoint, an MCP call, refresh, expiry and revocation. With
 * FIRESTORE_EMULATOR_HOST set, OAuth state lives in the Firestore emulator.
 */
const emulator = process.env.FIRESTORE_EMULATOR_HOST;
let clock = Date.UTC(2026, 9, 22, 12);
const now = () => clock;
let google: FakeGoogle;
let hosted: Running;
const REDIRECT = "http://127.0.0.1:33418/callback";

beforeAll(async () => {
  google = startFakeGoogle(now);
  hosted = await startHosted(hostedEnv(), {
    googleEndpoints: google.endpoints,
    now,
    ...(emulator
      ? {
          oauthStore: new FirestoreOAuthStore(
            new FirestoreClient({
              projectId: `pca-oauth-test-${Date.now()}`,
              emulatorHost: emulator,
            }),
            undefined,
            now,
          ),
        }
      : {}),
  });
});
afterAll(async () => {
  await hosted.stop();
  google.stop();
});
beforeEach(() => {
  google.refreshResult = "ok";
  google.issueRefreshToken = true;
  google.user = {
    sub: "google-sub-1",
    email: "User@Example.com",
    email_verified: true,
  };
});

const get = (path: string, headers: Record<string, string> = {}) =>
  fetch(`${hosted.url}${path}`, { redirect: "manual", headers });

async function register(redirectUris = [REDIRECT]) {
  const response = await fetch(`${hosted.url}/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      client_name: "Test MCP client",
      redirect_uris: redirectUris,
      grant_types: ["authorization_code", "refresh_token"],
      token_endpoint_auth_method: "client_secret_post",
    }),
  });
  return { response, body: (await response.json()) as Record<string, unknown> };
}

function authorizeQuery(
  clientId: string,
  challenge: string,
  extra: Record<string, string> = {},
) {
  return new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: REDIRECT,
    code_challenge: challenge,
    code_challenge_method: "S256",
    state: "client-state-123",
    scope: "openid https://www.googleapis.com/auth/userinfo.email",
    resource: `${hosted.url}/mcp`,
    ...extra,
  }).toString();
}

/** Run the browser leg; returns the client redirect (code or error) and the jar. */
async function browserFlow(
  clientId: string,
  challenge: string,
  options: { dropBinding?: boolean } = {},
) {
  const jar = new Map<string, string>();
  const query = authorizeQuery(clientId, challenge);
  // 1. No terms cookie: diverted to /consent with the original request in next.
  const gated = await get(`/authorize?${query}`);
  expect(gated.status).toBe(302);
  const consentUrl = gated.headers.get("location") ?? "";
  expect(consentUrl.startsWith("/consent?next=")).toBe(true);
  const next = new URL(consentUrl, hosted.url).searchParams.get("next") ?? "";
  expect(next).toBe(`/authorize?${query}`);
  // 2. The consent page renders the form with the next URL.
  const form = await get(consentUrl);
  expect(form.status).toBe(200);
  expect(await form.text()).toContain("Before you connect");
  // 3. Accepting sets the cookie and replays /authorize.
  const accepted = await fetch(`${hosted.url}/consent/accept`, {
    method: "POST",
    redirect: "manual",
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      origin: hosted.url,
    },
    body: new URLSearchParams({ next, agree: "on" }),
  });
  expect(accepted.status).toBe(303);
  expect(accepted.headers.get("location")).toBe(next);
  cookieHeader(accepted, jar);
  expect(jar.get("pca_terms_accepted")).toBe("2026-04-23");
  // 4. With the cookie, /authorize redirects to Google and binds the browser.
  const authorize = await get(next, { cookie: jarHeader(jar) });
  expect(authorize.status).toBe(302);
  const googleUrl = new URL(authorize.headers.get("location") ?? "");
  expect(googleUrl.origin).toBe(google.url);
  expect(googleUrl.searchParams.get("redirect_uri")).toBe(
    `${hosted.url}/auth/callback`,
  );
  cookieHeader(authorize, jar);
  // 5. Google signs the user in and redirects to the callback.
  const signedIn = await fetch(googleUrl, { redirect: "manual" });
  expect(signedIn.status).toBe(302);
  const callback = new URL(signedIn.headers.get("location") ?? "");
  if (options.dropBinding)
    for (const name of [...jar.keys()])
      if (name.startsWith("pca_oauth_")) jar.delete(name);
  const returned = await get(`${callback.pathname}${callback.search}`, {
    cookie: jarHeader(jar),
  });
  return { returned, jar };
}

async function tokenRequest(params: Record<string, string>) {
  const response = await fetch(`${hosted.url}/token`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(params),
  });
  return { response, body: (await response.json()) as Record<string, string> };
}

async function signIn() {
  const { body: client } = await register();
  const clientId = String(client.client_id);
  const { verifier, challenge } = pkcePair();
  const { returned } = await browserFlow(clientId, challenge);
  expect(returned.status).toBe(302);
  const location = new URL(returned.headers.get("location") ?? "");
  expect(`${location.origin}${location.pathname}`).toBe(REDIRECT);
  expect(location.searchParams.get("state")).toBe("client-state-123");
  const code = location.searchParams.get("code") ?? "";
  const { response, body } = await tokenRequest({
    grant_type: "authorization_code",
    client_id: clientId,
    code,
    code_verifier: verifier,
    redirect_uri: REDIRECT,
  });
  expect(response.status).toBe(200);
  expect(response.headers.get("cache-control")).toBe("no-store");
  return { clientId, code, verifier, tokens: body };
}

describe("hosted Google OAuth proxy", () => {
  test("DCR, consent, Google sign-in, token, MCP call, refresh, expiry and revocation", async () => {
    const { clientId, tokens } = await signIn();
    expect(tokens.token_type).toBe("Bearer");
    expect(tokens.refresh_token).toBeString();
    expect(Number(tokens.expires_in)).toBe(3599);
    expect(tokens.scope).toBe(
      "openid https://www.googleapis.com/auth/userinfo.email",
    );
    // Tokens are ours, never Google's.
    expect(JSON.stringify(tokens)).not.toContain("google-access");
    expect(JSON.stringify(tokens)).not.toContain("google-refresh");

    const listed = await rpc(hosted.url, "tools/list", {}, tokens.access_token);
    expect(listed.status).toBe(200);
    const names = (
      (listed.body?.result as { tools?: { name: string }[] } | undefined)
        ?.tools ?? []
    ).map((tool) => tool.name);
    expect(names).toContain("patent_client_status");
    expect(names).not.toContain("search_trademarks");

    const called = await rpc(
      hosted.url,
      "tools/call",
      { name: "patent_client_status", arguments: {} },
      tokens.access_token,
    );
    expect(called.status).toBe(200);
    expect(
      (called.body?.result as { isError?: boolean } | undefined)?.isError,
    ).not.toBe(true);
    // The usage log holds the pseudonymous actor, not the email.
    const record = hosted.usage.records.at(-1);
    expect(record?.tool).toBe("patent_client_status");
    expect(record?.actor_id).toMatch(/^[0-9a-f]{32}$/);
    expect(JSON.stringify(hosted.usage.records)).not.toContain("example.com");
    expect(JSON.stringify(hosted.events)).not.toContain("example.com");
    expect(JSON.stringify(hosted.events)).not.toContain(tokens.access_token);

    // Refresh rotates the refresh token and keeps the grant.
    const refreshed = await tokenRequest({
      grant_type: "refresh_token",
      client_id: clientId,
      refresh_token: tokens.refresh_token ?? "",
    });
    expect(refreshed.response.status).toBe(200);
    expect(refreshed.body.refresh_token).not.toBe(tokens.refresh_token);
    expect(google.tokenRequests.at(-1)?.get("grant_type")).toBe(
      "refresh_token",
    );
    const replay = await tokenRequest({
      grant_type: "refresh_token",
      client_id: clientId,
      refresh_token: tokens.refresh_token ?? "",
    });
    expect(replay.response.status).toBe(400);
    expect(replay.body.error).toBe("invalid_grant");
    expect(
      (await rpc(hosted.url, "tools/list", {}, refreshed.body.access_token))
        .status,
    ).toBe(200);

    // Expiry: past its lifetime and the 30 s clock tolerance, the access
    // token is refused with a 401 challenge.
    clock += 3700 * 1000;
    const expired = await rpc(
      hosted.url,
      "tools/list",
      {},
      refreshed.body.access_token,
    );
    expect(expired.status).toBe(401);
    expect(expired.response.headers.get("www-authenticate")).toContain(
      "resource_metadata=",
    );
    expect(expired.body?.error_description).toContain("expired");
    // ...and refresh still works.
    const again = await tokenRequest({
      grant_type: "refresh_token",
      client_id: clientId,
      refresh_token: refreshed.body.refresh_token ?? "",
    });
    expect(again.response.status).toBe(200);

    // Revoking the refresh token ends the grant, access tokens included.
    const revoked = await fetch(`${hosted.url}/revoke`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: clientId,
        token: again.body.refresh_token ?? "",
      }),
    });
    expect(revoked.status).toBe(200);
    expect(
      (await rpc(hosted.url, "tools/list", {}, again.body.access_token)).status,
    ).toBe(401);
    expect(
      (
        await tokenRequest({
          grant_type: "refresh_token",
          client_id: clientId,
          refresh_token: again.body.refresh_token ?? "",
        })
      ).body.error,
    ).toBe("invalid_grant");
  });

  test("revoking an access token ends its grant", async () => {
    const { clientId, tokens } = await signIn();
    const response = await fetch(`${hosted.url}/revoke`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: clientId,
        token: tokens.access_token ?? "",
      }),
    });
    expect(response.status).toBe(200);
    expect(
      (await rpc(hosted.url, "tools/list", {}, tokens.access_token)).status,
    ).toBe(401);
  });

  test("codes are single use, PKCE-bound and client-bound", async () => {
    const { body: client } = await register();
    const clientId = String(client.client_id);
    const { body: other } = await register();
    const { verifier, challenge } = pkcePair();
    const { returned } = await browserFlow(clientId, challenge);
    const code =
      new URL(returned.headers.get("location") ?? "").searchParams.get(
        "code",
      ) ?? "";
    const wrongVerifier = await tokenRequest({
      grant_type: "authorization_code",
      client_id: clientId,
      code,
      code_verifier: pkcePair().verifier,
    });
    expect(wrongVerifier.body.error).toBe("invalid_grant");
    // The failed attempt consumed the code.
    const retry = await tokenRequest({
      grant_type: "authorization_code",
      client_id: clientId,
      code,
      code_verifier: verifier,
    });
    expect(retry.body.error).toBe("invalid_grant");

    const second = pkcePair();
    const { returned: again } = await browserFlow(clientId, second.challenge);
    const code2 =
      new URL(again.headers.get("location") ?? "").searchParams.get("code") ??
      "";
    const otherClient = await tokenRequest({
      grant_type: "authorization_code",
      client_id: String(other.client_id),
      code: code2,
      code_verifier: second.verifier,
    });
    expect(otherClient.body.error).toBe("invalid_grant");
    const unknown = await tokenRequest({
      grant_type: "authorization_code",
      client_id: "nobody",
      code: code2,
      code_verifier: second.verifier,
    });
    expect(unknown.response.status).toBe(401);
    expect(unknown.body.error).toBe("invalid_client");
  });

  test("the callback refuses a browser without the binding cookie", async () => {
    const { body: client } = await register();
    const { returned } = await browserFlow(
      String(client.client_id),
      pkcePair().challenge,
      {
        dropBinding: true,
      },
    );
    expect(returned.status).toBe(403);
    expect(returned.headers.get("content-type")).toContain("text/html");
    expect(await returned.text()).toContain("different browser");
  });

  test("unverified Google emails are refused", async () => {
    google.user = {
      sub: "g2",
      email: "new@example.com",
      email_verified: false,
    };
    const { body: client } = await register();
    const { returned } = await browserFlow(
      String(client.client_id),
      pkcePair().challenge,
    );
    expect(returned.status).toBe(403);
    expect(await returned.text()).toContain("not verified");
  });

  test("Google invalid_grant on refresh ends the grant; outages keep the refresh token", async () => {
    const { clientId, tokens } = await signIn();
    google.refreshResult = "unavailable";
    const outage = await tokenRequest({
      grant_type: "refresh_token",
      client_id: clientId,
      refresh_token: tokens.refresh_token ?? "",
    });
    expect(outage.response.status).toBe(503);
    expect(outage.body.error).toBe("temporarily_unavailable");
    google.refreshResult = "invalid_grant";
    const refused = await tokenRequest({
      grant_type: "refresh_token",
      client_id: clientId,
      refresh_token: tokens.refresh_token ?? "",
    });
    expect(refused.body.error).toBe("invalid_grant");
    expect(
      (await rpc(hosted.url, "tools/list", {}, tokens.access_token)).status,
    ).toBe(401);
  });

  test("without an upstream refresh token, no refresh token is issued", async () => {
    google.issueRefreshToken = false;
    const { tokens } = await signIn();
    expect(tokens.refresh_token).toBeUndefined();
    expect(
      (await rpc(hosted.url, "tools/list", {}, tokens.access_token)).status,
    ).toBe(200);
  });

  test("registration enforces the redirect URI allowlist", async () => {
    const refused = await register(["https://evil.example/callback"]);
    expect(refused.response.status).toBe(400);
    expect(refused.body.error).toBe("invalid_redirect_uri");
    const userinfo = await register(["http://localhost@evil.example/cb"]);
    expect(userinfo.response.status).toBe(400);
    for (const uri of [
      "https://claude.ai/api/mcp/auth_callback",
      "claude://claude.ai/mcp-auth-callback/sdk",
      "http://localhost:51234/callback",
      "https://chatgpt.com/connector_platform_oauth_redirect",
    ]) {
      const accepted = await register([uri]);
      expect([uri, accepted.response.status]).toEqual([uri, 201]);
      expect(accepted.body.token_endpoint_auth_method).toBe("none");
      expect(accepted.body.client_secret).toBeUndefined();
    }
  });

  test("authorize validates client, redirect, PKCE, scope and resource", async () => {
    const cookie = "pca_terms_accepted=2026-04-23";
    const { body: client } = await register();
    const clientId = String(client.client_id);
    const { challenge } = pkcePair();
    const unknown = await get(
      `/authorize?${authorizeQuery("missing", challenge)}`,
      { cookie },
    );
    expect(unknown.status).toBe(400);
    expect(unknown.headers.get("content-type")).toContain("text/html");
    const badRedirect = await get(
      `/authorize?${authorizeQuery(clientId, challenge, { redirect_uri: "https://claude.ai/other" })}`,
      { cookie },
    );
    expect(badRedirect.status).toBe(400);
    // Loopback redirects may change port between sign-ins (RFC 8252 §7.3).
    const otherPort = await get(
      `/authorize?${authorizeQuery(clientId, challenge, { redirect_uri: "http://127.0.0.1:40000/callback" })}`,
      { cookie },
    );
    expect(otherPort.status).toBe(302);
    expect(new URL(otherPort.headers.get("location") ?? "").origin).toBe(
      google.url,
    );
    const errorOf = async (extra: Record<string, string>) => {
      const response = await get(
        `/authorize?${authorizeQuery(clientId, challenge, extra)}`,
        { cookie },
      );
      expect(response.status).toBe(302);
      const location = new URL(response.headers.get("location") ?? "");
      expect(location.searchParams.get("state")).toBe("client-state-123");
      return location.searchParams.get("error");
    };
    expect(await errorOf({ code_challenge: "" })).toBe("invalid_request");
    expect(await errorOf({ code_challenge_method: "plain" })).toBe(
      "invalid_request",
    );
    expect(
      await errorOf({ scope: "openid https://www.googleapis.com/auth/drive" }),
    ).toBe("invalid_scope");
    expect(await errorOf({ resource: "https://other.example/mcp" })).toBe(
      "invalid_target",
    );
    expect(await errorOf({ response_type: "token" })).toBe(
      "unsupported_response_type",
    );
    // A resource with a query string still names this server.
    const withQuery = await get(
      `/authorize?${authorizeQuery(clientId, challenge, { resource: `${hosted.url}/mcp?kb=1` })}`,
      { cookie },
    );
    expect(new URL(withQuery.headers.get("location") ?? "").origin).toBe(
      google.url,
    );
  });

  test("forged, wrongly signed or foreign tokens are refused", async () => {
    const { tokens } = await signIn();
    const [header, payload] = (tokens.access_token ?? "").split(".");
    const forged = `${header}.${payload}.${"A".repeat(43)}`;
    for (const token of [forged, "not-a-jwt", tokens.refresh_token ?? ""]) {
      const response = await rpc(hosted.url, "tools/list", {}, token);
      expect(response.status).toBe(401);
    }
    const missing = await rpc(hosted.url, "tools/list");
    expect(missing.status).toBe(401);
    expect(missing.response.headers.get("www-authenticate")).toMatch(
      /^Bearer .*resource_metadata="http:\/\/127\.0\.0\.1:\d+\/\.well-known\/oauth-protected-resource\/mcp"/,
    );
  });

  test.if(!emulator)("stored Google tokens are sealed", async () => {
    await signIn();
    const raw = JSON.stringify(
      Object.fromEntries(
        (hosted.oauthStore as unknown as { records: Map<string, unknown> })
          .records,
      ),
    );
    expect(raw).not.toContain("google-access");
    expect(raw).not.toContain("google-refresh");
  });
});

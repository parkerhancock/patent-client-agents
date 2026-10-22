import { decodeJwt, errors as joseErrors, jwtVerify, SignJWT } from "jose";
import {
  constantTimeEqual,
  deriveKey,
  pkceChallenge,
  randomToken,
  Sealer,
  sha256Hex,
} from "../crypto.js";
import {
  BodyTooLarge,
  type FetchLike,
  json,
  parseCookies,
  readBody,
  readForm,
  redirect,
  serializeCookie,
} from "../http.js";
import type { Clock, OAuthStore } from "../storage.js";
import { DEFAULT_REDIRECT_PATTERNS, redirectAllowed } from "./redirects.js";

/**
 * OAuth 2.1 authorization server for MCP clients that proxies sign-in to
 * Google, after the Python FastMCP GoogleProvider (an OAuthProxy): clients
 * register dynamically, the browser signs in with Google through this
 * server's fixed /auth/callback, and the client receives tokens issued here,
 * never Google's. Every piece of state lives in an OAuthStore, so any
 * instance can serve any step.
 */

export const GOOGLE_ENDPOINTS = {
  authorization: "https://accounts.google.com/o/oauth2/v2/auth",
  token: "https://oauth2.googleapis.com/token",
} as const;

/** Scopes advertised and granted, in the full form Google returns. */
export const SUPPORTED_SCOPES = [
  "openid",
  "https://www.googleapis.com/auth/userinfo.email",
  "https://www.googleapis.com/auth/userinfo.profile",
] as const;
const SCOPE_ALIASES: Record<string, string> = {
  email: "https://www.googleapis.com/auth/userinfo.email",
  profile: "https://www.googleapis.com/auth/userinfo.profile",
};
const GOOGLE_ISSUERS = new Set([
  "https://accounts.google.com",
  "accounts.google.com",
]);

const TRANSACTION_TTL = 15 * 60;
const CODE_TTL = 5 * 60;
const DEFAULT_ACCESS_TTL = 60 * 60;
const DEFAULT_REFRESH_TTL = 30 * 24 * 60 * 60;
const BINDING_COOKIE_PREFIX = "pca_oauth_";

export interface GoogleProxyOptions {
  /** Issuer identifier advertised in metadata and access tokens. */
  issuer: string;
  /** Public origin; Google redirects to `${baseUrl}/auth/callback`. */
  baseUrl: string;
  /** Protected resource (the MCP endpoint); the access-token audience. */
  resource: string;
  clientId: string;
  clientSecret: string;
  /** Derives the token-signing and token-sealing keys. */
  sessionSecret: string;
  store: OAuthStore;
  /** HTML error page renderer for browser-facing failures. */
  errorPage: (status: number, title: string, message: string) => Response;
  redirectPatterns?: readonly string[];
  endpoints?: { authorization: string; token: string };
  fetch?: FetchLike;
  now?: Clock;
  accessTokenTtlSeconds?: number;
  refreshTokenTtlSeconds?: number;
}

export interface Identity {
  sub: string;
  email: string;
  email_verified: boolean;
  name?: string;
}

interface ClientRecord {
  client_id: string;
  client_name?: string;
  redirect_uris: string[];
  grant_types: string[];
  response_types: string[];
  token_endpoint_auth_method: "none";
  scope: string;
  client_id_issued_at: number;
}
interface TransactionRecord {
  client_id: string;
  redirect_uri: string;
  state?: string;
  code_challenge: string;
  scopes: string[];
  resource?: string;
  upstream_verifier: string;
  binding: string;
  created_at: number;
}
interface Upstream {
  access_token: string;
  refresh_token?: string;
}
interface CodeRecord {
  client_id: string;
  redirect_uri: string;
  code_challenge: string;
  scopes: string[];
  identity: Identity;
  sealed: string;
  upstream_expires_in: number;
  created_at: number;
}
interface GrantRecord {
  client_id: string;
  scopes: string[];
  identity: Identity;
  sealed: string;
  upstream_expires_at: number;
  /** Absolute end of the grant; refresh tokens never outlive it. */
  expires_at: number;
  created_at: number;
}
interface RefreshRecord {
  client_id: string;
  grant_id: string;
  scopes: string[];
  expires_at: number;
}

/** What a verified access token carries into MCP request handling. */
export interface VerifiedToken {
  token: string;
  clientId: string;
  scopes: string[];
  expiresAt: number;
  extra: {
    sub: string;
    email: string;
    email_verified: boolean;
    name?: string;
    iss: string;
    client_id: string;
  };
}

export class InvalidTokenError extends Error {
  override name = "InvalidTokenError";
}

class OAuthError extends Error {
  constructor(
    readonly error: string,
    readonly description: string,
    readonly status = 400,
  ) {
    super(description);
  }
}

function normalizeScopes(scope: string | null | undefined): string[] {
  return [
    ...new Set(
      (scope ?? "")
        .split(/\s+/)
        .filter(Boolean)
        .map((item) => SCOPE_ALIASES[item] ?? item),
    ),
  ];
}

function isLoopbackHttp(uri: string): URL | undefined {
  try {
    const url = new URL(uri);
    return url.protocol === "http:" &&
      ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
      ? url
      : undefined;
  } catch {
    return undefined;
  }
}

/** Exact match, or a loopback redirect differing only in port (RFC 8252 §7.3). */
function sameRedirect(registered: string, requested: string): boolean {
  if (registered === requested) return true;
  const left = isLoopbackHttp(registered);
  const right = isLoopbackHttp(requested);
  if (!left || !right) return false;
  left.port = "";
  right.port = "";
  return left.href === right.href;
}

function normalizeResource(value: string): string {
  const url = new URL(value);
  url.search = "";
  url.hash = "";
  return url.href.replace(/\/+$/, "");
}

function withParams(uri: string, params: Record<string, string | undefined>) {
  const url = new URL(uri);
  for (const [name, value] of Object.entries(params))
    if (value !== undefined) url.searchParams.set(name, value);
  return url.href;
}

const NO_STORE = { "cache-control": "no-store", pragma: "no-cache" };

export class GoogleOAuthProxy {
  private readonly endpoints: { authorization: string; token: string };
  private readonly fetcher: FetchLike;
  private readonly now: Clock;
  private readonly patterns: readonly string[];
  private readonly accessTtl: number;
  private readonly refreshTtl: number;
  private readonly secureCookies: boolean;
  private keys?: Promise<{ signing: Uint8Array; sealer: Sealer }>;

  constructor(private readonly options: GoogleProxyOptions) {
    this.endpoints = options.endpoints ?? GOOGLE_ENDPOINTS;
    this.fetcher = options.fetch ?? fetch;
    this.now = options.now ?? Date.now;
    this.patterns = options.redirectPatterns ?? DEFAULT_REDIRECT_PATTERNS;
    this.accessTtl = options.accessTokenTtlSeconds ?? DEFAULT_ACCESS_TTL;
    this.refreshTtl = options.refreshTokenTtlSeconds ?? DEFAULT_REFRESH_TTL;
    this.secureCookies = options.baseUrl.startsWith("https://");
  }

  private material() {
    this.keys ??= (async () => ({
      signing: await deriveKey(this.options.sessionSecret, "access-token/v1"),
      sealer: await Sealer.fromSecret(this.options.sessionSecret),
    }))();
    return this.keys;
  }

  private seconds() {
    return Math.floor(this.now() / 1000);
  }

  get callbackUrl() {
    return `${this.options.baseUrl}/auth/callback`;
  }

  get resourceMetadataUrl() {
    const path = new URL(this.options.resource).pathname;
    return `${this.options.baseUrl}/.well-known/oauth-protected-resource${path === "/" ? "" : path}`;
  }

  authorizationServerMetadata() {
    const base = this.options.baseUrl;
    return {
      issuer: this.options.issuer,
      authorization_endpoint: `${base}/authorize`,
      token_endpoint: `${base}/token`,
      registration_endpoint: `${base}/register`,
      revocation_endpoint: `${base}/revoke`,
      scopes_supported: [...SUPPORTED_SCOPES],
      response_types_supported: ["code"],
      grant_types_supported: ["authorization_code", "refresh_token"],
      token_endpoint_auth_methods_supported: ["none"],
      revocation_endpoint_auth_methods_supported: ["none"],
      code_challenge_methods_supported: ["S256"],
    };
  }

  protectedResourceMetadata() {
    return {
      resource: this.options.resource,
      authorization_servers: [this.options.issuer],
      scopes_supported: [...SUPPORTED_SCOPES],
      bearer_methods_supported: ["header"],
    };
  }

  /** WWW-Authenticate for a 401 from the MCP endpoint (RFC 6750, RFC 9728). */
  challenge(description: string) {
    const quoted = description.replace(/["\\]/g, "");
    return `Bearer error="invalid_token", error_description="${quoted}", resource_metadata="${this.resourceMetadataUrl}"`;
  }

  // ---------------------------------------------------------------- register

  async register(request: Request): Promise<Response> {
    let body: unknown;
    try {
      body = JSON.parse(await readBody(request, 64 * 1024));
    } catch (error) {
      return error instanceof BodyTooLarge
        ? json(
            {
              error: "invalid_client_metadata",
              error_description: "Registration body is too large.",
            },
            413,
          )
        : json(
            {
              error: "invalid_client_metadata",
              error_description: "Registration body must be JSON.",
            },
            400,
          );
    }
    const metadata = (body ?? {}) as Record<string, unknown>;
    const fail = (error: string, description: string) =>
      json({ error, error_description: description }, 400, NO_STORE);
    const uris = metadata.redirect_uris;
    if (
      !Array.isArray(uris) ||
      uris.length === 0 ||
      uris.length > 10 ||
      !uris.every((uri) => typeof uri === "string" && uri.length <= 2048)
    )
      return fail("invalid_redirect_uri", "Provide one to ten redirect_uris.");
    const rejected = (uris as string[]).filter(
      (uri) => !redirectAllowed(uri, this.patterns),
    );
    if (rejected.length)
      return fail(
        "invalid_redirect_uri",
        `Redirect URI is not allowed for this server: ${rejected[0]}`,
      );
    const grantTypes = metadata.grant_types ?? [
      "authorization_code",
      "refresh_token",
    ];
    if (
      !Array.isArray(grantTypes) ||
      !grantTypes.every((grant) =>
        ["authorization_code", "refresh_token"].includes(grant as string),
      )
    )
      return fail(
        "invalid_client_metadata",
        "Supported grant_types are authorization_code and refresh_token.",
      );
    const responseTypes = metadata.response_types ?? ["code"];
    if (
      !Array.isArray(responseTypes) ||
      !responseTypes.every((type) => type === "code")
    )
      return fail("invalid_client_metadata", "The only response_type is code.");
    const scopes = normalizeScopes(
      typeof metadata.scope === "string" ? metadata.scope : undefined,
    );
    if (
      scopes.some(
        (scope) => !(SUPPORTED_SCOPES as readonly string[]).includes(scope),
      )
    )
      return fail("invalid_client_metadata", "Unsupported scope requested.");
    const clientName =
      typeof metadata.client_name === "string"
        ? metadata.client_name.slice(0, 200)
        : undefined;
    // Every client is public: the proxy authenticates to Google itself, and
    // PKCE binds codes to the client that started the flow.
    const record: ClientRecord = {
      client_id: randomToken(),
      ...(clientName ? { client_name: clientName } : {}),
      redirect_uris: uris as string[],
      grant_types: grantTypes as string[],
      response_types: ["code"],
      token_endpoint_auth_method: "none",
      scope: (scopes.length ? scopes : [...SUPPORTED_SCOPES]).join(" "),
      client_id_issued_at: this.seconds(),
    };
    await this.options.store.put("clients", record.client_id, record);
    return json(record, 201, NO_STORE);
  }

  // --------------------------------------------------------------- authorize

  async authorize(request: Request): Promise<Response> {
    const params = new URL(request.url).searchParams;
    const clientId = params.get("client_id");
    const client = clientId
      ? await this.options.store.get<ClientRecord>("clients", clientId)
      : undefined;
    if (!client)
      return this.options.errorPage(
        400,
        "Unknown client",
        "This connector's registration was not found. Remove the connector from your MCP client and add it again so it registers afresh.",
      );
    const requested = params.get("redirect_uri");
    const redirectUri = requested
      ? client.redirect_uris.find((uri) => sameRedirect(uri, requested)) &&
        requested
      : client.redirect_uris.length === 1
        ? client.redirect_uris[0]
        : undefined;
    if (!redirectUri)
      return this.options.errorPage(
        400,
        "Invalid redirect",
        "The redirect URI does not match this connector's registration.",
      );
    const state = params.get("state") ?? undefined;
    const back = (error: string, description: string) =>
      redirect(
        withParams(redirectUri, {
          error,
          error_description: description,
          state,
        }),
      );
    if (params.get("response_type") !== "code")
      return back("unsupported_response_type", "response_type must be code.");
    const challenge = params.get("code_challenge");
    if (!challenge || !/^[A-Za-z0-9_-]{43,128}$/.test(challenge))
      return back("invalid_request", "A PKCE code_challenge is required.");
    if ((params.get("code_challenge_method") ?? "plain") !== "S256")
      return back("invalid_request", "code_challenge_method must be S256.");
    const scopes = normalizeScopes(params.get("scope") ?? client.scope);
    if (
      scopes.length === 0 ||
      scopes.some(
        (scope) => !(SUPPORTED_SCOPES as readonly string[]).includes(scope),
      )
    )
      return back("invalid_scope", "Unsupported scope requested.");
    const resource = params.get("resource") ?? undefined;
    if (resource) {
      let matches = false;
      try {
        matches =
          normalizeResource(resource) ===
          normalizeResource(this.options.resource);
      } catch {}
      if (!matches)
        return back("invalid_target", "Resource does not match this server.");
    }
    const transactionId = randomToken();
    const nonce = randomToken();
    const upstreamVerifier = randomToken();
    const transaction: TransactionRecord = {
      client_id: client.client_id,
      redirect_uri: redirectUri,
      ...(state !== undefined ? { state } : {}),
      code_challenge: challenge,
      scopes,
      ...(resource ? { resource } : {}),
      upstream_verifier: upstreamVerifier,
      binding: await sha256Hex(nonce),
      created_at: this.seconds(),
    };
    await this.options.store.put(
      "transactions",
      transactionId,
      transaction,
      TRANSACTION_TTL,
    );
    const google = withParams(this.endpoints.authorization, {
      client_id: this.options.clientId,
      redirect_uri: this.callbackUrl,
      response_type: "code",
      scope: "openid email profile",
      state: transactionId,
      code_challenge: await pkceChallenge(upstreamVerifier),
      code_challenge_method: "S256",
      access_type: "offline",
      prompt: "consent",
    });
    // Bind the transaction to this browser so a Google redirect replayed in
    // another browser cannot finish someone else's authorization.
    return redirect(google, 302, {
      "set-cookie": serializeCookie(this.bindingCookie(transactionId), nonce, {
        maxAge: TRANSACTION_TTL,
        path: "/auth/callback",
        secure: this.secureCookies,
      }),
      ...NO_STORE,
    });
  }

  private bindingCookie(transactionId: string) {
    return `${BINDING_COOKIE_PREFIX}${transactionId.slice(0, 16)}`;
  }

  // ---------------------------------------------------------------- callback

  async callback(request: Request): Promise<Response> {
    const params = new URL(request.url).searchParams;
    const transactionId = params.get("state");
    const transaction =
      transactionId && /^[A-Za-z0-9_-]{43}$/.test(transactionId)
        ? await this.options.store.take<TransactionRecord>(
            "transactions",
            transactionId,
          )
        : undefined;
    if (!transactionId || !transaction)
      return this.options.errorPage(
        400,
        "Sign-in expired",
        "This sign-in attempt is invalid or has expired. Start the connection again from your MCP client.",
      );
    const cookieName = this.bindingCookie(transactionId);
    const clear = serializeCookie(cookieName, "", {
      maxAge: 0,
      path: "/auth/callback",
      secure: this.secureCookies,
    });
    const page = (status: number, title: string, message: string) => {
      const response = this.options.errorPage(status, title, message);
      response.headers.append("set-cookie", clear);
      return response;
    };
    const nonce = parseCookies(request.headers.get("cookie"))[cookieName];
    if (
      !nonce ||
      !constantTimeEqual(await sha256Hex(nonce), transaction.binding)
    )
      return page(
        403,
        "Sign-in session mismatch",
        "This sign-in was started in a different browser or the session expired. Start the connection again from your MCP client.",
      );
    const upstreamError = params.get("error");
    if (upstreamError) {
      const response = redirect(
        withParams(transaction.redirect_uri, {
          error: "access_denied",
          error_description: "Google sign-in did not complete.",
          state: transaction.state,
        }),
      );
      response.headers.append("set-cookie", clear);
      return response;
    }
    const code = params.get("code");
    if (!code)
      return page(
        400,
        "Sign-in failed",
        "Google returned no authorization code.",
      );
    let upstream: GoogleTokenResponse;
    try {
      upstream = await this.googleToken({
        grant_type: "authorization_code",
        code,
        redirect_uri: this.callbackUrl,
        code_verifier: transaction.upstream_verifier,
      });
    } catch {
      return page(
        502,
        "Sign-in failed",
        "Google did not accept the sign-in. Start the connection again from your MCP client.",
      );
    }
    let identity: Identity;
    try {
      identity = this.identityFrom(upstream.id_token);
    } catch (error) {
      return page(
        403,
        "Sign-in refused",
        error instanceof UnverifiedEmail
          ? "Your Google account's email address is not verified. Verify it with Google, then connect again."
          : "Google's sign-in response could not be verified.",
      );
    }
    const clientCode = randomToken();
    const codeId = await sha256Hex(clientCode);
    const { sealer } = await this.material();
    const record: CodeRecord = {
      client_id: transaction.client_id,
      redirect_uri: transaction.redirect_uri,
      code_challenge: transaction.code_challenge,
      scopes: transaction.scopes,
      identity,
      sealed: await sealer.seal(
        {
          access_token: upstream.access_token,
          ...(upstream.refresh_token
            ? { refresh_token: upstream.refresh_token }
            : {}),
        } satisfies Upstream,
        `code:${codeId}`,
      ),
      upstream_expires_in: upstream.expires_in ?? DEFAULT_ACCESS_TTL,
      created_at: this.seconds(),
    };
    await this.options.store.put("codes", codeId, record, CODE_TTL);
    const response = redirect(
      withParams(transaction.redirect_uri, {
        code: clientCode,
        state: transaction.state,
      }),
    );
    response.headers.append("set-cookie", clear);
    return response;
  }

  private identityFrom(idToken: string | undefined): Identity {
    // The ID token came straight from Google's token endpoint over TLS, so
    // its signature need not be checked (OIDC Core 3.1.3.7); its issuer,
    // audience and expiry still must match.
    if (!idToken) throw new Error("No ID token.");
    const claims = decodeJwt(idToken);
    const audience = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    if (
      !GOOGLE_ISSUERS.has(String(claims.iss)) ||
      !audience.includes(this.options.clientId) ||
      typeof claims.exp !== "number" ||
      claims.exp + 300 < this.seconds() ||
      typeof claims.sub !== "string" ||
      typeof claims.email !== "string"
    )
      throw new Error("ID token claims do not match.");
    if (claims.email_verified !== true && claims.email_verified !== "true")
      throw new UnverifiedEmail();
    return {
      sub: claims.sub,
      email: claims.email.toLowerCase(),
      email_verified: true,
      ...(typeof claims.name === "string" ? { name: claims.name } : {}),
    };
  }

  private async googleToken(
    params: Record<string, string>,
  ): Promise<GoogleTokenResponse> {
    const response = await this.fetcher(this.endpoints.token, {
      method: "POST",
      headers: {
        "content-type": "application/x-www-form-urlencoded",
        accept: "application/json",
      },
      body: new URLSearchParams({
        ...params,
        client_id: this.options.clientId,
        client_secret: this.options.clientSecret,
      }),
      signal: AbortSignal.timeout(15_000),
    });
    let body: Record<string, unknown> = {};
    try {
      body = (await response.json()) as Record<string, unknown>;
    } catch {}
    if (!response.ok || typeof body.access_token !== "string")
      throw new UpstreamTokenError(
        typeof body.error === "string" ? body.error : `http_${response.status}`,
      );
    return {
      access_token: body.access_token,
      ...(typeof body.refresh_token === "string"
        ? { refresh_token: body.refresh_token }
        : {}),
      ...(typeof body.expires_in === "number"
        ? { expires_in: body.expires_in }
        : {}),
      ...(typeof body.id_token === "string" ? { id_token: body.id_token } : {}),
    };
  }

  // ------------------------------------------------------------------- token

  async token(request: Request): Promise<Response> {
    try {
      const form = await readForm(request);
      const client = await this.authenticateClient(request, form);
      const grantType = form.get("grant_type");
      if (grantType === "authorization_code")
        return await this.exchangeCode(client, form);
      if (grantType === "refresh_token")
        return await this.exchangeRefresh(client, form);
      throw new OAuthError(
        "unsupported_grant_type",
        "grant_type must be authorization_code or refresh_token.",
      );
    } catch (error) {
      if (error instanceof OAuthError)
        return json(
          { error: error.error, error_description: error.description },
          error.status,
          NO_STORE,
        );
      if (error instanceof BodyTooLarge)
        return json(
          {
            error: "invalid_request",
            error_description: "Request is too large.",
          },
          413,
          NO_STORE,
        );
      throw error;
    }
  }

  private async authenticateClient(request: Request, form: URLSearchParams) {
    let clientId = form.get("client_id");
    const basic = /^Basic\s+(.+)$/i.exec(
      request.headers.get("authorization") ?? "",
    )?.[1];
    if (basic) {
      try {
        const decoded = atob(basic);
        const user = decodeURIComponent(decoded.slice(0, decoded.indexOf(":")));
        if (clientId && clientId !== user)
          throw new OAuthError("invalid_request", "Conflicting client ids.");
        clientId = user;
      } catch (error) {
        if (error instanceof OAuthError) throw error;
        throw new OAuthError(
          "invalid_client",
          "Malformed client credentials.",
          401,
        );
      }
    }
    const client = clientId
      ? await this.options.store.get<ClientRecord>("clients", clientId)
      : undefined;
    if (!client)
      throw new OAuthError(
        "invalid_client",
        "Client not found. Register again.",
        401,
      );
    return client;
  }

  private async exchangeCode(client: ClientRecord, form: URLSearchParams) {
    const code = form.get("code");
    const verifier = form.get("code_verifier");
    if (!code || !verifier)
      throw new OAuthError(
        "invalid_request",
        "code and code_verifier are required.",
      );
    const codeId = await sha256Hex(code);
    const record = await this.options.store.take<CodeRecord>("codes", codeId);
    if (!record || record.client_id !== client.client_id)
      throw new OAuthError(
        "invalid_grant",
        "Authorization code is invalid or expired.",
      );
    const redirectUri = form.get("redirect_uri");
    if (redirectUri && redirectUri !== record.redirect_uri)
      throw new OAuthError("invalid_grant", "redirect_uri does not match.");
    if (
      !/^[A-Za-z0-9._~-]{43,128}$/.test(verifier) ||
      !constantTimeEqual(await pkceChallenge(verifier), record.code_challenge)
    )
      throw new OAuthError("invalid_grant", "PKCE verification failed.");
    const { sealer } = await this.material();
    const upstream = await sealer.open<Upstream>(
      record.sealed,
      `code:${codeId}`,
    );
    const grantId = randomToken();
    const now = this.seconds();
    const accessLifetime = Math.min(this.accessTtl, record.upstream_expires_in);
    const refreshable =
      Boolean(upstream.refresh_token) &&
      client.grant_types.includes("refresh_token");
    const grant: GrantRecord = {
      client_id: client.client_id,
      scopes: record.scopes,
      identity: record.identity,
      sealed: await sealer.seal(upstream, `grant:${grantId}`),
      upstream_expires_at: now + record.upstream_expires_in,
      expires_at: now + (refreshable ? this.refreshTtl : accessLifetime),
      created_at: now,
    };
    await this.options.store.put(
      "grants",
      grantId,
      grant,
      grant.expires_at - now,
    );
    return this.issue(grantId, grant, accessLifetime, refreshable);
  }

  private async exchangeRefresh(client: ClientRecord, form: URLSearchParams) {
    const presented = form.get("refresh_token");
    if (!presented)
      throw new OAuthError("invalid_request", "refresh_token is required.");
    const refreshId = await sha256Hex(presented);
    const record = await this.options.store.take<RefreshRecord>(
      "refresh_tokens",
      refreshId,
    );
    const now = this.seconds();
    if (
      !record ||
      record.client_id !== client.client_id ||
      record.expires_at <= now
    )
      throw new OAuthError(
        "invalid_grant",
        "Refresh token is invalid or expired.",
      );
    const grant = await this.options.store.get<GrantRecord>(
      "grants",
      record.grant_id,
    );
    if (!grant || grant.client_id !== client.client_id)
      throw new OAuthError("invalid_grant", "The authorization was revoked.");
    const requested = normalizeScopes(form.get("scope"));
    if (requested.some((scope) => !grant.scopes.includes(scope)))
      throw new OAuthError(
        "invalid_scope",
        "Requested scope exceeds the grant.",
      );
    const { sealer } = await this.material();
    const upstream = await sealer.open<Upstream>(
      grant.sealed,
      `grant:${record.grant_id}`,
    );
    if (!upstream.refresh_token)
      throw new OAuthError(
        "invalid_grant",
        "The authorization cannot be refreshed.",
      );
    let refreshed: GoogleTokenResponse;
    try {
      refreshed = await this.googleToken({
        grant_type: "refresh_token",
        refresh_token: upstream.refresh_token,
      });
    } catch (error) {
      if (
        error instanceof UpstreamTokenError &&
        error.code === "invalid_grant"
      ) {
        await this.options.store.delete("grants", record.grant_id);
        throw new OAuthError(
          "invalid_grant",
          "Google no longer accepts this authorization. Sign in again.",
        );
      }
      // Transient upstream failure: give the client its refresh token back.
      await this.options.store.put(
        "refresh_tokens",
        refreshId,
        record,
        Math.max(1, record.expires_at - now),
      );
      throw new OAuthError(
        "temporarily_unavailable",
        "Google could not be reached. Try again shortly.",
        503,
      );
    }
    const updatedUpstream: Upstream = {
      access_token: refreshed.access_token,
      refresh_token: refreshed.refresh_token ?? upstream.refresh_token,
    };
    const expiresIn = refreshed.expires_in ?? DEFAULT_ACCESS_TTL;
    const updated: GrantRecord = {
      ...grant,
      sealed: await sealer.seal(updatedUpstream, `grant:${record.grant_id}`),
      upstream_expires_at: now + expiresIn,
    };
    await this.options.store.put(
      "grants",
      record.grant_id,
      updated,
      Math.max(1, updated.expires_at - now),
    );
    const scoped = requested.length
      ? { ...updated, scopes: requested }
      : updated;
    return this.issue(
      record.grant_id,
      scoped,
      Math.min(this.accessTtl, expiresIn, updated.expires_at - now),
      true,
    );
  }

  private async issue(
    grantId: string,
    grant: GrantRecord,
    lifetime: number,
    refreshable: boolean,
  ) {
    const { signing } = await this.material();
    const now = this.seconds();
    const accessToken = await new SignJWT({
      client_id: grant.client_id,
      scope: grant.scopes.join(" "),
      gid: grantId,
    })
      .setProtectedHeader({ alg: "HS256", typ: "at+jwt" })
      .setIssuer(this.options.issuer)
      .setAudience(this.options.resource)
      .setSubject(grant.identity.sub)
      .setJti(randomToken())
      .setIssuedAt(now)
      .setExpirationTime(now + lifetime)
      .sign(signing);
    let refreshToken: string | undefined;
    if (refreshable) {
      refreshToken = randomToken();
      const record: RefreshRecord = {
        client_id: grant.client_id,
        grant_id: grantId,
        scopes: grant.scopes,
        expires_at: grant.expires_at,
      };
      await this.options.store.put(
        "refresh_tokens",
        await sha256Hex(refreshToken),
        record,
        Math.max(1, grant.expires_at - now),
      );
    }
    return json(
      {
        access_token: accessToken,
        token_type: "Bearer",
        expires_in: lifetime,
        ...(refreshToken ? { refresh_token: refreshToken } : {}),
        scope: grant.scopes.join(" "),
      },
      200,
      NO_STORE,
    );
  }

  // ------------------------------------------------------------------ revoke

  /** RFC 7009. Revoking either token ends the whole grant. */
  async revoke(request: Request): Promise<Response> {
    let form: URLSearchParams;
    let client: ClientRecord;
    try {
      form = await readForm(request);
      client = await this.authenticateClient(request, form);
    } catch (error) {
      if (error instanceof OAuthError)
        return json(
          { error: error.error, error_description: error.description },
          error.status,
          NO_STORE,
        );
      throw error;
    }
    const token = form.get("token");
    if (!token)
      return json(
        { error: "invalid_request", error_description: "token is required." },
        400,
        NO_STORE,
      );
    const refresh = await this.options.store.take<RefreshRecord>(
      "refresh_tokens",
      await sha256Hex(token),
    );
    if (refresh) {
      if (refresh.client_id === client.client_id)
        await this.options.store.delete("grants", refresh.grant_id);
      else
        await this.options.store.put(
          "refresh_tokens",
          await sha256Hex(token),
          refresh,
          Math.max(1, refresh.expires_at - this.seconds()),
        );
      return new Response(null, { status: 200, headers: NO_STORE });
    }
    try {
      const claims = await this.verifyJwt(token, { ignoreExpiry: true });
      if (claims.client_id === client.client_id)
        await this.options.store.delete("grants", claims.gid);
    } catch {
      // Unknown or invalid tokens are not an error (RFC 7009 §2.2).
    }
    return new Response(null, { status: 200, headers: NO_STORE });
  }

  // ------------------------------------------------------------ verification

  private async verifyJwt(
    token: string,
    options: { ignoreExpiry?: boolean } = {},
  ) {
    const { signing } = await this.material();
    const { payload } = await jwtVerify(token, signing, {
      algorithms: ["HS256"],
      typ: "at+jwt",
      issuer: this.options.issuer,
      audience: this.options.resource,
      requiredClaims: ["exp", "sub", "jti"],
      currentDate: new Date(options.ignoreExpiry ? 0 : this.now()),
      clockTolerance: options.ignoreExpiry ? 0 : 30,
    });
    if (
      typeof payload.gid !== "string" ||
      typeof payload.client_id !== "string" ||
      typeof payload.scope !== "string"
    )
      throw new InvalidTokenError("Malformed access token.");
    return payload as typeof payload & {
      gid: string;
      client_id: string;
      scope: string;
      exp: number;
      sub: string;
    };
  }

  /** Validate an access token issued here and still backed by a live grant. */
  async verifyAccessToken(token: string): Promise<VerifiedToken> {
    let claims: Awaited<ReturnType<GoogleOAuthProxy["verifyJwt"]>>;
    try {
      claims = await this.verifyJwt(token);
    } catch (error) {
      if (error instanceof joseErrors.JWTExpired)
        throw new InvalidTokenError("Access token expired.");
      throw new InvalidTokenError("Access token is invalid.");
    }
    const grant = await this.options.store.get<GrantRecord>(
      "grants",
      claims.gid,
    );
    if (
      !grant ||
      grant.client_id !== claims.client_id ||
      grant.identity.sub !== claims.sub
    )
      throw new InvalidTokenError("Access token was revoked.");
    return {
      token,
      clientId: claims.client_id,
      scopes: claims.scope.split(" ").filter(Boolean),
      expiresAt: claims.exp,
      extra: {
        sub: grant.identity.sub,
        email: grant.identity.email,
        email_verified: grant.identity.email_verified,
        ...(grant.identity.name ? { name: grant.identity.name } : {}),
        iss: this.options.issuer,
        client_id: claims.client_id,
      },
    };
  }
}

interface GoogleTokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  id_token?: string;
}

class UpstreamTokenError extends Error {
  constructor(readonly code: string) {
    super(`Google token endpoint returned ${code}.`);
  }
}

class UnverifiedEmail extends Error {}

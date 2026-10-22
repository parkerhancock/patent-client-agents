import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { importPKCS8, SignJWT } from "jose";
import type { FetchLike } from "./http.js";

/**
 * Minimal Google credentials for the Firestore REST API, without the Google
 * SDKs: the Cloud Run metadata server, or Application Default Credentials
 * from GOOGLE_APPLICATION_CREDENTIALS or gcloud's well-known file (service
 * account keys and `gcloud auth application-default login` user credentials).
 */
export interface GoogleCredentials {
  /** OAuth access token with the datastore scope. */
  token(): Promise<string>;
  /** Project from the credentials or metadata server, when known. */
  projectId(): Promise<string | undefined>;
  /** Extra request headers, such as the quota project for user credentials. */
  headers(): Promise<Record<string, string>>;
}

const SCOPE = "https://www.googleapis.com/auth/datastore";
const METADATA = "http://metadata.google.internal/computeMetadata/v1";
const TOKEN_URI = "https://oauth2.googleapis.com/token";

type Fetch = FetchLike;

interface Minted {
  token: string;
  expiresAt: number;
}

function cached(mint: () => Promise<Minted>, now: () => number) {
  let current: Minted | undefined;
  let pending: Promise<Minted> | undefined;
  return async () => {
    if (current && current.expiresAt - 60_000 > now()) return current.token;
    pending ??= mint().finally(() => {
      pending = undefined;
    });
    current = await pending;
    return current.token;
  };
}

async function tokenResponse(response: Response, source: string) {
  if (!response.ok)
    throw new Error(
      `${source} token request failed with HTTP ${response.status}.`,
    );
  const body = (await response.json()) as {
    access_token?: unknown;
    expires_in?: unknown;
  };
  if (typeof body.access_token !== "string")
    throw new Error(`${source} token response had no access_token.`);
  return {
    token: body.access_token,
    expiresIn: typeof body.expires_in === "number" ? body.expires_in : 3600,
  };
}

export function metadataCredentials(
  fetcher: Fetch = fetch,
  now: () => number = Date.now,
): GoogleCredentials {
  const headers = { "Metadata-Flavor": "Google" };
  const token = cached(async () => {
    const { token, expiresIn } = await tokenResponse(
      await fetcher(
        `${METADATA}/instance/service-accounts/default/token?scopes=${encodeURIComponent(SCOPE)}`,
        { headers },
      ),
      "Metadata server",
    );
    return { token, expiresAt: now() + expiresIn * 1000 };
  }, now);
  return {
    token,
    async projectId() {
      const response = await fetcher(`${METADATA}/project/project-id`, {
        headers,
      });
      return response.ok ? (await response.text()).trim() : undefined;
    },
    async headers() {
      return {};
    },
  };
}

interface ServiceAccountKey {
  type: "service_account";
  client_email: string;
  private_key: string;
  project_id?: string;
  token_uri?: string;
}
interface AuthorizedUser {
  type: "authorized_user";
  client_id: string;
  client_secret: string;
  refresh_token: string;
  quota_project_id?: string;
}

export function fileCredentials(
  json: ServiceAccountKey | AuthorizedUser,
  fetcher: Fetch = fetch,
  now: () => number = Date.now,
): GoogleCredentials {
  if (json.type === "service_account") {
    const tokenUri = json.token_uri ?? TOKEN_URI;
    const token = cached(async () => {
      const issuedAt = Math.floor(now() / 1000);
      const assertion = await new SignJWT({ scope: SCOPE })
        .setProtectedHeader({ alg: "RS256", typ: "JWT" })
        .setIssuer(json.client_email)
        .setAudience(tokenUri)
        .setIssuedAt(issuedAt)
        .setExpirationTime(issuedAt + 3600)
        .sign(await importPKCS8(json.private_key, "RS256"));
      const minted = await tokenResponse(
        await fetcher(tokenUri, {
          method: "POST",
          headers: { "content-type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
            assertion,
          }),
        }),
        "Service account",
      );
      return {
        token: minted.token,
        expiresAt: now() + minted.expiresIn * 1000,
      };
    }, now);
    return {
      token,
      async projectId() {
        return json.project_id;
      },
      async headers() {
        return {};
      },
    };
  }
  if (json.type === "authorized_user") {
    const token = cached(async () => {
      const minted = await tokenResponse(
        await fetcher(TOKEN_URI, {
          method: "POST",
          headers: { "content-type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            grant_type: "refresh_token",
            client_id: json.client_id,
            client_secret: json.client_secret,
            refresh_token: json.refresh_token,
          }),
        }),
        "User credentials",
      );
      return {
        token: minted.token,
        expiresAt: now() + minted.expiresIn * 1000,
      };
    }, now);
    return {
      token,
      async projectId() {
        return json.quota_project_id;
      },
      async headers() {
        return json.quota_project_id
          ? { "x-goog-user-project": json.quota_project_id }
          : {};
      },
    };
  }
  throw new Error("Unsupported Application Default Credentials type.");
}

/**
 * GOOGLE_APPLICATION_CREDENTIALS, then gcloud's well-known ADC file, then the
 * metadata server (Cloud Run).
 */
export async function defaultCredentials(
  env: Record<string, string | undefined> = process.env,
  fetcher: Fetch = fetch,
): Promise<GoogleCredentials> {
  const candidates = [
    env.GOOGLE_APPLICATION_CREDENTIALS,
    join(
      env.CLOUDSDK_CONFIG ?? join(homedir(), ".config", "gcloud"),
      "application_default_credentials.json",
    ),
  ].filter((path): path is string => Boolean(path));
  for (const path of candidates) {
    let text: string;
    try {
      text = await readFile(path, "utf8");
    } catch (error) {
      if (path === env.GOOGLE_APPLICATION_CREDENTIALS)
        throw new Error("GOOGLE_APPLICATION_CREDENTIALS is not readable.", {
          cause: error,
        });
      continue;
    }
    return fileCredentials(JSON.parse(text), fetcher);
  }
  return metadataCredentials(fetcher);
}

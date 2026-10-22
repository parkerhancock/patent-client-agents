// Server-only: Google Cloud Storage downloads with V4 signed URLs, using fetch
// and the IAM Credentials signBlob API (no private key on Cloud Run).
import { createHash, randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import type { BlobObject, BlobStore, StoredBlob } from "./downloads.js";

const storageHost = "storage.googleapis.com";
const metadataBase =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default";
/** V4 signed URLs cannot outlive seven days. */
export const MAX_V4_TTL_SECONDS = 604800;

export interface GcsBlobStoreOptions {
  bucket: string;
  /** Object name prefix; Python writes under "downloads/". */
  prefix?: string;
  /** Signed URL lifetime; defaults to Python's 86400 seconds. */
  ttlSeconds?: number;
  /**
   * Service account that signs URLs through IAM signBlob. Defaults to the
   * metadata server's account on Cloud Run; required with user ADC.
   */
  signerEmail?: string;
  /** OAuth access token source; defaults to ADC file, then the metadata server. */
  accessToken?: () => Promise<string>;
  fetch?: typeof fetch;
  now?: () => Date;
  timeoutMs?: number;
  /** Environment for locating ADC; defaults to process.env. */
  env?: Record<string, string | undefined>;
}

/** Reads DOWNLOAD_* (or Python's LAW_TOOLS_CORE_* names); undefined without a bucket. */
export function gcsBlobStoreOptionsFromEnv(
  env: Record<string, string | undefined>,
): GcsBlobStoreOptions | undefined {
  const pick = (name: string) => {
    const value =
      env[`DOWNLOAD_${name}`] ??
      env[
        `LAW_TOOLS_CORE_${name === "BUCKET" ? "GCS_BUCKET" : `DOWNLOAD_${name}`}`
      ];
    return value?.trim() || undefined;
  };
  const bucket = pick("BUCKET");
  if (!bucket) return undefined;
  const ttl = pick("TTL_SECONDS");
  const prefix = env.DOWNLOAD_PREFIX?.trim();
  const signerEmail = env.DOWNLOAD_SIGNER_EMAIL?.trim();
  return {
    bucket,
    ...(ttl ? { ttlSeconds: Number(ttl) } : {}),
    ...(prefix !== undefined ? { prefix } : {}),
    ...(signerEmail ? { signerEmail } : {}),
  };
}

/** RFC 3986 encoding as V4 signing requires (unreserved characters kept). */
function encode(value: string): string {
  return encodeURIComponent(value).replace(
    /[!'()*]/g,
    (character) =>
      `%${character.charCodeAt(0).toString(16).toUpperCase().padStart(2, "0")}`,
  );
}

/** Quoted ASCII filename plus an RFC 5987 form when characters were replaced. */
export function contentDisposition(filename: string): string {
  const ascii = filename.replace(/[^\x20-\x7e]|["\\%]/g, "_") || "document";
  return ascii === filename
    ? `attachment; filename="${ascii}"`
    : `attachment; filename="${ascii}"; filename*=UTF-8''${encode(filename)}`;
}

function sha256Hex(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function timestamps(date: Date) {
  const stamp = date.toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "");
  return { stamp, day: stamp.slice(0, 8) };
}

/**
 * The V4 canonical request and string-to-sign for a GET on a path-style
 * object URL, per cloud.google.com/storage/docs/authentication/signatures.
 */
export function v4SigningParts(input: {
  bucket: string;
  objectName: string;
  signerEmail: string;
  date: Date;
  ttlSeconds: number;
}) {
  const { stamp, day } = timestamps(input.date);
  const scope = `${day}/auto/storage/goog4_request`;
  const path = `/${encode(input.bucket)}/${input.objectName.split("/").map(encode).join("/")}`;
  const query = [
    ["X-Goog-Algorithm", "GOOG4-RSA-SHA256"],
    ["X-Goog-Credential", `${input.signerEmail}/${scope}`],
    ["X-Goog-Date", stamp],
    ["X-Goog-Expires", String(input.ttlSeconds)],
    ["X-Goog-SignedHeaders", "host"],
  ]
    .map(
      ([key, value]) => `${encode(key as string)}=${encode(value as string)}`,
    )
    .join("&");
  const canonicalRequest = [
    "GET",
    path,
    query,
    `host:${storageHost}`,
    "",
    "host",
    "UNSIGNED-PAYLOAD",
  ].join("\n");
  const stringToSign = [
    "GOOG4-RSA-SHA256",
    stamp,
    scope,
    sha256Hex(canonicalRequest),
  ].join("\n");
  return { path, query, canonicalRequest, stringToSign };
}

async function googleError(response: Response): Promise<string> {
  const text = await response.text().catch(() => "");
  try {
    const message = (JSON.parse(text) as { error?: { message?: unknown } })
      .error?.message;
    if (typeof message === "string") return message.slice(0, 300);
  } catch {}
  return response.statusText || "no details";
}

export class GcsBlobStore implements BlobStore {
  readonly bucket: string;
  readonly prefix: string;
  readonly ttlSeconds: number;
  private readonly fetcher: typeof fetch;
  private readonly now: () => Date;
  private readonly timeoutMs: number;
  private readonly env: Record<string, string | undefined>;
  private readonly tokenSource: () => Promise<string>;
  private signer: Promise<string> | undefined;
  private cachedToken: { token: string; expires: number } | undefined;

  constructor(options: GcsBlobStoreOptions) {
    // Bucket names: 3-63 (or dotted up to 222) lowercase letters, digits, -, _, .
    if (!/^[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]$/.test(options.bucket))
      throw new Error("Invalid GCS bucket name.");
    this.bucket = options.bucket;
    const prefix = (options.prefix ?? "downloads").replace(/^\/+|\/+$/g, "");
    this.prefix = prefix ? `${prefix}/` : "";
    this.ttlSeconds = options.ttlSeconds ?? 86400;
    if (
      !Number.isSafeInteger(this.ttlSeconds) ||
      this.ttlSeconds < 1 ||
      this.ttlSeconds > MAX_V4_TTL_SECONDS
    )
      throw new Error(
        `GCS download TTL must be 1–${MAX_V4_TTL_SECONDS} seconds.`,
      );
    this.fetcher = options.fetch ?? fetch;
    this.now = options.now ?? (() => new Date());
    this.timeoutMs = options.timeoutMs ?? 30000;
    this.env = options.env ?? process.env;
    this.tokenSource = options.accessToken ?? (() => this.defaultToken());
    if (options.signerEmail) this.signer = Promise.resolve(options.signerEmail);
  }

  private request(url: string, init: RequestInit = {}) {
    return this.fetcher(url, {
      ...init,
      redirect: "error",
      signal: AbortSignal.timeout(this.timeoutMs),
    });
  }

  /** ADC order as google-auth: GOOGLE_APPLICATION_CREDENTIALS, gcloud's file, metadata server. */
  private async defaultToken(): Promise<string> {
    const cached = this.cachedToken;
    if (cached && cached.expires > Date.now()) return cached.token;
    const explicit = this.env.GOOGLE_APPLICATION_CREDENTIALS;
    const adcPath =
      explicit ||
      join(
        this.env.CLOUDSDK_CONFIG ?? join(homedir(), ".config", "gcloud"),
        "application_default_credentials.json",
      );
    let adc: Record<string, unknown> | undefined;
    try {
      adc = JSON.parse(await readFile(adcPath, "utf8"));
    } catch (error) {
      if (explicit)
        throw new Error(
          "GOOGLE_APPLICATION_CREDENTIALS does not point to readable JSON.",
          { cause: error },
        );
    }
    let body: Record<string, unknown>;
    if (adc) {
      if (adc.type !== "authorized_user")
        throw new Error(
          "Only user ADC (gcloud auth application-default login) or the metadata server are supported for GCS downloads.",
        );
      const response = await this.request(
        "https://oauth2.googleapis.com/token",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            grant_type: "refresh_token",
            client_id: String(adc.client_id),
            client_secret: String(adc.client_secret),
            refresh_token: String(adc.refresh_token),
          }),
        },
      );
      if (!response.ok)
        throw new Error(
          `Refreshing local ADC failed (HTTP ${response.status}); run gcloud auth application-default login.`,
        );
      body = (await response.json()) as Record<string, unknown>;
    } else {
      const response = await this.request(`${metadataBase}/token`, {
        headers: { "Metadata-Flavor": "Google" },
      }).catch((error: unknown) => {
        throw new Error(
          "No Google credentials: no ADC file and the metadata server is unreachable.",
          { cause: error },
        );
      });
      if (!response.ok || response.headers.get("metadata-flavor") !== "Google")
        throw new Error(
          `Metadata server token request failed (HTTP ${response.status}).`,
        );
      body = (await response.json()) as Record<string, unknown>;
    }
    const token = body.access_token;
    if (typeof token !== "string" || !token || /[\r\n]/.test(token))
      throw new Error("Google token response had no access token.");
    const lifetime = Number(body.expires_in) || 300;
    this.cachedToken = {
      token,
      expires: Date.now() + Math.max(lifetime - 60, 30) * 1000,
    };
    return token;
  }

  private signerEmail(): Promise<string> {
    this.signer ??= (async () => {
      const response = await this.request(`${metadataBase}/email`, {
        headers: { "Metadata-Flavor": "Google" },
      }).catch(() => undefined);
      const email = response?.ok ? (await response.text()).trim() : "";
      if (!/^[^\s@/]+@[^\s@/]+$/.test(email))
        throw new Error(
          "Set DOWNLOAD_SIGNER_EMAIL: no service account is available from the metadata server.",
        );
      return email;
    })().catch((error: unknown) => {
      this.signer = undefined;
      throw error;
    });
    return this.signer;
  }

  private async upload(object: BlobObject, name: string, token: string) {
    const boundary = `pca-${randomUUID()}`;
    const metadata = JSON.stringify({
      name,
      contentType: object.contentType,
      contentDisposition: contentDisposition(object.filename),
      cacheControl: "private, no-store",
    });
    const head = new TextEncoder().encode(
      `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${metadata}\r\n--${boundary}\r\nContent-Type: ${object.contentType}\r\n\r\n`,
    );
    const tail = new TextEncoder().encode(`\r\n--${boundary}--\r\n`);
    const body = new Uint8Array(
      head.byteLength + object.bytes.byteLength + tail.byteLength,
    );
    body.set(head, 0);
    body.set(object.bytes, head.byteLength);
    body.set(tail, head.byteLength + object.bytes.byteLength);
    // ifGenerationMatch=0 creates only, so storage.objects.create suffices.
    const response = await this.request(
      `https://${storageHost}/upload/storage/v1/b/${encode(this.bucket)}/o?uploadType=multipart&ifGenerationMatch=0`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": `multipart/related; boundary=${boundary}`,
        },
        body,
      },
    );
    if (!response.ok)
      throw new Error(
        `GCS upload to bucket ${this.bucket} failed (HTTP ${response.status}): ${await googleError(response)}`,
      );
    await response.body?.cancel();
  }

  private async signBlob(email: string, payload: string, token: string) {
    const response = await this.request(
      `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${encode(email)}:signBlob`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          payload: Buffer.from(payload, "utf8").toString("base64"),
        }),
      },
    );
    if (!response.ok)
      throw new Error(
        `IAM signBlob for ${email} failed (HTTP ${response.status}): ${await googleError(response)}${response.status === 403 ? ". The caller needs roles/iam.serviceAccountTokenCreator on that service account." : ""}`,
      );
    const signed = ((await response.json()) as { signedBlob?: unknown })
      .signedBlob;
    if (typeof signed !== "string" || !signed)
      throw new Error("IAM signBlob returned no signature.");
    return Buffer.from(signed, "base64").toString("hex");
  }

  /** The object name for a key, as Python's prefix + key. */
  objectName(key: string): string {
    return this.prefix + key.replace(/^\/+/, "");
  }

  async put(object: BlobObject): Promise<StoredBlob> {
    const name = this.objectName(
      `${randomUUID()}/${object.filename.replace(/[^\w.\- ]/g, "_").slice(0, 180) || "document"}`,
    );
    const token = await this.tokenSource();
    await this.upload(object, name, token);
    return this.sign(name, token);
  }

  /** A V4 signed GET URL for an existing object name. */
  async sign(objectName: string, token?: string): Promise<StoredBlob> {
    const signerEmail = await this.signerEmail();
    const date = this.now();
    const parts = v4SigningParts({
      bucket: this.bucket,
      objectName,
      signerEmail,
      date,
      ttlSeconds: this.ttlSeconds,
    });
    const signature = await this.signBlob(
      signerEmail,
      parts.stringToSign,
      token ?? (await this.tokenSource()),
    );
    return {
      url: `https://${storageHost}${parts.path}?${parts.query}&X-Goog-Signature=${signature}`,
      expiresAt: new Date(date.getTime() + this.ttlSeconds * 1000),
    };
  }
}

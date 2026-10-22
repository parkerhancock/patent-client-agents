import { randomToken } from "./crypto.js";
import type { GoogleCredentials } from "./google-auth.js";
import type { FetchLike } from "./http.js";
import type {
  BucketState,
  Clock,
  OAuthKind,
  OAuthStore,
  RateLimitStore,
  UsageRecord,
  UsageSink,
} from "./storage.js";

/**
 * Firestore over its REST API (v1), with conditional writes for atomic
 * take and read-modify-write. No Google SDK. Works against the emulator when
 * `emulatorHost` is set (FIRESTORE_EMULATOR_HOST).
 */
export const COLLECTION_PREFIX = "ts-mcp-";

type Value =
  | { nullValue: null }
  | { booleanValue: boolean }
  | { integerValue: string }
  | { doubleValue: number }
  | { stringValue: string }
  | { timestampValue: string }
  | { arrayValue: { values?: Value[] } }
  | { mapValue: { fields?: Record<string, Value> } };

export function encodeValue(value: unknown): Value {
  if (value === null || value === undefined) return { nullValue: null };
  if (typeof value === "boolean") return { booleanValue: value };
  if (typeof value === "number")
    return Number.isSafeInteger(value)
      ? { integerValue: String(value) }
      : { doubleValue: value };
  if (typeof value === "string") return { stringValue: value };
  if (value instanceof Date) return { timestampValue: value.toISOString() };
  if (Array.isArray(value))
    return { arrayValue: { values: value.map(encodeValue) } };
  if (typeof value === "object")
    return {
      mapValue: { fields: encodeFields(value as Record<string, unknown>) },
    };
  throw new TypeError(`Cannot store a ${typeof value} in Firestore.`);
}

export function encodeFields(record: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(record)
      .filter(([, value]) => value !== undefined)
      .map(([key, value]) => [key, encodeValue(value)]),
  );
}

export function decodeValue(value: Value): unknown {
  if ("nullValue" in value) return null;
  if ("booleanValue" in value) return value.booleanValue;
  if ("integerValue" in value) return Number(value.integerValue);
  if ("doubleValue" in value) return value.doubleValue;
  if ("stringValue" in value) return value.stringValue;
  if ("timestampValue" in value) return new Date(value.timestampValue);
  if ("arrayValue" in value)
    return (value.arrayValue.values ?? []).map(decodeValue);
  if ("mapValue" in value) return decodeFields(value.mapValue.fields ?? {});
  throw new TypeError("Unsupported Firestore value.");
}

export function decodeFields(fields: Record<string, Value>) {
  return Object.fromEntries(
    Object.entries(fields).map(([key, value]) => [key, decodeValue(value)]),
  );
}

export interface FirestoreDocument {
  fields: Record<string, unknown>;
  updateTime: string;
}

type Precondition = { exists: boolean } | { updateTime: string };
export type Write =
  | {
      update: { path: string; fields: Record<string, unknown> };
      currentDocument?: Precondition;
    }
  | { delete: string; currentDocument?: Precondition };

export class FirestoreConflict extends Error {
  override name = "FirestoreConflict";
}

export class FirestoreError extends Error {
  override name = "FirestoreError";
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export interface FirestoreOptions {
  projectId: string;
  database?: string;
  /** host:port of the emulator; requests go over plain HTTP with no credentials. */
  emulatorHost?: string;
  credentials?: GoogleCredentials;
  fetch?: FetchLike;
  /** Per-request deadline in milliseconds. */
  timeoutMs?: number;
}

export class FirestoreClient {
  private readonly root: string;
  private readonly base: string;
  private readonly fetcher: FetchLike;

  constructor(private readonly options: FirestoreOptions) {
    if (!options.emulatorHost && !options.credentials)
      throw new Error(
        "Firestore needs credentials unless the emulator is used.",
      );
    this.root = `projects/${options.projectId}/databases/${options.database ?? "(default)"}/documents`;
    this.base = options.emulatorHost
      ? `http://${options.emulatorHost}/v1`
      : "https://firestore.googleapis.com/v1";
    this.fetcher = options.fetch ?? fetch;
  }

  private async request(path: string, init: RequestInit = {}) {
    const headers = new Headers(init.headers);
    headers.set("content-type", "application/json");
    if (this.options.emulatorHost) headers.set("authorization", "Bearer owner");
    else if (this.options.credentials) {
      headers.set(
        "authorization",
        `Bearer ${await this.options.credentials.token()}`,
      );
      for (const [name, value] of Object.entries(
        await this.options.credentials.headers(),
      ))
        headers.set(name, value);
    }
    return this.fetcher(`${this.base}/${path}`, {
      ...init,
      headers,
      signal: AbortSignal.timeout(this.options.timeoutMs ?? 10_000),
    });
  }

  private name(path: string) {
    return `${this.root}/${path}`;
  }

  async get(path: string): Promise<FirestoreDocument | undefined> {
    const response = await this.request(this.name(path));
    if (response.status === 404) return undefined;
    if (!response.ok)
      throw new FirestoreError(
        `Firestore read failed with HTTP ${response.status}.`,
        response.status,
      );
    const body = (await response.json()) as {
      fields?: Record<string, Value>;
      updateTime: string;
    };
    return {
      fields: decodeFields(body.fields ?? {}),
      updateTime: body.updateTime,
    };
  }

  /** Apply writes atomically; a failed precondition raises FirestoreConflict. */
  async commit(writes: Write[]): Promise<void> {
    const response = await this.request(
      `projects/${this.options.projectId}/databases/${this.options.database ?? "(default)"}/documents:commit`,
      {
        method: "POST",
        body: JSON.stringify({
          writes: writes.map((write) =>
            "update" in write
              ? {
                  update: {
                    name: this.name(write.update.path),
                    fields: encodeFields(write.update.fields),
                  },
                  ...(write.currentDocument
                    ? { currentDocument: write.currentDocument }
                    : {}),
                }
              : {
                  delete: this.name(write.delete),
                  ...(write.currentDocument
                    ? { currentDocument: write.currentDocument }
                    : {}),
                },
          ),
        }),
      },
    );
    if (response.ok) return;
    let status = "";
    try {
      status =
        ((await response.json()) as { error?: { status?: string } }).error
          ?.status ?? "";
    } catch {}
    if (
      response.status === 409 ||
      [
        "FAILED_PRECONDITION",
        "ALREADY_EXISTS",
        "ABORTED",
        "NOT_FOUND",
      ].includes(status)
    )
      throw new FirestoreConflict("Firestore precondition failed.");
    throw new FirestoreError(
      `Firestore commit failed with HTTP ${response.status}.`,
      response.status,
    );
  }
}

/** OAuth records as `{ value: <map>, expires_at: <timestamp> }` in `ts-mcp-oauth-<kind>`. */
export class FirestoreOAuthStore implements OAuthStore {
  constructor(
    private readonly client: FirestoreClient,
    private readonly prefix = COLLECTION_PREFIX,
    private readonly now: Clock = Date.now,
  ) {}

  private path(kind: OAuthKind, id: string) {
    if (!/^[A-Za-z0-9_-]{1,512}$/.test(id))
      throw new Error("Invalid OAuth record id.");
    return `${this.prefix}oauth-${kind.replace("_", "-")}/${id}`;
  }

  private live(document: FirestoreDocument | undefined) {
    if (!document) return undefined;
    const expires = document.fields.expires_at;
    if (expires instanceof Date && expires.getTime() <= this.now())
      return undefined;
    return document;
  }

  async get<T>(kind: OAuthKind, id: string) {
    return this.live(await this.client.get(this.path(kind, id)))?.fields
      .value as T | undefined;
  }

  async put<T>(kind: OAuthKind, id: string, value: T, ttlSeconds?: number) {
    await this.client.commit([
      {
        update: {
          path: this.path(kind, id),
          fields: {
            value,
            ...(ttlSeconds !== undefined
              ? { expires_at: new Date(this.now() + ttlSeconds * 1000) }
              : {}),
          },
        },
      },
    ]);
  }

  async take<T>(kind: OAuthKind, id: string) {
    const path = this.path(kind, id);
    const document = await this.client.get(path);
    if (!document) return undefined;
    try {
      await this.client.commit([
        { delete: path, currentDocument: { updateTime: document.updateTime } },
      ]);
    } catch (error) {
      if (error instanceof FirestoreConflict) return undefined;
      throw error;
    }
    return this.live(document)?.fields.value as T | undefined;
  }

  async delete(kind: OAuthKind, id: string) {
    await this.client.commit([{ delete: this.path(kind, id) }]);
  }
}

/** One document per actor in `ts-mcp-rate-limits`, updated with optimistic concurrency. */
export class FirestoreRateLimitStore implements RateLimitStore {
  constructor(
    private readonly client: FirestoreClient,
    private readonly prefix = COLLECTION_PREFIX,
    private readonly attempts = 8,
  ) {}

  private path(actor: string) {
    return `${this.prefix}rate-limits/${actor}`;
  }

  async read(actor: string) {
    return (await this.client.get(this.path(actor)))?.fields as
      | BucketState
      | undefined;
  }

  async update(
    actor: string,
    change: (current: BucketState | undefined) => BucketState,
  ) {
    const path = this.path(actor);
    for (let attempt = 1; ; attempt++) {
      const document = await this.client.get(path);
      const next = change(document?.fields as BucketState | undefined);
      try {
        await this.client.commit([
          {
            update: { path, fields: next as Record<string, unknown> },
            currentDocument: document
              ? { updateTime: document.updateTime }
              : { exists: false },
          },
        ]);
        return;
      } catch (error) {
        if (!(error instanceof FirestoreConflict) || attempt >= this.attempts)
          throw error;
        await Bun.sleep(Math.random() * 20 * attempt);
      }
    }
  }
}

/** One document per tool call in `ts-mcp-usage`. */
export class FirestoreUsageSink implements UsageSink {
  constructor(
    private readonly client: FirestoreClient,
    private readonly prefix = COLLECTION_PREFIX,
  ) {}

  async record(entry: UsageRecord) {
    await this.client.commit([
      {
        update: {
          path: `${this.prefix}usage/${randomToken()}`,
          fields: { ...entry },
        },
        currentDocument: { exists: false },
      },
    ]);
  }
}

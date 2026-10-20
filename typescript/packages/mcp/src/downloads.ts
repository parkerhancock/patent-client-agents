import { AsyncLocalStorage } from "node:async_hooks";
import {
  createHmac,
  randomBytes,
  randomUUID,
  timingSafeEqual,
} from "node:crypto";
import { mkdtemp, readFile, rmdir, unlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Provenance } from "@patent-client-agents/client";

export interface DownloadOptions {
  /** Externally reachable server origin, including an optional deployment prefix. */
  publicBaseUrl?: string;
  mode?: "authenticated" | "signed";
  ttlSeconds?: number;
  maxBytes?: number;
}
interface Artifact {
  owner?: string;
  path: string;
  filename: string;
  contentType: string;
  size: number;
  expires: number;
}

/** Per-server temporary artifacts. Restart invalidates URLs; callers can request a fresh one. */
export class DownloadStore {
  readonly mode: "authenticated" | "signed";
  private readonly key = randomBytes(32);
  private readonly artifacts = new Map<string, Artifact>();
  private directory?: Promise<string>;
  private readonly baseUrl?: string;
  private readonly ttl: number;
  private readonly maxBytes: number;
  private usedBytes = 0;
  private closed = false;
  private pending: Promise<void> = Promise.resolve();
  private closing: Promise<void> | undefined;
  private cleanupTimer?: ReturnType<typeof setInterval>;
  private readonly createdFiles = new Set<string>();
  constructor(options: DownloadOptions = {}) {
    if (options.publicBaseUrl) {
      const url = new URL(options.publicBaseUrl);
      if (
        url.username ||
        url.password ||
        url.search ||
        url.hash ||
        (url.protocol !== "https:" &&
          !(
            url.protocol === "http:" &&
            ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
          ))
      )
        throw new Error(
          "Download base URL must use HTTPS without credentials or query parameters.",
        );
      this.baseUrl = url.href.replace(/\/$/, "");
    }
    this.mode = options.mode ?? "authenticated";
    this.ttl = options.ttlSeconds ?? 900;
    this.maxBytes = options.maxBytes ?? 256 * 1024 * 1024;
    if (!Number.isSafeInteger(this.ttl) || this.ttl < 1 || this.ttl > 86400)
      throw new Error("Download TTL must be 1–86400 seconds.");
    if (!Number.isSafeInteger(this.maxBytes) || this.maxBytes < 1)
      throw new Error("Download cache capacity must be positive.");
  }
  private signature(id: string, expires: number) {
    return createHmac("sha256", this.key)
      .update(`${id}\n${expires}`)
      .digest("hex");
  }
  private exclusive<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.pending.then(operation);
    this.pending = result.then(
      () => {},
      () => {},
    );
    return result;
  }
  private startCleanup() {
    if (this.cleanupTimer || this.closed) return;
    this.cleanupTimer = setInterval(
      () => {
        void this.exclusive(() => this.prune()).catch(() => {
          // Filesystem errors can contain local paths; keep background logs generic.
          console.warn(
            "Temporary download cleanup failed; explicit close() can retry.",
          );
        });
      },
      Math.min(this.ttl * 1000, 60_000),
    );
    this.cleanupTimer.unref();
  }
  private async removeCreatedFile(path: string) {
    await unlink(path).catch((error: NodeJS.ErrnoException) => {
      if (error.code !== "ENOENT") throw error;
    });
    this.createdFiles.delete(path);
  }
  private async prune() {
    const now = Math.floor(Date.now() / 1000);
    for (const [id, artifact] of this.artifacts) {
      if (artifact.expires > now) continue;
      await this.removeCreatedFile(artifact.path);
      this.artifacts.delete(id);
      this.usedBytes -= artifact.size;
    }
  }
  /** Wait for accepted writes, then remove only this store's files and empty directory. */
  close(): Promise<void> {
    if (this.closing) return this.closing;
    this.closed = true;
    if (this.cleanupTimer) clearInterval(this.cleanupTimer);
    this.closing = this.exclusive(async () => {
      for (const path of this.createdFiles) await this.removeCreatedFile(path);
      this.artifacts.clear();
      this.usedBytes = 0;
      if (this.directory)
        await rmdir(await this.directory).catch(
          (error: NodeJS.ErrnoException) => {
            if (error.code !== "ENOENT") throw error;
          },
        );
    }).catch((error: unknown) => {
      this.closing = undefined;
      throw error;
    });
    return this.closing;
  }
  put(
    bytes: Uint8Array,
    name: string,
    mime: string,
    provenance: Provenance,
    owner?: string,
  ) {
    if (this.closed)
      return Promise.reject(new Error("Download store is closed."));
    return this.exclusive(() =>
      this.putArtifact(bytes, name, mime, provenance, owner),
    );
  }
  private async putArtifact(
    bytes: Uint8Array,
    name: string,
    mime: string,
    provenance: Provenance,
    owner?: string,
  ) {
    if (this.baseUrl && this.mode === "authenticated" && !owner)
      throw new Error(
        "Authenticated downloads require a verified caller identity.",
      );
    await this.prune();
    if (!bytes.byteLength) throw new Error("Cannot publish an empty document.");
    if (bytes.byteLength > this.maxBytes - this.usedBytes)
      throw new Error("Document download cache capacity exceeded.");
    const filename =
      name.replace(/[^\w.\- ]/g, "_").slice(0, 180) || "document";
    const contentType = mime.split(";")[0]?.trim().toLowerCase() ?? "";
    if (!/^[\w.+-]+\/[\w.+-]+$/.test(contentType))
      throw new Error("Invalid download content type.");
    // Reserve before awaiting filesystem I/O so concurrent downloads cannot exceed the cap.
    this.usedBytes += bytes.byteLength;
    const id = randomUUID();
    const expires = Math.floor(Date.now() / 1000) + this.ttl;
    let createdPath: string | undefined;
    try {
      this.directory ??= mkdtemp(join(tmpdir(), "pca-downloads-"));
      const path = join(await this.directory, id);
      createdPath = path;
      this.createdFiles.add(path);
      await writeFile(path, bytes, { mode: 0o600, flag: "wx" });
      this.artifacts.set(id, {
        path,
        filename,
        contentType,
        size: bytes.byteLength,
        expires,
        ...(owner ? { owner } : {}),
      });
      this.startCleanup();
      const common = {
        filename,
        content_type: contentType,
        size: bytes.byteLength,
        expires_at: new Date(expires * 1000).toISOString(),
        provenance: { ...provenance, connector_version: "0.1.0" as const },
      };
      return this.baseUrl
        ? {
            ...common,
            download_url: `${this.baseUrl}/downloads?id=${id}${this.mode === "signed" ? `&expires=${expires}&signature=${this.signature(id, expires)}` : ""}`,
            expires_at: new Date(expires * 1000).toISOString(),
          }
        : { ...common, file_path: path };
    } catch (error) {
      this.usedBytes -= bytes.byteLength;
      if (createdPath)
        await this.removeCreatedFile(createdPath).catch(() => {
          console.warn(
            "Temporary download cleanup failed; explicit close() can retry.",
          );
        });
      throw error;
    }
  }
  async handle(request: Request, owner?: string): Promise<Response> {
    const headers = {
      "Cache-Control": "private, no-store",
      "Referrer-Policy": "no-referrer",
      "X-Content-Type-Options": "nosniff",
    };
    if (request.method !== "GET" && request.method !== "HEAD")
      return new Response("Method not allowed", {
        status: 405,
        headers: { ...headers, Allow: "GET, HEAD" },
      });
    const query = new URL(request.url).searchParams;
    const id = query.get("id") ?? "";
    const expiresText = query.get("expires") ?? "";
    const signature = query.get("signature") ?? "";
    const expires = Number(expiresText);
    if (
      this.mode === "signed" &&
      (!/^[0-9a-f-]{36}$/.test(id) ||
        !/^\d{1,12}$/.test(expiresText) ||
        !/^[a-f0-9]{64}$/.test(signature) ||
        expires <= Math.floor(Date.now() / 1000) ||
        !timingSafeEqual(
          Buffer.from(signature, "hex"),
          Buffer.from(this.signature(id, expires), "hex"),
        ))
    )
      return new Response("Invalid or expired download link", {
        status: 403,
        headers,
      });
    const artifact = this.closed ? undefined : this.artifacts.get(id);
    if (
      !artifact ||
      artifact.expires <= Math.floor(Date.now() / 1000) ||
      (this.mode === "signed"
        ? artifact.expires !== expires
        : !owner || artifact.owner !== owner)
    )
      return new Response("Document no longer available", {
        status: 404,
        headers,
      });
    return new Response(
      request.method === "HEAD" ? null : await readFile(artifact.path),
      {
        headers: {
          ...headers,
          "Content-Type": artifact.contentType,
          "Content-Length": String(artifact.size),
          "Content-Disposition": `attachment; filename="${artifact.filename}"`,
        },
      },
    );
  }
}
export const downloadContext = new AsyncLocalStorage<{
  store: DownloadStore;
  owner?: string;
}>();
let localStore: DownloadStore | undefined;
export function downloadResult(
  bytes: Uint8Array,
  name: string,
  mime: string,
  provenance: Provenance,
) {
  const context = downloadContext.getStore();
  if (!context && !localStore) localStore = new DownloadStore();
  const store = context?.store ?? localStore;
  if (!store) throw new Error("Download store is unavailable.");
  return store.put(bytes, name, mime, provenance, context?.owner);
}

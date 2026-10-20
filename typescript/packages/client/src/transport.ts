import ky, { HTTPError } from "ky";
import { z } from "zod";
import type { Provenance } from "./models.js";

export class ConfigurationError extends Error {
  override name = "ConfigurationError";
}
export class ApiError extends Error {
  override name = "ApiError";
  constructor(
    message: string,
    public readonly status: number,
    public readonly code = "HTTP_ERROR",
  ) {
    super(message);
  }
}
export class OdpApiError extends ApiError {
  override name = "OdpApiError";
}
export interface ClientOptions {
  apiKey?: string;
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
  /** Total per-request budget, including retries and reading the body. */
  timeoutMs?: number;
  /** Retries after the first attempt; defaults to three. */
  retryLimit?: number;
  /** Maximum decoded response bytes buffered by one request. Defaults to 64 MiB. */
  maxResponseBytes?: number;
}
export interface HttpTransportOptions extends Omit<ClientOptions, "apiKey"> {
  baseUrl: string;
  sourceName: string;
  headers?: HeadersInit;
}
export interface TransportRequestOptions {
  maxBytes?: number;
  body?: unknown;
  rawBody?: BodyInit;
  form?: Record<string, string>;
  headers?: HeadersInit;
  searchParams?:
    | URLSearchParams
    | Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
  emptyOn404?: Record<string, unknown>;
  timeoutMs?: number;
  /** Exact HTTPS hostnames approved by the connector for public downloads. */
  allowedHosts?: string[];
}
export interface TransportResult<T> {
  data: T;
  provenance: Provenance;
  headers: Headers;
  status: number;
}
export type JsonResult = TransportResult<unknown>;

function secureUrl(url: URL) {
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (
    url.username ||
    url.password ||
    url.hash ||
    (url.protocol !== "https:" && !(local && url.protocol === "http:"))
  ) {
    throw new ConfigurationError(
      "Requests require HTTPS without embedded credentials, except local test servers.",
    );
  }
}

/** Read-only HTTP requests. Cross-origin downloads never inherit service credentials. */
export class GenericHttpTransport {
  private readonly http;
  private readonly baseUrl: URL;
  private readonly timeoutMs: number;
  private readonly headers: Headers;
  private readonly maxResponseBytes: number;
  private readonly sourceName: string;
  constructor(options: HttpTransportOptions) {
    this.baseUrl = new URL(options.baseUrl);
    secureUrl(this.baseUrl);
    if (this.baseUrl.search)
      throw new ConfigurationError("baseUrl must not contain a query.");
    this.sourceName = options.sourceName;
    this.maxResponseBytes = z
      .number()
      .int()
      .positive()
      .safe()
      .parse(options.maxResponseBytes ?? 64 * 1024 * 1024);
    this.headers = new Headers(options.headers);
    if (!this.headers.has("accept"))
      this.headers.set("accept", "application/json");
    this.timeoutMs = z
      .number()
      .int()
      .positive()
      .max(2_147_483_647)
      .parse(options.timeoutMs ?? 30_000);
    const retryLimit = z
      .number()
      .int()
      .min(0)
      .max(10)
      .parse(options.retryLimit ?? 3);
    this.http = ky.create({
      redirect: "manual",
      throwHttpErrors: (status) => status >= 400,
      timeout: this.timeoutMs,
      totalTimeout: this.timeoutMs,
      retry: {
        limit: retryLimit,
        methods: ["get", "post"],
        statusCodes: [408, 429, 500, 502, 503, 504],
        maxRetryAfter: this.timeoutMs,
        jitter: true,
      },
      fetch: options.fetch ?? ((input, init) => globalThis.fetch(input, init)),
    });
  }
  json(
    method: "GET" | "POST",
    path: string,
    options: TransportRequestOptions = {},
  ): Promise<JsonResult> {
    return this.request(method, path, "json", options);
  }
  text(
    method: "GET" | "POST",
    path: string,
    options: TransportRequestOptions = {},
  ): Promise<TransportResult<string>> {
    return this.request(method, path, "text", options) as Promise<
      TransportResult<string>
    >;
  }
  bytes(
    method: "GET" | "POST",
    path: string,
    options: TransportRequestOptions = {},
  ): Promise<TransportResult<Uint8Array>> {
    return this.request(method, path, "bytes", options) as Promise<
      TransportResult<Uint8Array>
    >;
  }
  private error(
    message: string,
    status: number,
    code = "HTTP_ERROR",
  ): ApiError {
    return this.sourceName === "USPTO Open Data Portal"
      ? new OdpApiError(message, status, code)
      : new ApiError(message, status, code);
  }
  private async request(
    method: "GET" | "POST",
    path: string,
    mode: "json" | "text" | "bytes",
    options: TransportRequestOptions,
  ): Promise<TransportResult<unknown>> {
    let url = new URL(path, this.baseUrl);
    secureUrl(url);
    const allowed = (candidate: URL) =>
      candidate.origin === this.baseUrl.origin ||
      (candidate.protocol === "https:" &&
        !candidate.port &&
        options.allowedHosts?.includes(candidate.hostname));
    if (!allowed(url))
      throw new ConfigurationError(
        "URL must use the configured origin or an explicitly approved HTTPS download host.",
      );
    if (
      [
        options.body !== undefined,
        options.rawBody !== undefined,
        options.form !== undefined,
      ].filter(Boolean).length > 1
    )
      throw new ConfigurationError("Supply only one request body format.");
    if (options.searchParams) {
      const params =
        options.searchParams instanceof URLSearchParams
          ? options.searchParams
          : new URLSearchParams(
              Object.entries(options.searchParams)
                .filter(([, v]) => v !== undefined)
                .map(([k, v]) => [k, String(v)]),
            );
      for (const [key, value] of params) url.searchParams.append(key, value);
    }
    const budget = z
      .number()
      .int()
      .positive()
      .max(2_147_483_647)
      .parse(options.timeoutMs ?? this.timeoutMs);
    const maxBytes = z
      .number()
      .int()
      .positive()
      .safe()
      .parse(options.maxBytes ?? this.maxResponseBytes);
    const deadline = AbortSignal.timeout(budget);
    const signal = options.signal
      ? AbortSignal.any([options.signal, deadline])
      : deadline;
    const sourceUrl = new URL(url);
    for (const key of [...sourceUrl.searchParams.keys()]) {
      if (
        /^(?:api[-_]?key|key|token|access_token|authorization|signature|expires|key-pair-id|x-amz-.+)$/i.test(
          key,
        )
      )
        sourceUrl.searchParams.delete(key);
    }
    const provenance = (): Provenance => ({
      source_url: sourceUrl.href,
      source_name: this.sourceName,
      retrieved_at: new Date().toISOString(),
      cache_hit: false,
    });
    try {
      for (let redirects = 0; redirects <= 5; redirects++) {
        const sameOrigin = url.origin === this.baseUrl.origin;
        const headers = sameOrigin
          ? new Headers(this.headers)
          : new Headers({ accept: "*/*" });
        if (sameOrigin)
          new Headers(options.headers).forEach((value, key) => {
            headers.set(key, value);
          });
        const response = await this.http(url, {
          method,
          signal,
          headers,
          timeout: budget,
          totalTimeout: budget,
          ...(options.body === undefined ? {} : { json: options.body }),
          ...(options.form ? { body: new URLSearchParams(options.form) } : {}),
          ...(options.rawBody === undefined ? {} : { body: options.rawBody }),
        });
        if (response.status >= 300 && response.status < 400) {
          const location = response.headers.get("location");
          if (
            !options.allowedHosts ||
            !location ||
            method !== "GET" ||
            redirects === 5
          )
            throw this.error(
              `${this.sourceName} redirect rejected.`,
              0,
              "NETWORK_ERROR",
            );
          const next = new URL(location, url);
          secureUrl(next);
          if (!allowed(next))
            throw this.error(
              `${this.sourceName} redirect host rejected.`,
              0,
              "NETWORK_ERROR",
            );
          url = next;
          continue;
        }
        const declaredLength = Number(response.headers.get("content-length"));
        if (declaredLength > maxBytes) {
          await response.body?.cancel();
          throw this.error(
            `${this.sourceName} response exceeds the configured size limit.`,
            response.status,
            "RESPONSE_TOO_LARGE",
          );
        }
        const reader = response.body?.getReader();
        const chunks: Uint8Array[] = [];
        let length = 0;
        if (reader) {
          try {
            for (;;) {
              const chunk = await reader.read();
              if (chunk.done) break;
              length += chunk.value.byteLength;
              if (length > maxBytes) {
                await reader.cancel();
                throw this.error(
                  `${this.sourceName} response exceeds the configured size limit.`,
                  response.status,
                  "RESPONSE_TOO_LARGE",
                );
              }
              chunks.push(chunk.value);
            }
          } finally {
            reader.releaseLock();
          }
        }
        const bytes = new Uint8Array(length);
        let position = 0;
        for (const chunk of chunks) {
          bytes.set(chunk, position);
          position += chunk.byteLength;
        }
        const text =
          mode === "bytes" ? undefined : new TextDecoder().decode(bytes);
        const data: unknown =
          mode === "bytes"
            ? bytes
            : mode === "text"
              ? text
              : JSON.parse(text ?? "");
        return {
          data,
          provenance: provenance(),
          headers: response.headers,
          status: response.status,
        };
      }
      throw this.error("Too many redirects.", 0, "NETWORK_ERROR");
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error instanceof HTTPError) {
        if (
          error.response.status === 404 &&
          options.emptyOn404 &&
          mode === "json"
        )
          return {
            data: options.emptyOn404,
            provenance: provenance(),
            headers: error.response.headers,
            status: 404,
          };
        throw this.error(
          `${this.sourceName} returned HTTP ${error.response.status}.`,
          error.response.status,
        );
      }
      if (options.signal?.aborted)
        throw this.error(
          `${this.sourceName} request was cancelled.`,
          0,
          "ABORTED",
        );
      if (
        deadline.aborted ||
        (error instanceof Error && error.name === "TimeoutError")
      )
        throw this.error(
          `${this.sourceName} request exceeded its time budget.`,
          0,
          "TIMEOUT",
        );
      if (error instanceof SyntaxError)
        throw this.error(
          `${this.sourceName} returned invalid JSON.`,
          200,
          "INVALID_RESPONSE",
        );
      throw this.error(
        `${this.sourceName} request failed.`,
        0,
        "NETWORK_ERROR",
      );
    }
  }
}
export class OdpTransport extends GenericHttpTransport {
  constructor(options: ClientOptions = {}) {
    const apiKey = options.apiKey || process.env.USPTO_ODP_API_KEY;
    if (!apiKey?.trim())
      throw new ConfigurationError(
        "Set USPTO_ODP_API_KEY or pass apiKey to use USPTO ODP.",
      );
    super({
      ...options,
      baseUrl: options.baseUrl ?? "https://api.uspto.gov",
      sourceName: "USPTO Open Data Portal",
      headers: { "X-API-KEY": apiKey },
    });
  }
}

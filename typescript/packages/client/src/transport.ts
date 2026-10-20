import ky, { HTTPError } from "ky";
import { z } from "zod";
import type { Provenance } from "./models.js";

export class ConfigurationError extends Error {
  override name = "ConfigurationError";
}

export class OdpApiError extends Error {
  override name = "OdpApiError";
  constructor(
    message: string,
    public readonly status: number,
    public readonly code = "HTTP_ERROR",
  ) {
    super(message);
  }
}

export interface ClientOptions {
  apiKey?: string;
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
  /** Total per-request budget, including retries and reading the body. */
  timeoutMs?: number;
  /** Retries after the first attempt; defaults to three (four attempts total). */
  retryLimit?: number;
}

export interface JsonResult {
  data: unknown;
  provenance: Provenance;
}

export class OdpTransport {
  private readonly http;
  private readonly baseUrl: URL;
  private readonly timeoutMs: number;

  constructor(options: ClientOptions = {}) {
    const apiKey = options.apiKey || process.env.USPTO_ODP_API_KEY;
    if (!apiKey?.trim()) {
      throw new ConfigurationError(
        "Set USPTO_ODP_API_KEY or pass apiKey to use USPTO ODP.",
      );
    }
    this.baseUrl = new URL(options.baseUrl ?? "https://api.uspto.gov");
    if (
      this.baseUrl.username ||
      this.baseUrl.password ||
      this.baseUrl.search ||
      this.baseUrl.hash
    ) {
      throw new ConfigurationError(
        "baseUrl must not contain credentials, a query, or a fragment.",
      );
    }
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(
      this.baseUrl.hostname,
    );
    if (
      this.baseUrl.protocol !== "https:" &&
      !(local && this.baseUrl.protocol === "http:")
    ) {
      throw new ConfigurationError(
        "ODP requests require HTTPS, except local test servers.",
      );
    }
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
      headers: { "X-API-KEY": apiKey, Accept: "application/json" },
      redirect: "error",
      timeout: this.timeoutMs,
      totalTimeout: this.timeoutMs,
      retry: {
        limit: retryLimit,
        // This transport is private to read-only ODP application methods.
        methods: ["get", "post"],
        statusCodes: [408, 429, 500, 502, 503, 504],
        maxRetryAfter: this.timeoutMs,
        jitter: true,
      },
      fetch: options.fetch ?? ((input, init) => globalThis.fetch(input, init)),
    });
  }

  async json(
    method: "GET" | "POST",
    path: string,
    options: {
      body?: unknown;
      signal?: AbortSignal;
      emptyOn404?: Record<string, unknown>;
    } = {},
  ): Promise<JsonResult> {
    const url = new URL(path, this.baseUrl);
    if (url.origin !== this.baseUrl.origin)
      throw new ConfigurationError("ODP URL must use the configured origin.");
    const deadline = AbortSignal.timeout(this.timeoutMs);
    const signal = options.signal
      ? AbortSignal.any([options.signal, deadline])
      : deadline;
    try {
      const response = await this.http(url, {
        method,
        signal,
        ...(options.body === undefined ? {} : { json: options.body }),
      });
      const provenance = this.provenance(url, new Date().toISOString());
      const data: unknown = await response.json();
      return { data, provenance };
    } catch (error) {
      if (error instanceof HTTPError) {
        const provenance = this.provenance(url, new Date().toISOString());
        if (error.response.status === 404 && options.emptyOn404) {
          return { data: options.emptyOn404, provenance };
        }
        throw new OdpApiError(
          `USPTO ODP returned HTTP ${error.response.status}.`,
          error.response.status,
        );
      }
      if (options.signal?.aborted)
        throw new OdpApiError("USPTO ODP request was cancelled.", 0, "ABORTED");
      if (
        deadline.aborted ||
        (error instanceof Error && error.name === "TimeoutError")
      ) {
        throw new OdpApiError(
          "USPTO ODP request exceeded its time budget.",
          0,
          "TIMEOUT",
        );
      }
      if (error instanceof SyntaxError)
        throw new OdpApiError(
          "USPTO ODP returned invalid JSON.",
          200,
          "INVALID_RESPONSE",
        );
      // Ky errors can hold a Request with credentials; never expose them as causes.
      throw new OdpApiError("USPTO ODP request failed.", 0, "NETWORK_ERROR");
    }
  }

  private provenance(url: URL, retrievedAt: string): Provenance {
    return {
      source_url: url.href,
      source_name: "USPTO Open Data Portal",
      retrieved_at: retrievedAt,
      cache_hit: false,
    };
  }
}

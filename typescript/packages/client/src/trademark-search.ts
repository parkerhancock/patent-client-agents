import { z } from "zod";
import {
  ApiError,
  type ClientOptions,
  ConfigurationError,
  GenericHttpTransport,
} from "./transport.js";
export const WAF_USER_AGENT =
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
export interface WafToken {
  token: string;
  expires: number;
  userAgent?: string;
}
/** A trusted deployment adapter; browser acquisition stays outside this library. */
export interface WafTokenProvider {
  load(options: {
    forceRefresh: boolean;
    rejectedToken?: WafToken;
  }): Promise<WafToken>;
}
export interface TrademarkSearchOptions {
  wordmark?: string;
  owner?: string;
  goodsServices?: string;
  serialNumber?: string;
  registrationNumber?: string;
  liveOnly?: boolean;
  status?: "live" | "dead" | "all";
  size?: number;
  from?: number;
  signal?: AbortSignal;
}
export interface TrademarkSearchClientOptions
  extends Omit<ClientOptions, "apiKey"> {
  token?: WafToken;
  userAgent?: string;
  refreshToken?: () => Promise<WafToken>;
  sessionProvider?: WafTokenProvider;
}
export interface TrademarkSearchResult extends Record<string, unknown> {
  serial_number: string;
  registration_number: string | null;
  wordmark: string | null;
  status_live: boolean;
  is_live: boolean;
  is_registered: boolean;
  primary_owner: string | null;
}
function normalize(
  d: Record<string, unknown>,
  id: unknown,
): TrademarkSearchResult {
  const result: Record<string, unknown> = {};
  const arrays = new Set([
    "ownerName",
    "goodsAndServices",
    "currentBasis",
    "internationalClass",
    "usClass",
    "designCode",
    "designCodeDescription",
    "markDescription",
  ]);
  for (const [key, value] of Object.entries(d)) {
    const name = key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
    result[name] = arrays.has(key)
      ? value == null
        ? null
        : Array.isArray(value)
          ? value
          : String(value)
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean)
      : value;
  }
  for (const name of [
    "filed_date",
    "registration_date",
    "abandon_date",
    "cancel_date",
  ]) {
    const raw = result[name];
    result[name] =
      raw != null && !Number.isNaN(new Date(String(raw)).valueOf())
        ? new Date(String(raw)).toISOString()
        : null;
  }
  const serial = d.serialNumber ?? id;
  if (serial == null || typeof d.alive !== "boolean")
    throw new ApiError(
      "Trademark Search returned a malformed result.",
      200,
      "INVALID_RESPONSE",
    );
  return {
    ...result,
    serial_number: String(serial),
    registration_number:
      d.registrationNumber == null ? null : String(d.registrationNumber),
    wordmark: d.wordmark == null ? null : String(d.wordmark),
    status_live: d.alive,
    is_live: d.alive,
    is_registered: d.registrationNumber != null && result.cancel_date === null,
    primary_owner: (result.owner_name as string[] | null)?.[0] ?? null,
    assignment_recorded: d.assignmentRecorded ?? false,
  };
}
/** Requires an externally supplied AWS WAF token and its matching browser User-Agent.
 * An injected fetch may supply a browser-compatible session; native fetch TLS acceptance is not guaranteed.
 */
export class TrademarkSearchClient {
  private readonly transport: GenericHttpTransport;
  private token: WafToken | undefined;
  private readonly options: TrademarkSearchClientOptions;
  private refreshing: Promise<WafToken> | undefined;
  constructor(options: TrademarkSearchClientOptions = {}) {
    this.options = options;
    this.token = options.token;
    this.transport = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://tmsearch.uspto.gov",
      sourceName: "USPTO Trademark Search",
      headers: {
        Accept: "application/json, text/plain, */*",
        Origin: "https://tmsearch.uspto.gov",
        Referer: "https://tmsearch.uspto.gov/",
        "Accept-Language": "en-US,en;q=0.9",
      },
    });
  }
  private async getToken(
    force = false,
    rejectedToken?: WafToken,
  ): Promise<WafToken> {
    if (this.options.sessionProvider) {
      let candidate: WafToken;
      try {
        candidate = await this.options.sessionProvider.load({
          forceRefresh: force,
          ...(rejectedToken ? { rejectedToken } : {}),
        });
      } catch {
        throw new ConfigurationError(
          "The trusted WAF session provider failed.",
        );
      }
      this.validateToken(candidate);
      this.token = candidate;
      return candidate;
    }
    if (!this.token && !force) {
      const raw =
        process.env.PCA_WAF_TOKEN_JSON ?? process.env.LAW_TOOLS_WAF_TOKEN_JSON;
      if (raw)
        try {
          this.token = JSON.parse(raw) as WafToken;
        } catch {
          throw new ConfigurationError(
            "PCA_WAF_TOKEN_JSON is not valid token JSON.",
          );
        }
    }
    const nearExpiry =
      !this.token ||
      !Number.isFinite(this.token.expires) ||
      this.token.expires * 1000 <= Date.now() + 6 * 3600000;
    if ((force || nearExpiry) && this.options.refreshToken) {
      this.refreshing ??= Promise.resolve()
        .then(() => this.options.refreshToken?.())
        .then((token) => {
          if (!token) throw new Error("No token returned");
          this.token = token;
          return token;
        })
        .catch(() => {
          throw new ConfigurationError(
            "The external WAF session refresh failed.",
          );
        });
      const refreshing = this.refreshing;
      try {
        await refreshing;
      } finally {
        if (this.refreshing === refreshing) this.refreshing = undefined;
      }
    } else if (force)
      throw new ApiError(
        "Trademark Search rejected the session; provide a refreshed external WAF token.",
        403,
        "AUTHENTICATION",
      );
    this.validateToken(this.token);
    return this.token;
  }
  private validateToken(token: unknown): asserts token is WafToken {
    if (
      !token ||
      typeof token !== "object" ||
      !("token" in token) ||
      typeof token.token !== "string" ||
      !token.token.trim() ||
      /[\r\n;]/.test(token.token) ||
      !("expires" in token) ||
      typeof token.expires !== "number" ||
      !Number.isFinite(token.expires) ||
      token.expires * 1000 <= Date.now() ||
      ("userAgent" in token &&
        (typeof token.userAgent !== "string" ||
          !token.userAgent.trim() ||
          /[^\x20-\x7e]/.test(token.userAgent)))
    )
      throw new ConfigurationError(
        "Supply a current externally minted WAF token with its matching User-Agent, or a refreshToken callback.",
      );
  }
  private userAgent(token: WafToken): string {
    return this.options.sessionProvider
      ? (token.userAgent ?? WAF_USER_AGENT)
      : (this.options.userAgent ?? token.userAgent ?? WAF_USER_AGENT);
  }
  private requestToken(
    force: boolean,
    signal?: AbortSignal,
    rejectedToken?: WafToken,
  ): Promise<WafToken> {
    if (signal?.aborted)
      return Promise.reject(
        new ApiError("Trademark Search request was cancelled.", 0, "ABORTED"),
      );
    const work = this.getToken(force, rejectedToken).then((token) => {
      if (
        rejectedToken &&
        token.token === rejectedToken.token &&
        this.userAgent(token) === this.userAgent(rejectedToken)
      )
        throw new ApiError(
          "The WAF session provider returned the rejected session unchanged.",
          403,
          "AUTHENTICATION",
        );
      return token;
    });
    if (!signal) return work;
    return new Promise((resolve, reject) => {
      const abort = () =>
        reject(
          new ApiError("Trademark Search request was cancelled.", 0, "ABORTED"),
        );
      signal.addEventListener("abort", abort, { once: true });
      if (signal.aborted) abort();
      void work
        .then(resolve, reject)
        .finally(() => signal.removeEventListener("abort", abort));
    });
  }
  async searchQuery(
    query: Record<string, unknown>,
    options: { size?: number; from?: number; signal?: AbortSignal } = {},
  ) {
    const size = Math.min(
      options.size ?? 100,
      500,
      10000 - (options.from ?? 0),
    );
    const from = options.from ?? 0;
    if (
      !Number.isInteger(size) ||
      size < 1 ||
      !Number.isInteger(from) ||
      from < 0 ||
      from >= 10000
    )
      throw new ConfigurationError(
        "Trademark pagination requires positive size and nonnegative from.",
      );
    const cancelled = () => {
      if (options.signal?.aborted)
        throw new ApiError(
          "Trademark Search request was cancelled.",
          0,
          "ABORTED",
        );
    };
    cancelled();
    let token = await this.requestToken(false, options.signal);
    cancelled();
    const send = () =>
      this.transport.text("POST", "/prod-stage-v1-0-0/tmsearch", {
        body: { query, size, from },
        headers: {
          Cookie: `aws-waf-token=${token.token}`,
          "User-Agent": this.userAgent(token),
        },
        ...(options.signal ? { signal: options.signal } : {}),
      });
    let response: Awaited<ReturnType<typeof send>>;
    try {
      response = await send();
      if (response.status !== 200)
        throw new ApiError(
          "Trademark Search requires a refreshed WAF session.",
          response.status,
          "AUTHENTICATION",
        );
    } catch (error) {
      if (
        !(error instanceof ApiError) ||
        ![202, 401, 403].includes(error.status)
      )
        throw error;
      token = await this.requestToken(
        this.token === token,
        options.signal,
        token,
      );
      cancelled();
      response = await send();
      if (response.status !== 200)
        throw new ApiError(
          "Trademark Search rejected the refreshed WAF session.",
          response.status,
          "AUTHENTICATION",
        );
    }
    let decoded: unknown;
    try {
      decoded = JSON.parse(response.data);
    } catch {
      throw new ApiError(
        "Trademark Search returned invalid JSON.",
        response.status,
        "INVALID_RESPONSE",
      );
    }
    const hit = z.looseObject({
      source: z.record(z.string(), z.unknown()).optional(),
      _source: z.record(z.string(), z.unknown()).optional(),
      id: z.union([z.string(), z.number()]).optional(),
      _id: z.union([z.string(), z.number()]).optional(),
    });
    const parsed = z
      .looseObject({
        hits: z
          .looseObject({
            totalValue: z.number().int().nonnegative().optional(),
            total: z
              .union([
                z.number().int().nonnegative(),
                z.object({ value: z.number().int().nonnegative() }),
              ])
              .optional(),
            hits: z.array(hit),
          })
          .refine(
            (value) =>
              value.total !== undefined || value.totalValue !== undefined,
          ),
        took: z.number().nonnegative().optional(),
      })
      .safeParse(decoded);
    if (!parsed.success)
      throw new ApiError(
        "Trademark Search returned an invalid result envelope.",
        response.status,
        "INVALID_RESPONSE",
      );
    const data = parsed.data;
    const results = data.hits.hits.map((hit) =>
      normalize(hit.source ?? hit._source ?? {}, hit.id ?? hit._id),
    );
    return {
      count: results.length,
      total:
        typeof data.hits.total === "number"
          ? data.hits.total
          : (data.hits.total?.value ?? data.hits.totalValue ?? 0),
      results,
      query_time_ms: data.took ?? 0,
      provenance: response.provenance,
    };
  }
  search(options: TrademarkSearchOptions) {
    const should: Record<string, unknown>[] = [];
    for (const [key, value] of Object.entries({
      wordmark: options.wordmark,
      ownerName: options.owner,
      goodsAndServices: options.goodsServices,
    }))
      if (value) should.push({ match: { [key]: value } });
    const must: Record<string, unknown>[] = [];
    if (should.length) must.push({ bool: { should, minimum_should_match: 1 } });
    if (options.serialNumber)
      must.push({ term: { serialNumber: options.serialNumber } });
    if (options.registrationNumber)
      must.push({ term: { registrationNumber: options.registrationNumber } });
    if (!must.length)
      throw new ConfigurationError(
        "Specify a wordmark, owner, goods/services, serial number, or registration number.",
      );
    if (options.liveOnly || options.status === "live")
      must.push({ term: { alive: true } });
    else if (options.status === "dead") must.push({ term: { alive: false } });
    return this.searchQuery({ bool: { must } }, options);
  }
  searchWordmark(
    wordmark: string,
    options: Omit<TrademarkSearchOptions, "wordmark"> = {},
  ) {
    return this.searchField("wordmark", wordmark, options);
  }
  searchOwner(
    owner: string,
    options: Omit<TrademarkSearchOptions, "owner"> = {},
  ) {
    return this.searchField("ownerName", owner, options);
  }
  searchGoodsServices(
    goods: string,
    options: Omit<TrademarkSearchOptions, "goodsServices"> = {},
  ) {
    return this.searchField("goodsAndServices", goods, options);
  }
  private searchField(
    field: string,
    value: string,
    options: TrademarkSearchOptions,
  ) {
    if (!value.trim())
      throw new ConfigurationError("A trademark search term is required.");
    const must: Record<string, unknown>[] = [{ match: { [field]: value } }];
    if (options.liveOnly || options.status === "live")
      must.push({ term: { alive: true } });
    else if (options.status === "dead") must.push({ term: { alive: false } });
    return this.searchQuery({ bool: { must } }, options);
  }
  async getBySerial(
    serialNumber: string,
    options: { signal?: AbortSignal } = {},
  ) {
    if (!serialNumber.trim())
      throw new ConfigurationError("A trademark serial number is required.");
    const r = await this.searchQuery(
      { term: { serialNumber } },
      { size: 1, ...options },
    );
    return { record: r.results[0] ?? null, provenance: r.provenance };
  }
  async getByRegistration(
    registrationNumber: string,
    options: { signal?: AbortSignal } = {},
  ) {
    if (!registrationNumber.trim())
      throw new ConfigurationError(
        "A trademark registration number is required.",
      );
    const r = await this.searchQuery(
      { term: { registrationNumber } },
      { size: 1, ...options },
    );
    return { record: r.results[0] ?? null, provenance: r.provenance };
  }
  async searchAll(
    options: Pick<
      TrademarkSearchOptions,
      "wordmark" | "owner" | "liveOnly" | "signal"
    > & { batchSize?: number; maxResults?: number },
  ) {
    const size = Math.min(options.batchSize ?? 500, 500);
    if (
      !Number.isInteger(size) ||
      size < 1 ||
      (options.maxResults !== undefined &&
        (!Number.isInteger(options.maxResults) || options.maxResults < 1))
    )
      throw new ConfigurationError("Invalid trademark searchAll bounds.");
    const results: TrademarkSearchResult[] = [];
    for (let from = 0; from < 10000; ) {
      const requested = Math.min(
        size,
        options.maxResults ? options.maxResults - results.length : size,
        10000 - from,
      );
      const page = await this.search({ ...options, size: requested, from });
      from += page.results.length;
      results.push(...page.results);
      if (options.maxResults && results.length >= options.maxResults)
        return results.slice(0, options.maxResults);
      if (page.results.length < requested || results.length >= page.total)
        return results;
    }
    return results;
  }
}
export { TrademarkSearchClient as TmsearchClient };

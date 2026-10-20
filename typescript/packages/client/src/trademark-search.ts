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
  private async getToken(force = false): Promise<WafToken> {
    if (force && this.options.refreshToken) {
      this.refreshing ??= this.options.refreshToken();
      try {
        this.token = await this.refreshing;
      } finally {
        this.refreshing = undefined;
      }
    }
    if (!this.token && !force) {
      const raw =
        process.env.PCA_WAF_TOKEN_JSON ?? process.env.LAW_TOOLS_WAF_TOKEN_JSON;
      if (raw) {
        try {
          this.token = JSON.parse(raw) as WafToken;
        } catch {
          throw new ConfigurationError(
            "PCA_WAF_TOKEN_JSON is not valid token JSON.",
          );
        }
      }
    }
    if (!this.token && !force && this.options.refreshToken)
      return this.getToken(true);
    const t = this.token;
    if (
      !t ||
      typeof t.token !== "string" ||
      !t.token.trim() ||
      /[\r\n;]/.test(t.token) ||
      !Number.isFinite(t.expires) ||
      t.expires * 1000 <= Date.now() + (force ? 0 : 6 * 3600000) ||
      (force && !this.options.refreshToken)
    )
      throw new ConfigurationError(
        "Supply a current externally minted WAF token with its matching User-Agent, or a refreshToken callback.",
      );
    return t;
  }
  async searchQuery(
    query: Record<string, unknown>,
    options: { size?: number; from?: number; signal?: AbortSignal } = {},
  ) {
    const size = Math.min(options.size ?? 100, 500);
    const from = options.from ?? 0;
    if (
      !Number.isInteger(size) ||
      size < 1 ||
      !Number.isInteger(from) ||
      from < 0
    )
      throw new ConfigurationError(
        "Trademark pagination requires positive size and nonnegative from.",
      );
    let token = await this.getToken();
    const send = () =>
      this.transport.json("POST", "/prod-stage-v1-0-0/tmsearch", {
        body: { query, size, from },
        headers: {
          Cookie: `aws-waf-token=${token.token}`,
          "User-Agent":
            this.options.userAgent ?? token.userAgent ?? WAF_USER_AGENT,
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
        error.status === 0 ||
        error.status >= 500 ||
        error.status === 429
      )
        throw error;
      token = await this.getToken(true);
      response = await send();
      if (response.status !== 200)
        throw new ApiError(
          "Trademark Search rejected the refreshed WAF session.",
          response.status,
          "AUTHENTICATION",
        );
    }
    const data = response.data as {
      hits?: {
        totalValue?: number;
        total?: { value?: number } | number;
        hits?: Array<{
          source?: Record<string, unknown>;
          id?: string;
          _source?: Record<string, unknown>;
          _id?: string;
        }>;
      };
      took?: number;
    };
    if (!data.hits)
      throw new ApiError(
        "Trademark Search returned no result envelope.",
        response.status,
        "INVALID_RESPONSE",
      );
    return {
      total:
        typeof data.hits.total === "number"
          ? data.hits.total
          : (data.hits.total?.value ?? data.hits.totalValue ?? 0),
      results: (data.hits.hits ?? []).map((hit) =>
        normalize(hit.source ?? hit._source ?? {}, hit.id ?? hit._id),
      ),
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
    if (options.liveOnly) must.push({ term: { alive: true } });
    return this.searchQuery({ bool: { must } }, options);
  }
  async getBySerial(serialNumber: string) {
    const r = await this.searchQuery({ term: { serialNumber } }, { size: 1 });
    return { record: r.results[0] ?? null, provenance: r.provenance };
  }
  async getByRegistration(registrationNumber: string) {
    const r = await this.searchQuery(
      { term: { registrationNumber } },
      { size: 1 },
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
    for (let from = 0; from <= 10000; from += size) {
      const page = await this.search({ ...options, size, from });
      results.push(...page.results);
      if (options.maxResults && results.length >= options.maxResults)
        return results.slice(0, options.maxResults);
      if (page.results.length < size || results.length >= page.total)
        return results;
    }
    return results;
  }
}
export { TrademarkSearchClient as TmsearchClient };

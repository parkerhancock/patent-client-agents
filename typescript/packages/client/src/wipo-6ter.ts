import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  HttpResponseError,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * WIPO Article 6ter Express: the state emblems, official hallmarks and
 * names, abbreviations and emblems of intergovernmental organizations
 * communicated under Article 6ter of the Paris Convention, which member
 * states must refuse as trademarks. The JSON API is documented by WIPO's
 * OpenAPI 3.0 file (Article6ter_API_v1_OpenAPI.yaml, v1.2.0, archived in
 * references/wipo-6ter) and needs no credentials.
 */
export const WIPO_6TER_BASE_URL = "https://6ter.wipo.int/api/v1";
export const WIPO_6TER_SOURCE = "WIPO Article 6ter Express";
/** The spec also lists STARTS_WITH, which the live API rejects. */
export const WIPO_6TER_SEARCH_TYPES = ["ANY", "ALL", "PHRASE"] as const;
export type Wipo6terSearchType = (typeof WIPO_6TER_SEARCH_TYPES)[number];

export type Wipo6terSign = Record<string, unknown>;
export interface Wipo6terPage {
  signs: Wipo6terSign[];
  /** Every sign matching the query. */
  count: number;
  offset: number;
  more_available: boolean;
  provenance: Provenance;
}
export interface Wipo6terSearch extends TransportRequestOptions {
  /** Full-text keywords over every field; "*" matches every sign. */
  keywords: string;
  searchType?: Wipo6terSearchType;
  /** KEY: by sign number; REL: by relevance. */
  sortBy?: "KEY" | "REL";
  limit?: number;
  offset?: number;
}

export type Wipo6terErrorCode =
  | "NOT_FOUND"
  | "INVALID_REQUEST"
  | "UPSTREAM_ERROR"
  | "INVALID_RESPONSE";
export class Wipo6terError extends ApiError {
  override name = "Wipo6terError";
  constructor(message: string, status: number, code: Wipo6terErrorCode) {
    super(message, status, code);
  }
}

const signSchema = z.looseObject({
  numberAlias: z.string().min(1),
  stateOrg: z.string().nullish(),
});
const pageSchema = z.looseObject({
  count: z.number().int().nonnegative(),
  records: z.array(signSchema),
});
const detailSchema = z.looseObject({ details: signSchema });
/** A sign's alias, the detail endpoint's key: two letters and digits (QO0088, MT0013). */
const ALIAS = /^[A-Z]{2}\d{1,6}$/;

function translate(error: unknown): unknown {
  if (!(error instanceof ApiError) || error instanceof Wipo6terError)
    return error;
  let detail = "";
  if (error instanceof HttpResponseError)
    try {
      const body = JSON.parse(error.bodyText) as { details?: unknown };
      if (typeof body.details === "string") detail = `: ${body.details}`;
    } catch {}
  return new Wipo6terError(
    `WIPO 6ter returned HTTP ${error.status}${detail}.`,
    error.status,
    error.status < 500 || detail ? "INVALID_REQUEST" : "UPSTREAM_ERROR",
  );
}

export class Wipo6terClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey" | "baseUrl"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      // A trailing slash, so operation paths resolve under /api/v1/.
      baseUrl: `${WIPO_6TER_BASE_URL}/`,
      sourceName: WIPO_6TER_SOURCE,
      cache: { name: "wipo_6ter" },
      headers: {
        accept: "application/json",
        "user-agent": "patent-client-agents/0 (+https://patentclient.com)",
      },
    });
  }

  /** `GET /signs`: full-text search over every field of every sign. */
  async search(query: Wipo6terSearch): Promise<Wipo6terPage> {
    const keywords = query.keywords.trim();
    if (!keywords)
      throw new TypeError('keywords is required; "*" matches every sign.');
    const limit = z
      .number()
      .int()
      .min(1)
      .max(500)
      .parse(query.limit ?? 25);
    const offset = z
      .number()
      .int()
      .min(0)
      .parse(query.offset ?? 0);
    const searchType = z
      .enum(WIPO_6TER_SEARCH_TYPES)
      .parse(query.searchType ?? "ANY");
    const sortBy = z.enum(["KEY", "REL"]).parse(query.sortBy ?? "KEY");
    const {
      keywords: _k,
      searchType: _t,
      sortBy: _s,
      limit: _l,
      offset: _o,
      ...request
    } = query;
    let result: Awaited<ReturnType<GenericHttpTransport["json"]>>;
    try {
      result = await this.http.json("GET", "signs", {
        ...request,
        searchParams: { keywords, searchType, sortBy, limit, offset },
        readErrorBody: true,
      });
    } catch (error) {
      throw translate(error);
    }
    const parsed = pageSchema.safeParse(result.data);
    if (!parsed.success)
      throw new Wipo6terError(
        "WIPO 6ter returned an unexpected search response.",
        result.status,
        "INVALID_RESPONSE",
      );
    return {
      signs: parsed.data.records as Wipo6terSign[],
      count: parsed.data.count,
      offset,
      more_available: offset + parsed.data.records.length < parsed.data.count,
      provenance: result.provenance,
    };
  }

  /** `GET /signs/{alias}`. WIPO answers an unknown alias with HTTP 204 and no body. */
  async getSign(
    alias: string,
    options: TransportRequestOptions = {},
  ): Promise<{ data: Wipo6terSign; provenance: Provenance }> {
    const id = alias.trim().toUpperCase();
    if (!ALIAS.test(id))
      throw new TypeError(
        `Article 6ter sign numbers look like QO0088 or MT0013: ${alias}`,
      );
    let result: Awaited<ReturnType<GenericHttpTransport["text"]>>;
    try {
      result = await this.http.text("GET", `signs/${id}`, {
        ...options,
        readErrorBody: true,
      });
    } catch (error) {
      throw translate(error);
    }
    if (result.status === 204 || !result.data.trim())
      throw new Wipo6terError(`WIPO 6ter has no sign ${id}.`, 404, "NOT_FOUND");
    let body: unknown;
    try {
      body = JSON.parse(result.data);
    } catch {
      body = undefined;
    }
    const parsed = detailSchema.safeParse(body);
    if (!parsed.success)
      throw new Wipo6terError(
        `WIPO 6ter returned an unexpected record for ${id}.`,
        result.status,
        "INVALID_RESPONSE",
      );
    return {
      data: parsed.data.details as Wipo6terSign,
      provenance: result.provenance,
    };
  }

  /** `GET /last-updated`: the database's last update (YYYY-MM-DD). */
  async lastUpdated(options: TransportRequestOptions = {}): Promise<string> {
    const result = await this.http
      .json("GET", "last-updated", options)
      .catch((error) => {
        throw translate(error);
      });
    const parsed = z
      .looseObject({ lastUpdated: z.string().min(1) })
      .safeParse(result.data);
    if (!parsed.success)
      throw new Wipo6terError(
        "WIPO 6ter returned no update date.",
        result.status,
        "INVALID_RESPONSE",
      );
    return parsed.data.lastUpdated;
  }

  /** `GET /publication`: the bulk ZIP's URL, date and size. */
  async publication(options: TransportRequestOptions = {}) {
    const result = await this.http
      .json("GET", "publication", options)
      .catch((error) => {
        throw translate(error);
      });
    const file = z.looseObject({
      url: z.string().url(),
      available: z.boolean(),
      lastModified: z.string().nullish(),
      size: z.number().int().nonnegative().nullish(),
    });
    const parsed = z
      .looseObject({ zip: file, md5: file.nullish() })
      .safeParse(result.data);
    if (!parsed.success)
      throw new Wipo6terError(
        "WIPO 6ter returned an unexpected publication response.",
        result.status,
        "INVALID_RESPONSE",
      );
    return { data: parsed.data, provenance: result.provenance };
  }
}

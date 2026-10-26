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
 * PRV (Sweden): the unauthenticated JSON APIs behind search.prv.se. Patent
 * search and SPC search on patents-search-api.prv.se, trademark and design
 * search on dv-search-api.prv.se, and the patent register record on
 * api.prv.se. Undocumented: request shapes follow the search.prv.se bundle
 * (main.7a8cf370.js, October 27, 2026). Register data is reusable under
 * Sweden's Open Data Act; PRV asks reusers to register at data@prv.se.
 */
export const PRV_PATENTS_HOST = "https://patents-search-api.prv.se";
export const PRV_DV_HOST = "https://dv-search-api.prv.se";
export const PRV_API_HOST = "https://api.prv.se";
export const PRV_SOURCE = "Patent- och registreringsverket (PRV, Sweden)";
export const PRV_USER_AGENT =
  "patent-client-agents/0 (+https://patentclient.com; contact data@prv.se)";
/** Python's conservative cap; PRV's own app pages by 10-20 and accepts more. */
export const PRV_MAX_PAGE_SIZE = 100;

export type PrvRow = Record<string, unknown>;
export interface PrvPage {
  rows: PrvRow[];
  total_hits: number;
  /** Pages at this page size (PRV reports a last page index instead). */
  total_pages: number;
  /** Zero-based. */
  page: number;
  more_available: boolean;
  provenance: Provenance;
}
export interface PrvSearchOptions extends TransportRequestOptions {
  text?: string | null;
  /** Zero-based page. */
  page?: number;
  pageSize?: number;
  sortColumn?: string | null;
  sortOrder?: "ASC" | "DESC" | null;
  /** Further body keys, sent as given. */
  extra?: Record<string, unknown>;
}
export type PrvMatchType = "CONTAINS" | "STARTS_WITH" | "EXACT";
/** The gazette announcement types PRV's SPC search offers, as it sends them. */
export const PRV_SPC_ANNOUNCEMENTS = [
  "Ansökan om tilläggsskydd",
  "Meddelade tilläggsskydd",
  "Inkomna ansökningar om förlängda tilläggsskydd",
  "Meddelade förlängda tilläggsskydd",
  "Avslagna ansökningar om tilläggsskydd",
  "Avslagna ansökningar om förlängda tilläggsskydd",
  "Tilläggsskydd som har upphört att gälla och därför avförts ur patentregistret",
  "Förlängda tilläggsskydd som har upphört att gälla och därför avförts ur patentregistret",
  "Rättelser och korrigeringar gällande tilläggsskydd",
  "Rättelser och korrigeringar gällande förlängda tilläggsskydd",
  "Övriga kungörelser om tilläggsskydd",
  "Övriga kungörelser om förlängda tilläggsskydd",
] as const;
export interface PrvSpcSearchOptions extends TransportRequestOptions {
  substance?: string | null;
  applicants?: string | null;
  /** The SPC's own number, e.g. 1190011-5. */
  applicationNumberSpc?: string | null;
  /** The base patent's application number, e.g. EP00108480.5. */
  basePatentNumber?: string | null;
  marketingAuthorizationNumber?: string | null;
  /** One of PRV_SPC_ANNOUNCEMENTS; always an exact match. */
  announcement?: (typeof PRV_SPC_ANNOUNCEMENTS)[number] | null;
  /** Applies to every text filter; PRV's own default is CONTAINS (STARTS_WITH for SPC numbers). */
  matchType?: PrvMatchType;
  page?: number;
  pageSize?: number;
}

export type PrvErrorCode =
  | "NOT_FOUND"
  | "INVALID_REQUEST"
  | "UPSTREAM_ERROR"
  | "INVALID_RESPONSE";
export class PrvError extends ApiError {
  override name = "PrvError";
  constructor(message: string, status: number, code: PrvErrorCode) {
    super(message, status, code);
  }
}

const pageSchema = z.looseObject({
  totalHits: z.number().int().nonnegative(),
  // The last zero-based page index, not a count: 0 for one hit, -1 for none.
  totalPages: z.number().int(),
  page: z.number().int().nonnegative(),
});
const rowsSchema = z.array(z.looseObject({}));
/** Patent records carry applicationNumberFormatted; trademark and design records applicationNumber. */
const recordSchema = z.union([
  z.looseObject({ applicationNumberFormatted: z.string().min(1) }),
  z.looseObject({ applicationNumber: z.string().min(1) }),
]);
/** A trademark or design application number (2025-05038, 2026-0151). */
function dvNumber(value: string): string {
  const number = value.trim();
  if (!/^\d{4}-\d{1,6}$/.test(number))
    throw new TypeError(
      `PRV trademark and design numbers look like 2025-05038: ${value}`,
    );
  return number;
}

/**
 * The register's form of a patent application number. The record endpoint
 * goes by the number's own prefix and answers HTTP 400 for the compact forms
 * Python documented (26155556, 2615555-6), so those gain their SE prefix.
 */
export function prvApplicationNumber(value: string): string {
  const number = value.trim().toUpperCase().replace(/\s+/g, "");
  if (!number) throw new TypeError("applicationNumber is required.");
  const compact = /^(?:SE)?(\d{7})-?(\d)$/.exec(number);
  if (compact) return `SE${compact[1]}-${compact[2]}`;
  const ep = /^EP(\d{8})\.?(\d)$/.exec(number);
  if (ep) return `EP${ep[1]}.${ep[2]}`;
  return number;
}

function translate(error: unknown): unknown {
  if (!(error instanceof ApiError) || error instanceof PrvError) return error;
  let message = "";
  if (error instanceof HttpResponseError)
    try {
      const body = JSON.parse(error.bodyText) as { message?: unknown };
      if (typeof body.message === "string")
        message = body.message.replace(/\.$/, "");
    } catch {}
  const detail = message ? `: ${message}` : "";
  if (error.status === 404)
    return new PrvError(`PRV found no record${detail}.`, 404, "NOT_FOUND");
  if (error.status === 400 || error.status === 406)
    return new PrvError(
      `PRV rejected the request${detail}.`,
      error.status,
      "INVALID_REQUEST",
    );
  if (error.status >= 400)
    return new PrvError(
      `PRV returned HTTP ${error.status}${detail}.`,
      error.status,
      "UPSTREAM_ERROR",
    );
  return error;
}

/** PRV Sweden: patents, SPCs, trademarks and designs. No credentials. */
export class PrvClient extends CachedClient {
  private readonly patents: GenericHttpTransport;
  private readonly dv: GenericHttpTransport;
  private readonly api: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey" | "baseUrl"> = {}) {
    super();
    const transport = (baseUrl: string) =>
      new GenericHttpTransport({
        ...options,
        baseUrl,
        sourceName: PRV_SOURCE,
        cache: { name: "prv_se" },
        headers: { accept: "application/json", "user-agent": PRV_USER_AGENT },
      });
    this.patents = transport(PRV_PATENTS_HOST);
    this.dv = transport(PRV_DV_HOST);
    this.api = transport(PRV_API_HOST);
  }

  private async search(
    http: GenericHttpTransport,
    path: string,
    key: string,
    body: Record<string, unknown>,
    options: TransportRequestOptions,
  ): Promise<PrvPage> {
    let result: Awaited<ReturnType<GenericHttpTransport["json"]>>;
    try {
      result = await http.json("POST", path, {
        ...options,
        body,
        readErrorBody: true,
      });
    } catch (error) {
      throw translate(error);
    }
    const parsed = pageSchema.safeParse(result.data);
    const list = rowsSchema.safeParse(
      (result.data as Record<string, unknown> | null)?.[key],
    );
    if (!parsed.success || !list.success)
      throw new PrvError(
        `PRV ${path} returned an unexpected response.`,
        result.status,
        "INVALID_RESPONSE",
      );
    const rows = list.data as PrvRow[];
    const size = Number(body.pageSize);
    return {
      rows,
      total_hits: parsed.data.totalHits,
      // Python compared page + 1 with totalPages, a last index, so it said
      // nothing more on the second-to-last page.
      total_pages: Math.ceil(parsed.data.totalHits / size),
      page: parsed.data.page,
      more_available: (parsed.data.page + 1) * size < parsed.data.totalHits,
      provenance: result.provenance,
    };
  }
  private simpleBody(options: PrvSearchOptions) {
    const page = z
      .number()
      .int()
      .min(0)
      .parse(options.page ?? 0);
    const size = z
      .number()
      .int()
      .min(1)
      .parse(options.pageSize ?? 10);
    const body: Record<string, unknown> = {
      page,
      pageSize: Math.min(size, PRV_MAX_PAGE_SIZE),
    };
    const sortColumn =
      options.sortColumn === undefined ? "filingDate" : options.sortColumn;
    const sortOrder =
      options.sortOrder === undefined ? "DESC" : options.sortOrder;
    if (sortColumn) body.sortColumn = sortColumn;
    if (sortOrder) body.sortOrder = sortOrder;
    if (options.text?.trim()) body.simpleSearchText = options.text.trim();
    for (const [key, value] of Object.entries(options.extra ?? {}))
      if (value !== undefined && value !== null) body[key] = value;
    return body;
  }
  /** The transport options among a search's options. */
  private request(options: TransportRequestOptions): TransportRequestOptions {
    const out: TransportRequestOptions = {};
    if (options.signal) out.signal = options.signal;
    if (options.timeoutMs) out.timeoutMs = options.timeoutMs;
    if (options.headers) out.headers = options.headers;
    return out;
  }

  /** Patent simple search: applicant, inventor, title and number. National filings and EP validations. */
  searchPatents(options: PrvSearchOptions = {}): Promise<PrvPage> {
    return this.search(
      this.patents,
      "/searchpatent/patentsimplesearch/",
      "searchPatentDTOS",
      this.simpleBody(options),
      this.request(options),
    );
  }
  /** Trademark simple search: mark text, applicant and representative. National marks and Madrid designations. */
  searchTrademarks(options: PrvSearchOptions = {}): Promise<PrvPage> {
    return this.search(
      this.dv,
      "/searchtrademark/tmsimplesearch/",
      "trademarks",
      this.simpleBody(options),
      this.request(options),
    );
  }
  /** Design simple search; one row per design within an application. */
  searchDesigns(options: PrvSearchOptions = {}): Promise<PrvPage> {
    return this.search(
      this.dv,
      "/searchdesign/dssimplesearch/",
      "designs",
      this.simpleBody(options),
      this.request(options),
    );
  }
  /**
   * Supplementary protection certificate search. Filter keys are the ones
   * PRV's app sends; Python sent its form's names (substanceProduct,
   * basePatentNumber, ...), which PRV ignores, so those filters found nothing.
   */
  async searchSpcs(options: PrvSpcSearchOptions = {}): Promise<PrvPage> {
    const match = z
      .enum(["CONTAINS", "STARTS_WITH", "EXACT"])
      .optional()
      .parse(options.matchType);
    // Each field accepts only some match types (PRV answers 406 or 500
    // otherwise): the requested type where it is accepted, else the default.
    const filters: [string, string | null | undefined, PrvMatchType[]][] = [
      ["substance", options.substance, ["CONTAINS", "STARTS_WITH", "EXACT"]],
      ["applicants", options.applicants, ["CONTAINS", "STARTS_WITH", "EXACT"]],
      [
        "applicationNumberSpc",
        options.applicationNumberSpc,
        ["STARTS_WITH", "EXACT"],
      ],
      ["applicationNumber", options.basePatentNumber, ["STARTS_WITH", "EXACT"]],
      [
        "firstMarketingAuthorization",
        options.marketingAuthorizationNumber,
        ["CONTAINS"],
      ],
    ];
    const page = z
      .number()
      .int()
      .min(0)
      .parse(options.page ?? 0);
    const size = z
      .number()
      .int()
      .min(1)
      .parse(options.pageSize ?? 10);
    const body: Record<string, unknown> = {
      page,
      pageSize: Math.min(size, PRV_MAX_PAGE_SIZE),
      sortColumn: "",
      sortOrder: "ASC",
    };
    for (const [key, value, accepted] of filters)
      if (value?.trim())
        body[key] = {
          value: value.trim(),
          searchType: match && accepted.includes(match) ? match : accepted[0],
        };
    if (options.announcement) {
      if (
        !(PRV_SPC_ANNOUNCEMENTS as readonly string[]).includes(
          options.announcement,
        )
      )
        throw new TypeError(
          `Unknown SPC announcement type. Use one of: ${PRV_SPC_ANNOUNCEMENTS.join("; ")}.`,
        );
      body.announcement = { value: options.announcement, searchType: "EXACT" };
    }
    if (Object.keys(body).length === 4)
      throw new TypeError(
        "searchSpcs needs at least one filter: substance, applicants, applicationNumberSpc, basePatentNumber, marketingAuthorizationNumber or announcement.",
      );
    return this.search(
      this.patents,
      "/searchpatentspc/patentsearchspc/",
      "searchSpcDTOS",
      body,
      this.request(options),
    );
  }

  /** GET one api.prv.se record; PRV answers an unknown number with HTTP 404 and a message. */
  private async record(
    path: string,
    number: string,
    options: TransportRequestOptions,
  ): Promise<{ data: PrvRow; provenance: Provenance }> {
    let result: Awaited<ReturnType<GenericHttpTransport["json"]>>;
    try {
      result = await this.api.json(
        "GET",
        `${path}${encodeURIComponent(number)}`,
        {
          ...options,
          readErrorBody: true,
        },
      );
    } catch (error) {
      throw translate(error);
    }
    const parsed = recordSchema.safeParse(result.data);
    if (!parsed.success)
      throw new PrvError(
        `PRV returned an unexpected record for ${number}.`,
        result.status,
        "INVALID_RESPONSE",
      );
    return { data: parsed.data as PrvRow, provenance: result.provenance };
  }
  /** The patent register record: status, register entries, gazette announcements, publications and first drawing. */
  async getPatent(
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ) {
    return this.record(
      "/patents/applications/",
      prvApplicationNumber(applicationNumber),
      options,
    );
  }
  /**
   * The trademark record (PRV's app reads it; Python never wrapped it):
   * status, dates, opposition period, applicants and representatives, Nice
   * classes with their terms, Vienna classes, documents with image URLs and
   * inline image bytes, and gazette publications.
   */
  async getTrademark(
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ) {
    return this.record(
      "/trademarks/applications/",
      dvNumber(applicationNumber),
      options,
    );
  }
  /** The design record: status, dates, applicants, designers, each design's title and views, documents and publications. */
  async getDesign(
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ) {
    return this.record(
      "/designs/applications/",
      dvNumber(applicationNumber),
      options,
    );
  }
}

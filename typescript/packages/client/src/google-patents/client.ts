import { z } from "zod";
import type { Provenance } from "../models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "../transport.js";
import { extractClaims, type GoogleClaim } from "./claims.js";
import { parseDocument } from "./dom.js";
import { extractFigures, type GoogleFigure } from "./figures.js";
import { descriptionToMarkdown } from "./markdown.js";
import { extractMetadata, type GooglePatentMetadata } from "./metadata.js";

export const GOOGLE_PATENTS_SOURCE = "Google Patents";
const ORIGIN = "https://patents.google.com";
const IMAGES = "patentimages.storage.googleapis.com";

export type GooglePatentsErrorCode =
  | "NOT_FOUND"
  | "RATE_LIMITED"
  | "INVALID_RESPONSE";
export class GooglePatentsError extends ApiError {
  override name = "GooglePatentsError";
  constructor(
    message: string,
    status: number,
    code: GooglePatentsErrorCode,
    /** Seconds until the shared cooldown ends, for RATE_LIMITED. */
    public readonly retryAfterSeconds: number | null = null,
  ) {
    super(message, status, code);
  }
}

/**
 * Google Patents throttles hard: a few rapid requests return 503 and need a
 * multi-minute cooldown. One limiter per process spaces requests (4 s by
 * default) and, after a 503, fails fast until the cooldown ends rather than
 * holding callers for minutes.
 */
export class GooglePatentsRateLimiter {
  private last = 0;
  private cooldownUntil = 0;
  private queue: Promise<void> = Promise.resolve();
  constructor(
    readonly minIntervalMs = 4_000,
    readonly cooldownMs = 90_000,
  ) {}
  /** Wait for this caller's turn. */
  acquire(signal?: AbortSignal): Promise<void> {
    const turn = this.queue.then(async () => {
      const now = Date.now();
      if (now < this.cooldownUntil)
        throw new GooglePatentsError(
          "Google Patents is rate limiting this server; try again later.",
          503,
          "RATE_LIMITED",
          Math.ceil((this.cooldownUntil - now) / 1000),
        );
      const wait = this.last + this.minIntervalMs - now;
      if (wait > 0)
        await new Promise<void>((resolve, reject) => {
          const timer = setTimeout(resolve, wait);
          signal?.addEventListener(
            "abort",
            () => {
              clearTimeout(timer);
              reject(signal.reason);
            },
            { once: true },
          );
        });
      this.last = Date.now();
    });
    this.queue = turn.catch(() => {});
    return turn;
  }
  cooldown(): void {
    this.cooldownUntil = Date.now() + this.cooldownMs;
  }
}
const sharedLimiter = new GooglePatentsRateLimiter();

/**
 * Normalize to Google's publication form: bare numbers become US numbers,
 * 10-digit US pre-grant serials gain the leading zero, short WO numbers
 * gain the century and padding.
 */
export function normalizeGooglePatentNumber(value: string): string {
  let normalized = value
    .toUpperCase()
    .trim()
    .replace(/[\s,/-]/g, "");
  if (/^\d/.test(normalized)) normalized = `US${normalized}`;
  if (/^US\d{4}\d{6}A1$/.test(normalized))
    normalized = `${normalized.slice(0, 6)}0${normalized.slice(6)}`;
  const wo = /^WO(\d{2})(\d+[A-Z]\d*)$/.exec(normalized);
  if (wo && normalized.length <= 12) {
    const [, year = "", suffix = ""] = wo;
    const century = Number(year) >= 80 ? "19" : "20";
    normalized =
      suffix.length >= 5
        ? `WO${century}${year}0${suffix}`
        : `WO${century}${year}${suffix}`;
  }
  if (!/^[A-Z]{2}[A-Z0-9]{1,20}$/.test(normalized))
    throw new TypeError(`Invalid patent number: ${value}`);
  return normalized;
}

/**
 * Expiration from the page, else priority date plus 20 years, flagged as an
 * estimate. The estimate ignores term adjustment and later US filing dates;
 * refine it from USPTO data before relying on it.
 */
export function resolveExpiration(
  pageExpiration: string,
  priorityDate: string | null,
): { expiration_date: string; expiration_estimated: boolean } {
  if (pageExpiration)
    return { expiration_date: pageExpiration, expiration_estimated: false };
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(priorityDate?.trim() ?? "");
  if (!match) return { expiration_date: "", expiration_estimated: false };
  const [, year = "", month = "", day = ""] = match;
  const target = Number(year) + 20;
  const leap = (target % 4 === 0 && target % 100 !== 0) || target % 400 === 0;
  const safeDay = month === "02" && day === "29" && !leap ? "28" : day;
  return {
    expiration_date: `${target}-${month}-${safeDay}`,
    expiration_estimated: true,
  };
}

const LANGUAGES: Record<string, string> = {
  JP: "ja",
  CN: "zh",
  KR: "ko",
  DE: "de",
  FR: "fr",
  ES: "es",
  IT: "it",
  RU: "ru",
  BR: "pt",
};

export interface GooglePatent extends GooglePatentMetadata {
  patent_number: string;
  claims: GoogleClaim[];
  structured_limitations: Record<string, string[]>;
  original_limitations: Record<string, string[]>;
  description_markdown: string | null;
  figures: GoogleFigure[];
  expiration_date: string;
  /** True when expiration_date is the priority + 20 years estimate. */
  expiration_estimated: boolean;
  /** ISO 639-1 code of the original language on machine-translated pages. */
  source_language: string | null;
}

/** Search parameters, mirroring the Google Patents query string. */
export interface GooglePatentsSearch {
  keywords?: string[];
  cpcCodes?: string[];
  inventors?: string[];
  assignees?: string[];
  countries?: string[];
  languages?: string[];
  dateType?: "priority" | "filing" | "publication";
  after?: string;
  before?: string;
  status?: "GRANT" | "APPLICATION";
  patentType?: "PATENT" | "DESIGN";
  litigation?: "YES" | "NO";
  includePatents?: boolean;
  includeNpl?: boolean;
  sort?: "new" | "old";
  dups?: "language" | "family";
  /** 1-based page. */
  page?: number;
  /** Results per page, 10 to 100. */
  pageSize?: number;
  clusterResults?: boolean;
}
export interface GooglePatentsSearchResult {
  result_type: "patent" | "scholar" | "web";
  id: string;
  rank: number;
  title: string | null;
  snippet: string | null;
  publication_number: string | null;
  language: string | null;
  priority_date: string | null;
  filing_date: string | null;
  grant_date: string | null;
  publication_date: string | null;
  inventor: string | null;
  assignee: string | null;
  pdf_url: string | null;
  thumbnail_url: string | null;
  detail_url: string | null;
  family_country_status: unknown[];
}
export interface GooglePatentsSearchResponse {
  query_url: string;
  total_results: number;
  total_pages: number;
  page: number;
  page_size: number;
  has_more: boolean;
  results: GooglePatentsSearchResult[];
}

/** The Google Patents front end's own query-value encoder. */
function encode(value: string): string {
  return Array.from(value, (char) =>
    "&?/,=+%#".includes(char)
      ? `%${char.charCodeAt(0).toString(16)}`
      : char === " "
        ? "+"
        : char,
  ).join("");
}
const clean = (values?: string[]) =>
  (values ?? []).map((v) => v.trim()).filter(Boolean);
const isoDate = z.iso.date();
/** Google rejects YYYY-MM-DD in date filters with HTTP 500; it takes YYYYMMDD. */
const compact = (value: string) => isoDate.parse(value).replaceAll("-", "");

/** Build the `url` value for /xhr/query. */
export function buildGoogleQuery(search: GooglePatentsSearch): string {
  const parts: string[] = [];
  for (const keyword of clean(search.keywords))
    parts.push(`q=${encode(keyword)}`);
  const list = (name: string, values?: string[]) => {
    const items = clean(values);
    if (items.length) parts.push(`${name}=${items.map(encode).join(",")}`);
  };
  list("cpc", search.cpcCodes);
  list("inventor", search.inventors);
  list("assignee", search.assignees);
  const countries = clean(search.countries).map((c) => c.toUpperCase());
  if (countries.length) parts.push(`country=${countries.join(",")}`);
  const languages = clean(search.languages).map((l) => l.toLowerCase());
  if (languages.length) parts.push(`language=${languages.join(",")}`);
  const dateType = search.dateType ?? "priority";
  if (search.after) parts.push(`after=${dateType}:${compact(search.after)}`);
  if (search.before) parts.push(`before=${dateType}:${compact(search.before)}`);
  if (search.status) parts.push(`status=${encode(search.status)}`);
  if (search.patentType) parts.push(`type=${encode(search.patentType)}`);
  if (search.litigation) parts.push(`litigation=${encode(search.litigation)}`);
  if (search.pageSize !== undefined && search.pageSize !== 10)
    parts.push(
      `num=${z.number().int().min(10).max(100).parse(search.pageSize)}`,
    );
  if (search.includePatents === false) parts.push("patents=false");
  if (search.includeNpl) parts.push("scholar");
  if (search.sort)
    parts.push(`sort=${z.enum(["new", "old"]).parse(search.sort)}`);
  if (search.dups) parts.push(`dups=${encode(search.dups)}`);
  if (search.page !== undefined && search.page > 1)
    parts.push(`page=${z.number().int().max(100).parse(search.page) - 1}`);
  if (search.clusterResults) parts.push("clustered=true");
  if (!parts.length)
    throw new TypeError(
      "Provide at least one search term (keyword, CPC, inventor, assignee, country or language).",
    );
  return parts.join("&");
}

const entrySchema = z.looseObject({
  id: z.string().optional(),
  rank: z.number().optional(),
  patent: z.record(z.string(), z.unknown()).optional(),
  scholar: z.record(z.string(), z.unknown()).optional(),
  webdoc: z.record(z.string(), z.unknown()).optional(),
});
const searchSchema = z.looseObject({
  results: z.looseObject({
    total_num_results: z.number().int().nonnegative().optional(),
    total_num_pages: z.number().int().nonnegative().optional(),
    num_page: z.number().int().nonnegative().optional(),
    cluster: z
      .array(z.looseObject({ result: z.array(entrySchema).optional() }))
      .optional(),
  }),
});
const imageUrl = (path: unknown) =>
  typeof path === "string" && path ? `https://${IMAGES}/${path}` : null;
const str = (value: unknown) => (typeof value === "string" ? value : null);

export function parseGoogleSearch(
  payload: unknown,
  queryUrl: string,
): GooglePatentsSearchResponse {
  const parsed = searchSchema.safeParse(payload);
  if (!parsed.success)
    throw new GooglePatentsError(
      "Google Patents search returned an unexpected shape.",
      200,
      "INVALID_RESPONSE",
    );
  const block = parsed.data.results;
  const results = (block.cluster ?? []).flatMap((cluster) =>
    (cluster.result ?? []).flatMap((entry): GooglePatentsSearchResult[] => {
      const [type, data] = entry.patent
        ? (["patent", entry.patent] as const)
        : entry.scholar
          ? (["scholar", entry.scholar] as const)
          : entry.webdoc
            ? (["web", entry.webdoc] as const)
            : [null, null];
      if (!type || !data) return [];
      const family = data.family_metadata as
        | { aggregated?: { country_status?: unknown[] } }
        | undefined;
      return [
        {
          result_type: type,
          id: entry.id ?? "",
          rank: entry.rank ?? 0,
          title: str(data.title),
          snippet: str(data.snippet),
          publication_number: str(data.publication_number) ?? str(data.number),
          language: str(data.language),
          priority_date: str(data.priority_date),
          filing_date: str(data.filing_date),
          grant_date: str(data.grant_date),
          publication_date: str(data.publication_date),
          inventor: str(data.inventor),
          assignee: str(data.assignee),
          pdf_url: imageUrl(data.pdf),
          thumbnail_url: imageUrl(data.thumbnail),
          detail_url: entry.id ? `${ORIGIN}/${entry.id}` : null,
          family_country_status: Array.isArray(
            family?.aggregated?.country_status,
          )
            ? family.aggregated.country_status
            : [],
        },
      ];
    }),
  );
  const totalPages = block.total_num_pages ?? 1;
  const current = block.num_page ?? 0;
  return {
    query_url: queryUrl,
    total_results: block.total_num_results ?? results.length,
    total_pages: totalPages,
    page: current + 1,
    page_size: results.length,
    has_more: current + 1 < totalPages,
    results,
  };
}

export interface GooglePatentsClientOptions
  extends Omit<ClientOptions, "apiKey"> {
  /** Defaults to one process-wide limiter. */
  rateLimiter?: GooglePatentsRateLimiter;
}

/**
 * Google Patents pages and search. Unofficial: the page is scraped and the
 * search endpoint is the site's own JSON backend, so markup changes break
 * parsing; archived fixtures pin the expected structure.
 */
export class GooglePatentsClient {
  private readonly http: GenericHttpTransport;
  private readonly limiter: GooglePatentsRateLimiter;
  constructor(options: GooglePatentsClientOptions = {}) {
    const { rateLimiter, ...transport } = options;
    this.limiter = rateLimiter ?? sharedLimiter;
    this.http = new GenericHttpTransport({
      // Retries make throttling worse; a 503 starts the shared cooldown instead.
      retryLimit: 0,
      timeoutMs: 30_000,
      ...transport,
      baseUrl: options.baseUrl ?? ORIGIN,
      sourceName: GOOGLE_PATENTS_SOURCE,
      headers: { "accept-language": "en-US,en;q=0.9" },
    });
  }
  private async fetch<M extends "text" | "json" | "bytes">(
    mode: M,
    path: string,
    options: TransportRequestOptions,
  ) {
    await this.limiter.acquire(options.signal);
    try {
      return await (this.http[mode](
        "GET",
        path,
        // Same-origin redirects only (an empty allowlist enables them).
        { allowedHosts: [], ...options },
      ) as ReturnType<GenericHttpTransport[M]>);
    } catch (error) {
      if (
        error instanceof ApiError &&
        (error.status === 503 || error.status === 429)
      ) {
        this.limiter.cooldown();
        throw new GooglePatentsError(
          "Google Patents is rate limiting this server; try again later.",
          error.status,
          "RATE_LIMITED",
          Math.ceil(this.limiter.cooldownMs / 1000),
        );
      }
      throw error;
    }
  }

  /** Raw page HTML for a publication. */
  async getPatentHtml(
    number: string,
    options: TransportRequestOptions = {},
  ): Promise<{ html: string; patentNumber: string; provenance: Provenance }> {
    const patentNumber = normalizeGooglePatentNumber(number);
    let result: Awaited<ReturnType<GenericHttpTransport["text"]>>;
    try {
      result = await this.fetch("text", `/patent/${patentNumber}/en`, options);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404)
        throw new GooglePatentsError(
          `${patentNumber} was not found on Google Patents.`,
          404,
          "NOT_FOUND",
        );
      throw error;
    }
    // Older pages served a 200 "not found" page; keep recognizing it.
    if (result.data.includes("Sorry, we couldn't find this patent"))
      throw new GooglePatentsError(
        `${patentNumber} was not found on Google Patents.`,
        404,
        "NOT_FOUND",
      );
    return { html: result.data, patentNumber, provenance: result.provenance };
  }

  /** Parse an already-fetched page; exported for fixtures and offline use. */
  static parsePatent(html: string, patentNumber: string): GooglePatent {
    const document = parseDocument(html);
    const metadata = extractMetadata(document, html, patentNumber);
    if (!metadata.title || metadata.title === "Title not found")
      throw new GooglePatentsError(
        `Google Patents page for ${patentNumber} has no recognizable title; the page structure may have changed.`,
        200,
        "INVALID_RESPONSE",
      );
    const claims = extractClaims(document);
    const translated = claims.claims.some((claim) => claim.original_text);
    return {
      ...metadata,
      patent_number: patentNumber,
      ...claims,
      description_markdown: descriptionToMarkdown(metadata.description_html),
      figures: extractFigures(document),
      ...resolveExpiration(
        metadata.expiration_date,
        metadata.priority_date || null,
      ),
      source_language: translated
        ? (LANGUAGES[patentNumber.slice(0, 2)] ?? null)
        : null,
    };
  }

  /** Metadata, claims, limitations, description, figures, citations and family for one publication. */
  async getPatent(
    number: string,
    options: TransportRequestOptions = {},
  ): Promise<{ data: GooglePatent; provenance: Provenance }> {
    const page = await this.getPatentHtml(number, options);
    return {
      data: GooglePatentsClient.parsePatent(page.html, page.patentNumber),
      provenance: page.provenance,
    };
  }

  async search(
    search: GooglePatentsSearch,
    options: TransportRequestOptions = {},
  ): Promise<{ data: GooglePatentsSearchResponse; provenance: Provenance }> {
    const query = buildGoogleQuery(search);
    const result = await this.fetch("text", "/xhr/query", {
      ...options,
      headers: { accept: "application/json" },
      searchParams: { url: query },
    });
    const body = result.data.trim();
    // Throttled searches come back as an HTML page.
    if (body.startsWith("<")) {
      this.limiter.cooldown();
      throw new GooglePatentsError(
        "Google Patents is rate limiting this server; try again later.",
        result.status,
        "RATE_LIMITED",
        Math.ceil(this.limiter.cooldownMs / 1000),
      );
    }
    let payload: unknown;
    try {
      payload = JSON.parse(body);
    } catch {
      throw new GooglePatentsError(
        "Google Patents search returned invalid JSON.",
        result.status,
        "INVALID_RESPONSE",
      );
    }
    return {
      data: parseGoogleSearch(payload, query),
      provenance: result.provenance,
    };
  }

  /** The publication PDF from Google's image store. */
  async downloadPdf(
    number: string,
    options: TransportRequestOptions = {},
  ): Promise<{
    data: Uint8Array;
    patentNumber: string;
    provenance: Provenance;
  }> {
    const { data: patent } = await this.getPatent(number, options);
    if (!patent.pdf_url)
      throw new GooglePatentsError(
        `Google Patents has no PDF for ${patent.patent_number}.`,
        404,
        "NOT_FOUND",
      );
    const url = new URL(patent.pdf_url, ORIGIN);
    if (url.protocol !== "https:" || url.hostname !== IMAGES)
      throw new GooglePatentsError(
        "Google Patents PDF link is not on the expected image host.",
        200,
        "INVALID_RESPONSE",
      );
    const result = await this.http.bytes("GET", url.href, {
      ...options,
      allowedHosts: [IMAGES],
      timeoutMs: 45_000,
    });
    if (new TextDecoder().decode(result.data.subarray(0, 5)) !== "%PDF-")
      throw new GooglePatentsError(
        `Expected a PDF for ${patent.patent_number}.`,
        result.status,
        "INVALID_RESPONSE",
      );
    return {
      data: result.data,
      patentNumber: patent.patent_number,
      provenance: result.provenance,
    };
  }
}

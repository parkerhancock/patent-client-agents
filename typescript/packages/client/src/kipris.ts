import { XMLParser, XMLValidator } from "fast-xml-parser";
import { z } from "zod";
import type { Provenance } from "./models.js";
import { env } from "./runtime/env.js";
import {
  ApiError,
  type ClientOptions,
  ConfigurationError,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * KIPO KIPRIS Plus (Korea): patents and utility models, trademarks and
 * designs over three XML information-search services. Auth is a per-user
 * `serviceKey` query parameter (ToS §11 forbids sharing keys), so the key is
 * bring-your-own and every request must go to an operator-verified HTTPS
 * endpoint: KIPRIS documents only the HTTP host below.
 */
export const KIPRIS_DOCUMENTED_BASE_URL =
  "http://kipo-api.kipi.or.kr/openapi/service";
export const KIPRIS_SIGNUP_URL = "https://plus.kipris.or.kr/eng/main.do";
/** Python _KIPO_ATTRIBUTION: the ToS §11 constraint travels with every record. */
export const KIPRIS_SOURCE =
  "Source: Korean Intellectual Property Office (KIPO), via KIPRIS Plus operated by KIPI. Per-user API key required by ToS §11.";
export const KIPRIS_SERVICES = {
  patents: "patUtliInfoSearchService",
  trademarks: "trademarkInfoSearchService",
  designs: "designInfoSearchService",
} as const;
export type KiprisService =
  (typeof KIPRIS_SERVICES)[keyof typeof KIPRIS_SERVICES];
export const KIPRIS_DEFAULT_ROWS = 10;
export const KIPRIS_MAX_ROWS = 1000;

type Field = readonly [key: string, kind: "text" | "date"];
const PATENT_FIELDS: readonly Field[] = [
  ["applicationNumber", "text"],
  ["applicationDate", "date"],
  ["publicationNumber", "text"],
  ["publicationDate", "date"],
  ["openNumber", "text"],
  ["openDate", "date"],
  ["registerNumber", "text"],
  ["registerDate", "date"],
  ["registerStatus", "text"],
  ["inventionTitle", "text"],
  ["inventionTitleEnglish", "text"],
  ["astrtCont", "text"],
  ["applicantName", "text"],
  ["inventorName", "text"],
  ["agentName", "text"],
  ["ipcNumber", "text"],
];
const TRADEMARK_FIELDS: readonly Field[] = [
  ["applicationNumber", "text"],
  ["applicationDate", "date"],
  ["registrationNumber", "text"],
  ["registrationDate", "date"],
  ["registrationPublicNumber", "text"],
  ["title", "text"],
  ["bigDrawing", "text"],
  ["classificationCode", "text"],
  ["viennaCode", "text"],
  ["applicantName", "text"],
  ["agentName", "text"],
  ["regPrivilegeName", "text"],
];
const DESIGN_FIELDS: readonly Field[] = [
  ["applicationNumber", "text"],
  ["applicationDate", "date"],
  ["registrationNumber", "text"],
  ["registrationDate", "date"],
  ["registerStatus", "text"],
  ["articleName", "text"],
  ["drawing", "text"],
  ["locCode", "text"],
  ["applicantName", "text"],
  ["inventorName", "text"],
  ["agentName", "text"],
];

type Text = string | null;
/** Unmodeled upstream elements are retained as text (normalized fields win). */
type Unmodeled = { [key: string]: string | null };
/** Patent or utility-model row, keyed by the upstream camelCase element names. */
export interface KiprisPatentRow extends Unmodeled {
  applicationNumber: Text;
  /** ISO date (YYYY-MM-DD). */
  applicationDate: Text;
  /** Granted-patent publication number. */
  publicationNumber: Text;
  publicationDate: Text;
  /** Laid-open (pre-grant) publication number. */
  openNumber: Text;
  openDate: Text;
  registerNumber: Text;
  registerDate: Text;
  /** Korean status label, such as 등록 (registered) or 공개 (published). */
  registerStatus: Text;
  inventionTitle: Text;
  inventionTitleEnglish: Text;
  /** Korean abstract. */
  astrtCont: Text;
  /** May be semicolon-delimited. */
  applicantName: Text;
  inventorName: Text;
  agentName: Text;
  ipcNumber: Text;
}
export interface KiprisTrademarkRow extends Unmodeled {
  applicationNumber: Text;
  applicationDate: Text;
  registrationNumber: Text;
  registrationDate: Text;
  registrationPublicNumber: Text;
  /** The mark text. */
  title: Text;
  /** Mark image URL; empty for word marks. */
  bigDrawing: Text;
  /** Nice classes, may be semicolon-delimited. */
  classificationCode: Text;
  viennaCode: Text;
  applicantName: Text;
  agentName: Text;
  /** Registered proprietor. */
  regPrivilegeName: Text;
}
export interface KiprisDesignRow extends Unmodeled {
  applicationNumber: Text;
  applicationDate: Text;
  registrationNumber: Text;
  registrationDate: Text;
  registerStatus: Text;
  /** The article the design is applied to. */
  articleName: Text;
  /** Drawing image URL. */
  drawing: Text;
  /** Locarno classification. */
  locCode: Text;
  applicantName: Text;
  /** Designer. */
  inventorName: Text;
  agentName: Text;
}

export interface KiprisPagination {
  resultCode: string | null;
  resultMsg: string | null;
  numOfRows: number | string | null;
  pageNo: number | string | null;
  totalCount: number | string | null;
}
export interface KiprisPage<T> {
  items: T[];
  pagination: KiprisPagination;
  provenance: Provenance;
}
/** Extra upstream filters, forwarded verbatim; `serviceKey` cannot be overridden. */
export type KiprisExtra = Record<string, string | number | undefined>;
export interface KiprisPageOptions {
  numOfRows?: number | undefined;
  pageNo?: number | undefined;
  extra?: KiprisExtra | undefined;
}
export interface KiprisPatentSearchOptions extends KiprisPageOptions {
  /** Include patents (default true). */
  patent?: boolean | undefined;
  /** Include utility models (default true). */
  utility?: boolean | undefined;
}
export interface KiprisPatentAdvancedOptions extends KiprisPatentSearchOptions {
  inventionTitle?: string | undefined;
  astrtCont?: string | undefined;
  claimScope?: string | undefined;
  applicant?: string | undefined;
  inventor?: string | undefined;
  ipc?: string | undefined;
  /** YYYYMMDD or YYYYMMDD~YYYYMMDD. */
  applicationDate?: string | undefined;
  publicationDate?: string | undefined;
}
export interface KiprisTrademarkAdvancedOptions extends KiprisPageOptions {
  title?: string | undefined;
  applicant?: string | undefined;
  classification?: string | undefined;
  viennaCode?: string | undefined;
  applicationDate?: string | undefined;
  registrationDate?: string | undefined;
}
export interface KiprisDesignAdvancedOptions extends KiprisPageOptions {
  articleName?: string | undefined;
  applicant?: string | undefined;
  locCode?: string | undefined;
  applicationDate?: string | undefined;
  registrationDate?: string | undefined;
}
export interface KiprisClientOptions extends ClientOptions {
  /** Per-user KIPRIS Plus serviceKey; falls back to apiKey, then KIPO_KIPRIS_API_KEY. */
  serviceKey?: string;
}

const invalid = (message: string) =>
  new ApiError(message, 200, "INVALID_RESPONSE");

/** Python parse_iso_date: ISO or YYYYMMDD; blank, 00000000 and impossible dates become null. */
export function kiprisDate(value: string | null): string | null {
  const cleaned = value?.trim();
  if (!cleaned || cleaned === "00000000") return null;
  const match =
    /^(\d{4})-(\d{2})-(\d{2})$/.exec(cleaned) ??
    /^(\d{4})(\d{2})(\d{2})$/.exec(cleaned);
  if (!match) return null;
  const [, y, m, d] = match;
  const date = new Date(`${y}-${m}-${d}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) &&
    date.toISOString().slice(0, 10) === `${y}-${m}-${d}`
    ? `${y}-${m}-${d}`
    : null;
}

function normalize<T>(raw: Unmodeled, fields: readonly Field[]): T {
  const row: Unmodeled = { ...raw };
  for (const [key, kind] of fields) {
    const value = raw[key]?.trim() || null;
    row[key] = kind === "date" ? kiprisDate(value) : value;
  }
  return row as T;
}

const textOf = (value: unknown): string | null => {
  if (Array.isArray(value)) return textOf(value.at(-1));
  if (typeof value === "string") return value.trim() || null;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
  return null;
};
const countOf = (value: unknown) => {
  const text = textOf(value);
  if (text === null) return null;
  return /^-?\d+$/.test(text) ? Number(text) : text;
};
const objectOf = (value: unknown): Record<string, unknown> | undefined =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;

/**
 * Parse a KIPRIS XML envelope into raw rows and pagination. A non-"00"
 * resultCode (or a data.go.kr gateway error) is an ApiError; a response
 * without the `response` and `body` elements is malformed, not empty.
 */
export function parseKiprisResponse(xml: string): {
  items: Unmodeled[];
  pagination: KiprisPagination;
} {
  if (/<!(?:ENTITY|DOCTYPE)\s/i.test(xml))
    throw invalid("KIPRIS Plus XML entity declarations are not supported.");
  if (XMLValidator.validate(xml) !== true)
    throw invalid("KIPRIS Plus returned a non-XML response.");
  const document = new XMLParser({
    ignoreAttributes: true,
    removeNSPrefix: true,
    parseTagValue: false,
    trimValues: true,
    processEntities: true,
    isArray: (name, path) =>
      name === "item" && path === "response.body.items.item",
  }).parse(xml) as Record<string, unknown>;
  const gateway = objectOf(
    objectOf(document.OpenAPI_ServiceResponse)?.cmmMsgHeader,
  );
  if (gateway) {
    const code = textOf(gateway.returnReasonCode);
    const reason = textOf(gateway.returnAuthMsg) ?? textOf(gateway.errMsg);
    throw new ApiError(
      `KIPRIS Plus result ${code ?? "unknown"}: ${reason ?? "unknown error"}`,
      502,
      "UPSTREAM_ERROR",
    );
  }
  const response = objectOf(document.response);
  if (!response) throw invalid("KIPRIS Plus response is missing <response>.");
  const header = objectOf(response.header);
  const resultCode = textOf(header?.resultCode);
  const resultMsg = textOf(header?.resultMsg);
  // "00" is NORMAL SERVICE; Python also accepts an absent code.
  if (resultCode !== null && resultCode !== "00")
    throw new ApiError(
      `KIPRIS Plus result ${resultCode}: ${resultMsg ?? "unknown error"}`,
      502,
      "UPSTREAM_ERROR",
    );
  const body = objectOf(response.body);
  if (!body)
    throw invalid(
      "KIPRIS Plus response is missing <body>; coverage is unknown.",
    );
  const itemsElement = body.items;
  const rawItems =
    objectOf(itemsElement)?.item ??
    (itemsElement === undefined || itemsElement === "" ? [] : undefined);
  if (!Array.isArray(rawItems))
    throw invalid("KIPRIS Plus returned malformed <items>.");
  const items = rawItems.map((item) => {
    const element = objectOf(item) ?? {};
    // Python flattens <item> children to {tag: text}; nested elements lose their text.
    return Object.fromEntries(
      Object.entries(element).map(([key, value]) => [key, textOf(value)]),
    );
  });
  return {
    items,
    pagination: {
      resultCode,
      resultMsg,
      numOfRows: countOf(body.numOfRows),
      pageNo: countOf(body.pageNo),
      totalCount: countOf(body.totalCount),
    },
  };
}

const positive = z.number().int().positive().safe();
function pageParams(options: KiprisPageOptions) {
  const rows = positive.safeParse(options.numOfRows ?? KIPRIS_DEFAULT_ROWS);
  const page = positive.safeParse(options.pageNo ?? 1);
  if (!rows.success || !page.success)
    throw new ApiError(
      "num_of_rows and page_no must be positive integers.",
      400,
      "INVALID_INPUT",
    );
  return {
    numOfRows: Math.min(rows.data, KIPRIS_MAX_ROWS),
    pageNo: page.data,
  };
}
const yn = (value: boolean | undefined) => (value === false ? "N" : "Y");

export class KiprisClient {
  private readonly http: GenericHttpTransport;
  private readonly serviceKey: string;
  private readonly baseUrl: string;

  constructor(options: KiprisClientOptions = {}) {
    const key =
      options.serviceKey || options.apiKey || env("KIPO_KIPRIS_API_KEY");
    if (!key?.trim())
      throw new ConfigurationError(
        `KIPRIS Plus API key required. Set KIPO_KIPRIS_API_KEY or pass serviceKey. Sign up at ${KIPRIS_SIGNUP_URL} (KIPRIS Plus ToS §11: per-user keys only, no shared keys).`,
      );
    const base = options.baseUrl || env("KIPO_KIPRIS_BASE_URL");
    if (!base?.trim())
      throw new ConfigurationError(
        "KIPRIS Plus HTTPS endpoint required. Set KIPO_KIPRIS_BASE_URL or pass baseUrl. The documented HTTP endpoint is disabled because requests include the API key in the query string.",
      );
    let url: URL;
    try {
      url = new URL(base.trim());
    } catch {
      throw new ConfigurationError("KIPO_KIPRIS_BASE_URL is not a valid URL.");
    }
    if (url.protocol !== "https:")
      throw new ConfigurationError(
        "KIPRIS Plus base URL must use HTTPS; refusing to send the API key over an unencrypted connection.",
      );
    this.serviceKey = key.trim();
    // A trailing slash keeps the configured path when operations resolve against it.
    this.baseUrl = url.href.replace(/\/*$/, "/");
    const { apiKey: _apiKey, serviceKey: _serviceKey, ...transport } = options;
    this.http = new GenericHttpTransport({
      ...transport,
      baseUrl: this.baseUrl,
      sourceName: KIPRIS_SOURCE,
      headers: { accept: "application/xml" },
    });
  }

  /** Operation URL without credentials, used as provenance. */
  operationUrl(service: KiprisService, operation: string): string {
    return `${this.baseUrl}${service}/${operation}`;
  }

  private async get<T>(
    service: KiprisService,
    operation: string,
    params: Record<string, string | number | undefined>,
    extra: KiprisExtra | undefined,
    fields: readonly Field[],
    options: TransportRequestOptions,
  ): Promise<KiprisPage<T>> {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...params, ...extra }))
      if (value !== undefined && value !== null && key !== "serviceKey")
        searchParams.set(key, String(value));
    searchParams.set("serviceKey", this.serviceKey);
    const result = await this.http.text("GET", `${service}/${operation}`, {
      ...options,
      searchParams,
    });
    const parsed = parseKiprisResponse(result.data);
    return {
      items: parsed.items.map((item) => normalize<T>(item, fields)),
      pagination: parsed.pagination,
      // The transport's provenance would keep the serviceKey query parameter.
      provenance: {
        ...result.provenance,
        source_url: this.operationUrl(service, operation),
      },
    };
  }

  /** patUtliInfoSearchService/getWordSearch: free text over patents and utility models. */
  searchPatentsWord(
    word: string,
    search: KiprisPatentSearchOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisPatentRow>> {
    return this.get(
      KIPRIS_SERVICES.patents,
      "getWordSearch",
      {
        word,
        patent: yn(search.patent),
        utility: yn(search.utility),
        ...pageParams(search),
      },
      search.extra,
      PATENT_FIELDS,
      options,
    );
  }

  /** patUtliInfoSearchService/getAdvancedSearch: KIPRIS ANDs the supplied fields. */
  searchPatentsAdvanced(
    search: KiprisPatentAdvancedOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisPatentRow>> {
    return this.get(
      KIPRIS_SERVICES.patents,
      "getAdvancedSearch",
      {
        inventionTitle: search.inventionTitle,
        astrtCont: search.astrtCont,
        claimScope: search.claimScope,
        applicant: search.applicant,
        inventors: search.inventor,
        ipcNumber: search.ipc,
        applicationDate: search.applicationDate,
        publicationDate: search.publicationDate,
        patent: yn(search.patent),
        utility: yn(search.utility),
        ...pageParams(search),
      },
      search.extra,
      PATENT_FIELDS,
      options,
    );
  }

  /** Rows for one application number (KIPRIS has no by-number endpoint; advanced search filters on it). */
  getPatent(
    number: string,
    extra?: KiprisExtra,
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisPatentRow>> {
    return this.get(
      KIPRIS_SERVICES.patents,
      "getAdvancedSearch",
      {
        applicationNumber: number,
        patent: "Y",
        utility: "Y",
        numOfRows: KIPRIS_DEFAULT_ROWS,
        pageNo: 1,
      },
      extra,
      PATENT_FIELDS,
      options,
    );
  }

  /** trademarkInfoSearchService/getWordSearch. */
  searchTrademarksWord(
    word: string,
    search: KiprisPageOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisTrademarkRow>> {
    return this.get(
      KIPRIS_SERVICES.trademarks,
      "getWordSearch",
      { word, ...pageParams(search) },
      search.extra,
      TRADEMARK_FIELDS,
      options,
    );
  }

  /** trademarkInfoSearchService/getAdvancedSearch. */
  searchTrademarksAdvanced(
    search: KiprisTrademarkAdvancedOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisTrademarkRow>> {
    return this.get(
      KIPRIS_SERVICES.trademarks,
      "getAdvancedSearch",
      {
        title: search.title,
        applicantName: search.applicant,
        classification: search.classification,
        viennaCode: search.viennaCode,
        applicationDate: search.applicationDate,
        registrationDate: search.registrationDate,
        ...pageParams(search),
      },
      search.extra,
      TRADEMARK_FIELDS,
      options,
    );
  }

  getTrademark(
    number: string,
    extra?: KiprisExtra,
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisTrademarkRow>> {
    return this.get(
      KIPRIS_SERVICES.trademarks,
      "getAdvancedSearch",
      { applicationNumber: number, numOfRows: KIPRIS_DEFAULT_ROWS, pageNo: 1 },
      extra,
      TRADEMARK_FIELDS,
      options,
    );
  }

  /** designInfoSearchService/getWordSearch. */
  searchDesignsWord(
    word: string,
    search: KiprisPageOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisDesignRow>> {
    return this.get(
      KIPRIS_SERVICES.designs,
      "getWordSearch",
      { word, ...pageParams(search) },
      search.extra,
      DESIGN_FIELDS,
      options,
    );
  }

  /** designInfoSearchService/getAdvancedSearch. */
  searchDesignsAdvanced(
    search: KiprisDesignAdvancedOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisDesignRow>> {
    return this.get(
      KIPRIS_SERVICES.designs,
      "getAdvancedSearch",
      {
        articleName: search.articleName,
        applicantName: search.applicant,
        locCode: search.locCode,
        applicationDate: search.applicationDate,
        registrationDate: search.registrationDate,
        ...pageParams(search),
      },
      search.extra,
      DESIGN_FIELDS,
      options,
    );
  }

  getDesign(
    number: string,
    extra?: KiprisExtra,
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisDesignRow>> {
    return this.get(
      KIPRIS_SERVICES.designs,
      "getAdvancedSearch",
      { applicationNumber: number, numOfRows: KIPRIS_DEFAULT_ROWS, pageNo: 1 },
      extra,
      DESIGN_FIELDS,
      options,
    );
  }

  /**
   * Python paginate: call a search with pageNo 1, 2, ... and yield rows
   * until a short page or maxPages.
   */
  async *paginate<T>(
    search: (page: {
      numOfRows: number;
      pageNo: number;
    }) => Promise<KiprisPage<T>>,
    options: { numOfRows?: number; maxPages?: number } = {},
  ): AsyncGenerator<T> {
    const { numOfRows } = pageParams({ numOfRows: options.numOfRows });
    for (let pageNo = 1; ; pageNo++) {
      const page = await search({ numOfRows, pageNo });
      yield* page.items;
      if (page.items.length < numOfRows) return;
      if (options.maxPages !== undefined && pageNo >= options.maxPages) return;
    }
  }
}

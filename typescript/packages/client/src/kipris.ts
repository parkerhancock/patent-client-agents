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
 * designs over three XML information-search services. Operation names,
 * parameters and response elements follow the KIPRIS Plus Open API pages
 * archived in references/kipris (see docs/kipris.md). Auth is a per-user
 * `ServiceKey` query parameter; ToS §11 forbids sharing keys, so the key is
 * bring-your-own.
 */
export const KIPRIS_BASE_URL = "https://plus.kipris.or.kr/kipo-api/kipi";
export const KIPRIS_SIGNUP_URL = "https://plus.kipris.or.kr/eng/main.do";
/** Python _KIPO_ATTRIBUTION: the ToS §11 constraint travels with every record. */
export const KIPRIS_SOURCE =
  "Source: Korean Intellectual Property Office (KIPO), via KIPRIS Plus operated by KIPI. Per-user API key required by ToS §11.";
/** Service names as documented, including the upstream "Sevice" spelling. */
export const KIPRIS_SERVICES = {
  patents: "patUtiModInfoSearchSevice",
  trademarks: "trademarkInfoSearchService",
  designs: "designInfoSearchService",
} as const;
export type KiprisService =
  (typeof KIPRIS_SERVICES)[keyof typeof KIPRIS_SERVICES];
export const KIPRIS_DEFAULT_ROWS = 10;
/** Documented maximum numOfRows for every search operation used here. */
export const KIPRIS_MAX_ROWS = 500;

type Field = readonly [key: string, kind: "text" | "date"];
const text = (...keys: string[]) => keys.map((k) => [k, "text"] as const);
const date = (...keys: string[]) => keys.map((k) => [k, "date"] as const);
/** getWordSearch / getAdvancedSearch item elements (patUtiModInfoSearchSevice). */
const PATENT_FIELDS: readonly Field[] = [
  ...text(
    "indexNo",
    "registerStatus",
    "inventionTitle",
    "ipcNumber",
    "registerNumber",
    "applicationNumber",
    "openNumber",
    "publicationNumber",
    "astrtCont",
    "drawing",
    "bigDrawing",
    "applicantName",
  ),
  ...date("registerDate", "applicationDate", "openDate", "publicationDate"),
];
/** trademarkInfoSearchService search item elements. */
const TRADEMARK_FIELDS: readonly Field[] = [
  ...text(
    "indexNo",
    "applicationNumber",
    "publicationNumber",
    "registrationPublicNumber",
    "registrationNumber",
    "priorityNumber",
    "applicationStatus",
    "classificationCode",
    "viennaCode",
    "applicantName",
    "agentName",
    "regPrivilegeName",
    "title",
    "fullText",
    "drawing",
    "bigDrawing",
    "appReferenceNumber",
    "regReferenceNumber",
    "internationalRegisterNumber",
  ),
  ...date(
    "applicationDate",
    "publicationDate",
    "registrationPublicDate",
    "registrationDate",
    "priorityDate",
    "internationalRegisterDate",
  ),
];
/** designInfoSearchService search item elements. */
const DESIGN_FIELDS: readonly Field[] = [
  ...text(
    "number",
    "applicationNumber",
    "publicationNumber",
    "registrationNumber",
    "priorityNumber",
    "applicationStatus",
    "applicantName",
    "agentName",
    "fullText",
    "inventorName",
    "articleName",
    "designMainClassification",
    "openNumber",
    "dsShpClssCd",
    "imagePath",
    "imagePathLarge",
    "designNumber",
    "appReferenceNumber",
    "regReferenceNumber",
    "internationalRegisterNumber",
  ),
  ...date(
    "applicationDate",
    "publicationDate",
    "registrationDate",
    "priorityDate",
    "openDate",
    "internationalRegisterDate",
  ),
];

type Text = string | null;
/** Unmodeled upstream elements are retained as text (normalized fields win). */
type Unmodeled = { [key: string]: string | null };
/** Patent or utility-model search row, keyed by the documented element names. */
export interface KiprisPatentRow extends Unmodeled {
  indexNo: Text;
  /** Korean status: 공개, 등록, 거절, 무효, 소멸, 취하, 포기. */
  registerStatus: Text;
  inventionTitle: Text;
  /** Several values are separated by "|". */
  ipcNumber: Text;
  registerNumber: Text;
  /** ISO date (YYYY-MM-DD). */
  registerDate: Text;
  applicationNumber: Text;
  applicationDate: Text;
  /** Laid-open publication. */
  openNumber: Text;
  openDate: Text;
  /** Examined (grant) publication. */
  publicationNumber: Text;
  publicationDate: Text;
  /** Korean abstract. */
  astrtCont: Text;
  drawing: Text;
  bigDrawing: Text;
  /** Several values are separated by "|". */
  applicantName: Text;
}
export interface KiprisTrademarkRow extends Unmodeled {
  indexNo: Text;
  applicationNumber: Text;
  applicationDate: Text;
  /** Application publication. */
  publicationNumber: Text;
  publicationDate: Text;
  registrationPublicNumber: Text;
  registrationPublicDate: Text;
  registrationNumber: Text;
  registrationDate: Text;
  priorityNumber: Text;
  priorityDate: Text;
  /** Korean status, such as 출원 or 등록. */
  applicationStatus: Text;
  /** Nice classes, space-separated. */
  classificationCode: Text;
  /** Vienna codes, space-separated. */
  viennaCode: Text;
  applicantName: Text;
  agentName: Text;
  /** Registered proprietor. */
  regPrivilegeName: Text;
  /** The mark text. */
  title: Text;
  /** Y when the full text is available. */
  fullText: Text;
  drawing: Text;
  bigDrawing: Text;
  appReferenceNumber: Text;
  regReferenceNumber: Text;
  internationalRegisterNumber: Text;
  internationalRegisterDate: Text;
}
export interface KiprisDesignRow extends Unmodeled {
  number: Text;
  applicationNumber: Text;
  applicationDate: Text;
  publicationNumber: Text;
  publicationDate: Text;
  registrationNumber: Text;
  registrationDate: Text;
  priorityNumber: Text;
  priorityDate: Text;
  applicationStatus: Text;
  applicantName: Text;
  agentName: Text;
  fullText: Text;
  /** Designer. */
  inventorName: Text;
  /** The article the design is applied to. */
  articleName: Text;
  /** KIPO design classification code. */
  designMainClassification: Text;
  openNumber: Text;
  openDate: Text;
  /** Shape classification. */
  dsShpClssCd: Text;
  imagePath: Text;
  imagePathLarge: Text;
  designNumber: Text;
  appReferenceNumber: Text;
  regReferenceNumber: Text;
  internationalRegisterNumber: Text;
  internationalRegisterDate: Text;
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
/** A nested element tree: repeated elements become arrays, leaves text or null. */
export type KiprisTree = { [key: string]: KiprisNode };
export type KiprisNode = string | null | KiprisTree | KiprisNode[];
export interface KiprisBibliography {
  /** The <item> (or <items>) element, or null when the number has no record. */
  item: KiprisTree | null;
  provenance: Provenance;
}
/** Extra documented filters, forwarded verbatim; `ServiceKey` cannot be overridden. */
export type KiprisExtra = Record<string, string | number | boolean | undefined>;
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
  word?: string | undefined;
  inventionTitle?: string | undefined;
  astrtCont?: string | undefined;
  claimScope?: string | undefined;
  /** Applicant name or customer number. */
  applicant?: string | undefined;
  /** Inventor name or customer number (upstream `inventors`). */
  inventor?: string | undefined;
  /** Upstream `ipcNumber`. */
  ipc?: string | undefined;
  /** YYYYMMDD~YYYYMMDD. */
  applicationDate?: string | undefined;
  publicationDate?: string | undefined;
}
export interface KiprisTrademarkAdvancedOptions extends KiprisPageOptions {
  /** Upstream `trademarkName`. */
  title?: string | undefined;
  /** Upstream `applicantName`. */
  applicant?: string | undefined;
  /** Nice class (upstream `classification`). */
  classification?: string | undefined;
  viennaCode?: string | undefined;
  applicationDate?: string | undefined;
  /** Upstream `registerDate`. */
  registrationDate?: string | undefined;
}
export interface KiprisDesignAdvancedOptions extends KiprisPageOptions {
  articleName?: string | undefined;
  /** Upstream `applicantName`. */
  applicant?: string | undefined;
  /** KIPO design classification (upstream `designMainClassification`). */
  designClassification?: string | undefined;
  applicationDate?: string | undefined;
  registrationDate?: string | undefined;
}
export interface KiprisClientOptions extends ClientOptions {
  /** Per-user ServiceKey; falls back to apiKey, then KIPO_KIPRIS_API_KEY. */
  serviceKey?: string;
}

/**
 * The trademark advanced search rejects a request unless at least one flag
 * in each group is true; the documented sample sets them all.
 */
const TRADEMARK_FLAGS = [
  "application",
  "registration",
  "refused",
  "expiration",
  "withdrawal",
  "publication",
  "cancel",
  "abandonment",
  "trademark",
  "serviceMark",
  "trademarkServiceMark",
  "businessEmblem",
  "collectiveMark",
  "geoOrgMark",
  "internationalMark",
  "certMark",
  "geoCertMark",
  "character",
  "figure",
  "compositionCharacter",
  "figureComposition",
  "sound",
  "fragrance",
  "color",
  "dimension",
  "colorMixed",
  "hologram",
  "motion",
  "visual",
  "invisible",
] as const;
/** Status and design-type flags, all true in the documented sample (the upstream spells "cancle"). */
const DESIGN_FLAGS = [
  "open",
  "rejection",
  "destroy",
  "cancle",
  "notice",
  "registration",
  "invalid",
  "abandonment",
  "simi",
  "part",
  "etc",
] as const;
const allTrue = (flags: readonly string[]) =>
  Object.fromEntries(flags.map((flag) => [flag, "true"]));

/**
 * Result codes. 00, 10 and 30 are observed from plus.kipris.or.kr; the
 * others are the data.go.kr common codes KIPRIS shares, unconfirmed here.
 */
const RESULT_CODES: Record<
  string,
  { status: number; code: string; hint: string }
> = {
  "10": {
    status: 400,
    code: "INVALID_INPUT",
    hint: "KIPRIS rejected the request parameters.",
  },
  "11": {
    status: 400,
    code: "INVALID_INPUT",
    hint: "A required request parameter is missing.",
  },
  "12": {
    status: 404,
    code: "UPSTREAM_ERROR",
    hint: "The operation does not exist or was withdrawn.",
  },
  "20": {
    status: 403,
    code: "UNAUTHORIZED",
    hint: "The key is not approved for this service.",
  },
  "22": {
    status: 429,
    code: "RATE_LIMITED",
    hint: "The key's daily request quota is used up.",
  },
  "23": {
    status: 429,
    code: "RATE_LIMITED",
    hint: "Too many requests per second; retry shortly.",
  },
  "30": {
    status: 401,
    code: "UNAUTHORIZED",
    hint: "KIPO_KIPRIS_API_KEY is not a registered KIPRIS Plus key, or it is not approved for this service.",
  },
  "31": {
    status: 401,
    code: "UNAUTHORIZED",
    hint: "The KIPRIS Plus key has expired.",
  },
  "32": {
    status: 403,
    code: "UNAUTHORIZED",
    hint: "This server's IP address is not registered for the key.",
  },
};

const invalid = (message: string) =>
  new ApiError(message, 200, "INVALID_RESPONSE");

/**
 * ISO date from KIPRIS's forms: YYYYMMDD, YYYY-MM-DD, YYYY.MM.DD and the
 * older "YYYY/MM/DD 00:00:00". Blank, 00000000 and impossible dates are null.
 */
export function kiprisDate(value: string | null): string | null {
  const cleaned = value?.trim();
  if (!cleaned || cleaned === "00000000") return null;
  const match =
    /^(\d{4})[-./](\d{2})[-./](\d{2})(?:\s+\d{2}:\d{2}:\d{2})?$/.exec(
      cleaned,
    ) ?? /^(\d{4})(\d{2})(\d{2})$/.exec(cleaned);
  if (!match) return null;
  const [, y, m, d] = match;
  const iso = `${y}-${m}-${d}`;
  const parsed = new Date(`${iso}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === iso
    ? iso
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

function parseDocument(xml: string): Record<string, unknown> {
  if (/<!(?:ENTITY|DOCTYPE)\s/i.test(xml))
    throw invalid("KIPRIS Plus XML entity declarations are not supported.");
  if (XMLValidator.validate(xml) !== true)
    throw invalid("KIPRIS Plus returned a non-XML response.");
  return new XMLParser({
    ignoreAttributes: true,
    removeNSPrefix: true,
    parseTagValue: false,
    trimValues: true,
    processEntities: true,
    isArray: (name, path) =>
      name === "item" && path === "response.body.items.item",
  }).parse(xml) as Record<string, unknown>;
}

/**
 * Check the <response><header> envelope and return the response element.
 * A non-"00" resultCode is an ApiError naming the code; a success without
 * <body> is malformed, never an empty result.
 */
function checkedResponse(document: Record<string, unknown>) {
  const response = objectOf(document.response);
  if (!response) throw invalid("KIPRIS Plus response is missing <response>.");
  const header = objectOf(response.header);
  const resultCode = textOf(header?.resultCode);
  const resultMsg = textOf(header?.resultMsg);
  if (resultCode !== null && resultCode !== "00") {
    const known = RESULT_CODES[resultCode];
    throw new ApiError(
      `KIPRIS Plus result ${resultCode}: ${resultMsg ?? "unknown error"}.${known ? ` ${known.hint}` : ""}`,
      known?.status ?? 502,
      known?.code ?? "UPSTREAM_ERROR",
    );
  }
  // An empty <body/> is present (no record); an absent one is malformed.
  const body = response.body === "" ? {} : objectOf(response.body);
  if (!body)
    throw invalid(
      "KIPRIS Plus response is missing <body>; coverage is unknown.",
    );
  return { response, body, resultCode, resultMsg };
}

/** Parse a search response into raw rows and the <count> pagination. */
export function parseKiprisResponse(xml: string): {
  items: Unmodeled[];
  pagination: KiprisPagination;
} {
  const { response, body, resultCode, resultMsg } = checkedResponse(
    parseDocument(xml),
  );
  const itemsElement = body.items;
  const rawItems =
    objectOf(itemsElement)?.item ??
    (itemsElement === undefined || itemsElement === "" ? [] : undefined);
  if (!Array.isArray(rawItems))
    throw invalid("KIPRIS Plus returned malformed <items>.");
  const items = rawItems.map((item) => {
    const element = objectOf(item) ?? {};
    // Search items are flat; a nested element keeps no text, as in Python.
    return Object.fromEntries(
      Object.entries(element).map(([key, value]) => [key, textOf(value)]),
    );
  });
  // The documented responses put paging in <count>, a sibling of <body>.
  const count = objectOf(response.count) ?? body;
  return {
    items,
    pagination: {
      resultCode,
      resultMsg,
      numOfRows: countOf(count.numOfRows),
      pageNo: countOf(count.pageNo),
      totalCount: countOf(count.totalCount),
    },
  };
}

function tree(value: unknown): KiprisNode {
  if (Array.isArray(value)) return value.map(tree);
  const object = objectOf(value);
  if (object)
    return Object.fromEntries(
      Object.entries(object).map(([key, child]) => [key, tree(child)]),
    );
  return textOf(value);
}
/** Parse a getBibliographyDetailInfoSearch response into its item tree. */
export function parseKiprisBibliography(xml: string): KiprisTree | null {
  const { body } = checkedResponse(parseDocument(xml));
  // Patents wrap the record in <items>; trademarks and designs in <item>.
  const item = tree(body.item ?? body.items);
  if (item === null) return null;
  if (typeof item !== "object" || Array.isArray(item))
    throw invalid("KIPRIS Plus returned a malformed bibliography item.");
  return item;
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
const flag = (value: boolean | undefined) =>
  value === false ? "false" : "true";

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
    const base =
      options.baseUrl || env("KIPO_KIPRIS_BASE_URL") || KIPRIS_BASE_URL;
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

  private async request(
    service: KiprisService,
    operation: string,
    params: Record<string, string | number | undefined>,
    extra: KiprisExtra | undefined,
    options: TransportRequestOptions,
  ) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...params, ...extra }))
      if (value !== undefined && value !== null && !/^servicekey$/i.test(key))
        searchParams.set(key, String(value));
    searchParams.set("ServiceKey", this.serviceKey);
    const result = await this.http.text("GET", `${service}/${operation}`, {
      ...options,
      searchParams,
    });
    return {
      xml: result.data,
      // The transport's provenance would keep the ServiceKey query parameter.
      provenance: {
        ...result.provenance,
        source_url: this.operationUrl(service, operation),
      },
    };
  }

  private async search<T>(
    service: KiprisService,
    operation: string,
    params: Record<string, string | number | undefined>,
    extra: KiprisExtra | undefined,
    fields: readonly Field[],
    options: TransportRequestOptions,
  ): Promise<KiprisPage<T>> {
    const { xml, provenance } = await this.request(
      service,
      operation,
      params,
      extra,
      options,
    );
    const parsed = parseKiprisResponse(xml);
    return {
      items: parsed.items.map((item) => normalize<T>(item, fields)),
      pagination: parsed.pagination,
      provenance,
    };
  }

  private async bibliography(
    service: KiprisService,
    applicationNumber: string,
    options: TransportRequestOptions,
  ): Promise<KiprisBibliography> {
    const { xml, provenance } = await this.request(
      service,
      "getBibliographyDetailInfoSearch",
      { applicationNumber },
      undefined,
      options,
    );
    return { item: parseKiprisBibliography(xml), provenance };
  }

  /** patUtiModInfoSearchSevice/getWordSearch: free text over patents and utility models. */
  searchPatentsWord(
    word: string,
    search: KiprisPatentSearchOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisPatentRow>> {
    return this.search(
      KIPRIS_SERVICES.patents,
      "getWordSearch",
      {
        word,
        patent: flag(search.patent),
        utility: flag(search.utility),
        ...pageParams(search),
      },
      search.extra,
      PATENT_FIELDS,
      options,
    );
  }

  /** patUtiModInfoSearchSevice/getAdvancedSearch: KIPRIS ANDs the supplied fields. */
  searchPatentsAdvanced(
    search: KiprisPatentAdvancedOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisPatentRow>> {
    return this.search(
      KIPRIS_SERVICES.patents,
      "getAdvancedSearch",
      {
        word: search.word,
        inventionTitle: search.inventionTitle,
        astrtCont: search.astrtCont,
        claimScope: search.claimScope,
        applicant: search.applicant,
        inventors: search.inventor,
        ipcNumber: search.ipc,
        applicationDate: search.applicationDate,
        publicationDate: search.publicationDate,
        patent: flag(search.patent),
        utility: flag(search.utility),
        ...pageParams(search),
      },
      search.extra,
      PATENT_FIELDS,
      options,
    );
  }

  /** Search rows for one application number (advanced search on `applicationNumber`). */
  getPatent(
    number: string,
    extra?: KiprisExtra,
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisPatentRow>> {
    return this.search(
      KIPRIS_SERVICES.patents,
      "getAdvancedSearch",
      {
        applicationNumber: number,
        patent: "true",
        utility: "true",
        numOfRows: KIPRIS_DEFAULT_ROWS,
        pageNo: 1,
      },
      extra,
      PATENT_FIELDS,
      options,
    );
  }

  /** patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch: the full nested record. */
  getPatentBibliography(
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<KiprisBibliography> {
    return this.bibliography(
      KIPRIS_SERVICES.patents,
      applicationNumber,
      options,
    );
  }

  /** trademarkInfoSearchService/getWordSearch (upstream `searchString`). */
  searchTrademarksWord(
    word: string,
    search: KiprisPageOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisTrademarkRow>> {
    return this.search(
      KIPRIS_SERVICES.trademarks,
      "getWordSearch",
      { searchString: word, ...pageParams(search) },
      search.extra,
      TRADEMARK_FIELDS,
      options,
    );
  }

  /** trademarkInfoSearchService/getAdvancedSearch, with every status and type flag true by default. */
  searchTrademarksAdvanced(
    search: KiprisTrademarkAdvancedOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisTrademarkRow>> {
    return this.search(
      KIPRIS_SERVICES.trademarks,
      "getAdvancedSearch",
      {
        trademarkName: search.title,
        applicantName: search.applicant,
        classification: search.classification,
        viennaCode: search.viennaCode,
        applicationDate: search.applicationDate,
        registerDate: search.registrationDate,
        ...allTrue(TRADEMARK_FLAGS),
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
    return this.search(
      KIPRIS_SERVICES.trademarks,
      "getAdvancedSearch",
      {
        applicationNumber: number,
        ...allTrue(TRADEMARK_FLAGS),
        numOfRows: KIPRIS_DEFAULT_ROWS,
        pageNo: 1,
      },
      extra,
      TRADEMARK_FIELDS,
      options,
    );
  }

  getTrademarkBibliography(
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<KiprisBibliography> {
    return this.bibliography(
      KIPRIS_SERVICES.trademarks,
      applicationNumber,
      options,
    );
  }

  /** designInfoSearchService/getWordSearch (upstream `articleName`, which also matches applicants and designers). */
  searchDesignsWord(
    word: string,
    search: KiprisPageOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisDesignRow>> {
    return this.search(
      KIPRIS_SERVICES.designs,
      "getWordSearch",
      { articleName: word, ...pageParams(search) },
      search.extra,
      DESIGN_FIELDS,
      options,
    );
  }

  /** designInfoSearchService/getAdvancedSearch, with every status and type flag true by default. */
  searchDesignsAdvanced(
    search: KiprisDesignAdvancedOptions = {},
    options: TransportRequestOptions = {},
  ): Promise<KiprisPage<KiprisDesignRow>> {
    return this.search(
      KIPRIS_SERVICES.designs,
      "getAdvancedSearch",
      {
        articleName: search.articleName,
        applicantName: search.applicant,
        designMainClassification: search.designClassification,
        applicationDate: search.applicationDate,
        registrationDate: search.registrationDate,
        ...allTrue(DESIGN_FLAGS),
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
    return this.search(
      KIPRIS_SERVICES.designs,
      "getAdvancedSearch",
      {
        applicationNumber: number,
        ...allTrue(DESIGN_FLAGS),
        numOfRows: KIPRIS_DEFAULT_ROWS,
        pageNo: 1,
      },
      extra,
      DESIGN_FIELDS,
      options,
    );
  }

  getDesignBibliography(
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<KiprisBibliography> {
    return this.bibliography(
      KIPRIS_SERVICES.designs,
      applicationNumber,
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

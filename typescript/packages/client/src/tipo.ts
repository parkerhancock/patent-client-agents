import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import type { Provenance } from "./models.js";
import { env } from "./runtime/env.js";
import {
  ApiError,
  type ClientOptions,
  ConfigurationError,
  GenericHttpTransport,
  HttpResponseError,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * TIPO (Taiwan) OpenData REST API: 15 GET endpoints of patent, utility-model,
 * design and trademark bibliographic and status records. Bibliographic only:
 * no claims, abstracts or figures. Auth is a `tk` UUID token in the query
 * string, issued by TIPO on application (TIPO_API_KEY). Endpoints and their
 * filters follow the Swagger 2.0 specification archived in references/tipo.
 */
export const TIPO_BASE_URL = "https://cloud.tipo.gov.tw/S220/opdataapi/api";
export const TIPO_SOURCE =
  "Intellectual Property Office, Ministry of Economic Affairs, Taiwan (TIPO/MOEA)";
/** Taiwan Open Government Data License v1.0 attribution. */
export const TIPO_ATTRIBUTION =
  "Source: Intellectual Property Office, Ministry of Economic Affairs, Taiwan (TIPO/MOEA). Licence: Taiwan Open Government Data License v1.0.";
export const TIPO_REGISTRATION_HINT =
  "Request a TIPO OpenData tk token by emailing the Word-form application to ipoid@tipo.gov.tw.";
/** The empirical cap on `top` per request. */
export const TIPO_MAX_TOP = 6000;
export const TIPO_DEFAULT_TOP = 100;

/**
 * Each endpoint's query filters as the specification documents them, less
 * format, top, skip, orderby and tk. TIPO ignores names it does not know and
 * answers with the unfiltered database, so the client refuses them; Python
 * sent appl-no, q, appl-date-from and applicant, none of which exist.
 */
export const TIPO_ENDPOINTS = {
  PatentAppl: {
    description: "專利申請案IPC/LOC及第1申請人國籍資訊",
    required: ["applclass"],
    filters: [
      "applclass",
      "applno",
      "applbdate",
      "appledate",
      "ipcfull",
      "ipcsection",
      "ipcclass",
      "ipcsubclass",
      "ipcmaingroup",
      "ipcgroup",
      "locfull",
      "loclevel1",
      "loclevel2",
    ],
  },
  PatentPub: {
    description: "發明公開案",
    required: [],
    filters: [
      "noticeno",
      "noticebdate",
      "noticeedate",
      "noticebvolisu",
      "noticeevolisu",
      "applno",
      "applbdate",
      "appledate",
      "patentname",
      "ipcfull",
      "ipcsection",
      "ipcclass",
      "ipcsubclass",
      "ipcmaingroup",
      "ipcgroup",
      "applnamec",
      "applnamee",
      "inventornamec",
      "inventornamee",
      "agentnamec",
    ],
  },
  PatentRights: {
    description: "專利權狀態異動資料",
    required: ["applclass"],
    filters: [
      "applclass",
      "publishbdate",
      "applnamec",
      "patentno",
      "noticeno",
      "noticebdate",
      "noticeedate",
      "noticebvolisu",
      "noticeevolisu",
      "publishno",
      "publishedate",
      "publishbvolisu",
      "publishevolisu",
      "applno",
      "applbdate",
      "appledate",
      "patentname",
      "ipcfull",
      "ipcsection",
      "ipcclass",
      "ipcsubclass",
      "ipcmaingroup",
      "ipcgroup",
      "locfull",
      "loclevel1",
      "loclevel2",
      "applnamee",
      "applcountry",
      "inventornamec",
      "inventornamee",
      "inventorcountry",
      "agentnamec",
      "chargeexpirbdate",
      "chargeexpiredate",
    ],
  },
  PatentPriority: {
    description: "專利優先權案",
    required: [],
    filters: [
      "applclass",
      "publishbdate",
      "applnamec",
      "patentno",
      "noticeno",
      "noticebdate",
      "noticeedate",
      "noticebvolisu",
      "noticeevolisu",
      "publishno",
      "publishedate",
      "publishbvolisu",
      "publishevolisu",
      "applno",
      "applbdate",
      "appledate",
      "patentname",
      "ipcfull",
      "ipcsection",
      "ipcclass",
      "ipcsubclass",
      "ipcmaingroup",
      "ipcgroup",
      "locfull",
      "loclevel1",
      "loclevel2",
      "applnamee",
      "applcountry",
      "inventornamec",
      "inventornamee",
      "inventorcountry",
      "agentnamec",
      "chargeexpirbdate",
      "chargeexpiredate",
      "prioritycountry",
      "priorityapplno",
      "prioritybdate",
      "priorityedate",
    ],
  },
  PatentAnnuity: {
    description: "專利案件年費繳納紀錄",
    required: [],
    filters: [
      "applclass",
      "publishbdate",
      "applnamec",
      "patentno",
      "noticeno",
      "noticebdate",
      "noticeedate",
      "noticebvolisu",
      "noticeevolisu",
      "publishno",
      "publishedate",
      "publishbvolisu",
      "publishevolisu",
      "applno",
      "applbdate",
      "appledate",
      "patentname",
      "ipcfull",
      "ipcsection",
      "ipcclass",
      "ipcsubclass",
      "ipcmaingroup",
      "ipcgroup",
      "locfull",
      "loclevel1",
      "loclevel2",
      "applnamee",
      "applcountry",
      "inventornamec",
      "inventornamee",
      "inventorcountry",
      "agentnamec",
      "chargeexpirbdate",
      "chargeexpiredate",
      "chargeexpiryear",
    ],
  },
  PatentTwins: {
    description: "專利一案兩請關聯案件",
    required: ["applclass"],
    filters: [
      "applno",
      "applclass",
      "twinsapplno",
      "patentno",
      "noticeno",
      "noticebdate",
      "noticeedate",
      "noticebvolisu",
      "noticeevolisu",
      "publishno",
      "publishbdate",
      "publishedate",
      "publishbvolisu",
      "publishevolisu",
      "applbdate",
      "appledate",
      "patentname",
      "ipcfull",
      "ipcsection",
      "ipcclass",
      "ipcsubclass",
      "ipcmaingroup",
      "ipcgroup",
      "applnamec",
      "applnamee",
      "applcountry",
      "inventornamec",
      "inventornamee",
      "inventorcountry",
      "agentnamec",
      "chargeexpirbdate",
      "chargeexpiredate",
    ],
  },
  PatentAlteration: {
    description: "專利案件讓與紀錄",
    required: [],
    filters: [
      "applclass",
      "publishbdate",
      "applnamec",
      "patentno",
      "noticeno",
      "noticebdate",
      "noticeedate",
      "noticebvolisu",
      "noticeevolisu",
      "publishno",
      "publishedate",
      "publishbvolisu",
      "publishevolisu",
      "applno",
      "applbdate",
      "appledate",
      "patentname",
      "ipcfull",
      "ipcsection",
      "ipcclass",
      "ipcsubclass",
      "ipcmaingroup",
      "ipcgroup",
      "locfull",
      "loclevel1",
      "loclevel2",
      "applnamee",
      "applcountry",
      "inventornamec",
      "inventornamee",
      "inventorcountry",
      "agentnamec",
      "chargeexpirbdate",
      "chargeexpiredate",
      "transferer",
      "transferere",
      "transferee",
      "transfereee",
    ],
  },
  PatentChange: {
    description: "專利改請案",
    required: [],
    filters: [
      "applclass",
      "publishbdate",
      "applnamec",
      "patentno",
      "noticeno",
      "noticebdate",
      "noticeedate",
      "noticebvolisu",
      "noticeevolisu",
      "publishno",
      "publishedate",
      "publishbvolisu",
      "publishevolisu",
      "applno",
      "applbdate",
      "appledate",
      "patentname",
      "ipcfull",
      "ipcsection",
      "ipcclass",
      "ipcsubclass",
      "ipcmaingroup",
      "ipcgroup",
      "locfull",
      "loclevel1",
      "loclevel2",
      "applnamee",
      "applcountry",
      "inventornamec",
      "inventornamee",
      "inventorcountry",
      "agentnamec",
      "chargeexpirbdate",
      "chargeexpiredate",
      "newapplno",
    ],
  },
  PatentDivide: {
    description: "專利分割案",
    required: ["querytype"],
    filters: [
      "querytype",
      "applclass",
      "patentno",
      "noticeno",
      "noticebdate",
      "noticeedate",
      "noticebvolisu",
      "noticeevolisu",
      "publishno",
      "publishbdate",
      "publishedate",
      "publishbvolisu",
      "publishevolisu",
      "applno",
      "applbdate",
      "appledate",
      "patentname",
      "ipcfull",
      "ipcsection",
      "ipcclass",
      "ipcsubclass",
      "ipcmaingroup",
      "ipcgroup",
      "locfull",
      "loclevel1",
      "loclevel2",
      "applnamec",
      "applnamee",
      "applcountry",
      "inventornamec",
      "inventornamee",
      "inventorcountry",
      "agentnamec",
      "chargeexpirbdate",
      "chargeexpiredate",
      "newapplno",
    ],
  },
  TmarkAppl: {
    description: "商標註冊申請案",
    required: [],
    filters: [
      "applno",
      "applbdate",
      "appledate",
      "tmarkname",
      "tmarkclass",
      "tmarktype",
      "tmarkcolor",
      "goodclasscode",
      "applnamec",
      "applnamee",
      "applcountry",
      "agentname",
    ],
  },
  TmarkRights: {
    description: "商標權狀態異動資料",
    required: [],
    filters: [
      "applno",
      "applbdate",
      "appledate",
      "tmarkname",
      "tmarkclass",
      "tmarktype",
      "tmarkcolor",
      "goodclasscode",
      "applnamec",
      "applnamee",
      "applcountry",
      "agentname",
      "examno",
      "regnoticebdate",
      "regnoticeedate",
      "deadlinebdate",
      "deadlineedate",
    ],
  },
  TmarkPriority: {
    description: "商標案優先權資料",
    required: [],
    filters: [
      "applno",
      "applbdate",
      "appledate",
      "tmarkname",
      "tmarkclass",
      "tmarktype",
      "tmarkcolor",
      "goodclasscode",
      "applnamec",
      "applnamee",
      "applcountry",
      "agentname",
      "examno",
      "regnoticebdate",
      "regnoticeedate",
      "prioritytype",
    ],
  },
  TmarkPics: {
    description: "商標申請案圖庫資料",
    required: [],
    filters: ["applno", "picsbmoddate", "picsemoddate"],
  },
  TmarkChange: {
    description: "商標註冊案移轉紀錄",
    required: [],
    filters: [
      "applno",
      "applbdate",
      "appledate",
      "tmarkname",
      "tmarkclass",
      "tmarktype",
      "tmarkcolor",
      "goodclasscode",
      "applnamec",
      "applnamee",
      "applcountry",
      "agentname",
      "examno",
      "regnoticebdate",
      "regnoticeedate",
      "volno",
      "deadlinebdate",
      "deadlineedate",
      "transfereenamec",
      "transfereenamee",
    ],
  },
  TmarkDivide: {
    description: "商標註冊案分割紀錄",
    required: [],
    filters: ["tmarkname", "examno", "origntmarkclass", "originexamno"],
  },
} as const satisfies Record<
  string,
  {
    description: string;
    required: readonly string[];
    filters: readonly string[];
  }
>;
export type TipoEndpoint = keyof typeof TIPO_ENDPOINTS;
export type TipoFilterValue = string | number | null | undefined;
export type TipoFilters = Record<string, TipoFilterValue>;
/** A row as TIPO sends it (kebab-case keys, "-sequence"), with dates as ISO YYYY-MM-DD. */
export type TipoRow = Record<string, unknown>;

export interface TipoPage {
  endpoint: TipoEndpoint;
  rows: TipoRow[];
  total_count: number;
  top: number;
  skip: number;
  order_by: string | null;
  /** TIPO's message, such as 輸入條件查無資料 (no data for these conditions). */
  message: string;
  /** The dataset's build date ("-create-date"), ISO. */
  created: string | null;
  more_available: boolean;
  provenance: Provenance;
}

export type TipoErrorCode =
  | "AUTHENTICATION_FAILED"
  | "INVALID_REQUEST"
  | "UPSTREAM_ERROR"
  | "INVALID_RESPONSE";
/** Safe TIPO error: HTTP status, TIPO status and message, never the token. */
export class TipoError extends ApiError {
  override name = "TipoError";
  constructor(
    message: string,
    status: number,
    code: TipoErrorCode,
    public readonly tipoStatus: string | null = null,
  ) {
    super(message, status, code);
  }
}

export interface TipoQueryOptions extends TransportRequestOptions {
  filters?: TipoFilters;
  /** Rows per request, at most 6,000. Defaults to 100. */
  top?: number;
  skip?: number;
  orderby?: string;
}
export interface TipoClientOptions extends Omit<ClientOptions, "apiKey"> {
  /** TIPO-issued UUID token; defaults to TIPO_API_KEY. */
  tk?: string;
  apiKey?: string;
}

const SCALARS = new Set([
  "version",
  "status",
  "message",
  "top",
  "skip",
  "order-by",
  "total-count",
]);
const envelopeSchema = z.looseObject({
  status: z.string(),
  message: z.string().nullish(),
  top: z.number().int().nonnegative().nullish(),
  skip: z.number().int().nonnegative().nullish(),
  "order-by": z.string().nullish(),
  "total-count": z.number().int().nonnegative().nullish(),
});
const DATE = /^(\d{4})\/(\d{2})\/(\d{2})$/;

/** YYYY/MM/DD strings anywhere in a row become ISO dates; all-zero placeholders become null. */
function isoDates(value: unknown): unknown {
  if (typeof value === "string") {
    const match = DATE.exec(value);
    if (!match) return value;
    return /^0+$/.test(match.slice(1).join(""))
      ? null
      : match.slice(1).join("-");
  }
  if (Array.isArray(value)) return value.map(isoDates);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, isoDates(item)]),
    );
  return value;
}

/** A filter date as YYYY/MM/DD, from that form, ISO YYYY-MM-DD or YYYYMMDD; TIPO rejects ISO. */
export function tipoDate(value: string): string {
  const match = /^(\d{4})[-/]?(\d{2})[-/]?(\d{2})$/.exec(value.trim());
  if (!match)
    throw new TypeError(`Dates must be YYYY-MM-DD or YYYY/MM/DD: ${value}`);
  return `${match[1]}/${match[2]}/${match[3]}`;
}
const isDateFilter = (name: string) =>
  /(?:b|e)date$|^picsbmoddate$|^picsemoddate$/.test(name);

function searchParams(
  endpoint: TipoEndpoint,
  filters: TipoFilters,
): Record<string, string> {
  const allowed: readonly string[] = TIPO_ENDPOINTS[endpoint].filters;
  const out: Record<string, string> = {};
  for (const [name, raw] of Object.entries(filters)) {
    if (raw === undefined || raw === null || String(raw).trim() === "")
      continue;
    if (!allowed.includes(name))
      throw new TypeError(
        `${endpoint} has no filter "${name}"; TIPO would ignore it and return unfiltered rows. Documented filters: ${allowed.join(", ")}.`,
      );
    let value = String(raw).trim();
    if (isDateFilter(name)) value = tipoDate(value);
    // Nice classes are three digits: 017 matches, 17 does not.
    if (name === "goodclasscode" && /^\d{1,2}$/.test(value))
      value = value.padStart(3, "0");
    out[name] = value;
  }
  return out;
}

/**
 * The rows inside the one endpoint-named object (tw-patent-applI,
 * tmarkappl, ...). Keys starting "-" are metadata. Where it holds two lists
 * (PatentTwins: twins-announceds and twins-approveds), each row is tagged
 * with its list; Python kept only the first.
 */
function extract(body: Record<string, unknown>) {
  const containers = Object.entries(body).filter(
    ([key, value]) =>
      !SCALARS.has(key) &&
      value &&
      typeof value === "object" &&
      !Array.isArray(value),
  );
  if (containers.length !== 1) return null;
  const container = (containers[0] as [string, Record<string, unknown>])[1];
  const lists = Object.entries(container).filter(
    ([key]) => !key.startsWith("-"),
  );
  if (!lists.every(([, value]) => Array.isArray(value))) return null;
  const rows: TipoRow[] = [];
  for (const [key, list] of lists as [string, unknown[]][])
    for (const row of list) {
      if (!row || typeof row !== "object" || Array.isArray(row)) return null;
      const converted = isoDates(row) as TipoRow;
      rows.push(lists.length > 1 ? { list: key, ...converted } : converted);
    }
  const created = container["-create-date"];
  return {
    rows,
    created:
      typeof created === "string" ? (isoDates(created) as string | null) : null,
  };
}

/** TIPO OpenData: patents, utility models, designs and trademarks (bibliographic only). */
export class TipoClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private readonly tk: string;
  constructor(options: TipoClientOptions = {}) {
    super();
    const tk = (options.tk ?? options.apiKey ?? env("TIPO_API_KEY"))?.trim();
    if (!tk)
      throw new ConfigurationError(
        `Set TIPO_API_KEY, or pass tk, to use TIPO OpenData. ${TIPO_REGISTRATION_HINT}`,
      );
    this.tk = tk;
    const { tk: _tk, apiKey: _key, ...transport } = options;
    this.http = new GenericHttpTransport({
      ...transport,
      // A trailing slash, so endpoint names resolve under /api/ rather than replacing it.
      baseUrl: (options.baseUrl ?? TIPO_BASE_URL).replace(/\/?$/, "/"),
      sourceName: TIPO_SOURCE,
      cache: { name: "tipo_opdata" },
      headers: { accept: "application/json" },
    });
  }

  /** One page of an endpoint. Unknown filter names are refused rather than ignored. */
  async query(
    endpoint: TipoEndpoint,
    options: TipoQueryOptions = {},
  ): Promise<TipoPage> {
    if (!Object.hasOwn(TIPO_ENDPOINTS, endpoint))
      throw new TypeError(`Unknown TIPO endpoint: ${endpoint}`);
    const { filters = {}, top, skip, orderby, ...request } = options;
    const size = z
      .number()
      .int()
      .min(1)
      .parse(top ?? TIPO_DEFAULT_TOP);
    const offset = z
      .number()
      .int()
      .min(0)
      .parse(skip ?? 0);
    const params = {
      format: "json",
      top: String(Math.min(size, TIPO_MAX_TOP)),
      skip: String(offset),
      ...(orderby ? { orderby } : {}),
      ...searchParams(endpoint, filters),
      tk: this.tk,
    };
    let result: Awaited<ReturnType<GenericHttpTransport["json"]>>;
    try {
      result = await this.http.json("GET", endpoint, {
        ...request,
        searchParams: params,
        readErrorBody: true,
      });
    } catch (error) {
      throw translate(error);
    }
    const parsed = envelopeSchema.safeParse(result.data);
    if (!parsed.success)
      throw new TipoError(
        `TIPO ${endpoint} returned an unexpected response.`,
        result.status,
        "INVALID_RESPONSE",
      );
    const body = parsed.data;
    const message = body.message ?? "";
    if (body.status === "sample")
      throw new TipoError(
        `TIPO rejected the tk token and served sample data instead (${message}). ${TIPO_REGISTRATION_HINT}`,
        result.status,
        "AUTHENTICATION_FAILED",
        body.status,
      );
    if (body.status !== "ok")
      throw new TipoError(
        `TIPO ${endpoint} returned status "${body.status}"${message ? `: ${message}` : ""}.`,
        result.status,
        "UPSTREAM_ERROR",
        body.status,
      );
    const extracted = extract(result.data as Record<string, unknown>);
    if (!extracted)
      throw new TipoError(
        `TIPO ${endpoint} returned rows in an unexpected shape.`,
        result.status,
        "INVALID_RESPONSE",
        body.status,
      );
    const total = body["total-count"] ?? extracted.rows.length;
    const start = body.skip ?? offset;
    return {
      endpoint,
      rows: extracted.rows,
      total_count: total,
      top: body.top ?? size,
      skip: start,
      order_by: body["order-by"] ?? null,
      message,
      created: extracted.created,
      more_available: start + extracted.rows.length < total,
      provenance: result.provenance,
    };
  }

  /** Every row past the 6,000-row cap, a page at a time, until a short page. */
  async *paginate(
    endpoint: TipoEndpoint,
    options: TipoQueryOptions = {},
  ): AsyncGenerator<TipoRow> {
    const size = Math.min(options.top ?? TIPO_MAX_TOP, TIPO_MAX_TOP);
    let skip = options.skip ?? 0;
    for (;;) {
      const page = await this.query(endpoint, { ...options, top: size, skip });
      yield* page.rows;
      if (page.rows.length < size) return;
      skip += size;
    }
  }

  /** Rows for one application number on an endpoint that documents `applno`; it matches exactly. */
  getByApplicationNumber(
    endpoint: TipoEndpoint,
    applicationNumber: string,
    options: TipoQueryOptions = {},
  ): Promise<TipoPage> {
    const allowed: readonly string[] = TIPO_ENDPOINTS[endpoint]?.filters ?? [];
    if (!allowed.includes("applno"))
      return Promise.reject(
        new TypeError(`${endpoint} cannot be filtered by application number.`),
      );
    const number = applicationNumber.trim();
    if (!number)
      return Promise.reject(new TypeError("applicationNumber is required."));
    return this.query(endpoint, {
      ...options,
      filters: { ...options.filters, applno: number },
    });
  }
}

function translate(error: unknown): unknown {
  if (!(error instanceof ApiError) || error instanceof TipoError) return error;
  if (error instanceof HttpResponseError) {
    let message = "";
    try {
      const body = JSON.parse(error.bodyText) as { message?: unknown };
      if (typeof body.message === "string") message = body.message;
    } catch {}
    return new TipoError(
      `TIPO returned HTTP ${error.status}${message ? `: ${message}` : ""}.`,
      error.status,
      error.status === 400 ? "INVALID_REQUEST" : "UPSTREAM_ERROR",
      message ? "error" : null,
    );
  }
  return error;
}

import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import {
  type JpoDocumentKind,
  type JpoIpType,
  type JpoParsedBundle,
  parseJpoDocumentBundle,
} from "./jpo-documents.js";
import type { Provenance } from "./models.js";
import { env } from "./runtime/env.js";
import {
  ApiError,
  type ClientOptions,
  ConfigurationError,
  GenericHttpTransport,
  type TransportRequestOptions,
  type TransportResult,
} from "./transport.js";

export * from "./jpo-documents.js";

/**
 * JPO Patent Information Retrieval API (handbook v14): progress, priority,
 * applicant, number cross-reference, registration, J-PlatPat link and
 * document-bundle endpoints for patents, designs and trademarks, plus three
 * patent-only endpoints. Credentials are JPO-issued (JPO_API_USERNAME /
 * JPO_API_PASSWORD) and exchanged for a bearer token by password grant.
 * Shapes follow the live API as Python's models record it, not the OpenAPI
 * description, which is wrong in several places.
 */
export const JPO_BASE_URL = "https://ip-data.jpo.go.jp";
export const JPO_SOURCE = "Japan Patent Office (JPO)";
/** Handbook v14 §3: at most 10 requests a minute across the three APIs; daily caps are per endpoint, server side. */
export const JPO_RATE_LIMIT = { requests: 10, windowMs: 60_000 } as const;

export const JPO_STATUS = {
  SUCCESS: "100",
  NO_DATA: "107",
  NO_DOCUMENT: "108",
  UNAVAILABLE_NUMBER: "111",
  DAILY_LIMIT_EXCEEDED: "203",
  INVALID_PARAMETER: "204",
  INVALID_CHARACTERS: "208",
  INVALID_TOKEN: "210",
  INVALID_AUTH: "212",
  URL_NOT_FOUND: "301",
  TIMEOUT: "302",
  CONCENTRATED_ACCESS: "303",
  INVALID_REQUEST: "400",
  UNEXPECTED_ERROR: "999",
} as const;
/** 107, 108 and 111 mean "no result", not failure. */
const EMPTY_STATUS = new Set<string>([
  JPO_STATUS.NO_DATA,
  JPO_STATUS.NO_DOCUMENT,
  JPO_STATUS.UNAVAILABLE_NUMBER,
]);

export type JpoErrorCode =
  | "RATE_LIMITED"
  | "AUTHENTICATION_FAILED"
  | "INVALID_REQUEST"
  | "NOT_FOUND"
  | "UPSTREAM_ERROR"
  | "INVALID_RESPONSE";
/** Safe JPO error: HTTP status, JPO status code and JPO's message, never tokens or credentials. */
export class JpoError extends ApiError {
  override name = "JpoError";
  constructor(
    message: string,
    status: number,
    code: JpoErrorCode,
    /** The `result.statusCode` JPO returned, when there was one. */
    public readonly jpoStatus: string | null = null,
    public readonly retryable = false,
  ) {
    super(message, status, code);
  }
}

export type JpoCaseNumberKind = "application" | "publication" | "registration";
export type JpoPctKind =
  | "international_application"
  | "international_publication";

// ── Models ───────────────────────────────────────────────────────────
// Field names are Python's (snake_case); the wire key is the camelCase form
// unless ALIASES says otherwise. Absent text is "", as in Python. Upstream
// keys no model names are kept under their own names.

type Spec = { readonly [field: string]: FieldSpec };
type FieldSpec =
  | "text"
  | "record"
  | { readonly list: Spec }
  | { readonly one: Spec };
type Model<S extends Spec> = {
  -readonly [K in keyof S]: S[K] extends "text"
    ? string
    : S[K] extends "record"
      ? Record<string, unknown>
      : S[K] extends { list: infer M extends Spec }
        ? Model<M>[]
        : S[K] extends { one: infer M extends Spec }
          ? Model<M> | null
          : never;
} & { [upstream: string]: unknown };
const text = <const K extends string>(...keys: K[]) =>
  Object.fromEntries(keys.map((k) => [k, "text"])) as { [P in K]: "text" };

const ALIASES: Record<string, string> = {
  ad_publication_number: "ADPublicationNumber",
  ad_national_publication_number: "ADNationalPublicationNumber",
  appeal_trial_decision_date: "appealTrialDecisiondDate",
};
const wireKey = (field: string) =>
  ALIASES[field] ??
  field.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase());

const APPLICANT = text(
  "applicant_attorney_cd",
  "repeat_number",
  "name",
  "applicant_attorney_class",
);
const PRIORITY = text(
  "paris_priority_application_number",
  "paris_priority_date",
  "paris_priority_country_cd",
  "national_priority_law_cd",
  "national_priority_application_number",
  "national_priority_international_application_number",
  "national_priority_date",
);
const PARENT = text(
  "parent_application_number",
  "filing_date",
  "parent_application_category",
  "parent_application_law_code",
);
const DIVISIONAL = text(
  "application_number",
  "publication_number",
  "ad_publication_number",
  "national_publication_number",
  "ad_national_publication_number",
  "registration_number",
  "international_application_number",
  "international_publication_number",
  "erasure_identifier",
  "expire_date",
  "disappearance_date",
  "divisional_generation",
);
const BIBLIOGRAPHY = {
  ...text("number_type", "number"),
  document_list: {
    list: text(
      "legal_date",
      "irir_flg",
      "availability_flag",
      "document_code",
      "document_description",
      "document_number",
      "version_number",
      "document_separator",
      "number_of_pages",
      "size_of_document",
    ),
  },
} as const;
const GOODS = text("goods_service_class", "goods_service_name", "similar_code");
const PATENT_PROGRESS = {
  ...text("application_number", "invention_title"),
  applicant_attorney: { list: APPLICANT },
  ...text(
    "filing_date",
    "publication_number",
    "ad_publication_number",
    "national_publication_number",
    "ad_national_publication_number",
    "publication_date",
    "registration_number",
    "registration_date",
    "international_application_number",
    "international_publication_number",
    "international_publication_date",
    "erasure_identifier",
    "expire_date",
    "disappearance_date",
  ),
  priority_right_information: { list: PRIORITY },
  parent_application_information: { one: PARENT },
  divisional_application_information: { list: DIVISIONAL },
  bibliography_information: { list: BIBLIOGRAPHY },
} as const;
const DESIGN_PROGRESS = {
  ...text("application_number", "design_article", "design_class"),
  applicant_attorney: { list: APPLICANT },
  ...text(
    "filing_date",
    "publication_date",
    "registration_number",
    "registration_date",
    "principal_design_application_number",
    "erasure_identifier",
    "expire_date",
    "disappearance_date",
  ),
  priority_right_information: { list: PRIORITY },
  parent_application_information: { one: PARENT },
  bibliography_information: { list: BIBLIOGRAPHY },
} as const;
const TRADEMARK_PROGRESS = {
  application_number: "text",
  applicant_attorney: { list: APPLICANT },
  ...text(
    "filing_date",
    "publication_date",
    "registration_number",
    "registration_date",
    "erasure_identifier",
    "expire_date",
    "disappearance_date",
    "trademark_for_display",
  ),
  transliteration: "record",
  vienna_class: "record",
  goods_service_information: { list: GOODS },
  priority_right_information: { list: PRIORITY },
  parent_application_information: { one: PARENT },
  bibliography_information: { list: BIBLIOGRAPHY },
} as const;
const DIVISIONAL_INFO = {
  application_number: "text",
  parent_application_information: { one: PARENT },
  divisional_application_information: { list: DIVISIONAL },
} as const;
const NUMBER_REFERENCE = text(
  "application_number",
  "publication_number",
  "national_publication_number",
  "registration_number",
  "international_publication_number",
  "international_registration_number",
  "design_number",
);
const CITED_DOCUMENTS = {
  application_number: "text",
  patent_doc: {
    list: text(
      "draft_date",
      "citation_type",
      "citation_order",
      "document_number",
    ),
  },
  non_patent_doc: {
    list: text(
      "draft_date",
      "citation_type",
      "citation_order",
      "document_type",
      "author_name",
      "paper_title",
      "publication_name",
      "issue_country_cd",
      "publisher",
      "issue_date",
      "issue_date_type",
      "issue_number",
      "citation_pages",
    ),
  },
} as const;
const REGISTRATION = {
  ...text(
    "application_number",
    "filing_date",
    "registration_number",
    "registration_date",
    "decision_date",
    "appeal_trial_decision_date",
  ),
  right_person_information: {
    list: text("right_person_cd", "right_person_name"),
  },
  ...text(
    "invention_title",
    "number_of_claims",
    "expire_date",
    "next_pension_payment_date",
    "last_payment_yearly",
    "erasure_identifier",
    "disappearance_date",
    "update_date",
    "design_article",
    "trademark_for_display",
  ),
  transliteration: "record",
  vienna_class: "record",
  goods_service_information: { list: GOODS },
} as const;
const PCT_NATIONAL_PHASE = text(
  "application_number",
  "international_application_number",
  "international_publication_number",
);

export type JpoApplicantAttorney = Model<typeof APPLICANT>;
export type JpoPriorityInfo = Model<typeof PRIORITY>;
export type JpoPatentProgress = Model<typeof PATENT_PROGRESS>;
export type JpoDesignProgress = Model<typeof DESIGN_PROGRESS>;
export type JpoTrademarkProgress = Model<typeof TRADEMARK_PROGRESS>;
export type JpoProgress = {
  patent: JpoPatentProgress;
  design: JpoDesignProgress;
  trademark: JpoTrademarkProgress;
};
export type JpoDivisionalInfo = Model<typeof DIVISIONAL_INFO>;
export type JpoNumberReference = Model<typeof NUMBER_REFERENCE>;
export type JpoCitedDocuments = Model<typeof CITED_DOCUMENTS>;
export type JpoRegistrationInfo = Model<typeof REGISTRATION>;
export type JpoPctNationalPhase = Model<typeof PCT_NATIONAL_PHASE>;
const PROGRESS_SPECS = {
  patent: PATENT_PROGRESS,
  design: DESIGN_PROGRESS,
  trademark: TRADEMARK_PROGRESS,
} as const;

function invalid(detail: string): JpoError {
  return new JpoError(
    `JPO returned an unexpected response: ${detail}.`,
    200,
    "INVALID_RESPONSE",
  );
}
function normalize<S extends Spec>(
  spec: S,
  raw: unknown,
  path = "data",
): Model<S> {
  if (!raw || typeof raw !== "object" || Array.isArray(raw))
    throw invalid(`${path} is not an object`);
  const source = raw as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  const used = new Set<string>();
  for (const [field, kind] of Object.entries(spec)) {
    const key = wireKey(field);
    used.add(key);
    const value = source[key];
    const at = `${path}.${key}`;
    if (kind === "text") {
      if (value === undefined || value === null) out[field] = "";
      else if (typeof value === "string") out[field] = value;
      else if (typeof value === "number") out[field] = String(value);
      else throw invalid(`${at} is not text`);
    } else if (kind === "record") {
      if (value === undefined || value === null) out[field] = {};
      else if (typeof value === "object" && !Array.isArray(value))
        out[field] = value;
      else throw invalid(`${at} is not an object`);
    } else if ("list" in kind) {
      if (value === undefined || value === null) out[field] = [];
      else if (Array.isArray(value))
        out[field] = value.map((item, i) =>
          normalize(kind.list, item, `${at}[${i}]`),
        );
      else throw invalid(`${at} is not a list`);
    } else
      out[field] =
        value === undefined || value === null
          ? null
          : normalize(kind.one, value, at);
  }
  for (const [key, value] of Object.entries(source))
    if (!used.has(key) && !(key in out)) out[key] = value;
  return out as Model<S>;
}

// ── Results ──────────────────────────────────────────────────────────

export interface JpoResult<T> {
  /** null (or [] for lists) when JPO reports no data: status 107, 108 or 111. */
  data: T;
  /** JPO's `result.statusCode`. */
  status_code: string;
  /** JPO's `remainAccessCount` for this endpoint today, when reported. */
  remaining_access_count: string | null;
  provenance: Provenance;
}
/** A document bundle: the ZIP inline (under 10 MB) or JPO's URL for a larger one. Both empty means no documents. */
export interface JpoDocumentBundle {
  application_number: string;
  ip_type: JpoIpType;
  doc_kind: JpoDocumentKind;
  zip: Uint8Array | null;
  /** JPO's own link to an oversize archive. Treat it as a credential; fetch it with downloadOversizeBundle. */
  download_url: string | null;
  content_type: string;
  status_code: string;
  remaining_access_count: string | null;
  provenance: Provenance;
}

const envelopeSchema = z.looseObject({
  result: z.looseObject({
    statusCode: z.union([z.string(), z.number()]).transform(String),
    errorMessage: z.string().nullish(),
    remainAccessCount: z.union([z.string(), z.number()]).nullish(),
    data: z.record(z.string(), z.unknown()).nullish(),
  }),
});
type Envelope = z.infer<typeof envelopeSchema>["result"];

/** Map a JPO status code to an error; 100 and the empty codes pass. */
function checkStatus(result: Envelope, context: string): void {
  const code = result.statusCode;
  if (code === JPO_STATUS.SUCCESS || EMPTY_STATUS.has(code)) return;
  const detail = result.errorMessage ? `: ${result.errorMessage}` : "";
  const fail = (message: string, kind: JpoErrorCode, retryable = false) =>
    new JpoError(`${message}${detail}`, 200, kind, code, retryable);
  switch (code) {
    case JPO_STATUS.DAILY_LIMIT_EXCEEDED:
      throw fail(
        `JPO daily access limit exceeded for ${context}`,
        "RATE_LIMITED",
      );
    case JPO_STATUS.CONCENTRATED_ACCESS:
      throw fail(
        `JPO API access is concentrated; retry ${context} later`,
        "RATE_LIMITED",
        true,
      );
    case JPO_STATUS.INVALID_TOKEN:
      throw fail(
        "JPO rejected the access token",
        "AUTHENTICATION_FAILED",
        true,
      );
    case JPO_STATUS.INVALID_AUTH:
      throw fail("JPO rejected the authentication", "AUTHENTICATION_FAILED");
    case JPO_STATUS.INVALID_PARAMETER:
    case JPO_STATUS.INVALID_CHARACTERS:
    case JPO_STATUS.INVALID_REQUEST:
      throw fail(`JPO rejected the request for ${context}`, "INVALID_REQUEST");
    case JPO_STATUS.URL_NOT_FOUND:
      throw fail(`JPO API URL not found for ${context}`, "NOT_FOUND");
    case JPO_STATUS.TIMEOUT:
      throw fail(`JPO timed out on ${context}`, "UPSTREAM_ERROR", true);
    default:
      // Python treated unknown codes as data; an unrecognized status is not a record.
      throw fail(
        `JPO returned status ${code} for ${context}`,
        "UPSTREAM_ERROR",
        code === JPO_STATUS.UNEXPECTED_ERROR,
      );
  }
}

// ── Token and rate limit, shared across clients in the process ──────

class JpoToken {
  private header?: string;
  private expiresAt = 0;
  private pending: Promise<string> | undefined;
  constructor(
    private readonly http: GenericHttpTransport,
    private readonly form: Record<string, string>,
  ) {}
  /** The cached token until a minute before expiry, measured on the local clock. */
  current(): Promise<string> {
    if (this.header && Date.now() < this.expiresAt - 60_000)
      return Promise.resolve(this.header);
    return this.refresh();
  }
  /** Replace `stale` unless another caller already did; single-flight. */
  refresh(stale?: string): Promise<string> {
    if (stale && this.header && this.header !== stale)
      return Promise.resolve(this.header);
    this.pending ??= this.request().finally(() => {
      this.pending = undefined;
    });
    return this.pending;
  }
  private async request(): Promise<string> {
    let result: TransportResult<unknown>;
    try {
      result = await this.http.json("POST", "/auth/token", {
        form: this.form,
        cache: false,
      });
    } catch (error) {
      if (error instanceof ApiError && [400, 401, 403].includes(error.status))
        throw new JpoError(
          "JPO rejected the configured credentials.",
          error.status,
          "AUTHENTICATION_FAILED",
        );
      throw error;
    }
    const parsed = z
      .looseObject({
        access_token: z.string().min(1),
        expires_in: z.coerce.number().positive().default(3600),
      })
      .safeParse(result.data);
    if (!parsed.success)
      throw new JpoError(
        "JPO returned an invalid token response.",
        result.status,
        "INVALID_RESPONSE",
      );
    this.header = `Bearer ${parsed.data.access_token}`;
    this.expiresAt = Date.now() + parsed.data.expires_in * 1000;
    return this.header;
  }
}

/** Sliding-window limiter: callers wait in order until the window has room. */
class SlidingWindow {
  private readonly stamps: number[] = [];
  private tail: Promise<void> = Promise.resolve();
  constructor(
    private readonly requests: number,
    private readonly windowMs: number,
  ) {}
  acquire(signal?: AbortSignal): Promise<void> {
    const turn = this.tail.then(async () => {
      for (;;) {
        signal?.throwIfAborted();
        const now = Date.now();
        while (
          this.stamps.length &&
          (this.stamps[0] ?? 0) <= now - this.windowMs
        )
          this.stamps.shift();
        if (this.stamps.length < this.requests) {
          this.stamps.push(now);
          return;
        }
        const wait = (this.stamps[0] ?? now) + this.windowMs - now;
        await new Promise<void>((resolve, reject) => {
          const abort = () => {
            clearTimeout(timer);
            reject(signal?.reason);
          };
          const timer = setTimeout(() => {
            signal?.removeEventListener("abort", abort);
            resolve();
          }, wait);
          signal?.addEventListener("abort", abort, { once: true });
        });
      }
    });
    this.tail = turn.catch(() => {});
    return turn;
  }
}

// Python's process_shared: one token per account and one budget per host.
const tokens = new Map<string, JpoToken>();
const windows = new Map<string, SlidingWindow>();

export interface JpoClientOptions extends Omit<ClientOptions, "apiKey"> {
  /** JPO-issued username; defaults to JPO_API_USERNAME. */
  username?: string;
  /** JPO-issued password; defaults to JPO_API_PASSWORD. */
  password?: string;
  /** Requests per window shared by every client on this origin; false disables it (tests). */
  rateLimit?: { requests: number; windowMs: number } | false;
}

const ipTypeSchema = z.enum(["patent", "design", "trademark"]);
const docKindSchema = z.enum(["application", "mailed", "refusal"]);
const caseKindSchema = z.enum(["application", "publication", "registration"]);
const pctKindSchema = z.enum([
  "international_application",
  "international_publication",
]);
const DOCUMENT_ENDPOINTS: Record<JpoDocumentKind, string> = {
  application: "app_doc_cont_opinion_amendment",
  mailed: "app_doc_cont_refusal_reason_decision",
  refusal: "app_doc_cont_refusal_reason",
};
function segment(value: string, name: string) {
  const trimmed = value.trim();
  if (!trimmed) throw new TypeError(`${name} is required.`);
  return encodeURIComponent(trimmed);
}
/** JPO's oversize-bundle links point at JPO hosts; anything else is refused. */
function jpoHost(url: URL) {
  return url.hostname === "jpo.go.jp" || url.hostname.endsWith(".jpo.go.jp");
}

/** JPO Patent Information Retrieval API for patents, designs and trademarks. */
export class JpoClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private readonly token: JpoToken;
  private readonly window: SlidingWindow | undefined;
  constructor(options: JpoClientOptions = {}) {
    super();
    const username = (options.username ?? env("JPO_API_USERNAME"))?.trim();
    const password = options.password ?? env("JPO_API_PASSWORD");
    if (!username || !password)
      throw new ConfigurationError(
        "Set JPO_API_USERNAME and JPO_API_PASSWORD, or pass username and password, to use the JPO API.",
      );
    const { username: _u, password: _p, rateLimit, ...transport } = options;
    this.http = new GenericHttpTransport({
      ...transport,
      baseUrl: options.baseUrl ?? JPO_BASE_URL,
      sourceName: JPO_SOURCE,
      cache: { name: "jpo" },
      headers: { accept: "application/json, application/zip" },
    });
    const origin = new URL(options.baseUrl ?? JPO_BASE_URL).origin;
    const account = `${origin}\0${username}\0${password}`;
    let token = tokens.get(account);
    if (!token) {
      token = new JpoToken(this.http, {
        grant_type: "password",
        username,
        password,
      });
      tokens.set(account, token);
    }
    this.token = token;
    if (rateLimit !== false) {
      const { requests, windowMs } = rateLimit ?? JPO_RATE_LIMIT;
      const key = `${origin}\0${requests}\0${windowMs}`;
      this.window = windows.get(key) ?? new SlidingWindow(requests, windowMs);
      windows.set(key, this.window);
    }
  }

  /** Rate-limited, authorized GET; one token refresh when JPO rejects the token. */
  private async get(
    path: string,
    options: TransportRequestOptions = {},
  ): Promise<TransportResult<Uint8Array>> {
    const send = async (authorization: string) => {
      await this.window?.acquire(options.signal);
      const headers = new Headers(options.headers);
      headers.set("authorization", authorization);
      return this.http.bytes("GET", `/api${path}`, { ...options, headers });
    };
    const rejected = (error: unknown) =>
      error instanceof ApiError &&
      !(error instanceof JpoError) &&
      (error.status === 401 || error.status === 403);
    const authorization = await this.token.current();
    try {
      return await send(authorization);
    } catch (error) {
      if (!rejected(error)) throw translate(error);
    }
    try {
      return await send(await this.token.refresh(authorization));
    } catch (error) {
      if (rejected(error))
        throw new JpoError(
          "JPO rejected an access token after refresh.",
          (error as ApiError).status,
          "AUTHENTICATION_FAILED",
        );
      throw translate(error);
    }
  }
  private envelope(bytes: Uint8Array, context: string): Envelope {
    let body: unknown;
    try {
      body = JSON.parse(new TextDecoder().decode(bytes));
    } catch {
      throw invalid(`${context} is not JSON`);
    }
    const parsed = envelopeSchema.safeParse(body);
    if (!parsed.success) throw invalid(`${context} has no result envelope`);
    return parsed.data.result;
  }
  /** GET a JSON endpoint, retrying once with a new token on status 210. */
  private async call<T>(
    path: string,
    context: string,
    read: (data: Record<string, unknown>) => T,
    empty: T,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<T>> {
    let response = await this.get(path, options);
    let result = this.envelope(response.data, context);
    if (result.statusCode === JPO_STATUS.INVALID_TOKEN) {
      await this.token.refresh();
      response = await this.get(path, { ...options, cache: false });
      result = this.envelope(response.data, context);
    }
    checkStatus(result, context);
    const hasData = !EMPTY_STATUS.has(result.statusCode) && result.data;
    return {
      data: hasData ? read(result.data as Record<string, unknown>) : empty,
      status_code: result.statusCode,
      remaining_access_count:
        result.remainAccessCount == null
          ? null
          : String(result.remainAccessCount),
      provenance: response.provenance,
    };
  }

  /** `app_progress` or, with `simple`, `app_progress_simple` (no priority, parent or divisional sections). */
  async getProgress<T extends JpoIpType>(
    ipType: T,
    applicationNumber: string,
    options: TransportRequestOptions & { simple?: boolean } = {},
  ): Promise<JpoResult<JpoProgress[T] | null>> {
    const ip = ipTypeSchema.parse(ipType) as T;
    const { simple, ...request } = options;
    const endpoint = simple ? "app_progress_simple" : "app_progress";
    return this.call(
      `/${ip}/v1/${endpoint}/${segment(applicationNumber, "applicationNumber")}`,
      `${ip} progress`,
      (data) => normalize(PROGRESS_SPECS[ip], data) as JpoProgress[T],
      null,
      request,
    );
  }
  /** `priority_right_app_info`: Paris and domestic priority claims. */
  async getPriorityInfo(
    ipType: JpoIpType,
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<JpoPriorityInfo[]>> {
    const ip = ipTypeSchema.parse(ipType);
    return this.call(
      `/${ip}/v1/priority_right_app_info/${segment(applicationNumber, "applicationNumber")}`,
      `${ip} priority`,
      (data) =>
        normalize({ priority_right_information: { list: PRIORITY } }, data)
          .priority_right_information,
      [],
      options,
    );
  }
  /** `applicant_attorney_cd`: the registered name for a 9-digit applicant/attorney code. */
  async getApplicantByCode(
    ipType: JpoIpType,
    code: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<string | null>> {
    const ip = ipTypeSchema.parse(ipType);
    return this.call(
      `/${ip}/v1/applicant_attorney_cd/${segment(code, "code")}`,
      `${ip} applicant by code`,
      (data) =>
        normalize({ applicant_attorney_name: "text" }, data)
          .applicant_attorney_name || null,
      null,
      options,
    );
  }
  /** `applicant_attorney`: codes for an exactly matching registered name; partial names find nothing. */
  async getApplicantByName(
    ipType: JpoIpType,
    name: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<JpoApplicantAttorney[]>> {
    const ip = ipTypeSchema.parse(ipType);
    return this.call(
      `/${ip}/v1/applicant_attorney/${segment(name, "name")}`,
      `${ip} applicant by name`,
      (data) =>
        normalize({ applicant_attorney: { list: APPLICANT } }, data)
          .applicant_attorney,
      [],
      options,
    );
  }
  /** `case_number_reference`: application, publication and registration numbers of one record. */
  async getNumberReference(
    ipType: JpoIpType,
    kind: JpoCaseNumberKind,
    number: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<JpoNumberReference | null>> {
    const ip = ipTypeSchema.parse(ipType);
    const k = caseKindSchema.parse(kind);
    return this.call(
      `/${ip}/v1/case_number_reference/${k}/${segment(number, "number")}`,
      `${ip} number reference`,
      (data) => normalize(NUMBER_REFERENCE, data),
      null,
      options,
    );
  }
  /** `registration_info`: the granted-rights record. */
  async getRegistrationInfo(
    ipType: JpoIpType,
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<JpoRegistrationInfo | null>> {
    const ip = ipTypeSchema.parse(ipType);
    return this.call(
      `/${ip}/v1/registration_info/${segment(applicationNumber, "applicationNumber")}`,
      `${ip} registration`,
      (data) => normalize(REGISTRATION, data),
      null,
      options,
    );
  }
  /** `jpp_fixed_address`: the J-PlatPat permalink. The live key is URL, not the documented jplatpatUrl. */
  async getJplatpatUrl(
    ipType: JpoIpType,
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<string | null>> {
    const ip = ipTypeSchema.parse(ipType);
    return this.call(
      `/${ip}/v1/jpp_fixed_address/${segment(applicationNumber, "applicationNumber")}`,
      `${ip} J-PlatPat URL`,
      (data) => {
        const { URL: url, jplatpat_url } = normalize(
          { URL: "text", jplatpat_url: "text" },
          data,
        );
        return url || jplatpat_url || null;
      },
      null,
      options,
    );
  }
  /** Patent `divisional_app_info`: the parent application and divisional descendants. */
  async getPatentDivisionalInfo(
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<JpoDivisionalInfo | null>> {
    return this.call(
      `/patent/v1/divisional_app_info/${segment(applicationNumber, "applicationNumber")}`,
      "divisional info",
      (data) => normalize(DIVISIONAL_INFO, data),
      null,
      options,
    );
  }
  /** Patent `cite_doc_info`: patent and non-patent citations (arrays, not the documented objects). */
  async getPatentCitedDocuments(
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<JpoCitedDocuments | null>> {
    return this.call(
      `/patent/v1/cite_doc_info/${segment(applicationNumber, "applicationNumber")}`,
      "cited documents",
      (data) => normalize(CITED_DOCUMENTS, data),
      null,
      options,
    );
  }
  /** Patent `pct_national_phase_application_number`: the JP national-phase application for a PCT number. */
  async getPatentPctNationalPhase(
    kind: JpoPctKind,
    number: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoResult<JpoPctNationalPhase | null>> {
    const k = pctKindSchema.parse(kind);
    return this.call(
      `/patent/v1/pct_national_phase_application_number/${k}/${segment(number, "number")}`,
      "PCT national phase",
      (data) => normalize(PCT_NATIONAL_PHASE, data),
      null,
      options,
    );
  }

  /**
   * `app_doc_cont_*`: a ZIP inline when under 10 MB, JSON with JPO's URL when
   * larger, or JSON with status 107/108 when there are no documents.
   */
  async getDocumentBundle(
    ipType: JpoIpType,
    docKind: JpoDocumentKind,
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<JpoDocumentBundle> {
    const ip = ipTypeSchema.parse(ipType);
    const kind = docKindSchema.parse(docKind);
    const number = applicationNumber.trim();
    const path = `/${ip}/v1/${DOCUMENT_ENDPOINTS[kind]}/${segment(number, "applicationNumber")}`;
    const context = `${ip} ${kind} documents`;
    let response = await this.get(path, options);
    const contentType = () =>
      (response.headers.get("content-type") ?? "").toLowerCase();
    const base = () => ({
      application_number: number,
      ip_type: ip,
      doc_kind: kind,
      content_type: contentType(),
      provenance: response.provenance,
    });
    if (contentType().includes("zip"))
      return {
        ...base(),
        zip: response.data,
        download_url: null,
        status_code: JPO_STATUS.SUCCESS,
        remaining_access_count: null,
      };
    let result = this.envelope(response.data, context);
    if (result.statusCode === JPO_STATUS.INVALID_TOKEN) {
      await this.token.refresh();
      response = await this.get(path, { ...options, cache: false });
      if (contentType().includes("zip"))
        return {
          ...base(),
          zip: response.data,
          download_url: null,
          status_code: JPO_STATUS.SUCCESS,
          remaining_access_count: null,
        };
      result = this.envelope(response.data, context);
    }
    checkStatus(result, context);
    const url =
      !EMPTY_STATUS.has(result.statusCode) &&
      typeof result.data?.URL === "string"
        ? result.data.URL
        : "";
    return {
      ...base(),
      zip: null,
      download_url: url || null,
      status_code: result.statusCode,
      remaining_access_count:
        result.remainAccessCount == null
          ? null
          : String(result.remainAccessCount),
    };
  }
  /**
   * Fetch the archive behind an oversize bundle's `download_url`. Only HTTPS
   * links on jpo.go.jp hosts are followed, without JPO credentials; Python
   * fetched whatever URL the response named.
   */
  async downloadOversizeBundle(
    bundle: Pick<JpoDocumentBundle, "download_url">,
    options: TransportRequestOptions = {},
  ): Promise<TransportResult<Uint8Array>> {
    if (!bundle.download_url)
      throw new TypeError("This bundle has no oversize download URL.");
    const url = new URL(bundle.download_url);
    if (url.protocol !== "https:" || url.port || !jpoHost(url))
      throw new JpoError(
        `JPO's oversize bundle link points outside jpo.go.jp (${url.hostname}); it was not fetched.`,
        0,
        "INVALID_RESPONSE",
      );
    return this.http.bytes("GET", url.href, {
      timeoutMs: 120_000,
      ...options,
      allowedHosts: [url.hostname],
      cache: false,
    });
  }
  /** The bundle's archive bytes, following an oversize link; null when JPO has no documents. */
  async getDocumentArchive(
    ipType: JpoIpType,
    docKind: JpoDocumentKind,
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<{ bundle: JpoDocumentBundle; zip: Uint8Array | null }> {
    const bundle = await this.getDocumentBundle(
      ipType,
      docKind,
      applicationNumber,
      options,
    );
    if (bundle.zip) return { bundle, zip: bundle.zip };
    if (!bundle.download_url) return { bundle, zip: null };
    const archive = await this.downloadOversizeBundle(bundle, options);
    return { bundle, zip: archive.data };
  }
  /** Fetch and parse a bundle; an empty bundle parses to no entries. */
  async getDocuments(
    ipType: JpoIpType,
    docKind: JpoDocumentKind,
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<{
    data: JpoParsedBundle;
    zip: Uint8Array | null;
    provenance: Provenance;
  }> {
    const { bundle, zip } = await this.getDocumentArchive(
      ipType,
      docKind,
      applicationNumber,
      options,
    );
    return {
      data: parseJpoDocumentBundle(
        zip,
        bundle.doc_kind,
        bundle.ip_type,
        bundle.application_number,
      ),
      zip,
      provenance: bundle.provenance,
    };
  }
}

function translate(error: unknown): unknown {
  if (!(error instanceof ApiError) || error instanceof JpoError) return error;
  if (error.status === 429)
    return new JpoError(
      "JPO API rate limit exceeded (HTTP 429).",
      429,
      "RATE_LIMITED",
      null,
      true,
    );
  if (error.status === 401 || error.status === 403)
    return new JpoError(
      `JPO refused access (HTTP ${error.status}).`,
      error.status,
      "AUTHENTICATION_FAILED",
    );
  if (error.status >= 400)
    return new JpoError(
      `JPO API returned HTTP ${error.status}.`,
      error.status,
      error.status === 404 ? "NOT_FOUND" : "UPSTREAM_ERROR",
      null,
      error.status >= 500,
    );
  return error;
}

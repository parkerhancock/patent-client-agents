import { decodeHTML, decodeXML } from "entities";
import { XMLParser } from "fast-xml-parser";
import { CachedClient } from "./cache/client.js";
import type { Provenance } from "./models.js";
import { env } from "./runtime/env.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * U.S. International Trade Commission services: EDIS (Section 337 and other
 * investigation dockets), the Harmonized Tariff Schedule REST API, the IDS
 * investigations feed and DataWeb trade statistics.
 */
export const USITC_SOURCE = "U.S. International Trade Commission (USITC)";
export const EDIS_ORIGIN = "https://edis.usitc.gov";
export const DATAWEB_ORIGIN = "https://datawebws.usitc.gov";
export const HTS_ORIGIN = "https://hts.usitc.gov";
export const IDS_ORIGIN = "https://ids.usitc.gov";
/**
 * Akamai bot management in front of every USITC host answers 403 to the
 * default Bun, Node and browser-like user agents but admits programmatic
 * clients that name themselves. The client names this project. Override with
 * `userAgent` if the edge's allowlist changes.
 */
export const USITC_USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

export interface UsitcClientOptions extends Omit<ClientOptions, "apiKey"> {
  /** Defaults to USITC_USER_AGENT. */
  userAgent?: string;
}

const invalid = (message: string, status = 200) =>
  new ApiError(message, status, "INVALID_RESPONSE");

function transport(
  cacheName: string,
  options: UsitcClientOptions,
  origin: string,
  headers: Record<string, string>,
  timeoutMs = 30_000,
) {
  const { userAgent, ...rest } = options;
  return new GenericHttpTransport({
    ...rest,
    timeoutMs: rest.timeoutMs ?? timeoutMs,
    baseUrl: rest.baseUrl ?? origin,
    sourceName: USITC_SOURCE,
    cache: { name: cacheName },
    headers: { ...headers, "user-agent": userAgent ?? USITC_USER_AGENT },
  });
}

/** The `exp` claim of a JWT as epoch milliseconds, or null when absent or not a JWT. */
export function jwtExpiry(token: string): number | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const payload = (parts[1] as string).replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(
      atob(payload + "=".repeat((4 - (payload.length % 4)) % 4)),
    ) as { exp?: unknown };
    const exp = Number(claims.exp);
    return claims.exp === undefined || !Number.isFinite(exp)
      ? null
      : exp * 1000;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// EDIS
// ---------------------------------------------------------------------------

export interface EdisInvestigation extends Record<string, unknown> {
  investigation_number: string;
  investigation_phase: string | null;
  investigation_type: string | null;
  investigation_status: string | null;
  title: string | null;
  docket_number: string | null;
  document_list_uri: string | null;
}
export interface EdisDocument extends Record<string, unknown> {
  id: number;
  document_type: string | null;
  title: string | null;
  security_level: string | null;
  investigation_number: string | null;
  investigation_phase: string | null;
  investigation_status: string | null;
  investigation_title: string | null;
  investigation_type: string | null;
  firm_organization: string | null;
  filed_by: string | null;
  on_behalf_of: string | null;
  document_date: string | null;
  official_received_date: string | null;
  attachment_list_uri: string | null;
  modified_date: string | null;
}
export interface EdisAttachment extends Record<string, unknown> {
  id: number;
  document_id: number;
  title: string | null;
  file_size: number | null;
  original_file_name: string | null;
  page_count: number | null;
  create_date: string | null;
  last_modified_date: string | null;
  download_uri: string | null;
}
export interface EdisList<T> {
  data: T[];
  provenance: Provenance;
}
export interface EdisDownload {
  document_id: number;
  attachment_id: number;
  /** From Content-Disposition, or null when EDIS sends none. */
  filename: string | null;
  content_type: string | null;
  data: Uint8Array;
  provenance: Provenance;
}
export interface EdisInvestigationQuery {
  /** EDIS form without the TA- infix, such as 337-1380. A path segment. */
  investigationNumber?: string;
  /** Violation, Final, Other1 and so on. */
  investigationPhase?: string;
  investigationType?: string;
  investigationStatus?: string;
  pageNumber?: number;
}
export interface EdisDocumentQuery {
  investigationNumber?: string;
  investigationPhase?: string;
  documentType?: string;
  /** Each word is an OR term upstream. */
  firmOrg?: string;
  securityLevel?: string;
  /** 100 documents per page. */
  pageNumber?: number;
}
export interface EdisClientOptions extends UsitcClientOptions {
  /** EDIS API bearer token; defaults to USITC_EDIS_TOKEN. */
  token?: string;
  /** Clock for token-expiry checks (epoch milliseconds). */
  now?: () => number;
}

/** Upstream tag -> field, where Python's model renames instead of snake-casing. */
const RENAMES: Record<string, Record<string, string>> = {
  investigation: { investigationTitle: "title" },
  document: { documentTitle: "title" },
  attachment: {},
};
const INTEGER_FIELDS: Record<string, Set<string>> = {
  investigation: new Set(),
  document: new Set(["id"]),
  attachment: new Set(["id", "document_id", "file_size", "page_count"]),
};
const snake = (tag: string) =>
  tag.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
const xml = new XMLParser({
  parseTagValue: false,
  processEntities: false,
  ignoreAttributes: true,
  trimValues: true,
  isArray: (name) => ["investigation", "document", "attachment"].includes(name),
});
/**
 * Text of one element. EDIS double-escapes some titles ("Nokia&amp;#39;s"),
 * so after XML decoding any remaining HTML entity is decoded once more.
 */
function text(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const decoded = decodeHTML(decodeXML(value)).trim();
  return decoded || null;
}

function parseEdis(
  body: string,
  collection: "investigations" | "documents" | "attachments",
  kind: "investigation" | "document" | "attachment",
  status: number,
): Record<string, unknown>[] {
  let parsed: unknown;
  try {
    parsed = xml.parse(body);
  } catch {
    throw invalid("EDIS returned invalid XML.", status);
  }
  const results = (parsed as { results?: unknown }).results;
  if (results === undefined || results === null || typeof results !== "object")
    throw invalid(
      `EDIS response has no <results>; the ${collection} list is unknown.`,
      status,
    );
  const group = (results as Record<string, unknown>)[collection];
  if (group === undefined)
    throw invalid(
      `EDIS response has no <${collection}>; the list is unknown.`,
      status,
    );
  // <investigations/> parses to an empty string.
  if (group === "" || group === null) return [];
  const rows = (group as Record<string, unknown>)[kind];
  if (rows === undefined) return [];
  if (!Array.isArray(rows))
    throw invalid(`EDIS returned a malformed <${collection}> list.`, status);
  return rows.map((row) => {
    if (!row || typeof row !== "object")
      throw invalid(`EDIS returned a malformed <${kind}>.`, status);
    const record: Record<string, unknown> = {};
    for (const [tag, value] of Object.entries(row)) {
      const field = RENAMES[kind]?.[tag] ?? snake(tag);
      const content = text(value);
      if (INTEGER_FIELDS[kind]?.has(field) && content !== null) {
        if (!/^-?\d+$/.test(content))
          throw invalid(`EDIS ${kind} ${field} is not an integer.`, status);
        record[field] = Number(content);
      } else record[field] = content;
    }
    return record;
  });
}

function requireFields(
  rows: Record<string, unknown>[],
  fields: string[],
  kind: string,
  status: number,
) {
  for (const row of rows)
    for (const field of fields)
      if (row[field] === null || row[field] === undefined)
        throw invalid(`EDIS ${kind} is missing ${field}.`, status);
}

function withDefaults<T>(row: Record<string, unknown>, fields: string[]): T {
  const out: Record<string, unknown> = {};
  for (const field of fields) out[field] = row[field] ?? null;
  return { ...out, ...row } as T;
}
const INVESTIGATION_FIELDS = [
  "investigation_number",
  "investigation_phase",
  "investigation_type",
  "investigation_status",
  "title",
  "docket_number",
  "document_list_uri",
];
const DOCUMENT_FIELDS = [
  "id",
  "document_type",
  "title",
  "security_level",
  "investigation_number",
  "investigation_phase",
  "investigation_status",
  "investigation_title",
  "investigation_type",
  "firm_organization",
  "filed_by",
  "on_behalf_of",
  "document_date",
  "official_received_date",
  "attachment_list_uri",
  "modified_date",
];
const ATTACHMENT_FIELDS = [
  "id",
  "document_id",
  "title",
  "file_size",
  "original_file_name",
  "page_count",
  "create_date",
  "last_modified_date",
  "download_uri",
];
const segment = (value: string, label: string) => {
  const trimmed = value.trim();
  if (!trimmed || /[/?#\\]|\.\./.test(trimmed))
    throw new ApiError(
      `${label} is not a valid EDIS value.`,
      400,
      "INVALID_INPUT",
    );
  return encodeURIComponent(trimmed);
};
const positiveId = (value: number, label: string) => {
  if (!Number.isSafeInteger(value) || value <= 0)
    throw new ApiError(
      `${label} must be a positive integer.`,
      400,
      "INVALID_INPUT",
    );
  return value;
};

/** The filename in a Content-Disposition header, or null. */
export function dispositionFilename(header: string | null): string | null {
  if (!header) return null;
  const extended = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (extended?.[1]) {
    try {
      return decodeURIComponent(extended[1].trim().replace(/^"|"$/g, ""));
    } catch {
      // fall through to the plain parameter
    }
  }
  const plain = /filename\s*=\s*("([^"]*)"|[^;]+)/i.exec(header);
  const value = (plain?.[2] ?? plain?.[1])?.trim();
  return value ? value : null;
}

/**
 * EDIS (https://edis.usitc.gov/data). Investigation, document and attachment
 * metadata are public; attachment downloads need an EDIS API bearer token.
 */
export class EdisClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private readonly token: string | undefined;
  private readonly expiresAt: number | null;
  private readonly now: () => number;
  constructor(options: EdisClientOptions = {}) {
    super();
    const { token, now, ...rest } = options;
    this.token = (token ?? env("USITC_EDIS_TOKEN"))?.trim() || undefined;
    this.expiresAt = this.token ? jwtExpiry(this.token) : null;
    this.now = now ?? Date.now;
    this.http = transport("usitc_edis", rest, EDIS_ORIGIN, {
      accept: "application/xml",
    });
  }
  /** True when a token is configured. */
  get hasToken(): boolean {
    return this.token !== undefined;
  }
  /** Expiry of the configured token (JWT exp), when it carries one. */
  get tokenExpiresAt(): Date | null {
    return this.expiresAt === null ? null : new Date(this.expiresAt);
  }
  private tokenExpired(): boolean {
    return this.expiresAt !== null && this.now() >= this.expiresAt;
  }
  /**
   * EDIS answers an expired bearer token with an HTML 503 even on public
   * metadata routes, so metadata requests send the token only while it is
   * unexpired.
   */
  private metadataHeaders(): Record<string, string> {
    return this.token && !this.tokenExpired()
      ? { authorization: `Bearer ${this.token}` }
      : {};
  }
  private async list(
    path: string,
    collection: "investigations" | "documents" | "attachments",
    kind: "investigation" | "document" | "attachment",
    searchParams: Record<string, string | number | undefined>,
    options: TransportRequestOptions,
  ) {
    const result = await this.http.text("GET", path, {
      ...options,
      searchParams,
      headers: { ...this.metadataHeaders(), ...headersObject(options.headers) },
    });
    return {
      rows: parseEdis(result.data, collection, kind, result.status),
      status: result.status,
      provenance: result.provenance,
    };
  }

  /**
   * Investigations. The number and phase are path segments; a phase without a
   * number is sent as the investigationPhase query filter.
   */
  async listInvestigations(
    query: EdisInvestigationQuery = {},
    options: TransportRequestOptions = {},
  ): Promise<EdisList<EdisInvestigation>> {
    let path = "/data/investigation";
    const params: Record<string, string | number | undefined> = {
      investigationType: query.investigationType || undefined,
      investigationStatus: query.investigationStatus || undefined,
      pageNumber: query.pageNumber,
    };
    if (query.investigationNumber) {
      path += `/${segment(query.investigationNumber, "investigation_number")}`;
      if (query.investigationPhase)
        path += `/${segment(query.investigationPhase, "investigation_phase")}`;
    } else if (query.investigationPhase)
      params.investigationPhase = query.investigationPhase;
    const { rows, status, provenance } = await this.list(
      path,
      "investigations",
      "investigation",
      params,
      options,
    );
    requireFields(rows, ["investigation_number"], "investigation", status);
    return {
      data: rows.map((row) =>
        withDefaults<EdisInvestigation>(row, INVESTIGATION_FIELDS),
      ),
      provenance,
    };
  }

  /** Documents, 100 per page; an empty page ends the listing. */
  async listDocuments(
    query: EdisDocumentQuery = {},
    options: TransportRequestOptions = {},
  ): Promise<EdisList<EdisDocument>> {
    const { rows, status, provenance } = await this.list(
      "/data/document",
      "documents",
      "document",
      {
        investigationNumber: query.investigationNumber || undefined,
        investigationPhase: query.investigationPhase || undefined,
        documentType: query.documentType || undefined,
        firmOrg: query.firmOrg || undefined,
        securityLevel: query.securityLevel || undefined,
        pageNumber: query.pageNumber,
      },
      options,
    );
    requireFields(rows, ["id"], "document", status);
    return {
      data: rows.map((row) => withDefaults<EdisDocument>(row, DOCUMENT_FIELDS)),
      provenance,
    };
  }

  /** Attachments of one document. */
  async listAttachments(
    documentId: number,
    options: TransportRequestOptions = {},
  ): Promise<EdisList<EdisAttachment>> {
    const { rows, status, provenance } = await this.list(
      `/data/attachment/${positiveId(documentId, "document_id")}`,
      "attachments",
      "attachment",
      {},
      options,
    );
    requireFields(rows, ["id", "document_id"], "attachment", status);
    return {
      data: rows.map((row) =>
        withDefaults<EdisAttachment>(row, ATTACHMENT_FIELDS),
      ),
      provenance,
    };
  }

  /** Download one attachment. Requires an unexpired token. */
  async downloadAttachment(
    documentId: number,
    attachmentId: number,
    options: TransportRequestOptions = {},
  ): Promise<EdisDownload> {
    positiveId(documentId, "document_id");
    positiveId(attachmentId, "attachment_id");
    if (!this.token)
      throw new ApiError(
        "USITC_EDIS_TOKEN is required to download EDIS attachments. Generate a token at https://edis.usitc.gov (profile, API Token Generator).",
        401,
        "AUTH_REQUIRED",
      );
    if (this.tokenExpired())
      throw new ApiError(
        `USITC_EDIS_TOKEN expired at ${new Date(this.expiresAt as number).toISOString()}. Mint a new token at https://edis.usitc.gov (profile, API Token Generator) and update USITC_EDIS_TOKEN.`,
        401,
        "AUTH_EXPIRED",
      );
    const result = await this.http.bytes(
      "GET",
      `/data/download/${documentId}/${attachmentId}`,
      {
        ...options,
        headers: {
          accept: "*/*",
          authorization: `Bearer ${this.token}`,
          ...headersObject(options.headers),
        },
      },
    );
    return {
      document_id: documentId,
      attachment_id: attachmentId,
      filename: dispositionFilename(result.headers.get("content-disposition")),
      content_type: result.headers.get("content-type"),
      data: result.data,
      provenance: result.provenance,
    };
  }
}

function headersObject(headers: HeadersInit | undefined) {
  const out: Record<string, string> = {};
  new Headers(headers).forEach((value, key) => {
    out[key] = value;
  });
  return out;
}

// ---------------------------------------------------------------------------
// HTS
// ---------------------------------------------------------------------------

/** One HTS search hit; every upstream field is kept. */
export interface HtsSearchResult extends Record<string, unknown> {
  hts_number: string | null;
  description: string | null;
  /** Four-digit heading, from upstream or derived from the HTS number. */
  heading: string | null;
  /** Two-digit chapter, from upstream or derived from the HTS number. */
  chapter: string | null;
}
const rowsOf = (value: unknown, status: number, label: string) => {
  if (!Array.isArray(value)) throw invalid(`${label} is not a list.`, status);
  return value.map((row) => {
    if (!row || typeof row !== "object" || Array.isArray(row))
      throw invalid(`${label} contains a non-object row.`, status);
    return row as Record<string, unknown>;
  });
};
const stringOrNull = (value: unknown) =>
  typeof value === "string" && value ? value : null;

/** Harmonized Tariff Schedule REST (https://hts.usitc.gov/reststop). No key. */
export class HtsClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: UsitcClientOptions = {}) {
    super();
    this.http = transport("usitc_hts", options, HTS_ORIGIN, {
      accept: "application/json",
    });
  }
  /** Keyword search; the service returns at most about 100 rows. */
  async search(
    keyword: string,
    options: TransportRequestOptions = {},
  ): Promise<{ data: HtsSearchResult[]; provenance: Provenance }> {
    if (!keyword.trim())
      throw new ApiError("keyword must be nonempty.", 400, "INVALID_INPUT");
    const result = await this.http.json("GET", "/reststop/search", {
      ...options,
      searchParams: { keyword },
    });
    const payload = result.data as Record<string, unknown> | unknown[];
    const list = Array.isArray(payload)
      ? payload
      : Array.isArray(payload?.results)
        ? payload.results
        : payload?.items;
    return {
      data: rowsOf(list, result.status, "HTS search response").map((row) => {
        const htsno = stringOrNull(row.htsno);
        const digits = htsno?.replace(/\D/g, "") ?? "";
        return {
          hts_number: htsno,
          description: stringOrNull(row.description),
          heading:
            stringOrNull(row.heading) ??
            (digits.length >= 4 ? digits.slice(0, 4) : null),
          chapter:
            stringOrNull(row.chapter) ??
            (digits.length >= 2 ? digits.slice(0, 2) : null),
          ...Object.fromEntries(
            Object.entries(row).filter(
              ([key]) =>
                !["htsno", "heading", "chapter", "description"].includes(key),
            ),
          ),
        };
      }),
      provenance: result.provenance,
    };
  }
  /**
   * Schedule rows from one HTS number to another (inclusive), as JSON. The
   * service also offers CSV and XLSX; this client reads JSON only.
   */
  async exportRange(
    from: string,
    to: string,
    exportOptions: { styles?: boolean } = {},
    options: TransportRequestOptions = {},
  ): Promise<{ entries: Record<string, unknown>[]; provenance: Provenance }> {
    if (!from.trim() || !to.trim())
      throw new ApiError("from and to must be nonempty.", 400, "INVALID_INPUT");
    // exportList answers application/octet-stream, so parse the text.
    const result = await this.http.text("GET", "/reststop/exportList", {
      ...options,
      searchParams: {
        from,
        to,
        format: "JSON",
        styles: String(exportOptions.styles ?? true),
      },
    });
    let payload: unknown;
    try {
      payload = JSON.parse(result.data);
    } catch {
      throw invalid("HTS exportList returned invalid JSON.", result.status);
    }
    const list = Array.isArray(payload)
      ? payload
      : ((payload as { entries?: unknown } | null)?.entries ?? []);
    return {
      entries: rowsOf(list, result.status, "HTS exportList response"),
      provenance: result.provenance,
    };
  }
}

// ---------------------------------------------------------------------------
// IDS
// ---------------------------------------------------------------------------

/** One IDS investigation; the upstream's other columns are kept by their names. */
export interface IdsInvestigation extends Record<string, unknown> {
  investigation_id: number;
  investigation_number: string;
  title: string | null;
  topic: string | null;
  product_group: unknown;
  phase: unknown;
  investigation_status: unknown;
  investigation_type: unknown;
  docket_number: string | null;
  start_date: string | null;
  end_date: string | null;
  staff_contacts: Record<string, unknown>[] | null;
  participants: Record<string, unknown>[] | null;
}
const IDS_FIELDS: Record<string, string> = {
  "Investigation ID": "investigation_id",
  "Investigation Number": "investigation_number",
  "Full Title": "title",
  Topic: "topic",
  "Product Group Code Description": "product_group",
  "Phase Number": "phase",
  "Investigation Status": "investigation_status",
  "Investigation Type": "investigation_type",
  "Docket Number": "docket_number",
  "Start Date": "start_date",
  "Investigation End Date": "end_date",
  Staff: "staff_contacts",
  Participants: "participants",
};

/** USITC IDS investigations feed (https://ids.usitc.gov/investigations.json). No key. */
export class IdsClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: UsitcClientOptions = {}) {
    super();
    // The feed was 37 MB in October 2026 and grows; allow headroom.
    this.http = transport(
      "usitc_ids",
      {
        ...options,
        maxResponseBytes: options.maxResponseBytes ?? 128 * 1024 * 1024,
      },
      IDS_ORIGIN,
      { accept: "application/json" },
      120_000,
    );
  }
  /** Every investigation in the feed (about 4,400 rows, 37 MB in October 2026). */
  async listInvestigations(
    options: TransportRequestOptions = {},
  ): Promise<{ data: IdsInvestigation[]; provenance: Provenance }> {
    const result = await this.http.json("GET", "/investigations.json", options);
    const data = (result.data as { data?: unknown } | null)?.data;
    const rows = rowsOf(data, result.status, "IDS feed data");
    return {
      data: rows.map((row) => {
        const record: Record<string, unknown> = {};
        for (const field of Object.values(IDS_FIELDS)) record[field] = null;
        for (const [key, value] of Object.entries(row))
          record[IDS_FIELDS[key] ?? key] = value ?? null;
        const id = Number(record.investigation_id);
        if (
          !Number.isSafeInteger(id) ||
          typeof record.investigation_number !== "string"
        )
          throw invalid(
            "IDS row lacks an investigation id or number.",
            result.status,
          );
        record.investigation_id = id;
        return record as IdsInvestigation;
      }),
      provenance: result.provenance,
    };
  }
}

// ---------------------------------------------------------------------------
// DataWeb
// ---------------------------------------------------------------------------

export interface DataWebQueryOptions {
  /** Import, Export, GenImp, TotExp, Balance, ForeignExp, ImpExp. */
  tradeType?: string;
  /** HTS, SITC, NAIC, SIC, QUICK, EXPERT. */
  classification?: string;
  years?: string[];
  /** Annual or Monthly. */
  timeline?: string;
  dataMetrics?: string[];
  /** 1, 1000 or 1000000. */
  scale?: string;
  commodities?: string[] | null;
  /** HTS digit level: 2, 4, 6, 8 or 10. */
  granularity?: string;
  countries?: { name: string; value: string }[] | null;
  aggregateCountries?: boolean;
  aggregateCommodities?: boolean;
  maxRows?: string;
}

/** The nested DataWeb query object, built from simple parameters as Python's build_dataweb_query. */
export function buildDataWebQuery(
  options: DataWebQueryOptions = {},
): Record<string, unknown> {
  const countries = options.countries?.length ? options.countries : null;
  const commodities = options.commodities?.length ? options.commodities : null;
  const countryAggregation =
    (options.aggregateCountries ?? true)
      ? "Aggregate Countries"
      : "Break Out Countries";
  const commodityAggregation =
    (options.aggregateCommodities ?? true)
      ? "Aggregate Commodities"
      : "Break Out Commodities";
  return {
    savedQueryName: "",
    savedQueryDesc: "",
    isOwner: true,
    runMonthly: false,
    reportOptions: {
      tradeType: options.tradeType ?? "Import",
      classificationSystem: options.classification ?? "HTS",
    },
    searchOptions: {
      countries: {
        aggregation: countryAggregation,
        countriesSelectType: countries ? "selected" : "all",
        countries: countries ?? [],
        countriesExpanded: countries ?? [
          { name: "All Countries", value: "all" },
        ],
        countryGroups: { systemGroups: [], userGroups: [] },
      },
      commodities: {
        aggregation: commodityAggregation,
        commoditySelectType: commodities ? "manual" : "all",
        commodities: [],
        commoditiesExpanded: [],
        commoditiesManual: commodities ? commodities.join(",") : "",
        commodityGroups: { systemGroups: [], userGroups: [] },
        granularity: options.granularity ?? "2",
        codeDisplayFormat: "YES",
        groupGranularity: null,
        searchGranularity: null,
      },
      componentSettings: {
        timeframeSelectType: "fullYears",
        years: options.years ?? ["2024"],
        yearsTimeline: options.timeline ?? "Annual",
        dataToReport: options.dataMetrics ?? ["CONS_CUSTOMS_VALUE"],
        scale: options.scale ?? "1",
        startDate: null,
        endDate: null,
        startMonth: null,
        endMonth: null,
      },
      MiscGroup: {
        districts: {
          aggregation: "Aggregate District",
          districtGroups: { userGroups: [] },
          districts: [],
          districtsExpanded: [{ name: "All Districts", value: "all" }],
          districtsSelectType: "all",
        },
        importPrograms: {
          aggregation: null,
          importPrograms: [],
          programsSelectType: "all",
        },
        extImportPrograms: {
          aggregation: "Aggregate CSC",
          extImportPrograms: [],
          extImportProgramsExpanded: [],
          programsSelectType: "all",
        },
        provisionCodes: {
          aggregation: "Aggregate RPCODE",
          provisionCodesSelectType: "all",
          rateProvisionCodes: [],
          rateProvisionCodesExpanded: [],
        },
      },
    },
    sortingAndDataFormat: {
      DataSort: { columnOrder: [], fullColumnOrder: [], sortOrder: [] },
      reportCustomizations: {
        exportCombineTables: false,
        showAllSubtotal: true,
        subtotalRecords: "",
        totalRecords: options.maxRows ?? "20000",
        exportRawData: false,
      },
    },
  };
}

export interface DataWebReport {
  dto: Record<string, unknown>;
  raw: Record<string, unknown>;
  provenance: Provenance;
}
export interface SavedQuerySummary extends Record<string, unknown> {
  id: number;
  name: string;
  description: string | null;
  created_at: string | null;
}
export interface DataWebClientOptions extends UsitcClientOptions {
  /** DataWeb API bearer token; defaults to USITC_DATAWEB_TOKEN. */
  token?: string;
}

/** Rows across every table's row groups (DataWeb's rowsNew arrays). */
export function dataWebRowCount(dto: Record<string, unknown>): number | null {
  const tables = dto.tables;
  if (!Array.isArray(tables)) return null;
  let count = 0;
  for (const table of tables) {
    const groups = (table as { row_groups?: unknown } | null)?.row_groups;
    if (!Array.isArray(groups)) continue;
    for (const group of groups) {
      const rows = (group as { rowsNew?: unknown } | null)?.rowsNew;
      if (Array.isArray(rows)) count += rows.length;
    }
  }
  return count;
}

/** USITC DataWeb trade statistics (https://datawebws.usitc.gov/dataweb). Bearer token. */
export class DataWebClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private readonly token: string | undefined;
  constructor(options: DataWebClientOptions = {}) {
    super();
    const { token, ...rest } = options;
    this.token = (token ?? env("USITC_DATAWEB_TOKEN"))?.trim() || undefined;
    this.http = transport(
      "usitc_dataweb",
      rest,
      DATAWEB_ORIGIN,
      { accept: "application/json" },
      60_000,
    );
  }
  get hasToken(): boolean {
    return this.token !== undefined;
  }
  private auth(): Record<string, string> {
    if (!this.token)
      throw new ApiError(
        "USITC_DATAWEB_TOKEN is required to call DataWeb endpoints.",
        401,
        "AUTH_REQUIRED",
      );
    const expires = jwtExpiry(this.token);
    if (expires !== null && Date.now() >= expires)
      throw new ApiError(
        `USITC_DATAWEB_TOKEN expired at ${new Date(expires).toISOString()}. Copy a new token from the API tab at https://dataweb.usitc.gov.`,
        401,
        "AUTH_EXPIRED",
      );
    return { authorization: `Bearer ${this.token}` };
  }
  private object(value: unknown, status: number, label: string) {
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw invalid(`${label} is not a JSON object.`, status);
    return value as Record<string, unknown>;
  }
  /** Run a report query (see buildDataWebQuery). */
  async runReport(
    query: Record<string, unknown>,
    options: TransportRequestOptions = {},
  ): Promise<DataWebReport> {
    const result = await this.http.json(
      "POST",
      "/dataweb/api/v2/report2/runReport",
      { ...options, body: query, headers: this.auth() },
    );
    const raw = this.object(result.data, result.status, "DataWeb report");
    const dto = raw.dto ?? {};
    return {
      dto: this.object(dto, result.status, "DataWeb report dto"),
      raw,
      provenance: result.provenance,
    };
  }
  async getAllCountries(
    options: TransportRequestOptions = {},
  ): Promise<Record<string, unknown>[]> {
    const result = await this.http.json(
      "GET",
      "/dataweb/api/v2/country/getAllCountries",
      { ...options, headers: this.auth() },
    );
    const payload = this.object(
      result.data,
      result.status,
      "DataWeb countries",
    );
    return rowsOf(payload.options ?? [], result.status, "DataWeb countries");
  }
  async getGlobalVars(
    options: TransportRequestOptions = {},
  ): Promise<Record<string, unknown>> {
    const result = await this.http.json(
      "GET",
      "/dataweb/api/v2/query/getGlobalVars",
      { ...options, headers: this.auth() },
    );
    return this.object(result.data, result.status, "DataWeb global vars");
  }
  /** Saved queries of the token's account. DataWeb wraps them as {"list": [...]}. */
  async listSavedQueries(
    options: TransportRequestOptions = {},
  ): Promise<SavedQuerySummary[]> {
    const result = await this.http.json(
      "GET",
      "/dataweb/api/v2/savedQuery/getAllSavedQueries",
      { ...options, headers: this.auth() },
    );
    const list = Array.isArray(result.data)
      ? result.data
      : (result.data as { list?: unknown } | null)?.list;
    return rowsOf(list, result.status, "DataWeb saved queries").map((row) => {
      const id = Number(row.id);
      if (!Number.isSafeInteger(id) || typeof row.name !== "string")
        throw invalid("DataWeb saved query lacks id or name.", result.status);
      return {
        ...row,
        id,
        name: row.name,
        description: stringOrNull(row.description),
        created_at: stringOrNull(row.createdDate),
      };
    });
  }
}

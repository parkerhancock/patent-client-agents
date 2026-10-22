import { degrees, PDFDocument } from "pdf-lib";
import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import {
  type ClassificationMappingResponse,
  type CpciBiblioResponse,
  type CpcRetrievalResponse,
  type CpcSearchResponse,
  type EpoBiblioResponse,
  type EpoCitationResponse,
  type EpoEquivalentsResponse,
  type EpoFamilyResponse,
  type EpoFullTextResponse,
  type EpoLegalEventsResponse,
  type EpoNumberConversionResponse,
  type EpoSearchResponse,
  type EpoSearchResult,
  parseBiblio,
  parseCitations,
  parseClassificationMapping,
  parseCpciBiblio,
  parseCpcRetrieval,
  parseCpcSearch,
  parseEquivalents,
  parseFamily,
  parseFault,
  parseFullDocumentImage,
  parseFullText,
  parseLegalEvents,
  parseNumberConversion,
  parseRegisterBiblio,
  parseRegisterEvents,
  parseRegisterProceduralSteps,
  parseSearch,
  parseUnitaryPatentPackage,
  type RegisterBiblioResponse,
  type RegisterEventsResponse,
  type RegisterProceduralStepsResponse,
  type UnitaryPatentPackage,
} from "./epo-ops-parsing.js";
import type { Provenance } from "./models.js";
import { env, textToBase64 } from "./runtime/env.js";
import {
  ApiError,
  type ClientOptions,
  ConfigurationError,
  GenericHttpTransport,
  HttpResponseError,
  type TransportRequestOptions,
  type TransportResult,
} from "./transport.js";

export * from "./epo-ops-parsing.js";

export const EPO_OPS_SOURCE =
  "European Patent Office Open Patent Services (EPO OPS)";
export const EPO_REGISTER_SOURCE = "European Patent Register";
const ORIGIN = "https://ops.epo.org";
const SERVICES = "/3.2/rest-services";

export type EpoOpsErrorCode =
  | "NOT_FOUND"
  | "RATE_LIMITED"
  | "AUTHENTICATION_FAILED"
  | "HTTP_ERROR";
/** Safe OPS error: status, fault code/message and quota headers, never request objects or tokens. */
export class EpoOpsError extends ApiError {
  override name = "EpoOpsError";
  constructor(
    message: string,
    status: number,
    code: EpoOpsErrorCode,
    public readonly faultCode: string | null = null,
    public readonly retryable = false,
  ) {
    super(message, status, code);
  }
}

export interface EpoOpsClientOptions extends Omit<ClientOptions, "apiKey"> {
  /** OPS consumer key; defaults to EPO_OPS_API_KEY (or legacy EPO_API_KEY). */
  apiKey?: string;
  /** OPS consumer secret; defaults to EPO_OPS_API_SECRET (or legacy EPO_API_SECRET). */
  apiSecret?: string;
  /** Upper bound on pages merged into one full-document PDF. Defaults to 500. */
  maxPdfPages?: number;
}
export type DocType = "publication" | "application" | "priority";
export type NumberFormat = "docdb" | "epodoc" | "original";
export interface PublicationOptions extends TransportRequestOptions {
  docType?: DocType;
  format?: NumberFormat;
}
export type EpoResult<T> = { data: T; provenance: Provenance };

const tokenSchema = z.looseObject({
  access_token: z.string().min(1),
  expires_in: z.coerce.number().int().positive(),
});
const docTypeSchema = z.enum(["publication", "application", "priority"]);
const formatSchema = z.enum(["docdb", "epodoc", "original"]);

/**
 * OAuth2 client-credentials token for OPS. Expiry is measured on the local
 * clock from receipt, so server clock skew and replayed recordings cannot
 * make a fresh token look expired. Refreshes are single-flight.
 */
class OpsToken {
  private header?: string;
  private expiresAt = 0;
  private pending: Promise<string> | undefined;
  constructor(
    private readonly http: GenericHttpTransport,
    private readonly basic: string,
  ) {}
  current(): Promise<string> {
    if (this.header && Date.now() < this.expiresAt - 30_000)
      return Promise.resolve(this.header);
    return this.refresh();
  }
  /** Replace `stale` unless another caller already did. */
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
      result = await this.http.json("POST", "/3.2/auth/accesstoken", {
        form: { grant_type: "client_credentials" },
        headers: { authorization: `Basic ${this.basic}` },
        readErrorBody: true,
      });
    } catch (error) {
      if (error instanceof HttpResponseError) {
        const retryable = error.status === 429 || error.status >= 500;
        throw new EpoOpsError(
          retryable
            ? `EPO OPS token request failed with HTTP ${error.status}.`
            : "EPO OPS rejected the configured credentials.",
          error.status,
          retryable ? "HTTP_ERROR" : "AUTHENTICATION_FAILED",
          null,
          retryable,
        );
      }
      throw error;
    }
    const parsed = tokenSchema.safeParse(result.data);
    if (!parsed.success)
      throw new ApiError(
        "EPO OPS returned an invalid token response.",
        result.status,
        "INVALID_RESPONSE",
      );
    this.header = `Bearer ${parsed.data.access_token}`;
    this.expiresAt = Date.now() + parsed.data.expires_in * 1000;
    return this.header;
  }
}

function credential(
  value: string | undefined,
  primary: string,
  legacy: string,
): string | undefined {
  return (value ?? env(primary) ?? env(legacy))?.trim() || undefined;
}
function invalidToken(error: unknown) {
  return (
    error instanceof HttpResponseError &&
    (error.status === 401 ||
      (error.status === 400 && error.bodyText.includes("invalid_access_token")))
  );
}
function translate(error: unknown, source: string): unknown {
  if (!(error instanceof HttpResponseError)) return error;
  const fault = parseFault(error.bodyText);
  const detail = [fault.code, fault.message].filter(Boolean).join(": ");
  if (error.status === 403 || error.status === 429) {
    const header = (name: string) => error.headers.get(name);
    const parts = [
      ["reason", header("x-rejection-reason")],
      ["throttling", header("x-throttling-control")],
      ["hourly_used", header("x-individualquotaperhour-used")],
      ["weekly_used", header("x-registeredquotaperweek-used")],
    ].filter(([, value]) => value);
    return new EpoOpsError(
      `${source} returned HTTP ${error.status}${
        parts.length
          ? ` (${parts.map(([key, value]) => `${key}=${value}`).join("; ")})`
          : " - likely rate limited or quota exceeded"
      }.`,
      error.status,
      "RATE_LIMITED",
      fault.code,
      true,
    );
  }
  if (error.status === 404)
    return new EpoOpsError(
      `${source} found no matching record${detail ? ` (${detail})` : ""}.`,
      404,
      "NOT_FOUND",
      fault.code,
    );
  return new EpoOpsError(
    `${source} returned HTTP ${error.status}${detail ? ` (${detail})` : ""}.`,
    error.status,
    "HTTP_ERROR",
    fault.code,
    error.status >= 500,
  );
}
function segment(value: string, name: string) {
  const text = value.trim();
  if (!text) throw new TypeError(`${name} is required.`);
  return encodeURIComponent(text);
}
const normalize = (value: string) =>
  value.trim().replace(/\s+/g, "").toUpperCase();
const US_PGPUB_PRINTED = /^US(20\d{2})0(\d{6})([A-Z]\d?)?$/;
/**
 * Normalize a publication number for docdb/epodoc paths. Printed US
 * pre-grant numbers carry a 7-digit serial (US20050262543A1) but OPS indexes
 * a 6-digit one (US2005262543A1); the printed form returns EntityNotFound.
 */
export function opsNumber(
  number: string,
  docType: DocType = "publication",
  format: NumberFormat = "docdb",
): string {
  const value = normalize(number);
  if (docType === "publication" && format !== "original") {
    const match = US_PGPUB_PRINTED.exec(value);
    if (match) return `US${match[1]}${match[2]}${match[3] ?? ""}`;
  }
  return value;
}
/** CPC, IPC or ECLA symbol such as H04L9/32 or A61K31/00B2; at most one slash. */
function classSymbol(symbol: string) {
  const value = normalize(symbol);
  if (value.length > 40 || !/^[A-Z][A-Z0-9]*(?:\/[A-Z0-9]+)?$/.test(value))
    throw new TypeError(`Invalid classification symbol: ${symbol}`);
  return value;
}

export const FAMILY_EVIDENCE_LIMITATIONS = [
  "EPO OPS worldwide legal events may lag official national registers; verify current validation, renewal, lapse, and revocation in each national register.",
  "European Patent Register dossier and term-of-grant data do not establish current enforceability in national registers.",
  "UPC opt-out and case-management status are not exposed by EPO OPS; verify them against the UPC register.",
  "The evidence is source-separated; no family-wide legal-status conclusion is drawn.",
] as const;
export interface EvidenceFailure {
  code:
    | "not_found"
    | "rate_limited"
    | "upstream_server_error"
    | "upstream_api_error"
    | "parse_error"
    | "transport_error";
  message: string;
  retryable: boolean;
  source_name: string;
}
export type SourceEvidence<T> =
  | { outcome: "ok" | "empty"; data: T; provenance: Provenance }
  | { outcome: "not_applicable" }
  | { outcome: "not_found" | "error"; failure: EvidenceFailure };
export interface FamilyEvidence {
  publication_number: string;
  inpadoc_family: SourceEvidence<EpoFamilyResponse>;
  simple_family_equivalents: SourceEvidence<EpoEquivalentsResponse>;
  backward_citations: SourceEvidence<EpoCitationResponse>;
  worldwide_legal_events: SourceEvidence<EpoLegalEventsResponse>;
  register_biblio: SourceEvidence<RegisterBiblioResponse>;
  register_events: SourceEvidence<RegisterEventsResponse>;
  register_procedural_steps: SourceEvidence<RegisterProceduralStepsResponse>;
  limitations: string[];
}
function evidenceIsEmpty(name: string, data: object): boolean {
  const record = data as Record<string, unknown>;
  const collection = {
    inpadoc_family: "members",
    simple_family_equivalents: "equivalents",
    backward_citations: "citations",
    worldwide_legal_events: "events",
    register_events: "events",
    register_procedural_steps: "procedural_steps",
  }[name];
  const filled = (value: unknown) =>
    Array.isArray(value) ? value.length > 0 : Boolean(value);
  if (collection) return !filled(record[collection]);
  return ![
    "bibliographic_status",
    "application_id",
    "patent_statuses",
    "publication_references",
    "application_references",
    "priority_claim_sets",
    "titles",
    "party_sets",
    "classification_sets",
    "state_designation_sets",
    "term_of_grant_snapshots",
  ].some((field) => filled(record[field]));
}

/** EPO Open Patent Services 3.2: published data, family, legal, register, number service and CPC. */
export class EpoOpsClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private readonly token: OpsToken;
  private readonly maxPdfPages: number;
  constructor(options: EpoOpsClientOptions = {}) {
    super();
    const key = credential(options.apiKey, "EPO_OPS_API_KEY", "EPO_API_KEY");
    const secret = credential(
      options.apiSecret,
      "EPO_OPS_API_SECRET",
      "EPO_API_SECRET",
    );
    if (!key || !secret)
      throw new ConfigurationError(
        "Set EPO_OPS_API_KEY and EPO_OPS_API_SECRET, or pass apiKey and apiSecret, to use EPO OPS.",
      );
    const {
      apiKey: _key,
      apiSecret: _secret,
      maxPdfPages,
      ...transport
    } = options;
    this.http = new GenericHttpTransport({
      timeoutMs: 60_000,
      ...transport,
      baseUrl: options.baseUrl ?? ORIGIN,
      sourceName: EPO_OPS_SOURCE,
      cache: { name: "epo_ops" },
      headers: { accept: "application/xml" },
    });
    this.token = new OpsToken(this.http, textToBase64(`${key}:${secret}`));
    this.maxPdfPages = z
      .number()
      .int()
      .positive()
      .max(5000)
      .parse(maxPdfPages ?? 500);
  }

  /** Authorized GET; one refresh-and-retry when OPS reports an invalid token. */
  private async get<M extends "text" | "bytes">(
    mode: M,
    path: string,
    options: TransportRequestOptions = {},
    source = EPO_OPS_SOURCE,
  ): Promise<TransportResult<M extends "text" ? string : Uint8Array>> {
    const send = (authorization: string) => {
      const headers = new Headers(options.headers);
      headers.set("authorization", authorization);
      return this.http[mode]("GET", path, {
        ...options,
        headers,
        readErrorBody: true,
      }) as Promise<TransportResult<M extends "text" ? string : Uint8Array>>;
    };
    const authorization = await this.token.current();
    try {
      return await send(authorization);
    } catch (error) {
      if (!invalidToken(error)) throw translate(error, source);
    }
    try {
      return await send(await this.token.refresh(authorization));
    } catch (error) {
      if (invalidToken(error))
        throw new EpoOpsError(
          "EPO OPS rejected an access token after refresh.",
          (error as HttpResponseError).status,
          "AUTHENTICATION_FAILED",
          null,
          true,
        );
      throw translate(error, source);
    }
  }
  private async xml<T>(
    path: string,
    parse: (xml: string) => T,
    options: TransportRequestOptions = {},
    source = EPO_OPS_SOURCE,
  ): Promise<EpoResult<T>> {
    const result = await this.get("text", path, options, source);
    return {
      data: parse(result.data),
      provenance:
        source === EPO_OPS_SOURCE
          ? result.provenance
          : { ...result.provenance, source_name: source },
    };
  }
  private published(number: string, options: PublicationOptions, view: string) {
    const docType = docTypeSchema.parse(options.docType ?? "publication");
    const format = formatSchema.parse(options.format ?? "docdb");
    const value = opsNumber(number, docType, format);
    return {
      value,
      path: `${SERVICES}/published-data/${docType}/${format}/${segment(value, "number")}/${view}`,
    };
  }
  private request(options: PublicationOptions): TransportRequestOptions {
    const { docType: _docType, format: _format, ...rest } = options;
    return rest;
  }

  /** CQL search of published documents. An OPS "No results found" fault becomes an empty page. */
  async search(
    query: string,
    options: TransportRequestOptions & {
      rangeBegin?: number;
      rangeEnd?: number;
    } = {},
  ): Promise<EpoResult<EpoSearchResponse>> {
    const { rangeBegin = 1, rangeEnd = 25, ...rest } = options;
    const begin = z.number().int().min(1).max(2000).parse(rangeBegin);
    const end = z
      .number()
      .int()
      .min(begin)
      .max(begin + 99)
      .parse(rangeEnd);
    if (!query.trim()) throw new TypeError("A CQL query is required.");
    try {
      return await this.xml(`${SERVICES}/published-data/search`, parseSearch, {
        ...rest,
        searchParams: { q: query, Range: `${begin}-${end}` },
      });
    } catch (error) {
      if (
        error instanceof EpoOpsError &&
        error.code === "NOT_FOUND" &&
        error.faultCode === "SERVER.EntityNotFound" &&
        /No results found/i.test(error.message)
      )
        return {
          data: {
            query,
            range_begin: begin,
            range_end: end,
            total_results: 0,
            results: [],
          },
          provenance: {
            source_url: `${ORIGIN}${SERVICES}/published-data/search?${new URLSearchParams({ q: query, Range: `${begin}-${end}` })}`,
            source_name: EPO_OPS_SOURCE,
            retrieved_at: new Date().toISOString(),
            cache_hit: false,
          },
        };
      throw error;
    }
  }
  /** Search, grouping the page's publications by DOCDB family. */
  async searchFamilies(
    query: string,
    options: TransportRequestOptions & {
      rangeBegin?: number;
      rangeEnd?: number;
    } = {},
  ) {
    const result = await this.search(query, {
      rangeBegin: 1,
      rangeEnd: 100,
      ...options,
    });
    const families = new Map<string, EpoSearchResult[]>();
    for (const member of result.data.results) {
      const id = member.family_id ?? "unknown";
      families.set(id, [...(families.get(id) ?? []), member]);
    }
    return {
      data: {
        query: result.data.query,
        total_results: result.data.total_results,
        range_begin: result.data.range_begin,
        range_end: result.data.range_end,
        families: [...families].map(([family_id, members]) => ({
          family_id,
          members,
        })),
      },
      provenance: result.provenance,
    };
  }
  getBiblio(
    number: string,
    options: PublicationOptions = {},
  ): Promise<EpoResult<EpoBiblioResponse>> {
    return this.xml(
      this.published(number, options, "biblio").path,
      parseBiblio,
      this.request(options),
    );
  }
  getCitations(
    number: string,
    options: PublicationOptions = {},
  ): Promise<EpoResult<EpoCitationResponse>> {
    const { value, path } = this.published(number, options, "biblio");
    return this.xml(
      path,
      (xml) => parseCitations(xml, value),
      this.request(options),
    );
  }
  getEquivalents(
    number: string,
    options: PublicationOptions = {},
  ): Promise<EpoResult<EpoEquivalentsResponse>> {
    return this.xml(
      this.published(number, options, "equivalents").path,
      parseEquivalents,
      this.request(options),
    );
  }
  /** Claims or description. OPS full text mainly covers EP and WO, plus some national offices. */
  async getFullText(
    number: string,
    section: "claims" | "description" = "claims",
    options: PublicationOptions = {},
  ): Promise<EpoResult<EpoFullTextResponse>> {
    const kind = z.enum(["claims", "description"]).parse(section);
    try {
      return await this.xml(
        this.published(number, options, kind).path,
        (xml) => parseFullText(xml, kind),
        this.request(options),
      );
    } catch (error) {
      if (error instanceof EpoOpsError && error.code === "NOT_FOUND")
        throw new EpoOpsError(
          `EPO has no ${kind} full text for ${number.trim()}. Older publications and most non-EP/non-WO documents are not indexed for full text; try biblio or family instead.`,
          404,
          "NOT_FOUND",
          error.faultCode,
        );
      throw error;
    }
  }
  getCpciBiblio(
    number: string,
    options: PublicationOptions & { condensed?: boolean } = {},
  ): Promise<EpoResult<CpciBiblioResponse>> {
    const { condensed, ...rest } = options;
    return this.xml(
      this.published(number, rest, "biblio").path,
      parseCpciBiblio,
      {
        ...this.request(rest),
        ...(condensed ? { searchParams: { cpci: "condensed" } } : {}),
      },
    );
  }
  /** INPADOC family. `constituents` adds biblio and/or legal data to each member. */
  getFamily(
    number: string,
    options: PublicationOptions & {
      constituents?: "biblio" | "legal" | "biblio,legal";
    } = {},
  ): Promise<EpoResult<EpoFamilyResponse>> {
    const { constituents, ...rest } = options;
    const docType = docTypeSchema.parse(rest.docType ?? "publication");
    const format = formatSchema.parse(rest.format ?? "docdb");
    const value = opsNumber(number, docType, format);
    const suffix = constituents
      ? `/${z.enum(["biblio", "legal", "biblio,legal"]).parse(constituents)}`
      : "";
    return this.xml(
      `${SERVICES}/family/${docType}/${format}/${segment(value, "number")}${suffix}`,
      parseFamily,
      this.request(rest),
    );
  }
  getLegalEvents(
    number: string,
    options: PublicationOptions = {},
  ): Promise<EpoResult<EpoLegalEventsResponse>> {
    const docType = docTypeSchema.parse(options.docType ?? "publication");
    const format = formatSchema.parse(options.format ?? "docdb");
    const value = opsNumber(number, docType, format);
    return this.xml(
      `${SERVICES}/legal/${docType}/${format}/${segment(value, "number")}`,
      parseLegalEvents,
      this.request(options),
    );
  }
  /** Raw European Patent Register XML for `view`. */
  getRegisterXml(
    number: string,
    view: "biblio" | "events" | "procedural-steps" | "upp" = "biblio",
    options: PublicationOptions = {},
  ) {
    const docType = docTypeSchema.parse(options.docType ?? "publication");
    const format = formatSchema.parse(options.format ?? "epodoc");
    const kind = z
      .enum(["biblio", "events", "procedural-steps", "upp"])
      .parse(view);
    return this.get(
      "text",
      `${SERVICES}/register/${docType}/${format}/${segment(normalize(number), "number")}/${kind}`,
      this.request(options),
      EPO_REGISTER_SOURCE,
    ).then((result) => ({
      ...result,
      provenance: { ...result.provenance, source_name: EPO_REGISTER_SOURCE },
    }));
  }
  private async register<T>(
    number: string,
    view: "biblio" | "events" | "procedural-steps" | "upp",
    parse: (xml: string, epoNumber: string) => T,
    options: PublicationOptions,
  ): Promise<EpoResult<T>> {
    const value = normalize(number);
    const result = await this.getRegisterXml(value, view, options);
    return { data: parse(result.data, value), provenance: result.provenance };
  }
  /**
   * Correction-aware register bibliography. Designations are application-stage
   * records; term-of-grant lapses cover the opposition period, not current
   * national validation or lapse status.
   */
  getRegisterBiblio(
    number: string,
    options: PublicationOptions = {},
  ): Promise<EpoResult<RegisterBiblioResponse>> {
    return this.register(number, "biblio", parseRegisterBiblio, options);
  }
  getRegisterEvents(
    number: string,
    options: PublicationOptions = {},
  ): Promise<EpoResult<RegisterEventsResponse>> {
    return this.register(number, "events", parseRegisterEvents, options);
  }
  getRegisterProceduralSteps(
    number: string,
    options: PublicationOptions = {},
  ): Promise<EpoResult<RegisterProceduralStepsResponse>> {
    return this.register(
      number,
      "procedural-steps",
      parseRegisterProceduralSteps,
      options,
    );
  }
  /**
   * Unitary Patent Package from the register; data is null when no unitary
   * effect was requested or recorded. UPC opt-out status is not in OPS.
   */
  getUnitaryPatentPackage(
    number: string,
    options: PublicationOptions = {},
  ): Promise<EpoResult<UnitaryPatentPackage | null>> {
    return this.register(number, "upp", parseUnitaryPatentPackage, options);
  }
  convertNumber(
    number: string,
    options: TransportRequestOptions & {
      docType?: DocType;
      inputFormat?: NumberFormat;
      outputFormat?: NumberFormat;
    } = {},
  ): Promise<EpoResult<EpoNumberConversionResponse>> {
    const {
      docType = "publication",
      inputFormat = "original",
      outputFormat = "docdb",
      ...rest
    } = options;
    return this.xml(
      `${SERVICES}/number-service/${docTypeSchema.parse(docType)}/${formatSchema.parse(inputFormat)}/${segment(number, "number")}/${formatSchema.parse(outputFormat)}`,
      parseNumberConversion,
      rest,
    );
  }
  /** Merge the FullDocument page images into one PDF, correcting 90-degree page rotation. */
  async downloadPdf(
    number: string,
    options: PublicationOptions = {},
  ): Promise<
    EpoResult<Uint8Array> & { pages: number; publicationNumber: string }
  > {
    const { value, path } = this.published(number, options, "images");
    const inquiry = await this.xml(
      path,
      parseFullDocumentImage,
      this.request(options),
    );
    const { link, pages } = inquiry.data;
    if (pages > this.maxPdfPages)
      throw new ApiError(
        `${value} has ${pages} pages; the configured limit is ${this.maxPdfPages}.`,
        200,
        "RESPONSE_TOO_LARGE",
      );
    const merged = await PDFDocument.create();
    for (let page = 1; page <= pages; page++) {
      const result = await this.get("bytes", `${SERVICES}/${link}.pdf`, {
        ...this.request(options),
        headers: { accept: "application/pdf" },
        searchParams: { Range: page },
      });
      let source: PDFDocument;
      try {
        source = await PDFDocument.load(result.data);
      } catch {
        throw new ApiError(
          `EPO OPS returned an invalid PDF for page ${page}.`,
          result.status,
          "INVALID_RESPONSE",
        );
      }
      const [copied] = await merged.copyPages(source, [0]);
      if (!copied)
        throw new ApiError(
          `EPO OPS page ${page} is empty.`,
          result.status,
          "INVALID_RESPONSE",
        );
      if (copied.getRotation().angle === 90) copied.setRotation(degrees(0));
      merged.addPage(copied);
    }
    return {
      data: await merged.save(),
      pages,
      publicationNumber: value,
      provenance: inquiry.provenance,
    };
  }

  retrieveCpc(
    symbol: string,
    options: TransportRequestOptions & {
      depth?: number | "all";
      ancestors?: boolean;
      navigation?: boolean;
    } = {},
  ): Promise<EpoResult<CpcRetrievalResponse>> {
    const { depth, ancestors, navigation, ...rest } = options;
    if (depth !== undefined && depth !== "all")
      z.number().int().min(0).max(10).parse(depth);
    return this.xml(
      `${SERVICES}/classification/cpc/${classSymbol(symbol)}`,
      parseCpcRetrieval,
      {
        ...rest,
        searchParams: {
          depth,
          ancestors: ancestors ? "true" : undefined,
          navigation: navigation ? "true" : undefined,
        },
      },
    );
  }
  searchCpc(
    query: string,
    options: TransportRequestOptions & {
      rangeBegin?: number;
      rangeEnd?: number;
    } = {},
  ): Promise<EpoResult<CpcSearchResponse>> {
    const { rangeBegin = 1, rangeEnd = 10, ...rest } = options;
    const begin = z.number().int().min(1).parse(rangeBegin);
    const end = z
      .number()
      .int()
      .min(begin)
      .max(begin + 99)
      .parse(rangeEnd);
    if (!query.trim()) throw new TypeError("A CPC search query is required.");
    const headers = new Headers(rest.headers);
    headers.set("x-ops-range", `${begin}-${end}`);
    return this.xml(`${SERVICES}/classification/cpc/search`, parseCpcSearch, {
      ...rest,
      headers,
      searchParams: { q: query },
    });
  }
  /** Concordance between CPC, ECLA and IPC; an empty body means no mapping. */
  async mapClassification(
    inputSchema: "cpc" | "ecla" | "ipc",
    symbol: string,
    outputSchema: "cpc" | "ecla" | "ipc",
    options: TransportRequestOptions & { additional?: boolean } = {},
  ): Promise<EpoResult<ClassificationMappingResponse>> {
    const schema = z.enum(["cpc", "ecla", "ipc"]);
    const { additional, ...rest } = options;
    const input = schema.parse(inputSchema.toLowerCase());
    const output = schema.parse(outputSchema.toLowerCase());
    const result = await this.get(
      "text",
      `${SERVICES}/classification/map/${input}/${classSymbol(symbol)}/${output}`,
      {
        ...rest,
        searchParams: { additional: additional ? "true" : undefined },
      },
    );
    return {
      data: result.data.trim().startsWith("<")
        ? parseClassificationMapping(result.data)
        : { input_schema: input, output_schema: output, mappings: [] },
      provenance: result.provenance,
    };
  }
  /**
   * Source-separated family, citation, legal-event and (for EP numbers)
   * register evidence for one publication. It does not fan out across family
   * members or infer family-wide legal status. Authentication and
   * configuration failures propagate; other source failures are recorded per
   * view, and the call fails only when every attempted view fails.
   */
  async getFamilyEvidence(
    number: string,
    options: TransportRequestOptions = {},
  ): Promise<FamilyEvidence> {
    const value = normalize(number);
    if (!value) throw new TypeError("A publication number is required.");
    const register = value.startsWith("EP");
    const views = {
      inpadoc_family: () => this.getFamily(value, options),
      simple_family_equivalents: () => this.getEquivalents(value, options),
      backward_citations: () => this.getCitations(value, options),
      worldwide_legal_events: () => this.getLegalEvents(value, options),
      register_biblio: register
        ? () => this.getRegisterBiblio(value, options)
        : undefined,
      register_events: register
        ? () => this.getRegisterEvents(value, options)
        : undefined,
      register_procedural_steps: register
        ? () => this.getRegisterProceduralSteps(value, options)
        : undefined,
    };
    const entries = await Promise.all(
      Object.entries(views).map(async ([name, run]) => {
        const sourceName = name.startsWith("register")
          ? EPO_REGISTER_SOURCE
          : EPO_OPS_SOURCE;
        if (!run) return [name, { outcome: "not_applicable" }] as const;
        try {
          const result = (await run()) as EpoResult<object>;
          return [
            name,
            {
              outcome: evidenceIsEmpty(name, result.data) ? "empty" : "ok",
              data: result.data,
              provenance: result.provenance,
            },
          ] as const;
        } catch (error) {
          if (
            error instanceof ConfigurationError ||
            (error instanceof EpoOpsError &&
              error.code === "AUTHENTICATION_FAILED")
          )
            throw error;
          if (!(error instanceof ApiError)) throw error;
          return [name, { outcome: "failed", error, sourceName }] as const;
        }
      }),
    );
    const attempted = entries.filter(
      ([, item]) => item.outcome !== "not_applicable",
    );
    const failed = attempted.filter(([, item]) => item.outcome === "failed");
    if (attempted.length && failed.length === attempted.length) {
      const first = failed[0]?.[1];
      if (first && "error" in first) throw first.error;
    }
    const blocks = Object.fromEntries(
      entries.map(([name, item]) => {
        if (item.outcome !== "failed") return [name, item];
        const error = item.error;
        const code = error.code;
        return [
          name,
          {
            outcome: code === "NOT_FOUND" ? "not_found" : "error",
            failure: {
              code:
                code === "NOT_FOUND"
                  ? "not_found"
                  : code === "RATE_LIMITED"
                    ? "rate_limited"
                    : code === "INVALID_RESPONSE"
                      ? "parse_error"
                      : ["NETWORK_ERROR", "TIMEOUT", "ABORTED"].includes(code)
                        ? "transport_error"
                        : error.status >= 500
                          ? "upstream_server_error"
                          : "upstream_api_error",
              message: error.message,
              retryable:
                error instanceof EpoOpsError
                  ? error.retryable
                  : ["NETWORK_ERROR", "TIMEOUT"].includes(code) ||
                    error.status >= 500,
              source_name: item.sourceName,
            },
          },
        ];
      }),
    );
    return {
      publication_number: value,
      ...(blocks as Omit<FamilyEvidence, "publication_number" | "limitations">),
      limitations: [...FAMILY_EVIDENCE_LIMITATIONS],
    };
  }

  /** CPC illustration referenced by a title part's media_id. */
  async getCpcMedia(
    mediaId: string,
    options: TransportRequestOptions & { accept?: string } = {},
  ) {
    const { accept = "image/gif", ...rest } = options;
    const id = mediaId
      .replace(/^\/?classification\/cpc\/media\//, "")
      .replace(/^\/+/, "");
    if (!/^[A-Za-z0-9._-]+$/.test(id))
      throw new TypeError("Invalid CPC media id.");
    const headers = new Headers(rest.headers);
    headers.set("accept", accept);
    const result = await this.get(
      "bytes",
      `${SERVICES}/classification/cpc/media/${id}`,
      {
        ...rest,
        headers,
      },
    );
    return {
      ...result,
      mediaId: id,
      mimeType: result.headers.get("content-type") ?? accept,
    };
  }
}

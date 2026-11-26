import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import { all, first, parseDocument, type Root } from "./google-patents/dom.js";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  HttpResponseError,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * The Unified Patent Court's decisions-and-orders listing, a Drupal Views
 * table at https://www.unifiedpatentcourt.org/en/decisions-and-orders. Each
 * row carries the case identifier, division, case type, parties and PDF/A
 * attachments, so the client reads only listing pages, as Python does.
 *
 * Since about October 2026 the site answers automated requests with a
 * Cloudflare challenge. That is reported as UPSTREAM_BLOCKED, never as an
 * empty page.
 */
export const UPC_DECISIONS_SOURCE = "Unified Patent Court";
export const UPC_DECISIONS_ORIGIN = "https://www.unifiedpatentcourt.org";
export const UPC_DECISIONS_LANGUAGES = ["en", "fr", "de"] as const;
export type UpcDecisionsLanguage = (typeof UPC_DECISIONS_LANGUAGES)[number];
const USER_AGENT =
  "patent-client-agents-upc/0.11 (+https://github.com/parkerhancock/patent-client-agents)";

export const UpcDecisionSchema = z.object({
  /** Canonical id: UPC_CFI_<n>/<yyyy>, UPC_CoA_<n>/<yyyy> or ACT_<n>/<yyyy>. */
  case_id: z.string(),
  /** Every case-identifier string in the row, verbatim. */
  raw_references: z.array(z.string()),
  /** Per-decision page (/en/node/<id>); Cloudflare-challenged upstream. */
  detail_url: z.string(),
  court: z.string(),
  type_of_action: z.string(),
  /** Split on "v."; the first entry is the claimant side. */
  parties: z.array(z.string()),
  pdf_urls: z.array(z.string()),
});
export type UpcDecision = z.infer<typeof UpcDecisionSchema>;

export const UpcDecisionSearchResponseSchema = z.object({
  page: z.number().int().nonnegative(),
  total_pages: z.number().int().positive(),
  hits: z.array(UpcDecisionSchema),
});
export type UpcDecisionSearchResponse = z.infer<
  typeof UpcDecisionSearchResponseSchema
>;

/** A division or procedural-language filter option. */
export const UpcFilterOptionSchema = z.object({
  id: z.string(),
  name: z.string(),
});
export type UpcFilterOption = z.infer<typeof UpcFilterOptionSchema>;

export interface UpcDecisionSearchInput {
  /** 0-indexed page; 0 is the most recent. */
  page?: number;
  /** "order" or "decision"; omit for both. */
  judgement_type?: string | null;
  /** "1" Court of Appeal, "2" Central CFI, "3" Local CFI, "4" Regional CFI. */
  court_type?: string | null;
  division?: string | null;
  proceedings_lang?: string | null;
}

export interface UpcDecisionsResult<T> {
  data: T;
  provenance: Provenance;
}

const CASE_ID = /\b(UPC[_-](?:CFI|CoA|COA)|ACT)[_-](\d{1,7})\/(\d{4})\b/;
const PARTIES_SPLIT = /\bv\.\s*/i;
const squash = (value: string) => value.replace(/\s+/g, " ").trim();

/**
 * Canonical underscored form: UPC-CFI-478/2025 → UPC_CFI_478/2025,
 * UPC-COA-35/2026 → UPC_CoA_35/2026. Zero padding is kept; an unrecognized
 * string comes back trimmed.
 */
export function canonicalUpcCaseId(raw: string): string {
  const match = CASE_ID.exec(raw);
  if (!match) return raw.trim();
  let prefix = (match[1] as string).replace("-", "_");
  if (prefix.toUpperCase() === "UPC_COA") prefix = "UPC_CoA";
  return `${prefix}_${match[2]}/${match[3]}`;
}

function parseParties(raw: string): string[] {
  if (!raw) return [];
  return raw
    .split(PARTIES_SPLIT)
    .filter((side) => side.trim())
    .map(squash);
}

/** Map a row's cells by Drupal Views column; the first parties cell wins. */
function rowCells(row: Element): Record<string, Element> {
  const cells: Record<string, Element> = {};
  for (const cell of all(row, "td")) {
    const headers = cell.getAttribute("headers") ?? "";
    if (headers.includes("view-field-judgement-application-no-1"))
      cells.case = cell;
    else if (headers.includes("view-field-location")) cells.court = cell;
    else if (headers.includes("view-field-upc-case-type")) cells.type = cell;
    else if (headers.includes("view-field-upc-document")) cells.document = cell;
    else if (headers.includes("view-field-judgement-parties-long"))
      cells.parties ??= cell;
  }
  return cells;
}

function descendantText(node: Node): string[] {
  const out: string[] = [];
  for (const child of Array.from(node.childNodes)) {
    if (child.nodeType === 3) out.push(child.textContent ?? "");
    else if (child.nodeType === 1) out.push(...descendantText(child));
  }
  return out;
}

const absolute = (href: string, baseUrl: string) =>
  href.startsWith("http") ? href : `${baseUrl}${href}`;

function caseData(cell: Element, baseUrl: string) {
  // Python first takes the cell's own text nodes (duplicates included), then
  // adds any other descendant text not already present.
  const refs: string[] = [];
  for (const node of Array.from(cell.childNodes)) {
    if (node.nodeType !== 3) continue;
    const value = squash(node.textContent ?? "");
    if (value && CASE_ID.test(value)) refs.push(value);
  }
  for (const piece of descendantText(cell)) {
    const value = squash(piece);
    if (value && CASE_ID.test(value) && !refs.includes(value)) refs.push(value);
  }
  const href =
    first(cell, 'a[class*="btn--primary"]')?.getAttribute("href") ?? "";
  return {
    case_id: refs[0] ? canonicalUpcCaseId(refs[0]) : "",
    raw_references: refs,
    detail_url: href ? absolute(href, baseUrl) : "",
  };
}

function pdfUrls(cell: Element, baseUrl: string): string[] {
  const urls: string[] = [];
  for (const anchor of all(cell, "a[href]")) {
    const href = anchor.getAttribute("href") ?? "";
    if (!href.toLowerCase().endsWith(".pdf")) continue;
    const url = absolute(href, baseUrl);
    if (!urls.includes(url)) urls.push(url);
  }
  return urls;
}

const cellText = (cell: Element | undefined) =>
  cell ? squash(cell.textContent ?? "") : "";

/**
 * Parse one listing page into rows and the total page count. The count comes
 * from the pager's last-page link (0-indexed), or 1 without a pager. A page
 * with no table at all is not a listing and raises INVALID_RESPONSE.
 */
export function parseUpcDecisionsPage(
  html: string,
  options: { baseUrl?: string } = {},
): { hits: UpcDecision[]; total_pages: number } {
  const baseUrl = options.baseUrl ?? UPC_DECISIONS_ORIGIN;
  const document = parseDocument(html);
  if (!first(document, "table") && !first(document, ".view-empty"))
    throw new ApiError(
      "UPC decisions page has no listing table; the page layout may have changed.",
      200,
      "INVALID_RESPONSE",
    );
  const hits: UpcDecision[] = [];
  const seen = new Set<string>();
  for (const row of all(document, "table tbody tr")) {
    const cells = rowCells(row);
    if (!cells.case) continue;
    const data = caseData(cells.case, baseUrl);
    if (!data.case_id || seen.has(data.case_id)) continue;
    seen.add(data.case_id);
    hits.push({
      case_id: data.case_id,
      raw_references: data.raw_references,
      detail_url: data.detail_url,
      court: cellText(cells.court),
      type_of_action: cellText(cells.type),
      parties: parseParties(cells.parties?.textContent ?? ""),
      pdf_urls: cells.document ? pdfUrls(cells.document, baseUrl) : [],
    });
  }
  let totalPages = 1;
  const last = first(document, 'li[class*="pager__item--last"] a');
  const page = /[?&]page=(\d+)/.exec(last?.getAttribute("href") ?? "");
  if (page) totalPages = Number(page[1]) + 1;
  return { hits, total_pages: totalPages };
}

/** (value, label) pairs from a named <select>, without the "All" option. */
function selectOptions(root: Root, name: string): UpcFilterOption[] {
  const options: UpcFilterOption[] = [];
  for (const option of all(root, `select[name="${name}"] option`)) {
    const id = option.getAttribute("value") ?? "";
    const label = squash(option.textContent ?? "");
    if (id && id !== "All" && label) options.push({ id, name: label });
  }
  return options;
}

/** Division filter options, deduplicated across the division_1..4 selects. */
export function parseUpcDivisions(html: string): UpcFilterOption[] {
  const document = parseDocument(html);
  const seen = new Set<string>();
  const out: UpcFilterOption[] = [];
  for (const field of ["division_1", "division_2", "division_3", "division_4"])
    for (const option of selectOptions(document, field))
      if (!seen.has(option.id)) {
        seen.add(option.id);
        out.push(option);
      }
  return out;
}

export function parseUpcLanguages(html: string): UpcFilterOption[] {
  return selectOptions(parseDocument(html), "proceedings_lang");
}

const isChallenge = (body: string) =>
  /<title>\s*Just a moment/i.test(body) ||
  body.includes("challenges.cloudflare.com") ||
  body.includes("cf-chl");

export class UpcDecisionsClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private readonly baseUrl: string;
  readonly language: UpcDecisionsLanguage;

  constructor(
    options: Omit<ClientOptions, "apiKey"> & {
      language?: UpcDecisionsLanguage;
    } = {},
  ) {
    super();
    const language = options.language ?? "en";
    if (!UPC_DECISIONS_LANGUAGES.includes(language))
      throw new ApiError(
        "language must be one of 'en', 'fr', 'de'",
        400,
        "INVALID_INPUT",
      );
    this.language = language;
    this.baseUrl = (options.baseUrl ?? UPC_DECISIONS_ORIGIN).replace(
      /\/+$/,
      "",
    );
    this.http = new GenericHttpTransport({
      ...options,
      timeoutMs: options.timeoutMs ?? 60_000,
      baseUrl: this.baseUrl,
      sourceName: UPC_DECISIONS_SOURCE,
      cache: { name: "upc_decisions" },
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }

  private get indexPath() {
    return `/${this.language}/decisions-and-orders`;
  }

  private async page(
    searchParams: Record<string, string | number>,
    options: TransportRequestOptions,
  ) {
    try {
      return await this.http.text("GET", this.indexPath, {
        ...options,
        readErrorBody: true,
        ...(Object.keys(searchParams).length ? { searchParams } : {}),
      });
    } catch (error) {
      if (
        error instanceof HttpResponseError &&
        (error.status === 403 || error.status === 503) &&
        isChallenge(error.bodyText)
      )
        throw new ApiError(
          "The UPC decisions site answered with a Cloudflare challenge; automated access is blocked upstream.",
          error.status,
          "UPSTREAM_BLOCKED",
        );
      throw error;
    }
  }

  /** One listing page, optionally filtered. */
  async search(
    input: UpcDecisionSearchInput = {},
    options: TransportRequestOptions = {},
  ): Promise<UpcDecisionsResult<UpcDecisionSearchResponse>> {
    const page = input.page ?? 0;
    if (!Number.isSafeInteger(page) || page < 0)
      throw new ApiError("page must be at least 0", 400, "INVALID_INPUT");
    // Drupal Views renders its empty template for ?page=0, so page 0 omits it.
    const params: Record<string, string | number> = {};
    if (page > 0) params.page = page;
    if (input.judgement_type) params.judgement_type = input.judgement_type;
    if (input.court_type) params.court_type = input.court_type;
    if (input.division != null) params.division_1 = input.division;
    if (input.proceedings_lang != null)
      params.proceedings_lang = input.proceedings_lang;
    const result = await this.page(params, options);
    const parsed = parseUpcDecisionsPage(result.data, {
      baseUrl: this.baseUrl,
    });
    return { data: { page, ...parsed }, provenance: result.provenance };
  }

  async listDivisions(
    options: TransportRequestOptions = {},
  ): Promise<UpcDecisionsResult<UpcFilterOption[]>> {
    const result = await this.page({}, options);
    return {
      data: parseUpcDivisions(result.data),
      provenance: result.provenance,
    };
  }

  async listLanguages(
    options: TransportRequestOptions = {},
  ): Promise<UpcDecisionsResult<UpcFilterOption[]>> {
    const result = await this.page({}, options);
    return {
      data: parseUpcLanguages(result.data),
      provenance: result.provenance,
    };
  }
}

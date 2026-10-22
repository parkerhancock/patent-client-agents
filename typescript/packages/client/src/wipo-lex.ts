import { CachedClient } from "./cache/client.js";
import { parseDocument, squash } from "./google-patents/dom.js";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * WIPO Lex legislation (https://www.wipo.int/wipolex/), scraped from the
 * server-rendered results and detail pages. There is no documented API.
 */
export const WIPO_LEX_SOURCE = "WIPO Lex";
export const WIPO_LEX_ORIGIN = "https://www.wipo.int";
const RESULTS_PATH = "/wipolex/en/legislation/results";
const DETAILS_PATH = "/wipolex/en/legislation/details";

/** subjectMatter codes from the search form, with the site's labels. */
export const WIPO_LEX_SUBJECT_MATTER = {
  1: "Patents (Inventions)",
  2: "Utility Models",
  3: "Industrial Designs",
  4: "Trademarks",
  5: "Geographical Indications",
  6: "Trade Names",
  7: "Layout Designs of Integrated Circuits",
  8: "Competition",
  9: "Undisclosed Information (Trade Secrets)",
  10: "Plant Variety Protection",
  11: "Copyright and Related Rights (Neighboring Rights)",
  12: "Enforcement of IP and Related Laws",
  13: "Alternative Dispute Resolution (ADR)",
  14: "Domain Names",
  15: "Genetic Resources",
  16: "Traditional Cultural Expressions",
  17: "Transfer of Technology",
  18: "Traditional Knowledge (TK)",
  19: "IP Regulatory Body",
  20: "Other",
  21: "Industrial Property",
} as const;
/** typeOfText codes from the search form. */
export const WIPO_LEX_TYPE_OF_TEXT = {
  205: "Main IP Laws",
  207: "Implementing Rules/Regulations",
  210: "IP-related Laws",
  213: "Framework Laws",
  214: "Other Texts",
  215: "National IP Strategy",
} as const;

export interface WipoLexSearchOptions {
  /** Jurisdiction codes as WIPO Lex lists them: ISO alpha-2 or a regional code (EU, OAPI, GCC). */
  countryCodes?: readonly string[];
  subjectMatter?: readonly number[];
  typeOfText?: readonly number[];
  /** Title and notes; quotes and AND/OR work as on the site. */
  keywords?: string;
  /** Inclusive YYYY-MM-DD bounds on the date of the text. */
  startDate?: string;
  endDate?: string;
  /** Superseded versions and supplemental texts as well as the latest versions. */
  includeHistorical?: boolean;
}
export interface WipoLexSearchHit {
  legislation_id: string;
  /** Display title with its inline citation. */
  title: string;
  url: string;
}
export interface WipoLexSearchResult {
  /** Every match; WIPO Lex returns the whole list in one page. */
  data: WipoLexSearchHit[];
  /** The page's own legislation count, checked against the parsed hits. */
  total: number;
  query_url: string;
  provenance: Provenance;
}
export interface WipoLexFileLink {
  label: string;
  /** Signed download URL; it stops working at expires_at. */
  url: string;
  mime_type: string | null;
  /** When the signed URL expires (WIPO signs them for five minutes), or null if unsigned. */
  expires_at: string | null;
}
export interface WipoLexLegislation {
  legislation_id: string;
  title: string;
  jurisdiction: string | null;
  /** The page description: jurisdiction, year of version, dates, type and subjects. */
  summary: string | null;
  url: string;
  files: WipoLexFileLink[];
}

const MIME: Record<string, string> = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  doc: "application/msword",
};
const invalidInput = (message: string) =>
  new ApiError(message, 400, "INVALID_INPUT");
const invalidResponse = (message: string, status = 200) =>
  new ApiError(message, status, "INVALID_RESPONSE");
/** YYYY-MM-DD -> DD/MM/YYYY, the only date form the results page accepts (ISO dates get a 503). */
function formDate(value: string, label: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match || Number.isNaN(Date.parse(value)))
    throw invalidInput(`${label} must use YYYY-MM-DD.`);
  return `${match[3]}/${match[2]}/${match[1]}`;
}

export class WipoLexClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      timeoutMs: 60_000,
      ...options,
      baseUrl: options.baseUrl ?? WIPO_LEX_ORIGIN,
      sourceName: WIPO_LEX_SOURCE,
      cache: { name: "wipo_lex" },
      headers: {
        "user-agent":
          "patent-client-agents-wipolex/0.1 (+https://patentclient.com)",
        accept: "text/html,application/xhtml+xml",
      },
    });
  }

  /** Search the legislation collection; filters AND together. */
  async search(
    search: WipoLexSearchOptions,
    options: TransportRequestOptions = {},
  ): Promise<WipoLexSearchResult> {
    const params = new URLSearchParams();
    for (const raw of search.countryCodes ?? []) {
      const code = raw.trim().toUpperCase();
      if (!/^[A-Z]{2,6}$/.test(code))
        throw invalidInput(`Unknown WIPO Lex jurisdiction code: ${raw}`);
      params.append("countryOrgs", code);
    }
    for (const code of search.subjectMatter ?? []) {
      if (!Object.hasOwn(WIPO_LEX_SUBJECT_MATTER, code))
        throw invalidInput(`Unknown WIPO Lex subject_matter code: ${code}`);
      params.append("subjectMatter", String(code));
    }
    for (const code of search.typeOfText ?? []) {
      if (!Object.hasOwn(WIPO_LEX_TYPE_OF_TEXT, code))
        throw invalidInput(`Unknown WIPO Lex type_of_text code: ${code}`);
      params.append("typeOfText", String(code));
    }
    const keywords = search.keywords?.trim();
    if (keywords) params.append("keywords", keywords);
    if (search.startDate !== undefined || search.endDate !== undefined) {
      // Observed October 2026: the site drops the date filter whenever a
      // jurisdiction is set, so the combination would silently return undated results.
      if (params.has("countryOrgs"))
        throw invalidInput(
          "WIPO Lex ignores start_date/end_date when country_codes is set; drop one of the filters.",
        );
      if (
        search.startDate !== undefined &&
        search.endDate !== undefined &&
        search.startDate > search.endDate
      )
        throw invalidInput("start_date must not be later than end_date.");
      if (search.startDate !== undefined)
        params.append("sDate", formDate(search.startDate, "start_date"));
      if (search.endDate !== undefined)
        params.append("eDate", formDate(search.endDate, "end_date"));
    }
    if (![...params.keys()].length)
      throw invalidInput(
        "Give at least one WIPO Lex filter (country_codes, subject_matter, type_of_text, keywords or a date).",
      );
    // The form's "Include supplemental and historical laws: No" sends last=true.
    params.append("last", search.includeHistorical ? "false" : "true");
    const result = await this.http.text("GET", RESULTS_PATH, {
      ...options,
      searchParams: params,
    });
    const queryUrl = `${WIPO_LEX_ORIGIN}${RESULTS_PATH}?${params}`;
    const { hits, total } = parseWipoLexSearch(result.data, result.status);
    return {
      data: hits,
      total,
      query_url: queryUrl,
      provenance: result.provenance,
    };
  }

  /** One legislation entry: title, jurisdiction, description and file links. */
  async get(
    legislationId: string,
    options: TransportRequestOptions = {},
  ): Promise<{ data: WipoLexLegislation; provenance: Provenance }> {
    const id = legislationId.trim();
    if (!/^\d{1,10}$/.test(id))
      throw invalidInput(
        `WIPO Lex legislation IDs are numeric (e.g. '23293'), not '${legislationId}'.`,
      );
    let result: Awaited<ReturnType<GenericHttpTransport["text"]>>;
    try {
      result = await this.http.text("GET", `${DETAILS_PATH}/${id}`, options);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404)
        throw new ApiError(
          `WIPO Lex has no legislation entry ${id}.`,
          404,
          "NOT_FOUND",
        );
      throw error;
    }
    return {
      data: parseWipoLexLegislation(result.data, id, result.status),
      provenance: result.provenance,
    };
  }
}

/** Parse a legislation results page. Exported for fixtures and offline use. */
export function parseWipoLexSearch(
  html: string,
  status = 200,
): { hits: WipoLexSearchHit[]; total: number } {
  const document = parseDocument(html);
  // One tab per collection with matches ("Laws (15)", "Treaties (73)");
  // the laws tab is absent when only treaties or judgments match.
  const tabs = Array.from(document.querySelectorAll("a.profile-tab-btn"));
  const laws = tabs.find((a) => a.getAttribute("data-tab") === "laws");
  const count = laws && /\((\d+)\)/.exec(laws.textContent ?? "")?.[1];
  let total: number;
  if (count) total = Number(count);
  else if (
    (!laws && tabs.length) ||
    (!tabs.length && /\b0 records displayed\b/.test(html))
  )
    total = 0;
  else
    throw invalidResponse(
      "WIPO Lex returned a page without a legislation count; it may have changed.",
      status,
    );
  const seen = new Set<string>();
  const hits: WipoLexSearchHit[] = [];
  for (const anchor of Array.from(
    document.querySelectorAll('a[href*="/legislation/details/"]'),
  )) {
    const href = anchor.getAttribute("href") ?? "";
    const id = /\/wipolex\/[a-z]{2}\/legislation\/details\/(\d+)/.exec(
      href,
    )?.[1];
    const title = squash(anchor.textContent ?? "");
    if (!id || !title || seen.has(id)) continue;
    seen.add(id);
    hits.push({
      legislation_id: id,
      title,
      url: new URL(href, WIPO_LEX_ORIGIN).href,
    });
  }
  if (hits.length !== total)
    throw invalidResponse(
      `WIPO Lex reports ${total} laws but ${hits.length} could be read; the page may have changed.`,
      status,
    );
  return { hits, total };
}

/** Parse a legislation detail page. Exported for fixtures and offline use. */
export function parseWipoLexLegislation(
  html: string,
  legislationId: string,
  status = 200,
): WipoLexLegislation {
  const document = parseDocument(html);
  const meta = (selector: string) =>
    document.querySelector(selector)?.getAttribute("content")?.trim() || null;
  const ogTitle = meta('meta[property="og:title"]');
  if (!ogTitle)
    throw invalidResponse(
      `WIPO Lex page for ${legislationId} has no title; it may have changed.`,
      status,
    );
  const canonical = meta('meta[property="og:url"]');
  const id =
    (canonical && /\/legislation\/details\/(\d+)/.exec(canonical)?.[1]) ||
    legislationId;
  const summary = meta('meta[name="description"]');
  // og:title is "<Law>, <Jurisdiction>, WIPO Lex". The description starts with
  // the jurisdiction, which can itself hold a comma ("Hong Kong, China").
  let title = ogTitle;
  let jurisdiction: string | null = null;
  if (ogTitle.endsWith(", WIPO Lex")) {
    const stripped = ogTitle.slice(0, -", WIPO Lex".length);
    const described = summary?.split(" - ")[0]?.trim();
    if (described && stripped.endsWith(`, ${described}`)) {
      title = stripped.slice(0, -`, ${described}`.length).trim();
      jurisdiction = described;
    } else {
      const comma = stripped.lastIndexOf(",");
      if (comma >= 0) {
        title = stripped.slice(0, comma).trim();
        jurisdiction = stripped.slice(comma + 1).trim();
      }
    }
  }
  const files: WipoLexFileLink[] = [];
  const seen = new Set<string>();
  for (const anchor of Array.from(document.querySelectorAll("a[href]"))) {
    const href = anchor.getAttribute("href") ?? "";
    let url: URL;
    try {
      url = new URL(href, WIPO_LEX_ORIGIN);
    } catch {
      continue;
    }
    const extension = /\.(pdf|docx|doc)$/i
      .exec(url.pathname)?.[1]
      ?.toLowerCase();
    if (!extension || seen.has(url.href)) continue;
    seen.add(url.href);
    const expires = Number(url.searchParams.get("Expires"));
    files.push({
      label: squash(anchor.textContent ?? "") || "Attachment",
      url: url.href,
      mime_type: MIME[extension] ?? null,
      expires_at:
        Number.isSafeInteger(expires) && expires > 0
          ? new Date(expires * 1000).toISOString()
          : null,
    });
  }
  return {
    legislation_id: id,
    title,
    jurisdiction,
    summary,
    url: canonical ?? `${WIPO_LEX_ORIGIN}${DETAILS_PATH}/${id}`,
    files,
  };
}

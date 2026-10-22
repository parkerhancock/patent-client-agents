import { z } from "zod";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * Federal Circuit opinions and orders from the court's WordPress DataTables
 * index (https://www.cafc.uscourts.gov/home/case-information/opinions-orders/).
 * The AJAX endpoint needs a nonce embedded in the opinions page; no cookie.
 */
export const CAFC_SOURCE = "U.S. Court of Appeals for the Federal Circuit";
export const CAFC_ORIGIN = "https://www.cafc.uscourts.gov";
export const CAFC_OPINIONS_PATH = "/home/case-information/opinions-orders/";
const API_PATH = "/wp-admin/admin-ajax.php?action=get_wdtable&table_id=1";
/** Origins that bring patent appeals: the USPTO, district courts, the ITC and the Court of Federal Claims. */
export const CAFC_PATENT_ORIGINS = ["PTO", "DCT", "ITC", "CFC"] as const;
/** WordPress nonces last 12-24 hours; refresh well inside that. */
const NONCE_TTL_MS = 60 * 60 * 1000;
const PAGE_SIZE = 100;

const COLUMNS = [
  ["Release_Date", true, true, false],
  ["Appeal_Number", true, true, false],
  ["Origin", true, true, true],
  ["Document_Type", true, true, true],
  ["Case_Name", true, true, false],
  ["Status", true, true, true],
  ["File_Path", false, false, false],
] as const;

export interface CafcOpinion {
  appeal_number: string;
  /** ISO date (YYYY-MM-DD), or null when the row's date is unparseable. */
  release_date: string | null;
  /** PTO, DCT, ITC, CFC, MSPB, and so on. */
  origin: string;
  /** OPINION, ORDER, RULE 36 JUDGMENT, ... */
  document_type: string;
  case_name: string;
  case_name_short: string;
  /** Precedential or Nonprecedential. */
  precedential_status: string;
  /** Path of the PDF relative to the court's site. */
  file_path: string;
  pdf_url: string;
  is_patent_case: boolean;
  patent_confidence: number;
  patent_keywords: string[];
}

export interface CafcSearchOptions {
  /** Free text matched by the court's index across appeal number, case name and other columns. */
  query?: string;
  /** Inclusive YYYY-MM-DD bounds. dateTo requires dateFrom and defaults to today. */
  dateFrom?: string;
  dateTo?: string;
  origins?: readonly string[];
  /** Positive cap on rows returned; pages of 100 are fetched until it is met. */
  maxResults: number;
  offset?: number;
}
export interface CafcSearchResult {
  data: CafcOpinion[];
  /** recordsFiltered: rows matching the query and filters upstream. */
  total: number;
  provenance: Provenance;
}

const ResponseSchema = z.looseObject({
  data: z.array(z.array(z.unknown())),
  recordsFiltered: z.union([z.number(), z.string()]),
  recordsTotal: z.union([z.number(), z.string()]).optional(),
  error: z.unknown().optional(),
});

const KEYWORDS: Record<string, { weight: number; keywords: string[] }> = {
  strong_indicators: {
    weight: 0.9,
    keywords: [
      "patent",
      "patents",
      "patented",
      "patentee",
      "patentability",
      "uspto",
      "patent and trademark office",
      "patent office",
      "ptab",
      "patent trial and appeal board",
      "ipr",
      "inter partes review",
      "pgr",
      "post-grant review",
      "post grant review",
      "cbm",
      "covered business method",
      "iancu",
      "vidal",
    ],
  },
  statute_references: {
    weight: 0.8,
    keywords: [
      "35 u.s.c",
      "35 usc",
      "section 101",
      "section 102",
      "section 103",
      "section 112",
      "§ 101",
      "§ 102",
      "§ 103",
      "§ 112",
      "§101",
      "§102",
      "§103",
      "§112",
    ],
  },
  technical_terms: {
    weight: 0.65,
    keywords: [
      "obviousness",
      "non-obvious",
      "nonobvious",
      "infringement",
      "infringed",
      "infringing",
      "claims",
      "claim construction",
      "claim interpretation",
      "prior art",
      "novelty",
      "anticipation",
      "anticipated",
      "enablement",
      "written description",
      "indefiniteness",
      "inventive step",
      "prosecution history",
    ],
  },
  parties: {
    weight: 0.7,
    keywords: [
      "andrei iancu",
      "katherine vidal",
      "kathi vidal",
      "director of the united states patent",
      "commissioner for patents",
      "commissioner of patents",
      "board of patent appeals",
    ],
  },
  case_types: {
    weight: 0.7,
    keywords: [
      "reexamination",
      "reissue",
      "interference",
      "derivation proceeding",
      "patent term adjustment",
      "patent term extension",
    ],
  },
};
const FALSE_POSITIVES =
  /patient\s+care|patient\s+treatment|patient\s+safety|medical\s+patient|patent\s+leather/i;
const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const PATTERNS = Object.entries(KEYWORDS).map(
  ([category, { weight, keywords }]) => ({
    category,
    weight,
    pattern: new RegExp(
      keywords
        .map((keyword) =>
          ["ipr", "pgr", "cbm"].includes(keyword)
            ? `\\b${keyword}(?=\\d|\\b)`
            : `\\b${escapeRegExp(keyword)}\\b`,
        )
        .join("|"),
      "gi",
    ),
  }),
);

/**
 * Heuristic patent-case classifier over a case name (and optional text),
 * scored the same way as the Python PatentClassifier. A case is patent-related
 * at confidence 0.5 or above.
 */
export function classifyPatentCase(
  caseName: string,
  text?: string,
): { isPatentCase: boolean; confidence: number; keywords: string[] } {
  let haystack = caseName.toLowerCase();
  if (text) haystack += ` ${text.slice(0, 5000).toLowerCase()}`;
  if (FALSE_POSITIVES.test(haystack))
    return { isPatentCase: false, confidence: 0, keywords: [] };
  const matches = new Set<string>();
  const scores = new Map<string, number>();
  for (const { category, weight, pattern } of PATTERNS) {
    const unique = new Set(
      [...haystack.matchAll(pattern)].map((m) => m[0].toLowerCase()),
    );
    if (!unique.size) continue;
    for (const match of unique) matches.add(match);
    scores.set(category, weight * Math.min(0.8 + (unique.size - 1) * 0.1, 1));
  }
  let confidence = scores.size ? Math.max(...scores.values()) : 0;
  if (scores.size >= 2) confidence = Math.min(confidence * 1.1, 0.95);
  if (matches.size >= 5) confidence = Math.min(confidence * 1.1, 0.95);
  else if (matches.size >= 3) confidence = Math.min(confidence * 1.05, 0.95);
  if (
    scores.has("strong_indicators") &&
    ["uspto", "ptab", "inter partes review"].some((k) => matches.has(k))
  )
    confidence = Math.max(confidence, 0.9);
  confidence = Math.round(confidence * 1000) / 1000;
  return {
    isPatentCase: confidence >= 0.5,
    confidence,
    keywords: [...matches],
  };
}

/** "2024-1945" or "24-1945" -> "24-1945", the form the court's index stores and matches. */
export function normalizeAppealNumber(value: string): string {
  const match = /^\s*(?:\d{2})?(\d{2})-(\d{4})\s*$/.exec(value);
  return match ? `${match[1]}-${match[2]}` : value.trim();
}

const isoDate = (value: string, label: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(value)))
    throw new ApiError(`${label} must use YYYY-MM-DD.`, 400, "INVALID_INPUT");
  return value;
};
const today = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};
/** YYYY-MM-DD -> MM/DD/YYYY, the index's range format. */
const usDate = (value: string) => {
  const [y, m, d] = value.split("-");
  return `${m}/${d}/${y}`;
};
const invalid = (message: string, status = 200) =>
  new ApiError(message, status, "INVALID_RESPONSE");
const decodeEntities = (value: string) =>
  value
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;|&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");

export class CafcClient {
  private readonly http: GenericHttpTransport;
  private nonce: { value: string; at: number } | undefined;
  private draw = 1;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      timeoutMs: options.timeoutMs ?? 60_000,
      baseUrl: options.baseUrl ?? CAFC_ORIGIN,
      sourceName: CAFC_SOURCE,
      // The court's edge has rejected non-browser user agents on the AJAX endpoint.
      headers: {
        "user-agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
      },
    });
  }

  private async getNonce(
    options: TransportRequestOptions,
    refresh = false,
  ): Promise<string> {
    if (!refresh && this.nonce && Date.now() - this.nonce.at < NONCE_TTL_MS)
      return this.nonce.value;
    const page = await this.http.text("GET", CAFC_OPINIONS_PATH, {
      ...options,
      headers: { accept: "text/html" },
    });
    const input = /<input[^>]*id="wdtNonceFrontendServerSide_1"[^>]*>/i.exec(
      page.data,
    )?.[0];
    const value = input && /value="([a-f0-9]{10})"/i.exec(input)?.[1];
    if (!value)
      throw invalid(
        "Could not find the opinions table nonce on the CAFC opinions page.",
      );
    this.nonce = { value, at: Date.now() };
    return value;
  }

  private form(
    nonce: string,
    start: number,
    length: number,
    query: string,
    range: string,
    origins: string,
  ): Record<string, string> {
    const form: Record<string, string> = {
      draw: String(this.draw++),
      start: String(start),
      length: String(length),
      "search[value]": query,
      "search[regex]": "false",
      "order[0][column]": "0",
      "order[0][dir]": "desc",
      wdtNonce: nonce,
      sRangeSeparator: "|",
    };
    COLUMNS.forEach(([name, searchable, orderable, regex], i) => {
      form[`columns[${i}][data]`] = String(i);
      form[`columns[${i}][name]`] = name;
      form[`columns[${i}][searchable]`] = String(searchable);
      form[`columns[${i}][orderable]`] = String(orderable);
      form[`columns[${i}][search][value]`] =
        i === 0 ? range : i === 2 ? origins : "";
      form[`columns[${i}][search][regex]`] = String(regex);
    });
    return form;
  }

  private async page(
    form: (nonce: string) => Record<string, string>,
    options: TransportRequestOptions,
  ) {
    const request = async (nonce: string) =>
      this.http.json("POST", API_PATH, {
        ...options,
        form: form(nonce),
        headers: {
          accept: "application/json, text/javascript, */*; q=0.01",
          "x-requested-with": "XMLHttpRequest",
          origin: CAFC_ORIGIN,
          referer: `${CAFC_ORIGIN}${CAFC_OPINIONS_PATH}`,
        },
      });
    let result = await request(await this.getNonce(options));
    // An expired nonce makes WordPress answer with a bare -1 or 0; refresh once.
    if (!result.data || typeof result.data !== "object")
      result = await request(await this.getNonce(options, true));
    return result;
  }

  /** Search opinions and orders, newest first, with optional text, date and origin filters. */
  async search(
    search: CafcSearchOptions,
    options: TransportRequestOptions = {},
  ): Promise<CafcSearchResult> {
    const offset = search.offset ?? 0;
    if (!Number.isSafeInteger(offset) || offset < 0)
      throw new ApiError(
        "offset must be a non-negative integer.",
        400,
        "INVALID_INPUT",
      );
    if (!Number.isSafeInteger(search.maxResults) || search.maxResults <= 0)
      throw new ApiError(
        "maxResults must be a positive integer.",
        400,
        "INVALID_INPUT",
      );
    if (search.dateTo !== undefined && search.dateFrom === undefined)
      throw new ApiError(
        "date_to requires date_from; an end-only range is unsupported.",
        400,
        "INVALID_INPUT",
      );
    let range = "";
    if (search.dateFrom !== undefined) {
      const from = isoDate(search.dateFrom, "date_from");
      const to =
        search.dateTo === undefined
          ? today()
          : isoDate(search.dateTo, "date_to");
      if (from > to)
        throw new ApiError(
          "date_from must not be later than date_to (default: today).",
          400,
          "INVALID_INPUT",
        );
      range = `${usDate(from)}|${usDate(to)}`;
    }
    const origins = (search.origins ?? []).join("|");
    const query = search.query?.trim() ?? "";
    const opinions: CafcOpinion[] = [];
    let start = offset;
    let total = 0;
    let provenance: Provenance | undefined;
    for (;;) {
      const length = Math.min(PAGE_SIZE, search.maxResults - opinions.length);
      const result = await this.page(
        (nonce) => this.form(nonce, start, length, query, range, origins),
        options,
      );
      provenance ??= result.provenance;
      const parsed = ResponseSchema.safeParse(result.data);
      if (!parsed.success)
        throw invalid(
          "CAFC response omitted a valid data array; coverage is unknown.",
          result.status,
        );
      if (parsed.data.error)
        throw invalid(
          "CAFC reported a source error; coverage is unknown.",
          result.status,
        );
      const rows = parsed.data.data;
      if (
        rows.length > length ||
        rows.some(
          (row) =>
            row.length < 7 ||
            row.slice(0, 7).some((cell) => typeof cell !== "string"),
        )
      )
        throw invalid(
          "CAFC returned malformed or oversized rows; coverage is unknown.",
          result.status,
        );
      const count = (value: unknown, key: string) => {
        const number =
          typeof value === "string" && /^\d+$/.test(value)
            ? Number(value)
            : value;
        if (!Number.isSafeInteger(number) || (number as number) < 0)
          throw invalid(
            `CAFC omitted a valid ${key}; coverage is unknown.`,
            result.status,
          );
        return number as number;
      };
      // recordsTotal is unfiltered; only recordsFiltered locates this query's end.
      total = count(parsed.data.recordsFiltered, "recordsFiltered");
      const unfiltered =
        parsed.data.recordsTotal === undefined
          ? undefined
          : count(parsed.data.recordsTotal, "recordsTotal");
      if (
        (rows.length && start + rows.length > total) ||
        (!rows.length && start < total) ||
        (unfiltered !== undefined && total > unfiltered)
      )
        throw invalid(
          "CAFC page contradicts its total count; retry the source query.",
          result.status,
        );
      opinions.push(...rows.map((row) => parseRow(row as string[])));
      start += rows.length;
      if (opinions.length >= search.maxResults || start >= total) break;
    }
    return {
      data: opinions,
      total,
      provenance: provenance as Provenance,
    };
  }

  /** Opinions from the four patent-relevant origins (PTO, DCT, ITC, CFC), which also carry non-patent cases. */
  searchPatentOpinions(
    search: Omit<CafcSearchOptions, "origins" | "query">,
    options: TransportRequestOptions = {},
  ): Promise<CafcSearchResult> {
    return this.search({ ...search, origins: CAFC_PATENT_ORIGINS }, options);
  }

  /**
   * Every index row for one appeal number (two- or four-digit year). An
   * appeal can have several documents, such as an order and an opinion.
   */
  async findAppeal(
    appealNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<CafcSearchResult> {
    const normalized = normalizeAppealNumber(appealNumber);
    const result = await this.search(
      { query: normalized, maxResults: PAGE_SIZE },
      options,
    );
    if (result.total > PAGE_SIZE)
      throw new ApiError(
        `More than ${PAGE_SIZE} CAFC rows match ${normalized}; pass the exact document URL.`,
        400,
        "AMBIGUOUS",
      );
    return {
      ...result,
      data: result.data.filter(
        (opinion) => opinion.appeal_number === normalized,
      ),
    };
  }

  /** Download an opinion PDF by its official URL on www.cafc.uscourts.gov/opinions-orders/. */
  async downloadPdf(
    pdfUrl: string,
    options: TransportRequestOptions = {},
  ): Promise<{ data: Uint8Array; provenance: Provenance; filename: string }> {
    const url = officialPdfUrl(pdfUrl);
    if (!url)
      throw new ApiError(
        "document_url must be an official CAFC opinions-orders PDF URL.",
        400,
        "INVALID_INPUT",
      );
    const result = await this.http.bytes("GET", url.pathname, {
      ...options,
      headers: { accept: "application/pdf" },
    });
    const head = new TextDecoder().decode(result.data.subarray(0, 5));
    if (head !== "%PDF-")
      throw invalid("CAFC returned something other than a PDF.", result.status);
    return {
      data: result.data,
      provenance: result.provenance,
      filename: decodeURIComponent(
        url.pathname.split("/").pop() ?? "opinion.pdf",
      ),
    };
  }
}

/** The parsed URL when it is an official opinions-orders PDF, otherwise null. */
export function officialPdfUrl(value: string): URL | null {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  return url.protocol === "https:" &&
    url.host === "www.cafc.uscourts.gov" &&
    url.pathname.startsWith("/opinions-orders/") &&
    url.pathname.toLowerCase().endsWith(".pdf") &&
    !url.search &&
    !url.hash &&
    !url.username &&
    !url.password
    ? url
    : null;
}

function parseRow(row: string[]): CafcOpinion {
  const [date = "", appeal = "", origin = "", type = "", nameHtml = ""] = row;
  const status = row[5] ?? "";
  const filePath = row[6] ?? "";
  const us = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(date);
  const caseName = decodeEntities(
    /sort="([^"]+)"/.exec(nameHtml)?.[1] ?? nameHtml.replace(/<[^>]+>/g, ""),
  ).trim();
  const { isPatentCase, confidence, keywords } = classifyPatentCase(caseName);
  return {
    appeal_number: appeal,
    release_date: us ? `${us[3]}-${us[1]}-${us[2]}` : null,
    origin,
    document_type: type,
    case_name: caseName,
    case_name_short: caseName.replace(/\s*\[[^\]]+\]\s*$/, "").trim(),
    precedential_status: status,
    file_path: filePath,
    pdf_url: filePath ? `${CAFC_ORIGIN}/${filePath.replace(/^\/+/, "")}` : "",
    is_patent_case: isPatentCase,
    patent_confidence: confidence,
    patent_keywords: keywords,
  };
}

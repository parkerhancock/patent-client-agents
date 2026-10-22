import {
  ApiError,
  CAFC_SOURCE,
  type CafcClient,
  type CafcOpinion,
  classifyPatentCase,
  normalizeAppealNumber,
  officialPdfUrl,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listToolOptions,
} from "./shared.js";

/** Lean projection of an opinion row, field for field with Python's _stub_opinion. */
export function stubOpinion(opinion: CafcOpinion): Record<string, unknown> {
  return {
    appeal_number: opinion.appeal_number,
    case_name_short: opinion.case_name_short || opinion.case_name,
    release_date: opinion.release_date,
    origin: opinion.origin,
    document_type: opinion.document_type,
    precedential_status: opinion.precedential_status,
    is_patent_case: opinion.is_patent_case,
    pdf_url: opinion.pdf_url,
  };
}

const cursorSchema = z.object({
  offset: z.number().int().nonnegative(),
  limit: z.number().int().min(1).max(100),
});
const encodeCursor = (offset: number, limit: number) =>
  Buffer.from(JSON.stringify({ offset, limit })).toString("base64url");
function pageArgs(
  offset: number,
  limit: number,
  nextCursor: string | null | undefined,
) {
  if (!nextCursor) return { offset, limit };
  try {
    return cursorSchema.parse(
      JSON.parse(Buffer.from(nextCursor, "base64url").toString("utf8")),
    );
  } catch {
    throw new Error("invalid CAFC next_cursor");
  }
}

export interface CafcSearchInput {
  query?: string | null | undefined;
  patent_only: boolean;
  limit: number;
  full: boolean;
  offset: number;
  next_cursor?: string | null | undefined;
}
/** search_cafc_opinions; also serves search_litigation(forum='cafc'). */
export async function searchCafcOpinions(
  client: CafcClient,
  input: CafcSearchInput,
) {
  const { offset, limit } = pageArgs(
    input.offset,
    input.limit,
    input.next_cursor,
  );
  const query = input.query?.trim() || undefined;
  const result = await client.search({
    ...(query ? { query } : {}),
    maxResults: limit,
    offset,
  });
  const rows = result.data;
  const end = offset + rows.length;
  const more = end < result.total;
  const hits = input.patent_only
    ? rows.filter((o) => classifyPatentCase(o.case_name).isPatentCase)
    : rows;
  const label = query ? `\`${query}\`` : "(recent opinions)";
  const scope = input.patent_only
    ? " (patent only; heuristic case-name filter)"
    : "";
  return {
    ...listEnvelope(
      `CAFC opinions — ${label}${scope}: ${hits.length} hits. Inspected ${rows.length} of ${result.total} source rows at offset ${offset}.`,
      hits.map((o) => (input.full ? { ...o } : stubOpinion(o))),
      result.provenance,
    ),
    more_available: more,
    next_cursor: more ? encodeCursor(end, limit) : null,
  };
}

export interface CafcPatentSearchInput {
  date_from?: string | null | undefined;
  date_to?: string | null | undefined;
  max_results: number;
  full: boolean;
  offset: number;
  next_cursor?: string | null | undefined;
}
export async function searchCafcPatentOpinions(
  client: CafcClient,
  input: CafcPatentSearchInput,
) {
  const { offset, limit } = pageArgs(
    input.offset,
    input.max_results,
    input.next_cursor,
  );
  const result = await client.searchPatentOpinions({
    ...(input.date_from ? { dateFrom: input.date_from } : {}),
    ...(input.date_to ? { dateTo: input.date_to } : {}),
    maxResults: limit,
    offset,
  });
  const end = offset + result.data.length;
  const more = end < result.total;
  const range =
    [
      input.date_from ? `from ${input.date_from}` : "",
      input.date_to ? `to ${input.date_to}` : "",
    ]
      .filter(Boolean)
      .join(" ") || "(no date range)";
  return {
    ...listEnvelope(
      `CAFC patent opinions — ${range}: ${result.data.length} of ${result.total} hits at offset ${offset}. PTO/DCT/ITC/CFC origin scope; may include non-patent cases.`,
      result.data.map((o) => (input.full ? { ...o } : stubOpinion(o))),
      result.provenance,
    ),
    more_available: more,
    next_cursor: more ? encodeCursor(end, limit) : null,
  };
}

/**
 * Download one opinion PDF. `reference` is an appeal number (two- or
 * four-digit year) or an official PDF URL; an appeal with several documents
 * needs the URL of the one wanted.
 */
export async function downloadCafcPdf(
  client: CafcClient,
  reference: string,
  documentUrl?: string | null,
) {
  let url = documentUrl ?? (officialPdfUrl(reference) ? reference : undefined);
  if (url === undefined) {
    const appeal = normalizeAppealNumber(reference);
    const found = await client.findAppeal(appeal);
    const urls = [...new Set(found.data.map((o) => o.pdf_url))].filter(Boolean);
    if (!urls.length)
      throw new ApiError(
        `No Federal Circuit opinion or order found for appeal ${appeal}.`,
        404,
        "NOT_FOUND",
      );
    if (urls.length > 1)
      throw new ApiError(
        `Appeal ${appeal} has ${urls.length} documents; pass the PDF URL of the one you want: ${urls.join(", ")}`,
        400,
        "AMBIGUOUS",
      );
    url = urls[0] as string;
  }
  const pdf = await client.downloadPdf(url);
  return downloadResult(pdf.data, pdf.filename, "application/pdf", {
    ...pdf.provenance,
    source_name: CAFC_SOURCE,
  });
}

const fullDescription = (record: string) =>
  `When False (the default), each hit is a lean stub: appeal number, short case name, release date, origin, document type, precedential status, patent classification, PDF URL. When True, each hit carries the full ${record}.`;

/** Input of search_cafc_patent_opinions, shared with the curated facade. */
export const cafcPatentSearchSchema = z.object({
  date_from: z
    .string()
    .nullable()
    .default(null)
    .describe("Start date (YYYY-MM-DD) to filter opinions"),
  date_to: z
    .string()
    .nullable()
    .default(null)
    .describe("End date (YYYY-MM-DD) to filter opinions"),
  max_results: z
    .number()
    .int()
    .min(1)
    .max(100)
    .default(25)
    .describe("Maximum source rows per page (1-100)"),
  full: z.boolean().default(false).describe(fullDescription("opinion record")),
  offset: z
    .number()
    .int()
    .nonnegative()
    .default(0)
    .describe("Offset into the upstream filtered index"),
  next_cursor: z
    .string()
    .max(2048)
    .nullable()
    .default(null)
    .describe(
      "Continuation from the previous page; overrides offset and page size",
    ),
});

export function registerCafcTools(
  server: FastMCP,
  client: CafcClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_cafc_opinions",
      description:
        "Search U.S. Court of Appeals for the Federal Circuit opinions and orders by free text across the court's index (appeal number, case name and other columns). patent_only=true applies a heuristic case-name classifier to each page; it can miss patent cases and pages may have zero hits while more_available is true. Continue with next_cursor and the same filters. Use download_cafc_pdf to fetch an opinion.",
      input: z.object({
        query: z
          .string()
          .max(500)
          .nullable()
          .default(null)
          .describe("Search text to filter CAFC opinions"),
        patent_only: z
          .boolean()
          .default(false)
          .describe(
            "Apply a heuristic case-name patent classifier to each source page",
          ),
        limit: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(25)
          .describe("Maximum source rows per page (1-100)"),
        full: z
          .boolean()
          .default(false)
          .describe(
            fullDescription(
              "opinion record (file_path, patent_confidence, patent_keywords)",
            ),
          ),
        offset: z
          .number()
          .int()
          .nonnegative()
          .default(0)
          .describe("Offset into the upstream filtered index"),
        next_cursor: z
          .string()
          .max(2048)
          .nullable()
          .default(null)
          .describe(
            "Continuation from the previous page; overrides offset and page size",
          ),
      }),
    },
    (input) => searchCafcOpinions(client, input),
  );

  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_cafc_patent_opinions",
      description:
        "Search U.S. Court of Appeals for the Federal Circuit opinions from patent-relevant origins (PTO, DCT, ITC, CFC), newest first, optionally within a date range. date_to requires date_from and reversed bounds are rejected. These origins also carry non-patent cases. Continue with next_cursor and the same dates. Use download_cafc_pdf to fetch an opinion.",
      input: cafcPatentSearchSchema,
    },
    (input) => searchCafcPatentOpinions(client, input),
  );

  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_cafc_pdf",
      description:
        "Download a U.S. Court of Appeals for the Federal Circuit opinion or order PDF by appeal number ('24-1945' or '2024-1945'). When an appeal has several documents, pass document_url from a search hit. Returns a download link or file path, not bytes.",
      input: z.object({
        appeal_number: z
          .string()
          .min(1)
          .max(40)
          .describe("CAFC appeal number (e.g. '2023-1234')"),
        document_url: z
          .string()
          .max(500)
          .nullable()
          .default(null)
          .describe("Exact official PDF URL from discovery"),
      }),
    },
    ({ appeal_number, document_url }) =>
      downloadCafcPdf(client, appeal_number, document_url),
  );
}

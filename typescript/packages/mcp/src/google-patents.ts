import { createHash } from "node:crypto";
import {
  ApiError,
  type GooglePatent,
  type GooglePatentsClient,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listEnvelopeSchema,
  listToolOptions,
} from "./shared.js";

const VIEWS = {
  /** Identity, dates, status, parties and classification; no long text. */
  summary: [
    "patent_number",
    "title",
    "abstract",
    "status",
    "legal_status_category",
    "kind_code",
    "application_number",
    "family_id",
    "current_assignee",
    "original_assignee",
    "inventors",
    "priority_date",
    "filing_date",
    "publication_date",
    "grant_date",
    "expiration_date",
    "expiration_estimated",
    "source_language",
    "cpc_classifications",
    "pdf_url",
  ],
  claims: [
    "patent_number",
    "claims",
    "structured_limitations",
    "original_limitations",
  ],
  description: ["patent_number", "description_markdown"],
  citations: [
    "patent_number",
    "cited_patents",
    "citing_patents",
    "cited_patents_family",
    "citing_patents_family",
    "non_patent_literature",
    "detailed_non_patent_literature",
  ],
  family: [
    "patent_number",
    "family_id",
    "family_members",
    "country_filings",
    "priority_applications",
    "child_applications",
    "apps_claiming_priority",
    "legal_events",
  ],
  figures: ["patent_number", "figures"],
} as const;
type View = keyof typeof VIEWS | "full";

function project(patent: GooglePatent, view: View): Record<string, unknown> {
  if (view === "full") {
    const { description_html: _html, ...rest } = patent as GooglePatent & {
      description_html?: unknown;
    };
    return rest;
  }
  const record = patent as unknown as Record<string, unknown>;
  return Object.fromEntries(
    VIEWS[view].map((key) => [key, record[key] ?? null]),
  );
}

const cursorSchema = z.object({
  page: z.number().int().min(1),
  query: z.string(),
});
const fingerprint = (input: object) =>
  createHash("sha256").update(JSON.stringify(input)).digest("hex");

export function registerGooglePatentsTools(
  server: FastMCP,
  client: GooglePatentsClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_google_patents",
      description:
        "Search worldwide patents and (optionally) scholarly literature through Google Patents by keywords, CPC, inventor, assignee, country, language and date range. Unofficial source scraped from patents.google.com and throttled to about one request every four seconds; prefer search_epo or office tools when exact provenance matters. Follow up with get_google_patent.",
      input: z.object({
        keywords: z.array(z.string().min(1).max(500)).max(10).optional(),
        cpc_codes: z.array(z.string().min(1).max(40)).max(10).optional(),
        inventors: z.array(z.string().min(1).max(200)).max(10).optional(),
        assignees: z.array(z.string().min(1).max(200)).max(10).optional(),
        countries: z
          .array(z.string().regex(/^[A-Za-z]{2}$/))
          .max(20)
          .optional(),
        languages: z
          .array(z.string().regex(/^[A-Za-z]{2}$/))
          .max(10)
          .optional(),
        date_type: z
          .enum(["priority", "filing", "publication"])
          .default("priority"),
        after: z.iso.date().optional(),
        before: z.iso.date().optional(),
        status: z.enum(["GRANT", "APPLICATION"]).optional(),
        patent_type: z.enum(["PATENT", "DESIGN"]).optional(),
        include_npl: z.boolean().default(false),
        sort: z.enum(["new", "old"]).optional(),
        dedupe: z.enum(["language", "family"]).optional(),
        limit: z.number().int().min(10).max(100).default(10),
        cursor: z.string().max(2048).optional(),
      }),
    },
    async (input) => {
      const { cursor, ...query } = input;
      let page = 1;
      if (cursor) {
        let parsed: z.infer<typeof cursorSchema>;
        try {
          parsed = cursorSchema.parse(
            JSON.parse(Buffer.from(cursor, "base64").toString("utf8")),
          );
        } catch {
          throw new Error("Invalid pagination cursor.");
        }
        if (parsed.query !== fingerprint(query))
          throw new Error("Cursor belongs to a different query.");
        page = parsed.page;
      }
      const response = await client.search({
        ...(query.keywords ? { keywords: query.keywords } : {}),
        ...(query.cpc_codes ? { cpcCodes: query.cpc_codes } : {}),
        ...(query.inventors ? { inventors: query.inventors } : {}),
        ...(query.assignees ? { assignees: query.assignees } : {}),
        ...(query.countries ? { countries: query.countries } : {}),
        ...(query.languages ? { languages: query.languages } : {}),
        dateType: query.date_type,
        ...(query.after ? { after: query.after } : {}),
        ...(query.before ? { before: query.before } : {}),
        ...(query.status ? { status: query.status } : {}),
        ...(query.patent_type ? { patentType: query.patent_type } : {}),
        includeNpl: query.include_npl,
        ...(query.sort ? { sort: query.sort } : {}),
        ...(query.dedupe ? { dups: query.dedupe } : {}),
        page,
        pageSize: query.limit,
      });
      const data = response.data;
      return {
        ...listEnvelope(
          `Google Patents: ${data.results.length} results on page ${data.page} of ${data.total_pages}; about ${data.total_results} matches.`,
          data.results.map((result) => ({ ...result })),
          response.provenance,
        ),
        more_available: data.has_more,
        next_cursor: data.has_more
          ? Buffer.from(
              JSON.stringify({
                page: data.page + 1,
                query: fingerprint(query),
              }),
            ).toString("base64")
          : null,
      };
    },
  );

  server.tool(
    {
      ...listToolOptions(auth),
      output: listEnvelopeSchema.extend({
        not_found: z.array(z.string()).optional(),
      }),
      name: "get_google_patent",
      description:
        "Get a publication from Google Patents by number, such as US7654321B2, EP3456789A1 or JP2019000001A; non-English pages include Google's machine translation and the original text. view: summary (default), claims (with dependencies and structured limitations), description (Markdown), citations, family (members, priorities, children, legal events), figures, or full. Up to 5 numbers, fetched one at a time because Google throttles. expiration_date may be a priority + 20 years estimate (expiration_estimated); verify term with USPTO data.",
      input: z.object({
        patent_numbers: z.union([
          z.string().min(1).max(40),
          z.array(z.string().min(1).max(40)).min(1).max(5),
        ]),
        view: z
          .enum([
            "summary",
            "claims",
            "description",
            "citations",
            "family",
            "figures",
            "full",
          ])
          .default("summary"),
      }),
    },
    async ({ patent_numbers, view }) => {
      const numbers =
        typeof patent_numbers === "string" ? [patent_numbers] : patent_numbers;
      const items: Record<string, unknown>[] = [];
      const notFound: string[] = [];
      let provenance:
        | Awaited<ReturnType<GooglePatentsClient["getPatent"]>>["provenance"]
        | undefined;
      for (const number of numbers) {
        try {
          const result = await client.getPatent(number);
          items.push(project(result.data, view));
          provenance ??= result.provenance;
        } catch (error) {
          if (
            typeof patent_numbers !== "string" &&
            error instanceof ApiError &&
            error.code === "NOT_FOUND"
          )
            notFound.push(number);
          else throw error;
        }
      }
      return {
        ...listEnvelope(
          `${items.length} Google Patents ${view} records.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`,
          items,
          provenance ?? {
            source_url: "https://patents.google.com/",
            source_name: "Google Patents",
            retrieved_at: new Date().toISOString(),
            cache_hit: false,
          },
        ),
        not_found: notFound,
      };
    },
  );

  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_google_patent_pdf",
      description:
        "Download a publication's PDF from Google Patents' image store. Returns a download link or file path, not bytes.",
      input: z.object({ patent_number: z.string().min(1).max(40) }),
    },
    async ({ patent_number }) => {
      const result = await client.downloadPdf(patent_number);
      return downloadResult(
        result.data,
        `${result.patentNumber}.pdf`,
        "application/pdf",
        result.provenance,
      );
    },
  );
}

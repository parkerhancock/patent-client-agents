import { createHash } from "node:crypto";
import {
  OFFICE_ACTION_ANALYTICS_DATASETS,
  type OfficeActionAnalyticsClient,
  OfficeActionResponseSchema,
  OfficeActionSearchOptionsSchema,
  type OfficeActionsClient,
  STUB_OFFICE_ACTION_FIELDS,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listToolOptions,
} from "./shared.js";

const cursorInput = z.string().max(2048).optional();
function queryKey(input: Record<string, unknown>, family: string) {
  const { cursor, offset, start, ...query } = input;
  return createHash("sha256")
    .update(JSON.stringify({ family, query }))
    .digest("hex");
}
function cursorOffset(
  input: Record<string, unknown> & { cursor?: string | undefined },
  offset: number,
  family: string,
) {
  if (!input.cursor) return offset;
  if (offset !== 0) throw new Error("Use cursor or offset/start, not both.");
  let page: { offset: number; key: string };
  try {
    page = z
      .object({ offset: z.number().int().nonnegative(), key: z.string() })
      .parse(JSON.parse(Buffer.from(input.cursor, "base64").toString("utf8")));
  } catch {
    throw new Error("Invalid pagination cursor.");
  }
  if (page.key !== queryKey(input, family))
    throw new Error("Cursor belongs to a different query.");
  return page.offset;
}
function cursorEnvelope(
  result: ReturnType<typeof listEnvelope>,
  input: Record<string, unknown>,
  offset: number,
  family: string,
) {
  return {
    ...result,
    next_cursor: result.more_available
      ? Buffer.from(
          JSON.stringify({
            offset: offset + result.items.length,
            key: queryKey(input, family),
          }),
        ).toString("base64")
      : null,
  };
}
function preview(value: unknown, depth = 0): unknown {
  if (typeof value === "string") return value.slice(0, 2000);
  if (value === null || typeof value !== "object") return value;
  if (depth >= 3) return "[nested content omitted]";
  if (Array.isArray(value))
    return value.slice(0, 20).map((item) => preview(item, depth + 1));
  return Object.fromEntries(
    Object.entries(value)
      .slice(0, 30)
      .map(([key, item]) => [key, preview(item, depth + 1)]),
  );
}
function boundedRecord(record: Record<string, unknown>, full: boolean) {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(record)) {
    if (
      !full &&
      !STUB_OFFICE_ACTION_FIELDS.includes(
        key as (typeof STUB_OFFICE_ACTION_FIELDS)[number],
      )
    )
      continue;
    result[key] =
      key === "officeActionText" && typeof value === "string"
        ? value.slice(0, 500)
        : preview(value);
  }
  return result;
}
const analyticsLean = new Set([
  "id",
  "patentApplicationNumber",
  "patent_application_number",
  "submissionDate",
  "submission_date",
  "referenceIdentifier",
  "reference_identifier",
  "legalSectionCode",
  "legal_section_code",
  "groupArtUnitNumber",
  "group_art_unit_number",
  "publicationNumber",
  "publication_number",
  "hasRej101",
  "hasRej102",
  "hasRej103",
  "hasRej112",
]);
function analyticsRecord(record: Record<string, unknown>, full: boolean) {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(record)) {
    if (!full && !analyticsLean.has(key)) continue;
    if (/body.?text|sections|office.?action.?text/i.test(key)) continue;
    result[key] = preview(value);
  }
  return result;
}
export function registerOfficeActionTools(
  server: FastMCP,
  clients: {
    officeActions: OfficeActionsClient;
    analytics: OfficeActionAnalyticsClient;
  },
  auth?: AuthCheck,
) {
  const searchInput = OfficeActionSearchOptionsSchema.omit({
    method: true,
  }).extend({
    limit: z.number().int().min(1).max(100).default(25),
    cursor: cursorInput,
  });
  const downloadInput = searchInput
    .omit({ facets: true, cursor: true })
    .extend({ format: z.enum(["csv", "json"]).default("csv") });
  server.tool(
    {
      ...listToolOptions(auth),
      output: listToolOptions(auth).output.extend({
        facets: OfficeActionResponseSchema.shape.facets,
      }),
      name: "search_office_actions",
      description:
        "Search US patent office actions by query, exact filters, art unit/date ranges, and facets. Text is a highlighted excerpt. Use download_office_action_text for full text. Use next_cursor for another page, or advance offset.",
      input: searchInput,
      inputSchema: z.toJSONSchema(searchInput, { io: "input" }),
    },
    async (input) => {
      const offset = cursorOffset(input, input.offset, "office-actions");
      const { cursor, ...options } = input;
      const result = await clients.officeActions.search({ ...options, offset });
      return {
        ...cursorEnvelope(
          listEnvelope(
            `${result.officeActionDataBag.length} office actions returned${result.count === undefined ? "" : `; ${result.count} matching`}.`,
            result.officeActionDataBag.map((r) => boundedRecord(r, input.full)),
            result.provenance,
            {
              ...(result.count === undefined ? {} : { count: result.count }),
              offset,
              limit: input.limit,
            },
          ),
          input,
          offset,
          "office-actions",
        ),
        ...(input.facets && result.facets ? { facets: result.facets } : {}),
      };
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_office_action",
      description:
        "Retrieve a US patent office action by record identifier. Text is limited to a 500 character excerpt; use download_office_action_text for the complete document.",
      input: z.object({
        record_identifier: z.string().min(1),
        full: z.boolean().default(false),
      }),
    },
    async (input) => {
      const { provenance, ...result } = await clients.officeActions.get(
        input.record_identifier,
      );
      return detailEnvelope(
        "Office action record.",
        {
          ...result,
          officeActionDataBag: result.officeActionDataBag.map((r) =>
            boundedRecord(r, input.full),
          ),
        },
        provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_office_actions",
      description:
        "Download matching US office actions as CSV or JSON. Returns download metadata; facets are unavailable. Advance offset for subsequent pages.",
      input: downloadInput,
      inputSchema: z.toJSONSchema(downloadInput, { io: "input" }),
    },
    async (input) => {
      const result = await clients.officeActions.download(input);
      return downloadResult(
        result.data,
        `office-actions.${input.format}`,
        input.format === "json" ? "application/json" : "text/csv",
        result.provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_office_action_text",
      description:
        "Download complete plain text of a US patent office action by record identifier. Returns download metadata without inserting full text in the response.",
      input: z.object({ record_identifier: z.string().min(1) }),
    },
    async (input) => {
      const result = await clients.officeActions.downloadText(
        input.record_identifier,
      );
      return downloadResult(
        new TextEncoder().encode(result.data),
        "office-action.txt",
        "text/plain",
        result.provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_office_action_analytics",
      description:
        "Download raw legacy USPTO rejection, citation, office action text, or enriched citation records as JSON. Includes full document text and sections outside model context. Use dataset and criteria from search_office_action_analytics; advance start for another bounded page.",
      input: z.object({
        dataset: z.enum(OFFICE_ACTION_ANALYTICS_DATASETS),
        criteria: z.string().min(1),
        start: z.number().int().nonnegative().default(0),
        rows: z.number().int().min(1).max(100).default(25),
      }),
    },
    async (input) => {
      const result = await clients.analytics.search(
        input.dataset,
        input.criteria,
        { start: input.start, rows: input.rows },
      );
      const { provenance, ...records } = result;
      return downloadResult(
        new TextEncoder().encode(
          JSON.stringify({
            dataset: input.dataset,
            criteria: input.criteria,
            ...records,
          }),
        ),
        `office-action-${input.dataset}.json`,
        "application/json",
        provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_office_action_analytics_fields",
      description:
        "Discover searchable fields and dataset information for legacy USPTO office action analytics. Use these field names in search_office_action_analytics criteria.",
      input: z.object({ dataset: z.enum(OFFICE_ACTION_ANALYTICS_DATASETS) }),
    },
    async (input) => {
      const result = await clients.analytics.getFields(input.dataset);
      return detailEnvelope(
        "Office action analytics searchable fields.",
        result.data,
        result.provenance,
      );
    },
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_office_action_analytics",
      description:
        "Search legacy USPTO rejection, citation, text metadata, or enriched citation datasets using Solr criteria. Document text and sections are omitted; use the library for raw records. Use next_cursor for another page, or advance start.",
      input: z.object({
        dataset: z.enum(OFFICE_ACTION_ANALYTICS_DATASETS),
        criteria: z.string().min(1),
        cursor: cursorInput,
        start: z.number().int().nonnegative().default(0),
        rows: z.number().int().min(1).max(100).default(25),
        full: z.boolean().default(false),
      }),
    },
    async (input) => {
      const start = cursorOffset(input, input.start, "office-action-analytics");
      const { cursor, ...options } = input;
      const result = await clients.analytics.search(
        input.dataset,
        input.criteria,
        { ...options, start },
      );
      return cursorEnvelope(
        listEnvelope(
          `${result.results.length} analytical records returned; ${result.numFound} matching.`,
          result.results.map((r) => analyticsRecord(r, input.full)),
          result.provenance,
          { count: result.numFound, offset: start, limit: input.rows },
        ),
        input,
        start,
        "office-action-analytics",
      );
    },
  );
}

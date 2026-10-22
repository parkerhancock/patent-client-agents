import type {
  Provenance,
  TrademarkAssignmentRecord,
  TrademarkSearchResult,
  TsdrClient,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  asList,
  type FacadeClients,
  facadeToolOptions,
  identifierInput,
  listEnvelope,
  notConfigured,
} from "./shared.js";

const TMSEARCH = "https://tmsearch.uspto.gov";
const TSDR = "https://tsdrapi.uspto.gov";
const ASSIGNMENTS = "https://assignmentcenter.uspto.gov";
const provenance = (
  base: string,
  path: string,
  source: string,
): Provenance => ({
  source_url: `${base}${path}`,
  source_name: source,
  retrieved_at: new Date().toISOString(),
  cache_hit: false,
});
const isoDate = (value: unknown) =>
  typeof value === "string" && value ? value.slice(0, 10) : null;

/** Lean trademark search hit, as the Python `_stub_trademark`. */
function stubTrademark(record: TrademarkSearchResult) {
  return {
    serial_number: record.serial_number,
    registration_number: record.registration_number,
    wordmark: record.wordmark,
    owner_name: record.owner_name ?? null,
    filing_date: isoDate(record.filed_date),
    registration_date: isoDate(record.registration_date),
    status: record.status_live ? "live" : "dead",
  };
}
/** 8 digits = serial; 6-7 = registration. Anything else is rejected, not guessed. */
function classify(value: string): "serial" | "registration" {
  const raw = value.trim();
  if (!/^\d+$/.test(raw))
    throw new Error(
      `trademark identifier must be all digits; got '${value}'. Accepts 8-digit serial numbers (e.g. '97123456') or 7-digit registration numbers (e.g. '1234567').`,
    );
  if (raw.length === 8) return "serial";
  if (raw.length === 6 || raw.length === 7) return "registration";
  throw new Error(
    `trademark identifier '${value}' has ${raw.length} digits; expected 8 (serial) or 6-7 (registration).`,
  );
}
function requireTsdr(clients: FacadeClients): TsdrClient {
  return clients.tsdr ?? notConfigured("TSDR", "USPTO_TSDR_API_KEY");
}
/** Lean assignment recordation, as the Python `_stub_trademark_assignment`. */
function stubAssignment(record: TrademarkAssignmentRecord) {
  const property = record.properties[0];
  return {
    reel_frame: record.reelFrame,
    assignor: record.assignors[0]?.assignorName ?? null,
    assignee: record.assignees[0] ?? null,
    assignor_execution_date: record.assignorExecutionDate ?? null,
    number_of_properties: record.noOfProperties,
    serial_number: property?.serialNumber ?? null,
    registration_number: property?.registrationNumber ?? null,
    mark: property?.mark ?? null,
  };
}
const notFoundStatus = (error: unknown) =>
  error instanceof Error &&
  "status" in error &&
  (error as { status?: number }).status === 404;

/**
 * Fetch each id four at a time. A missing single id fails; missing list
 * members are reported in not_found.
 */
async function each<T>(
  identifier: string | string[],
  fetch: (value: string) => Promise<T | null>,
) {
  const values = asList(identifier).map((value) => value.trim());
  const items: T[] = [];
  const notFound: string[] = [];
  for (let start = 0; start < values.length; start += 4) {
    const group = await Promise.all(
      values.slice(start, start + 4).map(async (value) => {
        try {
          return { value, item: await fetch(value) };
        } catch (error) {
          if (typeof identifier !== "string" && notFoundStatus(error))
            return { value, item: null };
          throw error;
        }
      }),
    );
    for (const { value, item } of group)
      if (item === null) notFound.push(value);
      else items.push(item);
  }
  return { values, items, notFound };
}
const batchSummary = (
  found: number,
  total: number,
  noun: string,
  missing: string[],
) =>
  `${found} of ${total} ${noun} retrieved.${missing.length ? ` Not found: ${missing.join(", ")}.` : ""}`;

export function registerTrademarksFacade(
  server: FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
): void {
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_trademarks",
      description: `Search USPTO trademarks by wordmark, owner, or goods/services (Trademark Search).

Returns lean stubs by default. Use \`get_trademark\` for a full record or
current status by serial/registration number. For assignment recordations
(reel/frame, assignor/assignee chains) use \`search_trademark_assignments\`.

Related tools: get_trademark, search_trademark_assignments.`,
      input: z.object({
        query: z
          .string()
          .min(1)
          .max(500)
          .describe(
            "Search query — a wordmark, owner name, or goods/services description.",
          ),
        search_by: z
          .enum(["wordmark", "owner", "goods_services"])
          .default("wordmark")
          .describe(
            "Which field to search. 'wordmark' (default) — trademark text; 'owner' — registrant name; 'goods_services' — goods/services description.",
          ),
        paginate_all: z
          .boolean()
          .default(false)
          .describe(
            "When true, auto-paginates through all matching results (wordmark/owner only). Ignored for goods_services.",
          ),
        max_results: z
          .number()
          .int()
          .min(1)
          .max(10_000)
          .default(500)
          .describe("Cap on total results when paginate_all=True."),
        full: z
          .boolean()
          .default(false)
          .describe(
            "False (default) = lean stub per hit (serial, wordmark, owner, status, dates, registration number). True = full Trademark Search record per hit (large; prefer get_trademark for one).",
          ),
      }),
    },
    async (input) => {
      const search = clients.trademarkSearch;
      let results: TrademarkSearchResult[];
      let source: Provenance | undefined;
      // Python rejects paginate_all for goods/services despite the description.
      if (input.paginate_all && input.search_by === "goods_services")
        throw new Error(
          "paginate_all is not supported for search_by='goods_services'",
        );
      if (input.paginate_all)
        results = await search.searchAll({
          ...(input.search_by === "owner"
            ? { owner: input.query }
            : { wordmark: input.query }),
          maxResults: input.max_results,
        });
      else {
        const page =
          input.search_by === "owner"
            ? await search.searchOwner(input.query)
            : input.search_by === "goods_services"
              ? await search.search({ goodsServices: input.query })
              : await search.search({ wordmark: input.query });
        results = page.results;
        source = page.provenance;
      }
      const items = results.map((record) =>
        input.full ? { ...record } : stubTrademark(record),
      );
      return listEnvelope(
        `USPTO trademarks (by ${input.search_by}) — \`${input.query}\`: ${items.length} hits.`,
        items,
        source ??
          provenance(
            TMSEARCH,
            "/prod-stage-v1-0-0/tmsearch",
            "USPTO Trademark Search",
          ),
      );
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "get_trademark",
      description: `Fetch one or more USPTO trademarks by serial or registration number.

Always returns a \`ListEnvelope\` (stable shape for one id or many). For
the full register record use view='record' (Trademark Search); for current
status, prosecution documents, or last-update timestamps use the TSDR views
(status/documents/last_update). Find identifiers with \`search_trademarks\`.

Related tools: search_trademarks, search_trademark_assignments.`,
      input: z.object({
        identifier: identifierInput.describe(
          "USPTO trademark serial number (8 digits, e.g. '97123456') or registration number (6-7 digits, e.g. '1234567'). Pass a list for portfolio workflows; the response shape stays a ListEnvelope. view='documents' accepts a single serial number only.",
        ),
        view: z
          .enum(["record", "status", "documents", "last_update"])
          .default("record")
          .describe(
            "Which facet to fetch. 'record' (default) = full Trademark Search register record (wordmark, owner, goods/services, dates). 'status' = current TSDR status. 'documents' = TSDR prosecution documents (single serial). 'last_update' = TSDR last-modified timestamp.",
          ),
      }),
    },
    async ({ identifier, view }) => {
      if (view === "documents") {
        if (typeof identifier !== "string")
          throw new Error(
            "get_trademark(view='documents') accepts a single serial number only, not a list.",
          );
        const result = await requireTsdr(clients).getDocuments(identifier);
        return listEnvelope(
          `TSDR prosecution documents for USPTO trademark ${identifier} — ${result.documents.length} documents.`,
          result.documents.map((document) => ({ ...document })),
          result.provenance,
        );
      }
      if (view === "status" || view === "last_update") {
        const tsdr = requireTsdr(clients);
        let first: Provenance | undefined;
        const batch = await each(identifier, async (value) => {
          const result =
            view === "status"
              ? await tsdr.getStatus(value)
              : await tsdr.getLastUpdate(value);
          first ??= result.provenance;
          return { ...result.data } as Record<string, unknown>;
        });
        const noun =
          view === "status"
            ? "TSDR trademark statuses"
            : "TSDR trademark last-update records";
        return {
          ...listEnvelope(
            batch.values.length === 1
              ? `TSDR ${view === "status" ? "status" : "last-update"} for USPTO trademark ${batch.values[0]}.`
              : batchSummary(
                  batch.items.length,
                  batch.values.length,
                  noun,
                  batch.notFound,
                ),
            batch.items,
            first ?? provenance(TSDR, "/ts/cd/casestatus", "USPTO TSDR"),
          ),
          not_found: batch.notFound,
        };
      }
      // view === "record": validate every id before any request.
      for (const value of asList(identifier)) classify(value);
      let first: Provenance | undefined;
      const batch = await each(identifier, async (value) => {
        const result =
          classify(value) === "serial"
            ? await clients.trademarkSearch.getBySerial(value)
            : await clients.trademarkSearch.getByRegistration(value);
        first ??= result.provenance;
        return result.record ? { ...result.record } : null;
      });
      const record = batch.items[0] as TrademarkSearchResult | undefined;
      const owner = Array.isArray(record?.owner_name)
        ? (record.owner_name as string[]).join("; ")
        : "";
      const summary =
        batch.values.length === 1
          ? record
            ? `**US trademark ${record.serial_number}** — ${record.wordmark ?? "(no mark)"} (owner: ${owner || "(no owner)"})\n${record.registration_number ? `Registration ${record.registration_number}. ` : ""}Status: ${record.status_live ? "live" : "dead"}.`
            : `USPTO trademark ${batch.values[0]} — not found.`
          : batchSummary(
              batch.items.length,
              batch.values.length,
              "USPTO trademarks",
              batch.notFound,
            );
      return {
        ...listEnvelope(
          summary,
          batch.items,
          first ??
            provenance(
              TMSEARCH,
              "/prod-stage-v1-0-0/tmsearch",
              "USPTO Trademark Search",
            ),
        ),
        not_found: batch.notFound,
      };
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_trademark_assignments",
      description: `Search USPTO trademark assignment recordations by assignee, assignor, or mark identifier.

Returns recordations with reel/frame, assignors, assignees, and
affected trademark properties. Lean by default (§5.5); use
\`full=True\` for the upstream record per hit. No auth required.
For the underlying register data, use \`get_trademark\` (full record)
or get_trademark(view='status') (current TSDR status).

Related tools: get_trademark, search_trademarks.`,
      input: z.object({
        query: z
          .string()
          .min(1)
          .max(500)
          .describe(
            "Value to search for (e.g. 'Apple Inc', '97123456', '9006/0093').",
          ),
        by: z
          .string()
          .describe(
            "What kind of value `query` is. One of: assignee, assignor, serial_number, registration_number, reel_frame.",
          ),
        limit: z
          .number()
          .int()
          .min(1)
          .max(1000)
          .default(100)
          .describe("Maximum records to return per request (max 1000)."),
        start_row: z
          .number()
          .int()
          .min(1)
          .default(1)
          .describe("1-based starting row for pagination."),
        full: z
          .boolean()
          .default(false)
          .describe(
            "When False (the default), each hit is a lean stub: reel/frame, first assignor, first assignee, execution date, number of properties, plus the lead property's serial/registration number and mark text. When True, every hit is the full Trademark Assignment Center record (all properties, all assignors, correspondent, domestic representative, etc.).",
          ),
      }),
    },
    async (input) => {
      const axis = input.by.trim().toLowerCase();
      const client = clients.trademarkAssignments;
      const options = { startRow: input.start_row, limit: input.limit };
      const response =
        axis === "assignee"
          ? await client.searchByAssignee(input.query, options)
          : axis === "assignor"
            ? await client.searchByAssignor(input.query, options)
            : axis === "serial_number"
              ? await client.searchBySerial(input.query, { limit: input.limit })
              : axis === "registration_number"
                ? await client.searchByRegistration(input.query, {
                    limit: input.limit,
                  })
                : axis === "reel_frame"
                  ? await client.searchByReelFrame(input.query)
                  : null;
      if (!response)
        throw new Error(
          `\`by\` must be one of assignee, assignor, serial_number, registration_number, reel_frame; got '${input.by}'`,
        );
      const items = response.data.map((record) =>
        input.full ? { ...record } : stubAssignment(record),
      );
      return listEnvelope(
        `USPTO trademark assignments (by ${axis}) — \`${input.query}\`: ${items.length} hit${items.length === 1 ? "" : "s"}.`,
        items,
        response.provenance ??
          provenance(
            ASSIGNMENTS,
            "/ipas/search/api/v3/public/search/trademark",
            "USPTO Trademark Assignment Center",
          ),
      );
    },
  );
}

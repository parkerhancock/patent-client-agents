import {
  COPYRIGHT_ORIGIN,
  COPYRIGHT_SEARCH_PATH,
  COPYRIGHT_SOURCE,
  type CopyrightClient,
  CopyrightFieldSchema,
  type CopyrightRecord,
  type Provenance,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  listToolOptions,
} from "./shared.js";

/** Fields of the Python CopyrightRecord, the shape of a full search hit. */
const RECORD_FIELDS = [
  "public_records_id",
  "title_of_work",
  "registration_number",
  "copyright_number_for_display",
  "type_of_record",
  "registration_status",
  "registration_class",
  "claimant",
  "claimants",
  "publisher_name",
  "type_of_work",
  "all_type_of_work",
  "system_of_origin",
  "application_date",
  "first_published_date",
  "fee_date",
  "deposit_received_date",
  "representative_date",
  "link_to_image_url",
  "score",
] as const;
/** Python CopyrightClient.get_record fetches at most this many ids per call. */
const ID_CAP = 50;
const CONCURRENCY = 5;

const first = (values: string[]) => values[0] ?? null;

/** Lean projection of a hit, field for field with Python's _stub_copyright. */
export function stubCopyright(
  record: CopyrightRecord,
): Record<string, unknown> {
  return {
    public_records_id: record.public_records_id,
    title: first(record.title_of_work),
    registration_number:
      record.copyright_number_for_display || first(record.registration_number),
    registration_class: first(record.registration_class),
    type_of_record: record.type_of_record,
    type_of_work: record.type_of_work,
    claimant: first(record.claimant),
    representative_date: record.representative_date || null,
  };
}
function pythonFields(record: CopyrightRecord): Record<string, unknown> {
  return Object.fromEntries(RECORD_FIELDS.map((key) => [key, record[key]]));
}
/** One-line summary of a record, as Python's _summarize_record. */
function summarizeRecord(record: CopyrightRecord): string {
  const id = record.public_records_id || "(no id)";
  const title = first(record.title_of_work) ?? "(no title)";
  const reg =
    record.copyright_number_for_display || first(record.registration_number);
  const claimant = first(record.claimant) ?? "(no claimant)";
  const status = record.registration_status || "(unknown status)";
  const kind = record.type_of_record || "record";
  return `**U.S. Copyright ${kind} ${id}** — ${title}\nClaimant: ${claimant}. Status: ${status}${reg ? `; registration ${reg}.` : "."}`;
}
const fallbackProvenance = (): Provenance => ({
  source_url: `${COPYRIGHT_ORIGIN}${COPYRIGHT_SEARCH_PATH}`,
  source_name: COPYRIGHT_SOURCE,
  retrieved_at: new Date().toISOString(),
  cache_hit: false,
});

export interface CopyrightSearchInput {
  query: string;
  field: string;
  page: number;
  page_size: number;
  full: boolean;
}
/** search_copyright; also serves the facade copyright(mode='search'). */
export async function searchCopyright(
  client: CopyrightClient,
  input: CopyrightSearchInput,
) {
  const field = CopyrightFieldSchema.safeParse(input.field);
  if (!field.success)
    throw new Error(
      `Invalid field: '${input.field}'. Must be 'keyword', 'title', or 'name'.`,
    );
  const result = await client.search({
    query: input.query,
    field: field.data,
    page: input.page,
    pageSize: input.page_size,
  });
  const items = result.records.map((record) =>
    input.full ? pythonFields(record) : stubCopyright(record),
  );
  const { hit_count: total, hit_count_capped: capped } = result.metadata;
  const shown = total
    ? `${items.length} of ${capped ? "at least " : ""}${total} hits${capped ? " (the Copyright Office pages through only the first 50000; narrow the query to reach the rest)" : ""}`
    : `${items.length} hits`;
  return {
    ...listEnvelope(
      `U.S. Copyright Office — \`${input.query}\` (by ${field.data}): ${shown}.`,
      items,
      result.provenance,
    ),
    more_available: input.page * input.page_size < total,
  };
}

/** get_copyright_record; also serves the facade copyright(mode='get'). */
export async function getCopyrightRecords(
  client: CopyrightClient,
  publicRecordsId: string | string[],
) {
  const single = typeof publicRecordsId === "string";
  const ids = (single ? [publicRecordsId] : publicRecordsId)
    .map((id) => id.trim())
    .filter(Boolean);
  if (!ids.length)
    throw new Error("Provide at least one Public Records identifier.");
  if (ids.length > ID_CAP)
    throw new Error(
      `Too many Public Records identifiers: ${ids.length} (limit ${ID_CAP} per call). Split the list into batches of ${ID_CAP} or fewer.`,
    );
  const results: Awaited<ReturnType<CopyrightClient["getRecord"]>>[] = [];
  for (let offset = 0; offset < ids.length; offset += CONCURRENCY)
    results.push(
      ...(await Promise.all(
        ids
          .slice(offset, offset + CONCURRENCY)
          .map((id) => client.getRecord(id)),
      )),
    );
  const items = results.flatMap((result) =>
    result.record ? [result.record] : [],
  );
  const notFound = ids.filter((_id, i) => !results[i]?.record);
  const summary =
    ids.length === 1 && items[0]
      ? summarizeRecord(items[0])
      : single
        ? `U.S. Copyright record ${ids[0]} — not found.`
        : `Fetched ${items.length} of ${ids.length} U.S. Copyright records.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      items.map((record) => ({ ...record })),
      results[0]?.provenance ?? fallbackProvenance(),
    ),
    not_found: notFound,
  };
}

const idInput = z.union([
  z.string().min(1).max(200),
  z.array(z.string().min(1).max(200)).min(1).max(ID_CAP),
]);

export function registerCopyrightTools(
  server: FastMCP,
  client: CopyrightClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_copyright",
      description:
        "Search U.S. Copyright Office registrations and recorded documents by keyword. Covers post-1978 registrations, digitized card-catalog records, and recorded documents (transfers, assignments, licenses). Returns lean stubs by default. Pass the public_records_id from any hit to get_copyright_record to fetch the full record. The office pages through only the first 50,000 hits of a query.",
      input: z.object({
        query: z
          .string()
          .min(1)
          .max(500)
          .describe(
            "Search query: a title, a claimant/author name, a registration number (e.g. 'TX 1234567'), or any keyword.",
          ),
        field: CopyrightFieldSchema.default("keyword").describe(
          "Which field to search. 'keyword' (default) — all fields; 'title' — work title only; 'name' — claimant/author only.",
        ),
        page: z
          .number()
          .int()
          .min(1)
          .default(1)
          .describe("Page number (1-based)."),
        page_size: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(10)
          .describe("Results per page (default 10, max 100)."),
        full: z
          .boolean()
          .default(false)
          .describe(
            "When False (the default), each hit is a lean stub: public records id, title, registration number, registration class, type of record, type of work, first claimant, and representative date. When True, each hit carries every title/claimant/date/class list plus the relevance score.",
          ),
      }),
    },
    (input) => searchCopyright(client, input),
  );

  server.tool(
    {
      ...listToolOptions(auth),
      output: listEnvelopeSchema.extend({
        not_found: z.array(z.string()).optional(),
      }),
      name: "get_copyright_record",
      description:
        "Get one or more U.S. Copyright Office records by their Public Records identifier. Accepts a single identifier or a list of up to 50; the response is always a list envelope, with unmatched identifiers in not_found. Returns the full registration or recordation record as the office publishes it (titles, claimants, dates, class, work type, recordation parties and titles, card-catalog image URLs).",
      input: z.object({
        public_records_id: idInput.describe(
          "Public Records identifier — the opaque ID returned by search_copyright in each hit's public_records_id field. NOT a registration number (like 'TX 1234567'); to look up a registration number, call search_copyright with the number as the query. Examples: 'voyager_37022961', 'card_catalog_CC19381945B_390000-391999.1449', or a list of such IDs for portfolio workflows.",
        ),
      }),
    },
    ({ public_records_id }) => getCopyrightRecords(client, public_records_id),
  );
}

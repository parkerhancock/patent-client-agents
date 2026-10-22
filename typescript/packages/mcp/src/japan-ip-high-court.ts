import {
  ApiError,
  findJapanIpHighCourtCase,
  type JapanIpHighCourtCaseStatusFilter,
  type JapanIpHighCourtClient,
  normalizeJapanCaseNumber,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  listToolOptions,
} from "./shared.js";

const ID_CAP = 50;
const invalid = (message: string) =>
  new ApiError(message, 400, "INVALID_INPUT");

function terms(query: string | string[] | null | undefined): string[] {
  if (query === null || query === undefined) return [];
  const values = typeof query === "string" ? [query] : query;
  const out = values
    .filter((value) => value.trim())
    .map((value) => normalizeJapanCaseNumber(value));
  if (!out.length)
    throw invalid("query must contain at least one non-empty term");
  return out;
}

function dateFilter(value: string | null | undefined, field: string) {
  if (value === null || value === undefined) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(value)))
    throw invalid(`${field} must use YYYY-MM-DD format`);
  return value;
}

/** Python's str() of a JSON value, so searches match the same text. */
const pyText = (value: unknown) =>
  value === true ? "True" : value === false ? "False" : String(value);
const searchable = (record: Record<string, unknown>) =>
  normalizeJapanCaseNumber(
    Object.values(record)
      .filter((value) => value !== null && value !== undefined)
      .map(pyText)
      .join(" "),
  );

export interface JapanIpHighCourtSearchInput {
  query?: string | string[] | null | undefined;
  case_status: JapanIpHighCourtCaseStatusFilter;
  date_from?: string | null | undefined;
  date_to?: string | null | undefined;
  limit: number;
}

/** search_japan_ip_high_court_cases: filter the whole workbook locally. */
export async function searchJapanIpHighCourtCases(
  client: JapanIpHighCourtClient,
  input: JapanIpHighCourtSearchInput,
) {
  if (!Number.isInteger(input.limit) || input.limit < 1 || input.limit > 250)
    throw invalid("limit must be between 1 and 250");
  const start = dateFilter(input.date_from, "date_from");
  const end = dateFilter(input.date_to, "date_to");
  if (start && end && start > end)
    throw invalid("date_from must not be after date_to");
  const searchTerms = terms(input.query);
  const caseList = await client.listCases();
  const status = input.case_status;
  const relevant = (record: Record<string, unknown>) =>
    ((record.scheduled_judgment_date ?? record.termination_date) as
      | string
      | null) ?? null;
  let records: Record<string, unknown>[] = caseList.cases
    .filter((item) => status === "all" || item.case_status === status)
    .map((item) => ({ ...item }));
  if (searchTerms.length)
    records = records.filter((record) => {
      const haystack = searchable(record);
      return searchTerms.some((term) => haystack.includes(term));
    });
  if (start)
    records = records.filter((record) => {
      const date = relevant(record);
      return date !== null && date >= start;
    });
  if (end)
    records = records.filter((record) => {
      const date = relevant(record);
      return date !== null && date <= end;
    });
  const compare = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
  if (status === "closed")
    records.sort(
      (a, b) =>
        compare(
          (b.termination_date as string | null) ?? "",
          (a.termination_date as string | null) ?? "",
        ) || compare(b.case_number as string, a.case_number as string),
    );
  else
    records.sort((a, b) => {
      const da = relevant(a);
      const db = relevant(b);
      return (
        Number(!da) - Number(!db) ||
        compare(da ?? "", db ?? "") ||
        compare(a.case_number as string, b.case_number as string)
      );
    });
  const total = records.length;
  const items = records.slice(0, input.limit);
  const asOf = caseList.as_of_date ?? "unknown date";
  return {
    ...listEnvelope(
      `Japan IP High Court ${status} patent and utility-model case list: ${items.length} returned from ${total} match(es), workbook as of ${asOf}. The source does not publish party names and is not a general infringement docket.`,
      items,
      caseList.provenance,
    ),
    more_available: total > items.length,
  };
}

/** get_japan_ip_high_court_case: exact lookups against one workbook download. */
export async function getJapanIpHighCourtCases(
  client: JapanIpHighCourtClient,
  caseNumber: string | string[],
  caseStatus: JapanIpHighCourtCaseStatusFilter = "all",
) {
  const single = typeof caseNumber === "string";
  const values = (single ? [caseNumber] : caseNumber)
    .map((value) => value.trim())
    .filter(Boolean);
  if (!values.length) throw invalid("Provide at least one case number.");
  if (values.length > ID_CAP)
    throw invalid(
      `Too many case numbers: ${values.length} (limit ${ID_CAP} per call). Split the list into batches of ${ID_CAP} or fewer.`,
    );
  const caseList = await client.listCases();
  const items: Record<string, unknown>[] = [];
  const notFound: string[] = [];
  for (const value of values) {
    try {
      items.push({
        ...findJapanIpHighCourtCase(caseList, value, caseStatus),
      });
    } catch (error) {
      if (single || !(error instanceof ApiError) || error.status !== 404)
        throw error;
      notFound.push(value);
    }
  }
  const summary =
    values.length === 1 && items.length
      ? "Fetched 1 official Japan IP High Court case-list record(s)."
      : `Fetched ${items.length} of ${values.length} official Japan IP High Court case-list records.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(summary, items, caseList.provenance),
    more_available: false,
    not_found: notFound,
  };
}

const statusSchema = z.enum(["pending", "closed", "all"]);

export function registerJapanIpHighCourtTools(
  server: FastMCP,
  client: JapanIpHighCourtClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_japan_ip_high_court_cases",
      description:
        "Search the official Japanese IP High Court patent and utility-model case lists.\n\nThe workbook covers pending and recently closed suits seeking cancellation of JPO patent or utility-model decisions. It is useful for monitoring a known Japanese patent/application number or court case number. It is not a general infringement docket and does not publish party names, pleadings, or docket entries.\n\nRelated tool: get_japan_ip_high_court_case.",
      input: z.object({
        query: z
          .union([
            z.string().max(500),
            z.array(z.string().max(500)).min(1).max(ID_CAP),
          ])
          .nullable()
          .default(null)
          .describe(
            "Optional case number, patent/utility-model/application number, proceeding type, division, or disposition; a list is OR-matched.",
          ),
        case_status: statusSchema
          .default("pending")
          .describe(
            "Workbook sheet to search. Defaults to currently pending cases.",
          ),
        date_from: z
          .string()
          .max(10)
          .nullable()
          .default(null)
          .describe(
            "Optional YYYY-MM-DD lower bound for scheduled judgment (pending) or termination (closed).",
          ),
        date_to: z
          .string()
          .max(10)
          .nullable()
          .default(null)
          .describe(
            "Optional YYYY-MM-DD upper bound for scheduled judgment (pending) or termination (closed).",
          ),
        limit: z
          .number()
          .int()
          .min(1)
          .max(250)
          .default(100)
          .describe("Maximum results (1-250)."),
      }),
    },
    (input) => searchJapanIpHighCourtCases(client, input),
  );

  server.tool(
    {
      ...listToolOptions(auth),
      output: listEnvelopeSchema.extend({
        not_found: z.array(z.string()).optional(),
      }),
      name: "get_japan_ip_high_court_case",
      description:
        "Get exact official Japanese IP High Court case-list records.\n\nWidth variants in parentheses and whitespace are normalized. Accepts one case number or a list of up to 50; a list reports misses in not_found. Related tool: search_japan_ip_high_court_cases.",
      input: z.object({
        case_number: z
          .union([
            z.string().min(1).max(100),
            z.array(z.string().min(1).max(100)).min(1).max(ID_CAP),
          ])
          .describe(
            "Exact Japanese case number or list, e.g. '令和7年（行ケ）第10011号'.",
          ),
        case_status: statusSchema
          .default("all")
          .describe("Limit lookup to one workbook sheet or search both."),
      }),
    },
    ({ case_number, case_status }) =>
      getJapanIpHighCourtCases(client, case_number, case_status),
  );
}

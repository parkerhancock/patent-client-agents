import {
  ApiError,
  CANADA_FEDERAL_COURT_FILES_URL,
  type CanadaFederalCourtClient,
  type CourtDivision,
  CourtDivisionSchema,
  type DocketStatus,
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

const CONCURRENCY = 5;
const ID_CAP = 50;
const UNKNOWN_STATUS: DocketStatus = {
  assessment: "unknown",
  basis: "The docket status lookup failed; case metadata remains available.",
  inferred: true,
};

/** Python's provenance points at the human Court Files page, not the JSON endpoint. */
function provenance(base: Provenance, status: string, url?: string) {
  return {
    ...base,
    source_url: url ?? CANADA_FEDERAL_COURT_FILES_URL,
    as_of_status: status,
  };
}

/** Run `fn` over `items` with bounded concurrency, preserving order. */
async function mapBounded<T, R>(
  items: readonly T[],
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const results: R[] = [];
  for (let offset = 0; offset < items.length; offset += CONCURRENCY)
    results.push(
      ...(await Promise.all(items.slice(offset, offset + CONCURRENCY).map(fn))),
    );
  return results;
}

/** Lean case projection, field for field with Python's _case_stub. */
function caseStub(record: Record<string, unknown>): Record<string, unknown> {
  return {
    court_number: record.court_number,
    style_of_cause: record.style_of_cause,
    nature_en: record.nature_en,
    filed_date: record.filed_date,
    city_en: record.city_en,
    parties: record.parties ?? [],
    status_assessment: record.status_assessment,
  };
}

export interface CanadaFederalCourtSearchInput {
  party_name: string;
  filed_from?: string | null | undefined;
  filed_to?: string | null | undefined;
  division: CourtDivision;
  limit: number;
  patent_only: boolean;
  assess_status: boolean;
  full: boolean;
}
export async function searchCanadaFederalCourtPatentCases(
  client: CanadaFederalCourtClient,
  input: CanadaFederalCourtSearchInput,
) {
  if (!input.filed_from !== !input.filed_to)
    throw new ApiError(
      "filed_from and filed_to must be supplied together",
      400,
      "INVALID_INPUT",
    );
  const response = await client.searchPartyCases({
    partyName: input.party_name,
    division: input.division,
    ...(input.filed_from && input.filed_to
      ? { filedFrom: input.filed_from, filedTo: input.filed_to }
      : {}),
    patentOnly: input.patent_only,
    limit: input.limit,
  });
  const records: Record<string, unknown>[] = response.cases.map((c) => ({
    ...c,
  }));
  if (input.assess_status)
    await mapBounded(records, async (record) => {
      try {
        const docket = await client.listDocketEntries(
          String(record.court_number),
          { division: input.division, limit: 10 },
        );
        record.status_assessment = docket.status;
      } catch {
        record.status_assessment = { ...UNKNOWN_STATUS };
      }
    });
  else
    for (const record of records)
      record.status_assessment = {
        assessment: "unknown",
        basis:
          "Status assessment was not requested; the search response has no status field.",
        inferred: true,
      };
  const items = input.full ? records : records.map(caseStub);
  const resultLabel = input.patent_only
    ? "patent-filtered hits"
    : "IP-related hits";
  return {
    ...listEnvelope(
      `Canada Federal Court patent cases for \`${input.party_name}\`: ${items.length} returned from ${response.filtered_count} ${resultLabel} (${response.upstream_count} party-name hits before filtering). Party side/role and pending status are not official search fields.`,
      items,
      provenance(
        response.provenance,
        input.assess_status ? "inferred per item" : "not reported by upstream",
      ),
    ),
    more_available: response.filtered_count > items.length,
  };
}

/**
 * get_canada_federal_court_case. A single string propagates its not-found
 * error; list members that are missing go to not_found.
 */
export async function getCanadaFederalCourtCases(
  client: CanadaFederalCourtClient,
  courtNumber: string | string[],
  division: CourtDivision,
) {
  const single = typeof courtNumber === "string";
  const numbers = (single ? [courtNumber] : courtNumber)
    .map((n) => n.trim())
    .filter(Boolean);
  if (!numbers.length)
    throw new ApiError(
      "Provide at least one Federal Court file number.",
      400,
      "INVALID_INPUT",
    );
  if (numbers.length > ID_CAP)
    throw new ApiError(
      `Too many Federal Court file numbers: ${numbers.length} (limit ${ID_CAP} per call). Split the list into batches of ${ID_CAP} or fewer.`,
      400,
      "INVALID_INPUT",
    );
  const results = await mapBounded(numbers, async (number) => {
    try {
      const [record, docket] = await Promise.all([
        client.getCase(number, division),
        client.listDocketEntries(number, { division, limit: 10 }),
      ]);
      const { provenance: source, ...rest } = record;
      return {
        item: { ...rest, status_assessment: docket.status },
        provenance: source,
      };
    } catch (error) {
      if (!single && error instanceof ApiError && error.status === 404)
        return undefined;
      throw error;
    }
  });
  const found = results.filter((r) => r !== undefined);
  const notFound = numbers.filter((_n, i) => results[i] === undefined);
  const summary =
    numbers.length === 1 && found.length
      ? `Fetched 1 Canadian Federal Court file(s): ${numbers[0]}.`
      : `Fetched ${found.length} of ${numbers.length} Canadian Federal Court files.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  const statuses = [
    ...new Set(found.map((r) => r.item.status_assessment.assessment)),
  ].sort();
  const base: Provenance = found[0]?.provenance ?? {
    source_url: CANADA_FEDERAL_COURT_FILES_URL,
    source_name: "Federal Court of Canada — Court Files",
    retrieved_at: new Date().toISOString(),
    cache_hit: false,
  };
  return {
    ...listEnvelope(
      summary,
      found.map((r) => r.item),
      provenance(base, statuses.join(", ")),
    ),
    more_available: false,
    not_found: notFound,
  };
}

export interface CanadaFederalCourtDocketInput {
  court_number: string;
  division: CourtDivision;
  limit: number;
  full: boolean;
}
export async function listCanadaFederalCourtDocketEntries(
  client: CanadaFederalCourtClient,
  input: CanadaFederalCourtDocketInput,
) {
  const docket = await client.listDocketEntries(input.court_number, {
    division: input.division,
    limit: input.limit,
  });
  const items: Record<string, unknown>[] = docket.entries.map((entry) =>
    input.full
      ? { ...entry }
      : {
          entry_number: entry.entry_number,
          document_date: entry.document_date,
          office_en: entry.office_en,
          summary: entry.summary,
          document_number: entry.document_number,
          download_url: entry.download_url,
        },
  );
  return {
    ...listEnvelope(
      `Canada Federal Court ${docket.court_number}: ${items.length} recorded entries. Status assessment: ${docket.status.assessment} (${docket.status.basis})`,
      items,
      provenance(
        docket.provenance,
        docket.status.assessment,
        `${CANADA_FEDERAL_COURT_FILES_URL}?courtNumber=${encodeURIComponent(docket.court_number)}`,
      ),
    ),
    more_available: docket.total_count > docket.entries.length,
  };
}

const divisionInput = CourtDivisionSchema.default("t").describe(
  "Court selector: 't' Federal Court, 'a' Federal Court of Appeal, 'b' both.",
);
const isoDateInput = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "must be ISO date YYYY-MM-DD")
  .nullable()
  .default(null);

export function registerCanadaFederalCourtTools(
  server: FastMCP,
  client: CanadaFederalCourtClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_canada_federal_court_patent_cases",
      description:
        "Find Canadian Federal Court patent cases involving a party, including pending-case clues.\n\nSearches the official Court Files service, not CanLII's published-decision collection. Results include both plaintiff/applicant and defendant/respondent matches. The Registry stores most corporate names without periods, so search 'Apotex Inc', not 'Apotex Inc.'. The Court does not publish an official open/closed field, so any status is explicitly labeled as a conservative docket-text inference; ``unknown`` is common and should not be treated as no pending litigation.\n\nRelated tools: get_canada_federal_court_case, list_canada_federal_court_docket_entries, search_canlii_ip_cases.",
      input: z.object({
        party_name: z
          .string()
          .trim()
          .min(2)
          .max(200)
          .describe(
            "Party or corporation name; searches both sides of Federal Court case files.",
          ),
        filed_from: isoDateInput.describe(
          "Inclusive filing date, YYYY-MM-DD; requires filed_to.",
        ),
        filed_to: isoDateInput.describe(
          "Inclusive filing date, YYYY-MM-DD; requires filed_from.",
        ),
        division: divisionInput,
        limit: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(25)
          .describe("Maximum results after patent filtering (1-100)."),
        patent_only: z
          .boolean()
          .default(true)
          .describe(
            "Keep explicit patent/brevet nature labels only. False also returns ambiguous 'IP - Other' cases.",
          ),
        assess_status: z
          .boolean()
          .default(true)
          .describe(
            "Fetch each returned docket to infer likely_pending/likely_closed/unknown.",
          ),
        full: z
          .boolean()
          .default(false)
          .describe(
            "False returns lean case stubs; True returns all official search-result fields.",
          ),
      }),
    },
    (input) => searchCanadaFederalCourtPatentCases(client, input),
  );

  server.tool(
    {
      ...listToolOptions(auth),
      output: listEnvelopeSchema.extend({
        not_found: z.array(z.string()).optional(),
      }),
      name: "get_canada_federal_court_case",
      description:
        "Get official Canadian Federal Court case metadata, parties/counsel, and patent references.\n\nThe exact-file record includes the Registry's public party/counsel list, intellectual-property names and numbers, and related cases. It also includes a conservative status assessment from the recorded docket. Accepts one file number or a list of up to 50; missing files in a list go to not_found.\n\nRelated tools: search_canada_federal_court_patent_cases, list_canada_federal_court_docket_entries.",
      input: z.object({
        court_number: z
          .union([
            z.string().trim().min(3).max(40),
            z.array(z.string().trim().min(3).max(40)).min(1).max(ID_CAP),
          ])
          .describe(
            "Federal Court file number or list, e.g. 'T-2962-24' or ['T-2962-24', 'T-675-24'].",
          ),
        division: divisionInput,
      }),
    },
    ({ court_number, division }) =>
      getCanadaFederalCourtCases(client, court_number, division),
  );

  server.tool(
    {
      ...listToolOptions(auth),
      name: "list_canada_federal_court_docket_entries",
      description:
        "List the official recorded docket entries for a Canadian Federal Court file.\n\nEntries are live Registry snapshots, newest first, and may link downloadable public documents for eligible post-September-2022 IP cases. The envelope's status is inferred from explicit docket language and is not an official Court status.\n\nRelated tools: get_canada_federal_court_case, search_canada_federal_court_patent_cases.",
      input: z.object({
        court_number: z
          .string()
          .trim()
          .min(3)
          .max(40)
          .describe("Federal Court file number, e.g. 'T-2962-24'."),
        division: divisionInput,
        limit: z
          .number()
          .int()
          .min(1)
          .max(500)
          .default(100)
          .describe("Maximum recorded entries, newest first (1-500)."),
        full: z
          .boolean()
          .default(false)
          .describe(
            "False omits internal document/command fields; True returns the complete normalized entry.",
          ),
      }),
    },
    (input) => listCanadaFederalCourtDocketEntries(client, input),
  );
}

import {
  ApiError,
  CHINA_SPC_HEARING_INDEX_URL,
  CHINA_SPC_IP_COURT_ORIGIN,
  type ChinaSpcIpCourtClient,
  type ChinaSpcIpHearingNotice,
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

const SOURCE_NAME =
  "Supreme People's Court Intellectual Property Court — Hearing Notices";
const CONCURRENCY = 5;
const LIST_CAP = 50;
const NOT_AUTHORITATIVE = "scheduled hearings; not authoritative case status";

/** Lean projection of a notice, field for field with Python's _lean_hearing. */
export function leanHearing(
  notice: ChinaSpcIpHearingNotice,
): Record<string, unknown> {
  return {
    notice_id: notice.notice_id,
    hearing_date: notice.hearing_date,
    hearing_time_text: notice.hearing_time_text,
    venue: notice.venue,
    dispute_type: notice.dispute_type,
    parties: notice.parties,
    notice_url: notice.notice_url,
  };
}

/**
 * Today's date in China (UTC+8, no daylight saving), so a hearing on the
 * China calendar's today still counts as upcoming late in the UTC day.
 */
export function chinaToday(now: Date = new Date()): string {
  return new Date(now.getTime() + 8 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
}

/** Run `task` over `values` with at most `limit` in flight, keeping input order. */
async function mapLimit<T, R>(
  values: readonly T[],
  limit: number,
  task: (value: T) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(values.length);
  let next = 0;
  const worker = async () => {
    while (next < values.length) {
      const index = next++;
      results[index] = await task(values[index] as T);
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(limit, values.length) }, worker),
  );
  return results;
}

function sourceProvenance(
  provenance: Provenance | undefined,
  sourceUrl: string,
  status: string,
): Provenance {
  return {
    source_url: sourceUrl,
    source_name: SOURCE_NAME,
    retrieved_at: provenance?.retrieved_at ?? new Date().toISOString(),
    cache_hit: false,
    as_of_status: status,
  };
}

function terms(query: string | string[] | null | undefined): string[] {
  if (query === null || query === undefined) return [];
  const values = (typeof query === "string" ? [query] : query)
    .map((value) => value.trim())
    .filter(Boolean);
  if (!values.length)
    throw new ApiError(
      "query must contain at least one non-empty term",
      400,
      "INVALID_INPUT",
    );
  return values;
}

/** Every value of a notice as one string, for term matching. */
const haystack = (notice: ChinaSpcIpHearingNotice) =>
  Object.values(notice)
    .map((value) => (typeof value === "string" ? value : JSON.stringify(value)))
    .join(" ")
    .toLowerCase();

export interface ChinaSpcHearingSearchInput {
  query?: string | string[] | null | undefined;
  pages: number;
  future_only: boolean;
  limit: number;
  full: boolean;
}

/** search_china_spc_ip_hearing_notices */
export async function searchChinaSpcHearingNotices(
  client: ChinaSpcIpCourtClient,
  input: ChinaSpcHearingSearchInput,
  now: Date = new Date(),
) {
  const searchTerms = terms(input.query).map((term) => term.toLowerCase());
  const indexes = await mapLimit(
    Array.from({ length: input.pages }, (_, i) => i + 1),
    CONCURRENCY,
    (page) => client.listHearingIndex(page),
  );
  const today = chinaToday(now);
  const seen = new Set<string>();
  const stubs = indexes
    .flatMap((index) => index.data.notices)
    .filter((stub) => {
      if (seen.has(stub.notice_id)) return false;
      seen.add(stub.notice_id);
      // The index title carries the hearing date; skip fetching past hearings.
      const date = /(20\d{2})年(\d{1,2})月(\d{1,2})日/.exec(stub.title);
      if (!input.future_only || !date) return true;
      const iso = `${date[1]}-${date[2]?.padStart(2, "0")}-${date[3]?.padStart(2, "0")}`;
      return iso >= today;
    });
  let records = (
    await mapLimit(stubs, CONCURRENCY, (stub) =>
      client.getHearingNotice(stub.notice_id),
    )
  ).map((result) => result.data);
  if (input.future_only)
    records = records.filter((record) => (record.hearing_date ?? "") >= today);
  if (searchTerms.length)
    records = records.filter((record) => {
      const text = haystack(record);
      return searchTerms.some((term) => text.includes(term));
    });
  records.sort((a, b) =>
    (b.hearing_date ?? "").localeCompare(a.hearing_date ?? ""),
  );
  const totalMatches = records.length;
  const page = records.slice(0, input.limit);
  const totalIndexPages = Math.max(
    input.pages,
    ...indexes.map((index) => index.data.total_pages),
  );
  const label = searchTerms.length
    ? ` for ${JSON.stringify(terms(input.query))}`
    : "";
  return {
    ...listEnvelope(
      `China SPC IP Court hearing notices${label}: ${page.length} returned from ${totalMatches} matches across ${input.pages} recent index page(s). This is a hearing calendar, not a complete docket or party-side search.`,
      page.map((record) => (input.full ? { ...record } : leanHearing(record))),
      sourceProvenance(
        indexes[0]?.provenance,
        CHINA_SPC_HEARING_INDEX_URL,
        NOT_AUTHORITATIVE,
      ),
    ),
    more_available: totalMatches > page.length || totalIndexPages > input.pages,
    next_cursor: null,
  };
}

/** get_china_spc_ip_hearing_notice */
export async function getChinaSpcHearingNotices(
  client: ChinaSpcIpCourtClient,
  notice: string | string[],
  full: boolean,
) {
  const single = typeof notice === "string";
  const values = (single ? [notice] : notice)
    .map((value) => value.trim())
    .filter(Boolean);
  if (!values.length)
    throw new ApiError(
      "Provide at least one hearing notice ID or URL.",
      400,
      "INVALID_INPUT",
    );
  if (values.length > LIST_CAP)
    throw new ApiError(
      `Too many hearing notice ID or URLs: ${values.length} (limit ${LIST_CAP} per call). Split the list into batches of ${LIST_CAP} or fewer.`,
      400,
      "INVALID_INPUT",
    );
  const results = await mapLimit(values, CONCURRENCY, async (value) => {
    try {
      return await client.getHearingNotice(value);
    } catch (error) {
      if (!single && error instanceof ApiError && error.code === "NOT_FOUND")
        return null;
      throw error;
    }
  });
  const found = results.filter((result) => result !== null);
  const notFound = values.filter((_value, i) => results[i] === null);
  const records = found.map((result) => result.data);
  const summary =
    values.length === 1 && records.length
      ? "Fetched 1 official China SPC IP Court hearing notice(s)."
      : `Fetched ${records.length} of ${values.length} official China SPC IP Court hearing notices.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  const dates = [
    ...new Set(records.map((record) => record.hearing_date ?? "date unknown")),
  ].sort();
  return {
    ...listEnvelope(
      summary,
      records.map((record) => (full ? { ...record } : leanHearing(record))),
      sourceProvenance(
        found[0]?.provenance,
        records[0]?.notice_url ?? CHINA_SPC_HEARING_INDEX_URL,
        `scheduled hearing date(s): ${dates.join(", ")}`,
      ),
    ),
    more_available: false,
    next_cursor: null,
    not_found: notFound,
  };
}

export interface ChinaSpcSiteSearchInput {
  query: string;
  page: number;
  hearing_notices_only: boolean;
  limit: number;
}

/** search_china_spc_ip_court_site */
export async function searchChinaSpcCourtSite(
  client: ChinaSpcIpCourtClient,
  input: ChinaSpcSiteSearchInput,
) {
  const result = await client.searchSite(input.query, input.page);
  const response = result.data;
  const hits = input.hearing_notices_only
    ? response.hits.filter((hit) => hit.is_hearing_notice)
    : response.hits;
  const records = hits.slice(0, input.limit);
  const more = response.total_pages > input.page;
  return {
    ...listEnvelope(
      `China SPC IP Court site search for \`${response.query}\`: ${records.length} result(s) returned from approximately ${response.total_count} upstream matches (page ${input.page} of ${response.total_pages}, oldest first).`,
      records.map((hit) => ({ ...hit })),
      sourceProvenance(
        result.provenance,
        `${CHINA_SPC_IP_COURT_ORIGIN}/zh-cn/search.html?${new URLSearchParams({ content: response.query })}`,
        "site content; not authoritative case status",
      ),
    ),
    more_available: more || hits.length > records.length,
    next_cursor: more ? String(input.page + 1) : null,
  };
}

const RELATED_SEARCH =
  "Related tools: get_china_spc_ip_hearing_notice, search_china_spc_ip_court_site.";

export function registerChinaSpcIpCourtTools(
  server: FastMCP,
  client: ChinaSpcIpCourtClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_china_spc_ip_hearing_notices",
      description: `Search recent scheduled hearings at China's national appellate IP court, the Supreme People's Court Intellectual Property Court.

The official feed covers public hearing notices for patent, integrated-circuit, trade-secret, software, plant-variety, and technology antitrust appeals. It is useful for pending-hearing monitoring but is not a complete case docket: notices may omit the case number, patent number, and subsequent disposition. Chinese party names or aliases produce the best matches.

${RELATED_SEARCH}`,
      input: z.object({
        query: z
          .union([
            z.string().max(200),
            z.array(z.string().max(200)).min(1).max(20),
          ])
          .nullable()
          .default(null)
          .describe(
            "Optional Chinese party/company or technology term, or OR-list such as ['芯片', '半导体', '集成电路'].",
          ),
        pages: z
          .number()
          .int()
          .min(1)
          .max(50)
          .default(10)
          .describe(
            "Recent hearing-index pages to inspect (1-50); each page currently contains five notices.",
          ),
        future_only: z
          .boolean()
          .default(true)
          .describe(
            "Keep notices whose scheduled hearing date is today or later (China calendar).",
          ),
        limit: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(25)
          .describe("Maximum matching notices (1-100)."),
        full: z
          .boolean()
          .default(false)
          .describe(
            "False returns lean hearing records; True also includes the Chinese notice body and raw party clause.",
          ),
      }),
    },
    (input) => searchChinaSpcHearingNotices(client, input),
  );

  server.tool(
    {
      ...listToolOptions(auth),
      output: listEnvelopeSchema.extend({
        not_found: z.array(z.string()).optional(),
      }),
      name: "get_china_spc_ip_hearing_notice",
      description: `Get exact official Chinese scheduled-hearing notices from the Supreme People's Court Intellectual Property Court.

Accepts a numeric notice ID ('6173'), an official URL ('https://ipc.court.gov.cn/zh-cn/news/view-6173.html') or a list of up to 50; the response is always a list envelope, with missing notices in not_found.

Related tools: search_china_spc_ip_hearing_notices, search_china_spc_ip_court_site.`,
      input: z.object({
        notice: z
          .union([
            z.string().min(1).max(200),
            z.array(z.string().min(1).max(200)).min(1).max(LIST_CAP),
          ])
          .describe("Official numeric notice ID/URL or a list, e.g. '6173'."),
        full: z
          .boolean()
          .default(true)
          .describe(
            "False returns lean normalized fields; True includes the complete Chinese notice text.",
          ),
      }),
    },
    ({ notice, full }) => getChinaSpcHearingNotices(client, notice, full),
  );

  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_china_spc_ip_court_site",
      description: `Search the official website of China's Supreme People's Court Intellectual Property Court by party or technology term.

This broader source can locate judgments, case write-ups and court news as well as hearing notices; results run oldest first, 20 to a page. It does not search the restricted national judicial-process system and should not be treated as exhaustive party litigation coverage.

Related tools: search_china_spc_ip_hearing_notices, get_china_spc_ip_hearing_notice.`,
      input: z.object({
        query: z
          .string()
          .min(2)
          .max(200)
          .describe(
            "Chinese party/company, case, or technology term; e.g. '华为', '芯片', or '集成电路'.",
          ),
        page: z
          .number()
          .int()
          .min(1)
          .default(1)
          .describe("One-indexed upstream result page."),
        hearing_notices_only: z
          .boolean()
          .default(false)
          .describe(
            "Keep results explicitly titled as hearing notices; false also returns judgments, case analyses, and court news.",
          ),
        limit: z
          .number()
          .int()
          .min(1)
          .max(25)
          .default(25)
          .describe("Maximum results from this page (1-25)."),
      }),
    },
    (input) => searchChinaSpcCourtSite(client, input),
  );
}

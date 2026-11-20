import {
  JPO_BASE_URL,
  type JpoClient,
  type JpoIpType,
  type JpoResult,
  type Provenance,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

/** Python LIST_CAP and DEFAULT_CONCURRENCY for list-accepting fetch tools. */
const LIST_CAP = 50;
const CONCURRENCY = 5;

const ipType = z
  .enum(["patent", "design", "trademark"])
  .default("patent")
  .describe("Which JPO register to query. The same tool works for all three.");
const numberList = (description: string) =>
  z
    .union([
      z.string().min(1).max(40),
      // Blank entries are dropped, as Python's as_id_list does.
      z.array(z.string().max(40)).min(1).max(LIST_CAP),
    ])
    .describe(description);
const numberField = (description: string) =>
  z.string().trim().min(1).max(40).describe(description);

function ids(value: string | string[]): string[] {
  const list = (typeof value === "string" ? [value] : value)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!list.length)
    throw new Error("Provide at least one JP application number.");
  if (list.length > LIST_CAP)
    throw new Error(
      `Too many JP application numbers: ${list.length} (limit ${LIST_CAP} per call). Split the list into batches of ${LIST_CAP} or fewer.`,
    );
  return list;
}

/** Python fetch_many: bounded concurrency, input order, empty results listed as not found. */
async function fetchMany<T>(
  numbers: string[],
  fetch: (number: string) => Promise<JpoResult<T | null>>,
) {
  const results: JpoResult<T | null>[] = new Array(numbers.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, numbers.length) }, async () => {
      while (next < numbers.length) {
        const index = next++;
        results[index] = await fetch(numbers[index] as string);
      }
    }),
  );
  const items: Record<string, unknown>[] = [];
  const notFound: string[] = [];
  results.forEach((result, index) => {
    if (result.data) items.push(result.data as Record<string, unknown>);
    else notFound.push(numbers[index] as string);
  });
  return {
    items,
    notFound,
    provenance: (results[0] as JpoResult<T>).provenance,
  };
}
/** One request's provenance, or the endpoint's for a list. */
function listProvenance(
  provenance: Provenance,
  numbers: string[],
  path: string,
) {
  return numbers.length === 1
    ? provenance
    : { ...provenance, source_url: `${JPO_BASE_URL}/api${path}` };
}
function fetchedSummary(
  found: number,
  requested: number,
  noun: string,
  notFound: string[],
) {
  return `Fetched ${found} of ${requested} ${noun}.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
}

const TITLE_FIELD: Record<JpoIpType, string> = {
  patent: "invention_title",
  design: "design_article",
  trademark: "trademark_for_display",
};
/**
 * Python looked for camelCase and status keys its snake_case records never
 * have, so design and trademark titles and every status read "unknown".
 */
function progressSummary(
  ip: JpoIpType,
  number: string,
  record: Record<string, unknown> | undefined,
) {
  if (!record) return `**JPO application ${number}** — no data on file.`;
  const title = String(record[TITLE_FIELD[ip]] ?? "") || "(no title)";
  const filing = String(record.filing_date ?? "") || "?";
  const registration = String(record.registration_number ?? "");
  const registered = registration
    ? ` Registration ${registration}${record.registration_date ? ` (${record.registration_date})` : ""}.`
    : "";
  return `**JPO application ${number}** — ${title}\nFiled ${filing}.${registered}`;
}
function registrationSummary(
  number: string,
  record: Record<string, unknown> | undefined,
) {
  if (!record) return `**JPO application ${number}** — not registered.`;
  const reg = String(record.registration_number ?? "") || "(no reg #)";
  const date = String(record.registration_date ?? "") || "?";
  return `**JPO registration ${reg}** (application ${number})\nRegistered ${date}.`;
}

const fetchedSchema = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});
const DOC_KINDS = {
  application: "application (applicant-filed opinions and amendments)",
  mailed: "mailed (JPO notices and decisions)",
  refusal: "refusal (notices of reasons for refusal)",
} as const;

/**
 * The eleven Python JPO tools, with the same names and parameters. Register
 * them only when a client exists: JPO_API_USERNAME and JPO_API_PASSWORD are
 * JPO-issued, and the public demo carries none, per JPO's terms.
 */
export function registerJpoTools(
  server: FastMCP,
  client: JpoClient,
  auth?: AuthCheck,
) {
  const fetched = {
    output: fetchedSchema,
    outputSchema: objectOutputSchema(fetchedSchema),
    annotations: detailToolOptions().annotations,
    ...(auth ? { auth } : {}),
  };
  const detail = detailToolOptions(auth);

  const progress =
    (simple: boolean) =>
    async (input: {
      application_number: string | string[];
      ip_type: JpoIpType;
    }) => {
      const numbers = ids(input.application_number);
      const ip = input.ip_type;
      const endpoint = simple ? "app_progress_simple" : "app_progress";
      const { items, notFound, provenance } = await fetchMany(numbers, (n) =>
        client.getProgress(ip, n, { simple }),
      );
      return {
        ...listEnvelope(
          numbers.length === 1
            ? progressSummary(ip, numbers[0] as string, items[0])
            : fetchedSummary(
                items.length,
                numbers.length,
                `JPO ${ip} ${simple ? "simplified status" : "progress"} records`,
                notFound,
              ),
          items,
          listProvenance(provenance, numbers, `/${ip}/v1/${endpoint}`),
        ),
        not_found: notFound,
      };
    };

  server.tool(
    {
      ...fetched,
      name: "get_jpo_progress",
      description:
        "Get full prosecution status for a JPO patent, design, or trademark filing.\n\nReturns title, applicants, filing/publication/registration dates, priority claims (Paris Convention or domestic), parent + divisional family info (patents and designs), expiration, erasure status, and the file-wrapper inventory.\n\nAccepts a single number or a list; the response is always a list envelope. An unknown number (status 107 / 111) is left out of `items` and listed in `not_found`.\n\nRelated tools: get_jpo_progress_simple, get_jpo_priority_info, get_jpo_registration_info, get_jpo_documents, get_jpo_jplatpat_url.",
      input: z.object({
        application_number: numberList(
          "10-digit JP application number (Gregorian year 4 digits + 6-digit serial, e.g. '2020123456'), or a list for portfolio workflows. Format is the same for patent, design, and trademark applications.",
        ),
        ip_type: ipType,
      }),
    },
    progress(false),
  );

  server.tool(
    {
      ...fetched,
      name: "get_jpo_progress_simple",
      description:
        "Get a simplified JPO status (no priority or family detail).\n\nWorks for patent, design, or trademark applications. Cheaper than `get_jpo_progress` for bulk status checks — same daily quota tier but skips the priority and divisional sections. Accepts a single number or a list; the response is always a list envelope.\n\nRelated tools: get_jpo_progress, get_jpo_priority_info, get_jpo_registration_info, get_jpo_documents.",
      input: z.object({
        application_number: numberList(
          "10-digit JP application number, or a list for portfolio workflows.",
        ),
        ip_type: ipType,
      }),
    },
    progress(true),
  );

  server.tool(
    {
      ...fetched,
      name: "get_jpo_priority_info",
      description:
        "List priority basis applications (Paris + domestic) for a JPO filing.\n\nEach row carries either a Paris Convention foreign priority (application number + country code + date) or a domestic JP priority (application number + four-law code + date). Works for patent, design, or trademark applications.\n\nRelated tools: get_jpo_progress, get_jpo_registration_info, get_jpo_number_reference.",
      input: z.object({
        application_number: numberField("10-digit JP application number"),
        ip_type: ipType,
      }),
    },
    async ({ application_number, ip_type }) => {
      const result = await client.getPriorityInfo(ip_type, application_number);
      const count = result.data.length;
      return {
        ...listEnvelope(
          `**JPO application ${application_number}** — ${count} priority claim${count === 1 ? "" : "s"}.`,
          result.data,
          result.provenance,
        ),
        not_found: [],
      };
    },
  );

  server.tool(
    {
      ...fetched,
      name: "get_jpo_registration_info",
      description:
        "Get the JPO granted-rights record for a patent, design, or trademark filing.\n\nIncludes registration number/date, decision date, current rights holders, claim count (patents) / design article (designs) / trademark display (trademarks), expiration, next annuity payment due date, last paid year, erasure flag/date, and last update date. Accepts a single number or a list. An application that is not registered is left out of `items` and listed in `not_found`.\n\nRelated tools: get_jpo_progress, get_jpo_priority_info, get_jpo_number_reference.",
      input: z.object({
        application_number: numberList(
          "10-digit JP application number, or a list for portfolio workflows.",
        ),
        ip_type: ipType,
      }),
    },
    async ({ application_number, ip_type }) => {
      const numbers = ids(application_number);
      const { items, notFound, provenance } = await fetchMany(numbers, (n) =>
        client.getRegistrationInfo(ip_type, n),
      );
      return {
        ...listEnvelope(
          numbers.length === 1
            ? registrationSummary(numbers[0] as string, items[0])
            : fetchedSummary(
                items.length,
                numbers.length,
                `JPO ${ip_type} registration records`,
                notFound,
              ),
          items,
          listProvenance(
            provenance,
            numbers,
            `/${ip_type}/v1/registration_info`,
          ),
        ),
        not_found: notFound,
      };
    },
  );

  server.tool(
    {
      ...detail,
      name: "get_jpo_number_reference",
      description:
        "Convert a JPO number between application, publication, and registration forms.\n\nGiven any one of the three identifiers for a JPO record, returns the other associated numbers for the same record. Works for patent, design, or trademark applications. `details` is `{}` when no cross-reference exists.\n\nRelated tools: get_jpo_progress, get_jpo_registration_info, get_jpo_jplatpat_url.",
      input: z.object({
        number: numberField(
          "The number to look up. Application number = 10 digits (YYYY+6 digits), publication = 10 digits (Gregorian), registration = 7 digits.",
        ),
        kind: z
          .enum(["application", "publication", "registration"])
          .default("application")
          .describe(
            "Number type — descriptive strings, NOT the numeric NumberType codes used in bibliographyInformation.",
          ),
        ip_type: ipType,
      }),
    },
    async ({ number, kind, ip_type }) => {
      const result = await client.getNumberReference(ip_type, kind, number);
      return detailEnvelope(
        result.data
          ? `**JPO ${kind} ${number}** — cross-reference resolved.`
          : `**JPO ${kind} ${number}** — no cross-reference found.`,
        result.data ?? {},
        result.provenance,
      );
    },
  );

  server.tool(
    {
      ...detail,
      name: "get_jpo_jplatpat_url",
      description:
        "Get the J-PlatPat (JPO public search portal) permalink for a JPO filing.\n\nJ-PlatPat is JPO's free public search portal — the returned URL is a stable permalink that opens directly to this filing's bibliographic page (in Japanese). Works for patent, design, or trademark applications. `details.url` is the permalink, or absent when no URL is available.\n\nRelated tools: get_jpo_progress, get_jpo_number_reference.",
      input: z.object({
        application_number: numberField("10-digit JP application number"),
        ip_type: ipType,
      }),
    },
    async ({ application_number, ip_type }) => {
      const result = await client.getJplatpatUrl(ip_type, application_number);
      return detailEnvelope(
        result.data
          ? `**JPO application ${application_number}** — J-PlatPat permalink: ${result.data}`
          : `**JPO application ${application_number}** — no J-PlatPat URL available.`,
        result.data ? { url: result.data } : {},
        result.provenance,
      );
    },
  );

  server.tool(
    {
      ...detail,
      name: "get_jpo_applicant",
      description:
        "Look up a JPO applicant/attorney by 9-digit code or by exact registered name.\n\nAuto-detects which lookup to run from the input shape: 9-digit numeric → code-to-name; anything else → exact-name-to-code(s). `details.name` carries the resolved name for a code lookup; `details.results` carries the matching code rows for a name lookup. Empty when nothing matches. Works for patent, design, or trademark registers.\n\nRelated tools: get_jpo_progress, get_jpo_registration_info.",
      input: z.object({
        applicant: z
          .string()
          .trim()
          .min(1)
          .max(200)
          .describe(
            "JPO applicant/attorney identifier. Either a 9-digit code (e.g. '000003207') or the EXACT registered name (e.g. 'トヨタ自動車株式会社'). Auto-detected: 9 digits → code lookup; anything else → name lookup. Name search requires an exact match — partial / fuzzy queries return no data.",
          ),
        ip_type: ipType,
      }),
    },
    async ({ applicant, ip_type }) => {
      if (/^\d{9}$/.test(applicant)) {
        const result = await client.getApplicantByCode(ip_type, applicant);
        return detailEnvelope(
          result.data
            ? `**JPO applicant code ${applicant}** — ${result.data}`
            : `**JPO applicant code ${applicant}** — not found.`,
          result.data ? { name: result.data } : {},
          result.provenance,
        );
      }
      const result = await client.getApplicantByName(ip_type, applicant);
      return detailEnvelope(
        result.data.length
          ? `**JPO applicant \`${applicant}\`** — ${result.data.length} matching code(s).`
          : `**JPO applicant \`${applicant}\`** — not found (exact match required).`,
        { results: result.data },
        result.provenance,
      );
    },
  );

  server.tool(
    {
      ...detail,
      name: "get_jpo_patent_divisional_info",
      description:
        "Get the divisional family (parent + descendants) for a JP patent.\n\nPatent-only endpoint (no design or trademark equivalent). Returns the parent application info (if any) and a list of divisional descendants with their generation, publication/registration numbers, erasure status, and expiration. `details` is `{}` when the application has no divisional history.\n\nRelated tools: get_jpo_progress, get_jpo_patent_cited_documents, get_jpo_pct_national_phase_number.",
      input: z.object({
        application_number: numberField(
          "10-digit JP patent application number",
        ),
      }),
    },
    async ({ application_number }) => {
      const result = await client.getPatentDivisionalInfo(application_number);
      return detailEnvelope(
        result.data
          ? `**JPO patent ${application_number}** — divisional family resolved.`
          : `**JPO patent ${application_number}** — no divisional history.`,
        result.data ?? {},
        result.provenance,
      );
    },
  );

  server.tool(
    {
      ...detail,
      name: "get_jpo_patent_cited_documents",
      description:
        "Get patent and non-patent literature citations for a JP patent application.\n\nPatent-only endpoint. Returns `patent_doc` (cited patent documents with type/order) and `non_patent_doc` (non-patent literature with author, title, publication, etc.). Citation types follow JPO code-table 07010. `details` is `{}` when no citations exist.\n\nRelated tools: get_jpo_progress, get_jpo_patent_divisional_info.",
      input: z.object({
        application_number: numberField(
          "10-digit JP patent application number",
        ),
      }),
    },
    async ({ application_number }) => {
      const result = await client.getPatentCitedDocuments(application_number);
      return detailEnvelope(
        result.data
          ? `**JPO patent ${application_number}** — citation record resolved.`
          : `**JPO patent ${application_number}** — no citations on file.`,
        result.data ?? {},
        result.provenance,
      );
    },
  );

  server.tool(
    {
      ...detail,
      name: "get_jpo_pct_national_phase_number",
      description:
        "Look up the JP national-phase application number for a PCT filing.\n\nPatent-only endpoint. Useful for following PCT applications that have entered Japan's national phase. `details` is `{}` when the PCT filing has no JP national-phase record.\n\nRelated tools: get_jpo_progress, get_jpo_patent_divisional_info.",
      input: z.object({
        number: numberField(
          "PCT international application number (e.g. 'JP2019011858') or international publication number (e.g. 'WO2019123456').",
        ),
        kind: z
          .enum(["international_application", "international_publication"])
          .default("international_application")
          .describe(
            "Either 'international_application' (use with PCT/JP-style number) or 'international_publication' (use with WO-style number).",
          ),
      }),
    },
    async ({ number, kind }) => {
      const result = await client.getPatentPctNationalPhase(kind, number);
      return detailEnvelope(
        result.data
          ? `**PCT ${number}** — JP national phase resolved.`
          : `**PCT ${number}** — no JP national-phase record.`,
        result.data ?? {},
        result.provenance,
      );
    },
  );

  server.tool(
    {
      ...detail,
      name: "get_jpo_documents",
      description:
        "Download (and optionally parse) a JPO document bundle.\n\nWorks for patent, design, or trademark applications across all three doc-kinds. Patent bundles ship Shift-JIS XML; design and trademark bundles ship Shift-JIS HTM. The parser decodes both.\n\nWith `parse=True` (default) returns the parsed file-history entries (one per document in the JPO ZIP) in `details.entries`, plus `details.document`, a link (or local path) to the raw archive for binary attachments and fields not surfaced inline. Each entry includes (where applicable): JPO document code, document name (Japanese), document variant (root XML element / `htm` for HTM), application number, drafting/filing date (YYYYMMDD), examiner / drafting person (mailed docs), statute references (refusal notices), and body text. `details.binary_attachments` lists other files in the archive.\n\nWith `parse=False` skips parsing and returns the bundle metadata with empty `entries` and the archive link.\n\n`details` is `{}` when JPO has no documents on file (status 107 / 108), regardless of `parse`.",
      input: z.object({
        application_number: numberField(
          "10-digit JP application number (Gregorian year + 6-digit serial). Format is the same for patent, design, and trademark applications.",
        ),
        doc_kind: z
          .enum(["application", "mailed", "refusal"])
          .default("mailed")
          .describe(
            "Which document set to fetch: 'application' (applicant-filed opinions / amendments), 'mailed' (JPO-mailed notices including rejections AND decisions of grant), or 'refusal' (rejection notices only — strict subset of 'mailed').",
          ),
        ip_type: ipType,
        parse: z
          .boolean()
          .default(true)
          .describe(
            "If True (default), parse the bundle ZIP and return file-history entries with body text inline. If False, skip parsing and return just the bundle metadata + the archive link.",
          ),
      }),
    },
    async ({ application_number, doc_kind, ip_type, parse }) => {
      const label = `**JPO ${ip_type} application ${application_number}**`;
      const result = parse
        ? await client.getDocuments(ip_type, doc_kind, application_number)
        : await client
            .getDocumentArchive(ip_type, doc_kind, application_number)
            .then(({ bundle, zip }) => ({
              data: {
                application_number: bundle.application_number,
                ip_type: bundle.ip_type,
                doc_kind: bundle.doc_kind,
                entries: [],
                binary_attachments: [],
              },
              zip,
              provenance: bundle.provenance,
            }));
      if (!result.zip)
        return detailEnvelope(
          `${label} — no ${DOC_KINDS[doc_kind]} documents on file.`,
          {},
          result.provenance,
        );
      const document = await downloadResult(
        result.zip,
        `jpo_${ip_type}_${application_number}_${doc_kind}.zip`,
        "application/zip",
        result.provenance,
      );
      const entries = result.data.entries;
      const listed = entries
        .map(
          (entry) =>
            `${entry.document_name || entry.document_code || entry.filename}${entry.legal_date ? ` (${entry.legal_date})` : ""}`,
        )
        .join(", ");
      return detailEnvelope(
        parse
          ? `${label} — ${entries.length} ${DOC_KINDS[doc_kind]} document${entries.length === 1 ? "" : "s"}${listed ? `: ${listed}` : ""}.`
          : `${label} — ${DOC_KINDS[doc_kind]} bundle archived, not parsed.`,
        { ...result.data, document },
        result.provenance,
      );
    },
  );
}

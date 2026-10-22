import {
  KIPRIS_MAX_ROWS,
  type KiprisClient,
  type KiprisDesignRow,
  type KiprisPage,
  type KiprisPatentRow,
  type KiprisTrademarkRow,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

/** Python LIST_CAP for list-accepting fetch tools. */
const LIST_CAP = 50;

// ── Lean projections. Python's _lean_* keys, less the fields the KIPRIS
// documentation shows no search element for (see docs/kipris.md). ─────

export function leanKiprisPatent(row: KiprisPatentRow) {
  return {
    application_number: row.applicationNumber,
    application_date: row.applicationDate,
    publication_number: row.publicationNumber,
    publication_date: row.publicationDate,
    register_number: row.registerNumber,
    register_status: row.registerStatus,
    invention_title: row.inventionTitle,
    applicant_name: row.applicantName,
    ipc_number: row.ipcNumber,
  };
}
export function leanKiprisTrademark(row: KiprisTrademarkRow) {
  return {
    application_number: row.applicationNumber,
    application_date: row.applicationDate,
    registration_number: row.registrationNumber,
    registration_date: row.registrationDate,
    title: row.title,
    classification_code: row.classificationCode,
    vienna_code: row.viennaCode,
    applicant_name: row.applicantName,
    big_drawing: row.bigDrawing,
  };
}
export function leanKiprisDesign(row: KiprisDesignRow) {
  return {
    application_number: row.applicationNumber,
    application_date: row.applicationDate,
    registration_number: row.registrationNumber,
    registration_date: row.registrationDate,
    register_status: row.applicationStatus,
    article_name: row.articleName,
    design_classification: row.designMainClassification,
    applicant_name: row.applicantName,
    inventor_name: row.inventorName,
    drawing: row.imagePath,
  };
}

/** Python's summary and more_available arithmetic over one search page. */
function searchEnvelope<T extends Record<string, unknown>>(
  label: string,
  page: KiprisPage<T>,
  lean: (row: T) => Record<string, unknown>,
  full: boolean,
  pageNo: number,
  numOfRows: number,
) {
  const items = page.items.map((row) => (full ? { ...row } : lean(row)));
  const total = page.pagination.totalCount;
  const counted = typeof total === "number";
  // Python multiplied by the requested size; the client caps it at the documented 500 rows.
  const rows = Math.min(numOfRows, KIPRIS_MAX_ROWS);
  return {
    ...listEnvelope(
      `${label}: ${counted ? `${items.length} of ${total} hits` : `${items.length} hits`}.`,
      items,
      page.provenance,
    ),
    more_available: counted && pageNo * rows < total,
  };
}

const rightFlags = (rightType: "patent" | "utility_model" | "both") => ({
  patent: rightType === "patent" || rightType === "both",
  utility: rightType === "utility_model" || rightType === "both",
});

export interface KiprisPatentSearchInput {
  query: string;
  right_type: "patent" | "utility_model" | "both";
  num_of_rows: number;
  page_no: number;
  full: boolean;
}
/** search_kipo_patents; also serves search_patents(jurisdiction='kr'). */
export async function searchKipoPatents(
  client: KiprisClient,
  input: KiprisPatentSearchInput,
) {
  const page = await client.searchPatentsWord(input.query, {
    ...rightFlags(input.right_type),
    numOfRows: input.num_of_rows,
    pageNo: input.page_no,
  });
  return searchEnvelope(
    `KIPO patents/UM — \`${input.query}\``,
    page,
    leanKiprisPatent,
    input.full,
    input.page_no,
    input.num_of_rows,
  );
}

type Getter<T> = (number: string) => Promise<KiprisPage<T>>;
/**
 * Python get_kipo_*: one request per number, serially (ToS §11 quota). An
 * empty hit list is not found, for a single number as well as for a list.
 */
async function fetchKipo<T extends Record<string, unknown>>(
  value: string | string[],
  get: Getter<T>,
  lean: (row: T) => Record<string, unknown>,
  full: boolean,
  noun: { single: string; plural: string },
) {
  const numbers = (typeof value === "string" ? [value] : value)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!numbers.length)
    throw new Error("Provide at least one application number.");
  if (numbers.length > LIST_CAP)
    throw new Error(
      `Too many application numbers: ${numbers.length} (limit ${LIST_CAP} per call). Split the list into batches of ${LIST_CAP} or fewer.`,
    );
  const rows: T[] = [];
  const notFound: string[] = [];
  let provenance: KiprisPage<T>["provenance"] | undefined;
  for (const number of numbers) {
    const page = await get(number);
    provenance ??= page.provenance;
    if (page.items.length) rows.push(...page.items);
    else notFound.push(number);
  }
  const items = rows.map((row) => (full ? { ...row } : lean(row)));
  const found = numbers.length - notFound.length;
  const summary =
    numbers.length === 1
      ? `Fetched ${items.length} KIPO ${noun.single} record(s) for 1 number(s).`
      : `Fetched ${found} of ${numbers.length} KIPO ${noun.plural}.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      items,
      // At least one number was requested, so a page (and provenance) exists.
      provenance as KiprisPage<T>["provenance"],
    ),
    more_available: false,
    not_found: notFound,
  };
}

/** get_kipo_patent; also serves get_patent(view='biblio') for KR numbers. */
export function getKipoPatents(
  client: KiprisClient,
  numbers: string | string[],
  full = false,
) {
  return fetchKipo(
    numbers,
    (n) => client.getPatent(n),
    leanKiprisPatent,
    full,
    { single: "patent/UM", plural: "patent/UM records" },
  );
}

// ── Tool schemas ─────────────────────────────────────────────────────

const rowsField = z
  .number()
  .int()
  .min(1)
  .default(10)
  .describe("Page size (max 500).");
const pageField = z
  .number()
  .int()
  .min(1)
  .default(1)
  .describe("1-indexed page number.");
const fullField = z
  .boolean()
  .default(false)
  .describe("When True, return full upstream rows (default lean).");
const optionalText = (description: string) =>
  z.string().nullable().default(null).describe(description);
const rightType = z
  .enum(["patent", "utility_model", "both"])
  .default("both")
  .describe("One of 'patent', 'utility_model', 'both' (default).");
const numberInput = (description: string) =>
  z
    .union([
      z.string().min(1).max(80),
      z.array(z.string().min(1).max(80)).min(1).max(LIST_CAP),
    ])
    .describe(description);
const orUndefined = (value: string | null) => value ?? undefined;

const fetchedSchema = listEnvelopeSchema.extend({
  not_found: z.array(z.string()).optional(),
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};
const RELATED =
  "Related tools: `search_epo_patents` / `get_epo_biblio` — EPO INPADOC provides KR biblio + family at the regional layer with no BYOK requirement; prefer KIPO only for KR-language full text, prosecution depth, or utility models.";

/**
 * The nine Python KIPO KIPRIS tools, with the same names and parameters.
 * Register them only when a client exists (KIPO_KIPRIS_API_KEY and an HTTPS
 * KIPO_KIPRIS_BASE_URL are configured).
 */
export function registerKiprisTools(
  server: FastMCP,
  client: KiprisClient,
  auth?: AuthCheck,
) {
  const options = {
    output: fetchedSchema,
    outputSchema: objectOutputSchema(fetchedSchema),
    annotations,
    ...(auth ? { auth } : {}),
  };

  server.tool(
    {
      ...options,
      name: "search_kipo_patents",
      description: `Search KIPO patents and utility models by free text.\n\nReturns a lean stub per hit by default; pass full=True for the full XML-derived row. Use right_type to limit to patents-only or utility-models-only.\n\n${RELATED}`,
      input: z.object({
        query: z
          .string()
          .min(1)
          .describe(
            "Free-text search string. Matches title, abstract, applicant, and inventor across KIPRIS patent + utility-model rows.",
          ),
        right_type: rightType,
        num_of_rows: rowsField.describe(
          "Page size. Defaults to 10; KIPRIS Plus allows at most 500.",
        ),
        page_no: pageField,
        full: z
          .boolean()
          .default(false)
          .describe(
            "When False (default), each hit is a lean stub (drops the Korean-only astrt_cont abstract). When True, every hit carries the full upstream-shaped row.",
          ),
      }),
    },
    (input) => searchKipoPatents(client, input),
  );

  server.tool(
    {
      ...options,
      name: "search_kipo_patents_advanced",
      description: `Structured-field search over KIPO patents and utility models.\n\nEvery field is optional; KIPRIS ANDs whatever is provided. Use this when free-text search is too imprecise (e.g. exact applicant match, IPC + date-range filtering).\n\n${RELATED}`,
      input: z.object({
        invention_title: optionalText(
          "Match against invention title (Korean or English).",
        ),
        astrt_cont: optionalText("Match against abstract content."),
        claim_scope: optionalText("Match against claim text."),
        applicant: optionalText(
          "Match against applicant name (Korean or romanized).",
        ),
        inventor: optionalText("Match against inventor name."),
        ipc: optionalText("IPC classification code (e.g. 'G06F')."),
        application_date: optionalText(
          "Filing date filter (YYYYMMDD or YYYYMMDD~YYYYMMDD range).",
        ),
        publication_date: optionalText(
          "Publication date filter (YYYYMMDD or range).",
        ),
        right_type: rightType,
        num_of_rows: rowsField,
        page_no: pageField,
        full: fullField,
      }),
    },
    async (input) => {
      const page = await client.searchPatentsAdvanced({
        inventionTitle: orUndefined(input.invention_title),
        astrtCont: orUndefined(input.astrt_cont),
        claimScope: orUndefined(input.claim_scope),
        applicant: orUndefined(input.applicant),
        inventor: orUndefined(input.inventor),
        ipc: orUndefined(input.ipc),
        applicationDate: orUndefined(input.application_date),
        publicationDate: orUndefined(input.publication_date),
        ...rightFlags(input.right_type),
        numOfRows: input.num_of_rows,
        pageNo: input.page_no,
      });
      return searchEnvelope(
        "KIPO advanced patent/UM search",
        page,
        leanKiprisPatent,
        input.full,
        input.page_no,
        input.num_of_rows,
      );
    },
  );

  server.tool(
    {
      ...options,
      name: "get_kipo_patent",
      description: `Fetch a single KIPO patent / utility model by application number.\n\nAccepts a single number or a list (capped at ${LIST_CAP}). Iterates serially per ToS §11 quota awareness; the response stays a list envelope even for a single ID.\n\n${RELATED}`,
      input: z.object({
        application_number: numberInput(
          `KIPO application number (13 digits, e.g. 1020230012345), or a list (capped at ${LIST_CAP}) for portfolio workflows. Fan-out is serial — KIPRIS has no batch endpoint.`,
        ),
        full: fullField,
      }),
    },
    ({ application_number, full }) =>
      getKipoPatents(client, application_number, full),
  );

  server.tool(
    {
      ...options,
      name: "search_kipo_trademarks",
      description:
        "Search KIPO trademarks by free text.\n\nReturns a lean stub per hit by default; pass full=True for the full upstream row including Vienna codes and image URLs.",
      input: z.object({
        query: z
          .string()
          .min(1)
          .describe(
            "Free-text search string. Matches mark text, applicant, and classification codes across KIPRIS trademark rows.",
          ),
        num_of_rows: rowsField,
        page_no: pageField,
        full: fullField,
      }),
    },
    async (input) => {
      const page = await client.searchTrademarksWord(input.query, {
        numOfRows: input.num_of_rows,
        pageNo: input.page_no,
      });
      return searchEnvelope(
        `KIPO trademarks — \`${input.query}\``,
        page,
        leanKiprisTrademark,
        input.full,
        input.page_no,
        input.num_of_rows,
      );
    },
  );

  server.tool(
    {
      ...options,
      name: "search_kipo_trademarks_advanced",
      description:
        "Structured-field search over KIPO trademarks.\n\nEvery field is optional; KIPRIS ANDs whatever is provided.",
      input: z.object({
        title: optionalText("Match against mark text."),
        applicant: optionalText("Match against applicant name."),
        classification: optionalText("Nice goods/services class (e.g. '09')."),
        vienna_code: optionalText("Vienna figurative classification code."),
        application_date: optionalText(
          "Filing date filter (YYYYMMDD or range).",
        ),
        registration_date: optionalText(
          "Registration date filter (YYYYMMDD or range).",
        ),
        num_of_rows: rowsField,
        page_no: pageField,
        full: fullField,
      }),
    },
    async (input) => {
      const page = await client.searchTrademarksAdvanced({
        title: orUndefined(input.title),
        applicant: orUndefined(input.applicant),
        classification: orUndefined(input.classification),
        viennaCode: orUndefined(input.vienna_code),
        applicationDate: orUndefined(input.application_date),
        registrationDate: orUndefined(input.registration_date),
        numOfRows: input.num_of_rows,
        pageNo: input.page_no,
      });
      return searchEnvelope(
        "KIPO advanced trademark search",
        page,
        leanKiprisTrademark,
        input.full,
        input.page_no,
        input.num_of_rows,
      );
    },
  );

  server.tool(
    {
      ...options,
      name: "get_kipo_trademark",
      description: `Fetch a single KIPO trademark by application number.\n\nAccepts a single number or a list (capped at ${LIST_CAP}).`,
      input: z.object({
        application_number: numberInput(
          `KIPO trademark application number (13 digits), or a list (capped at ${LIST_CAP}). Fan-out is serial — KIPRIS has no batch endpoint.`,
        ),
        full: fullField,
      }),
    },
    ({ application_number, full }) =>
      fetchKipo(
        application_number,
        (n) => client.getTrademark(n),
        leanKiprisTrademark,
        full,
        { single: "trademark", plural: "trademarks" },
      ),
  );

  server.tool(
    {
      ...options,
      name: "search_kipo_designs",
      description:
        "Search KIPO designs by free text.\n\nReturns a lean stub per hit by default; pass full=True for the full upstream row. Lean output still keeps the drawing image URL.",
      input: z.object({
        query: z
          .string()
          .min(1)
          .describe(
            "Free-text search string. Matches article name, applicant, and classification codes across KIPRIS design rows.",
          ),
        num_of_rows: rowsField,
        page_no: pageField,
        full: fullField,
      }),
    },
    async (input) => {
      const page = await client.searchDesignsWord(input.query, {
        numOfRows: input.num_of_rows,
        pageNo: input.page_no,
      });
      return searchEnvelope(
        `KIPO designs — \`${input.query}\``,
        page,
        leanKiprisDesign,
        input.full,
        input.page_no,
        input.num_of_rows,
      );
    },
  );

  server.tool(
    {
      ...options,
      name: "search_kipo_designs_advanced",
      description:
        "Structured-field search over KIPO designs.\n\nEvery field is optional; KIPRIS ANDs whatever is provided.",
      input: z.object({
        article_name: optionalText(
          "Match against article name (the product the design covers).",
        ),
        applicant: optionalText("Match against applicant name."),
        loc_code: optionalText(
          "KIPO design classification code (upstream designMainClassification, e.g. 'M1110'). KIPRIS offers no Locarno filter.",
        ),
        application_date: optionalText(
          "Filing date filter (YYYYMMDD or range).",
        ),
        registration_date: optionalText(
          "Registration date filter (YYYYMMDD or range).",
        ),
        num_of_rows: rowsField,
        page_no: pageField,
        full: fullField,
      }),
    },
    async (input) => {
      const page = await client.searchDesignsAdvanced({
        articleName: orUndefined(input.article_name),
        applicant: orUndefined(input.applicant),
        designClassification: orUndefined(input.loc_code),
        applicationDate: orUndefined(input.application_date),
        registrationDate: orUndefined(input.registration_date),
        numOfRows: input.num_of_rows,
        pageNo: input.page_no,
      });
      return searchEnvelope(
        "KIPO advanced design search",
        page,
        leanKiprisDesign,
        input.full,
        input.page_no,
        input.num_of_rows,
      );
    },
  );

  server.tool(
    {
      ...options,
      name: "get_kipo_design",
      description: `Fetch a single KIPO design by application number.\n\nAccepts a single number or a list (capped at ${LIST_CAP}). Always includes the drawing image URL field.`,
      input: z.object({
        application_number: numberInput(
          `KIPO design application number (13 digits), or a list (capped at ${LIST_CAP}). Fan-out is serial — KIPRIS has no batch endpoint.`,
        ),
        full: fullField,
      }),
    },
    ({ application_number, full }) =>
      fetchKipo(
        application_number,
        (n) => client.getDesign(n),
        leanKiprisDesign,
        full,
        { single: "design", plural: "designs" },
      ),
  );
}

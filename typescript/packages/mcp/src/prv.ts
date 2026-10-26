import {
  PRV_API_HOST,
  PRV_MAX_PAGE_SIZE,
  PRV_SPC_ANNOUNCEMENTS,
  type Provenance,
  type PrvClient,
  PrvError,
  type PrvPage,
  type PrvRow,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailToolOptions,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

/** Python LIST_CAP and DEFAULT_CONCURRENCY for list-accepting fetch tools. */
const LIST_CAP = 50;
const CONCURRENCY = 5;

/** Lean records drop the base64 first-drawing bytes (about 32 KB) and keep its metadata. */
export function leanPrvPatent(record: PrvRow): PrvRow {
  const drawing = record.firstDrawing;
  if (!drawing || typeof drawing !== "object") return record;
  const { data: _bytes, ...metadata } = drawing as Record<string, unknown>;
  return { ...record, firstDrawing: metadata };
}

function summary(label: string, page: PrvPage, text: string | null) {
  const total = page.total_hits.toLocaleString("en-US");
  return text
    ? `PRV ${label} — ${total} total hits for \`${text}\`, returned ${page.rows.length}.`
    : `PRV ${label} — ${total} total hits, returned ${page.rows.length}.`;
}

const fetchedSchema = listEnvelopeSchema.extend({
  not_found: z.array(z.string()).optional(),
});
const pageField = z
  .number()
  .int()
  .min(0)
  .default(0)
  .describe("Zero-indexed page number.");
const pageSizeField = z
  .number()
  .int()
  .min(1)
  .max(PRV_MAX_PAGE_SIZE)
  .default(25)
  .describe(`Hits per page (capped at ${PRV_MAX_PAGE_SIZE}).`);
const orderField = z
  .enum(["DESC", "ASC"])
  .default("DESC")
  .describe("'DESC' (default) or 'ASC'.");
const fullField = (description: string) =>
  z.boolean().default(false).describe(description);
const optionalText = (description: string) =>
  z.string().nullable().default(null).describe(description);

/** The five Python PRV tools, with the same names and parameters. PRV needs no credentials. */
export function registerPrvTools(
  server: FastMCP,
  client: PrvClient,
  auth?: AuthCheck,
) {
  const options = {
    output: fetchedSchema,
    outputSchema: objectOutputSchema(fetchedSchema),
    annotations: detailToolOptions().annotations,
    ...(auth ? { auth } : {}),
  };
  const page = (label: string, result: PrvPage, text: string | null) => ({
    ...listEnvelope(
      summary(label, result, text),
      result.rows,
      result.provenance,
    ),
    more_available: result.more_available,
  });

  server.tool(
    {
      ...options,
      name: "search_prv_patents",
      description:
        "Search Sweden national patent applications and grants at PRV.\n\nWraps `POST patents-search-api.prv.se/searchpatent/patentsimplesearch/`. Covers SE-national filings (`applicationType=NAT`); EP-route validations also appear with `applicationType=EP`. Status codes are numeric on this surface — full text resolves on `get_prv_patent`.\n\nRelated tools: `get_prv_patent` for the full register record with bilingual status text and gazette announcements; `search_epo_patents` for SE-validated EP patents at INPADOC fidelity.",
      input: z.object({
        text: optionalText(
          "Free-text query — matches applicant, inventor, title, and application number. Example: 'Volvo'.",
        ),
        page: pageField,
        page_size: pageSizeField,
        sort_column: z
          .string()
          .default("filingDate")
          .describe(
            "Sort key: 'filingDate' (default), 'publicationDate', 'grantDate', 'title'.",
          ),
        sort_order: orderField,
        full: fullField(
          "Accepted for compatibility; PRV search rows are already minimal, so lean and full are identical.",
        ),
      }),
    },
    async (input) =>
      page(
        "patents",
        await client.searchPatents({
          text: input.text,
          page: input.page,
          pageSize: input.page_size,
          sortColumn: input.sort_column,
          sortOrder: input.sort_order,
        }),
        input.text,
      ),
  );

  server.tool(
    {
      ...options,
      name: "get_prv_patent",
      description:
        "Fetch one or more Sweden patent register records from PRV.\n\nWraps `GET api.prv.se/patents/applications/{number}`. Returns the full register entry — bilingual status text (Sv/En), prosecution timeline (`registryEntries{Sv,En}`), gazette and electronic announcements, next annuity date and publication URLs. The first-drawing image bytes are dropped by default to keep responses under context budget. A number PRV does not know is listed in `not_found`.\n\nRelated tools: `search_prv_patents` to find candidate application numbers; `get_epo_biblio` for SE-validated EP patents at INPADOC fidelity.",
      input: z.object({
        application_number: z
          .union([
            z.string().min(1).max(40),
            z.array(z.string().max(40)).min(1).max(LIST_CAP),
          ])
          .describe(
            "PRV application number: national 'SE2615555-6' (also '2615555-6' or '26155556') or EP route 'EP00108480.5'. Pass a list for portfolio fan-outs.",
          ),
        application_type: z
          .enum(["NAT", "EP", "PCT"])
          .default("NAT")
          .describe(
            "Application route: 'NAT' (default, national) or 'EP'. PRV goes by the number's prefix; this only supplies 'EP' to an EP number given without one.",
          ),
        full: fullField(
          "When False (default), drops ~32 KB of base64-encoded first-drawing image bytes. When True, returns the upstream-shaped record.",
        ),
      }),
    },
    async ({ application_number, application_type, full }) => {
      const numbers = (
        typeof application_number === "string"
          ? [application_number]
          : application_number
      )
        .map((n) => n.trim())
        .filter(Boolean)
        .map((n) =>
          application_type === "EP" && /^\d/.test(n) ? `EP${n}` : n,
        );
      if (!numbers.length)
        throw new Error("Provide at least one PRV application number.");
      const single = typeof application_number === "string";
      const results: (PrvRow | null)[] = new Array(numbers.length);
      let first: Provenance | undefined;
      let next = 0;
      await Promise.all(
        Array.from(
          { length: Math.min(CONCURRENCY, numbers.length) },
          async () => {
            while (next < numbers.length) {
              const index = next++;
              try {
                const record = await client.getPatent(numbers[index] as string);
                first ??= record.provenance;
                results[index] = record.data;
              } catch (error) {
                // Python's fetch_many: a single lookup raises; a list collects not_found.
                if (
                  single ||
                  !(error instanceof PrvError && error.code === "NOT_FOUND")
                )
                  throw error;
                results[index] = null;
              }
            }
          },
        ),
      );
      const notFound = numbers.filter((_, i) => !results[i]);
      const items = results
        .filter((row): row is PrvRow => !!row)
        .map((row) => (full ? row : leanPrvPatent(row)));
      const provenance: Provenance = {
        ...(first ?? {
          source_name: "Patent- och registreringsverket (PRV, Sweden)",
          retrieved_at: new Date().toISOString(),
          cache_hit: false,
          source_url: "",
        }),
        source_url:
          numbers.length === 1 && first
            ? first.source_url
            : `${PRV_API_HOST}/patents/applications/`,
      };
      return {
        ...listEnvelope(
          numbers.length === 1 && items.length
            ? `PRV patent records — 1 record for ${numbers[0]}.`
            : `Fetched ${items.length} of ${numbers.length} PRV patent records.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`,
          items,
          provenance,
        ),
        more_available: false,
        not_found: notFound,
      };
    },
  );

  server.tool(
    {
      ...options,
      name: "search_prv_trademarks",
      description:
        "Search Sweden national trademarks at PRV.\n\nWraps `POST dv-search-api.prv.se/searchtrademark/tmsimplesearch/`. Returns biblio rows with Nice classes, mark feature (Word / Figurative / etc.), and bilingual status. `dossierTypeEn` / `dossierTypeSv` discriminates national filings from Madrid IRs designating Sweden.\n\nRelated tools: EUIPO trademark search for EU-wide marks covering Sweden; Madrid IR coverage requires WIPO Madrid Monitor.",
      input: z.object({
        text: optionalText(
          "Free-text query — matches mark text, applicant, and representative. Example: 'IKEA'.",
        ),
        page: pageField,
        page_size: pageSizeField,
        sort_column: z
          .string()
          .default("filingDate")
          .describe(
            "Sort key: 'filingDate' (default), 'expiryDate', 'markSpecification'.",
          ),
        sort_order: orderField,
        full: fullField(
          "Accepted for compatibility; rows are returned as PRV sends them.",
        ),
      }),
    },
    async (input) =>
      page(
        "trademarks",
        await client.searchTrademarks({
          text: input.text,
          page: input.page,
          pageSize: input.page_size,
          sortColumn: input.sort_column,
          sortOrder: input.sort_order,
        }),
        input.text,
      ),
  );

  server.tool(
    {
      ...options,
      name: "search_prv_designs",
      description:
        "Search Sweden national design (mönster) registrations at PRV.\n\nWraps `POST dv-search-api.prv.se/searchdesign/dssimplesearch/`. Each row represents one design within a multi-design application — `designNumber` and `designsTotal` indicate position. Locarno classes appear in `classes`.\n\nRelated tools: EUIPO registered EU designs (cover SE transitively); WIPO Hague IR coverage is not in this catalog.",
      input: z.object({
        text: optionalText(
          "Free-text query — matches product title, applicant, and representative. Example: 'stol' (Swedish for 'chair').",
        ),
        page: pageField,
        page_size: pageSizeField,
        sort_column: z
          .string()
          .default("filingDate")
          .describe(
            "Sort key: 'filingDate' (default), 'expiryDate', 'productTitle'.",
          ),
        sort_order: orderField,
        full: fullField(
          "Accepted for compatibility; rows are returned as PRV sends them.",
        ),
      }),
    },
    async (input) =>
      page(
        "designs",
        await client.searchDesigns({
          text: input.text,
          page: input.page,
          pageSize: input.page_size,
          sortColumn: input.sort_column,
          sortOrder: input.sort_order,
        }),
        input.text,
      ),
  );

  server.tool(
    {
      ...options,
      name: "search_prv_spcs",
      description:
        "Search Sweden Supplementary Protection Certificates (SPCs) at PRV.\n\nWraps `POST patents-search-api.prv.se/searchpatentspc/patentsearchspc/`. SPCs are patent-term extensions for pharmaceuticals and plant-protection products under EU Regulations 469/2009 and 1610/96. At least one filter is required. Substance names are as PRV records them, often in Swedish (e.g. 'naproxen och esomeprazol').\n\nEach row carries the base patent application number, the SPC's own application + publication numbers, the substance, and the SPC term (`validFromDate` / `validUntilDate`).\n\nRelated tools: `search_prv_patents` for the base patents the SPCs extend; `get_prv_patent` for the full base-patent register record.",
      input: z.object({
        substance_product: optionalText(
          "Substance or product name (active pharmaceutical ingredient / agrochemical). Example: 'naproxen'.",
        ),
        applicants: optionalText("SPC applicant name. Example: 'AstraZeneca'."),
        application_number_spc: optionalText(
          "SPC's own application number (e.g. '1190011-5').",
        ),
        base_patent_number: optionalText(
          "Base patent application number (the patent the SPC extends, typically EP-route, e.g. 'EP00108480.5').",
        ),
        marketing_authorization_number: optionalText(
          "First marketing authorization (MA) number.",
        ),
        announcement: z
          .enum(PRV_SPC_ANNOUNCEMENTS)
          .nullable()
          .default(null)
          .describe("Gazette announcement type (Swedish, exact)."),
        match_type: z
          .enum(["CONTAINS", "STARTS_WITH", "EXACT"])
          .default("CONTAINS")
          .describe(
            "Match strategy applied to every populated text filter: 'CONTAINS' (default), 'STARTS_WITH', or 'EXACT'.",
          ),
        page: pageField,
        page_size: pageSizeField,
        full: fullField(
          "Accepted for compatibility; rows are returned as PRV sends them.",
        ),
      }),
    },
    async (input) => {
      const result = await client.searchSpcs({
        substance: input.substance_product,
        applicants: input.applicants,
        applicationNumberSpc: input.application_number_spc,
        basePatentNumber: input.base_patent_number,
        marketingAuthorizationNumber: input.marketing_authorization_number,
        announcement: input.announcement,
        matchType: input.match_type,
        page: input.page,
        pageSize: input.page_size,
      });
      const hint =
        input.substance_product ??
        input.applicants ??
        input.application_number_spc ??
        input.base_patent_number ??
        input.marketing_authorization_number ??
        input.announcement;
      return page("SPCs", result, hint);
    },
  );
}

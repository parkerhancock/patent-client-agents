import {
  PRH_PATENT_HOST,
  PRH_PATENT_TYPES,
  PRH_RESULT_CAP,
  type PrhClient,
  PrhError,
  type PrhRow,
  type PrhSearch,
  type Provenance,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

/** Python LIST_CAP and DEFAULT_CONCURRENCY for list-accepting fetch tools. */
const LIST_CAP = 50;
const CONCURRENCY = 5;
const DEFAULT_LIMIT = 25;
const MAX_LIMIT = 200;

/** Python's lean projections. */
export function leanPrhDossier(row: PrhRow): PrhRow {
  const { thumbnailUrl: _t, largeThumbnailUrl: _l, ordinal: _o, ...rest } = row;
  return rest;
}
export function leanPrhPatentRow(row: PrhRow): PrhRow {
  const { ordinal: _o, ...rest } = row;
  return rest;
}
export function leanPrhPatent(record: PrhRow): PrhRow {
  const { documents: _d, paymentDetails: _p, events: _e, ...rest } = record;
  return rest;
}

const fetchedSchema = listEnvelopeSchema.extend({
  not_found: z.array(z.string()).optional(),
});
const text = (description: string) =>
  z.string().nullable().default(null).describe(description);
const date = (description: string) =>
  z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .nullable()
    .default(null)
    .describe(`${description}, YYYY-MM-DD.`);
const fullField = z
  .boolean()
  .default(false)
  .describe("Lean (default) vs upstream-shaped rows.");
const window = {
  limit: z
    .number()
    .int()
    .min(1)
    .max(MAX_LIMIT)
    .default(DEFAULT_LIMIT)
    .describe(
      `Rows to return (default ${DEFAULT_LIMIT}, at most ${MAX_LIMIT}). PRH sends every match at once, up to ${PRH_RESULT_CAP.toLocaleString("en-US")}; this pages through them.`,
    ),
  offset: z.number().int().min(0).default(0).describe("Rows to skip."),
};
const omitNull = <T extends Record<string, unknown>>(value: T) =>
  Object.fromEntries(Object.entries(value).filter(([, v]) => v !== null)) as {
    [K in keyof T]?: Exclude<T[K], null>;
  };

/**
 * PRH sends every match in one response; Python returned them all (491
 * design rows, 527 KB, for "tuoli"). The tools return a window of them.
 */
function windowed(
  label: string,
  result: PrhSearch,
  hint: string | null | undefined,
  input: { limit: number; offset: number; full: boolean },
  lean: (row: PrhRow) => PrhRow,
) {
  const rows = result.rows.slice(input.offset, input.offset + input.limit);
  const items = input.full ? rows : rows.map(lean);
  const total = result.total_results.toLocaleString("en-US");
  const shown = rows.length
    ? `rows ${input.offset + 1}-${input.offset + rows.length}`
    : "no rows";
  const cap = result.capped
    ? ` PRH returns only the first ${result.rows.length.toLocaleString("en-US")}; narrow the query for the rest.`
    : "";
  return {
    ...listEnvelope(
      `PRH ${label} — ${total} total hits${hint ? ` for \`${hint}\`` : ""}, returned ${shown}.${cap}`,
      items,
      result.provenance,
    ),
    more_available: input.offset + rows.length < result.total_results,
  };
}

const IMAGE_EXTENSIONS: Record<string, string> = {
  "image/gif": "gif",
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
};

/** The seven Python PRH tools, with the same names and parameters. PRH needs no credentials. */
export function registerPrhTools(
  server: FastMCP,
  client: PrhClient,
  auth?: AuthCheck,
) {
  const options = {
    output: fetchedSchema,
    outputSchema: objectOutputSchema(fetchedSchema),
    annotations: detailToolOptions().annotations,
    ...(auth ? { auth } : {}),
  };
  const detail = detailToolOptions(auth);

  server.tool(
    {
      ...options,
      name: "search_prh_patents",
      description:
        "Search Finland national patents, utility models, SPCs, and EP-FI validations at PRH.\n\nWraps `POST patenttitietopalvelu.prh.fi/nis-api-gateway-pat/patent`. The upstream form takes 30 fields; the most useful filters are exposed here directly. The status, type and publication inclusion lists are supplied automatically with every value PRH's own app sends, so a caller setting only `applicant` gets every match. PRH returns at most 3,000 rows; use `limit` and `offset` to page through them.\n\nRelated tools: `get_prh_patent` for the full register record with prosecution events and named examiner; `search_epo_patents` for FI-validated EP patents at INPADOC fidelity.",
      input: z.object({
        applicant: text(
          "Applicant name filter (substring match). Example: 'Nokia'.",
        ),
        inventor: text("Inventor name filter."),
        patent_title: text("Title text filter (any language)."),
        application_number: text(
          "Exact PRH application number, e.g. '20245203'.",
        ),
        registration_number: text("Exact PRH registration (patent) number."),
        ipc_classification: text("IPC class filter, e.g. 'H04W'."),
        cpc_classification: text("CPC class filter."),
        filing_start_date: date("Earliest filing date"),
        filing_end_date: date("Latest filing date"),
        patent_types: z
          .array(z.enum(PRH_PATENT_TYPES))
          .min(1)
          .nullable()
          .default(null)
          .describe(
            "Filter by patent route: 'PatentDossier' (national), 'PatentDossierUtilityModel', 'PatentEurope' (EP-FI), 'Spc'. Default returns all four.",
          ),
        ...window,
        full: fullField,
      }),
    },
    async (input) => {
      const result = await client.searchPatents(
        omitNull({
          applicant: input.applicant,
          inventor: input.inventor,
          patentTitle: input.patent_title,
          applicationNumber: input.application_number,
          registrationNumber: input.registration_number,
          ipcClassification: input.ipc_classification,
          cpcClassification: input.cpc_classification,
          filingStartDate: input.filing_start_date,
          filingEndDate: input.filing_end_date,
          patentTypes: input.patent_types,
        }),
      );
      const hint =
        input.applicant ??
        input.inventor ??
        input.patent_title ??
        input.application_number;
      return windowed("patents", result, hint, input, leanPrhPatentRow);
    },
  );

  server.tool(
    {
      ...options,
      name: "get_prh_patent",
      description:
        "Fetch one or more Finland patent register records from PRH.\n\nWraps `GET patenttitietopalvelu.prh.fi/nis-api-gateway-pat/patent/{n}`. Returns the full register entry with titles and abstracts in FI/SV/EN, prosecution events, file-history pointers, named examiner, payment timeline, and SPC authorizations. The lean default drops the file-history list, payment timeline and events. A number PRH does not know is listed in `not_found`.\n\nRelated tools: `search_prh_patents` to find candidate application numbers; `get_epo_biblio` for FI-validated EP patents at INPADOC fidelity.",
      input: z.object({
        application_number: z
          .union([
            z.string().min(1).max(40),
            z.array(z.string().max(40)).min(1).max(LIST_CAP),
          ])
          .describe(
            "PRH application number(s), e.g. '20245203'. Pass a list for portfolio fan-outs.",
          ),
        full: z
          .boolean()
          .default(false)
          .describe(
            "When False (default), drops the file-history pointer list, payment timeline, and raw events array to keep responses lean.",
          ),
      }),
    },
    async ({ application_number, full }) => {
      const numbers = (
        typeof application_number === "string"
          ? [application_number]
          : application_number
      )
        .map((n) => n.trim())
        .filter(Boolean);
      if (!numbers.length)
        throw new Error("Provide at least one PRH application number.");
      const single = typeof application_number === "string";
      const results: (PrhRow | null)[] = new Array(numbers.length);
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
                  !(error instanceof PrhError && error.code === "NOT_FOUND")
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
        .filter((row): row is PrhRow => !!row)
        .map((row) => (full ? row : leanPrhPatent(row)));
      const base = `${PRH_PATENT_HOST}/nis-api-gateway-pat/patent/`;
      const provenance: Provenance = first
        ? {
            ...first,
            source_url: numbers.length === 1 ? first.source_url : base,
          }
        : {
            source_url: base,
            source_name: "Patentti- ja rekisterihallitus (PRH, Finland)",
            retrieved_at: new Date().toISOString(),
            cache_hit: false,
          };
      return {
        ...listEnvelope(
          numbers.length === 1 && items.length
            ? `PRH patent records — 1 record for ${numbers[0]}.`
            : `Fetched ${items.length} of ${numbers.length} PRH patent records.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`,
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
      name: "search_prh_trademarks",
      description:
        "Search Finland national trademarks at PRH.\n\nWraps `POST tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/trademark`. Covers ~283k national trademarks back to 1891. Mark images are reachable via `download_prh_trademark_image` with the row's application and registration numbers. PRH returns at most 3,000 rows; use `limit` and `offset` to page through them.\n\nRelated tools: `search_prh_well_known_trademarks` for the well-known marks register (TMR); EUIPO trademark search for EU-wide trademarks covering Finland.",
      input: z.object({
        trademark_word: text(
          "Mark text filter (substring match). Example: 'SISU'.",
        ),
        applicant_name: text("Applicant name filter."),
        representative_name: text("Representative / agent name filter."),
        business_id: text("Finnish Y-tunnus / Business ID filter (NNNNNNN-N)."),
        application_number: text("Exact application number."),
        registration_number: text("Exact registration number."),
        goods_and_services_class_number: text("Nice class filter, e.g. '9'."),
        application_start_date: date("Earliest application date"),
        application_end_date: date("Latest application date"),
        ...window,
        full: fullField,
      }),
    },
    async (input) => {
      const result = await client.searchTrademarks(
        omitNull({
          trademarkWord: input.trademark_word,
          applicantName: input.applicant_name,
          representativeName: input.representative_name,
          businessID: input.business_id,
          applicationNumber: input.application_number,
          registrationNumber: input.registration_number,
          goodsAndServicesClassNumber: input.goods_and_services_class_number,
          applicationStartDate: input.application_start_date,
          applicationEndDate: input.application_end_date,
        }),
      );
      const hint =
        input.trademark_word ??
        input.applicant_name ??
        input.application_number;
      return windowed("trademarks", result, hint, input, leanPrhDossier);
    },
  );

  server.tool(
    {
      ...options,
      name: "search_prh_well_known_trademarks",
      description:
        "Search the Finnish well-known trademarks register (TMR) at PRH.\n\nWraps `POST tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/tmr`. The TMR records marks recognized as well-known in Finland under §6 of the Trade Marks Act (544/2019), about 111 records; each carries a free-text `targetGroup` audience description (e.g. '15-44-vuotiaat suomalaiset' for the TAFFEL snack mark).\n\nRelated tools: `search_prh_trademarks` for the regular national trademark register.",
      input: z.object({
        trademark_word: text("Mark text filter."),
        applicant_name: text("Applicant name filter."),
        ...window,
        full: fullField,
      }),
    },
    async (input) => {
      const result = await client.searchWellKnownTrademarks(
        omitNull({
          trademarkWord: input.trademark_word,
          applicantName: input.applicant_name,
        }),
      );
      return windowed(
        "well-known trademarks (TMR)",
        result,
        input.trademark_word ?? input.applicant_name,
        input,
        leanPrhDossier,
      );
    },
  );

  server.tool(
    {
      ...options,
      name: "search_prh_designs",
      description:
        "Search Finland national design (malli) registrations at PRH.\n\nWraps `POST mallioikeustietopalvelu.prh.fi/nis-api-gateway/design`. Covers ~34k national designs back to 1971. Each dossier may carry multiple `designs[]` embodiments with Locarno classifications and image ids for `download_prh_design_image`. PRH returns at most 3,000 rows; use `limit` and `offset` to page through them.\n\nRelated tools: EUIPO registered EU designs (cover FI transitively); WIPO Hague IR coverage is not in this catalog.",
      input: z.object({
        product_title: text("Product title filter."),
        applicant_name: text("Applicant name filter."),
        designer_name: text("Designer name filter."),
        class_number: text("Locarno class filter, e.g. '08'."),
        application_number: text("Exact application number."),
        registration_number: text("Exact registration number."),
        ...window,
        full: fullField,
      }),
    },
    async (input) => {
      const result = await client.searchDesigns(
        omitNull({
          productTitle: input.product_title,
          applicantName: input.applicant_name,
          designerName: input.designer_name,
          classNumber: input.class_number,
          applicationNumber: input.application_number,
          registrationNumber: input.registration_number,
        }),
      );
      const hint =
        input.product_title ?? input.applicant_name ?? input.designer_name;
      return windowed("designs", result, hint, input, leanPrhDossier);
    },
  );

  server.tool(
    {
      ...detail,
      name: "download_prh_trademark_image",
      description:
        "Download a Finland national trademark mark image from PRH.\n\nWraps `GET tavaramerkkitietopalvelu.prh.fi/opendata/trademark/{variant}/...`. Returns a single-use download link (hosted) or a local file path (stdio) with filename, content type and size.\n\nUse the `applicationNumber` and `registrationNumber` of a `search_prh_trademarks` row (its `imageUrl` path carries both).\n\nRelated tools: `search_prh_trademarks`, `search_prh_well_known_trademarks`, `download_prh_design_image`.",
      input: z.object({
        application_number: z
          .string()
          .trim()
          .min(1)
          .max(40)
          .describe("PRH trademark application number, e.g. 'T196300976'."),
        registration_number: text(
          "PRH trademark registration number, e.g. '43707'. Omit for well-known TMR rows (registered without a separate regno).",
        ),
        variant: z
          .enum(["image", "thumbnail", "thumbnail/large"])
          .default("image")
          .describe(
            "Image variant: 'image' (default, full-size), 'thumbnail', 'thumbnail/large'.",
          ),
      }),
    },
    async ({ application_number, registration_number, variant }) => {
      const image = await client.downloadTrademarkImage(
        application_number,
        registration_number,
        variant,
      );
      const label = [application_number, registration_number]
        .filter(Boolean)
        .join("-");
      return downloadResult(
        image.data,
        `prh-tm-${label}-${variant.replace("/", "_")}.${IMAGE_EXTENSIONS[image.content_type] ?? "bin"}`,
        image.content_type,
        image.provenance,
      );
    },
  );

  server.tool(
    {
      ...detail,
      name: "download_prh_design_image",
      description:
        "Download a Finland national design embodiment image from PRH.\n\nWraps `GET mallioikeustietopalvelu.prh.fi/opendata/design/{variant}/{image_id}`. Returns a single-use download link (hosted) or a local file path (stdio) with filename, content type and size.\n\nThe image id ends the `dominantViewImageUrl` of a `search_prh_designs` embodiment, e.g. 'M19710035.1.1'.\n\nRelated tools: `search_prh_designs`, `download_prh_trademark_image`.",
      input: z.object({
        image_id: z
          .string()
          .trim()
          .regex(/^[A-Za-z0-9.]+$/)
          .describe(
            "Per-embodiment design image identifier, e.g. 'M19710035.1.1'.",
          ),
        variant: z
          .enum(["image", "thumbnail", "thumbnail/medium"])
          .default("image")
          .describe(
            "Image variant: 'image' (default, full-size), 'thumbnail', 'thumbnail/medium'.",
          ),
      }),
    },
    async ({ image_id, variant }) => {
      const image = await client.downloadDesignImage(image_id, variant);
      return downloadResult(
        image.data,
        `prh-design-${image_id}-${variant.replace("/", "_")}.${IMAGE_EXTENSIONS[image.content_type] ?? "bin"}`,
        image.content_type,
        image.provenance,
      );
    },
  );
}

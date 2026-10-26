import {
  TIPO_ATTRIBUTION,
  TIPO_BASE_URL,
  TIPO_DEFAULT_TOP,
  TIPO_MAX_TOP,
  type TipoClient,
  type TipoEndpoint,
  type TipoFilters,
  type TipoPage,
  type TipoRow,
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

/**
 * Lean rows drop nulls, empty strings and ftps:// pointers (TIPO's XML
 * mirror, which an agent cannot fetch). Python's lean list named keys
 * (applicant-name-e, xml-detail-url, ...) that TIPO rows never carry.
 */
export function leanTipo(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(leanTipo);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .filter(
          ([, item]) =>
            item !== null &&
            item !== "" &&
            !(typeof item === "string" && item.startsWith("ftps://")),
        )
        .map(([key, item]) => [key, leanTipo(item)]),
    );
  return value;
}
const project = (rows: TipoRow[], full: boolean) =>
  (full ? rows : rows.map(leanTipo)) as Record<string, unknown>[];

const han = /\p{Script=Han}/u;
/** Applicant filters are per script: applnamec for Chinese names, applnamee otherwise. */
const applicantFilter = (name: string | null) =>
  name ? (han.test(name) ? { applnamec: name } : { applnamee: name }) : {};

function ids(value: string | string[]): string[] {
  const list = (typeof value === "string" ? [value] : value)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!list.length)
    throw new Error("Provide at least one TIPO application number.");
  if (list.length > LIST_CAP)
    throw new Error(
      `Too many TIPO application numbers: ${list.length} (limit ${LIST_CAP} per call). Split the list into batches of ${LIST_CAP} or fewer.`,
    );
  return list;
}
/** Bounded concurrency in input order. */
async function each<T>(numbers: string[], run: (n: string) => Promise<T>) {
  const results: T[] = new Array(numbers.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, numbers.length) }, async () => {
      while (next < numbers.length) {
        const index = next++;
        results[index] = await run(numbers[index] as string);
      }
    }),
  );
  return results;
}
function rowsSummary(
  label: string,
  unit: string,
  count: number,
  numbers: string[],
  notFound: string[],
) {
  if (numbers.length === 1)
    return `TIPO ${label} — ${count} ${unit} 1 application: ${numbers[0]}.`;
  const found = numbers.length - notFound.length;
  return `Fetched ${found} of ${numbers.length} applications for TIPO ${label}.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""} ${count} ${unit.split(" ")[0]}.`;
}
const endpointProvenance = (page: TipoPage, numbers: string[], path: string) =>
  numbers.length === 1
    ? page.provenance
    : { ...page.provenance, source_url: `${TIPO_BASE_URL}/${path}` };

const envelopeSchema = listEnvelopeSchema.extend({
  attribution: z.string(),
  not_found: z.array(z.string()).optional(),
});
const numberInput = (description: string) =>
  z
    .union([
      z.string().min(1).max(40),
      // Blank entries are dropped, as Python's as_id_list does.
      z.array(z.string().max(40)).min(1).max(LIST_CAP),
    ])
    .describe(description);
const fullField = z
  .boolean()
  .default(false)
  .describe(
    "When False (default), drops null and empty fields and ftps:// XML pointers. When True, returns upstream-shaped rows.",
  );
const dateField = (description: string) =>
  z
    .string()
    .nullable()
    .default(null)
    .describe(`${description} (YYYY-MM-DD or YYYY/MM/DD).`);
const topField = z
  .number()
  .int()
  .min(1)
  .max(TIPO_MAX_TOP)
  .default(TIPO_DEFAULT_TOP)
  .describe("Page size (capped at 6000).");
const skipField = z
  .number()
  .int()
  .min(0)
  .default(0)
  .describe("Offset into the result set.");

const PATENT_REGISTERS = {
  rights: "PatentRights",
  publications: "PatentPub",
  applications: "PatentAppl",
} as const satisfies Record<string, TipoEndpoint>;
const CLASSES: Record<number, string> = {
  1: "invention",
  2: "utility model",
  3: "design",
};

/**
 * The fourteen Python TIPO tools, with the same names and parameters.
 * Register them only when a client exists (TIPO_API_KEY is set).
 */
export function registerTipoTools(
  server: FastMCP,
  client: TipoClient,
  auth?: AuthCheck,
) {
  const options = {
    output: envelopeSchema,
    outputSchema: objectOutputSchema(envelopeSchema),
    annotations: detailToolOptions().annotations,
    ...(auth ? { auth } : {}),
  };
  const envelope = (
    summary: string,
    items: Record<string, unknown>[],
    page: TipoPage,
    extra: { more_available?: boolean; not_found?: string[] } = {},
  ) => ({
    ...listEnvelope(summary, items, page.provenance),
    more_available: extra.more_available ?? false,
    ...(extra.not_found ? { not_found: extra.not_found } : {}),
    attribution: TIPO_ATTRIBUTION,
  });

  /** One endpoint per number; `notFoundWhenEmpty` for record endpoints, not facets. */
  const byNumber = async (
    endpoint: TipoEndpoint,
    value: string | string[],
    full: boolean,
    label: string,
    notFoundWhenEmpty: boolean,
  ) => {
    const numbers = ids(value);
    const pages = await each(numbers, (n) =>
      client.getByApplicationNumber(endpoint, n),
    );
    const notFound = numbers.filter(
      (_, i) => notFoundWhenEmpty && !pages[i]?.rows.length,
    );
    const items = project(
      pages.flatMap((page) => page.rows),
      full,
    );
    const first = pages[0] as TipoPage;
    return {
      ...envelope(
        rowsSummary(label, "rows for", items.length, numbers, notFound),
        items,
        { ...first, provenance: endpointProvenance(first, numbers, endpoint) },
      ),
      not_found: notFound,
    };
  };
  /** Several queries per number, merged as events tagged with event_type. */
  const events = async (
    value: string | string[],
    full: boolean,
    label: string,
    path: string,
    queries: (n: string) => Promise<[string, TipoPage][]>,
  ) => {
    const numbers = ids(value);
    const results = await each(numbers, queries);
    const items: Record<string, unknown>[] = [];
    let first: TipoPage | undefined;
    results.forEach((pages, index) => {
      const seen = new Set<string>();
      for (const [eventType, page] of pages) {
        first ??= page;
        for (const row of page.rows) {
          // The same row can answer several queries; "-sequence" is only its
          // position on that page.
          const { "-sequence": _position, ...identity } = row;
          const key = `${eventType}\0${JSON.stringify(identity)}`;
          if (seen.has(key)) continue;
          seen.add(key);
          items.push({
            event_type: eventType,
            appl_no: numbers[index],
            ...((full ? row : leanTipo(row)) as Record<string, unknown>),
          });
        }
      }
    });
    const page = first as TipoPage;
    return {
      ...envelope(
        rowsSummary(label, "events across", items.length, numbers, []),
        items,
        {
          ...page,
          provenance: {
            ...page.provenance,
            source_url: `${TIPO_BASE_URL}/${path}`,
          },
        },
      ),
      not_found: [],
    };
  };

  server.tool(
    {
      ...options,
      name: "search_tipo_patents",
      description:
        "Search Taiwan patents / utility models / designs at TIPO.\n\nBibliographic only (no claims, abstracts, or figures via the API). `register` picks the dataset: 'rights' (default; granted patents of all three classes, with title, parties and status), 'publications' (published invention applications, with title and parties), or 'applications' (every application, filing data and IPC/Locarno only — title and applicant filters are not available there). Use `applclass` to scope to inventions (1), utility models (2), or designs (3).\n\nRelated tools: `get_tipo_patent` for one application at a time; `search_epo_patents` does NOT cover TW (Taiwan is not an INPADOC contributor) — TIPO is the only upstream substitute.",
      input: z.object({
        q: z
          .string()
          .nullable()
          .default(null)
          .describe(
            "Words in the patent title (Chinese or English), e.g. '半導體' or 'heater'.",
          ),
        applclass: z
          .union([z.literal(1), z.literal(2), z.literal(3)])
          .nullable()
          .default(null)
          .describe(
            "Application class: 1 = invention patent, 2 = utility model, 3 = design. Omit to span all three.",
          ),
        appl_date_from: dateField("Earliest application date"),
        appl_date_to: dateField("Latest application date"),
        applicant: z
          .string()
          .nullable()
          .default(null)
          .describe(
            "Applicant name filter: Chinese names match the Chinese name, others the English name.",
          ),
        register: z
          .enum(["rights", "publications", "applications"])
          .default("rights")
          .describe("Dataset to search; see the tool description."),
        top: topField,
        skip: skipField,
        full: fullField,
      }),
    },
    async (input) => {
      const endpoint = PATENT_REGISTERS[input.register];
      if (input.register === "applications" && (input.q || input.applicant))
        throw new Error(
          "TIPO's applications dataset has no title or applicant filter; use register='rights' or 'publications'.",
        );
      if (
        input.register === "publications" &&
        input.applclass &&
        input.applclass !== 1
      )
        throw new Error(
          "TIPO's publications dataset holds invention applications only (applclass 1).",
        );
      const filters: TipoFilters = {
        ...(input.q ? { patentname: input.q } : {}),
        ...applicantFilter(input.applicant),
        ...(input.register === "publications"
          ? {}
          : { applclass: input.applclass }),
        applbdate: input.appl_date_from,
        appledate: input.appl_date_to,
      };
      const page = await client.query(endpoint, {
        filters,
        top: input.top,
        skip: input.skip,
      });
      const items = project(page.rows, input.full);
      const parts = [
        `TIPO patents (${input.register}) — ${items.length} of ${page.total_count} hits`,
        input.q ? ` for \`${input.q}\`` : "",
        input.applicant ? ` by ${input.applicant}` : "",
        input.applclass ? ` (${CLASSES[input.applclass]})` : "",
      ];
      return envelope(`${parts.join("")}.`, items, page, {
        more_available: page.more_available,
      });
    },
  );

  const patentNumber = numberInput(
    "TW patent / UM / design application number (e.g. '113105712'), or a list for portfolio fan-outs.",
  );
  const fetchTool = (
    name: string,
    description: string,
    endpoint: TipoEndpoint,
    label: string,
    notFoundWhenEmpty: boolean,
    numberDescription = patentNumber,
  ) =>
    server.tool(
      {
        ...options,
        name,
        description,
        input: z.object({ appl_no: numberDescription, full: fullField }),
      },
      ({ appl_no, full }) =>
        byNumber(endpoint, appl_no, full, label, notFoundWhenEmpty),
    );

  fetchTool(
    "get_tipo_patent",
    "Fetch one or more Taiwan patent application biblio records.\n\nWraps `/PatentAppl?applno=...`. Returns the application-side bibliographic record (filing no, filing date, first applicant's country, IPC + Locarno classifications, publication flag). For grant status, use `get_tipo_patent_rights`. A number with no record is listed in `not_found`.\n\nRelated tools: `search_tipo_patents`; no upstream substitute available (Taiwan is not in INPADOC, so `get_epo_biblio` does not cover TW).",
    "PatentAppl",
    "patent applications",
    true,
  );
  fetchTool(
    "get_tipo_patent_publication",
    "Fetch Taiwan patent publication records (laid-open invention applications).\n\nWraps `/PatentPub`. Carries the publication reference, the application reference, title, parties, and IPC classifications.\n\nRelated tools: `get_tipo_patent` for the application-side record; no upstream substitute (TW not in INPADOC).",
    "PatentPub",
    "patent publications",
    false,
  );
  fetchTool(
    "get_tipo_patent_rights",
    "Fetch Taiwan patent grant + status records (with `twins-flag`).\n\nWraps `/PatentRights`. Carries the grant, term, annuity-paid-through date, status flags (licence, pledge, transfer, opposition, invalidation ...), parties, and the TW-specific `twins-flag` on `application-reference` flagging Article 32 dual-track invention / UM pairs.\n\nRelated tools: `get_tipo_patent_twins` for the explicit pair list; `get_tipo_patent_annuity` for maintenance status.",
    "PatentRights",
    "patent rights",
    false,
  );
  fetchTool(
    "get_tipo_patent_priority",
    "Fetch Taiwan Paris priority claim records for a patent.\n\nWraps `/PatentPriority`. One row per application; the `prioritys` list carries each claimed priority (country, number, date).\n\nRelated tools: `get_tipo_patent` (application biblio includes no priority); no upstream substitute (TW not in INPADOC).",
    "PatentPriority",
    "patent priority",
    false,
  );
  fetchTool(
    "get_tipo_patent_annuity",
    'Fetch Taiwan annuity payment schedule for a patent.\n\nWraps `/PatentAnnuity`. Carries paid-through dates and per-payment year ranges — useful for "still in force" / lapse-risk screening.\n\nRelated tools: `get_tipo_patent_rights` for grant status; no upstream substitute.',
    "PatentAnnuity",
    "patent annuity",
    false,
  );

  server.tool(
    {
      ...options,
      name: "get_tipo_patent_twins",
      description:
        'Fetch Taiwan Article 32 invention / UM "twin" pair records.\n\nWraps `/PatentTwins`. TW Patent Act Article 32 permits dual invention + utility-model filings on the same disclosure; the applicant must elect one when the invention is granted. Rows come from two lists, tagged `list`: `twins-announceds` (utility models announced as twins) and `twins-approveds` (pairs, with the invention as `twins-appl-no`). Either application number of a pair works.\n\nRelated tools: `get_tipo_patent_rights` (the `twins-flag` field on `application-reference`); no upstream substitute (this is a TW-specific dual-track regime).',
      input: z.object({
        appl_no: numberInput(
          "TW utility-model or invention application number of a twin pair, or a list.",
        ),
        full: fullField,
      }),
    },
    async ({ appl_no, full }) => {
      const numbers = ids(appl_no);
      // A utility model is the pair's applno; an invention is its twinsapplno.
      const pages = await each(numbers, async (n) => {
        const page = await client.getByApplicationNumber("PatentTwins", n);
        return page.rows.length
          ? page
          : client.query("PatentTwins", { filters: { twinsapplno: n } });
      });
      const items = project(
        pages.flatMap((page) => page.rows),
        full,
      );
      const first = pages[0] as TipoPage;
      return {
        ...envelope(
          rowsSummary("patent twins", "rows for", items.length, numbers, []),
          items,
          {
            ...first,
            provenance: endpointProvenance(first, numbers, "PatentTwins"),
          },
        ),
        not_found: [],
      };
    },
  );

  server.tool(
    {
      ...options,
      name: "get_tipo_patent_events",
      description:
        'Fetch Taiwan patent post-filing events (assignments, conversions, divisions).\n\nMerges `/PatentAlteration` (assignment records: assignor `alteration-name1`, assignee `alteration-name2`), `/PatentChange` (conversions between invention, utility model and design that mint a new application number) and `/PatentDivide` (divisional applications) into one envelope. Conversions and divisions are found whether the number is the original or the new application. Each item carries an `event_type` discriminator (`"alteration"`, `"change"`, `"divide"`).\n\nRelated tools: `get_tipo_patent` (application biblio); `get_tipo_patent_rights` (grant status); no upstream substitute.',
      input: z.object({
        appl_no: numberInput(
          "TW patent / UM / design application number, or a list.",
        ),
        full: fullField,
      }),
    },
    ({ appl_no, full }) =>
      events(
        appl_no,
        full,
        "patent events",
        "PatentAlteration+Change+Divide",
        (n) =>
          Promise.all([
            client
              .getByApplicationNumber("PatentAlteration", n)
              .then((p) => ["alteration", p] as [string, TipoPage]),
            client
              .getByApplicationNumber("PatentChange", n)
              .then((p) => ["change", p] as [string, TipoPage]),
            client
              .query("PatentChange", { filters: { newapplno: n } })
              .then((p) => ["change", p] as [string, TipoPage]),
            client
              .query("PatentDivide", { filters: { querytype: 1, applno: n } })
              .then((p) => ["divide", p] as [string, TipoPage]),
            client
              .query("PatentDivide", {
                filters: { querytype: 1, newapplno: n },
              })
              .then((p) => ["divide", p] as [string, TipoPage]),
          ]),
      ),
  );

  server.tool(
    {
      ...options,
      name: "search_tipo_trademarks",
      description:
        "Search Taiwan trademarks at TIPO.\n\nWraps `/TmarkAppl`. Returns biblio + Nice classes + goods/services + image URLs. Note: Taiwan is not a WIPO member, so no WIPO Global Brand DB equivalent — TIPO is the only upstream substitute.",
      input: z.object({
        q: z
          .string()
          .nullable()
          .default(null)
          .describe("Words in the mark name, e.g. 'LATEX' or '統一'."),
        tmark_class: z
          .union([
            z.number().int().min(1).max(45),
            z.string().regex(/^\d{1,3}$/),
          ])
          .nullable()
          .default(null)
          .describe("Nice classification class (1-45)."),
        appl_date_from: dateField("Earliest application date"),
        appl_date_to: dateField("Latest application date"),
        applicant: z
          .string()
          .nullable()
          .default(null)
          .describe(
            "Applicant name filter: Chinese names match the Chinese name, others the English name.",
          ),
        top: topField,
        skip: skipField,
        full: fullField,
      }),
    },
    async (input) => {
      const page = await client.query("TmarkAppl", {
        filters: {
          tmarkname: input.q,
          // TIPO's tmarkclass is the mark's kind; the Nice class is goodclasscode.
          goodclasscode:
            input.tmark_class === null ? null : String(input.tmark_class),
          ...applicantFilter(input.applicant),
          applbdate: input.appl_date_from,
          appledate: input.appl_date_to,
        },
        top: input.top,
        skip: input.skip,
      });
      const items = project(page.rows, input.full);
      const summary = [
        `TIPO trademarks — ${items.length} of ${page.total_count} hits`,
        input.q ? ` for \`${input.q}\`` : "",
        input.applicant ? ` by ${input.applicant}` : "",
        input.tmark_class ? ` (class ${input.tmark_class})` : "",
      ].join("");
      return envelope(`${summary}.`, items, page, {
        more_available: page.more_available,
      });
    },
  );

  const trademarkNumber = numberInput(
    "TW trademark application number (e.g. '112000113'), or a list.",
  );
  fetchTool(
    "get_tipo_trademark",
    "Fetch one or more Taiwan trademark application records.\n\nWraps `/TmarkAppl?applno=...`. Returns biblio + Nice classes + image URLs. A number with no record is listed in `not_found`.\n\nRelated tools: `search_tipo_trademarks`; `get_tipo_trademark_rights` for registration status.",
    "TmarkAppl",
    "trademark applications",
    true,
    trademarkNumber,
  );
  fetchTool(
    "get_tipo_trademark_rights",
    "Fetch Taiwan trademark registration + status records.\n\nWraps `/TmarkRights`. Carries the full status grid (opposition, exam, nullity, transfer, extended ...) plus the registration number (`exam-no`) + dates and the term (`deadline`).\n\nRelated tools: `get_tipo_trademark` for the application-side record; `get_tipo_trademark_events` for post-registration events.",
    "TmarkRights",
    "trademark rights",
    false,
    trademarkNumber,
  );
  fetchTool(
    "get_tipo_trademark_priority",
    "Fetch Taiwan trademark Paris priority claim records.\n\nWraps `/TmarkPriority`. Each row nests the registered mark (`tmarkcontent`) with its `priorities`.\n\nRelated tools: `get_tipo_trademark`; `get_tipo_trademark_rights`.",
    "TmarkPriority",
    "trademark priority",
    false,
    trademarkNumber,
  );
  fetchTool(
    "get_tipo_trademark_image_urls",
    "Fetch Taiwan trademark image URLs.\n\nWraps `/TmarkPics`. Returns image URLs only (up to six per mark); no rendering.\n\nRelated tools: `get_tipo_trademark` (the `tmark-image-url` list is also present on the application record).",
    "TmarkPics",
    "trademark images",
    false,
    trademarkNumber,
  );

  server.tool(
    {
      ...options,
      name: "get_tipo_trademark_events",
      description:
        'Fetch Taiwan trademark post-registration events (transfers, divisions).\n\nMerges `/TmarkChange` (transfer / name-change events) and `/TmarkDivide` (divisions of a registration) into one envelope. Divisions are recorded by registration number, so the tool looks the registration up first; an unregistered application has no division events. Each item carries an `event_type` discriminator (`"change"` or `"divide"`).\n\nRelated tools: `get_tipo_trademark_rights` for current status.',
      input: z.object({ appl_no: trademarkNumber, full: fullField }),
    },
    ({ appl_no, full }) =>
      events(
        appl_no,
        full,
        "trademark events",
        "TmarkChange+Divide",
        async (n) => {
          const [change, rights] = await Promise.all([
            client.getByApplicationNumber("TmarkChange", n),
            client.getByApplicationNumber("TmarkRights", n),
          ]);
          const examNumbers = [
            ...new Set(
              rights.rows
                .map((row) => row["exam-no"])
                .filter(
                  (value): value is string =>
                    typeof value === "string" && !!value,
                ),
            ),
          ];
          const divides = await Promise.all(
            examNumbers.flatMap((examno) => [
              client.query("TmarkDivide", { filters: { examno } }),
              client.query("TmarkDivide", {
                filters: { originexamno: examno },
              }),
            ]),
          );
          return [
            ["change", change] as [string, TipoPage],
            ...divides.map((page) => ["divide", page] as [string, TipoPage]),
          ];
        },
      ),
  );
}

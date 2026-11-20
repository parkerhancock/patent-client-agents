import {
  ILPO_STATUS_EN,
  type IlpoPage,
  type IlpoRegisterClient,
  type IlpoRow,
  type IlpoTable,
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

const LIST_CAP = 50;
const DEFAULT_LIMIT = 25;
const MAX_LIMIT = 100;

const TRADEMARK_STATUSES = [
  "רשום",
  "סגור",
  "אי תשלום",
  "בחינה ראשונה",
  "בחינה שנייה",
  "ממתין לבחינה",
  "ממתין לקבלת החלטה בתיק אחר",
  "קובל",
  "במיון",
] as const;
const PATENT_STATUSES = [
  "בקשה חדשה",
  "פרסום שני",
  "פטנט",
  "בקשה הוזנחה",
  "בקשה סורבה",
  "פג תוקף",
  "פקיעת תוקף",
  "פטנט בוטל",
  "צו ארכה",
  "צו ארכה פג תוקף",
] as const;
const ROUTES = {
  national: "לאומי",
  international: "בינלאומי",
  basis_for_international: "בסיס לבינלאומי",
} as const;

/** A status given in English (as ILPO_STATUS_EN renders it) or in the register's Hebrew. */
function statusInput(values: readonly string[]) {
  const english = values.map((value) => ILPO_STATUS_EN[value] as string);
  return z
    .enum([...english, ...values] as [string, ...string[]])
    .nullable()
    .default(null)
    .transform((value) =>
      value === null ? null : (values[english.indexOf(value)] ?? value),
    );
}
const hebrewText = (text: string) => /[֐-׿]/.test(text);
/** The column of a bilingual pair matching the text's script. */
const byScript = (text: string | null, he: string, en: string) =>
  text ? { [hebrewText(text) ? he : en]: text } : {};

/** Lean rows drop the customs-enforcement contact columns and the extract link, which is the same site root on every row. */
export function leanIlpoTrademark(row: IlpoRow): IlpoRow {
  const {
    customs_representative: _a,
    customs_address_start_date: _b,
    customs_representative_email: _c,
    customs_representative_phone: _d,
    extract_url: _e,
    ...rest
  } = row;
  return rest;
}

const envelopeSchema = listEnvelopeSchema.extend({
  not_found: z.array(z.string()).optional(),
});
const window = {
  limit: z
    .number()
    .int()
    .min(1)
    .max(MAX_LIMIT)
    .default(DEFAULT_LIMIT)
    .describe(
      `Rows to return (default ${DEFAULT_LIMIT}, at most ${MAX_LIMIT}).`,
    ),
  offset: z.number().int().min(0).default(0).describe("Rows to skip."),
};
const text = (description: string) =>
  z
    .string()
    .trim()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(description);
const numbers = (description: string) =>
  z
    .union([
      z.number().int().positive(),
      z.array(z.number().int().positive()).min(1).max(LIST_CAP),
    ])
    .describe(description);
const asList = (value: number | number[]) =>
  typeof value === "number" ? [value] : value;

function pageSummary(
  label: string,
  page: IlpoPage,
  count: number,
  hint: string | null,
) {
  const total = page.total.toLocaleString("en-US");
  const shown = count
    ? `rows ${page.offset + 1}-${page.offset + count}`
    : "no rows";
  return `ILPO ${label} — ${total} matches${hint ? ` for \`${hint}\`` : ""}, returned ${shown}.`;
}
function group(rows: IlpoRow[], key: string) {
  const out = new Map<number, IlpoRow[]>();
  for (const row of rows) {
    const id = row[key] as number;
    const { [key]: _key, ...rest } = row;
    out.set(id, [...(out.get(id) ?? []), rest]);
  }
  return out;
}

/** Search and fetch tools over the Israeli trade-mark and patent registers. No credentials. */
export function registerIlpoRegisterTools(
  server: FastMCP,
  client: IlpoRegisterClient,
  auth?: AuthCheck,
) {
  const options = {
    output: envelopeSchema,
    outputSchema: objectOutputSchema(envelopeSchema),
    annotations: detailToolOptions().annotations,
    ...(auth ? { auth } : {}),
  };
  /** The related rows of each table, attached to their parent records under `name`. */
  const attach = async (
    parents: IlpoRow[],
    key: string,
    related: [string, IlpoTable][],
  ) => {
    const ids = parents.map((row) => row[key] as number);
    const tables = await Promise.all(
      related.map(
        async ([name, table]) =>
          [name, group(await client.rowsFor(table, ids), key)] as const,
      ),
    );
    return parents.map((parent) => ({
      ...parent,
      ...Object.fromEntries(
        tables.map(([name, rows]) => [
          name,
          rows.get(parent[key] as number) ?? [],
        ]),
      ),
    }));
  };

  server.tool(
    {
      ...options,
      name: "search_ilpo_trademarks",
      description:
        "Search Israel's trade-mark register (Israel Patent Office, via the Ministry of Justice open data on data.gov.il, refreshed daily).\n\n`q` matches words at the start of words in the mark text (Hebrew or English, by the query's script); `owner` the owner's name the same way. Filters combine. Each row carries the mark number, status (Hebrew, with `status_en`), route (national or Madrid), dates, Nice and Vienna classes, goods and services in both languages, owner, licensee and agent.\n\nRelated tools: `get_ilpo_trademark` for priority claims, parties, events, foreign registrations and conditions; `search_ilpo_patents`.",
      input: z.object({
        q: text("Words in the mark, e.g. 'coca cola' or 'אסם'."),
        owner: text("Owner name words, e.g. 'Strauss' or 'שטראוס'."),
        nice_class: z
          .number()
          .int()
          .min(1)
          .max(45)
          .nullable()
          .default(null)
          .describe("Nice class the mark covers (1-45)."),
        status: statusInput(TRADEMARK_STATUSES).describe(
          `Register status, in English or Hebrew: ${TRADEMARK_STATUSES.map((s) => `'${ILPO_STATUS_EN[s]}' (${s})`).join(", ")}.`,
        ),
        route: z
          .enum(["national", "international", "basis_for_international"])
          .nullable()
          .default(null)
          .describe(
            "'national', 'international' (a Madrid designation of Israel), or 'basis_for_international' (a national mark underlying a Madrid application).",
          ),
        ...window,
        full: z
          .boolean()
          .default(false)
          .describe(
            "Lean (default) drops the customs-enforcement contact columns and the extract link; True returns every column.",
          ),
      }),
    },
    async (input) => {
      const page = await client.query("trademarks", {
        words: {
          ...byScript(input.q, "mark_text_he", "mark_text_en"),
          ...byScript(input.owner, "owner_name_he", "owner_name_en"),
        },
        tokens: { nice_classes: input.nice_class },
        filters: {
          status: input.status,
          route: input.route ? ROUTES[input.route] : null,
        },
        sort: "mark_number desc",
        limit: input.limit,
        offset: input.offset,
      });
      const items = input.full ? page.rows : page.rows.map(leanIlpoTrademark);
      return {
        ...listEnvelope(
          pageSummary(
            "trade marks",
            page,
            items.length,
            input.q ?? input.owner,
          ),
          items,
          page.provenance,
        ),
        more_available: page.more_available,
      };
    },
  );

  server.tool(
    {
      ...options,
      name: "get_ilpo_trademark",
      description:
        "Fetch Israeli trade-mark records by mark number, with their related register tables.\n\nEach item is the register row plus `priorities` (Paris priority claims and their examination result), `parties` (holders and licensees with their roles), `events` (the mark's change log), `foreign_registrations` (registrations a mark was based on) and `conditions` (conditions and disclaimers). A number with no record is listed in `not_found`.\n\nRelated tools: `search_ilpo_trademarks` to find mark numbers.",
      input: z.object({
        mark_number: numbers(
          "Israeli trade-mark number, e.g. 55359, or a list (up to 50).",
        ),
        full: z
          .boolean()
          .default(false)
          .describe(
            "Lean (default) drops the customs-enforcement contact columns and the extract link.",
          ),
      }),
    },
    async ({ mark_number, full }) => {
      const wanted = asList(mark_number);
      const page = await client.query("trademarks", {
        filters: { mark_number: wanted },
        limit: wanted.length,
      });
      const found = new Set(page.rows.map((row) => row.mark_number as number));
      const records = await attach(page.rows, "mark_number", [
        ["priorities", "trademarkPriorities"],
        ["parties", "trademarkParties"],
        ["events", "trademarkEvents"],
        ["foreign_registrations", "trademarkForeignRegistrations"],
        ["conditions", "trademarkConditions"],
      ]);
      const order = new Map(wanted.map((n, i) => [n, i]));
      records.sort(
        (a, b) =>
          (order.get(a.mark_number as number) ?? 0) -
          (order.get(b.mark_number as number) ?? 0),
      );
      const notFound = wanted.filter((n) => !found.has(n)).map(String);
      const items = full ? records : records.map(leanIlpoTrademark);
      return {
        ...listEnvelope(
          `Fetched ${items.length} of ${wanted.length} ILPO trade marks.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`,
          items,
          page.provenance,
        ),
        more_available: false,
        not_found: notFound,
      };
    },
  );

  server.tool(
    {
      ...options,
      name: "search_ilpo_patents",
      description:
        "Search Israel's patent register (Israel Patent Office, via the Ministry of Justice open data on data.gov.il, refreshed daily).\n\nSearch one way per call: by title words (`q`, Hebrew or English by the query's script, optionally with `status`), by `applicant` name words, or by `ipc` class prefix (e.g. 'H01M' or 'C07D 215'). Applicant and IPC searches run over those tables, whose matches are rows, so one application can appear for several matching applicants or classes; each row carries the application's register record. Each record has the application and filing dates, titles in both languages, PCT numbers, publication and grant dates and status (Hebrew, with `status_en`).\n\nRelated tools: `get_ilpo_patent` for applicants, inventors and IPC classes; `search_ilpo_trademarks`.",
      input: z.object({
        q: text("Words in the title, e.g. 'graphene' or 'סוללה'."),
        status: statusInput(PATENT_STATUSES).describe(
          `Register status, in English or Hebrew: ${PATENT_STATUSES.map((s) => `'${ILPO_STATUS_EN[s]}' (${s})`).join(", ")}. Only with q or alone.`,
        ),
        applicant: text("Applicant name words, e.g. 'Teva' or 'טבע'."),
        ipc: text("IPC class prefix, e.g. 'H01M' or 'A61K 31'."),
        ...window,
      }),
    },
    async (input) => {
      const driver = input.applicant
        ? "applicant"
        : input.ipc
          ? "ipc"
          : "register";
      if (input.applicant && input.ipc)
        throw new Error(
          "Search by applicant or by IPC class, not both in one call.",
        );
      if (driver !== "register" && (input.q || input.status))
        throw new Error(
          "q and status apply to the register search; run applicant and IPC searches without them.",
        );
      if (driver === "register") {
        const page = await client.query("patents", {
          words: byScript(input.q, "title_he", "title_en"),
          filters: { status: input.status },
          sort: "application_number desc",
          limit: input.limit,
          offset: input.offset,
        });
        return {
          ...listEnvelope(
            pageSummary("patent applications", page, page.rows.length, input.q),
            page.rows,
            page.provenance,
          ),
          more_available: page.more_available,
        };
      }
      const table: IlpoTable =
        driver === "applicant" ? "patentApplicants" : "patentClassifications";
      const page = await client.query(table, {
        words:
          driver === "applicant"
            ? byScript(input.applicant, "name_he", "name_en")
            : { ipc: input.ipc },
        sort: "application_number desc",
        limit: input.limit,
        offset: input.offset,
      });
      const ids = [
        ...new Set(page.rows.map((row) => row.application_number as number)),
      ];
      const records = new Map(
        (await client.rowsFor("patents", ids)).map((row) => [
          row.application_number as number,
          row,
        ]),
      );
      const items = page.rows.map((row) => ({
        match: Object.fromEntries(
          Object.entries(row).filter(([key]) => key !== "application_number"),
        ),
        ...(records.get(row.application_number as number) ?? {
          application_number: row.application_number,
        }),
      }));
      return {
        ...listEnvelope(
          pageSummary(
            driver === "applicant"
              ? "patent applicant rows"
              : "patent IPC rows",
            page,
            items.length,
            input.applicant ?? input.ipc,
          ),
          items,
          page.provenance,
        ),
        more_available: page.more_available,
      };
    },
  );

  server.tool(
    {
      ...options,
      name: "get_ilpo_patent",
      description:
        "Fetch Israeli patent applications by application number, with applicants, inventors and IPC classes.\n\nEach item is the register record plus `applicants` and `inventors` (names and addresses in Hebrew and English, as the register publishes them) and `classifications` (IPC codes, `main` marking the principal one). A number with no record is listed in `not_found`.\n\nRelated tools: `search_ilpo_patents` to find application numbers.",
      input: z.object({
        application_number: numbers(
          "Israeli patent application number, e.g. 250000, or a list (up to 50).",
        ),
      }),
    },
    async ({ application_number }) => {
      const wanted = asList(application_number);
      const page = await client.query("patents", {
        filters: { application_number: wanted },
        limit: wanted.length,
      });
      const found = new Set(
        page.rows.map((row) => row.application_number as number),
      );
      const records = await attach(page.rows, "application_number", [
        ["applicants", "patentApplicants"],
        ["inventors", "patentInventors"],
        ["classifications", "patentClassifications"],
      ]);
      const order = new Map(wanted.map((n, i) => [n, i]));
      records.sort(
        (a, b) =>
          (order.get(a.application_number as number) ?? 0) -
          (order.get(b.application_number as number) ?? 0),
      );
      const notFound = wanted.filter((n) => !found.has(n)).map(String);
      return {
        ...listEnvelope(
          `Fetched ${records.length} of ${wanted.length} ILPO patent applications.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`,
          records,
          page.provenance,
        ),
        more_available: false,
        not_found: notFound,
      };
    },
  );
}

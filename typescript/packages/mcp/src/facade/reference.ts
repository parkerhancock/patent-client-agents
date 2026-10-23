import {
  EntityTierSchema,
  FeeCategorySchema,
  FeeRouteError,
  type FeeSchedule,
  filterFees,
  PYTHON_FEE_ROUTES,
  RightTypeSchema,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import { getCopyrightRecords, searchCopyright } from "../copyright.js";
import { requireEpo } from "./epo.js";
import {
  type AuthCheck,
  detailEnvelope,
  type FacadeClients,
  facadeToolOptions,
  listEnvelope,
} from "./shared.js";

const CPC_SOURCE = "Cooperative Patent Classification (CPC)";
const NO_EFFECTIVE_DATE = "effective date not published by the office";

/** Lean CPC search hit, as the Python `_stub_cpc_search_hit`. */
function stubCpc(symbol: string, title: string | null) {
  const head = symbol.split("/", 1)[0];
  return {
    symbol,
    title,
    parent_symbol:
      symbol.includes("/") && !symbol.endsWith("/00") ? `${head}/00` : null,
  };
}
/** EPO OPS maps between CPC, ECLA and IPC only. */
function scheme(value: string, side: string): "cpc" | "ecla" | "ipc" {
  const parsed = z
    .enum(["cpc", "ecla", "ipc"])
    .safeParse(value.trim().toLowerCase());
  if (parsed.success) return parsed.data;
  throw new Error(
    `classify_cpc(mode='map') ${side} must be 'cpc', 'ipc' or 'ecla'; EPO OPS has no '${value}' concordance (USCLS mapping is not available).`,
  );
}
const effective = (schedule: FeeSchedule) =>
  schedule.effective_date
    ? `effective ${schedule.effective_date}`
    : NO_EFFECTIVE_DATE;
/** Fee route errors (unknown office, unsupported right, not yet ported) become plain tool errors. */
async function loadSchedule(
  clients: FacadeClients,
  jurisdiction: string,
  right: string,
) {
  try {
    return await clients.fees.getSchedule(
      jurisdiction,
      RightTypeSchema.parse(right),
    );
  } catch (error) {
    if (error instanceof FeeRouteError) throw new Error(error.message);
    if (error instanceof z.ZodError)
      throw new Error(
        `unknown right '${right}'; supported: ${RightTypeSchema.options.join(", ")}`,
      );
    throw error;
  }
}

export function registerReferenceFacade(
  server: FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
): void {
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "classify_cpc",
      description: `Work with CPC (Cooperative Patent Classification) codes — search, look up, or map them.

Routes by \`mode\`: 'search' finds candidate symbols by keyword (returns a
ranked list); 'lookup' returns one symbol's official title and hierarchy;
'map' cross-references one symbol between CPC, IPC, and ECLA. Find a symbol
with mode='search' first, then mode='lookup' to read it or mode='map' to
translate it.

Related tools: get_fees.`,
      input: z.object({
        mode: z
          .enum(["search", "lookup", "map"])
          .describe(
            "What to do. 'search' = find candidate CPC symbols by keyword. 'lookup' = get the title/definition for one symbol you already have. 'map' = cross-reference one symbol between schemes (CPC/IPC/ECLA).",
          ),
        query: z
          .string()
          .max(500)
          .nullable()
          .default(null)
          .describe(
            "mode='search': keyword(s) describing the technology area (e.g. 'machine learning', 'lithium battery thermal management').",
          ),
        symbol: z
          .string()
          .max(40)
          .nullable()
          .default(null)
          .describe(
            "mode='lookup'/'map': the CPC classification symbol (e.g. 'H04L9/32', 'G06F1/00').",
          ),
        from_scheme: z
          .string()
          .default("cpc")
          .describe("mode='map': source scheme — 'cpc', 'ipc', or 'ecla'."),
        to_scheme: z
          .string()
          .default("ipc")
          .describe("mode='map': target scheme — 'cpc', 'ipc', or 'ecla'."),
        range_begin: z
          .number()
          .int()
          .min(1)
          .default(1)
          .describe("mode='search': start of result range (1-indexed)."),
        range_end: z
          .number()
          .int()
          .min(1)
          .default(10)
          .describe("mode='search': end of result range."),
        full: z
          .boolean()
          .default(false)
          .describe(
            "mode='search': False (default) = lean stub per hit (symbol + title + parent). True = full upstream record (match percentage, title parts).",
          ),
      }),
    },
    async (input) => {
      if (input.mode === "lookup") {
        if (!input.symbol)
          throw new Error("classify_cpc(mode='lookup') requires symbol.");
        const response = await requireEpo(clients).retrieveCpc(input.symbol);
        const item = response.data.scheme.items[0];
        const extras = [
          item?.level != null ? `level ${item.level}` : null,
          item?.not_allocatable ? "not allocatable" : null,
          item?.breakdown_code ? "breakdown code" : null,
        ].filter(Boolean);
        return detailEnvelope(
          `**CPC ${item?.symbol ?? input.symbol}** — ${item?.title ?? "(no title)"}${extras.length ? ` (${extras.join(", ")})` : ""}.`,
          response.data,
          { ...response.provenance, source_name: CPC_SOURCE },
        );
      }
      if (input.mode === "map") {
        if (!input.symbol)
          throw new Error("classify_cpc(mode='map') requires symbol.");
        const from = scheme(input.from_scheme, "from_scheme");
        const to = scheme(input.to_scheme, "to_scheme");
        const response = await requireEpo(clients).mapClassification(
          from,
          input.symbol,
          to,
        );
        const targets = [
          ...new Set(
            response.data.mappings
              .map(
                (mapping) =>
                  mapping[to] ?? mapping.ipc ?? mapping.cpc ?? mapping.ecla,
              )
              .filter((value): value is string => Boolean(value)),
          ),
        ];
        const head = `**CPC mapping ${input.symbol}** (${from.toUpperCase()} → ${to.toUpperCase()})`;
        return detailEnvelope(
          targets.length
            ? `${head}: ${targets.join(", ")}.`
            : `${head}: no cross-reference found.`,
          response.data,
          { ...response.provenance, source_name: CPC_SOURCE },
        );
      }
      if (!input.query)
        throw new Error("classify_cpc(mode='search') requires query.");
      const response = await requireEpo(clients).searchCpc(input.query, {
        rangeBegin: input.range_begin,
        rangeEnd: input.range_end,
      });
      const results = response.data.results;
      const items = results.map((result) =>
        input.full
          ? { ...result }
          : stubCpc(result.classification_symbol, result.title),
      );
      const total = response.data.total_results;
      return {
        ...listEnvelope(
          `CPC search — \`${input.query}\`: ${total ? `${items.length} of ${total} hits` : `${items.length} hits`}.`,
          items,
          { ...response.provenance, source_name: CPC_SOURCE },
        ),
        more_available: Boolean(
          total && items.length + (input.range_begin - 1) < total,
        ),
      };
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "get_fees",
      description: `Get official patent fees. This server has the USPTO (patent, design and trademark), EPO (European patent application) and EPO-UP (Unitary Patent) schedules; other offices report that they are not yet ported.

Routes by \`mode\`: 'schedule' returns one office's full published fee
schedule; 'lookup' filters a schedule down to line items matching a
category/tier/year; 'jurisdictions' lists every available (office, right)
schedule so you know what to ask for. Discover with mode='jurisdictions'
first, then mode='schedule' or mode='lookup'.

Related tools: classify_cpc.`,
      input: z.object({
        mode: z
          .enum(["schedule", "lookup", "jurisdictions"])
          .describe(
            "What to do. 'schedule' = the full published fee schedule for one office. 'lookup' = filter a schedule down to matching line items. 'jurisdictions' = list which (office, right) schedules are available.",
          ),
        jurisdiction: z
          .string()
          .max(80)
          .nullable()
          .default(null)
          .describe(
            "mode='schedule'/'lookup': office or jurisdiction — 'USPTO' or 'US', 'EPO' or 'EP', or 'UP' (Unitary Patent). Not used for mode='jurisdictions'.",
          ),
        right: z
          .string()
          .default("patent")
          .describe(
            "mode='schedule'/'lookup': which IP right's schedule — 'patent' (default), 'trademark', or 'design'.",
          ),
        category: z
          .string()
          .nullable()
          .default(null)
          .describe(
            "mode='lookup': filter to one fee category ('filing', 'search', 'examination', 'grant', 'renewal', 'maintenance', 'excess_claims', 'extension', 'appeal', 'petition', 'opposition'). None = every category.",
          ),
        tier: z
          .string()
          .default("large")
          .describe(
            "mode='lookup': entity-tier filter for offices with discounts. 'large' (default), 'small', or 'micro'. Ignored on schedules with no tier dimension.",
          ),
        year: z
          .number()
          .int()
          .min(1)
          .max(30)
          .nullable()
          .default(null)
          .describe(
            "mode='lookup': required when filtering renewal/maintenance fees (USPTO maintenance: 4, 8, 12 for the 3.5/7.5/11.5-year fees; USPTO trademark renewals: 10; EPO renewals: 3-20; Unitary Patent renewals: 2-20). None excludes renewal/maintenance rows.",
          ),
        refresh: z
          .boolean()
          .default(false)
          .describe(
            "USPTO only. This server keeps no fee cache, so every USPTO request already fetches the live page; refresh is accepted for USPTO and rejected for other offices.",
          ),
      }),
    },
    async (input) => {
      if (input.mode === "jurisdictions") {
        if (input.refresh)
          throw new Error("refresh requires mode=schedule or lookup");
        const { schedules: rows, unavailable } =
          await clients.fees.listSchedules();
        const supported = new Set(clients.fees.supportedRoutes);
        const unported = PYTHON_FEE_ROUTES.filter(
          ([office, right]) => !supported.has(`${office}/${right}`),
        ).map(([office, right]) => `${office} ${right}`);
        const failed = unavailable.length
          ? ` Unavailable right now: ${unavailable.map((u) => `${u.route} (${u.error})`).join("; ")}.`
          : "";
        return listEnvelope(
          `${rows.length} fee schedules available: ${rows.map((row) => row.key).join(", ")}.${failed} Not yet ported: ${unported.join(", ")}.`,
          rows.map((row) => ({ ...row })),
          {
            source_url: "https://www.epo.org/en/applying/fees",
            source_name: "IP-office fee schedules",
            retrieved_at: new Date().toISOString(),
            cache_hit: false,
          },
        );
      }
      if (!input.jurisdiction)
        throw new Error(
          `get_fees(mode='${input.mode}') requires jurisdiction.`,
        );
      const schedule = await loadSchedule(
        clients,
        input.jurisdiction,
        input.right,
      );
      if (input.refresh && schedule.office_code !== "USPTO")
        throw new Error("refresh is supported only for USPTO fees.");
      const { provenance, ...details } = schedule;
      if (input.mode === "schedule")
        return detailEnvelope(
          `**${schedule.office_code} ${schedule.right} fee schedule** (${schedule.jurisdiction}) — ${effective(schedule)}, ${schedule.fees.length} fees in ${schedule.currency}. Source: ${schedule.source_url}`,
          details,
          provenance,
        );
      const tier = EntityTierSchema.safeParse(input.tier.toLowerCase());
      if (!tier.success)
        throw new Error(
          `unknown tier '${input.tier}'; supported: ${EntityTierSchema.options.join(", ")}`,
        );
      let category: z.infer<typeof FeeCategorySchema> | undefined;
      if (input.category !== null) {
        const parsed = FeeCategorySchema.safeParse(input.category);
        if (!parsed.success)
          throw new Error(
            `unknown category '${input.category}'; supported: ${FeeCategorySchema.options.join(", ")}`,
          );
        category = parsed.data;
      }
      const fees = filterFees(schedule.fees, {
        ...(category ? { category } : {}),
        tier: tier.data,
        ...(input.year === null ? {} : { year: input.year }),
      });
      const coverage = schedule.recurring_fee_coverage;
      const coverageNote = [
        `Recurring-fee coverage: ${coverage.status}`,
        coverage.missing_years.length
          ? `missing years: ${coverage.missing_years.join(", ")}`
          : "",
        coverage.notes ?? "",
      ]
        .filter(Boolean)
        .join("; ");
      const {
        fees: _all,
        notes: _notes,
        statutory_basis: _basis,
        ...metadata
      } = details;
      return {
        ...listEnvelope(
          `${schedule.office_code} ${schedule.right}${category ? ` category='${category}'` : ""}${input.year === null ? "" : ` year=${input.year}`}: ${fees.length} fee${fees.length === 1 ? "" : "s"} (schedule ${effective(schedule)}).${fees.length ? "" : ` No matching fees found. ${coverageNote}.`}`,
          fees.map((fee) => ({ ...fee })),
          provenance,
        ),
        source_metadata: metadata,
      };
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "copyright",
      description: `Search U.S. Copyright Office registrations and recorded documents, or fetch one by id.

Routes by \`mode\`: 'search' finds registrations and recorded documents
(transfers, assignments, licenses) by keyword and returns lean stubs;
'get' fetches the full record(s) for a Public Records id. Both return a
list envelope. Search first, then pass a hit's \`public_records_id\` to
mode='get'. The office pages through only the first 50,000 hits of a query.

Related tools: classify_cpc, get_fees.`,
      input: z.object({
        mode: z
          .enum(["search", "get"])
          .describe(
            "What to do. 'search' = find U.S. Copyright Office registrations by keyword. 'get' = fetch one or more full records by Public Records id.",
          ),
        query: z
          .string()
          .max(500)
          .nullable()
          .default(null)
          .describe(
            "mode='search': a title, a claimant/author name, a registration number (e.g. 'TX 1234567'), or any keyword.",
          ),
        public_records_id: z
          .union([
            z.string().min(1).max(200),
            z.array(z.string().min(1).max(200)).min(1).max(50),
          ])
          .nullable()
          .default(null)
          .describe(
            "mode='get': the opaque Public Records id from a search hit's `public_records_id` field (NOT a registration number). Single id or a list of up to 50 for portfolio workflows. Examples: 'voyager_37022961'.",
          ),
        field: z
          .string()
          .default("keyword")
          .describe(
            "mode='search': which field to search — 'keyword' (default, all fields), 'title', or 'name' (claimant/author).",
          ),
        page: z
          .number()
          .int()
          .min(1)
          .default(1)
          .describe("mode='search': page number (1-based)."),
        page_size: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(10)
          .describe("mode='search': results per page (default 10, max 100)."),
        full: z
          .boolean()
          .default(false)
          .describe(
            "mode='search': False (default) = lean stub per hit. True = every title/claimant/date/class list and the relevance score.",
          ),
      }),
    },
    async (input) => {
      if (input.mode === "get") {
        if (input.public_records_id === null)
          throw new Error("copyright(mode='get') requires public_records_id.");
        return getCopyrightRecords(clients.copyright, input.public_records_id);
      }
      if (!input.query?.trim())
        throw new Error("copyright(mode='search') requires query.");
      return searchCopyright(clients.copyright, {
        query: input.query,
        field: input.field,
        page: input.page,
        page_size: input.page_size,
        full: input.full,
      });
    },
  );
}

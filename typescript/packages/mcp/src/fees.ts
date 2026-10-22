import {
  EntityTierSchema,
  FeeCategorySchema,
  FeeRouteError,
  type FeeSchedule,
  type FeesClient,
  filterFees,
  type RightType,
  RightTypeSchema,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  detailToolOptions,
  listEnvelope,
  listEnvelopeSchema,
  listToolOptions,
} from "./shared.js";

const effective = (schedule: FeeSchedule) =>
  schedule.effective_date
    ? `effective ${schedule.effective_date}`
    : "effective date not published by the office";
function coverageNote(schedule: FeeSchedule) {
  const coverage = schedule.recurring_fee_coverage;
  return [
    `Recurring-fee coverage: ${coverage.status}`,
    coverage.missing_years.length
      ? `missing years: ${coverage.missing_years.join(", ")}`
      : "",
    coverage.notes ?? "",
  ]
    .filter(Boolean)
    .join("; ");
}
/** Route errors (unknown office, unsupported right, not yet ported) become plain tool errors. */
async function load(
  client: FeesClient,
  input: { jurisdiction: string; right: RightType },
) {
  try {
    return await client.getSchedule(input.jurisdiction, input.right);
  } catch (error) {
    if (error instanceof FeeRouteError) throw new Error(error.message);
    throw error;
  }
}
const jurisdiction = z
  .string()
  .min(1)
  .max(80)
  .describe(
    "Office or jurisdiction name, e.g. USPTO, US, EPO, EP, Unitary Patent (UP). EP means EPO for patents.",
  );

export function registerFeeTools(
  server: FastMCP,
  client: FeesClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_fee_schedule",
      description:
        "Fetch an IP office's full official fee schedule: every fee with code, category, amount as a decimal string, currency, year for renewals and any per-claim or per-page condition. effective_date is the office's published date (null when unpublished), distinct from provenance.retrieved_at. Currently USPTO (patent, design, trademark), EPO (EPC fees) and EPO-UP (Unitary Patent renewals); other offices report that they are not yet ported.",
      input: z.object({
        jurisdiction,
        right: RightTypeSchema.default("patent"),
      }),
    },
    async (input) => {
      const schedule = await load(client, input);
      const { provenance, ...details } = schedule;
      return detailEnvelope(
        `${schedule.office_code} ${schedule.right} fee schedule (${schedule.jurisdiction}): ${effective(schedule)}; ${schedule.fees.length} fees in ${schedule.currency}.${schedule.unmapped_codes.length ? ` Uncategorized codes: ${schedule.unmapped_codes.join(", ")}.` : ""}`,
        details,
        provenance,
      );
    },
  );

  server.tool(
    {
      ...listToolOptions(auth),
      name: "list_fee_jurisdictions",
      description:
        "List the fee schedules available in this server, one row per office and right, with currency, effective date, fee count and renewal-fee coverage. Fetches each schedule live.",
      input: z.object({}),
    },
    async () => {
      const rows = await client.listSchedules();
      return listEnvelope(
        `${rows.length} fee schedules: ${rows.map((row) => row.key).join(", ")}.`,
        rows.map((row) => ({ ...row })),
        {
          source_url: "https://www.epo.org/en/applying/fees",
          source_name: "IP-office fee schedules",
          retrieved_at: new Date().toISOString(),
          cache_hit: false,
        },
      );
    },
  );

  server.tool(
    {
      ...listToolOptions(auth),
      output: listEnvelopeSchema.extend({ source_metadata: z.unknown() }),
      name: "lookup_fee",
      description:
        "Filter one office's fee schedule. Omit year to exclude renewal rows; pass year (USPTO maintenance 4, 8, 12; USPTO trademark renewal 10; EPO 3-20; Unitary Patent 2-20) for a renewal or maintenance fee or its late-payment fee. tier applies only to offices with entity discounts. An empty result is authoritative for renewals only when coverage is complete.",
      input: z.object({
        jurisdiction,
        right: RightTypeSchema.default("patent"),
        category: FeeCategorySchema.optional(),
        tier: EntityTierSchema.default("large"),
        year: z.number().int().min(1).max(30).optional(),
      }),
    },
    async (input) => {
      const schedule = await load(client, input);
      const fees = filterFees(schedule.fees, {
        ...(input.category ? { category: input.category } : {}),
        tier: input.tier,
        ...(input.year === undefined ? {} : { year: input.year }),
      });
      const { provenance, fees: _all, ...metadata } = schedule;
      return {
        ...listEnvelope(
          `${schedule.office_code} ${schedule.right}${input.category ? ` ${input.category}` : ""}${input.year === undefined ? "" : ` year ${input.year}`}: ${fees.length} fees (${effective(schedule)}).${fees.length ? "" : ` No matching fees. ${coverageNote(schedule)}.`}`,
          fees.map((fee) => ({ ...fee })),
          provenance,
        ),
        source_metadata: metadata,
      };
    },
  );
}

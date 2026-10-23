import { z } from "zod";
import { ProvenanceSchema } from "../models.js";

/**
 * Closed vocabularies keep cross-office comparisons honest. They match the
 * Python `fees.models` enums value for value; map new fee types to the
 * closest value and explain nuance in `label` and `notes`.
 */
export const RightTypeSchema = z.enum([
  "patent",
  "utility_model",
  "trademark",
  "design",
  "plant_variety",
  "copyright",
  "gi",
]);
export type RightType = z.infer<typeof RightTypeSchema>;
export const EntityTierSchema = z.enum(["large", "small", "micro", "none"]);
export type EntityTier = z.infer<typeof EntityTierSchema>;
export const FeeCategorySchema = z.enum([
  "filing",
  "search",
  "examination",
  "designation",
  "grant",
  "publication",
  "renewal",
  "maintenance",
  "excess_claims",
  "excess_pages",
  "excess_classes",
  "application_size",
  "extension",
  "late_fee",
  "rce",
  "reissue",
  "appeal",
  "petition",
  "opposition",
  "cancellation",
  "ptab",
  "trial",
  "statement_of_use",
  "declaration_of_use",
  "madrid",
  "deferment",
  "translation",
  "transfer",
  "other",
]);
export type FeeCategory = z.infer<typeof FeeCategorySchema>;
export const ConditionalTriggerSchema = z.enum([
  "claims_over",
  "independent_claims_over",
  "pages_over",
  "sheets_over",
  "classes_over",
  "intent_to_use",
  "paper_filing",
  "late_days",
  "deferred_publication",
  "multi_design",
]);
const recurring = new Set<FeeCategory>(["renewal", "maintenance"]);

export const FeeConditionSchema = z.strictObject({
  trigger: ConditionalTriggerSchema,
  threshold: z.number().int().nonnegative().nullable().default(null),
  per_unit: z.boolean().default(false),
  description: z.string().min(1).nullable().default(null),
});
export type FeeCondition = z.infer<typeof FeeConditionSchema>;

/** Decimal amount as a string, never a float: "1595.00". */
export const AmountSchema = z.string().regex(/^\d+(?:\.\d{1,4})?$/);
const currency = z
  .string()
  .regex(/^[A-Za-z]{3}$/)
  .transform((value) => value.toUpperCase());

export const FeeItemSchema = z
  .strictObject({
    code: z.string().min(1),
    label: z.string().min(1),
    category: FeeCategorySchema,
    rights: z.array(RightTypeSchema).min(1),
    amount: AmountSchema,
    currency,
    tier: EntityTierSchema.default("none"),
    /** Renewal or maintenance year; required for those categories, allowed on year-indexed surcharges. */
    year: z.number().int().positive().nullable().default(null),
    condition: FeeConditionSchema.nullable().default(null),
    source_url: z.url().nullable().default(null),
    notes: z.string().min(1).nullable().default(null),
  })
  .refine((fee) => !recurring.has(fee.category) || fee.year !== null, {
    message: "Renewal and maintenance fees require a year.",
    path: ["year"],
  });
export type FeeItem = z.infer<typeof FeeItemSchema>;

export const RecurringFeeCoverageSchema = z
  .strictObject({
    status: z.enum(["complete", "partial", "not_applicable"]),
    missing_categories: z.array(z.enum(["renewal", "maintenance"])).default([]),
    missing_years: z.array(z.number().int().positive()).default([]),
    notes: z.string().min(1).nullable().default(null),
  })
  .refine((coverage) => {
    const gaps =
      coverage.missing_categories.length + coverage.missing_years.length > 0;
    return coverage.status === "partial"
      ? gaps || coverage.notes !== null
      : !gaps;
  }, "Partial coverage must name gaps or explain itself; complete and not_applicable coverage cannot list gaps.");
export type RecurringFeeCoverage = z.infer<typeof RecurringFeeCoverageSchema>;

/**
 * Fee provenance keeps two dates apart: when the office says the schedule
 * took effect (`effective_date`, null when unpublished) and when these bytes
 * were fetched (`retrieved_at`).
 */
export const FeeProvenanceSchema = ProvenanceSchema.extend({
  effective_date: z.iso.date().nullable(),
});
export type FeeProvenance = z.infer<typeof FeeProvenanceSchema>;

export const FeeScheduleSchema = z
  .strictObject({
    key: z.string().min(1),
    jurisdiction: z
      .string()
      .min(2)
      .transform((value) => value.toUpperCase()),
    issuing_body: z.string().min(1),
    office_code: z.string().min(1),
    right: RightTypeSchema,
    currency,
    effective_date: z.iso.date().nullable(),
    source_url: z.url(),
    statutory_basis: z.string().min(1).nullable(),
    fees: z.array(FeeItemSchema).min(1),
    recurring_fee_coverage: RecurringFeeCoverageSchema,
    /** Upstream codes with no explicit mapping; categorized as `other` until reviewed. */
    unmapped_codes: z.array(z.string()).default([]),
    notes: z.string().min(1).nullable(),
    provenance: FeeProvenanceSchema,
  })
  .superRefine((schedule, context) => {
    if (
      schedule.key !==
      `${schedule.jurisdiction}/${schedule.office_code}/${schedule.right}`
    )
      context.addIssue({ code: "custom", message: "Schedule key mismatch." });
    for (const fee of schedule.fees) {
      if (fee.currency !== schedule.currency)
        context.addIssue({
          code: "custom",
          message: `Fee ${fee.code} currency ${fee.currency} differs from the schedule.`,
        });
      if (!fee.rights.includes(schedule.right))
        context.addIssue({
          code: "custom",
          message: `Fee ${fee.code} does not cover ${schedule.right}.`,
        });
    }
    if (schedule.provenance.effective_date !== schedule.effective_date)
      context.addIssue({
        code: "custom",
        message: "Provenance effective_date must match the schedule.",
      });
  });
export type FeeSchedule = z.infer<typeof FeeScheduleSchema>;
export type FeeScheduleInput = z.input<typeof FeeScheduleSchema>;

/** Lean discovery row for one supported schedule. */
/** `FeesClient.listSchedules` result: the schedules fetched and the routes that failed. */
export interface FeeScheduleListing {
  schedules: FeeScheduleSummary[];
  unavailable: { route: string; error: string }[];
}
export interface FeeScheduleSummary {
  key: string;
  jurisdiction: string;
  office_code: string;
  issuing_body: string;
  right: RightType;
  currency: string;
  effective_date: string | null;
  source_url: string;
  fee_count: number;
  recurring_fee_coverage: RecurringFeeCoverage;
  retrieved_at: string;
}

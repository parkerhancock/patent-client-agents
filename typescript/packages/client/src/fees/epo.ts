import { z } from "zod";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "../transport.js";
import {
  type FeeCategory,
  type FeeCondition,
  type FeeItem,
  type FeeSchedule,
  FeeScheduleSchema,
} from "./models.js";

/**
 * The EPO Schedule of Fees SPA (https://fees.apps.epo.org/prod/ui/) reads an
 * undocumented JSON backend-for-frontend. One payload holds both the EPC
 * fees and the Unitary Patent fees; codes 701, 713 and 732-771 are Unitary
 * Patent fees and form a separate schedule here.
 */
export const EPO_FEES_SOURCE = "EPO Schedule of Fees";
export const EPO_FEES_PAGE = "https://www.epo.org/en/applying/fees";
export const UNITARY_PATENT_FEES_URL =
  "https://www.epo.org/en/legal/up-upc/2022/upf_2.html";
const BFF_PATH = "/prod/bff/api/fees";

const NodeSchema: z.ZodType<FeeNode> = z.lazy(() =>
  z.looseObject({
    data: z.looseObject({
      feeCode: z.string().nullable(),
      feeDescription: z.string().nullable(),
      amount: z.string().nullable(),
      validUntil: z.string().nullable().optional(),
    }),
    children: z.array(NodeSchema).default([]),
  }),
);
interface FeeNode {
  data: {
    feeCode: string | null;
    feeDescription: string | null;
    amount: string | null;
    validUntil?: string | null | undefined;
  };
  children: FeeNode[];
}

/** "1.595,00" -> "1595.00". European notation: dot thousands, comma decimal. */
export function parseEuroAmount(raw: string): string {
  const value = raw.trim();
  if (!/^\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?$|^\d+(?:,\d{1,2})?$/.test(value))
    throw new ApiError(
      `EPO fees returned an unrecognized amount: ${value.slice(0, 20)}`,
      200,
      "INVALID_RESPONSE",
    );
  const [whole = "0", fraction = ""] = value.replaceAll(".", "").split(",");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}

interface CodeRule {
  category: FeeCategory;
  year?: number;
  condition?: FeeCondition;
  notes?: string;
}
const perPage = (threshold: number, trigger: "pages_over" | "sheets_over") =>
  ({
    trigger,
    threshold,
    per_unit: true,
    description: `Per ${trigger === "pages_over" ? "page" : "sheet"} over ${threshold}.`,
  }) as const;
const range = (from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, i) => from + i);
const code = (value: number) => String(value).padStart(3, "0");

/** Stable EPO fee codes mapped to the closed vocabulary. */
const EPC_RULES: Record<string, CodeRule> = {
  "001": { category: "filing" },
  "002": { category: "search" },
  "003": { category: "search" },
  "004": { category: "search" },
  "005": { category: "designation" },
  "006": { category: "examination" },
  "007": { category: "grant" },
  "008": { category: "excess_pages", condition: perPage(35, "pages_over") },
  "010": { category: "opposition" },
  "011": { category: "appeal" },
  "013": { category: "petition" },
  "014": { category: "other" },
  "015": { category: "excess_claims" },
  "016": { category: "excess_claims" },
  "017": { category: "other" },
  "019": { category: "other" },
  "020": { category: "filing" },
  "021": { category: "examination" },
  "022": { category: "transfer" },
  "023": { category: "transfer" },
  "029": { category: "other" },
  "060": { category: "other" },
  "062": { category: "other" },
  "063": { category: "late_fee" },
  "064": { category: "late_fee" },
  "066": { category: "late_fee" },
  "067": { category: "late_fee" },
  "069": { category: "other" },
  "111": { category: "petition" },
  "121": { category: "late_fee" },
  "122": { category: "late_fee" },
  "123": {
    category: "late_fee",
    notes:
      "Percentage fee: 50% of the late-paid fee. The EPO feed lists 0.00 because the amount varies.",
  },
  "131": { category: "other" },
  "141": { category: "other" },
  "222": { category: "excess_pages", condition: perPage(30, "sheets_over") },
  "224": { category: "other" },
  "225": { category: "filing" },
  "316": {
    category: "other",
    notes: "A reduction of the PCT international filing fee, not a charge.",
  },
  "318": {
    category: "other",
    notes: "A reduction of the PCT international filing fee, not a charge.",
  },
  "319": {
    category: "other",
    notes: "A reduction of the PCT international filing fee, not a charge.",
  },
  "400": { category: "late_fee" },
  "501": { category: "excess_pages", condition: perPage(35, "pages_over") },
  "520": { category: "excess_pages", condition: perPage(35, "pages_over") },
  "552": { category: "filing" },
  "553": { category: "filing" },
  "554": { category: "filing" },
  "555": { category: "filing" },
  "999": { category: "other" },
  ...Object.fromEntries(
    range(403, 410).map((n) => [code(n), { category: "designation" as const }]),
  ),
  ...Object.fromEntries(
    range(420, 425).map((n) => [code(n), { category: "designation" as const }]),
  ),
  ...Object.fromEntries(
    range(450, 455).map((n) => [code(n), { category: "late_fee" as const }]),
  ),
  // EP application renewal fees start in year 3: 033-050, late fees 093-110.
  ...Object.fromEntries(
    range(33, 50).map((n) => [
      code(n),
      { category: "renewal" as const, year: n - 30 },
    ]),
  ),
  ...Object.fromEntries(
    range(93, 110).map((n) => [
      code(n),
      { category: "late_fee" as const, year: n - 90 },
    ]),
  ),
};
const claimsCondition = (description: string): FeeCondition | undefined => {
  if (/\b16th\b/.test(description))
    return {
      trigger: "claims_over",
      threshold: 15,
      per_unit: true,
      description: "Per claim from the 16th to the 50th.",
    };
  if (/\b51st\b/.test(description))
    return {
      trigger: "claims_over",
      threshold: 50,
      per_unit: true,
      description: "Per claim from the 51st.",
    };
  return undefined;
};

/** Unitary Patent fee codes: renewals 732-750 (years 2-20), late fees 752-770. */
const UP_RULES: Record<string, CodeRule> = {
  "701": { category: "late_fee" },
  "713": { category: "petition" },
  "771": { category: "other" },
  ...Object.fromEntries(
    range(732, 750).map((n) => [
      code(n),
      { category: "renewal" as const, year: n - 730 },
    ]),
  ),
  ...Object.fromEntries(
    range(752, 770).map((n) => [
      code(n),
      {
        category: "late_fee" as const,
        year: n - 750,
        condition: {
          trigger: "late_days" as const,
          threshold: 0,
          per_unit: false,
          description:
            "Paid within the six-month period under Rule 13(3) UPR; 50% of the renewal fee.",
        },
      },
    ]),
  ),
};
const isUnitary = (feeCode: string) =>
  feeCode === "701" || feeCode === "713" || /^7[3-7]\d$/.test(feeCode);

interface Row {
  code: string;
  label: string;
  description: string;
  amount: string;
}
/** Flatten the tree: priced parents and priced children, children labeled with their parent. */
function rows(
  nodes: FeeNode[],
  parent?: { code: string; label: string },
): Row[] {
  return nodes.flatMap((node) => {
    const description = (node.data.feeDescription ?? "").trim();
    const feeCode = node.data.feeCode || parent?.code || null;
    const label = parent ? `${parent.label} - ${description}` : description;
    const own: Row[] =
      node.data.amount !== null && feeCode
        ? [
            {
              code: feeCode,
              label,
              description,
              amount: parseEuroAmount(node.data.amount),
            },
          ]
        : [];
    return [
      ...own,
      ...rows(
        node.children,
        feeCode ? { code: feeCode, label: description } : parent,
      ),
    ];
  });
}
function item(
  row: Row,
  rules: Record<string, CodeRule>,
  sourceUrl: string,
): FeeItem {
  const rule = rules[row.code];
  const condition =
    rule?.condition ??
    (rule?.category === "excess_claims"
      ? claimsCondition(row.description)
      : undefined);
  return {
    code: row.code,
    label: row.label,
    category: rule?.category ?? "other",
    rights: ["patent"],
    amount: row.amount,
    currency: "EUR",
    tier: "none",
    year: rule?.year ?? null,
    condition: condition ?? null,
    source_url: sourceUrl,
    notes: rule?.notes ?? null,
  };
}
function coverage(fees: FeeItem[], years: number[]) {
  const present = new Set(
    fees.filter((fee) => fee.category === "renewal").map((fee) => fee.year),
  );
  const missing = years.filter((year) => !present.has(year));
  return missing.length
    ? {
        status: "partial" as const,
        missing_categories: [],
        missing_years: missing,
        notes: null,
      }
    : {
        status: "complete" as const,
        missing_categories: [],
        missing_years: [],
        notes: `Renewal years ${years[0]}-${years.at(-1)} present in the source.`,
      };
}

/** Fetches the EPO fee feed and projects the EPC and Unitary Patent schedules. */
export class EpoFeesClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://fees.apps.epo.org",
      sourceName: EPO_FEES_SOURCE,
      headers: { accept: "application/json" },
    });
  }
  private async feed(options: TransportRequestOptions) {
    const result = await this.http.json("GET", BFF_PATH, {
      ...options,
      searchParams: { language: "EN", currency: "EUR" },
    });
    const parsed = z.array(NodeSchema).min(1).safeParse(result.data);
    if (!parsed.success)
      throw new ApiError(
        "EPO fees feed changed shape; the schedule was not parsed.",
        result.status,
        "INVALID_RESPONSE",
      );
    if (parsed.data.some((node) => node.data.validUntil))
      throw new ApiError(
        "EPO fees feed now carries validUntil dates; review effective-date handling before use.",
        result.status,
        "INVALID_RESPONSE",
      );
    return { rows: rows(parsed.data), provenance: result.provenance };
  }
  private schedule(
    input: Omit<
      FeeSchedule,
      | "key"
      | "currency"
      | "right"
      | "issuing_body"
      | "provenance"
      | "effective_date"
    >,
    provenance: Awaited<ReturnType<EpoFeesClient["feed"]>>["provenance"],
  ): FeeSchedule {
    return FeeScheduleSchema.parse({
      ...input,
      key: `${input.jurisdiction}/${input.office_code}/patent`,
      right: "patent",
      currency: "EUR",
      issuing_body: "European Patent Office",
      effective_date: null,
      provenance: {
        ...provenance,
        as_of_status: "effective date not published by the office",
        effective_date: null,
      },
    });
  }
  /** Fees under the EPC and the PCT for EPO procedures, excluding Unitary Patent fees. */
  async getEpcSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const feed = await this.feed(options);
    const selected = feed.rows.filter((row) => !isUnitary(row.code));
    const fees = selected.map((row) => item(row, EPC_RULES, EPO_FEES_PAGE));
    const unmapped = [
      ...new Set(
        selected.filter((row) => !EPC_RULES[row.code]).map((row) => row.code),
      ),
    ];
    return this.schedule(
      {
        jurisdiction: "EP",
        office_code: "EPO",
        source_url: EPO_FEES_PAGE,
        statutory_basis:
          "Rules relating to Fees under the EPC; set by the EPO Administrative Council.",
        fees,
        recurring_fee_coverage: coverage(fees, range(3, 20)),
        unmapped_codes: unmapped,
        notes:
          "From the EPO Schedule of Fees feed (https://fees.apps.epo.org/prod/bff/api/fees), which publishes no effective date. EP application renewal fees are codes 033-050 (years 3-20) with late-payment fees 093-110. Unitary Patent fees are in the EPO-UP schedule. Fee reductions under Rule 7a EPC (micro-entities) are not applied.",
      },
      feed.provenance,
    );
  }
  /** Unitary Patent fees from the same feed: renewals for years 2-20 and their 50% late fees. */
  async getUnitaryPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const feed = await this.feed(options);
    const selected = feed.rows.filter((row) => isUnitary(row.code));
    const fees = selected.map((row) =>
      item(row, UP_RULES, UNITARY_PATENT_FEES_URL),
    );
    const unmapped = [
      ...new Set(
        selected.filter((row) => !UP_RULES[row.code]).map((row) => row.code),
      ),
    ];
    return this.schedule(
      {
        jurisdiction: "UP",
        office_code: "EPO-UP",
        source_url: UNITARY_PATENT_FEES_URL,
        statutory_basis:
          "Article 2, Rules relating to Fees for Unitary Patent Protection; Rule 13, Rules relating to Unitary Patent Protection.",
        fees,
        recurring_fee_coverage: coverage(fees, range(2, 20)),
        unmapped_codes: unmapped,
        notes:
          "Unitary Patent codes from the EPO Schedule of Fees feed. Renewal fees are due only for years after the calendar year in which grant is mentioned; Rule 13 UPR governs due dates and the six-month late period. The 15% licence-of-right reduction is not applied.",
      },
      feed.provenance,
    );
  }
}

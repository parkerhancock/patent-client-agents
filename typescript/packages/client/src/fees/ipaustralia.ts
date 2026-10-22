import { parseHTML } from "linkedom";
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
 * IP Australia publishes patent fees on two HTML pages: procedural fees in
 * small "Action | Fee" tables on the timeframes-and-fees page, and the
 * renewal ladder on the renew-my-IP page. The Patents Regulations 1991,
 * Schedule 7, is the legal source; neither page carries fee item numbers.
 */
export const IPAU_FEES_SOURCE = "IP Australia patent fees";
export const IPAU_FEES_URL =
  "https://www.ipaustralia.gov.au/patents/timeframes-and-fees";
export const IPAU_RENEWAL_FEES_URL =
  "https://www.ipaustralia.gov.au/manage-my-ip/how-to-renew-my-ip-right";
const FEES_PATH = "/patents/timeframes-and-fees";
const RENEWAL_PATH = "/manage-my-ip/how-to-renew-my-ip-right";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(
    `IP Australia fee schedule: ${message}`,
    200,
    "INVALID_RESPONSE",
  );

const squash = (text: string | null | undefined) =>
  (text ?? "").replace(/[\s ]+/g, " ").trim();

/** "$1100" / "$1,100" -> "1100.00". */
export function parseAudAmount(raw: string): string {
  const value = raw.replace(/^\$\s*/, "").trim();
  if (!/^\d{1,3}(?:,\d{3})*$|^\d+$/.test(value))
    throw invalid(`unrecognized amount ${raw.slice(0, 20)}`);
  return `${value.replaceAll(",", "")}.00`;
}

interface Table {
  /** Nearest heading (Python's code prefix) and the enclosing step heading. */
  heading: string;
  step: string;
  rows: string[][];
}

/** Tables with their headings, in document order. */
function tables(html: string): { tables: Table[]; text: string } {
  const document = parseHTML(html).document as unknown as Document;
  const main = document.querySelector("main") ?? document.body;
  const found: Table[] = [];
  let step = "";
  let heading = "";
  for (const element of Array.from(
    main?.querySelectorAll("h2, h3, h4, table") ?? [],
  )) {
    const tag = element.tagName.toLowerCase();
    if (tag === "h2" || tag === "h3") {
      step = squash(element.textContent);
      heading = step;
    } else if (tag === "h4") heading = squash(element.textContent);
    else
      found.push({
        heading,
        step,
        rows: Array.from(element.querySelectorAll("tr"))
          .map((tr) =>
            Array.from(tr.querySelectorAll("td")).map((td) =>
              squash(td.textContent),
            ),
          )
          .filter((cells) => cells.length >= 2 && cells[0] && cells[1]),
      });
  }
  return { tables: found, text: squash(main?.textContent) };
}

/** Python's slug: lowercase, non-alphanumerics to "-", trimmed, then cut. */
const slug = (text: string, length: number) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, length);
const code = (heading: string, label: string) => {
  const prefix = slug(heading, 15);
  return prefix ? `au-${prefix}-${slug(label, 50)}` : `au-${slug(label, 50)}`;
};

const claimsOver = (threshold: number, description: string): FeeCondition => ({
  trigger: "claims_over",
  threshold,
  per_unit: true,
  description,
});
const perMonth: FeeCondition = {
  trigger: "late_days",
  threshold: null,
  per_unit: true,
  description: "Per month or part of a month.",
};
const notOnline: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description: "Filed by post or paid other than through online services.",
};
const AFTER_2024 = "Examination requested on or after 1 October 2024.";
const BEFORE_2024 = "Examination requested before 1 October 2024.";

interface Rule {
  pattern: RegExp;
  category: FeeCategory;
  /** Which amount in the fee cell: the first, or the per-claim one after "plus". */
  perClaim?: boolean;
  condition?: FeeCondition;
  notes?: string;
}
const RULES: Rule[] = [
  { pattern: /^Provisional patent application$/, category: "filing" },
  { pattern: /^International-type search request/, category: "search" },
  { pattern: /^Standard patent application$/, category: "filing" },
  { pattern: /^Preliminary search and opinion/, category: "search" },
  {
    pattern: /^Error or omission/,
    category: "extension",
    condition: perMonth,
  },
  { pattern: /^Circumstances beyond the control/, category: "extension" },
  {
    pattern: /^Circumstances where due care/,
    category: "extension",
    condition: perMonth,
  },
  { pattern: /^Examination request$/, category: "examination" },
  { pattern: /^Amend standard patent specification/, category: "other" },
  {
    pattern: /^Examination of more than 20 but fewer than 31 claims$/,
    category: "excess_claims",
    condition: claimsOver(20, "Per claim from the 21st to the 30th."),
    notes: `Charged at the first examination report. ${AFTER_2024}`,
  },
  {
    pattern: /^Examination of more than 30 claims$/,
    category: "excess_claims",
    condition: claimsOver(30, "Per claim over 30."),
    notes: `Charged at the first examination report, plus the fee for claims 21-30. ${AFTER_2024}`,
  },
  {
    pattern: /^Standard patent acceptance \(mandatory\) up to 20 claims$/,
    category: "grant",
  },
  {
    pattern: /^If the specification was proposed to contain 21 to 30 claims/,
    category: "excess_claims",
    perClaim: true,
    condition: claimsOver(20, "Per claim from the 21st to the 30th."),
    notes: `Charged at acceptance with the acceptance fee, for the most claims considered in examination, less claim fees paid at the first report. ${AFTER_2024}`,
  },
  {
    pattern: /^If the specification was proposed to contain 31 or more claims/,
    category: "excess_claims",
    perClaim: true,
    condition: claimsOver(30, "Per claim over 30."),
    notes: `Charged at acceptance with the acceptance fee and the fee for claims 21-30 (together the published $1550 base), less claim fees paid at the first report. ${AFTER_2024}`,
  },
  {
    pattern: /^If the specification contains 21 to 30 claims at acceptance$/,
    category: "excess_claims",
    condition: claimsOver(20, "Per claim from the 21st to the 30th."),
    notes: `Charged at acceptance. ${BEFORE_2024}`,
  },
  {
    pattern: /^If the specification contains 31 or more claims at acceptance$/,
    category: "excess_claims",
    condition: claimsOver(30, "Per claim over 30."),
    notes: `Charged at acceptance, plus the fee for claims 21-30. ${BEFORE_2024}`,
  },
  {
    pattern: /^Increase claims in the complete specification/,
    category: "excess_claims",
    condition: claimsOver(20, "Per claim added beyond 20."),
    notes: "Voluntary amendment after acceptance.",
  },
  { pattern: /^Re-examination request$/, category: "other" },
  { pattern: /^Copy of /, category: "other" },
  { pattern: /^Expedited post$/, category: "other" },
];

/** Procedural fees from the timeframes-and-fees page. */
export function ipaustraliaProceduralFees(html: string): {
  fees: FeeItem[];
  unmapped: string[];
  text: string;
} {
  const { tables: found, text } = tables(html);
  const fees: FeeItem[] = [];
  const unmapped: string[] = [];
  const seen = new Set<string>();
  for (const table of found) {
    const postal = /^Postal/i.test(table.heading);
    for (const [label = "", cell = ""] of table.rows) {
      if (/^Action$|^Document request$/.test(label)) continue;
      const rule = RULES.find((candidate) => candidate.pattern.test(label));
      if (!rule) {
        unmapped.push(label);
        continue;
      }
      const amounts = [...cell.matchAll(/\$\s*([\d,]+)/g)].map(
        (match) => match[1] as string,
      );
      const raw = rule.perClaim ? amounts[1] : amounts[0];
      if (!raw) throw invalid(`no amount for "${label.slice(0, 40)}".`);
      const amount = parseAudAmount(raw);
      const feeCode = code(table.heading, label);
      const key = `${feeCode}|${amount}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const context = [table.step, table.heading]
        .filter((part, i, all) => part && all.indexOf(part) === i)
        .join(" - ");
      fees.push({
        code: feeCode,
        label,
        category: rule.category,
        rights: ["patent"],
        amount,
        currency: "AUD",
        tier: "none",
        year: null,
        condition: postal ? notOnline : (rule.condition ?? null),
        source_url: IPAU_FEES_URL,
        notes:
          [
            `IP Australia section: ${context}.`,
            `Published fee: ${cell}.`,
            rule.notes,
          ]
            .filter(Boolean)
            .join(" ") || null,
      });
    }
  }
  return { fees, unmapped, text };
}

const ORDINAL = /^(\d+)(?:st|nd|rd|th) anniversary/;

/** Standard patent renewal fees (online and other payment), plus the grace-period fee. */
export function ipaustraliaRenewalFees(html: string): FeeItem[] {
  const { tables: found, text } = tables(html);
  const table = found.find((candidate) =>
    /^Standard patent renewal fees/i.test(candidate.heading),
  );
  if (!table) throw invalid("the standard patent renewal table was not found.");
  const fees: FeeItem[] = [];
  for (const [label = "", online = "", other = ""] of table.rows) {
    const ordinal = ORDINAL.exec(label);
    if (!ordinal) continue;
    const year = Number(ordinal[1]);
    const pharma = /pharmaceutical/i.test(label)
      ? "Only for pharmaceutical patents whose term has been extended."
      : null;
    const base = {
      label: `Standard patent renewal fee, ${label}`,
      category: "renewal" as const,
      rights: ["patent" as const],
      currency: "AUD",
      tier: "none" as const,
      year,
      source_url: IPAU_RENEWAL_FEES_URL,
    };
    fees.push({
      ...base,
      code: `au-standard-patent-online-renewal-y${year}`,
      amount: parseAudAmount(online),
      condition: null,
      notes: ["Paid through online services.", pharma]
        .filter(Boolean)
        .join(" "),
    });
    if (other)
      fees.push({
        ...base,
        code: `au-standard-patent-other-renewal-y${year}`,
        amount: parseAudAmount(other),
        condition: notOnline,
        notes: ["Paid other than through online services.", pharma]
          .filter(Boolean)
          .join(" "),
      });
  }
  const grace =
    /renew your patent at an extra cost of \$(\d+) for each month/.exec(text);
  if (!grace)
    throw invalid("the patent renewal grace-period fee was not found.");
  fees.push({
    code: "au-patent-renewal-grace-period",
    label: "Late renewal in the six-month grace period",
    category: "late_fee",
    rights: ["patent"],
    amount: parseAudAmount(grace[1] as string),
    currency: "AUD",
    tier: "none",
    year: null,
    condition: perMonth,
    source_url: IPAU_RENEWAL_FEES_URL,
    notes: "Per month of the grace period in which the renewal fee is paid.",
  });
  return fees;
}

/** Fetches IP Australia's fee and renewal pages and projects the patent schedule. */
export class IpAustraliaFeesClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.ipaustralia.gov.au",
      sourceName: IPAU_FEES_SOURCE,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  /** Standard and provisional patent fees, with the renewal ladder for years 4-24. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const [page, renewalPage] = await Promise.all([
      this.http.text("GET", FEES_PATH, options),
      this.http.text("GET", RENEWAL_PATH, options),
    ]);
    const procedural = ipaustraliaProceduralFees(page.data);
    if (procedural.fees.length < 15)
      throw invalid(`only ${procedural.fees.length} procedural fees.`);
    const renewals = ipaustraliaRenewalFees(renewalPage.data);
    const fees = [...procedural.fees, ...renewals];
    const present = new Set(
      renewals
        .filter((fee) => fee.category === "renewal")
        .map((fee) => fee.year),
    );
    const years = Array.from({ length: 21 }, (_, i) => i + 4);
    const missing = years.filter((year) => !present.has(year));
    // The page dates the current claim fees from the 1 October 2024 fee changes.
    const effective = /1 October 2024/.test(procedural.text)
      ? "2024-10-01"
      : null;
    return FeeScheduleSchema.parse({
      key: "AU/IPAU/patent",
      jurisdiction: "AU",
      issuing_body: "IP Australia",
      office_code: "IPAU",
      right: "patent",
      currency: "AUD",
      effective_date: effective,
      source_url: IPAU_FEES_URL,
      statutory_basis: "Patents Regulations 1991 (Cth), Schedule 7.",
      fees,
      recurring_fee_coverage: missing.length
        ? {
            status: "partial",
            missing_categories: [],
            missing_years: missing,
            notes: null,
          }
        : {
            status: "complete",
            missing_categories: [],
            missing_years: [],
            notes:
              "Standard patent renewals for anniversary years 4-19, and years 20-24 for extended pharmaceutical patents, each paid online or by other means.",
          },
      unmapped_codes: procedural.unmapped,
      notes:
        "Procedural fees from the timeframes-and-fees page and the standard patent renewal ladder from the renewal page. Each renewal year has an online fee and a higher fee for other payment methods (paper_filing condition); postal application fees carry the same condition. Claim fees depend on when examination was requested (before or on/after 1 October 2024); the notes say which. Innovation patent renewals (2nd to 7th anniversaries, for innovation patents still in force) are not included.",
      provenance: {
        ...page.provenance,
        as_of_status: effective
          ? "the pages publish no schedule date; 2024-10-01 is when the current claim fees took effect"
          : "effective date not published by the office",
        effective_date: effective,
      },
    });
  }
}

import { CachedClient } from "../cache/client.js";
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
  type RecurringFeeCoverage,
} from "./models.js";

/**
 * The UK IPO's guidance "New fees from 1 April 2026" links one official CSV
 * per right listing every fee with its form number and its old and new
 * amount. The CSVs are the source here; the gov.uk per-form pages Python
 * scrapes mostly state no amount. Each CSV is linked as a gov.uk
 * `csv-preview` page whose download is the same path on
 * assets.publishing.service.gov.uk.
 */
export const UKIPO_FEES_SOURCE = "UK IPO fee tables";
export const UKIPO_FEES_GUIDANCE_URL =
  "https://www.gov.uk/government/publications/intellectual-property-office-new-fees-from-1-april-2026/new-fees-from-1-april-2026-for-designs-trade-marks-and-patents";
const ASSET_HOST = "assets.publishing.service.gov.uk";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`UK IPO fee tables: ${message}`, 200, "INVALID_RESPONSE");
const squash = (value: string) => value.replace(/\s+/g, " ").trim();

/** RFC 4180 rows: quoted fields may hold commas, doubled quotes and newlines. */
function csvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i] as string;
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (char === '"') quoted = false;
      else field += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += char;
  }
  if (field || row.length) rows.push([...row, field]);
  return rows.map((cells) => cells.map(squash));
}
/** The trade marks CSV is Windows-1252 (a bare 0xA3 for "£"); the patents CSV is UTF-8 with a BOM. */
function decode(bytes: Uint8Array): string {
  try {
    return new TextDecoder("utf-8", { fatal: true })
      .decode(bytes)
      .replace(/^﻿/, "");
  } catch {
    return new TextDecoder("windows-1252").decode(bytes);
  }
}
/**
 * "£1,070.00" -> "1070.00". The currency sign is not checked: a cassette
 * replay may hold the Windows-1252 pound sign as U+FFFD. Non-amounts
 * ("50% of renewal fee") return null.
 */
export function parseUkipoAmount(raw: string): string | null {
  const match = /^[^\d\s]{0,2}(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})$/.exec(
    raw.trim(),
  );
  return match
    ? `${(match[1] as string).replaceAll(",", "")}.${match[2]}`
    : null;
}
const slug = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60)
    .replace(/-+$/, "");
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

interface Rule {
  match: RegExp;
  category: FeeCategory;
  year?: number;
  condition?: FeeCondition;
  paper?: boolean;
  notes?: string;
}
const paper: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description: "Applies to filings on paper rather than online.",
};
const over = (
  trigger: "claims_over" | "pages_over" | "classes_over",
  threshold: number,
  what: string,
): FeeCondition => ({
  trigger,
  threshold,
  per_unit: true,
  description: `Per ${what} over ${threshold}.`,
});

/** Patent rows other than renewals and SPC annual fees, by label. */
const PATENT_RULES: Rule[] = [
  {
    match: /^Application fee \(if paid on filing\)$/,
    category: "filing",
    paper: true,
  },
  {
    match: /^Application fee \(if paid on filing online\)$/,
    category: "filing",
  },
  {
    match: /^Application fee \(if paid later\)$/,
    category: "filing",
    paper: true,
    notes: "Higher rate when the application fee is not paid on filing.",
  },
  {
    match: /^Application fee \(if paid later online\)$/,
    category: "filing",
    notes: "Higher rate when the application fee is not paid on filing.",
  },
  {
    match: /^Initiation of proceedings before the Comptroller/,
    category: "opposition",
  },
  {
    match: /^Continuation of proceedings before the Comptroller/,
    category: "opposition",
  },
  { match: /^Notice of opposition to proceedings/, category: "opposition" },
  { match: /^Late (?:declaration|claim) of priority$/, category: "late_fee" },
  {
    match: /^Request a search \((?:international|UK) application\)$/,
    category: "search",
    paper: true,
  },
  {
    match: /^Request a search \((?:international|UK) application online ?\)$/,
    category: "search",
  },
  {
    match: /^Excess claims fee \(for each claim over 25\)$/,
    category: "excess_claims",
    condition: over("claims_over", 25, "claim"),
    notes: "Payable with the search request (Form 9A).",
  },
  {
    match: /^Request a further or supplementary search .*\(8\)$/,
    category: "search",
    paper: true,
  },
  {
    match: /^Request a further or supplementary search .* - online$/,
    category: "search",
  },
  {
    match: /^Request for a substantive examination - paper$/,
    category: "examination",
    paper: true,
  },
  {
    match: /^Request for a substantive examination - online$/,
    category: "examination",
  },
  {
    match: /^Excess page fee \(each page of description over 35\)$/,
    category: "excess_pages",
    condition: over("pages_over", 35, "page of description"),
    notes: "Payable with the examination request (Form 10).",
  },
  {
    match: /^Request to reinstate a patent application$/,
    category: "petition",
  },
  { match: /^Application to restore a patent$/, category: "petition" },
  {
    match: /^Request for opinion as to the validity or infringement/,
    category: "petition",
  },
  {
    match: /^Application to register or give notice of rights$/,
    category: "transfer",
  },
  { match: /^Request for an? (?:un)?certified copy/, category: "other" },
  {
    match: /^Grant fee for patent application - per excess claim over 25/,
    category: "excess_claims",
    condition: over("claims_over", 25, "claim"),
    notes: "Payable with the grant fee (Form 34).",
  },
  {
    match:
      /^Grant fee for patent application - per excess description page over 35$/,
    category: "excess_pages",
    condition: over("pages_over", 35, "page of description"),
    notes: "Payable with the grant fee (Form 34).",
  },
  { match: /^Request to be informed of future events/, category: "other" },
  {
    match: /^Request to extend a prescribed time limit$/,
    category: "extension",
  },
  {
    match: /^National processing of international patent \(UK\) application$/,
    category: "filing",
    notes: "PCT national phase entry.",
  },
  {
    match: /^Publication of translation of international application$/,
    category: "translation",
  },
  {
    match: /^Transmit an international application/,
    category: "filing",
    notes: "PCT transmittal fee, the UK IPO acting as receiving office.",
  },
  {
    match: /^Request restoration of the right of priority/,
    category: "petition",
  },
  {
    match: /^Application for grant of a supplementary protection certificate$/,
    category: "filing",
  },
  {
    match: /^Application for declaration of lapse or invalidity/,
    category: "cancellation",
  },
  {
    match: /^Application to extend a supplementary protection certificate$/,
    category: "extension",
  },
];
const perClass = over("classes_over", 1, "class");
const TRADEMARK_RULES: Rule[] = [
  {
    match: /^Apply for a trade mark \(paper application\)$/,
    category: "filing",
    paper: true,
  },
  {
    match: /^Apply for a trade mark \(online application\)$/,
    category: "filing",
  },
  { match: /^Request for expedited examination$/, category: "examination" },
  {
    match: /^Apply for a trade mark \(paper application\) class fee$/,
    category: "excess_classes",
    condition: perClass,
  },
  {
    match: /^Apply for a trade mark \(online application\) class fee$/,
    category: "excess_classes",
    condition: perClass,
  },
  { match: /^Series fee - paper$/, category: "other", paper: true },
  { match: /^Series fee - online$/, category: "other" },
  {
    match: /^Application for additional classes following examination$/,
    category: "excess_classes",
  },
  {
    match: /^Record change of ownership$|^Record partial assignment$/,
    category: "transfer",
  },
  {
    match: /^Renew trade mark registration \(online\)$/,
    category: "renewal",
    year: 10,
  },
  {
    match: /^Renew trade mark registration \(paper\)$/,
    category: "renewal",
    year: 10,
    paper: true,
  },
  {
    match: /^Renew trade mark registration \((?:online|paper)\) class fee$/,
    category: "renewal",
    year: 10,
    condition: perClass,
  },
  { match: /^Late renewal$/, category: "late_fee", year: 10 },
  {
    match: /^Restore and renew a registration$/,
    category: "late_fee",
    year: 10,
    notes:
      "Restoration after removal for non-renewal; the renewal fee is also due.",
  },
  { match: /^Request (?:information about|certified copy)/, category: "other" },
  { match: /^Extension of time/, category: "extension" },
  {
    match: /^Appeal to appointed person|^Request statement of reasons/,
    category: "appeal",
  },
  { match: /opposition/i, category: "opposition" },
  {
    match: /^Application to start invalidation|^Application to revoke/,
    category: "cancellation",
  },
  { match: /security interest|licensee|license/i, category: "transfer" },
  { match: /^Request to divide an application$/, category: "other" },
  {
    match: /^Regulations governing|^Application to amend the regulations/,
    category: "other",
  },
  {
    match: /^Right Start Application - Stage \d Additonal Class$/,
    category: "excess_classes",
    condition: perClass,
  },
  { match: /^Right Start Application - Stage \d$/, category: "filing" },
  {
    match: /^Application to register an International trade mark$/,
    category: "madrid",
  },
  { match: /^Renewal of an international registration$/, category: "madrid" },
];

interface Row {
  label: string;
  form: string;
  amount: string | null;
  section: string;
}
function tableRows(text: string, header: RegExp): Row[] {
  const out: Row[] = [];
  let section = "";
  for (const cells of csvRows(text)) {
    const [label = "", form = "", , fee = ""] = cells;
    if (!cells.some(Boolean)) continue;
    if (/^Form$/.test(form) && /^New Fee$/.test(fee)) {
      section = label;
      continue;
    }
    if (!section) throw invalid("the CSV header row is missing.");
    out.push({ label, form, amount: parseUkipoAmount(fee), section });
  }
  if (!out.length || !header.test(out[0]?.section ?? ""))
    throw invalid("the CSV is not the expected fee table.");
  return out;
}

interface Built {
  fees: FeeItem[];
  omitted: string[];
  unmapped: string[];
}
function build(
  rows: Row[],
  right: "patent" | "trademark",
  sourceUrl: string,
  special: (
    row: Row,
  ) => Omit<FeeItem, "rights" | "currency" | "tier" | "source_url"> | null,
  rules: Rule[],
): Built {
  const prefix = right === "patent" ? "uk-patent" : "uk-tm";
  const byForm = new Map<string, number>();
  for (const row of rows)
    if (row.form) byForm.set(row.form, (byForm.get(row.form) ?? 0) + 1);
  const fees: FeeItem[] = [];
  const omitted: string[] = [];
  const unmapped: string[] = [];
  const codes = new Set<string>();
  for (const row of rows) {
    if (row.amount === null) {
      omitted.push(row.label);
      continue;
    }
    const base = special(row);
    if (base) {
      fees.push({
        ...base,
        rights: [right],
        currency: "GBP",
        tier: "none",
        source_url: sourceUrl,
      });
      continue;
    }
    const form = slug(row.form);
    const stem = row.form
      ? (byForm.get(row.form) ?? 0) > 1
        ? `${prefix}-form-${form}-${slug(row.label)}`
        : `${prefix}-form-${form}`
      : `${prefix}-${slug(row.label)}`;
    let code = stem;
    for (let n = 2; codes.has(code); n++) code = `${stem}-${n}`;
    codes.add(code);
    const rule = rules.find((candidate) => candidate.match.test(row.label));
    if (!rule) unmapped.push(code);
    const notes = [
      row.form ? `UK IPO form ${row.form}.` : null,
      right === "trademark" ? `Section: ${row.section}.` : null,
      rule?.notes,
      rule?.year === 10
        ? "Registrations renew every 10 years; stored as year 10."
        : null,
    ].filter(Boolean);
    fees.push({
      code,
      label: row.label,
      category: rule?.category ?? "other",
      rights: [right],
      amount: row.amount,
      currency: "GBP",
      tier: "none",
      year: rule?.year ?? null,
      condition: rule?.condition ?? (rule?.paper ? paper : null),
      source_url: sourceUrl,
      notes: notes.join(" ") || null,
    });
  }
  return { fees, omitted, unmapped };
}

/** Renewal, late-renewal and SPC annual rows, which carry a year or month in the label. */
function patentSpecial(row: Row) {
  const amount = row.amount as string;
  const renewal = /^Renewal year (\d+)$/.exec(row.label);
  if (renewal)
    return {
      code: `uk-patent-renewal-y${renewal[1]}`,
      label: `Patent renewal fee, year ${renewal[1]}`,
      category: "maintenance" as const,
      amount,
      year: Number(renewal[1]),
      condition: null,
      notes:
        "Form 12. Ordinary renewal fee; the licence-of-right 50% reduction and late-renewal fees are separate.",
    };
  const late = /^Late renewal month (\d+)$/.exec(row.label);
  if (late)
    return {
      code: `uk-patent-late-renewal-m${late[1]}`,
      label: `Late renewal fee, month ${late[1]} after the due date`,
      category: "late_fee" as const,
      amount,
      year: null,
      condition: {
        trigger: "late_days" as const,
        threshold: null,
        per_unit: false,
        description: `Paid in month ${late[1]} of the six-month late-renewal period, in addition to the renewal fee.`,
      },
      notes: "Form 12.",
    };
  const spc = /^SPC (late payment )?fee \(Year (\d)\)$/.exec(row.label);
  if (spc)
    return {
      code: `uk-patent-spc${spc[1] ? "-late" : ""}-y${spc[2]}`,
      label: row.label,
      category: spc[1] ? ("late_fee" as const) : ("other" as const),
      amount,
      year: Number(spc[2]),
      condition: null,
      notes:
        "Form SP2. Annual fee for year N of a supplementary protection certificate's term; not a patent renewal.",
    };
  return null;
}

function maintenanceCoverage(fees: FeeItem[]): RecurringFeeCoverage {
  const present = new Set(
    fees.filter((fee) => fee.category === "maintenance").map((fee) => fee.year),
  );
  const missing = Array.from({ length: 16 }, (_, i) => i + 5).filter(
    (year) => !present.has(year),
  );
  return missing.length
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
          "Ordinary renewal fees for years 5-20. Licence-of-right reductions and late fees are separate.",
      };
}

/** Fetches the UK IPO's official fee CSVs for patents and trade marks. */
export class UkipoFeesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  /** gov.uk serves the CSV files from a separate asset host. */
  private readonly assets: GenericHttpTransport;
  private pending: Promise<{
    links: Map<string, string>;
    effective: string;
  }> | null = null;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.gov.uk",
      sourceName: UKIPO_FEES_SOURCE,
      cache: { name: "ukipo_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
    this.assets = new GenericHttpTransport({
      ...options,
      baseUrl: `https://${ASSET_HOST}`,
      sourceName: UKIPO_FEES_SOURCE,
      cache: { name: "ukipo_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: { accept: "text/csv", "user-agent": USER_AGENT },
    });
  }
  /** The guidance page: its effective-date statement and the CSV link per right. */
  private guidance(options: TransportRequestOptions) {
    this.pending ??= (async () => {
      const page = await this.http.text(
        "GET",
        new URL(UKIPO_FEES_GUIDANCE_URL).pathname,
        options,
      );
      const text = squash(page.data.replace(/<[^>]+>/g, " "));
      const date =
        /new fees will take effect on (\d{1,2}) ([A-Z][a-z]+) (\d{4})/.exec(
          text,
        );
      const month = date ? MONTHS.indexOf(date[2] as string) + 1 : 0;
      if (!date || !month)
        throw invalid("the effective-date statement is missing.");
      const links = new Map<string, string>();
      for (const match of page.data.matchAll(
        /<a[^>]*href="https:\/\/www\.gov\.uk\/csv-preview\/([0-9a-f]+\/[^"]+\.csv)"[^>]*>([^<]+)<\/a>/g,
      ))
        links.set(
          squash(match[2] as string),
          `https://${ASSET_HOST}/media/${match[1]}`,
        );
      return {
        links,
        effective: `${date[3]}-${String(month).padStart(2, "0")}-${(date[1] as string).padStart(2, "0")}`,
      };
    })().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }
  private async table(title: string, options: TransportRequestOptions) {
    const guide = await this.guidance(options);
    const url = guide.links.get(title);
    if (!url)
      throw invalid(`the "${title}" link is missing from the guidance page.`);
    const result = await this.assets.bytes(
      "GET",
      new URL(url).pathname,
      options,
    );
    return {
      url,
      text: decode(result.data),
      effective: guide.effective,
      provenance: {
        ...result.provenance,
        as_of_status: `new fees effective ${guide.effective}, as the UK IPO guidance states`,
        effective_date: guide.effective,
      },
    };
  }
  private schedule(
    right: "patent" | "trademark",
    table: Awaited<ReturnType<UkipoFeesClient["table"]>>,
    built: Built,
    extra: {
      statutory_basis: string;
      coverage: RecurringFeeCoverage;
      notes: string;
    },
  ): FeeSchedule {
    if (!built.fees.length) throw invalid(`no ${right} fees parsed.`);
    const omitted = built.omitted.length
      ? ` Rows without a fixed amount are omitted: ${built.omitted.join("; ")}.`
      : "";
    return FeeScheduleSchema.parse({
      key: `GB/UKIPO/${right}`,
      jurisdiction: "GB",
      issuing_body: "UK Intellectual Property Office",
      office_code: "UKIPO",
      right,
      currency: "GBP",
      effective_date: table.effective,
      source_url: UKIPO_FEES_GUIDANCE_URL,
      statutory_basis: extra.statutory_basis,
      fees: built.fees,
      recurring_fee_coverage: extra.coverage,
      unmapped_codes: built.unmapped,
      notes: `${extra.notes} Amounts are the "New Fee" column of the official CSV (${table.url}); the "Current Fee" column holds the fees before ${table.effective}, which still apply in the transitional cases the guidance describes. No entity-size tiers.${omitted}`,
      provenance: table.provenance,
    });
  }
  /** Patent and SPC fees, including the ordinary renewal ladder for years 5-20. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const table = await this.table("Patents fees table", options);
    const built = build(
      tableRows(table.text, /^Patents$/),
      "patent",
      table.url,
      patentSpecial,
      PATENT_RULES,
    );
    return this.schedule("patent", table, built, {
      statutory_basis:
        "Patents Act 1977; The Patents (Fees) Rules 2007, as amended by The Intellectual Property Fees (Miscellaneous Amendments, Revocation and Transitional Provisions) Rules 2026.",
      coverage: maintenanceCoverage(built.fees),
      notes:
        "Renewal fees are maintenance fees by year (5-20), as in Python. Late-renewal fees are by month of lateness. SPC annual fees carry the SPC year but are not patent renewals. Rows with an online and a paper rate are separate fees; paper rows carry a paper_filing condition.",
    });
  }
  /** Domestic and international trade mark fees. */
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const table = await this.table("Trade marks fees table", options);
    const built = build(
      tableRows(table.text, /^Trade Marks - Domestic$/),
      "trademark",
      table.url,
      () => null,
      TRADEMARK_RULES,
    );
    return this.schedule("trademark", table, built, {
      statutory_basis:
        "Trade Marks Act 1994; The Trade Marks (Fees) Rules 2008, as amended by The Intellectual Property Fees (Miscellaneous Amendments, Revocation and Transitional Provisions) Rules 2026.",
      coverage: built.fees.some(
        (fee) => fee.category === "renewal" && fee.year === 10,
      )
        ? {
            status: "complete",
            missing_categories: [],
            missing_years: [],
            notes:
              "Registrations renew every 10 years; year 10 stands for each renewal.",
          }
        : {
            status: "partial",
            missing_categories: [],
            missing_years: [10],
            notes: null,
          },
      notes:
        "An application fee covers one class; class fees are per additional class. International rows are the UK IPO's own handling fees; WIPO's fees are in the WIPO-MADRID schedule.",
    });
  }
}

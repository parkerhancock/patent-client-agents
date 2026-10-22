import { pdfPageTexts } from "../runtime/pdf.js";
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
 * DPMA publishes its complete schedule only as the PDF "Information
 * Concerning Costs, Fees and Expenses" (form A 9510.1). The English HTML fee
 * page lists annual fees for years 3-6 and refers to the PDF for the rest.
 * Fee numbers are six digits; 31x xxx are patent fees.
 */
export const DPMA_FEES_SOURCE = "DPMA Information Concerning Costs (A 9510.1)";
export const DPMA_FEES_PDF_URL =
  "https://www.dpma.de/docs/english/formulare/allg_eng/a9510_1.pdf";
export const DPMA_FEES_HTML_URL =
  "https://www.dpma.de/english/services/fees/patents/index.html";
const PDF_PATH = "/docs/english/formulare/allg_eng/a9510_1.pdf";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`DPMA fee schedule: ${message}`, 200, "INVALID_RESPONSE");

/** "2 030" -> "2030.00". DPMA writes whole euros with a space as thousands separator. */
export function parseDpmaAmount(raw: string): string {
  const value = raw.trim();
  if (!/^\d{1,3}(?: \d{3})*$/.test(value))
    throw invalid(`unrecognized amount ${value.slice(0, 20)}`);
  return `${value.replaceAll(" ", "")}.00`;
}

export interface DpmaRow {
  code: string;
  description: string;
  /** Null for rows stated as a percentage of other fees (311 100). */
  amount: string | null;
  /** Nearest preceding heading line, for context. */
  heading: string;
  /** The "*" footnote marker after the amount (313 820). */
  footnote: boolean;
}

const CODE_LINE = /^(\d{3}) (\d{3})\s+(.*)$/;
// Amount after a dot leader, optionally followed by a footnote star.
const AMOUNT_TAIL = /\s*\.{2,}[\s.]*(\d{1,3}(?: \d{3})*)(\*)?$/;
const NOISE = [
  /^Number Statement of fees/,
  /^\d{1,2}$/,
  /^\* Note:/,
  /^relation to European patents/,
];

/** Rows of the fee table (all rights), from the line-ordered PDF text. */
export function dpmaRows(pages: string[]): DpmaRow[] {
  const rows: DpmaRow[] = [];
  let open: DpmaRow | null = null;
  let last: DpmaRow | null = null;
  let heading = "";
  let headingOpen = false;
  const setHeading = (line: string) => {
    // Dash lines ("- for electronic filing") qualify only the next row;
    // numbered section titles reset the context.
    if (line.startsWith("-")) return;
    if (/^(?:\d\.|[IVX]+\.|[A-Z]\.)\s/.test(line)) {
      heading = "";
      headingOpen = false;
      return;
    }
    heading = headingOpen ? `${heading} ${line}` : line;
    headingOpen = true;
  };
  const close = (row: DpmaRow, text: string) => {
    const tail = AMOUNT_TAIL.exec(text);
    if (!tail) return false;
    row.description = `${row.description} ${text.slice(0, tail.index)}`.trim();
    row.amount = parseDpmaAmount(tail[1] as string);
    row.footnote = tail[2] === "*";
    return true;
  };
  for (const page of pages) {
    for (const raw of page.split("\n")) {
      const line = raw.replace(/\s+/g, " ").trim();
      if (!line || NOISE.some((pattern) => pattern.test(line))) continue;
      const match = CODE_LINE.exec(line);
      if (match) {
        if (open) rows.push(open);
        headingOpen = false;
        const row: DpmaRow = {
          code: `${match[1]} ${match[2]}`,
          description: "",
          amount: null,
          heading,
          footnote: false,
        };
        if (close(row, match[3] as string)) {
          rows.push(row);
          open = null;
          last = row;
        } else {
          row.description = (match[3] as string).trim();
          open = row;
          last = null;
        }
        continue;
      }
      if (open) {
        // A percentage row (311 100) has no amount; the next heading ends it.
        if (open.description.includes("%") && /^[A-Z]/.test(line)) {
          rows.push(open);
          open = null;
          setHeading(line);
          continue;
        }
        if (close(open, line)) {
          rows.push(open);
          last = open;
          open = null;
        } else open.description = `${open.description} ${line}`;
        continue;
      }
      // "for each additional claim" continues the row whose amount came first.
      if (last && /^[a-z]/.test(line)) {
        last.description = `${last.description} ${line}`;
        continue;
      }
      last = null;
      setHeading(line);
    }
  }
  if (open) rows.push(open);
  return rows.map((row) => ({
    ...row,
    description: row.description.replace(/\s+/g, " ").trim(),
  }));
}

interface Rule {
  category: FeeCategory;
  year?: number;
  condition?: FeeCondition;
  notes?: string | undefined;
}
const claimsOver10: FeeCondition = {
  trigger: "claims_over",
  threshold: 10,
  per_unit: true,
  description: "Per claim over 10.",
};
const lateSurcharge: FeeCondition = {
  trigger: "late_days",
  threshold: 0,
  per_unit: false,
  description:
    "Paid after the due date, within the surcharge period of section 7 (1) PatKostG.",
};
const LICENCE_OF_RIGHT =
  "Licence-of-right rate (declaration of willingness to license, section 23 (1) Patent Act).";
const SPC =
  "Supplementary protection certificate annual fee; stored as year 20 plus the certificate year.";

/** Patent fee numbers mapped to the closed vocabulary. */
function patentRule(code: string): Rule | undefined {
  const fixed: Record<string, Rule> = {
    "311 000": { category: "filing", notes: "Electronic filing." },
    "311 050": {
      category: "excess_claims",
      condition: claimsOver10,
      notes: "Electronic filing.",
    },
    "311 100": {
      category: "filing",
      condition: {
        trigger: "paper_filing",
        threshold: null,
        per_unit: false,
        description: "Applies when the application is filed on paper.",
      },
      notes:
        "Stated as 150% of fees 311 000 and 311 050; the amount is 150% of 311 000 (up to ten claims). Each claim over ten costs 150% of 311 050 on paper.",
    },
    "311 150": {
      category: "filing",
      notes: "International (PCT) application filed with the DPMA.",
    },
    "311 160": { category: "excess_claims", condition: claimsOver10 },
    "311 200": { category: "search" },
    "311 300": { category: "examination" },
    "311 400": { category: "examination" },
    "311 500": {
      category: "filing",
      notes: "Supplementary protection certificate application.",
    },
    "311 600": {
      category: "other",
      notes: "Extension of a supplementary protection certificate's duration.",
    },
    "311 610": {
      category: "other",
      notes: "Extension of a supplementary protection certificate's duration.",
    },
    "312 205": {
      category: "other",
      year: 3,
      notes:
        "Annual fees for years 3 to 5 paid together on the due date of the year-3 fee.",
    },
    "312 206": {
      category: "other",
      year: 3,
      notes: `Annual fees for years 3 to 5 paid together. ${LICENCE_OF_RIGHT}`,
    },
    "312 207": { category: "late_fee", year: 3, condition: lateSurcharge },
    "313 000": { category: "late_fee", notes: "Further processing." },
    "313 200": { category: "other" },
    "313 300": { category: "other" },
    "313 400": { category: "transfer" },
    "313 500": { category: "transfer" },
    "313 600": { category: "opposition" },
    "313 700": {
      category: "other",
      notes: "Limitation or revocation requested by the patentee.",
    },
    "313 800": { category: "translation" },
    "313 810": { category: "translation" },
    "313 820": {
      category: "translation",
      notes:
        "Abolished in 2008 but still applicable to European patents whose grant was published before 1 May 2008.",
    },
    "313 900": {
      category: "other",
      notes: "Transmittal of an international application.",
    },
    "314 100": { category: "translation" },
    "314 200": { category: "search" },
    "315 100": { category: "other" },
    "315 200": { category: "other" },
  };
  if (fixed[code]) return fixed[code];
  const annual = /^312 (\d{2})(\d)$/.exec(code);
  if (!annual) return undefined;
  const step = Number(annual[1]);
  const variant = annual[2] as string;
  // 312 030-312 202: patent years 3-20; 312 210-312 262: SPC years 1-6.
  const year =
    step >= 3 && step <= 20 ? step : step >= 21 && step <= 26 ? step : null;
  if (year === null) return undefined;
  const spc = step >= 21;
  const base = spc ? SPC : undefined;
  if (variant === "0") return { category: "renewal", year, notes: base };
  if (variant === "1")
    return {
      category: "renewal",
      year,
      notes: [base, LICENCE_OF_RIGHT].filter(Boolean).join(" "),
    };
  if (variant === "2")
    return {
      category: "late_fee",
      year,
      condition: lateSurcharge,
      notes: base,
    };
  return undefined;
}

/** Patent fees (31x xxx) from the parsed rows. */
export function dpmaPatentFees(rows: DpmaRow[]): {
  fees: FeeItem[];
  unmapped: string[];
} {
  const patent = rows.filter((row) => row.code.startsWith("31"));
  const unmapped: string[] = [];
  const byCode = new Map(patent.map((row) => [row.code, row]));
  const fees = patent.map((row): FeeItem => {
    const rule = patentRule(row.code);
    if (!rule) unmapped.push(row.code);
    let amount = row.amount;
    if (amount === null) {
      // 311 100: 150% of 311 000.
      const filing = byCode.get("311 000")?.amount;
      if (row.code !== "311 100" || !filing || !/150 %/.test(row.description))
        throw invalid(`fee ${row.code} has no amount.`);
      amount = `${(Number(filing) * 1.5).toFixed(2)}`;
    }
    // Sub-rows ("- in case of ...") read with their parent fee or heading.
    const parent = /^312 20[67]$/.test(row.code)
      ? byCode.get("312 205")
      : /^312 \d{2}[12]$/.test(row.code)
        ? byCode.get(`${row.code.slice(0, 6)}0`)
        : undefined;
    const prefix = parent
      ? parent.description
      : row.description.startsWith("-")
        ? row.heading
        : "";
    const label = (
      prefix
        ? `${prefix} ${row.description}`
        : row.description.replace(/^- /, "")
    )
      .replace(/\s+/g, " ")
      .trim();
    return {
      code: row.code,
      label,
      category: rule?.category ?? "other",
      rights: ["patent"],
      amount,
      currency: "EUR",
      tier: "none",
      year: rule?.year ?? null,
      condition: rule?.condition ?? null,
      source_url: DPMA_FEES_PDF_URL,
      notes: rule?.notes ?? null,
    };
  });
  return { fees, unmapped };
}

/** Fetches DPMA form A 9510.1 and projects the patent schedule. */
export class DpmaFeesClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.dpma.de",
      sourceName: DPMA_FEES_SOURCE,
      headers: { accept: "application/pdf", "user-agent": USER_AGENT },
    });
  }
  /** Patent fees: filing, search, examination, annual fees for years 3-20, SPCs and other requests. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const result = await this.http.bytes("GET", PDF_PATH, options);
    const pages = await pdfPageTexts(result.data);
    const edition = /\(Edition ([A-Z][a-z]+ \d{4})\)/.exec(pages[0] ?? "")?.[1];
    if (!edition) throw invalid("the edition line was not found.");
    const { fees, unmapped } = dpmaPatentFees(dpmaRows(pages));
    if (fees.length < 50) throw invalid(`only ${fees.length} patent fees.`);
    const years = Array.from({ length: 18 }, (_, i) => i + 3);
    const present = new Set(
      fees
        .filter((fee) => fee.category === "renewal" && fee.year !== null)
        .map((fee) => fee.year),
    );
    const missing = years.filter((year) => !present.has(year));
    return FeeScheduleSchema.parse({
      key: "DE/DPMA/patent",
      jurisdiction: "DE",
      issuing_body: "Deutsches Patent- und Markenamt (DPMA)",
      office_code: "DPMA",
      right: "patent",
      currency: "EUR",
      effective_date: null,
      source_url: DPMA_FEES_HTML_URL,
      statutory_basis:
        "Patentkostengesetz (PatKostG), Annex to section 2 (1) (Schedule of Fees); published as form A 9510.1.",
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
              "Annual fees for patent years 3-20 present; supplementary protection certificate years 1-6 are stored as years 21-26.",
          },
      unmapped_codes: unmapped,
      notes: `From form A 9510.1 (edition ${edition}). Only fee numbers 31x xxx (patents and supplementary protection certificates); utility model, trade mark and design fees in the same PDF are not routed. Each annual fee has a licence-of-right row at half the amount (same year) and a late-payment surcharge (late_fee, same year). Supplementary protection certificate annual fees are years 21-26. Fees are whole euros.`,
      provenance: {
        ...result.provenance,
        as_of_status: `form A 9510.1, edition ${edition}; the office publishes no effective date`,
        effective_date: null,
      },
    });
  }
}

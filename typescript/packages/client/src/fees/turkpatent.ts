import { parseHTML } from "linkedom";
import { CachedClient } from "../cache/client.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "../transport.js";
import {
  type EntityTier,
  type FeeCategory,
  type FeeCondition,
  type FeeItem,
  type FeeSchedule,
  FeeScheduleSchema,
  type RecurringFeeCoverage,
} from "./models.js";

/**
 * TÜRKPATENT re-hosts the annual fee tariff (gazetted in the Resmî Gazete
 * each December) as one HTML table per right. Patent rows split the total
 * into the office fee, VAT and stamp duty; trademark and design rows give a
 * single amount. Every row carries a stable fee code (01.01.xx patents,
 * 02.01.xx trademarks, 04.01.xx designs).
 */
export const TURKPATENT_FEES_SOURCE = "TÜRKPATENT fee tariff";
export const TURKPATENT_PATENTS_URL =
  "https://www.turkpatent.gov.tr/patent-islem-ucretleri";
export const TURKPATENT_TRADEMARKS_URL =
  "https://www.turkpatent.gov.tr/marka-islem-ucretleri";
export const TURKPATENT_DESIGNS_URL =
  "https://www.turkpatent.gov.tr/tasarim-islem-ucretleri";
/** The 2026 tariff as gazetted, cited by Python as the version pin. */
const GAZETTE =
  "Resmî Gazete 5. mükerrer 31-12-2025, BİK/TÜRKPATENT 2026/1 (https://www.resmigazete.gov.tr/eskiler/2025/12/20251231M5-37.pdf)";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`TÜRKPATENT fee tariff: ${message}`, 200, "INVALID_RESPONSE");
const squash = (value: string | null | undefined) =>
  (value ?? "").replace(/\s+/g, " ").trim();

/** Turkish notation: "2.402,67" -> "2402.67", "9000" -> "9000.00", "522,3" -> "522.30". */
export function parseTryAmount(raw: string): string {
  const value = raw.replace(/\s*TL$/i, "").trim();
  if (!/^(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?$/.test(value))
    throw invalid(`unrecognized amount ${value.slice(0, 30)}`);
  const [whole = "0", fraction = ""] = value.replaceAll(".", "").split(",");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}
const cents = (amount: string) => Math.round(Number(amount) * 100);
const ordinal = (n: number) =>
  `${n}${n % 10 === 1 && n !== 11 ? "st" : n % 10 === 2 && n !== 12 ? "nd" : n % 10 === 3 && n !== 13 ? "rd" : "th"}`;

type Right = "patent" | "trademark" | "design";
const PREFIX: Record<Right, string> = {
  patent: "01.",
  trademark: "02.",
  design: "04.",
};
const CODE = /^0[124]\.\d{2}\.\d{2}$/;

function table(html: string, right: Right) {
  const document = parseHTML(html).document as unknown as Document;
  const tables = Array.from(document.querySelectorAll("table"));
  if (tables.length !== 1)
    throw invalid(`expected one ${right} table, found ${tables.length}.`);
  const rows = Array.from((tables[0] as Element).querySelectorAll("tr")).map(
    (tr) =>
      Array.from(tr.querySelectorAll("th, td")).map((cell) =>
        squash(cell.textContent),
      ),
  );
  const [header = [], ...body] = rows;
  const expected =
    right === "patent"
      ? /^KOD \| AC[Iİ]KLAMA \| ÜCRET \| KDV \| HARÇ \| TOPLAM TUTAR$/i
      : /^KOD \| AC[Iİ]KLAMA \| (\d{4}) İŞLEM ÜCRETLERİ$/i;
  const match = expected.exec(header.join(" | "));
  if (!match) throw invalid(`the ${right} table header changed.`);
  for (const cells of body) {
    if (cells.length !== header.length || !CODE.test(cells[0] as string))
      throw invalid(`a ${right} row changed shape.`);
    if (!(cells[0] as string).startsWith(PREFIX[right]))
      throw invalid(`a ${right} row has code ${cells[0]}.`);
  }
  if (body.length < 10) throw invalid(`too few ${right} rows.`);
  return { body, tariffYear: match[1] ? Number(match[1]) : null };
}

interface CodeRule {
  category: FeeCategory;
  tier?: EntityTier;
  condition?: FeeCondition;
  notes?: string;
}
const perClass = (
  threshold: number,
  perUnit: boolean,
  description: string,
): FeeCondition => ({
  trigger: "classes_over",
  threshold,
  per_unit: perUnit,
  description,
});
const multiDesign = (
  threshold: number,
  perUnit: boolean,
  description: string,
): FeeCondition => ({
  trigger: "multi_design",
  threshold,
  per_unit: perUnit,
  description,
});
const REDUCED =
  "Reduced rate for natural persons (up to 10 applications) and universities (up to 100 applications).";
const STARTUP =
  "Reduced rate for legal entities holding the Teknogirişim (technology start-up) badge.";

/** Patent codes, mapped explicitly. Codes not listed fall back to `other` and are reported as unmapped. */
const PATENT_RULES: Record<string, CodeRule> = {
  "01.01.01": { category: "filing" },
  "01.01.02": { category: "other", notes: "Per priority claimed." },
  "01.01.03": { category: "publication" },
  "01.01.04": { category: "publication" },
  "01.01.06": { category: "extension" },
  "01.01.07": { category: "other" },
  "01.01.08": { category: "grant" },
  "01.01.09": { category: "grant" },
  "01.01.10": { category: "transfer" },
  "01.01.11": { category: "transfer" },
  "01.01.12": { category: "transfer" },
  "01.01.13": { category: "other" },
  "01.01.14": { category: "transfer" },
  "01.01.15": { category: "transfer" },
  "01.01.17": { category: "other" },
  "01.01.18": { category: "other" },
  "01.01.19": { category: "other" },
  "01.01.41": { category: "filing" },
  "01.01.42": { category: "extension" },
  "01.01.44": { category: "publication" },
  "01.01.45": { category: "publication" },
  "01.01.46": { category: "extension" },
  "01.01.47": { category: "extension" },
  "01.01.48": { category: "search", tier: "small", notes: REDUCED },
  "01.01.49": { category: "search", tier: "large" },
  "01.01.50": { category: "examination", tier: "small", notes: REDUCED },
  "01.01.51": { category: "examination", tier: "large" },
  "01.01.54": { category: "examination" },
  "01.01.56": { category: "search" },
  "01.01.57": { category: "petition" },
  "01.01.58": { category: "extension" },
  "01.01.60": { category: "other" },
  "01.01.64": { category: "search", tier: "large" },
  "01.01.65": { category: "search", tier: "small", notes: STARTUP },
};
/** Annuities 01.01.23-01.01.40 are years 3-20, and the label must say so. */
const annuityYear = (code: string) => {
  const n = Number(code.slice(6));
  return code.startsWith("01.01.") && n >= 23 && n <= 40 ? n - 20 : null;
};
/** Rows whose amount is a formula over the annuity due, or a foreign currency. */
const PATENT_OMITTED: Record<string, string> = {
  "01.01.20":
    "force-majeure annuity surcharge (formula: annuity due + 50% of the annuity due less stamp duty)",
  "01.01.21":
    "late annuity payment (formula: annuity due + 25% of the annuity due less stamp duty)",
  "01.01.43": "PCT receiving-office priority document (30 CHF)",
  "01.01.59": "annuity compensation fee (formula: 1.5 times the fee due)",
};

const TRADEMARK_RULES: Record<string, CodeRule> = {
  "02.01.01": {
    category: "filing",
    notes: "Application fee covering one class.",
  },
  "02.01.02": {
    category: "excess_classes",
    condition: perClass(1, false, "Once, for the second class."),
  },
  "02.01.03": { category: "grant" },
  "02.01.04": { category: "other" },
  "02.01.05": { category: "other" },
  "02.01.06": { category: "transfer" },
  "02.01.07": { category: "transfer" },
  "02.01.08": { category: "transfer" },
  "02.01.09": { category: "transfer" },
  "02.01.10": { category: "transfer" },
  "02.01.14": { category: "other" },
  "02.01.15": { category: "other" },
  "02.01.16": { category: "other" },
  "02.01.17": { category: "opposition" },
  "02.01.18": { category: "other" },
  "02.01.19": { category: "madrid" },
  "02.01.20": { category: "madrid" },
  "02.01.21": { category: "madrid" },
  "02.01.22": { category: "other" },
  "02.01.23": {
    category: "renewal",
    notes:
      "Covers up to two classes; 02.01.32 is charged for each further class.",
  },
  "02.01.24": {
    category: "late_fee",
    notes:
      "Renewal of a mark whose protection has expired (within the grace period); covers up to two classes.",
  },
  "02.01.27": { category: "other" },
  "02.01.28": {
    category: "excess_classes",
    condition: perClass(
      2,
      true,
      "Per class from the third, except 02.01.34 applications.",
    ),
  },
  "02.01.30": { category: "cancellation" },
  "02.01.31": {
    category: "cancellation",
    notes: "A deposit lodged with a cancellation request.",
  },
  "02.01.32": {
    category: "excess_classes",
    condition: perClass(2, true, "Per class from the third, at renewal."),
  },
  "02.01.33": {
    category: "excess_classes",
    condition: perClass(
      2,
      true,
      "Per class from the third, renewing a mark whose protection has expired.",
    ),
  },
  "02.01.34": {
    category: "excess_classes",
    condition: perClass(
      2,
      true,
      "Per class from the third among the 34 goods classes chosen under Class 35 group 5 (retail).",
    ),
  },
  "02.01.35": { category: "madrid" },
};
const TRADEMARK_YEARS: Record<string, number> = {
  "02.01.23": 10,
  "02.01.24": 10,
};

const DESIGN_RULES: Record<string, CodeRule> = {
  "04.01.01": { category: "filing", notes: "Application fee for one design." },
  "04.01.03": {
    category: "publication",
    notes: "Per 8 x 8 cm area published.",
  },
  "04.01.04": { category: "deferment", notes: "Per design." },
  "04.01.05": { category: "renewal", notes: "For one design." },
  "04.01.06": {
    category: "renewal",
    condition: multiDesign(1, true, "Per design after the first."),
  },
  "04.01.07": {
    category: "late_fee",
    notes: "Renewal in the six-month extension period, for one design.",
  },
  "04.01.08": {
    category: "late_fee",
    condition: multiDesign(1, true, "Per design after the first."),
    notes: "Renewal in the six-month extension period.",
  },
  "04.01.09": { category: "transfer" },
  "04.01.10": { category: "transfer" },
  "04.01.11": { category: "transfer" },
  "04.01.12": { category: "transfer" },
  "04.01.14": { category: "transfer" },
  "04.01.15": { category: "other" },
  "04.01.16": { category: "other" },
  "04.01.17": { category: "other" },
};
/** Design protection runs in five-year terms up to 25 years; renewals fall due at years 5, 10, 15 and 20. */
const DESIGN_RENEWAL_YEARS = [5, 10, 15, 20];
const DESIGN_MULTI = "04.01.02";

const base = (
  right: Right,
  code: string,
  label: string,
  amount: string,
  rule: CodeRule | undefined,
  sourceUrl: string,
): FeeItem => ({
  code: `tr-${right === "patent" ? "pat" : right === "trademark" ? "tm" : "des"}-${code}`,
  label,
  category: rule?.category ?? "other",
  rights: [right],
  amount,
  currency: "TRY",
  tier: rule?.tier ?? "none",
  year: null,
  condition: rule?.condition ?? null,
  source_url: sourceUrl,
  notes: rule?.notes ?? null,
});

function patentFees(body: string[][]): {
  fees: FeeItem[];
  omitted: string[];
  unmapped: string[];
} {
  const fees: FeeItem[] = [];
  const omitted: string[] = [];
  const unmapped: string[] = [];
  for (const [code = "", label = "", fee, vat, stamp, total = ""] of body) {
    if (PATENT_OMITTED[code]) {
      omitted.push(`${code} ${PATENT_OMITTED[code]}`);
      continue;
    }
    const amount = parseTryAmount(total);
    const parts = [fee, vat, stamp].map((part) =>
      part ? parseTryAmount(part) : "0.00",
    );
    // The total must equal fee + VAT + stamp duty; anything else means the columns moved.
    if (parts.reduce((sum, part) => sum + cents(part), 0) !== cents(amount))
      throw invalid(`row ${code} total does not equal its components.`);
    const year = annuityYear(code);
    if (
      year !== null &&
      !new RegExp(`^${year}\\.Yıl Sicil Kayıt Ücreti$`, "i").test(label)
    )
      throw invalid(`annuity row ${code} is not labeled year ${year}.`);
    const rule: CodeRule | undefined =
      year !== null ? { category: "renewal" } : PATENT_RULES[code];
    if (!rule) unmapped.push(code);
    const breakdown = `Office fee TRY ${parts[0]}, VAT TRY ${parts[1]}, stamp duty TRY ${parts[2]}.`;
    const item = base(
      "patent",
      code,
      label,
      amount,
      rule,
      TURKPATENT_PATENTS_URL,
    );
    fees.push({
      ...item,
      year,
      notes: [item.notes, breakdown].filter(Boolean).join(" "),
    });
  }
  return { fees, omitted, unmapped };
}

/** "Başvurudaki 2. tasarım için ...: 1674,90TL Başvurudaki 3. 4. ve 5. her bir ...: 318,70 TL ..." */
export function designMultiAmounts(body: string): {
  suffix: string;
  label: string;
  amount: string;
  condition: FeeCondition;
}[] {
  const found = [
    ...body.matchAll(
      /Başvurudaki\s+([\d.\s\p{L}]+?)\s*için[^:]*:\s*((?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?)\s*TL/giu,
    ),
  ];
  if (found.length !== 3)
    throw invalid("the additional-design fee no longer lists three bands.");
  return found.map((match) => {
    const which = match[1] as string;
    const numbers = [...which.matchAll(/\d+/g)].map((n) => Number(n[0]));
    const first = numbers[0] as number;
    const last = numbers.at(-1) as number;
    const open = /fazlası/i.test(which);
    const amount = parseTryAmount(match[2] as string);
    if (open)
      return {
        suffix: `d${first}plus`,
        label: `designs ${first}+`,
        amount,
        condition: multiDesign(
          first - 1,
          true,
          `Per design from the ${ordinal(first)}.`,
        ),
      };
    if (first === last)
      return {
        suffix: `d${first}`,
        label: `designs ${first}`,
        amount,
        condition: multiDesign(first - 1, false, `Once, for design ${first}.`),
      };
    return {
      suffix: `d${first}to${last}`,
      label: `designs ${first}-${last}`,
      amount,
      condition: multiDesign(
        first - 1,
        true,
        `Per design from the ${ordinal(first)} to the ${ordinal(last)}.`,
      ),
    };
  });
}

function simpleFees(
  right: "trademark" | "design",
  body: string[][],
  rules: Record<string, CodeRule>,
  sourceUrl: string,
): { fees: FeeItem[]; unmapped: string[] } {
  const fees: FeeItem[] = [];
  const unmapped: string[] = [];
  for (const [code = "", label = "", amountText = ""] of body) {
    if (right === "design" && code === DESIGN_MULTI) {
      for (const band of designMultiAmounts(amountText))
        fees.push({
          ...base(
            right,
            `${code}-${band.suffix}`,
            `${label} (${band.label})`,
            band.amount,
            { category: "filing", condition: band.condition },
            sourceUrl,
          ),
          notes: amountText,
        });
      continue;
    }
    const rule = rules[code];
    if (!rule) unmapped.push(code);
    const item = base(
      right,
      code,
      label,
      parseTryAmount(amountText),
      rule,
      sourceUrl,
    );
    if (
      right === "design" &&
      (rule?.category === "renewal" || rule?.category === "late_fee")
    ) {
      for (const year of DESIGN_RENEWAL_YEARS)
        fees.push({
          ...item,
          code: `${item.code}-y${year}`,
          year,
          notes: [
            item.notes,
            `Renewal at the end of year ${year}; the same fee applies at each five-year renewal.`,
          ]
            .filter(Boolean)
            .join(" "),
        });
      continue;
    }
    fees.push({ ...item, year: TRADEMARK_YEARS[code] ?? null });
  }
  return { fees, unmapped };
}

function coverage(
  fees: FeeItem[],
  years: number[],
  notes: string,
): RecurringFeeCoverage {
  const present = new Set(
    fees.filter((fee) => fee.category === "renewal").map((fee) => fee.year),
  );
  const missing = years.filter((year) => !present.has(year));
  return missing.length
    ? {
        status: "partial",
        missing_categories: [],
        missing_years: missing,
        notes: null,
      }
    : { status: "complete", missing_categories: [], missing_years: [], notes };
}

const STATUTORY = `Sınai Mülkiyet Kanunu (Law 6769) Art. 188; ${GAZETTE}.`;

/** Fetches the TÜRKPATENT patent, trademark and design fee pages. */
export class TurkpatentFeesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.turkpatent.gov.tr",
      sourceName: TURKPATENT_FEES_SOURCE,
      cache: { name: "turkpatent_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  private async page(right: Right, options: TransportRequestOptions) {
    const path = {
      patent: "/patent-islem-ucretleri",
      trademark: "/marka-islem-ucretleri",
      design: "/tasarim-islem-ucretleri",
    }[right];
    const result = await this.http.text("GET", path, options);
    return { ...table(result.data, right), provenance: result.provenance };
  }
  private schedule(
    right: Right,
    page: Awaited<ReturnType<TurkpatentFeesClient["page"]>>,
    fees: FeeItem[],
    extra: {
      source_url: string;
      coverage: RecurringFeeCoverage;
      unmapped: string[];
      notes: string;
    },
  ): FeeSchedule {
    const effective = page.tariffYear ? `${page.tariffYear}-01-01` : null;
    return FeeScheduleSchema.parse({
      key: `TR/TURKPATENT/${right}`,
      jurisdiction: "TR",
      issuing_body: "Türk Patent ve Marka Kurumu (TÜRKPATENT)",
      office_code: "TURKPATENT",
      right,
      currency: "TRY",
      effective_date: effective,
      source_url: extra.source_url,
      statutory_basis: STATUTORY,
      fees,
      recurring_fee_coverage: extra.coverage,
      unmapped_codes: extra.unmapped,
      notes: `${extra.notes} TÜRKPATENT republishes the tariff each year in the Resmî Gazete, effective 1 January; amounts change sharply with inflation.`,
      provenance: {
        ...page.provenance,
        as_of_status: effective
          ? `${page.tariffYear} tariff per the table header; the annual tariff applies from 1 January`
          : "the page states no tariff year",
        effective_date: effective,
      },
    });
  }
  /** Patent fees (01.01.xx): amounts are the all-in total, with office fee, VAT and stamp duty in the notes. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page("patent", options);
    const { fees, omitted, unmapped } = patentFees(page.body);
    return this.schedule("patent", page, fees, {
      source_url: TURKPATENT_PATENTS_URL,
      coverage: coverage(
        fees,
        Array.from({ length: 18 }, (_, i) => i + 3),
        "Annuities (Sicil Kayıt Ücreti) for years 3-20 present.",
      ),
      unmapped,
      notes: `Amounts are the TOPLAM TUTAR (total), checked to equal the office fee plus VAT plus stamp duty. Annuities 01.01.23-01.01.40 are years 3-20. The search and examination report fees have a reduced rate for natural persons and universities (tier small) and a standard rate (tier large); the urgent search fee has a reduced rate for Teknogirişim-badge companies. Omitted rows: ${omitted.join("; ")}. The page states no tariff year, so the effective date is null. Utility model fees are on a separate TÜRKPATENT page and are not included, as in Python.`,
    });
  }
  /** Trademark fees (02.01.xx). */
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page("trademark", options);
    const { fees, unmapped } = simpleFees(
      "trademark",
      page.body,
      TRADEMARK_RULES,
      TURKPATENT_TRADEMARKS_URL,
    );
    return this.schedule("trademark", page, fees, {
      source_url: TURKPATENT_TRADEMARKS_URL,
      coverage: coverage(
        fees,
        [10],
        "Registrations renew every 10 years (Law 6769 Art. 23); year 10 stands for each renewal.",
      ),
      unmapped,
      notes:
        "The application fee covers one class; 02.01.02 is charged once for the second class and 02.01.28 for each class from the third. Renewal (02.01.23) covers two classes, with 02.01.32 for each further class. Renewing a mark whose protection has expired (02.01.24, 02.01.33) is a late fee. Madrid Protocol transmittal fees are madrid.",
    });
  }
  /** Industrial design fees (04.01.xx). */
  async getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page("design", options);
    const { fees, unmapped } = simpleFees(
      "design",
      page.body,
      DESIGN_RULES,
      TURKPATENT_DESIGNS_URL,
    );
    return this.schedule("design", page, fees, {
      source_url: TURKPATENT_DESIGNS_URL,
      coverage: coverage(
        fees,
        DESIGN_RENEWAL_YEARS,
        "Protection runs in five-year terms up to 25 years; renewal fees are stored at years 5, 10, 15 and 20.",
      ),
      unmapped,
      notes:
        "The additional-design fee (04.01.02) lists three bands in one cell; it becomes three fees (-d2, -d3to5, -d6plus) with multi_design conditions. Renewal and late-renewal fees repeat at years 5, 10, 15 and 20 with -y<year> codes.",
    });
  }
}

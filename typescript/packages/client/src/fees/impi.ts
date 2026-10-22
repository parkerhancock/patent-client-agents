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
  type RecurringFeeCoverage,
} from "./models.js";

/**
 * IMPI's tariff is the consolidated "Acuerdo por el que se da a conocer la
 * tarifa por los servicios que presta el Instituto Mexicano de la Propiedad
 * Industrial", a PDF on the gob.mx CMS. Articles 1-34 carry MXN amounts;
 * Article 35 (PCT) refers to WIPO's tariff, and Articles 36-37 (Madrid,
 * Hague) mix CHF fees paid to WIPO with a few MXN fees paid to IMPI.
 */
export const IMPI_FEES_SOURCE = "IMPI tariff (Acuerdo, DOF)";
export const IMPI_FEES_PDF_URL =
  "https://www.gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf";
const PDF_PATH =
  "/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`IMPI fee schedule: ${message}`, 200, "INVALID_RESPONSE");

/** "$4,550.00" / "1,044.91" / "$1,348. 51" -> "4550.00". */
export function parsePesoAmount(raw: string): string {
  const value = raw.replace(/[\s$]/g, "");
  if (!/^\d{1,3}(?:,\d{3})*(?:\.\d{2})?$/.test(value))
    throw invalid(`unrecognized amount ${raw.slice(0, 20)}`);
  const [whole = "0", fraction = "00"] = value.replaceAll(",", "").split(".");
  return `${whole}.${fraction}`;
}

/** One priced row of the tariff: article code ("1 a bis"), text, MXN amount. */
export interface ImpiRow {
  code: string;
  description: string;
  amount: string;
}

const NOISE = [
  /^Artículo Concepto Tarifa$/,
  /^Periférico Sur/,
  /^Ciudad de México/,
];
const CODE =
  /^(\d{1,2})(?:\s*([a-j])(?=\s))?(?:\s+(bis|BIS|ter|TER|quáter))?\.?(?:\s+(.*))?$/;
const AMOUNT = /\s*(\$?\s*\d{1,3}(?:,\d{3})*\.\s?\d{2})\s*$/;

/** Priced rows of Articles 1-34, the MXN Madrid fees (36 b) and the Hague transmittal fee (37 III). */
export function impiRows(pages: string[]): {
  rows: ImpiRow[];
  lastReform: string;
} {
  const lines = pages
    .flatMap((page) => page.split("\n"))
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter((line) => line && !NOISE.some((pattern) => pattern.test(line)));
  const reform = lines.find((line) => line.startsWith("Última reforma"));
  const date = /(\d{1,2})-(\d{1,2})-(\d{4})/.exec(
    (reform ?? "").replace(/\s+/g, ""),
  );
  if (!date) throw invalid("the last-reform date was not found.");
  const lastReform = `${date[3]}-${(date[2] as string).padStart(2, "0")}-${(date[1] as string).padStart(2, "0")}`;
  const rows: ImpiRow[] = [];
  let open: { code: string; text: string[] } | null = null;
  let base = 0;
  let region: "articles" | "pct" | "madrid-chf" | "madrid-mxn" | "hague" =
    "articles";
  const finish = (amount: string) => {
    if (!open) return;
    rows.push({
      code: open.code,
      description: open.text
        .join(" ")
        .replace(/\s+/g, " ")
        .replace(/[;,]$/, "")
        .trim(),
      amount: parsePesoAmount(amount),
    });
    open = null;
  };
  for (const line of lines) {
    if (/^DISPOSICIONES GENERALES/.test(line)) break;
    if (region === "articles" && /^35 Cuando se presenten/.test(line)) {
      region = "pct";
      open = null;
      continue;
    }
    if (/^36 Cuando se presenten/.test(line)) region = "madrid-chf";
    if (region === "madrid-chf" && /^b\) Tarifas Nacionales/.test(line))
      region = "madrid-mxn";
    if (/^37 Cuando se presenten/.test(line)) region = "hague";
    if (region === "pct" || region === "madrid-chf") continue;
    if (region === "hague") {
      if (/^III Por la transmisión/.test(line))
        open = { code: "37 III", text: [line.replace(/^III\s+/, "")] };
      else if (open) {
        const tail = /\s(\d{1,3}(?:,\d{3})*)$/.exec(line);
        if (tail) {
          open.text.push(line.slice(0, tail.index));
          finish(tail[1] as string);
        } else open.text.push(line);
      }
      continue;
    }
    if (region === "madrid-mxn") {
      const item = /^([1-4]) (.*)$/.exec(line);
      if (item) open = { code: `36 b ${item[1]}`, text: [] };
      const text = item ? (item[2] as string) : line;
      if (!open) continue;
      const tail = AMOUNT.exec(text);
      if (tail) {
        open.text.push(text.slice(0, tail.index));
        finish(tail[1] as string);
      } else open.text.push(text);
      continue;
    }
    // Articles 1-34. A suffix can wrap onto its own line ("16" ... "quáter").
    const suffix = /^(bis|ter|quáter)\s+(.*)$/i.exec(line);
    if (open && suffix) {
      open.code = `${open.code} ${suffix[1]}`;
      const tail = AMOUNT.exec(suffix[2] as string);
      if (tail) finish(tail[1] as string);
      continue;
    }
    const match = CODE.exec(line);
    const number = match ? Number(match[1]) : 0;
    if (match && number >= base && number <= base + 2) {
      base = number;
      open = {
        code: [match[1], match[2], match[3]].filter(Boolean).join(" "),
        text: [],
      };
      const text = match[4] ?? "";
      const tail = AMOUNT.exec(text);
      if (tail) {
        open.text.push(text.slice(0, tail.index));
        finish(tail[1] as string);
      } else if (text) open.text.push(text);
      continue;
    }
    if (!open) continue;
    const tail = AMOUNT.exec(line);
    if (tail) {
      open.text.push(line.slice(0, tail.index));
      finish(tail[1] as string);
    } else open.text.push(line);
  }
  return { rows, lastReform };
}

type Route = "patent" | "utility_model" | "design" | "trademark";
const P: Route[] = ["patent"];
const U: Route[] = ["utility_model"];
const D: Route[] = ["design"];
const T: Route[] = ["trademark"];
const PUD: Route[] = ["patent", "utility_model", "design"];
const PU: Route[] = ["patent", "utility_model"];
const ALL: Route[] = ["patent", "utility_model", "design", "trademark"];

interface Rule {
  routes: Route[];
  category: FeeCategory;
  /** Annuity band: one fee row per year. */
  years?: number[];
  condition?: FeeCondition;
  notes?: string;
}
const range = (from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, i) => from + i);
const perPage: FeeCondition = {
  trigger: "pages_over",
  threshold: 30,
  per_unit: true,
  description: "Per sheet over 30.",
};
const perMonth: FeeCondition = {
  trigger: "late_days",
  threshold: null,
  per_unit: true,
  description: "Per month.",
};
const extraPages = (routes: Route[]): Rule => ({
  routes,
  category: "excess_pages",
  condition: perPage,
});
const UM_IC =
  "Article 9 a-d are utility models; 9 e is integrated-circuit layout designs, which the tariff groups with utility models.";

/** Article codes mapped to routes and the closed vocabulary. */
const RULES: Record<string, Rule> = {
  "1 a": { routes: P, category: "filing" },
  "1 a bis": extraPages(P),
  "1 b": {
    routes: P,
    category: "filing",
    notes: "PCT Chapter I national phase.",
  },
  "1 b bis": extraPages(P),
  "1 c": {
    routes: P,
    category: "filing",
    notes: "PCT Chapter II national phase.",
  },
  "1 c bis": extraPages(P),
  "1 d": { routes: P, category: "publication" },
  "1 e": { routes: P, category: "grant" },
  "1 f": {
    routes: P,
    category: "other",
    notes: "Correction or limitation of a granted patent.",
  },
  "1 g": {
    routes: P,
    category: "other",
    notes: "Request for a complementary certificate (term adjustment).",
  },
  "1 h": { routes: P, category: "other" },
  "1 i": { routes: P, category: "other" },
  "1 j": { routes: P, category: "other" },
  "2 a": { routes: P, category: "renewal", years: range(1, 5) },
  "2 b": { routes: P, category: "renewal", years: range(6, 10) },
  "2 c": { routes: P, category: "renewal", years: range(11, 20) },
  "3": { routes: P, category: "other", notes: "Compulsory licence." },
  "4": { routes: P, category: "petition" },
  "5": { routes: P, category: "other" },
  "9 a": { routes: U, category: "filing", notes: UM_IC },
  "9 a bis": extraPages(U),
  "9 b": {
    routes: U,
    category: "filing",
    notes: "PCT Chapter I national phase.",
  },
  "9 b bis": extraPages(U),
  "9 c": {
    routes: U,
    category: "filing",
    notes: "PCT Chapter II national phase.",
  },
  "9 c bis": extraPages(U),
  "9 d": { routes: U, category: "grant" },
  "9 e": {
    routes: U,
    category: "filing",
    notes: `Integrated-circuit layout design; covers the procedure through grant. ${UM_IC}`,
  },
  "9 e bis": { ...extraPages(U), notes: "Integrated-circuit layout design." },
  "9 f": { routes: D, category: "filing" },
  "9 f bis": {
    routes: D,
    category: "filing",
    condition: {
      trigger: "multi_design",
      threshold: 1,
      per_unit: true,
      description: "Per additional design meeting the unity requirement.",
    },
  },
  "9 g": {
    routes: D,
    category: "grant",
    notes: "Includes the first five years of protection.",
  },
  "10 a": { routes: U, category: "renewal", years: range(1, 3) },
  "10 b": { routes: U, category: "renewal", years: range(4, 6) },
  "10 c": {
    routes: U,
    category: "renewal",
    years: range(7, 15),
    notes:
      "Utility models last 15 years; integrated-circuit layout designs 10 years.",
  },
  "11": {
    routes: D,
    category: "renewal",
    years: [5, 10, 15, 20],
    notes: "Each renewal covers the next five years, up to 25 years.",
  },
  "12 a": { routes: U, category: "petition" },
  "12 b": { routes: D, category: "petition" },
  "13": { routes: PUD, category: "other" },
  "14 a": { routes: T, category: "filing" },
  "14 b": { routes: T, category: "opposition" },
  "14 c": {
    routes: T,
    category: "renewal",
    years: [10],
    condition: {
      trigger: "classes_over",
      threshold: 0,
      per_unit: true,
      description: "Per class, including the first.",
    },
  },
  "14 d": { routes: T, category: "declaration_of_use" },
  "14 e": { routes: T, category: "other" },
  "14 f": { routes: T, category: "other" },
  "14 g": { routes: T, category: "other" },
  "14 h": { routes: T, category: "other" },
  "14 i": { routes: T, category: "other" },
  "14 j": { routes: T, category: "other" },
  // Article 15: appellations of origin and geographical indications; no route.
  ...Object.fromEntries(
    ["15 a", "15 b", "15 c", "15 d", "15 e"].map((code) => [
      code,
      { routes: [], category: "other" as const },
    ]),
  ),
  "16": {
    routes: ALL,
    category: "cancellation",
    notes:
      "Nullity, lapse, cancellation and administrative infringement declarations.",
  },
  "16 bis": { routes: ALL, category: "other" },
  "16 ter": { routes: ALL, category: "other" },
  "16 quáter": { routes: ALL, category: "other" },
  "17": { routes: ALL, category: "other" },
  "17 bis": { routes: ALL, category: "other" },
  "18": { routes: ALL, category: "other" },
  "19 a": { routes: PUD, category: "other" },
  "19 b": { routes: PUD, category: "other" },
  "20 a": { routes: PU, category: "other" },
  "20 b": { routes: PU, category: "other" },
  "21": {
    routes: PU,
    category: "search",
    notes: "State-of-the-art search report.",
  },
  "22": { routes: PUD, category: "other" },
  "23 c": { routes: P, category: "other" },
  "23 d": { routes: P, category: "other" },
  "23 e": { routes: P, category: "other" },
  "24": { routes: T, category: "search" },
  "26 bis": { routes: P, category: "other" },
  "27 a": { routes: ALL, category: "other" },
  "27 a bis": { routes: ALL, category: "other" },
  "27 b": { routes: ALL, category: "other" },
  "27 c": { routes: ALL, category: "other" },
  "27 c bis": { routes: ALL, category: "other" },
  "28": { routes: ALL, category: "other", notes: "Priority claim." },
  "29": { routes: ALL, category: "other" },
  "30": { routes: ALL, category: "extension", condition: perMonth },
  "31": {
    routes: ALL,
    category: "extension",
    condition: perMonth,
    notes: "Answering an office requirement within the two additional months.",
  },
  "32": { routes: ALL, category: "transfer" },
  "33": { routes: ALL, category: "transfer" },
  "34": { routes: ALL, category: "other" },
  "36 b 1": {
    routes: T,
    category: "madrid",
    notes: "Paid to IMPI; WIPO's Madrid fees are paid in CHF.",
  },
  "36 b 2": { routes: T, category: "madrid", notes: "Paid to IMPI." },
  "36 b 3": { routes: T, category: "madrid", notes: "Paid to IMPI." },
  "36 b 4": { routes: T, category: "madrid", notes: "Paid to IMPI." },
  "37 iii": {
    routes: D,
    category: "other",
    notes:
      "Hague international design applications; paid to IMPI. WIPO's Hague fees are paid in CHF.",
  },
};

/** Disposición Cuarta: Articles 1 a to 1 f, 2 to 13, 19 to 23 and 26 BIS. */
export function impiReducible(code: string): boolean {
  const [first = "", letter] = code.split(" ");
  const base = Number(first);
  if (code.startsWith("36") || code.startsWith("37")) return false;
  if (base === 1) return letter !== undefined && "abcdef".includes(letter);
  if (base === 26) return code === "26 bis";
  return (base >= 2 && base <= 13) || (base >= 19 && base <= 23);
}

/** Half of an amount in cents, rounded half to even (as Python's Decimal.quantize). */
function half(amount: string): string {
  const cents = Math.round(Number(amount) * 100);
  let halved = Math.floor(cents / 2);
  if (cents % 2 === 1 && halved % 2 === 1) halved += 1;
  return (halved / 100).toFixed(2);
}

const normal = (code: string) => code.toLowerCase();
const slug = (code: string) => `impi-${normal(code).replace(/\s+/g, "-")}`;

/** Fees of one route from the parsed rows. */
export function impiFees(
  rows: ImpiRow[],
  route: Route,
): { fees: FeeItem[]; unmapped: string[] } {
  const fees: FeeItem[] = [];
  const unmapped: string[] = [];
  for (const row of rows) {
    const code = normal(row.code);
    const rule = RULES[code];
    if (!rule) {
      unmapped.push(row.code);
      continue;
    }
    if (!rule.routes.includes(route)) continue;
    const reducible = impiReducible(code);
    for (const year of rule.years ?? [null]) {
      const item = (tier: "large" | "small" | "none", amount: string) => ({
        code: `${slug(row.code)}${tier === "small" ? "-small" : ""}`,
        label: row.description,
        category: rule.category,
        rights: [route],
        amount,
        currency: "MXN",
        tier,
        year,
        condition: rule.condition ?? null,
        source_url: IMPI_FEES_PDF_URL,
        notes:
          [
            `Article ${row.code}.`,
            rule.notes,
            tier === "small"
              ? "50% under Disposición Cuarta for individual inventors, micro and small industries, universities and public research institutes."
              : null,
          ]
            .filter(Boolean)
            .join(" ") || null,
      });
      if (reducible)
        fees.push(item("large", row.amount), item("small", half(row.amount)));
      else fees.push(item("none", row.amount));
    }
  }
  return { fees, unmapped };
}

function coverage(fees: FeeItem[], years: number[], notes: string) {
  const present = new Set(
    fees.filter((fee) => fee.category === "renewal").map((fee) => fee.year),
  );
  const missing = years.filter((year) => !present.has(year));
  return missing.length
    ? ({
        status: "partial",
        missing_categories: [],
        missing_years: missing,
        notes: null,
      } satisfies RecurringFeeCoverage)
    : ({
        status: "complete",
        missing_categories: [],
        missing_years: [],
        notes,
      } satisfies RecurringFeeCoverage);
}

const COMMON =
  "Amounts exclude 16% VAT (IVA), which Disposición Sexta adds. Rows eligible for the Disposición Cuarta 50% reduction have a large row at the published amount and a small row at half; other rows have no tier. Procedural fees of Articles 16-18 and 27-34 appear in every schedule. Article 35 (PCT) refers to WIPO's tariff and is omitted, as are Madrid and Hague fees paid to WIPO in CHF.";

/** Fetches IMPI's tariff and projects the patent, utility model, design and trade mark schedules. */
export class ImpiFeesClient {
  private readonly http: GenericHttpTransport;
  private pending: Promise<{
    rows: ImpiRow[];
    lastReform: string;
    provenance: FeeSchedule["provenance"];
  }> | null = null;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.gob.mx",
      sourceName: IMPI_FEES_SOURCE,
      headers: { accept: "application/pdf", "user-agent": USER_AGENT },
    });
  }
  /** One PDF fetch serves concurrent schedule requests. */
  private tariff(options: TransportRequestOptions) {
    this.pending ??= (async () => {
      const result = await this.http.bytes("GET", PDF_PATH, options);
      const { rows, lastReform } = impiRows(await pdfPageTexts(result.data));
      if (rows.length < 80) throw invalid(`only ${rows.length} priced rows.`);
      return {
        rows,
        lastReform,
        provenance: {
          ...result.provenance,
          as_of_status: `consolidated tariff, last reform published in the DOF ${lastReform}`,
          effective_date: lastReform,
        },
      };
    })().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }
  private async schedule(
    route: Route,
    options: TransportRequestOptions,
    extra: {
      coverage: (fees: FeeItem[]) => RecurringFeeCoverage;
      notes: string;
    },
  ): Promise<FeeSchedule> {
    const tariff = await this.tariff(options);
    const { fees, unmapped } = impiFees(tariff.rows, route);
    return FeeScheduleSchema.parse({
      key: `MX/IMPI/${route}`,
      jurisdiction: "MX",
      issuing_body: "Instituto Mexicano de la Propiedad Industrial (IMPI)",
      office_code: "IMPI",
      right: route,
      currency: "MXN",
      effective_date: tariff.lastReform,
      source_url: IMPI_FEES_PDF_URL,
      statutory_basis:
        "Ley Federal de Protección a la Propiedad Industrial (DOF 2020-07-01); tariff Acuerdo first published in the DOF 1995-08-23.",
      fees,
      recurring_fee_coverage: extra.coverage(fees),
      unmapped_codes: unmapped,
      notes: `${extra.notes} ${COMMON} The effective date is the DOF publication date of the tariff's last reform; the March 15, 2024 indigenous-community waiver (Disposición Décima Primera) is not in the consolidated PDF and is not applied.`,
      provenance: tariff.provenance,
    });
  }
  /** Patent fees (Articles 1-5) plus procedural and information-service fees. */
  getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("patent", options, {
      coverage: (fees) =>
        coverage(
          fees,
          range(1, 20),
          "Annuities for years 1-20 (Article 2 bands 1-5, 6-10, 11-20).",
        ),
      notes:
        "Article 2 annuities are expanded to one row per year. Utility models and integrated-circuit layout designs are in the IMPI utility_model schedule.",
    });
  }
  /** Utility model and integrated-circuit layout design fees (Articles 9 a-9 e bis, 10, 12 a). */
  getUtilityModelSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("utility_model", options, {
      coverage: (fees) =>
        coverage(
          fees,
          range(1, 15),
          "Annuities for years 1-15 (Article 10 bands 1-3, 4-6, 7 onward); layout designs end at year 10.",
        ),
      notes:
        "Article 10 annuities are expanded to one row per year. Integrated-circuit layout designs share Articles 9 e, 10 and 12 a with utility models.",
    });
  }
  /** Industrial design fees (Articles 9 f-9 g, 11, 12 b, 37 III). */
  getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("design", options, {
      coverage: (fees) =>
        coverage(
          fees,
          [5, 10, 15, 20],
          "The grant fee covers years 1-5; renewals are due at years 5, 10, 15 and 20.",
        ),
      notes:
        "The Article 11 renewal is stored once per five-year renewal (years 5, 10, 15, 20).",
    });
  }
  /** Trade mark, slogan and trade name fees (Article 14) and the MXN Madrid fees. */
  getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("trademark", options, {
      coverage: (fees) =>
        coverage(
          fees,
          [10],
          "Registrations renew every 10 years, per class; year 10 stands for each renewal.",
        ),
      notes:
        "Trade mark fees are not eligible for the Disposición Cuarta reduction.",
    });
  }
}

import { type PdfTextItem, pdfPageItems } from "../runtime/pdf.js";
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
 * The Israel Patent Office publishes its fee schedule each year as one
 * Hebrew-only PDF notice on gov.il (patents, patent term extensions, trade
 * marks, Madrid, designs, and legacy designs). The gov.il landing page
 * answers plain requests with a Cloudflare 403; the PDF itself is served.
 *
 * The PDF is right-to-left: item numbers sit at the right margin, amounts in
 * a column at the left. Lines are rebuilt from text positions rather than
 * from extracted text order, which reverses Hebrew runs.
 */
export const ILPO_FEES_SOURCE = "Israel Patent Office fee notice";
export const ILPO_FEES_LANDING_URL = "https://www.gov.il/he/pages/ilpo-fees";
export const ILPO_FEES_PDF_URL =
  "https://www.gov.il/BlobFolder/news/ilpo-fees/he/news_fees-2026.pdf";
const PDF_PATH = "/BlobFolder/news/ilpo-fees/he/news_fees-2026.pdf";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`ILPO fee schedule: ${message}`, 200, "INVALID_RESPONSE");

type Section =
  | "patent"
  | "extension"
  | "trademark"
  | "madrid"
  | "design"
  | "costs"
  | "legacy-design";

/** One priced item: its section, item path (e.g. `8(א)(1)`) and amount. */
export interface IlpoItem {
  section: Section;
  path: string;
  amount: string;
}

/** "2,402" -> "2402.00"; "4.3" -> "4.30". */
export function parseShekelAmount(raw: string): string {
  const value = raw.replace(/\s+/g, "");
  if (!/^\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?$/.test(value))
    throw invalid(`unrecognized amount ${value.slice(0, 20)}`);
  const [whole = "0", fraction = ""] = value.replaceAll(",", "").split(".");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}

interface Line {
  /** Item number or parenthesized sub-label in the right margin. */
  margin: string;
  /** Text items right to left, i.e. in reading order. */
  rtl: PdfTextItem[];
  /** The amount run at the left edge, if any. */
  amount: string | null;
}

/** Group a page's items into visual lines, top to bottom. */
function lines(items: PdfTextItem[], marginX: number): Line[] {
  const rows: { y: number; items: PdfTextItem[] }[] = [];
  for (const item of items) {
    if (!item.str.trim()) continue;
    const row = rows.find((r) => Math.abs(r.y - item.y) <= 2);
    if (row) row.items.push(item);
    else rows.push({ y: item.y, items: [item] });
  }
  return rows
    .sort((a, b) => b.y - a.y)
    .map(({ items: row }) => {
      const sorted = [...row].sort((a, b) => a.x - b.x);
      const margin = sorted
        .filter((item) => item.x >= marginX)
        .map((item) => item.str)
        .join("");
      const body = sorted.filter((item) => item.x < marginX);
      // The amount is the leftmost run of numeric items, set apart from text.
      let end = 0;
      const gap = (i: number) =>
        (body[i]?.x ?? 0) - ((body[i - 1]?.x ?? 0) + (body[i - 1]?.width ?? 0));
      while (
        end < body.length &&
        /^[\d,.\s]+$/.test(body[end]?.str ?? "") &&
        (end === 0 || gap(end) < 4)
      )
        end++;
      const next = body[end];
      const last = body[end - 1];
      const separated =
        end > 0 &&
        (!next || next.x - ((last?.x ?? 0) + (last?.width ?? 0)) > 8);
      const amount = separated
        ? body
            .slice(0, end)
            .map((item) => item.str)
            .join("")
        : null;
      return {
        margin,
        rtl: (separated ? body.slice(end) : body).reverse(),
        amount,
      };
    });
}

const squash = (text: string) => text.replace(/\s+/g, "");
function sectionOf(text: string): Section | null {
  const t = squash(text);
  if (t.includes("לוחהוצאותמרביות")) return "costs";
  if (t.includes("אגרותמדגמים")) return "legacy-design";
  if (t.includes("אגרותעיצובים")) return "design";
  if (t.includes("מדריד") && t.includes("אגרותסימנימסחר")) return "madrid";
  if (t.includes("אגרותסימנימסחר")) return "trademark";
  if (t.includes("צוויהארכה") && t.includes("אגרותפטנטים")) return "extension";
  if (t.startsWith("אגרותפטנטים")) return "patent";
  return null;
}
const HEBREW = /[א-ת]/;

/** Priced items of every section, keyed by item path, plus the effective date. */
export function ilpoItems(pages: PdfTextItem[][]): {
  items: IlpoItem[];
  effectiveDate: string;
} {
  const items: IlpoItem[] = [];
  let section: Section | null = null;
  let top = "";
  // Nested sub-labels below the item number, e.g. 8 (א) (1) or (3) (א).
  let levels: { kind: "letter" | "number"; value: string }[] = [];
  const sub = (kind: "letter" | "number", value: string) => {
    const at = levels.findIndex((level) => level.kind === kind);
    levels = [...(at < 0 ? levels : levels.slice(0, at)), { kind, value }];
  };
  let effectiveDate: string | null = null;
  const used = new Set<string>();
  for (const page of pages) {
    // Item numbers are right of every text column (x ~ 488-506).
    for (const line of lines(page, 480)) {
      const text = line.rtl.map((item) => item.str).join(" ");
      if (!effectiveDate) {
        const date = /(\d{1,2})\.(\d{1,2})\.(\d{4})/.exec(
          squash(
            [...line.rtl]
              .reverse()
              .map((item) => item.str)
              .join(""),
          ),
        );
        if (date && /לתוקף/.test(text))
          effectiveDate = `${date[3]}-${(date[2] as string).padStart(2, "0")}-${(date[1] as string).padStart(2, "0")}`;
      }
      const heading = !line.amount && !line.margin ? sectionOf(text) : null;
      if (heading) {
        section = heading;
        top = "";
        levels = [];
        continue;
      }
      if (!section) continue;
      // Margin labels: "1." top items, "(ב)" letters, "(2)" / "1)" numbers.
      if (line.margin) {
        if (HEBREW.test(line.margin))
          sub("letter", line.margin.replace(/[^\u05d0-\u05ea]/g, ""));
        else if (/[()]/.test(line.margin))
          sub("number", line.margin.replace(/\D/g, ""));
        else if (/\d/.test(line.margin)) {
          top = line.margin.replace(/\D/g, "");
          levels = [];
        }
      }
      // Sub-labels at the right edge of the text: "(א)", "(1)".
      const first = line.rtl[0];
      if (first && first.x + first.width >= 455) {
        const head = line.rtl
          .slice(0, 4)
          .map((item) => item.str)
          .join("");
        const label = /^\(\s*([\u05d0-\u05ea]|\d{1,2})\s*\)/.exec(head)?.[1];
        if (label) sub(HEBREW.test(label) ? "letter" : "number", label);
      }
      if (!line.amount) continue;
      const base =
        `${top}${levels.map((level) => `(${level.value})`).join("")}` || "item";
      let path = base;
      for (let n = 2; used.has(`${section}:${path}`); n++)
        path = `${base}#${n}`;
      used.add(`${section}:${path}`);
      items.push({ section, path, amount: parseShekelAmount(line.amount) });
    }
  }
  if (!effectiveDate) throw invalid("the effective date was not found.");
  return { items, effectiveDate };
}

interface Meta {
  code: string;
  label: string;
  category: FeeCategory;
  year?: number;
  condition?: FeeCondition;
  notes?: string;
  /** Item carries the 40% small-entity reduction for a first application. */
  small?: boolean;
}
const perMonth: FeeCondition = {
  trigger: "late_days",
  threshold: null,
  per_unit: true,
  description: "Per month or part of a month.",
};
const claims50: FeeCondition = {
  trigger: "claims_over",
  threshold: 50,
  per_unit: true,
  description: "Per claim from the 51st.",
};
const pages100: FeeCondition = {
  trigger: "pages_over",
  threshold: 100,
  per_unit: true,
  description:
    "Per 50 pages from the 101st, excluding genetic sequence listings.",
};
const perClass: FeeCondition = {
  trigger: "classes_over",
  threshold: 1,
  per_unit: true,
  description: "Per class of goods beyond the first in the same request.",
};

/** Patents section (Patents Law 5727-1967), keyed by item path. */
const PATENT: Record<string, Meta> = {
  "1": {
    code: "il-pat-1",
    label: "Filing a patent application (Patents Law §11(a)), first 50 claims",
    category: "filing",
    small: true,
  },
  "2": {
    code: "il-pat-2",
    label: "Each claim from the 51st (national application)",
    category: "excess_claims",
    condition: claims50,
  },
  "3": {
    code: "il-pat-3",
    label: "Each 50 pages from the 101st (national application)",
    category: "excess_pages",
    condition: pages100,
  },
  "4": {
    code: "il-pat-4",
    label: "Each claim from the 51st (PCT application designating Israel)",
    category: "excess_claims",
    condition: claims50,
  },
  "5": {
    code: "il-pat-5",
    label: "Each 50 pages from the 101st (PCT application designating Israel)",
    category: "excess_pages",
    condition: pages100,
  },
  "6": {
    code: "il-pat-6",
    label: "International-type search report (Patents Regulation 35A)",
    category: "search",
  },
  "7(א)": {
    code: "il-pat-7",
    label:
      "Request to revoke or cancel a patent or to correct the register (§§73(a), 170(a), 171)",
    category: "petition",
  },
  "7(ב)": {
    code: "il-pat-7-2",
    label: "Amended document that postpones the filing date (§23)",
    category: "other",
  },
  "7(ג)": {
    code: "il-pat-7-3",
    label:
      "Recording, changing or cancelling a right in a patent or an applied-for invention (§169)",
    category: "transfer",
  },
  "7(ד)": {
    code: "il-pat-7-4",
    label: "Correcting a clerical error in the specification (§69)",
    category: "other",
  },
  "8(א)(1)": {
    code: "il-pat-8-1",
    label: "Request to expedite examination (§19A(d)) under §19A(a)(3)-(6)",
    category: "examination",
  },
  "8(א)(2)": {
    code: "il-pat-8-2",
    label: "Request to expedite examination (§19A(d)) under §19A(c)",
    category: "examination",
  },
  "8(ב)(1)": {
    code: "il-pat-8-1-2",
    label: "On-site examination (§19A(e)), expedited under §19A(a)(3)-(6)",
    category: "examination",
  },
  "8(ב)(2)": {
    code: "il-pat-8-2-2",
    label: "On-site examination (§19A(e)), expedited under §19A(c)",
    category: "examination",
  },
  "9": {
    code: "il-pat-9",
    label: "Extension of any period (§§48D(c), 164; Regulations 5(a), 87(c))",
    category: "extension",
    condition: perMonth,
  },
  "10": {
    code: "il-pat-10",
    label: "Notice of acceptance (Regulation 52)",
    category: "grant",
    small: true,
  },
  "11(א)": {
    code: "il-pat-11",
    label:
      "Request in inter partes proceedings (§§25, 30, 61, 67, 73(c), 117, 124(b), 133, 170(c))",
    category: "opposition",
  },
  "11(ב)": {
    code: "il-pat-11-2",
    label:
      "Request to be heard before the Registrar (§159) or objection (§161)",
    category: "appeal",
  },
  "11(ג)": {
    code: "il-pat-11-3",
    label: "Request to amend the specification (§§29, 65)",
    category: "other",
  },
  "11(ד)": {
    code: "il-pat-11-4",
    label: "Request to restore a lapsed patent (§59)",
    category: "petition",
  },
  "12(1)": {
    code: "il-pat-12-1",
    label:
      "Renewal within three months of grant, until six years from the application date",
    category: "renewal",
    year: 6,
  },
  "12(2)": {
    code: "il-pat-12-2",
    label: "Renewal before the end of year 6, for years 7-10",
    category: "renewal",
    year: 10,
  },
  "12(3)": {
    code: "il-pat-12-3",
    label: "Renewal before the end of year 10, for years 11-14",
    category: "renewal",
    year: 14,
  },
  "12(4)": {
    code: "il-pat-12-4",
    label: "Renewal before the end of year 14, for years 15-18",
    category: "renewal",
    year: 18,
  },
  "12(5)": {
    code: "il-pat-12-5",
    label: "Renewal before the end of year 18, for years 19-20",
    category: "renewal",
    year: 20,
  },
  "12(6)": {
    code: "il-pat-12-6",
    label:
      "Comprehensive renewal for the whole term, within three months of grant",
    category: "other",
    notes:
      "An alternative to the five renewal payments 12(1)-12(5); not a renewal for any single year.",
  },
  "13": {
    code: "il-pat-13",
    label: "National fee (§48D(a)), PCT national phase",
    category: "filing",
  },
  "14": {
    code: "il-pat-14",
    label:
      "Search fee to the ILPO as International Searching Authority (PCT Implementation Regulation 6(d))",
    category: "search",
  },
  "15": {
    code: "il-pat-15",
    label: "Transmittal fee (PCT Implementation Regulation 6(e))",
    category: "other",
  },
  "16": {
    code: "il-pat-16",
    label:
      "Additional search fee as International Searching Authority (§48J(d))",
    category: "search",
  },
  "17": {
    code: "il-pat-17",
    label:
      "Preliminary examination fee to the ILPO as International Preliminary Examining Authority (PCT Implementation Regulation 6(g))",
    category: "examination",
  },
  "18": {
    code: "il-pat-18",
    label:
      "Additional preliminary examination fee as International Preliminary Examining Authority (§48K(d))",
    category: "examination",
  },
  "19": {
    code: "il-pat-19",
    label: "Late transmittal fee (PCT Implementation Regulation 6(h))",
    category: "late_fee",
  },
  "20": {
    code: "il-pat-20",
    label:
      "Request for reconsideration (§21A) or to cancel a cancellation (§21B)",
    category: "petition",
  },
  "21(א)": {
    code: "il-pat-21",
    label: "Patent attorney examination (§143) and registration (§142) request",
    category: "other",
  },
  "21(ב)": {
    code: "il-pat-21-2",
    label: "Annual patent attorney fee (§145)",
    category: "other",
  },
  "22": {
    code: "il-pat-22",
    label:
      "Certified copy of a document or extract from the register (§168(b))",
    category: "other",
  },
};

const PTE_YEAR =
  "Stored as year 20 plus the extension year it keeps in force; the extension can last up to five years.";
/** Patent term extension orders, numbered (1)-(3) then 1)-2) in the notice. */
const EXTENSION: Record<string, Meta> = {
  "(1)": {
    code: "il-pat-pte-app",
    label: "Application for an extension order (Regulation 2(c)(4))",
    category: "filing",
  },
  "(2)": {
    code: "il-pat-pte-ren-base",
    label: "Extension fee (Regulation 7(a)(1))",
    category: "renewal",
    year: 21,
    notes: PTE_YEAR,
  },
  "(3)(א)": {
    code: "il-pat-pte-ren-y1",
    label:
      "Extension fee (Regulation 7(a)(2)), before the end of the first extension year",
    category: "renewal",
    year: 22,
    notes: PTE_YEAR,
  },
  "(3)(ב)": {
    code: "il-pat-pte-ren-y2",
    label:
      "Extension fee (Regulation 7(a)(2)), before the end of the second extension year",
    category: "renewal",
    year: 23,
    notes: PTE_YEAR,
  },
  "(3)(ג)": {
    code: "il-pat-pte-ren-y3",
    label:
      "Extension fee (Regulation 7(a)(2)), before the end of the third extension year",
    category: "renewal",
    year: 24,
    notes: PTE_YEAR,
  },
  "(3)(ד)": {
    code: "il-pat-pte-ren-y4",
    label:
      "Extension fee (Regulation 7(a)(2)), before the end of the fourth extension year",
    category: "renewal",
    year: 25,
    notes: PTE_YEAR,
  },
  "(1)#2": {
    code: "il-pat-pte-opposition",
    label: "Opposition to an extension order (Regulation 3(a))",
    category: "opposition",
  },
  "(2)#2": {
    code: "il-pat-pte-cancel",
    label: "Request to cancel an extension order (Regulation 4)",
    category: "cancellation",
  },
};

/** Trade marks section (Trade Marks Ordinance [New Version] 5732-1972). */
const TRADEMARK: Record<string, Meta> = {
  "1(א)": {
    code: "il-tm-1",
    label: "Trade mark application (§7), one class of goods",
    category: "filing",
  },
  "1(ב)": {
    code: "il-tm-1-2",
    label: "Trade mark application, each further class in the same application",
    category: "excess_classes",
    condition: perClass,
  },
  "2": {
    code: "il-tm-2",
    label:
      "Opposition, register correction or cancellation request, per mark and class (§§24(a), 38, 41)",
    category: "opposition",
  },
  "3": {
    code: "il-tm-3",
    label:
      "Request to be heard in proceedings (§§24(f), 29, 41(b); Regulation 73)",
    category: "appeal",
  },
  "4(א)": {
    code: "il-tm-4",
    label: "Renewal (§32), one class of goods",
    category: "renewal",
    year: 10,
  },
  "4(ב)": {
    code: "il-tm-4-2",
    label: "Renewal, each further class of the same mark in the same request",
    category: "excess_classes",
    year: 10,
    condition: perClass,
  },
  "5": {
    code: "il-tm-5",
    label: "Late renewal fee (Regulation 52(2))",
    category: "late_fee",
    year: 10,
    condition: perMonth,
  },
  "6": {
    code: "il-tm-6",
    label: "Restoration of a registration (Regulation 53(1)), per class",
    category: "petition",
  },
  "7": {
    code: "il-tm-7",
    label:
      "Change in the register, transfer of ownership, or recording or cancelling a licence, per mark",
    category: "transfer",
  },
  "8(א)": {
    code: "il-tm-8",
    label: "Search (Regulation 78(a))",
    category: "search",
  },
  "9": {
    code: "il-tm-9",
    label: "Certified copy of a registration (§6(b))",
    category: "other",
  },
  "10": {
    code: "il-tm-10",
    label: "Extension of time (Regulation 82), per mark",
    category: "extension",
    condition: perMonth,
  },
  "11": {
    code: "il-tm-11",
    label: "Request to make submissions in a hearing (Regulation 26)",
    category: "other",
  },
  "12": {
    code: "il-tm-12",
    label: "On-site examination (Regulation 22(c)), per class",
    category: "examination",
  },
  "13": {
    code: "il-tm-13",
    label: "Photocopy of any document, per page",
    category: "other",
  },
  "14": {
    code: "il-tm-14",
    label: "Scanned copy of a registration file",
    category: "other",
  },
};
const MADRID_NOTE =
  "ILPO handling fee; WIPO's international fees are paid to the International Bureau in CHF.";
/** Madrid handling fees, printed as three unnumbered lines. */
const MADRID: Record<string, Meta> = {
  item: {
    code: "il-tm-madrid-international-application",
    label: "Handling an international registration application (§56C(1))",
    category: "madrid",
    notes: MADRID_NOTE,
  },
  "item#2": {
    code: "il-tm-madrid-extension-not-il",
    label: "Handling a subsequent designation not designating Israel (§56C(2))",
    category: "madrid",
    notes: MADRID_NOTE,
  },
  "item#3": {
    code: "il-tm-madrid-renewal",
    label: "Handling renewal of an international registration (§56J(1))",
    category: "madrid",
    notes: MADRID_NOTE,
  },
};

/** Designs section (Designs Law 5777-2017). */
const DESIGN: Record<string, Meta> = {
  "1": {
    code: "il-des-1",
    label:
      "Design application (§19, including a supplementary design under §55), per design",
    category: "filing",
    small: true,
  },
  "2": {
    code: "il-des-2",
    label:
      "Design application for a set of articles (§19, including a supplementary design under §55), per set",
    category: "filing",
    small: true,
  },
  "3": {
    code: "il-des-3",
    label: "On-site examination (§28), per design",
    category: "examination",
  },
  "4": {
    code: "il-des-4",
    label: "Request to name the designer (§33), per design",
    category: "other",
  },
  "5(1)": {
    code: "il-des-5-1",
    label: "Renewal (§§40, 86(1)) for the period from year 5 to year 10",
    category: "renewal",
    year: 10,
  },
  "5(2)": {
    code: "il-des-5-2",
    label: "Renewal for the period from year 10 to year 15",
    category: "renewal",
    year: 15,
  },
  "5(3)": {
    code: "il-des-5-3",
    label: "Renewal for the period from year 15 to year 20",
    category: "renewal",
    year: 20,
  },
  "5(4)": {
    code: "il-des-5-4",
    label: "Renewal for the period from year 20 to year 25",
    category: "renewal",
    year: 25,
  },
  "5(5)": {
    code: "il-des-5-5",
    label: "Renewal for all periods together",
    category: "other",
    notes:
      "An alternative to the four period renewals 5(1)-5(4); not a renewal for any single period.",
  },
  "6": {
    code: "il-des-6",
    label: "Late payment of a renewal fee (§§41, 86(1)), per design",
    category: "late_fee",
    condition: perMonth,
  },
  "7": {
    code: "il-des-7",
    label: "Request to restore a registration (§43)",
    category: "petition",
  },
  "8": {
    code: "il-des-8",
    label: "Request to correct records and documents (§46(a))",
    category: "other",
  },
  "9": {
    code: "il-des-9",
    label: "Request to record a right in a design (§17)",
    category: "transfer",
  },
  "10": {
    code: "il-des-10",
    label:
      "Cancellation of a registration, of a restoration or of a correction by a third party (§48)",
    category: "cancellation",
  },
  "11": {
    code: "il-des-11",
    label: "Objection before the Registrar (§96)",
    category: "appeal",
  },
  "12": {
    code: "il-des-12",
    label: "Request to join proceedings (§98)",
    category: "other",
  },
  "13": {
    code: "il-des-13",
    label: "Extension of time (§100)",
    category: "extension",
    condition: perMonth,
  },
  "14": {
    code: "il-des-14",
    label: "Certified document (§104)",
    category: "other",
  },
  "15": { code: "il-des-15", label: "File copy (§104)", category: "other" },
};

const SMALL_ENTITY =
  "60% of the full fee (the 40% reduction) for a first application for the invention or design by an individual, a company or partnership with turnover up to NIS 10 million in the previous year, a recognized institution of higher education or its wholly owned technology-transfer company. Rounded to the nearest shekel.";

/** 60% of a whole-shekel amount, rounded half to even like Python's Decimal.quantize. */
function sixtyPercent(amount: string): string {
  const tenths = Math.round(Number(amount) * 6);
  const whole = Math.floor(tenths / 10);
  const rest = tenths % 10;
  const rounded =
    rest > 5 || (rest === 5 && whole % 2 === 1) ? whole + 1 : whole;
  return `${rounded}.00`;
}

function project(
  items: IlpoItem[],
  sections: Partial<Record<Section, Record<string, Meta>>>,
  right: "patent" | "trademark" | "design",
): FeeItem[] {
  const fees: FeeItem[] = [];
  const expected = Object.entries(sections).flatMap(([section, table]) =>
    Object.keys(table ?? {}).map((path) => `${section}:${path}`),
  );
  const found = new Set<string>();
  for (const item of items) {
    const meta = sections[item.section]?.[item.path];
    if (!sections[item.section]) continue;
    if (!meta)
      throw invalid(
        `unexpected ${item.section} item ${item.path} in the notice.`,
      );
    found.add(`${item.section}:${item.path}`);
    const fee = (
      tier: EntityTier,
      amount: string,
      notes?: string,
    ): FeeItem => ({
      code: tier === "small" ? `${meta.code}-small` : meta.code,
      label: meta.label,
      category: meta.category,
      rights: [right],
      amount,
      currency: "ILS",
      tier,
      year: meta.year ?? null,
      condition: meta.condition ?? null,
      source_url: ILPO_FEES_PDF_URL,
      notes:
        [`Item ${item.path.replace(/#\d+$/, "")}.`, meta.notes, notes]
          .filter(Boolean)
          .join(" ") || null,
    });
    if (meta.small) {
      fees.push(fee("large", item.amount));
      fees.push(fee("small", sixtyPercent(item.amount), SMALL_ENTITY));
    } else fees.push(fee("none", item.amount));
  }
  const missing = expected.filter((key) => !found.has(key));
  if (missing.length)
    throw invalid(`items missing from the notice: ${missing.join(", ")}.`);
  return fees;
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

const LANGUAGE =
  "The notice is Hebrew only; labels are English summaries of the Hebrew items, and the notice says the Reshumot (Official Gazette) publication controls. Fees are CPI-linked and republished each January.";

/** Fetches the ILPO fee notice and projects the patent, trade mark and design schedules. */
export class IlpoFeesClient {
  private readonly http: GenericHttpTransport;
  private pending: Promise<{
    items: IlpoItem[];
    effectiveDate: string;
    provenance: FeeSchedule["provenance"];
  }> | null = null;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.gov.il",
      sourceName: ILPO_FEES_SOURCE,
      headers: { accept: "application/pdf", "user-agent": USER_AGENT },
    });
  }
  /** One PDF fetch serves concurrent schedule requests. */
  private notice(options: TransportRequestOptions) {
    this.pending ??= (async () => {
      const result = await this.http.bytes("GET", PDF_PATH, options);
      const { items, effectiveDate } = ilpoItems(
        await pdfPageItems(result.data),
      );
      return {
        items,
        effectiveDate,
        provenance: {
          ...result.provenance,
          as_of_status: `in force from ${effectiveDate} per the notice`,
          effective_date: effectiveDate,
        },
      };
    })().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }
  private schedule(
    right: "patent" | "trademark" | "design",
    notice: Awaited<ReturnType<IlpoFeesClient["notice"]>>,
    fees: FeeItem[],
    extra: {
      statutory_basis: string;
      coverage: RecurringFeeCoverage;
      notes: string;
    },
  ): FeeSchedule {
    return FeeScheduleSchema.parse({
      key: `IL/ILPO/${right}`,
      jurisdiction: "IL",
      issuing_body: "Israel Patent Office",
      office_code: "ILPO",
      right,
      currency: "ILS",
      effective_date: notice.effectiveDate,
      source_url: ILPO_FEES_PDF_URL,
      statutory_basis: extra.statutory_basis,
      fees,
      recurring_fee_coverage: extra.coverage,
      unmapped_codes: [],
      notes: `${extra.notes} ${LANGUAGE}`,
      provenance: notice.provenance,
    });
  }
  /** Patent fees, PCT authority fees and patent term extension fees. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const notice = await this.notice(options);
    const fees = project(
      notice.items,
      { patent: PATENT, extension: EXTENSION },
      "patent",
    );
    return this.schedule("patent", notice, fees, {
      statutory_basis:
        "Patents Law 5727-1967; Patents Regulations (Office Practice, Procedural Rules, Documents and Fees) 5728-1968, Schedule.",
      coverage: coverage(
        fees,
        [6, 10, 14, 18, 20],
        "Renewals are paid for periods, not years: year 6 covers the term to year 6, then years 10, 14, 18 and 20 each cover the period ending that year. Patent term extension fees are years 21-25.",
      ),
      notes:
        "Renewals are stored at the last year of the period they cover (6, 10, 14, 18, 20); the comprehensive whole-term renewal (12(6)) is an alternative and is categorized other. Items 1 and 10 have a large row at the full amount and a small row at 60% for qualifying first applications. Patent term extension fees from the separate extension-order table are included.",
    });
  }
  /** Trade mark fees and the three Madrid handling fees. */
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const notice = await this.notice(options);
    const fees = project(
      notice.items,
      { trademark: TRADEMARK, madrid: MADRID },
      "trademark",
    );
    return this.schedule("trademark", notice, fees, {
      statutory_basis:
        "Trade Marks Ordinance [New Version] 5732-1972; Trade Marks Regulations 5700-1940.",
      coverage: coverage(
        fees,
        [10],
        "Registrations renew every 10 years; year 10 stands for each renewal.",
      ),
      notes: "No entity tiers. Madrid fees are ILPO's handling fees only.",
    });
  }
  /** Design fees under the Designs Law 5777-2017. */
  async getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const notice = await this.notice(options);
    const fees = project(notice.items, { design: DESIGN }, "design");
    return this.schedule("design", notice, fees, {
      statutory_basis:
        "Designs Law 5777-2017 (in force 2018-08-07); Designs Regulations.",
      coverage: coverage(
        fees,
        [10, 15, 20, 25],
        "Renewals are stored at the last year of each five-year period (10, 15, 20, 25).",
      ),
      notes:
        "Fees under the Designs Law 5777-2017. The notice also lists fees for designs filed before 2018-08-07 under the Patents and Designs Ordinance and maximum costs in proceedings; neither is included. Items 1 and 2 have a large row at the full amount and a small row at 60% for qualifying first applications. The all-periods renewal (5(5)) is an alternative and is categorized other.",
    });
  }
}

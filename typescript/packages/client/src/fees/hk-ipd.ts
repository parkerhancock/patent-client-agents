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
  type RecurringFeeCoverage,
} from "./models.js";

/**
 * The Hong Kong Intellectual Property Department publishes one
 * server-rendered "forms and fees" page per right. Each form (OP1, P10, T2,
 * D11) is an accordion holding a small fee table; filing tables split
 * e-filing and paper-filing rates, trademark tables add a per-class column.
 * The statutory schedules (Cap. 514C, 559A, 522A) are the citation, the
 * pages the extraction target, as in Python.
 */
export const HK_IPD_FEES_SOURCE = "Hong Kong IPD Forms and Fees";
const HK_IPD_BASE = "https://www.ipd.gov.hk";
const PATHS = {
  patent: "/en/patents/forms-and-fees/index.html",
  trademark: "/en/trade-marks/forms-and-fees/index.html",
  design: "/en/designs/forms-and-fees/index.html",
} as const;
export const HK_IPD_PATENTS_URL = `${HK_IPD_BASE}${PATHS.patent}`;
export const HK_IPD_TRADEMARKS_URL = `${HK_IPD_BASE}${PATHS.trademark}`;
export const HK_IPD_DESIGNS_URL = `${HK_IPD_BASE}${PATHS.design}`;
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

type Right = keyof typeof PATHS;
const SOURCE_URL: Record<Right, string> = {
  patent: HK_IPD_PATENTS_URL,
  trademark: HK_IPD_TRADEMARKS_URL,
  design: HK_IPD_DESIGNS_URL,
};
const invalid = (message: string) =>
  new ApiError(`HK IPD fee schedule: ${message}`, 200, "INVALID_RESPONSE");

/** "$1,080" -> "1080.00"; "Nil" -> "0.00"; anything without a dollar amount -> null. */
export function parseHkdAmount(raw: string): string | null {
  const value = raw.trim();
  if (/^nil$/i.test(value)) return "0.00";
  const match = /\$\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)/.exec(value);
  if (!match) return null;
  const [whole = "0", fraction = ""] = (match[1] as string)
    .replaceAll(",", "")
    .split(".");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}

interface Cell {
  text: string;
  /** Copied from a cell to the left (colspan). */
  colCopy: boolean;
  /** Copied from a cell above (rowspan): a fee shared by several rows. */
  rowCopy: boolean;
}
type Element = ReturnType<typeof parseHTML>["document"]["body"];
const clean = (value: string) => value.replace(/\s+/g, " ").trim();

/** Expand rowspan and colspan so every row has one entry per column. */
function grid(table: Element): Cell[][] {
  const out: Cell[][] = [];
  const pending: Map<number, { cell: Cell; left: number }> = new Map();
  for (const tr of table.querySelectorAll("tr")) {
    const row: Cell[] = [];
    const take = () => {
      for (;;) {
        const carry = pending.get(row.length);
        if (!carry) return;
        row.push({ ...carry.cell, colCopy: false, rowCopy: true });
        if (--carry.left === 0) pending.delete(row.length - 1);
      }
    };
    for (const td of tr.querySelectorAll("td, th")) {
      take();
      const text = clean(td.textContent);
      const rows = Math.max(1, Number(td.getAttribute("rowspan") ?? 1) || 1);
      const cols = Math.max(1, Number(td.getAttribute("colspan") ?? 1) || 1);
      for (let c = 0; c < cols; c++) {
        const cell = { text, colCopy: c > 0, rowCopy: false };
        if (rows > 1) pending.set(row.length, { cell, left: rows - 1 });
        row.push(cell);
      }
    }
    take();
    out.push(row);
  }
  return out;
}

interface Row {
  form: string | null;
  description: string;
  section: string | null;
  fee: string;
  paper: string | null;
  additional: string | null;
  shared: boolean;
}

/** Walk every fee table; carry section rows forward; split e-filing and paper rates. */
function feeRows(html: string): Row[] {
  const { document } = parseHTML(html);
  const out: Row[] = [];
  for (const table of document.querySelectorAll("table")) {
    // The accordion button reads "Form OP1<br>Request for grant ...".
    const heading = clean(
      (
        table.closest(".accordion")?.querySelector(".accordion-btn")
          ?.innerHTML ?? ""
      ).split(/<br/i)[0] ?? "",
    );
    const form = /^Form ([A-Z]+\d+[A-Z]?)$/.exec(heading)?.[1] ?? null;
    let section: string | null = null;
    let split = false;
    let additional = false;
    let header = false;
    for (const cells of grid(table)) {
      const texts = cells.map((cell) => cell.text);
      const lower = texts.map((text) => text.toLowerCase());
      if (lower[0] === "descriptions") {
        header = true;
        additional ||= lower[2]?.startsWith("additional fee") ?? false;
        split ||= lower[1] === "e-filing" && lower[2] === "paper-filing";
        continue;
      }
      if (lower[1] === "e-filing" && lower[2] === "paper-filing") {
        split = true;
        continue;
      }
      const [first, second, third] = cells;
      if (!first || !second || (!first.text && !second.text)) continue;
      if (second.colCopy || (!second.text && !third?.text)) {
        section = first.text;
        continue;
      }
      out.push({
        form,
        description: first.text,
        section,
        fee: second.text,
        paper: split && third && !third.colCopy ? third.text : null,
        additional: additional && third ? third.text : null,
        shared: second.rowCopy,
      });
    }
    if (!header) throw invalid("a fee table lost its Descriptions header.");
  }
  if (!out.length) throw invalid("no fee tables found.");
  return out;
}

/** Python's slug: each part cut to 40 characters after slugging. */
function slug(...parts: string[]): string {
  return parts
    .map((part) =>
      part
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 40),
    )
    .filter(Boolean)
    .join("-");
}
function uniquer() {
  const seen = new Set<string>();
  return (code: string) => {
    let candidate = code;
    for (let n = 2; seen.has(candidate); n++) candidate = `${code}-${n}`;
    seen.add(candidate);
    return candidate;
  };
}
/** Python labels a row with its section only when the row is a fragment ("4th to 10th year", "For each other design"). */
function label(row: Row): string {
  return row.section &&
    !row.description.includes(row.section) &&
    /^(?:\d+\s*(?:st|nd|rd|th)(?:\s|-)|For\s+(?:the\s+|each\s+))/i.test(
      row.description,
    )
    ? `${row.section} — ${row.description}`
    : row.description;
}
/** Python's patent route tag, kept in the code: ogp (O), rr (R), stp (short-term) or gen. */
function route(text: string): "ogp" | "rr" | "stp" | "gen" {
  if (text.includes("(O)")) return "ogp";
  if (text.includes("(R)")) return "rr";
  return /short-term patent/i.test(text) ? "stp" : "gen";
}
const paperCondition: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description: "Applies when the form is filed on paper; e-filing is cheaper.",
};
/** Per-page copies get a pages_over condition; per-copy and per-design fees are noted, not conditioned. */
function unitCondition(fee: string): FeeCondition | null {
  return /\bper page\b/i.test(fee)
    ? {
        trigger: "pages_over",
        threshold: 0,
        per_unit: true,
        description: "Per page.",
      }
    : null;
}

/** Form codes mapped to the closed vocabulary; row rules below take precedence. */
const FORMS: Record<Right, Record<string, FeeCategory>> = {
  patent: {
    OP1: "filing",
    OP1A: "other",
    OP2: "examination",
    OP3: "appeal",
    OP4: "examination",
    OP5: "other",
    OP6: "appeal",
    OP7: "other",
    OP8: "appeal",
    P1: "other",
    P1A: "other",
    P2: "opposition",
    P4: "filing",
    P5: "grant",
    P6: "filing",
    P6A: "other",
    P7: "other",
    P8: "other",
    P9: "other",
    P10: "renewal",
    P11: "other",
    P12: "petition",
    P13: "petition",
    P14: "other",
    P15: "cancellation",
    P16: "other",
    P17: "other",
    P18: "other",
    P19: "transfer",
    SP1: "other",
    SP2: "other",
    SP3: "extension",
  },
  trademark: {
    T1: "search",
    T2: "filing",
    T3: "other",
    T4: "other",
    T5: "other",
    T5A: "other",
    T5B: "other",
    T6: "opposition",
    T7: "opposition",
    T8: "renewal",
    T9: "other",
    T10: "transfer",
    T11: "transfer",
    T12: "other",
    T13: "extension",
    T14: "other",
  },
  design: {
    D1: "filing",
    D2: "other",
    D3: "petition",
    D4: "extension",
    D5: "transfer",
    D6: "cancellation",
    D7: "cancellation",
    D8: "other",
    D9: "opposition",
    D10: "other",
    D11: "renewal",
    D12: "other",
  },
};
function category(right: Right, row: Row): FeeCategory {
  const text = row.description;
  if (/late payment|penalty fee for late/i.test(text)) return "late_fee";
  if (
    /^advertisement fee$|for advertisement in the official journal/i.test(text)
  )
    return "publication";
  if (/^request for restoration and renewal/i.test(text)) return "late_fee";
  if (
    /revocation, declaration of invalidity|intervention in proceedings/i.test(
      text,
    )
  )
    return "cancellation";
  if (/translation/i.test(text) && right === "patent") return "translation";
  if (/cancel claim to be mortgagee/i.test(text)) return "other";
  return (row.form && FORMS[right][row.form]) || "other";
}
const ORDINAL_EXTENSION = /(\d+)(?:st|nd|rd|th)\s+5-year extension/i;
const YEAR_BAND =
  /(\d+)\s*(?:st|nd|rd|th)\s+to\s+(\d+)\s*(?:st|nd|rd|th)\s+year/i;

interface Draft {
  code: string;
  label: string;
  category: FeeCategory;
  amount: string;
  year?: number | null;
  condition?: FeeCondition | null;
  notes?: string | null;
}
const formNote = (row: Row, extra?: string | null) =>
  [row.form ? `Form ${row.form}.` : null, extra].filter(Boolean).join(" ") ||
  null;

function patentDrafts(rows: Row[]): Draft[] {
  const unique = uniquer();
  const seen = new Set<string>();
  const out: Draft[] = [];
  for (const row of rows) {
    const amount = parseHkdAmount(row.fee);
    if (amount === null) continue;
    const text = label(row);
    const tag = route(`${row.description} ${row.section ?? ""}`);
    const kind = category("patent", row);
    if (kind === "renewal") {
      const band = YEAR_BAND.exec(text);
      const years = band
        ? Array.from(
            { length: Number(band[2]) - Number(band[1]) + 1 },
            (_, i) => Number(band[1]) + i,
          )
        : tag === "stp"
          ? [5]
          : [];
      if (!years.length) throw invalid(`unrecognized renewal row ${text}`);
      for (const year of years)
        out.push({
          code: unique(slug("hk", "pat", tag, "renewal", `y${year}`)),
          label: text,
          category: "renewal",
          amount,
          year,
          notes: formNote(
            row,
            tag === "stp"
              ? "A short-term patent is renewed once, after its 4th year, for years 5-8; stored as year 5. A year-5 renewal lookup also returns the standard-patent fee; the code prefix hk-pat-stp marks this one."
              : null,
          ),
        });
      continue;
    }
    // Rows repeated across the OP1, P4, P5 and P6 filing tables collapse to one.
    const key = `${text}|${amount}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      code: unique(slug("hk", "pat", tag, text.slice(0, 60))),
      label: text,
      category: kind,
      amount,
      condition: unitCondition(row.fee),
      notes: formNote(
        row,
        /^advertisement fee$|late payment of filing fee or advertisement/i.test(
          text,
        )
          ? "The same fee applies on forms OP1, P4, P5 and P6."
          : row.paper !== null
            ? "E-filing rate."
            : null,
      ),
    });
    const paper = row.paper === null ? null : parseHkdAmount(row.paper);
    if (paper !== null && paper !== amount)
      out.push({
        code: unique(slug("hk", "pat", tag, text.slice(0, 60), "paper")),
        label: `${text} (paper filing)`,
        category: kind,
        amount: paper,
        condition: paperCondition,
        notes: formNote(row, "Paper-filing rate."),
      });
  }
  return out;
}

function trademarkDrafts(rows: Row[]): Draft[] {
  const unique = uniquer();
  const out: Draft[] = [];
  for (const row of rows) {
    const amount = parseHkdAmount(row.fee);
    if (amount === null) continue;
    const text = label(row);
    const kind = category("trademark", row);
    const year = row.form === "T8" ? 10 : null;
    const base = slug("hk", "tm", text.slice(0, 60));
    const notes: string[] = [];
    if (row.shared) notes.push("The fee is shared with the row above it.");
    if (/\(Nil for extension of time hearing\)/i.test(row.fee))
      notes.push("Nil for a hearing on an extension of time.");
    if (/per (?:certified )?copy/i.test(row.fee)) notes.push("Per copy.");
    out.push({
      code: unique(base),
      label: text,
      category: kind,
      amount,
      year,
      condition: unitCondition(row.fee),
      notes: formNote(row, notes.join(" ") || null),
    });
    const late = /Late renewal charge:\s*\$\s*([\d,]+)/i.exec(row.fee);
    if (late)
      out.push({
        code: unique(slug("hk", "tm", "late renewal charge")),
        label: `${text} — late renewal charge`,
        category: "late_fee",
        amount: parseHkdAmount(`$${late[1]}`) as string,
        year: 10,
        notes: formNote(
          row,
          "Added to the renewal fee when renewal is requested after expiry.",
        ),
      });
    const extra = row.additional ?? "";
    if (/^nil$/i.test(extra) || !extra) continue;
    const series =
      /\$([\d,]+) for the first class and \$([\d,]+) for each additional class in respect of each additional application/i.exec(
        extra,
      );
    if (series) {
      out.push({
        code: unique(`${base}-addl-application`),
        label: `${text} — each additional application, first class`,
        category: "other",
        amount: parseHkdAmount(`$${series[1]}`) as string,
        notes: formNote(
          row,
          "Per additional application created by the division.",
        ),
      });
      out.push({
        code: unique(`${base}-addl-class`),
        label: `${text} — each additional application, each additional class`,
        category: "excess_classes",
        amount: parseHkdAmount(`$${series[2]}`) as string,
        condition: {
          trigger: "classes_over",
          threshold: 1,
          per_unit: true,
          description:
            "Per class beyond the first, in each additional application.",
        },
        notes: formNote(row),
      });
      continue;
    }
    const added = parseHkdAmount(extra);
    if (added === null || !/per additional class/i.test(extra))
      throw invalid(`unrecognized additional fee ${extra.slice(0, 60)}`);
    out.push({
      code: unique(`${base}-addl-class`),
      label: `${text} — additional class`,
      category: "excess_classes",
      amount: added,
      year,
      condition: {
        trigger: "classes_over",
        threshold: 1,
        per_unit: true,
        description: /amendment of specification/i.test(extra)
          ? "Per class added by amending the specification."
          : "Per additional class beyond the first.",
      },
      notes: formNote(row),
    });
  }
  return out;
}

function designDrafts(rows: Row[]): Draft[] {
  const unique = uniquer();
  const out: Draft[] = [];
  let renewal: string | null = null;
  for (const row of rows) {
    const amount = parseHkdAmount(row.fee);
    if (amount === null) continue;
    let text = label(row);
    const kind = category("design", row);
    let year: number | null = null;
    if (kind === "renewal") {
      const ordinal = ORDINAL_EXTENSION.exec(text);
      if (!ordinal) throw invalid(`unrecognized renewal row ${text}`);
      year = Number(ordinal[1]) * 5 + 5;
      renewal ??= text.slice(0, ordinal.index).trim();
      if (ordinal.index === 0) text = `${renewal} — ${text}`;
    }
    const multi = /^For each other (?:article|design)/i.test(row.description);
    const condition: FeeCondition | null = multi
      ? {
          trigger: "multi_design",
          threshold: 1,
          per_unit: true,
          description: row.description,
        }
      : unitCondition(row.fee);
    // Codes come from the description Python labels by, so they match Python's.
    const base = slug("hk", "des", label(row).slice(0, 60));
    out.push({
      code: unique(base),
      label: text,
      category: kind,
      amount,
      year,
      condition,
      notes: formNote(
        row,
        year
          ? `Extension of registration; stored as year ${year}, the last year it covers.`
          : row.paper !== null
            ? "E-filing rate."
            : /per design/i.test(text)
              ? "Per design."
              : null,
      ),
    });
    const paper = row.paper === null ? null : parseHkdAmount(row.paper);
    if (paper !== null && paper !== amount)
      out.push({
        code: unique(`${base}-paper`),
        label: `${text} (paper filing)`,
        category: kind,
        amount: paper,
        condition: multi ? condition : paperCondition,
        notes: formNote(row, "Paper-filing rate."),
      });
  }
  return out;
}

function item(draft: Draft, right: Right): FeeItem {
  return {
    code: draft.code,
    label: draft.label.slice(0, 300),
    category: draft.category,
    rights: [right],
    amount: draft.amount,
    currency: "HKD",
    tier: "none",
    year: draft.year ?? null,
    condition: draft.condition ?? null,
    source_url: SOURCE_URL[right],
    notes: draft.notes ?? null,
  };
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

const STATUTORY: Record<Right, string> = {
  patent:
    "Patents Ordinance (Cap. 514); Patents (General) Rules (Cap. 514C), Schedule 4.",
  trademark:
    "Trade Marks Ordinance (Cap. 559); Trade Marks Rules (Cap. 559A), Schedule 1.",
  design:
    "Registered Designs Ordinance (Cap. 522); Registered Designs Rules (Cap. 522A).",
};
const NOTES: Record<Right, string> = {
  patent:
    "Codes carry Python's route tag: hk-pat-ogp (original grant, (O)), hk-pat-rr (re-registration, (R)), hk-pat-stp (short-term patent) and hk-pat-gen (any route); notes name the form. Standard-patent renewals are years 4-20; a short-term patent is renewed once, stored as year 5. Pre-grant maintenance of a standard patent (R) application (P9) is category other. Paper-filing rates carry a paper_filing condition. 'Nil' rows are zero fees. Rows repeated across the four filing tables appear once.",
  trademark:
    "Registrations renew every 10 years; renewal, the late renewal charge and restoration-with-renewal are at year 10. Per-class additional fees are separate rows with a classes_over condition. Rows that share a fee cell (opposition, revocation and intervention) each get the fee. 'Nil' rows are zero fees.",
  design:
    "Registration lasts 5 years and is extended in four 5-year periods to 25 years; extensions are stored at years 10, 15, 20 and 25. Filing fees depend on the number of designs and articles and whether they form a set; follow-on designs or articles carry a multi_design condition. Paper-filing rates carry a paper_filing condition. 'Nil' rows are zero fees.",
};
const RENEWAL_YEARS: Record<Right, number[]> = {
  patent: Array.from({ length: 17 }, (_, i) => i + 4),
  trademark: [10],
  design: [10, 15, 20, 25],
};
const COVERAGE_NOTE: Record<Right, string> = {
  patent:
    "Standard-patent renewal years 4-20 present, plus the short-term patent renewal (year 5).",
  trademark:
    "Registrations renew every 10 years; year 10 stands for each renewal.",
  design: "Extensions for years 10, 15, 20 and 25 present.",
};

/** Fetches the IPD forms-and-fees pages and projects the patent, trademark and design schedules. */
export class HkIpdFeesClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? HK_IPD_BASE,
      sourceName: HK_IPD_FEES_SOURCE,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  private async schedule(
    right: Right,
    options: TransportRequestOptions,
  ): Promise<FeeSchedule> {
    const result = await this.http.text("GET", PATHS[right], options);
    const rows = feeRows(result.data);
    const drafts =
      right === "patent"
        ? patentDrafts(rows)
        : right === "trademark"
          ? trademarkDrafts(rows)
          : designDrafts(rows);
    if (!drafts.length) throw invalid(`no ${right} fees parsed.`);
    const fees = drafts.map((draft) => item(draft, right));
    const revised = [
      "revisionDate_Year",
      "revisionDate_Month",
      "revisionDate_Day",
    ].map((name) => new RegExp(`${name} = (\\d+);`).exec(result.data)?.[1]);
    const revisedDate = revised.every(Boolean)
      ? `${revised[0]}-${(revised[1] as string).padStart(2, "0")}-${(revised[2] as string).padStart(2, "0")}`
      : null;
    return FeeScheduleSchema.parse({
      key: `HK/HKIPD/${right}`,
      jurisdiction: "HK",
      issuing_body: "Intellectual Property Department, Hong Kong SAR",
      office_code: "HKIPD",
      right,
      currency: "HKD",
      effective_date: null,
      source_url: SOURCE_URL[right],
      statutory_basis: STATUTORY[right],
      fees,
      recurring_fee_coverage: coverage(
        fees,
        RENEWAL_YEARS[right],
        COVERAGE_NOTE[right],
      ),
      unmapped_codes: [
        ...new Set(
          rows
            .filter((row) => row.form && !FORMS[right][row.form])
            .map((row) => row.form as string),
        ),
      ],
      notes: NOTES[right],
      provenance: {
        ...result.provenance,
        as_of_status: [
          "effective date not published by the office",
          revisedDate ? `page last revised ${revisedDate}` : null,
        ]
          .filter(Boolean)
          .join("; "),
        effective_date: null,
      },
    });
  }
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("patent", options);
  }
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("trademark", options);
  }
  async getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("design", options);
  }
}

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
 * IPOS publishes one server-rendered "forms and fees" page per right, each
 * with `Form | Description | Fee` tables keyed by form code (PF1, TM4, D3).
 * The statutory schedules are on Singapore Statutes Online; the pages are
 * the extraction target, as in Python.
 */
export const IPOS_FEES_SOURCE = "IPOS Forms and Fees";
const IPOS_BASE = "https://www.ipos.gov.sg";
const PATHS = {
  patent: "/about-ip/patents/forms-and-fees-singapore/",
  trademark: "/about-ip/trade-marks/forms-and-fees/",
  design: "/about-ip/designs/forms-and-fees/",
} as const;
export const IPOS_PATENTS_URL = `${IPOS_BASE}${PATHS.patent}`;
export const IPOS_TRADEMARKS_URL = `${IPOS_BASE}${PATHS.trademark}`;
export const IPOS_DESIGNS_URL = `${IPOS_BASE}${PATHS.design}`;
/**
 * Second tranche of the 2025 fee reform (Patents Circular 3/2025, Trade Marks
 * Circular 3/2025, Designs Circular 1/2025). The pages state no effective
 * date of their own, only a "last updated" date.
 */
export const IPOS_EFFECTIVE_DATE = "2026-04-01";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

type Right = keyof typeof PATHS;
const SOURCE_URL: Record<Right, string> = {
  patent: IPOS_PATENTS_URL,
  trademark: IPOS_TRADEMARKS_URL,
  design: IPOS_DESIGNS_URL,
};

const invalid = (message: string) =>
  new ApiError(`IPOS fee schedule: ${message}`, 200, "INVALID_RESPONSE");

const AMOUNT = /S?\$\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)/g;
/** "1,750" -> "1750.00"; "1800.00" -> "1800.00". */
export function parseSgdAmount(raw: string): string {
  const value = raw.replaceAll(",", "");
  if (!/^\d+(?:\.\d{1,2})?$/.test(value))
    throw invalid(`unrecognized amount ${raw.slice(0, 20)}`);
  const [whole = "0", fraction = ""] = value.split(".");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}

/** One amount in a fee cell, with the bold heading or line text that names it. */
interface CellAmount {
  amount: string;
  /** Index among every amount in the cell, as Python numbers them. */
  index: number;
  heading: string;
  line: string;
  /** A "From <date>" line precedes this amount. */
  from: string | null;
  /** Followed by "for each claim": a per-claim surcharge. */
  perClaim: boolean;
  /** Preceded by "+": an add-on to the previous amount. */
  addOn: boolean;
}
interface Row {
  form: string;
  /** Python's text (section — row), which its codes are built from. */
  description: string;
  /** The description, except that a lettered row after a nested section keeps the form's own section. */
  label: string;
  feeText: string;
  amounts: CellAmount[];
}

const clean = (value: string) => value.replace(/\s+/g, " ").trim();
/** Drop the inline PPH promotion from labels; codes keep the raw text, as in Python. */
const display = (value: string) =>
  clean(value.replace(/Save on official [^.]*PPH pilot\. Find out more/g, " "));
type Element = ReturnType<typeof parseHTML>["document"]["body"];

/** Lines of a fee cell: paragraphs and <br> breaks, flagged when wholly bold. */
function cellLines(cell: Element): { text: string; bold: boolean }[] {
  const blocks = [...cell.querySelectorAll("p")];
  const out: { text: string; bold: boolean }[] = [];
  for (const block of blocks.length ? blocks : [cell]) {
    const bold = clean(
      [...block.querySelectorAll("b, strong")]
        .map((b) => b.textContent)
        .join(""),
    );
    for (const br of [...block.querySelectorAll("br")])
      br.replaceWith(block.ownerDocument.createTextNode("\n"));
    for (const line of block.textContent.split("\n").map(clean).filter(Boolean))
      out.push({ text: line, bold: bold !== "" && bold === clean(line) });
  }
  return out;
}

function cellAmounts(cell: Element): CellAmount[] {
  const out: CellAmount[] = [];
  let heading = "";
  let from: string | null = null;
  for (const { text, bold } of cellLines(cell)) {
    const fromMatch = /^From (\d{1,2} [A-Z][a-z]+ \d{4})$/.exec(text);
    if (fromMatch) {
      from = fromMatch[1] as string;
      continue;
    }
    const matches = [...text.matchAll(AMOUNT)];
    if (!matches.length) {
      if (bold) heading = text.replace(/:$/, "");
      continue;
    }
    for (const match of matches) {
      const start = match.index ?? 0;
      const end = start + match[0].length;
      out.push({
        amount: parseSgdAmount(match[1] as string),
        index: out.length,
        heading,
        line: text,
        from,
        perClaim: /^\s*for each claim/i.test(text.slice(end)),
        addOn: text.slice(0, start).trimEnd().endsWith("+"),
      });
    }
    from = null;
  }
  return out;
}

/** Python's walker: empty Form cells continue the previous form; empty Fee cells open a section. */
function feeRows(html: string): Row[] {
  const { document } = parseHTML(html);
  // Screen-reader-only link suffixes ("opens in new tab") are not part of the text.
  for (const element of document.querySelectorAll(
    '[aria-hidden="true"], .sr-only',
  ))
    element.remove();
  const rows: Row[] = [];
  let tables = 0;
  for (const table of document.querySelectorAll("table")) {
    const trs = [...table.querySelectorAll("tr")];
    const head = [...(trs[0]?.querySelectorAll("td, th") ?? [])].map((cell) =>
      clean(cell.textContent).toLowerCase(),
    );
    if (head.join("|") !== "form|description|fee") continue;
    tables++;
    let form = "";
    let section = "";
    let formSection = "";
    for (const tr of trs.slice(1)) {
      const cells = [...tr.querySelectorAll("td, th")];
      if (cells.length < 2) continue;
      const [formCell, descriptionCell, feeCell] = (
        cells.length === 2 ? [null, ...cells] : cells
      ) as [Element | null, Element, Element];
      const rowForm = formCell ? clean(formCell.textContent) : "";
      const description = clean(descriptionCell.textContent);
      const feeText = clean(feeCell.textContent);
      if (rowForm) {
        form = rowForm;
        section = "";
        formSection = "";
      }
      if (!feeText) {
        if (description) section = description;
        formSection ||= section;
        continue;
      }
      const amounts = cellAmounts(feeCell);
      if (amounts.length !== [...feeText.matchAll(AMOUNT)].length)
        throw invalid(`fee cell layout changed: ${feeText.slice(0, 60)}`);
      const full = section ? `${section} — ${description}` : description;
      rows.push({
        form: form || "NA",
        description: full,
        label:
          /^\([a-z]\) /.test(description) &&
          formSection &&
          section !== formSection
            ? `${formSection} — ${description}`
            : full,
        feeText,
        amounts,
      });
    }
  }
  if (!tables) throw invalid("no Form | Description | Fee table found.");
  return rows;
}

/** Python's slug: lowercase, non-alphanumerics to "-", each part cut to 50 characters. */
function slug(...parts: string[]): string {
  return parts
    .map((part) =>
      part
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 50),
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
/** "1 April 2026" -> "2026-04-01". */
function isoDate(value: string): string {
  const match = /^(\d{1,2}) ([A-Z][a-z]+) (\d{4})$/.exec(value);
  const month = match ? MONTHS.indexOf(match[2] as string) + 1 : 0;
  if (!match || month === 0) throw invalid(`unrecognized date ${value}`);
  return `${match[3]}-${String(month).padStart(2, "0")}-${(match[1] as string).padStart(2, "0")}`;
}

/** Keep the current amount when a cell lists an old amount and a "From <date>" replacement. */
function current(amounts: CellAmount[], today: string): CellAmount[] {
  return amounts.filter((amount, i) => {
    const next = amounts[i + 1];
    return !(next?.from && isoDate(next.from) <= today && !amount.from);
  });
}

const perClaimCondition = (text: string): FeeCondition => {
  const match = /each claim (?:over|in excess of)\s*(\d+)\s+claims?/i.exec(
    text,
  );
  return match
    ? {
        trigger: "claims_over",
        threshold: Number(match[1]),
        per_unit: true,
        description: `Per claim in excess of ${match[1]}.`,
      }
    : {
        trigger: "claims_over",
        threshold: null,
        per_unit: true,
        description: `Per claim in excess of a number that depends on the application: ${text.slice(0, 160)}`,
      };
};
const perClass = (text: string): FeeCondition | null => {
  if (/\b(?:each subsequent|per additional) class\b/i.test(text))
    return {
      trigger: "classes_over",
      threshold: 1,
      per_unit: true,
      description: "Per additional class beyond the first.",
    };
  if (/\bper (?:amended )?class\b/i.test(text))
    return {
      trigger: "classes_over",
      threshold: 0,
      per_unit: true,
      description: "Per class, including the first.",
    };
  return null;
};

/**
 * Form codes mapped to the closed vocabulary. Rows under unknown forms
 * still appear, as `other`, and the form is listed in `unmapped_codes`.
 */
const FORMS: Record<Right, Record<string, FeeCategory>> = {
  patent: {
    NA: "other",
    PF1: "filing",
    PF2: "other",
    PF7: "other",
    PF9: "publication",
    PF10: "search",
    PF11: "search",
    PF12: "examination",
    PF12B: "examination",
    PF13A: "examination",
    PF14: "grant",
    PF15: "renewal",
    PF17: "other",
    PF19: "petition",
    PF20: "late_fee",
    PF28: "other",
    PF35: "cancellation",
    PF36: "other",
    PF37: "filing",
    PF38: "publication",
    "PF45/46/47": "extension",
    PF54: "extension",
    PF57: "other",
    PF58: "opposition",
    CM4: "other",
    CM6: "transfer",
    CM7: "transfer",
    CM8: "transfer",
    "CM10 (Only e-filing available)": "other",
    CM12: "other",
    HC1: "appeal",
    HC3: "extension",
    HC4: "appeal",
    HC5: "other",
    HC6: "opposition",
  },
  trademark: {
    TM4: "filing",
    TM8: "other",
    TM10: "other",
    TM19: "renewal",
    TM27: "other",
    CM4: "other",
    CM5: "extension",
    CM6: "transfer",
    CM7: "transfer",
    CM8: "transfer",
    CM12: "other",
    CM13: "petition",
    MP1: "madrid",
    "MM2(E)": "madrid",
    TM11: "opposition",
    TM28: "cancellation",
    HC1: "appeal",
    HC3: "extension",
    HC4: "appeal",
    HC5: "other",
    HC6: "opposition",
  },
  design: {
    D3: "filing",
    D5: "other",
    D8: "renewal",
    D13: "cancellation",
    CM4: "other",
    CM5: "extension",
    CM6: "transfer",
    CM7: "transfer",
    CM8: "transfer",
    CM10: "other",
    CM12: "other",
    CM13: "petition",
    HC1: "appeal",
    HC3: "extension",
    HC4: "appeal",
    HC5: "other",
    HC6: "opposition",
  },
};

interface Draft {
  code: string;
  label: string;
  category: FeeCategory;
  amount: string;
  year?: number | null;
  condition?: FeeCondition | null;
  notes?: string | null;
}

const RENEWAL_BAND =
  /(\d+)(?:st|nd|rd|th)?,?\s+(\d+)(?:st|nd|rd|th)?\s+or\s+(\d+)(?:st|nd|rd|th)?\s+year/i;
/** PF15 bands: "5th, 6th or 7th year" -> [5, 6, 7]; "20th year" -> [20]; "after the 20th year" -> [21]. */
export function iposRenewalYears(description: string): number[] {
  const band = RENEWAL_BAND.exec(description);
  if (band) return [1, 2, 3].map((i) => Number(band[i]));
  const single = /renewal of the\s+(\d+)(?:st|nd|rd|th)?\s+year/i.exec(
    description,
  );
  if (single) return [Number(single[1])];
  const after = /after the\s+(\d+)(?:st|nd|rd|th)?\s+year/i.exec(description);
  return after ? [Number(after[1]) + 1] : [];
}
const ACCELERATION = "additional fee for request for patent acceleration";
const LICENCE_OF_RIGHT =
  /Licences under Patent are to be Available as of Right/i;

function patentDrafts(rows: Row[], today: string): Draft[] {
  const unique = uniquer();
  const out: Draft[] = [];
  for (const row of rows) {
    if (!row.amounts.length) continue;
    const { form, description } = row;
    const label = `${form}: ${display(row.label)}`;
    const base = FORMS.patent[form] ?? "other";
    const amounts = current(row.amounts, today);

    if (form === "PF15" || form === "PF20") {
      const years = iposRenewalYears(description);
      const lor = LICENCE_OF_RIGHT.test(description);
      const late = /late payment/i.test(description);
      for (const { amount } of amounts) {
        if (form === "PF20" && !years.length) {
          out.push({
            code: unique(slug("sg-pat", form, description.slice(0, 40))),
            label: `${form}: Additional fee for restoration of patent`,
            category: "late_fee",
            amount,
            notes:
              "Paid with the renewal fees due for each year the patent was lapsed (the PF20 year rows).",
          });
          continue;
        }
        if (!years.length) {
          if (!late) throw invalid(`unrecognized ${form} row ${label}`);
          out.push({
            code: unique(
              slug("sg-pat", form, lor ? "lor" : "", description.slice(0, 40)),
            ),
            label,
            category: "late_fee",
            amount,
            notes: lor ? "Licence-of-right patents (PF28 entry made)." : null,
          });
          continue;
        }
        for (const year of years)
          out.push({
            code: unique(
              slug("sg-pat", form, lor ? "lor" : "", "y", `${year}`),
            ),
            label,
            // Restoration renewals and licence-of-right renewals are not the standard renewal ladder.
            category: form === "PF20" ? "late_fee" : lor ? "other" : "renewal",
            amount,
            year,
            notes:
              form === "PF20"
                ? "Renewal fee for this year, paid on restoration with the PF20 additional fee."
                : lor
                  ? "Renewal fee for a patent endorsed licence of right (half the standard PF15 fee); category other so renewal lookups return the standard fee."
                  : year === 21
                    ? "Each year of renewal after the 20th year (term extended under PF54); stored as year 21."
                    : null,
          });
      }
      continue;
    }

    const lowerDescription = description.toLowerCase();
    let standard = amounts;
    let acceleration: CellAmount[] = [];
    let standardDescription = description;
    if (lowerDescription.includes(ACCELERATION)) {
      if (
        lowerDescription.startsWith(ACCELERATION) ||
        lowerDescription.includes(` — ${ACCELERATION}`)
      ) {
        standard = [];
        acceleration = amounts;
      } else if (amounts.length >= 4) {
        // PF12 concatenates base, per-claim, Fast 4 and Fast 8 into one cell.
        standard = amounts.slice(0, -2);
        acceleration = amounts.slice(-2);
        standardDescription = description
          .slice(0, lowerDescription.indexOf(ACCELERATION))
          .replace(/[\s—]+$/, "");
      }
    }
    for (const amount of standard.filter((a) => !a.perClaim)) {
      const suffix = amount.index === 0 ? "" : `v${amount.index + 1}`;
      out.push({
        code: unique(
          slug("sg-pat", form, standardDescription.slice(0, 40), suffix),
        ),
        label: `${form}: ${display(row.label === description ? standardDescription : row.label)}`,
        category: base,
        amount: amount.amount,
      });
    }
    for (const amount of standard.filter((a) => a.perClaim)) {
      const alone = standard.length === 1;
      out.push({
        code: unique(
          alone
            ? slug("sg-pat", form, standardDescription.slice(0, 40))
            : slug("sg-pat", form, "excess-claims"),
        ),
        label: alone
          ? `${form}: ${display(row.label === description ? standardDescription : row.label)}`
          : `${form}: excess claims surcharge`,
        category: "excess_claims",
        amount: amount.amount,
        condition: perClaimCondition(row.feeText),
        notes: alone ? null : `Surcharge over the base ${form} fee.`,
      });
    }
    const variants =
      acceleration.length === 2
        ? ["SG Patents Fast 4", "SG Patents Fast 8"]
        : acceleration.map(() => "Patent acceleration");
    acceleration.forEach((amount, i) => {
      out.push({
        code: unique(slug("sg-pat", form, "acceleration", variants[i] ?? "")),
        label: `${form}: Additional fee for ${variants[i]}`,
        category: base,
        amount: amount.amount,
      });
    });
  }
  return out;
}

function trademarkDrafts(rows: Row[], today: string): Draft[] {
  const unique = uniquer();
  const out: Draft[] = [];
  for (const row of rows) {
    if (!row.amounts.length) continue;
    const { form, description } = row;
    const base = FORMS.trademark[form] ?? "other";
    const amounts = current(row.amounts, today);
    if (form === "TM4") {
      const bases = amounts.filter((a) => !a.addOn);
      const addOns = amounts.filter((a) => a.addOn);
      if (bases.length !== 2 || addOns.length > 2)
        throw invalid("TM4 no longer lists two specification rates.");
      const kinds = ["preapproved", "custom"] as const;
      const notes = [
        "Specification fully adopted from IPOS' Classification Database.",
        "Specification not fully adopted from IPOS' Classification Database.",
      ];
      bases.forEach((amount, i) => {
        out.push({
          code: unique(slug("sg-tm", form, kinds[i] as string)),
          label: `${form}: ${row.label} (${kinds[i]})`,
          category: "filing",
          amount: amount.amount,
          condition: perClass(amount.line),
          notes: notes[i] as string,
        });
      });
      addOns.forEach((amount, i) => {
        out.push({
          code: unique(slug("sg-tm", form, "acceleration", kinds[i] as string)),
          label: `${form}: Acceleration under SG Trade Marks Fast (${kinds[i]})`,
          category: "filing",
          amount: amount.amount,
          condition: perClass(amount.line),
          notes: "Added to the TM4 class fee; requested only at filing.",
        });
      });
      continue;
    }
    for (const amount of amounts) {
      const suffix = amount.index === 0 ? "" : `v${amount.index + 1}`;
      const part = subLabel(amount, description);
      let category = base;
      let year: number | null = null;
      let condition = perClass(amount.line);
      if (form === "TM19") {
        category = /^Renewal of registration/i.test(part ?? "")
          ? "renewal"
          : "late_fee";
        year = 10;
      }
      if (form === "HC1")
        condition =
          amount.index === 0
            ? null
            : {
                trigger: "classes_over",
                threshold: 1,
                per_unit: true,
                description: "Per additional class beyond the first.",
              };
      out.push({
        code: unique(slug("sg-tm", form, description.slice(0, 40), suffix)),
        label: `${form}: ${row.label}${part ? ` — ${part}` : ""}`,
        category,
        amount: amount.amount,
        year,
        condition,
        notes: amount.from
          ? `Amount in force from ${amount.from}; the superseded amount is not listed.`
          : form === "MP1" || form === "MM2(E)"
            ? "Fee payable to IPOS; WIPO's fees in Swiss francs are separate."
            : null,
      });
    }
  }
  return out;
}

/** Name of one of several amounts in a cell: its bold heading, the text before it, or the lettered item it answers. */
function subLabel(amount: CellAmount, description: string): string | null {
  const before = clean(amount.line.split(/S?\$/)[0] ?? "").replace(/[:+]$/, "");
  const letter = /^([a-z])\.$/.exec(before);
  if (letter) {
    const item = new RegExp(`${letter[1]}\\. (.+?)(?=[a-z]\\. [A-Z]|$)`).exec(
      description,
    );
    return item ? clean(item[1] as string) : before;
  }
  const parts = [amount.heading, before].filter(Boolean);
  return parts.length ? parts.join(": ") : null;
}

const DESIGN_PERIODS: Record<string, number> = {
  first: 10,
  second: 15,
  third: 20,
  fourth: 25,
};
function designDrafts(rows: Row[], today: string): Draft[] {
  const unique = uniquer();
  const out: Draft[] = [];
  for (const row of rows) {
    if (!row.amounts.length) continue;
    const { form, description } = row;
    const amounts = current(row.amounts, today);
    for (const amount of amounts) {
      const suffix = amount.index === 0 ? "" : `v${amount.index + 1}`;
      let category = FORMS.design[form] ?? "other";
      let year: number | null = null;
      let notes: string | null = null;
      if (form === "D3" && /each request/i.test(amount.line)) {
        category = "deferment";
        notes = "Request for deferment of publication, per request.";
      }
      if (form === "D8") {
        const period = /for the (first|second|third|fourth) period/i.exec(
          description,
        );
        if (period) {
          year = DESIGN_PERIODS[(period[1] as string).toLowerCase()] ?? null;
          notes = `Extension for the ${(period[1] as string).toLowerCase()} further 5-year period; stored as year ${year}, the last year it covers.`;
        } else if (/restoration/i.test(description)) category = "petition";
        else if (/late application/i.test(description)) category = "late_fee";
        else throw invalid(`unrecognized D8 row ${description.slice(0, 60)}`);
      }
      out.push({
        code: unique(slug("sg-des", form, description.slice(0, 40), suffix)),
        label: `${form}: ${row.label}${amounts.length > 1 ? ` — ${clean(amount.line)}` : ""}`,
        category,
        amount: amount.amount,
        year,
        notes,
      });
    }
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
    currency: "SGD",
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
    "Patents Act 1994 and Patents Rules (SSO SL/PA1994-R1), First Schedule; Patents Circular 3/2025 (two tranches, 2025-09-01 and 2026-04-01).",
  trademark:
    "Trade Marks Act 1998 and Trade Marks Rules (SSO SL/TMA1998-R1); Trade Marks Circular 3/2025 (two tranches, 2025-09-01 and 2026-04-01).",
  design:
    "Registered Designs Act 2000 and Registered Designs Rules (SSO SL/RDA2000-R1); Designs Circular 1/2025 (two tranches, 2025-09-01 and 2026-04-01).",
};
const NOTES: Record<Right, string> = {
  patent:
    "Rows follow the PF form codes. PF15 renewal bands expand to one fee per year, years 5-20; 'each year after the 20th' (term extended under PF54) is stored as year 21. Licence-of-right renewals (half fees) and the renewal fees paid on restoration (PF20) carry years but are not in the renewal category, so a renewal lookup returns one standard fee. PF11, PF12 and PF14 per-claim surcharges are separate excess_claims rows; PF14's branches by request date are kept as separate grant rows. The PCT receiving-office, ISA and IPEA fee tables on the page are not included.",
  trademark:
    "TM4 has two per-class rates, chosen by whether the specification is fully adopted from IPOS' Classification Database (not an entity tier), plus SG Trade Marks Fast acceleration add-ons. Registrations renew every 10 years; TM19's late-renewal and restoration rates are late fees at year 10. Where a cell lists an old amount and a 'From <date>' amount now in force, only the current amount is kept. Madrid fees are the amounts payable to IPOS; WIPO's Swiss-franc fees are not included.",
  design:
    "Registration lasts 5 years and is extended in four further 5-year periods to 25 years; D8 extension fees are stored at years 10, 15, 20 and 25. D3 lists the per-design filing fee and the per-request deferment fee separately.",
};
const RENEWAL_YEARS: Record<Right, number[]> = {
  patent: Array.from({ length: 16 }, (_, i) => i + 5),
  trademark: [10],
  design: [10, 15, 20, 25],
};
const COVERAGE_NOTE: Record<Right, string> = {
  patent: "PF15 renewal years 5-20 present, plus each year after the 20th.",
  trademark:
    "Registrations renew every 10 years; year 10 stands for each renewal.",
  design: "Extensions for years 10, 15, 20 and 25 present.",
};

/** Fetches the IPOS forms-and-fees pages and projects the patent, trademark and design schedules. */
export class IposFeesClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? IPOS_BASE,
      sourceName: IPOS_FEES_SOURCE,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  private async schedule(
    right: Right,
    options: TransportRequestOptions,
  ): Promise<FeeSchedule> {
    const result = await this.http.text("GET", PATHS[right], options);
    const rows = feeRows(result.data);
    const today = result.provenance.retrieved_at.slice(0, 10);
    const drafts =
      right === "patent"
        ? patentDrafts(rows, today)
        : right === "trademark"
          ? trademarkDrafts(rows, today)
          : designDrafts(rows, today);
    if (!drafts.length) throw invalid(`no ${right} fees parsed.`);
    const fees = drafts.map((draft) => item(draft, right));
    const updated = /Last updated on (\d{1,2} [A-Z][a-z]+ \d{4})/.exec(
      result.data,
    );
    const status = [
      IPOS_EFFECTIVE_DATE > today
        ? `scheduled to take effect ${IPOS_EFFECTIVE_DATE}`
        : `effective ${IPOS_EFFECTIVE_DATE} (second tranche of the 2025 fee reform)`,
      updated ? `page last updated ${isoDate(updated[1] as string)}` : null,
    ]
      .filter(Boolean)
      .join("; ");
    return FeeScheduleSchema.parse({
      key: `SG/IPOS/${right}`,
      jurisdiction: "SG",
      issuing_body: "Intellectual Property Office of Singapore",
      office_code: "IPOS",
      right,
      currency: "SGD",
      effective_date: IPOS_EFFECTIVE_DATE,
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
            .filter((row) => row.amounts.length && !FORMS[right][row.form])
            .map((row) => row.form),
        ),
      ],
      notes: NOTES[right],
      provenance: {
        ...result.provenance,
        as_of_status: status,
        effective_date: IPOS_EFFECTIVE_DATE,
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

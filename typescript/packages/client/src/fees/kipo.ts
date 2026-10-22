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
 * KIPO publishes its fees on two English HTML pages, one table per right:
 * patents, utility models and PCT on one page; trademarks and designs on
 * the other. Each table has two columns (description, fee in KRW) with
 * colspan section rows ("Application Fee", "Annual Fee", ...). A fee with
 * sub-items ("a. Basic fee / b. Additional fee for each claim") spans
 * several rows: the description cell has a rowspan and the following rows
 * carry only further amounts. KIPO publishes no fee codes, so codes are
 * stable slugs. Utility model and PCT tables are not routed (as in Python).
 */
export const KIPO_FEES_SOURCE = "KIPO fee schedule";
export const KIPO_PATENT_FEES_URL =
  "https://www.kipo.go.kr/en/HtmlApp?c=92004&catmenu=ek03_04_01";
export const KIPO_TRADEMARK_DESIGN_FEES_URL =
  "https://www.kipo.go.kr/en/HtmlApp?c=93006&catmenu=ek04_04_01";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`KIPO fee page: ${message}`, 200, "INVALID_RESPONSE");

const MONTHS = [
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
];
/** "August 1, 2023" or "10 February 2026" -> ISO date. */
function isoDate(value: string): string {
  const match =
    /^([A-Za-z]+) (\d{1,2}), (\d{4})$/.exec(value) ??
    /^(\d{1,2}) ([A-Za-z]+) (\d{4})$/.exec(value);
  if (!match) throw invalid(`unrecognized date ${value}`);
  const [monthName, day] = /^\d/.test(match[1] as string)
    ? [match[2] as string, match[1] as string]
    : [match[1] as string, match[2] as string];
  const month = MONTHS.indexOf(monthName.toLowerCase()) + 1;
  if (month === 0) throw invalid(`unrecognized date ${value}`);
  return `${match[3]}-${String(month).padStart(2, "0")}-${day.padStart(2, "0")}`;
}

/** "18,000" -> "18000". KIPO amounts are whole won with thousands commas. */
export function parseKrwAmount(raw: string): string {
  const value = raw.trim();
  if (!/^\d{1,3}(?:,\d{3})*$/.test(value))
    throw invalid(`unrecognized amount ${value.slice(0, 30)}`);
  return value.replaceAll(",", "");
}

const squash = (value: string) => value.replace(/\s+/g, " ").trim();

/** One logical fee row: its section, description and every amount line, including rowspan continuations. */
export interface KipoEntry {
  section: string;
  description: string;
  fee: string;
}
interface Amount {
  value: string;
  channel: "e" | "p" | ".";
}

function cellText(cell: Element): string {
  for (const br of Array.from(cell.querySelectorAll("br")))
    br.replaceWith("\n");
  return (cell.textContent ?? "")
    .split("\n")
    .map(squash)
    .filter(Boolean)
    .join("\n");
}

/** Walk a two-column KIPO table into entries, using rowspan to attach continuation rows. */
function entries(table: Element): KipoEntry[] {
  const out: KipoEntry[] = [];
  let section = "";
  let continuation = 0;
  for (const tr of Array.from(table.querySelectorAll("tr"))) {
    const cells = Array.from(tr.children).filter((cell) =>
      ["TD", "TH"].includes(cell.tagName.toUpperCase()),
    );
    if (!cells.length) continue;
    const texts = cells.map(cellText);
    if (continuation > 0) {
      continuation--;
      const last = out.at(-1);
      if (!last) throw invalid("a continuation row has no fee row.");
      last.fee = [last.fee, ...texts].filter(Boolean).join("\n");
      continue;
    }
    if (/^description$/i.test(texts[0] ?? "")) continue;
    if (cells.length === 1) {
      if (Number(cells[0]?.getAttribute("colspan") ?? 1) < 2)
        throw invalid(`unexpected single-cell row ${texts[0]?.slice(0, 40)}.`);
      section = squash(texts[0] ?? "");
      continue;
    }
    if (cells.length !== 2) throw invalid(`a row has ${cells.length} cells.`);
    continuation = Number(cells[0]?.getAttribute("rowspan") ?? 1) - 1;
    out.push({
      section,
      description: squash(texts[0] ?? ""),
      fee: texts[1] ?? "",
    });
  }
  if (continuation > 0) throw invalid("a rowspan runs past the table.");
  return out;
}

const AMOUNT = /(\d{1,3}(?:,\d{3})+)(?:\s*\(([^)]*)\))?/g;
function amounts(fee: string): { amounts: Amount[]; rest: string } {
  const found: Amount[] = [];
  for (const match of fee.matchAll(AMOUNT)) {
    const label = (match[2] ?? "").toLowerCase();
    if (label && !/electronic|paper/.test(label))
      throw invalid(`unrecognized amount label ${label}.`);
    found.push({
      value: parseKrwAmount(match[1] as string),
      channel: label.includes("electronic")
        ? "e"
        : label.includes("paper")
          ? "p"
          : ".",
    });
  }
  return { amounts: found, rest: squash(fee.replace(AMOUNT, " ")) };
}

type Draft = Omit<
  FeeItem,
  "rights" | "currency" | "tier" | "source_url" | "year" | "condition" | "notes"
> & {
  year?: number | undefined;
  condition?: FeeCondition | undefined;
  notes?: string | undefined;
};
const fee = (
  code: string,
  label: string,
  category: FeeCategory,
  amount: string,
  extra: Pick<Draft, "year" | "condition" | "notes"> = {},
): Draft => ({ code, label, category, amount, ...extra });

const PAPER: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description: "Applies when the filing is made on paper.",
};
const PER_CLAIM: FeeCondition = {
  trigger: "claims_over",
  threshold: 0,
  per_unit: true,
  description: "Per claim, including the first.",
};
const PER_CLASS: FeeCondition = {
  trigger: "classes_over",
  threshold: 0,
  per_unit: true,
  description: "Per class, including the first.",
};
const PAGES_OVER_20: FeeCondition = {
  trigger: "pages_over",
  threshold: 20,
  per_unit: true,
  description:
    "Per page when the description, drawings and abstract exceed 20 pages.",
};
const EXCESS_GOODS =
  "Per designated good beyond 10 in each class. KIPO counts goods, not classes, so no condition trigger applies.";

/** Electronic then paper variants of one fee. */
const electronicPaper = (
  code: string,
  label: string,
  category: FeeCategory,
  [electronic, paper]: string[],
  extra: Pick<Draft, "year" | "notes"> & { condition?: FeeCondition } = {},
): Draft[] => [
  fee(
    `${code}-electronic`,
    `${label} (electronic)`,
    category,
    electronic as string,
    extra,
  ),
  fee(`${code}-paper`, `${label} (paper)`, category, paper as string, {
    ...extra,
    condition: PAPER,
    notes:
      [extra.notes, extra.condition?.description].filter(Boolean).join(" ") ||
      undefined,
  }),
];

const range = (from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, i) => from + i);

interface Rule {
  section: string;
  match: RegExp;
  /** Expected amount channels in order: e electronic, p paper, . unlabeled. */
  channels: string;
  /** Text other than amounts expected in the fee cell. */
  rest?: string;
  build: (amounts: string[], entry: KipoEntry) => Draft[];
}

const PATENT_RULES: Rule[] = [
  {
    section: "Application Fee",
    match: /^Patent Application \(Electronic\)$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-patent-application-electronic",
        "Patent application (electronic)",
        "filing",
        a as string,
      ),
    ],
  },
  {
    section: "Application Fee",
    match:
      /^Patent Application \(Paper\) a\. Basic fee b\. Additional fee for each page when the total of the description, drawing, and abstract exceeds 20 pages$/,
    channels: "..",
    build: ([basic, page]) => [
      fee(
        "kr-patent-application-paper",
        "Patent application (paper) - basic fee",
        "filing",
        basic as string,
        { condition: PAPER },
      ),
      fee(
        "kr-patent-application-paper-page-fee",
        "Patent application (paper) - additional fee for each page over 20",
        "excess_pages",
        page as string,
        { condition: PAGES_OVER_20, notes: "Paper applications only." },
      ),
    ],
  },
  {
    section: "Application Fee",
    match:
      /^Application for an extension of the term of a patent right, for each application$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-patent-term-extension",
        "Application for an extension of the term of a patent right",
        "other",
        a as string,
        { notes: "Patent term extension, not an extension of time." },
      ),
    ],
  },
  {
    section: "Examination Fee",
    match:
      /^Application for a priority claim a\. Basic fee b\. Additional fee for each priority claim$/,
    channels: "epep",
    build: ([be, bp, ae, ap]) => [
      ...electronicPaper(
        "kr-priority-claim",
        "Application for a priority claim - basic fee",
        "other",
        [be, bp] as string[],
      ),
      ...electronicPaper(
        "kr-priority-claim-additional",
        "Application for a priority claim - additional fee for each priority claim",
        "other",
        [ae, ap] as string[],
        { notes: "Per priority claim." },
      ),
    ],
  },
  {
    section: "Examination Fee",
    match:
      /^Request for substantive examination a\. Basic fee b\. Additional fee for each patent claim$/,
    channels: "..",
    build: ([basic, claim]) => [
      fee(
        "kr-substantive-examination",
        "Request for substantive examination - basic fee",
        "examination",
        basic as string,
      ),
      fee(
        "kr-substantive-examination-per-claim",
        "Request for substantive examination - additional fee for each claim",
        "excess_claims",
        claim as string,
        { condition: PER_CLAIM },
      ),
    ],
  },
  {
    section: "Examination Fee",
    match:
      /^Request for reexamination a\. Basic fee b\. Additional fee for each patent claim$/,
    channels: "..",
    build: ([basic, claim]) => [
      fee(
        "kr-reexamination",
        "Request for reexamination - basic fee",
        "examination",
        basic as string,
      ),
      fee(
        "kr-reexamination-per-claim",
        "Request for reexamination - additional fee for each claim",
        "excess_claims",
        claim as string,
        { condition: PER_CLAIM },
      ),
    ],
  },
  {
    section: "Examination Fee",
    match: /^Request for a preferential examination$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-preferential-examination",
        "Request for a preferential examination",
        "petition",
        a as string,
      ),
    ],
  },
  ...(
    [
      [1, 3],
      [4, 6],
      [7, 9],
      [10, 12],
      [13, 15],
      [16, 25],
    ] as const
  ).map(
    ([from, to]): Rule => ({
      section: "Annual Fee",
      match: new RegExp(
        `^${from} to ${to} years(?: \\(Grant fee is included\\))? a\\. Annual basic fee b\\. Annual additional fee for each claim$`,
      ),
      channels: "..",
      build: ([basic, claim]) => {
        const notes = `Band ${from}-${to} years.${from === 1 ? " Grant fee is included; years 1-3 are paid together at registration." : ""}`;
        return range(from, to).flatMap((year) => [
          fee(
            `kr-annual-fee-y${year}`,
            `Annual fee, year ${year} - basic fee`,
            "renewal",
            basic as string,
            { year, notes },
          ),
          fee(
            `kr-annual-fee-per-claim-y${year}`,
            `Annual fee, year ${year} - additional fee for each claim`,
            "excess_claims",
            claim as string,
            { year, condition: PER_CLAIM, notes },
          ),
        ]);
      },
    }),
  ),
  {
    section: "Others",
    match:
      /^Converted application fee Utility model application into Patent application\s?\(On-line\)$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-converted-application-electronic",
        "Converted application fee: utility model application into patent application (electronic)",
        "filing",
        a as string,
      ),
    ],
  },
  {
    section: "Others",
    match:
      /^Utility model application into Patent application\s?\(Paper\) a\. Basic fee b\. Additional fee for each page when the total of the description, drawing, and abstract exceeds 20 pages$/,
    channels: "..",
    build: ([basic, page]) => [
      fee(
        "kr-converted-application-paper",
        "Converted application fee: utility model application into patent application (paper) - basic fee",
        "filing",
        basic as string,
        { condition: PAPER },
      ),
      fee(
        "kr-converted-application-paper-page-fee",
        "Converted application fee (paper) - additional fee for each page over 20",
        "excess_pages",
        page as string,
        { condition: PAGES_OVER_20, notes: "Paper applications only." },
      ),
    ],
  },
];

/** Lump-sum and two-installment registration-type fees: [lump, lump goods, installment, installment goods]. */
const installments = (
  code: string,
  label: string,
  category: FeeCategory,
  [lump, lumpGoods, part, partGoods]: string[],
  year?: number,
  notes?: string,
): Draft[] => {
  const with_ = (extra: string) => [notes, extra].filter(Boolean).join(" ");
  const base = year === undefined ? {} : { year };
  return [
    fee(
      code,
      `${label} - single lump sum, per class`,
      category,
      lump as string,
      { ...base, condition: PER_CLASS, notes: with_("") || undefined },
    ),
    fee(
      `${code}-excess-goods`,
      `${label} - single lump sum, per designated good over 10 in each class`,
      "excess_classes",
      lumpGoods as string,
      { ...base, notes: with_(EXCESS_GOODS) },
    ),
    fee(
      `${code}-installment`,
      `${label} - each of two installments, per class`,
      category,
      part as string,
      {
        ...base,
        condition: PER_CLASS,
        notes: with_(
          "Payable in two installments; the amount is per installment.",
        ),
      },
    ),
    fee(
      `${code}-installment-excess-goods`,
      `${label} - each of two installments, per designated good over 10 in each class`,
      "excess_classes",
      partGoods as string,
      { ...base, notes: with_(EXCESS_GOODS) },
    ),
  ];
};

const TRADEMARK_RULES: Rule[] = [
  {
    section: "Application Fee",
    match: /^Trademark application fee for each class \(Electronic\)$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-tm-application-electronic",
        "Trademark application fee for each class (electronic)",
        "filing",
        a as string,
        { condition: PER_CLASS },
      ),
    ],
  },
  {
    section: "Application Fee",
    match:
      /^Trademark application fee for each class \(Paper\) \* Additional charge per number of designated goods exceeding 10 for each class\s?\(Electronic & Paper\)$/,
    channels: "..",
    build: ([paper, goods]) => [
      fee(
        "kr-tm-application-paper",
        "Trademark application fee for each class (paper)",
        "filing",
        paper as string,
        { condition: PAPER, notes: "Per class, including the first." },
      ),
      fee(
        "kr-tm-application-excess-goods",
        "Trademark application - additional charge per designated good over 10 in each class (electronic and paper)",
        "excess_classes",
        goods as string,
        { notes: EXCESS_GOODS },
      ),
    ],
  },
  {
    section: "Examination Fee",
    match: /^Application for a priority claim$/,
    channels: "ep",
    build: (a) =>
      electronicPaper(
        "kr-tm-priority-claim",
        "Application for a priority claim",
        "other",
        a,
      ),
  },
  {
    section: "Examination Fee",
    match: /^Request for a preferential examination$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-tm-preferential-examination",
        "Request for a preferential examination",
        "petition",
        a as string,
      ),
    ],
  },
  {
    section: "Registration Fee",
    match:
      /^Registration for establishment of right a\. Single lump sum payment/,
    channels: "....",
    build: (a) =>
      installments(
        "kr-tm-registration",
        "Registration for establishment of right",
        "grant",
        a,
      ),
  },
  {
    section: "Registration Fee",
    match:
      /^Additional registration of designated goods \* Additional charge per number of designated goods exceeding 10 for each class$/,
    channels: "..",
    build: ([basic, goods]) => [
      fee(
        "kr-tm-additional-goods-registration",
        "Additional registration of designated goods, per class",
        "grant",
        basic as string,
        { condition: PER_CLASS },
      ),
      fee(
        "kr-tm-additional-goods-registration-excess-goods",
        "Additional registration of designated goods - per designated good over 10 in each class",
        "excess_classes",
        goods as string,
        { notes: EXCESS_GOODS },
      ),
    ],
  },
  {
    section: "Registration Fee",
    match: /^Renewal of registration a\. Single lump sum payment/,
    channels: "....",
    build: (a) =>
      installments(
        "kr-tm-renewal",
        "Renewal of registration",
        "renewal",
        a,
        10,
        "Registrations renew every 10 years; year 10 stands for each renewal.",
      ),
  },
  {
    section: "Registration Fee",
    match:
      /^Late renewal of registration \(When renewal is applied for after the expiration of the term of registration\): a\. Single lump sum payment/,
    channels: "....",
    build: (a) =>
      installments(
        "kr-tm-late-renewal",
        "Late renewal of registration",
        "late_fee",
        a,
        10,
        "The full fee when renewal is requested after the term expires, in place of the renewal fee.",
      ),
  },
  {
    section: "Others",
    match:
      /^Request to divide types of goods or designated goods : a\. When dividing multiple-designated trademark application, for each divided application: b\. Others:$/,
    channels: ".",
    rest: "Application fee",
    build: ([a]) => [
      fee(
        "kr-tm-division",
        "Request to divide a multiple-designated trademark application, for each divided application",
        "other",
        a as string,
        { notes: "Other divisions are charged the application fee." },
      ),
    ],
  },
  {
    section: "Others",
    match: /^Filling an opposition to a registration, for each class$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-tm-opposition",
        "Filing an opposition to a registration, for each class",
        "opposition",
        a as string,
        { condition: PER_CLASS },
      ),
    ],
  },
  {
    section: "Others",
    match:
      /^Converted application fee Trademark application into service mark application, for each case$/,
    channels: "ep",
    build: (a) =>
      electronicPaper(
        "kr-tm-converted-application",
        "Converted application fee: trademark application into service mark application",
        "other",
        a,
      ),
  },
];

const designBands = (description: string) =>
  [...description.matchAll(/[a-e]\. (\d+) to (\d+) years, annually/g)].map(
    (match) => [Number(match[1]), Number(match[2])] as const,
  );
const annuity =
  (code: string, track: string, extraNote: string) =>
  (values: string[], entry: KipoEntry): Draft[] => {
    const bands = designBands(entry.description);
    if (bands.length !== values.length)
      throw invalid(`${track} annual fee bands and amounts differ.`);
    return bands.flatMap(([from, to], index) =>
      range(from, to).map((year) =>
        fee(
          `${code}-y${year}`,
          `Annual fee, ${track}, year ${year}, for each design`,
          "renewal",
          values[index] as string,
          {
            year,
            notes: `Band ${from}-${to} years.${from === 1 ? " Grant fee is included." : ""} ${extraNote}`,
          },
        ),
      ),
    );
  };

const DESIGN_RULES: Rule[] = [
  {
    section: "Application Fee",
    match:
      /^Request for a substantive examination a\. Design application fee \(Electronic\): b\. Design application fee\s?\(Paper\):$/,
    channels: "..",
    build: (a) =>
      electronicPaper(
        "kr-des-application-substantive",
        "Design application fee, substantive examination",
        "filing",
        a,
      ),
  },
  {
    section: "Application Fee",
    match:
      /^Request for partial-substantive examination a\. Design application fee for each design \(Electronic\) : b\. Design application fee for each design \(Paper\):$/,
    channels: "..",
    build: (a) =>
      electronicPaper(
        "kr-des-application-partial-substantive",
        "Design application fee for each design, partial-substantive examination",
        "filing",
        a,
      ),
  },
  {
    section: "Examination Fee",
    match:
      /^Application for a priority design, for each priority design a\. Basic fee$/,
    channels: "ep",
    build: (a) =>
      electronicPaper(
        "kr-des-priority-claim",
        "Application for a priority design, for each priority design",
        "other",
        a,
      ),
  },
  {
    section: "Examination Fee",
    match:
      /^Request for a reexamination, for each design \(Electronic\): a\. Basic fee$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-des-reexamination-electronic",
        "Request for a reexamination, for each design (electronic)",
        "examination",
        a as string,
      ),
    ],
  },
  {
    section: "Examination Fee",
    match: /^Request for a reexamination, for each design \(Paper\):$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-des-reexamination-paper",
        "Request for a reexamination, for each design (paper)",
        "examination",
        a as string,
        { condition: PAPER },
      ),
    ],
  },
  {
    section: "Examination Fee",
    match: /^Request for a preferential examination$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-des-preferential-examination",
        "Request for a preferential examination",
        "petition",
        a as string,
      ),
    ],
  },
  {
    section: "Annual Fee",
    match: /^Substantive examination a\. 1 to 3 years/,
    channels: ".....",
    build: annuity(
      "kr-des-annuity-substantive",
      "substantive examination",
      "Designs registered after substantive examination.",
    ),
  },
  {
    section: "Annual Fee",
    match: /^Partial-substantive examination a\. 1 to 3 years/,
    channels: "..",
    build: annuity(
      "kr-des-annuity-partial-substantive",
      "partial-substantive examination",
      "Designs registered after partial-substantive examination.",
    ),
  },
  {
    section: "Others",
    match:
      /^Converting non-substantive examination into substantive examination \(Electronic\):$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-des-conversion-to-substantive-electronic",
        "Converting non-substantive examination into substantive examination (electronic)",
        "other",
        a as string,
      ),
    ],
  },
  {
    section: "Others",
    match:
      /^Converting non-substantive examination into substantive examination \(Paper\) :$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-des-conversion-to-substantive-paper",
        "Converting non-substantive examination into substantive examination (paper)",
        "other",
        a as string,
        { condition: PAPER },
      ),
    ],
  },
  {
    section: "Others",
    match: /^Request for a secret design, for each design :$/,
    channels: "ep",
    build: (a) =>
      electronicPaper(
        "kr-des-secret-design",
        "Request for a secret design, for each design",
        "other",
        a,
      ),
  },
  {
    section: "Others",
    match: /^Request for laying-open of a design application, for each case :$/,
    channels: "ep",
    build: (a) =>
      electronicPaper(
        "kr-des-laying-open",
        "Request for laying-open of a design application, for each case",
        "other",
        a,
      ),
  },
  {
    section: "Others",
    match: /^Filling an opposition to a registration, for each design :$/,
    channels: ".",
    build: ([a]) => [
      fee(
        "kr-des-opposition",
        "Filing an opposition to a registration, for each design",
        "opposition",
        a as string,
      ),
    ],
  },
  {
    section: "Others",
    match:
      /^Divisional application fee: When dividing a multiple-design application, for each divided application, a\. In case of division into same application b\. In case of division partial substantive examination application into substantive examination application c\. others$/,
    channels: "epep",
    rest: "Application fee",
    build: ([se, sp, ce, cp]) => [
      ...electronicPaper(
        "kr-des-division",
        "Divisional application fee, division into the same type of application, for each divided application",
        "other",
        [se, sp] as string[],
      ),
      ...electronicPaper(
        "kr-des-division-to-substantive",
        "Divisional application fee, division of a partial-substantive examination application into a substantive examination application, for each divided application",
        "other",
        [ce, cp] as string[],
        { notes: "Other divisions are charged the application fee." },
      ),
    ],
  },
];

const slug = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 50)
    .replace(/-$/, "");

/** Apply the rules to a table's entries. Unknown rows still appear, as `other`, and are listed as unmapped. */
function build(
  rows: KipoEntry[],
  rules: Rule[],
  prefix: string,
): { drafts: Draft[]; unmapped: string[] } {
  const drafts: Draft[] = [];
  const unmapped: string[] = [];
  const used = new Set<Rule>();
  for (const entry of rows) {
    const { amounts: found, rest } = amounts(entry.fee);
    const rule = rules.find(
      (candidate) =>
        candidate.section === entry.section &&
        candidate.match.test(entry.description),
    );
    if (!rule) {
      const code = `${prefix}-${slug(entry.description)}`;
      unmapped.push(code);
      found.forEach((amount, index) => {
        drafts.push(
          fee(
            index ? `${code}-${index + 1}` : code,
            entry.description,
            "other",
            amount.value,
            {
              notes: `Unrecognized KIPO row in section ${entry.section}.${amount.channel === "p" ? " Paper filing." : ""}`,
            },
          ),
        );
      });
      continue;
    }
    if (used.has(rule))
      throw invalid(`"${entry.description.slice(0, 50)}" appears twice.`);
    used.add(rule);
    const channels = found.map((amount) => amount.channel).join("");
    if (channels !== rule.channels || rest !== (rule.rest ?? ""))
      throw invalid(`"${entry.description.slice(0, 50)}" changed shape.`);
    drafts.push(
      ...rule.build(
        found.map((amount) => amount.value),
        entry,
      ),
    );
  }
  const missing = rules.filter((rule) => !used.has(rule));
  if (missing.length)
    throw invalid(
      `rows not found: ${missing.map((rule) => rule.match.source.slice(1, 40)).join("; ")}.`,
    );
  const codes = new Set<string>();
  for (const draft of drafts) {
    if (codes.has(draft.code)) throw invalid(`duplicate code ${draft.code}.`);
    codes.add(draft.code);
  }
  return { drafts, unmapped };
}

interface Page {
  tables: Map<string, KipoEntry[]>;
  effectiveDate: string;
  updated: string | null;
  provenance: FeeSchedule["provenance"];
}

function parsePage(html: string, captions: string[]) {
  const document = parseHTML(html).document as unknown as Document;
  const text = squash(document.body?.textContent ?? "");
  const effective = /in effect since ([A-Z][a-z]+ \d{1,2}, \d{4})/.exec(text);
  if (!effective) throw invalid("the effective-date sentence was not found.");
  const updated = /Last updated (\d{1,2} [A-Z][a-z]+ \d{4})/.exec(text);
  const tables = new Map<string, KipoEntry[]>();
  for (const table of Array.from(document.querySelectorAll("table"))) {
    const caption = squash(table.querySelector("caption")?.textContent ?? "");
    if (captions.includes(caption)) tables.set(caption, entries(table));
  }
  const missing = captions.filter((caption) => !tables.has(caption));
  if (missing.length) throw invalid(`missing tables: ${missing.join(", ")}.`);
  return {
    tables,
    effectiveDate: isoDate(effective[1] as string),
    updated: updated ? isoDate(updated[1] as string) : null,
  };
}

function coverage(
  drafts: Draft[],
  years: number[],
  notes: string,
): RecurringFeeCoverage {
  const present = new Set(
    drafts.filter((draft) => draft.category === "renewal").map((d) => d.year),
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

const DISCOUNTS =
  "KIPO grants fee reductions (individuals, SMEs, universities and others) under a separate rule on fee reduction and refund; they are not on this schedule, so every fee has tier none.";

/** Fetches KIPO's two English fee pages and projects the patent, trademark and design schedules. */
export class KipoFeesClient {
  private readonly http: GenericHttpTransport;
  private readonly pending = new Map<string, Promise<Page>>();
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.kipo.go.kr",
      sourceName: KIPO_FEES_SOURCE,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  /** One fetch per page serves concurrent schedule requests. */
  private page(
    url: string,
    captions: string[],
    options: TransportRequestOptions,
  ): Promise<Page> {
    let pending = this.pending.get(url);
    if (!pending) {
      pending = (async () => {
        const { search } = new URL(url);
        const result = await this.http.text(
          "GET",
          `/en/HtmlApp${search}`,
          options,
        );
        const page = parsePage(result.data, captions);
        return {
          ...page,
          provenance: {
            ...result.provenance,
            as_of_status: [
              `in effect since ${page.effectiveDate}`,
              page.updated ? `page last updated ${page.updated}` : null,
            ]
              .filter(Boolean)
              .join("; "),
            effective_date: page.effectiveDate,
          },
        };
      })().finally(() => this.pending.delete(url));
      this.pending.set(url, pending);
    }
    return pending;
  }
  private schedule(
    right: "patent" | "trademark" | "design",
    page: Page,
    built: { drafts: Draft[]; unmapped: string[] },
    sourceUrl: string,
    extra: {
      statutory_basis: string;
      coverage: RecurringFeeCoverage;
      notes: string;
    },
  ): FeeSchedule {
    return FeeScheduleSchema.parse({
      key: `KR/KIPO/${right}`,
      jurisdiction: "KR",
      issuing_body: "Korean Intellectual Property Office",
      office_code: "KIPO",
      right,
      currency: "KRW",
      effective_date: page.effectiveDate,
      source_url: sourceUrl,
      statutory_basis: extra.statutory_basis,
      fees: built.drafts.map((draft) => ({
        code: draft.code,
        label: draft.label,
        category: draft.category,
        rights: [right],
        amount: draft.amount,
        currency: "KRW",
        tier: "none",
        year: draft.year ?? null,
        condition: draft.condition ?? null,
        source_url: sourceUrl,
        notes: draft.notes || null,
      })),
      recurring_fee_coverage: extra.coverage,
      unmapped_codes: built.unmapped,
      notes: `${extra.notes} ${DISCOUNTS}`,
      provenance: page.provenance,
    });
  }
  /** Patent fees: application, examination, annual fees (years 1-25, basic and per claim) and conversions. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page(
      KIPO_PATENT_FEES_URL,
      ["Patent fees", "Utility model fees", "PCT fees"],
      options,
    );
    const built = build(
      page.tables.get("Patent fees") ?? [],
      PATENT_RULES,
      "kr",
    );
    return this.schedule("patent", page, built, KIPO_PATENT_FEES_URL, {
      statutory_basis:
        "Rule on the Collection of Patent Fees, etc. (Korean Ministry of Trade, Industry and Energy Ordinance), under the Patent Act.",
      coverage: coverage(
        built.drafts,
        range(1, 25),
        "Annual fees for years 1-25 present (band 16-25 covers term extensions).",
      ),
      notes:
        "Electronic and paper rates are separate fees; paper rows carry a paper_filing condition. Annual fees are a basic fee plus a fee for each claim, both per year; the 1-3 year band includes the grant fee and is paid at registration. Utility model and PCT fees on the same page are not part of this schedule.",
    });
  }
  /** Trademark fees: per-class application, registration and renewal (lump sum or two installments), and others. */
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page(
      KIPO_TRADEMARK_DESIGN_FEES_URL,
      ["Trademark fees", "Design fees"],
      options,
    );
    const built = build(
      page.tables.get("Trademark fees") ?? [],
      TRADEMARK_RULES,
      "kr-tm",
    );
    return this.schedule(
      "trademark",
      page,
      built,
      KIPO_TRADEMARK_DESIGN_FEES_URL,
      {
        statutory_basis:
          "Rule on the Collection of Trademark Fees, etc., under the Trademark Act.",
        coverage: coverage(
          built.drafts,
          [10],
          "Registrations renew every 10 years; year 10 stands for each renewal.",
        ),
        notes:
          "Most fees are per class (classes_over threshold 0). Charges for designated goods beyond 10 in a class are excess_classes rows without a condition, because the closed trigger vocabulary has no goods count. Registration and renewal can be paid as a single lump sum or in two installments; both are listed.",
      },
    );
  }
  /** Design fees: application by examination track, examination, annual fees (years 1-20 for each track) and others. */
  async getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page(
      KIPO_TRADEMARK_DESIGN_FEES_URL,
      ["Trademark fees", "Design fees"],
      options,
    );
    const built = build(
      page.tables.get("Design fees") ?? [],
      DESIGN_RULES,
      "kr-des",
    );
    return this.schedule(
      "design",
      page,
      built,
      KIPO_TRADEMARK_DESIGN_FEES_URL,
      {
        statutory_basis:
          "Rule on the Collection of Design Fees, etc., under the Design Protection Act.",
        coverage: coverage(
          built.drafts,
          range(1, 20),
          "Annual fees for years 1-20 present for both examination tracks.",
        ),
        notes:
          "Two annual-fee tracks, one for designs registered after substantive examination and one after partial-substantive examination; a renewal lookup by year returns one row per track. The 1-3 year band includes the grant fee. Electronic and paper rates are separate fees.",
      },
    );
  }
}

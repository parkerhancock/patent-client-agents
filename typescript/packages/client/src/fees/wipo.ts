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
 * The WIPO International Bureau publishes each system's Schedule of Fees as
 * an HTML page on wipo.int: PCT (patents), Madrid (trademarks) and Hague
 * (designs). Amounts are whole Swiss francs. Fees fixed by each designated
 * Contracting Party (Madrid and Hague individual fees) are not on these pages.
 */
export const WIPO_FEES_SOURCE = "WIPO Schedules of Fees";
export const WIPO_PCT_FEES_URL =
  "https://www.wipo.int/en/web/pct-system/texts/rules/rtax";
export const WIPO_MADRID_FEES_URL =
  "https://www.wipo.int/en/web/madrid-system/fees/sched";
export const WIPO_HAGUE_FEES_URL =
  "https://www.wipo.int/en/web/hague-system/fees/sched";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";
const ISSUING_BODY =
  "World Intellectual Property Organization (WIPO) - International Bureau";

const invalid = (message: string) =>
  new ApiError(`WIPO fee schedule: ${message}`, 200, "INVALID_RESPONSE");
const squash = (value: string | null | undefined) =>
  (value ?? "").replace(/\s+/g, " ").trim();
/** "1,330" -> "1330.00". WIPO amounts are whole Swiss francs. */
function chf(raw: string): string {
  if (!/^\d{1,3}(?:,\d{3})*$|^\d+$/.test(raw))
    throw invalid(`unrecognized amount ${raw.slice(0, 30)}`);
  return `${raw.replaceAll(",", "")}.00`;
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
/** "as in force on July 1, 2026" in the page text -> "2026-07-01", else null. */
function inForce(text: string): string | null {
  const match = /as in force (?:on|from) ([A-Z][a-z]+) (\d{1,2}), (\d{4})/.exec(
    text,
  );
  if (!match) return null;
  const month = MONTHS.indexOf(match[1] as string) + 1;
  if (!month) throw invalid(`unrecognized date ${match[0]}`);
  return `${match[3]}-${String(month).padStart(2, "0")}-${(match[2] as string).padStart(2, "0")}`;
}
function documentOf(html: string): Document {
  const document = parseHTML(html).document as unknown as Document;
  // Footnote markers are <sup> (Madrid) or bare anchors to #note (Hague).
  for (const node of Array.from(
    document.querySelectorAll('sup, a[href^="#note"]'),
  ))
    node.remove();
  return document;
}
const cellTexts = (row: Element) =>
  Array.from(row.querySelectorAll("td, th")).map((cell) =>
    squash(cell.textContent),
  );
const code = (system: string, item: string) =>
  `wo-${system}-${item.replace(/\.$/, "").replaceAll(".", "-")}`;

interface Draft {
  code: string;
  label: string;
  category: FeeCategory;
  amount: string;
  year?: number;
  condition?: FeeCondition;
  notes?: string;
}
const perDesign: FeeCondition = {
  trigger: "multi_design",
  threshold: 1,
  per_unit: true,
  description: "Per design beyond the first.",
};

// PCT ----------------------------------------------------------------------

function pctFees(document: Document): {
  drafts: Draft[];
  unmapped: string[];
} {
  const table = document.querySelector("table");
  if (!table) throw invalid("the PCT schedule table is missing.");
  const drafts: Draft[] = [];
  const reductions = new Map<string, string>();
  for (const row of Array.from(table.querySelectorAll("tr"))) {
    // Direct cells only: item 4 nests its reductions in inner tables.
    const cells = Array.from(row.children).filter(
      (cell) => cell.tagName === "TD",
    );
    const first = squash(cells[0]?.textContent);
    const item = /^(\d+)\.$/.exec(first)?.[1];
    if (item && /^\d/.test(squash(cells[3]?.textContent))) {
      const label = squash(cells[1]?.textContent)
        .replace(/\s*\(Rule [^)]*\)\s*$/, "")
        .replace(/:$/, "");
      const amounts = squash(cells[3]?.textContent).split(" ").filter(Boolean);
      const unit = squash(cells[5]?.textContent);
      const [base, perSheet] = amounts;
      if (!base) throw invalid(`PCT item ${item} has no amount.`);
      drafts.push({
        code: code("pct", item),
        label,
        category: PCT_CATEGORIES[item] ?? "other",
        amount: chf(base),
        notes: `PCT Schedule of Fees, item ${item}.`,
      });
      if (perSheet) {
        const threshold = /in excess of (\d+)\s*sheets/.exec(unit)?.[1];
        if (!threshold)
          throw invalid(`PCT item ${item} per-sheet threshold changed.`);
        drafts.push({
          code: `${code("pct", item)}-sheet`,
          label: `${label} - each sheet over ${threshold}`,
          category: "excess_pages",
          amount: chf(perSheet),
          condition: {
            trigger: "sheets_over",
            threshold: Number(threshold),
            per_unit: true,
            description: `Per sheet of the international application over ${threshold}.`,
          },
          notes: `PCT Schedule of Fees, item ${item}.`,
        });
      }
      continue;
    }
    // Item 4: reductions of the international filing fee, one per letter.
    const letter = /^\(([a-z])\)$/.exec(first)?.[1];
    if (letter && cells.length === 2) {
      const text = squash(cells[1]?.textContent);
      const amount = /:\s*([\d,]+) Swiss francs$/.exec(text)?.[1];
      if (!amount) throw invalid(`PCT reduction (${letter}) changed shape.`);
      reductions.set(letter, text);
    }
  }
  for (const [letter, text] of reductions) {
    const amount = /:\s*([\d,]+) Swiss francs$/.exec(text)?.[1] as string;
    drafts.push({
      code: code("pct", `4.${letter}`),
      label: `Reduction of the international filing fee, ${text.replace(/:\s*[\d,]+ Swiss francs$/, "")}`,
      category: "other",
      amount: chf(amount),
      notes:
        "PCT Schedule of Fees, item 4. A reduction of the international filing fee, not a charge.",
    });
  }
  if (!drafts.some((draft) => draft.code === "wo-pct-1"))
    throw invalid("the international filing fee (item 1) is missing.");
  return { drafts, unmapped: [] };
}
const PCT_CATEGORIES: Record<string, FeeCategory> = {
  "1": "filing",
  "2": "search",
  "3": "examination",
};

// Madrid -------------------------------------------------------------------

/** Madrid categories by item number; longest prefix wins. */
const MADRID_RULES: [string, FeeCategory, number?][] = [
  ["2.1", "filing"],
  ["2.2", "excess_classes"],
  ["2.3", "designation"],
  ["4.", "other"],
  ["5.", "designation"],
  ["6.5", "late_fee", 10],
  ["6.", "renewal", 10],
  ["7.1", "transfer"],
  ["7.2", "transfer"],
  ["7.3", "other"],
  ["7.4", "transfer"],
  ["7.5", "transfer"],
  ["7.6", "petition"],
  ["7.7", "other"],
  ["8.", "other"],
  ["10.", "other"],
];
function madridRule(item: string) {
  const dotted = `${item}.`;
  return MADRID_RULES.filter(([prefix]) => dotted.startsWith(prefix)).sort(
    (a, b) => b[0].length - a[0].length,
  )[0];
}
const CONTRACTING_PARTY =
  /^the amount of the individual fee is fixed by each Contracting Party concerned$/;

function madridFees(document: Document): {
  drafts: Draft[];
  unmapped: string[];
} {
  const table = document.querySelector("table");
  if (!table) throw invalid("the Madrid schedule table is missing.");
  const drafts: Draft[] = [];
  const unmapped: string[] = [];
  const amounts = new Map<string, string>();
  const labels = new Map<string, string>();
  let section = "";
  let parent: { item: string; label: string; sub: number } | null = null;
  for (const row of Array.from(table.querySelectorAll("tbody tr"))) {
    const [label = "", value = ""] = cellTexts(row);
    const head = /^(\d+(?:\.\d+)*)\.? (.+)$/.exec(label);
    if (head && /^\d+$/.test(head[1] as string)) {
      section = (head[2] as string)
        .replace(/ The following fees.*$/, "")
        .replace(/ \(Article.*$/, "");
      labels.set(head[1] as string, section);
      parent = null;
      if (!value) continue;
    }
    let item: string;
    let text: string;
    if (head) {
      item = head[1] as string;
      text = head[2] as string;
      if (!labels.has(item))
        labels.set(item, text.replace(/ ?\(Articles? [^)]*\)$/, ""));
      parent = value ? null : { item, label: text, sub: 0 };
      if (!value) continue;
    } else if (parent && value) {
      // Unnumbered sub-rows (8.1-8.3: "up to three pages", ...).
      parent.sub += 1;
      item = `${parent.item}.${parent.sub}`;
      text = label;
    } else continue;
    const parts = item.split(".");
    text = [
      ...parts
        .slice(1)
        .map((_, i) => labels.get(parts.slice(0, i + 1).join("."))),
      text,
    ]
      .filter(Boolean)
      .join(" - ");
    if (CONTRACTING_PARTY.test(value)) continue;
    const rule = madridRule(item);
    if (!rule) unmapped.push(code("madrid", item));
    const base: Omit<Draft, "amount"> = {
      code: code("madrid", item),
      label: text,
      category: rule?.[1] ?? "other",
      ...(rule?.[2] ? { year: rule[2] } : {}),
      notes: `Madrid Schedule of Fees, item ${item}${section ? ` (${section})` : ""}.`,
    };
    if (/^\d[\d,]*$/.test(value)) {
      const amount = chf(value);
      amounts.set(item, amount);
      const condition: FeeCondition | undefined =
        /for each class of goods and services beyond three classes/.test(text)
          ? {
              trigger: "classes_over",
              threshold: 3,
              per_unit: true,
              description: "Per class beyond the first three.",
            }
          : undefined;
      drafts.push({ ...base, amount, ...(condition ? { condition } : {}) });
      continue;
    }
    // "77 plus 4 per term in excess of 20", "20 plus 4 per incorrectly classified term"
    const plus = /^(\d+) plus (\d+) per (.+)$/.exec(value);
    if (plus) {
      drafts.push({ ...base, amount: chf(plus[1] as string) });
      drafts.push({
        ...base,
        code: `${base.code}-term`,
        label: `${text} - per ${plus[3]}`,
        amount: chf(plus[2] as string),
      });
      continue;
    }
    // "50% of the amount of the fee payable under item 6.1"
    const share =
      /^(\d+)% of the amount of the fee payable under item ([\d.]+)$/.exec(
        value,
      );
    if (share) {
      const of = amounts.get(share[2] as string);
      if (!of)
        throw invalid(`item ${item} refers to missing item ${share[2]}.`);
      const cents = (Number(of) * 100 * Number(share[1])) / 100;
      drafts.push({
        ...base,
        amount: (cents / 100).toFixed(2),
        notes: `${base.notes} Computed as ${share[1]}% of item ${share[2]} (CHF ${of}).`,
      });
      continue;
    }
    throw invalid(
      `unrecognized amount for item ${item}: ${value.slice(0, 40)}`,
    );
  }
  if (!amounts.has("2.1.1") || !amounts.has("6.1"))
    throw invalid("the basic or renewal fee is missing.");
  return { drafts, unmapped };
}

// Hague --------------------------------------------------------------------

/** Hague categories by top-level item ("14bis" -> "14bis"). */
const HAGUE_RULES: Record<string, { category: FeeCategory; year?: number }> = {
  "1": { category: "filing" },
  "2": { category: "publication" },
  "3": { category: "other" },
  "4": { category: "designation" },
  "7": { category: "renewal", year: 5 },
  "8": { category: "renewal", year: 5 },
  "13": { category: "transfer" },
  "14": { category: "transfer" },
  "14bis": { category: "other" },
  "15": { category: "other" },
  "16": { category: "other" },
  "17": { category: "other" },
  "18": { category: "other" },
  "19": { category: "other" },
  "20": { category: "other" },
  "21": { category: "other" },
  "22": { category: "other" },
};

function hagueFees(document: Document): {
  drafts: Draft[];
  unmapped: string[];
} {
  const table = document.querySelector("table");
  if (!table) throw invalid("the Hague schedule table is missing.");
  const drafts: Draft[] = [];
  const unmapped: string[] = [];
  const labels = new Map<string, string>();
  let section = "";
  for (const row of Array.from(table.querySelectorAll("tr"))) {
    const [first = "", label = "", value = ""] = cellTexts(row);
    if (/^[IVX]+\.$/.test(first)) {
      section = label;
      continue;
    }
    const item = /^(\d+(?:bis)?(?:\.\d+)*)\.?$/.exec(first)?.[1];
    if (!item || /^\[Deleted\]$/.test(label)) continue;
    labels.set(item, label);
    if (!value) continue;
    if (!/^\d[\d,]*$/.test(value))
      throw invalid(
        `unrecognized amount for item ${item}: ${value.slice(0, 40)}`,
      );
    const top = item.split(".")[0] as string;
    const rule = HAGUE_RULES[top];
    if (!rule) unmapped.push(code("hague", item));
    // Label sub-items with their ancestors: "Standard designation fee - Where level one applies - For one design".
    const parts = item.split(".");
    const ancestors = parts
      .slice(1)
      .map((_, i) => labels.get(parts.slice(0, i + 1).join(".")))
      .filter((text): text is string => Boolean(text));
    const condition = /^For each additional design/.test(label)
      ? perDesign
      : undefined;
    drafts.push({
      code: code("hague", item),
      label: [...ancestors, label].join(" - "),
      category: rule?.category ?? "other",
      amount: chf(value),
      ...(rule?.year ? { year: rule.year } : {}),
      ...(condition ? { condition } : {}),
      notes: `Hague Schedule of Fees, item ${item}${section ? ` (${section})` : ""}.${rule?.year ? " Renewal is due every five years; stored as year 5 for each renewal." : ""}`,
    });
  }
  if (!drafts.some((draft) => draft.code === "wo-hague-1-1"))
    throw invalid("the basic fee (item 1.1) is missing.");
  return { drafts, unmapped };
}

// Client -------------------------------------------------------------------

const item = (
  draft: Draft,
  right: "patent" | "trademark" | "design",
  sourceUrl: string,
): FeeItem => ({
  code: draft.code,
  label: draft.label,
  category: draft.category,
  rights: [right],
  amount: draft.amount,
  currency: "CHF",
  tier: "none",
  year: draft.year ?? null,
  condition: draft.condition ?? null,
  source_url: sourceUrl,
  notes: draft.notes ?? null,
});
function renewalCoverage(
  fees: FeeItem[],
  year: number,
  notes: string,
): RecurringFeeCoverage {
  return fees.some((fee) => fee.category === "renewal" && fee.year === year)
    ? { status: "complete", missing_categories: [], missing_years: [], notes }
    : {
        status: "partial",
        missing_categories: [],
        missing_years: [year],
        notes: null,
      };
}

/** Fetches the three WIPO Schedules of Fees (PCT, Madrid, Hague). */
export class WipoFeesClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.wipo.int",
      sourceName: WIPO_FEES_SOURCE,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  private async schedule(
    url: string,
    options: TransportRequestOptions,
    parse: (document: Document) => { drafts: Draft[]; unmapped: string[] },
    meta: {
      office_code: string;
      right: "patent" | "trademark" | "design";
      statutory_basis: string;
      notes: string;
      coverage: (fees: FeeItem[]) => RecurringFeeCoverage;
    },
  ): Promise<FeeSchedule> {
    const result = await this.http.text("GET", new URL(url).pathname, options);
    const document = documentOf(result.data);
    const effective = inForce(squash(document.body?.textContent));
    const { drafts, unmapped } = parse(document);
    const fees = drafts.map((draft) => item(draft, meta.right, url));
    return FeeScheduleSchema.parse({
      key: `WO/${meta.office_code}/${meta.right}`,
      jurisdiction: "WO",
      issuing_body: ISSUING_BODY,
      office_code: meta.office_code,
      right: meta.right,
      currency: "CHF",
      effective_date: effective,
      source_url: url,
      statutory_basis: meta.statutory_basis,
      fees,
      recurring_fee_coverage: meta.coverage(fees),
      unmapped_codes: unmapped,
      notes: meta.notes,
      provenance: {
        ...result.provenance,
        as_of_status: effective
          ? `as in force on ${effective}, as the page states`
          : "effective date not published on the page",
        effective_date: effective,
      },
    });
  }
  /** PCT international fees paid to the International Bureau. */
  getPctSchedule(options: TransportRequestOptions = {}): Promise<FeeSchedule> {
    return this.schedule(WIPO_PCT_FEES_URL, options, pctFees, {
      office_code: "WIPO-PCT",
      right: "patent",
      statutory_basis:
        "Schedule of Fees annexed to the Regulations under the Patent Cooperation Treaty.",
      coverage: () => ({
        status: "not_applicable",
        missing_categories: [],
        missing_years: [],
        notes:
          "International applications carry no renewal fees; renewals are paid to national and regional offices.",
      }),
      notes:
        "International Bureau fees under the PCT Schedule of Fees: international filing fee (with the per-sheet fee over 30 sheets), supplementary search handling fee and handling fee, plus the item 4 electronic-filing reductions, which are reductions rather than charges. The item 5 reduction (90% for qualifying applicants) is a percentage and is not listed. Transmittal, search and preliminary examination fees set by receiving offices and international authorities are not on this page. The page states no effective date; the PCT Regulations containing the schedule are in force from January 1, 2026.",
    });
  }
  /** Madrid international trademark fees, excluding individual fees fixed by Contracting Parties. */
  getMadridSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule(WIPO_MADRID_FEES_URL, options, madridFees, {
      office_code: "WIPO-MADRID",
      right: "trademark",
      statutory_basis:
        "Schedule of Fees under the Common Regulations under the Madrid Agreement and Protocol.",
      coverage: (fees) =>
        renewalCoverage(
          fees,
          10,
          "International registrations renew every 10 years; year 10 stands for each renewal (items 6.1-6.3, grace surcharge 6.5).",
        ),
      notes:
        "International Bureau fees under the Madrid Schedule of Fees. Individual fees fixed by each designated Contracting Party (items 2.4, 5.3, 6.4) are not on this page and are omitted. Items 4.1 and 4.2 are split into a base fee and a per-term fee. The renewal grace-period surcharge (6.5) is stated as 50% of item 6.1 and is computed from it. Unnumbered sub-rows of items 8.1-8.3 are numbered in page order (8.1.1, 8.1.2).",
    });
  }
  /** Hague international design fees, excluding individual designation fees. */
  getHagueSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule(WIPO_HAGUE_FEES_URL, options, hagueFees, {
      office_code: "WIPO-HAGUE",
      right: "design",
      statutory_basis:
        "Schedule of Fees annexed to the Common Regulations under the 1999 Act and the 1960 Act of the Hague Agreement.",
      coverage: (fees) =>
        renewalCoverage(
          fees,
          5,
          "International registrations renew every five years; year 5 stands for each renewal (items 7 and 8).",
        ),
      notes:
        "International Bureau fees under the Hague Schedule of Fees, with standard designation fees at all three levels. Individual designation fees (items 5 and 9) are fixed by each Contracting Party and the grace-period surcharge (item 10) is stated only in a footnote; both are omitted. Renewal fees (items 7 and 8) are due every five years and are stored as year 5.",
    });
  }
}

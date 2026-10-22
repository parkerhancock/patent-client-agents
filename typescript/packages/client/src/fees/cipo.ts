import { parseHTML } from "linkedom";
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
} from "./models.js";

/**
 * CIPO's patent fee page lists one year's fees per panel ("2026 list of
 * fees for patents", and from autumn the next year's list), each as four
 * tables: extension of time, applications, international applications, and
 * patents. Columns are fee type, description, small entity fee and standard
 * fee; a fee type cell spans its sub-rows. CIPO publishes no fee codes.
 */
export const CIPO_FEES_SOURCE = "CIPO patent fees";
export const CIPO_FEES_URL =
  "https://ised-isde.canada.ca/site/canadian-intellectual-property-office/en/patents/patent-fees";
const PAGE_PATH =
  "/site/canadian-intellectual-property-office/en/patents/patent-fees";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`CIPO fee schedule: ${message}`, 200, "INVALID_RESPONSE");

const squash = (text: string | null | undefined) =>
  (text ?? "").replace(/[\s ]+/g, " ").trim();

/** "1,027.00" -> "1027.00"; "See description" -> null. Anything else fails. */
export function parseCadAmount(raw: string): string | null {
  const value = raw.trim();
  if (/^see description$/i.test(value)) return null;
  if (!/^\d{1,3}(?:,\d{3})*\.\d{2}$/.test(value))
    throw invalid(`unrecognized amount ${value.slice(0, 20)}`);
  return value.replaceAll(",", "");
}

export interface CipoRow {
  caption: string;
  feeType: string;
  description: string;
  small: string | null;
  standard: string | null;
}
export interface CipoList {
  year: number;
  rows: CipoRow[];
}

const CAPTIONS = [
  "Fee for applying for an extension of time",
  "Fees respecting applications",
  "Fees in respect of international applications",
  "Fees in respect of patents",
];

/** Each yearly list on the page, with its rows. A spanning fee type is copied to its sub-rows. */
export function cipoLists(html: string): CipoList[] {
  const document = parseHTML(html).document as unknown as Document;
  const lists: CipoList[] = [];
  let current: CipoList | null = null;
  for (const element of Array.from(document.querySelectorAll("h2, table"))) {
    if (element.tagName.toLowerCase() === "h2") {
      const year = /^(\d{4}) list of fees for patents$/.exec(
        squash(element.textContent),
      )?.[1];
      current = year ? { year: Number(year), rows: [] } : null;
      if (current) lists.push(current);
      continue;
    }
    if (!current) continue;
    const caption = squash(element.querySelector("caption")?.textContent);
    if (!CAPTIONS.includes(caption))
      throw invalid(`unrecognized table "${caption.slice(0, 60)}".`);
    const heads = Array.from(element.querySelectorAll("thead th")).map((th) =>
      squash(th.textContent),
    );
    const expected = [
      "Fee type",
      "Additional description",
      `Small entity fee – ${current.year} ($)`,
      `Standard fee – ${current.year} ($)`,
    ];
    if (heads.join("|") !== expected.join("|"))
      throw invalid(`${caption} columns changed: ${heads.join(" | ")}.`);
    let span = { text: "", remaining: 0 };
    for (const tr of Array.from(element.querySelectorAll("tbody tr"))) {
      const cells = Array.from(tr.querySelectorAll("td"));
      let texts = cells.map((td) => squash(td.textContent));
      if (cells.length === 4) {
        const rows = Number(cells[0]?.getAttribute("rowspan") ?? "1");
        span = { text: texts[0] ?? "", remaining: rows - 1 };
      } else if (cells.length === 3 && span.remaining > 0) {
        texts = [span.text, ...texts];
        span.remaining--;
      } else throw invalid(`a ${caption} row has ${cells.length} cells.`);
      const [feeType = "", description = "", small = "", standard = ""] = texts;
      current.rows.push({
        caption,
        feeType: feeType.replace(/Footnote \d+$/, "").trim(),
        description,
        small: parseCadAmount(small),
        standard: parseCadAmount(standard),
      });
    }
  }
  return lists;
}

const WORDS: Record<string, number> = {
  second: 2,
  third: 3,
  fourth: 4,
  fifth: 5,
  sixth: 6,
  seventh: 7,
  eighth: 8,
  ninth: 9,
};
/** "second, third and fourth" -> [2, 3, 4]; "20th and each subsequent" -> [20]. */
export function cipoYears(description: string): number[] {
  const years = new Set<number>();
  for (const match of description.matchAll(/\b(\d+)(?:st|nd|rd|th)\b/g))
    years.add(Number(match[1]));
  for (const [word, year] of Object.entries(WORDS))
    if (new RegExp(`\\b${word}\\b`, "i").test(description)) years.add(year);
  return [...years].sort((a, b) => a - b);
}

interface Rule {
  category: FeeCategory;
  condition?: FeeCondition;
  notes?: string;
}
const claimsOver20: FeeCondition = {
  trigger: "claims_over",
  threshold: 20,
  per_unit: true,
  description: "Per claim over 20.",
};

/** Category by table, fee type and description. */
function rule(row: CipoRow): Rule | null {
  const type = row.feeType.toLowerCase();
  const text = row.description.toLowerCase();
  switch (row.caption) {
    case CAPTIONS[0]:
      return { category: "extension" };
    case CAPTIONS[1]:
      if (type.startsWith("application fee")) return { category: "filing" };
      if (type.startsWith("late fee")) return { category: "late_fee" };
      if (type.startsWith("maintenance fees"))
        return {
          category: "renewal",
          notes: "Maintenance of a pending application.",
        };
      if (type.startsWith("request for examination"))
        return /in excess of 20/.test(text)
          ? { category: "excess_claims", condition: claimsOver20 }
          : { category: "examination" };
      if (type.startsWith("advanced examination"))
        return { category: "examination" };
      if (type.startsWith("fee for continued examination"))
        return { category: "rce" };
      if (type.startsWith("final fee")) {
        if (/in excess of 100 pages/.test(text))
          return {
            category: "excess_pages",
            condition: {
              trigger: "pages_over",
              threshold: 100,
              per_unit: true,
              description:
                "Per page of specification and drawings over 100, excluding electronic sequence listings.",
            },
          };
        if (/in excess of 20/.test(text))
          return {
            category: "excess_claims",
            condition: claimsOver20,
            notes:
              "Payable with the final fee for claims over 20 not paid for at examination.",
          };
        return { category: "grant" };
      }
      if (type.startsWith("reinstatement")) return { category: "petition" };
      return null;
    case CAPTIONS[2]:
      if (type.startsWith("transmittal fee")) return { category: "other" };
      if (/^(additional fee for )?search/.test(type))
        return { category: "search" };
      if (/^preliminary examination|^additional fee for examination/.test(type))
        return { category: "examination" };
      if (type.startsWith("basic national fee"))
        return { category: "filing", notes: "PCT national phase entry." };
      if (type.startsWith("fee for reinstatement of rights"))
        return { category: "petition" };
      if (type.startsWith("late fee")) return { category: "late_fee" };
      return null;
    case CAPTIONS[3]:
      if (type.startsWith("maintenance fees") && /category 1/.test(type))
        return {
          category: "other",
          notes:
            "Maintenance of a patent granted on a category 1 application (filed before October 1, 1989); years count from the issue date, so these rows are not renewals by application year.",
        };
      if (type.startsWith("maintenance fees"))
        return {
          category: "renewal",
          notes: /additional term/.test(type)
            ? "During an additional term granted under section 46.1 of the Patent Act."
            : "Maintenance of a granted patent.",
        };
      if (type.startsWith("late fee")) return { category: "late_fee" };
      if (type.startsWith("fee for requesting reversal"))
        return { category: "petition" };
      if (type.startsWith("reissue")) return { category: "reissue" };
      if (/^registration of a document|^recording of a/.test(type))
        return { category: "transfer" };
      if (
        /^fee for requesting correction|^disclaimer|^re-examination|^fees in respect of an additional term|^fee for presenting an application|^fee to advertise|^fees in respect of information/.test(
          type,
        )
      )
        return { category: "other" };
      return null;
    default:
      return null;
  }
}

/** Python's code: fee-type slug (30 characters), year, tier initial; repeats are numbered. */
const slug = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 30);

/** Fees of one yearly list. */
export function cipoFees(list: CipoList): {
  fees: FeeItem[];
  unmapped: string[];
  omitted: string[];
} {
  const fees: FeeItem[] = [];
  const unmapped: string[] = [];
  const omitted: string[] = [];
  const used = new Map<string, number>();
  const unique = (code: string) => {
    const n = (used.get(code) ?? 0) + 1;
    used.set(code, n);
    return n === 1 ? code : `${code}-${n}`;
  };
  for (const row of list.rows) {
    if (row.small === null || row.standard === null) {
      omitted.push(row.feeType);
      continue;
    }
    const found = rule(row);
    if (!found) unmapped.push(row.feeType);
    const category = found?.category ?? "other";
    const banded = row.feeType.toLowerCase().startsWith("maintenance fees");
    const years = banded ? cipoYears(row.description) : [null];
    if (banded && !years.length)
      throw invalid(`maintenance row without years: ${row.description}`);
    const tiers: [EntityTier, string][] =
      row.small === row.standard
        ? [["none", row.standard]]
        : [
            ["small", row.small],
            ["large", row.standard],
          ];
    for (const year of years)
      for (const [tier, amount] of tiers)
        fees.push({
          code: unique(
            `${slug(row.feeType)}${year === null ? "" : `-y${year}`}-${tier === "none" ? "n" : tier[0]}`,
          ),
          label: `${row.feeType} - ${row.description}`,
          category,
          rights: ["patent"],
          amount,
          currency: "CAD",
          tier,
          year,
          condition: found?.condition ?? null,
          source_url: CIPO_FEES_URL,
          notes:
            [
              `Table: ${row.caption}.`,
              found?.notes,
              year === 20 && /each subsequent/.test(row.description)
                ? "Also due on each later anniversary."
                : null,
            ]
              .filter(Boolean)
              .join(" ") || null,
        });
  }
  return { fees, unmapped, omitted };
}

/** Fetches CIPO's patent fee page and projects the current year's list. */
export class CipoFeesClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://ised-isde.canada.ca",
      sourceName: CIPO_FEES_SOURCE,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  /** Patent fees in force this year, with small entity and standard tiers. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const result = await this.http.text("GET", PAGE_PATH, options);
    const lists = cipoLists(result.data);
    // The server's Date header dates the page, so a replayed page keeps its year.
    const served = new Date(
      result.headers.get("date") ?? result.provenance.retrieved_at,
    );
    const now = Number.isNaN(served.getTime())
      ? Number(result.provenance.retrieved_at.slice(0, 4))
      : served.getUTCFullYear();
    const list = lists
      .filter((candidate) => candidate.year <= now)
      .sort((a, b) => b.year - a.year)[0];
    if (!list) throw invalid(`no fee list for ${now} or earlier.`);
    const { fees, unmapped, omitted } = cipoFees(list);
    if (fees.length < 50) throw invalid(`only ${fees.length} fees parsed.`);
    const present = new Set(
      fees.filter((fee) => fee.category === "renewal").map((fee) => fee.year),
    );
    const years = Array.from({ length: 19 }, (_, i) => i + 2);
    const missing = years.filter((year) => !present.has(year));
    const effective = `${list.year}-01-01`;
    const later = lists
      .filter((candidate) => candidate.year > list.year)
      .map((candidate) => candidate.year);
    return FeeScheduleSchema.parse({
      key: "CA/CIPO/patent",
      jurisdiction: "CA",
      issuing_body: "Canadian Intellectual Property Office",
      office_code: "CIPO",
      right: "patent",
      currency: "CAD",
      effective_date: effective,
      source_url: CIPO_FEES_URL,
      statutory_basis:
        "Patent Rules (SOR/2019-251), Schedule 2 (Tariff of Fees), adjusted each January 1 under the Service Fees Act.",
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
              "Maintenance fees for anniversaries 2-20 of pending applications and granted patents; year 20 is also due each later anniversary.",
          },
      unmapped_codes: unmapped,
      notes: `The ${list.year} list of fees (in force from January 1, ${list.year}).${later.length ? ` The page also lists ${later.join(", ")} fees, which are not yet in force.` : ""} Fees that differ for small entities have a small and a large row; fees that do not are untiered. Maintenance fees ("maintenance" in CIPO's terms) are annual and categorized renewal, expanded from the published bands to one row per anniversary; pending applications and granted patents each have their own rows; maintenance of category 1 patents (filed before October 1, 1989) is categorized other with its anniversary year. Fees given only as "See description" (${omitted.join("; ")}) are omitted.`,
      provenance: {
        ...result.provenance,
        as_of_status: `${list.year} fee list, in force from ${effective}`,
        effective_date: effective,
      },
    });
  }
}

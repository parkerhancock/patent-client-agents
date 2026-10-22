import { parseHTML } from "linkedom";
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
} from "./models.js";

/**
 * CNIPA's English fee page holds one table: a "Patent Fees – Domestic" part
 * with Roman-numeral sections (I. Filing Fee ... XIV) whose rows are split by
 * right ("1. Invention", "2. Utility Model", "3. Design"), then a PCT part.
 * CNIPA publishes no fee codes; codes here are slugs, as in Python.
 */
export const CNIPA_FEES_SOURCE = "CNIPA Patent Fee Schedule";
export const CNIPA_FEES_URL =
  "https://english.cnipa.gov.cn/col/col3000/index.html";
const PAGE_PATH = "/col/col3000/index.html";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`CNIPA fee schedule: ${message}`, 200, "INVALID_RESPONSE");

const squash = (text: string | null | undefined) =>
  (text ?? "").replace(/[\s ]+/g, " ").trim();

/** "2,500" -> "2500.00". */
export function parseYuanAmount(raw: string): string {
  const value = raw.trim();
  if (!/^\d{1,3}(?:,\d{3})*$|^\d+$/.test(value))
    throw invalid(`unrecognized amount ${value.slice(0, 20)}`);
  return `${value.replaceAll(",", "")}.00`;
}

/** The fee table's rows as [label, amount?] cell texts. */
export function cnipaRows(html: string): [string, string | null][] {
  const document = parseHTML(html).document as unknown as Document;
  const table = Array.from(document.querySelectorAll("table")).find(
    (candidate) =>
      /Filing Fee/.test(candidate.textContent ?? "") &&
      /Annual Fee/.test(candidate.textContent ?? ""),
  );
  if (!table) throw invalid("the fee table was not found.");
  return Array.from(table.querySelectorAll("tr"))
    .map((tr) =>
      Array.from(tr.querySelectorAll("td, th")).map((cell) =>
        squash(cell.textContent),
      ),
    )
    .filter((cells) => cells.some(Boolean))
    .map((cells) => [cells[0] ?? "", cells[1] ? cells[1] : null]);
}

/** Python's slug: lowercase, non-alphanumerics to "-", trimmed, then cut to 40. */
const slug = (label: string) =>
  label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);

const ROMAN = /^(XIV|XIII|XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)\.\s*/;
const RIGHT = /^\d+\.\s*(Invention|Utility Model|Design)\b/i;
const BAND = /^(\d+)\s*-\s*(\d+)\s*Years?/i;
const perMonth: FeeCondition = {
  trigger: "late_days",
  threshold: null,
  per_unit: true,
  description: "Per month of extension.",
};

/** Domestic sections, by Roman numeral. */
const DOMESTIC: Record<string, FeeCategory> = {
  I: "filing",
  III: "publication",
  IV: "other",
  V: "examination",
  VI: "appeal",
  VII: "renewal",
  IX: "petition",
  X: "extension",
  XI: "transfer",
  XIV: "other",
  XIII: "cancellation",
};
/** PCT rows by label; international phase (I) and national phase (II). */
const PCT: [RegExp, FeeCategory, string?][] = [
  [/^\(1\) Search Fee/, "search"],
  [/^Additional Search Fee/, "search"],
  [/Priority Document Fee/, "other"],
  [/^\(3\) Preliminary Examination Fee/, "examination"],
  [/^Additional Preliminary Examination Fee/, "examination"],
  [/Protest of the Unity/, "other"],
  [/Copy Document Fee/, "other"],
  [/Late Furnishing Fee/, "late_fee"],
  [/Restoration of Right/, "petition"],
  [/Surcharge for the Late Entry/, "late_fee"],
  [
    /^Preliminary Examination Phase/,
    "translation",
    "Correction of translation",
  ],
  [
    /^Substantive Examination Phase/,
    "translation",
    "Correction of translation",
  ],
  [/Restoration Fee for Unity/, "other"],
  [/Restoration Fee for Priority/, "petition"],
];

/** Invention-patent fees from the table rows. */
export function cnipaPatentFees(rows: [string, string | null][]): {
  fees: FeeItem[];
  unmapped: string[];
} {
  const fees: FeeItem[] = [];
  const unmapped: string[] = [];
  let part: "domestic" | "pct" | "other" = "other";
  let roman = "";
  let right = "";
  const push = (
    code: string,
    label: string,
    amount: string,
    category: FeeCategory,
    extra: Partial<FeeItem> = {},
  ) =>
    fees.push({
      code,
      label,
      category,
      rights: ["patent"],
      amount: parseYuanAmount(amount),
      currency: "CNY",
      tier: "none",
      year: null,
      condition: null,
      source_url: CNIPA_FEES_URL,
      notes: null,
      ...extra,
    });
  for (const [label, amount] of rows) {
    if (/^Patent Fees\s*[–-]\s*Domestic/.test(label)) {
      part = "domestic";
      continue;
    }
    if (/^Patent Fees\s*[–-]\s*PCT/.test(label)) {
      part = "pct";
      roman = "";
      continue;
    }
    if (/^Patent Fees\s*[–-]/.test(label)) {
      part = "other";
      continue;
    }
    const section = ROMAN.exec(label);
    if (section) {
      roman = section[1] as string;
      right = "";
    }
    if (part === "pct") {
      if (section || !amount) continue;
      const rule = PCT.find(([pattern]) => pattern.test(label));
      if (!rule) {
        unmapped.push(label);
        continue;
      }
      push(
        `cn-pct-${roman.toLowerCase()}-${slug(label)}`,
        rule[2] ? `${rule[2]} - ${label}` : label,
        amount,
        rule[1],
        {
          notes:
            roman === "I"
              ? "PCT international phase, fee charged by CNIPA as receiving office or international authority."
              : "PCT national phase in China.",
        },
      );
      continue;
    }
    if (part !== "domestic" || !roman) continue;
    const named = RIGHT.exec(label);
    if (named) right = (named[1] as string).toLowerCase();
    if (!amount) continue;
    const notes = `CNIPA section ${roman}.`;
    if (roman === "II") {
      const claims = /claim/i.test(label);
      const pages = /Exceeds page (\d+)/i.exec(label);
      push(
        `cn-ii-${slug(label)}`,
        label,
        amount,
        claims ? "excess_claims" : pages ? "excess_pages" : "filing",
        {
          condition: claims
            ? {
                trigger: "claims_over",
                threshold: 10,
                per_unit: true,
                description: "Per claim over 10.",
              }
            : pages
              ? {
                  trigger: "pages_over",
                  threshold: Number(pages[1]),
                  per_unit: true,
                  description: `Per description page over ${pages[1]}.`,
                }
              : null,
          notes,
        },
      );
      continue;
    }
    // Sections split by right: keep the invention rows only.
    if (
      ["I", "VI", "VII", "XII", "XIII"].includes(roman) &&
      right !== "invention"
    )
      continue;
    const category = DOMESTIC[roman];
    if (!category) {
      unmapped.push(label);
      continue;
    }
    if (roman === "VII") {
      const band = BAND.exec(label);
      if (!band)
        throw invalid(
          `annual fee row "${label.slice(0, 40)}" has no year band.`,
        );
      for (let year = Number(band[1]); year <= Number(band[2]); year++)
        push(
          `cn-vii-${slug(label)}-y${year}`,
          `Annual fee (invention), ${label}`,
          amount,
          "renewal",
          {
            year,
            notes,
          },
        );
      continue;
    }
    push(`cn-${roman.toLowerCase()}-${slug(label)}`, label, amount, category, {
      condition: roman === "X" ? perMonth : null,
      notes,
    });
  }
  return { fees, unmapped };
}

/** Fetches the CNIPA English fee page and projects the invention-patent schedule. */
export class CnipaFeesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://english.cnipa.gov.cn",
      sourceName: CNIPA_FEES_SOURCE,
      cache: { name: "cnipa_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  /** Invention-patent fees, domestic and PCT; utility model and design rows are not included. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const result = await this.http.text("GET", PAGE_PATH, options);
    const { fees, unmapped } = cnipaPatentFees(cnipaRows(result.data));
    if (fees.length < 30) throw invalid(`only ${fees.length} fees parsed.`);
    const present = new Set(
      fees.filter((fee) => fee.category === "renewal").map((fee) => fee.year),
    );
    const missing = Array.from({ length: 20 }, (_, i) => i + 1).filter(
      (year) => !present.has(year),
    );
    return FeeScheduleSchema.parse({
      key: "CN/CNIPA/patent",
      jurisdiction: "CN",
      issuing_body: "China National Intellectual Property Administration",
      office_code: "CNIPA",
      right: "patent",
      currency: "CNY",
      effective_date: null,
      source_url: CNIPA_FEES_URL,
      statutory_basis:
        "Patent Law of the People's Republic of China and its Implementing Regulations; fee standards set by the National Development and Reform Commission and the Ministry of Finance.",
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
              "Invention annual fees for years 1-20, expanded from the published bands.",
          },
      unmapped_codes: unmapped,
      notes:
        "Invention patents only; utility model and design rows on the same page are not routed. Annual fees are published in bands (1-3, 4-6, 7-9, 10-12, 13-15, 16-20 years) and expanded to one row per year. The late annual-fee surcharge (section VIII, 5% of the annual fee per month late) has no fixed amount and is omitted. Reductions for applicants with difficulty paying are granted separately and are not applied. PCT rows are fees CNIPA charges in the international phase and on national-phase entry.",
      provenance: {
        ...result.provenance,
        as_of_status: "effective date not published by the office",
        effective_date: null,
      },
    });
  }
}

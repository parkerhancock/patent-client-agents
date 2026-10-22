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
  type RecurringFeeCoverage,
} from "./models.js";

/**
 * PRV (Sweden) publishes English fee pages for patents, trademarks and
 * designs. The patent page has one table per section with a stable fee ID
 * (SE-1, N-3, PCT-2, ...); the trademark and design pages have two-column
 * tables under headings, without IDs. Amounts are SEK with space thousands
 * separators ("3 000 kr"). PRV has no entity-size tiers.
 */
export const PRV_FEES_SOURCE = "PRV fees";
export const PRV_PATENT_FEES_URL =
  "https://www.prv.se/en/patents/the-advanced-patent-guide/fees-and-payment/";
export const PRV_TRADEMARK_FEES_URL =
  "https://www.prv.se/en/trademarks/prepare-for-the-trademark-application/fees-and-payment/";
export const PRV_DESIGN_FEES_URL =
  "https://www.prv.se/en/designs/prepare-for-the-design-application/fees-for-designs/";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`PRV fee schedule: ${message}`, 200, "INVALID_RESPONSE");
const squash = (value: string | null | undefined) =>
  (value ?? "").replace(/\s+/g, " ").trim();

type Parsed =
  | { kind: "amount"; amount: string; unit: string }
  | { kind: "none"; text: string };
/** "3 000 kr" -> "3000.00"; "180 kr per sheet" keeps " per sheet" as the unit. */
export function parsePrvAmount(raw: string): Parsed {
  const text = squash(raw.replaceAll(" ", " "));
  const match = /^(\d{1,3}(?: \d{3})+|\d+)\s*(?:kr|SEK)\b\s*(.*)$/i.exec(text);
  if (!match) return { kind: "none", text };
  return {
    kind: "amount",
    amount: `${(match[1] as string).replaceAll(" ", "")}.00`,
    unit: match[2] as string,
  };
}
/** Python's slug: lowercase, non-alphanumerics to "-", each part capped at 50. */
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
function unique(code: string, seen: Set<string>): string {
  let candidate = code;
  for (let n = 2; seen.has(candidate); n++) candidate = `${code}-${n}`;
  seen.add(candidate);
  return candidate;
}
const document = (html: string) =>
  parseHTML(html).document as unknown as Document;
/** "Edited 2026-01-01" at the foot of each page: a revision date, not an effective date. */
const edited = (doc: Document) =>
  /Edited (\d{4}-\d{2}-\d{2})/.exec(squash(doc.body?.textContent))?.[1] ?? null;

const perClass = (threshold: number, what: string): FeeCondition => ({
  trigger: "classes_over",
  threshold,
  per_unit: true,
  description: `Per ${what} beyond the first.`,
});
const paper: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description:
    "Applies to filings made other than through PRV's e-service (paper, e-mail).",
};

// Patents -------------------------------------------------------------------

interface CodeRule {
  category: FeeCategory;
  condition?: FeeCondition;
  notes?: string;
}
const REDUCTION =
  "A reduction of another fee, not a charge; the amount is the reduction.";
/** Patent fee IDs mapped explicitly; N-1..N-20 are handled as the annuity ladder. */
const PATENT_RULES: Record<string, CodeRule> = {
  "SE-1": { category: "filing" },
  "SE-2": { category: "filing" },
  "SE-3": {
    category: "excess_claims",
    condition: {
      trigger: "claims_over",
      threshold: 10,
      per_unit: true,
      description: "Per claim beyond the first ten.",
    },
  },
  "SE-4": { category: "extension" },
  "SE-5": { category: "other" },
  "SE-6": { category: "other" },
  "SE-7": { category: "petition" },
  "SE-8": { category: "grant" },
  "SE-9": {
    category: "excess_claims",
    notes: "Per claim added after filing beyond the claims paid for.",
  },
  "SE-10": { category: "petition" },
  "SE-11": { category: "transfer" },
  "SE-12": { category: "search" },
  "SE-13": { category: "search" },
  "SE-14": { category: "search" },
  "SE-15": { category: "search" },
  "SE-16": {
    category: "excess_claims",
    condition: {
      trigger: "claims_over",
      threshold: 10,
      per_unit: true,
      description:
        "Per claim beyond ten for an International Type Search, where not already paid.",
    },
  },
  "SE-17": { category: "publication" },
  "SE-18": { category: "search" },
  "NM-1": { category: "petition" },
  "NM-2": { category: "transfer" },
  "NM-3": { category: "transfer" },
  "NM-4": { category: "transfer" },
  "NM-5": { category: "transfer" },
  "NT-1": {
    category: "filing",
    notes: "Supplementary protection certificate.",
  },
  "NT-2": {
    category: "other",
    notes:
      "Annual fee for a supplementary protection certificate, per year of SPC term; not a patent annuity.",
  },
  "NT-3": { category: "extension", notes: "SPC term extension." },
  "NPB-1": { category: "cancellation" },
  "PCT-1": { category: "filing" },
  "PCT-2": {
    category: "excess_pages",
    condition: {
      trigger: "sheets_over",
      threshold: 30,
      per_unit: true,
      description: "Per sheet over 30 (PCT Rule 15.2).",
    },
  },
  "PCT-3": { category: "other", notes: REDUCTION },
  "PCT-4": { category: "other", notes: REDUCTION },
  "PCT-6": { category: "petition" },
  "PCT-7": { category: "filing", notes: "Transmittal fee." },
  "PCT-8": { category: "search" },
  "PCT-9": { category: "other", notes: REDUCTION },
  "PCT-10": { category: "other", notes: REDUCTION },
  "PCT-12": {
    category: "search",
    notes: "Additional search fee for lack of unity.",
  },
  "PCT-14": { category: "search" },
  "PCT-15": { category: "examination" },
  "PCT-16": { category: "examination", notes: "IPEA handling fee." },
  "PCT-17": {
    category: "examination",
    notes: "Additional preliminary examination fee for lack of unity.",
  },
  "EP-1": { category: "translation" },
  "EP-2": { category: "translation" },
  "EP-3": { category: "translation" },
  "B-1": { category: "other" },
  "B-2": { category: "other" },
  "B-3": { category: "other" },
  "B-4": { category: "other" },
  "B-5": { category: "other" },
  "B-6": { category: "other" },
  "KT-1": { category: "search", notes: "PRV consultancy service." },
  "KT-2": { category: "search", notes: "PRV consultancy service." },
  "KT-3": { category: "other", notes: "PRV consultancy service." },
  "KT-4": { category: "search", notes: "PRV consultancy service." },
  "KT-5": { category: "other", notes: "PRV consultancy service." },
  "KT-16": { category: "search", notes: "PRV consultancy service." },
  "KT-18": { category: "other" },
  "KT-19": { category: "other" },
  "KT-20": { category: "other" },
  "KT-21": { category: "other" },
};
const ORDINAL = /^(\d+)(?:st|nd|rd|th) annual fee/;

interface PatentPage {
  fees: FeeItem[];
  omitted: string[];
  unmapped: string[];
}
function patentFees(doc: Document): PatentPage {
  const fees: FeeItem[] = [];
  const omitted: string[] = [];
  const unmapped: string[] = [];
  const seen = new Set<string>();
  let tables = 0;
  for (const table of Array.from(doc.querySelectorAll("table"))) {
    const rows = Array.from(table.querySelectorAll("tr"));
    const header = Array.from(rows[0]?.querySelectorAll("td, th") ?? []).map(
      (cell) => squash(cell.textContent),
    );
    if (header[0] !== "ID") continue;
    tables++;
    if (header[1] !== "Name of fee" || header[2] !== "Mandatory")
      throw invalid(`patent table columns changed: ${header.join(" | ")}`);
    const increased = /^Increased fee/.test(header[4] ?? "");
    for (const row of rows.slice(1)) {
      const cells = Array.from(row.querySelectorAll("td"));
      const id = squash(cells[0]?.textContent);
      if (!/^[A-Z]+-\d+$/.test(id)) continue;
      const name = cells[1];
      const title = squash(name?.querySelector("strong")?.textContent);
      const full = squash(name?.textContent);
      const description = squash(full.slice(title.length));
      const parsed = parsePrvAmount(cells[3]?.textContent ?? "");
      if (parsed.kind === "none") {
        omitted.push(id);
        continue;
      }
      const annuity = /^N-(\d+)$/.exec(id);
      let rule = PATENT_RULES[id];
      let year: number | null = null;
      if (annuity) {
        year = Number(annuity[1]);
        if (Number(ORDINAL.exec(title || full)?.[1]) !== year)
          throw invalid(`${id} is not the ${year} annual fee.`);
        rule = { category: "renewal" };
      } else if (!rule) unmapped.push(id);
      const notes = [
        description || null,
        parsed.unit ? `Charged ${parsed.unit.replace(/^\//, "per ")}.` : null,
        rule?.notes,
      ].filter(Boolean);
      const label = `${id}: ${title || full}`;
      fees.push({
        code: unique(slug("se", "pat", id), seen),
        label,
        category: rule?.category ?? "other",
        rights: ["patent"],
        amount: parsed.amount,
        currency: "SEK",
        tier: "none",
        year,
        condition: rule?.condition ?? null,
        source_url: PRV_PATENT_FEES_URL,
        notes: notes.join(" ") || null,
      });
      const late = increased
        ? parsePrvAmount(cells[4]?.textContent ?? "")
        : null;
      if (late?.kind === "amount" && year !== null)
        fees.push({
          code: unique(slug("se", "pat", id, "increased"), seen),
          label: `${label} (increased fee for late payment)`,
          category: "late_fee",
          rights: ["patent"],
          amount: late.amount,
          currency: "SEK",
          tier: "none",
          year,
          condition: null,
          source_url: PRV_PATENT_FEES_URL,
          notes:
            "The increased annual fee payable in the six-month period after the due date.",
        });
    }
  }
  if (tables < 10)
    throw invalid(`expected the full price list, found ${tables} tables.`);
  return { fees, omitted, unmapped };
}

// Trademarks and designs ------------------------------------------------------

interface LabelRule {
  match: RegExp;
  category: FeeCategory;
  year?: number;
  condition?: FeeCondition;
}
const TRADEMARK_RULES: LabelRule[] = [
  { match: /^Renewal application/, category: "renewal", year: 10 },
  {
    match: /^Increased fee for each class due to late renewal/,
    category: "late_fee",
    year: 10,
  },
  { match: /^Application for registration of a trademark/, category: "filing" },
  { match: /^Application of division|^Division of/, category: "other" },
  { match: /transfer of trademark ownership/, category: "transfer" },
  { match: /pledge/, category: "transfer" },
  { match: /licen[cs]e/, category: "transfer" },
  { match: /^Application for revocation/, category: "cancellation" },
  { match: /^Reinstatement/, category: "petition" },
  { match: /^Application for changes in a word mark/, category: "other" },
  { match: /^Application for permission to use/, category: "other" },
  {
    match:
      /^Registration certificates|^Historical certificate|^Priority document|^Dispatch fee|^Certificate relating to representation/,
    category: "other",
  },
  { match: /^Registration fee$/, category: "grant" },
  { match: /^Conversion of application/, category: "filing" },
  { match: /^Application for international registration/, category: "madrid" },
  { match: /^Replacement|^Transformation/, category: "madrid" },
];
const DESIGN_RULES: LabelRule[] = [
  { match: /^Filing fee for registration of 1 design/, category: "filing" },
  { match: /^For additional five-year period/, category: "filing" },
  {
    match: /^Multiple registration fee/,
    category: "filing",
    condition: {
      trigger: "multi_design",
      threshold: 1,
      per_unit: true,
      description: "Per design beyond the first in a multiple registration.",
    },
  },
  { match: /^Announcement fee/, category: "publication" },
  {
    match: /^Class fee for each additional class/,
    category: "excess_classes",
    condition: perClass(1, "class"),
  },
  { match: /^Storage fee/, category: "other" },
  {
    match: /^Surcharge when renewal fees are paid after/,
    category: "late_fee",
    year: 5,
  },
  {
    match: /^Renewal fee for a registered design|^Other renewal/,
    category: "renewal",
    year: 5,
  },
  { match: /new owner|new license/, category: "transfer" },
  {
    match:
      /^Priority document|^Certificate of registered design|^Dispatch fee|^Fee for issuing the certificate/,
    category: "other",
  },
];

interface Section {
  heading: string;
  tables: Element[];
}
function sections(doc: Document): Section[] {
  const main = doc.querySelector("main") ?? doc.body;
  const out: Section[] = [];
  for (const node of Array.from(main?.querySelectorAll("h2, table") ?? [])) {
    if (node.tagName === "H2")
      out.push({ heading: squash(node.textContent), tables: [] });
    else out.at(-1)?.tables.push(node);
  }
  return out.filter((section) => section.tables.length);
}
const rowsOf = (table: Element) =>
  Array.from(table.querySelectorAll("tr")).map((row) =>
    Array.from(row.querySelectorAll("td, th")).map((cell) =>
      squash(cell.textContent),
    ),
  );

interface LabelPage {
  fees: FeeItem[];
  unmapped: string[];
}
function trademarkFees(doc: Document): LabelPage {
  const fees: FeeItem[] = [];
  const unmapped: string[] = [];
  const seen = new Set<string>();
  const keys = new Set<string>();
  const all = sections(doc);
  for (const heading of [
    "Fees for Swedish trademark application",
    "Fees for changing, renewing and reinstatement a Swedish trademark",
  ]) {
    const section = all.find((s) => s.heading === heading);
    if (section?.tables.length !== 2)
      throw invalid(
        `"${heading}" no longer has an e-service and an other-channel table.`,
      );
  }
  for (const { heading, tables } of all) {
    const split = /Swedish trademark/.test(heading);
    const renewing = /renewing/.test(heading);
    tables.forEach((table, index) => {
      const channel = split
        ? index === 0
          ? "e-service"
          : "paper-or-other"
        : "";
      for (const [label = "", value = ""] of rowsOf(table)) {
        const parsed = parsePrvAmount(value);
        if (!label || parsed.kind === "none") continue;
        const key = [heading, label.slice(0, 60), channel].join("|");
        if (keys.has(key)) continue;
        keys.add(key);
        let rule = TRADEMARK_RULES.find((r) => r.match.test(label));
        if (/^For each additional class/.test(label))
          rule = renewing
            ? {
                match: /./,
                category: "renewal",
                year: 10,
                condition: perClass(1, "class"),
              }
            : {
                match: /./,
                category: "excess_classes",
                condition: perClass(1, "class"),
              };
        const code = unique(
          slug("se", "tm", channel, label.slice(0, 50)),
          seen,
        );
        if (!rule) unmapped.push(code);
        fees.push({
          code,
          label,
          category: rule?.category ?? "other",
          rights: ["trademark"],
          amount: parsed.amount,
          currency: "SEK",
          tier: "none",
          year: rule?.year ?? null,
          condition:
            rule?.condition ?? (channel === "paper-or-other" ? paper : null),
          source_url: PRV_TRADEMARK_FEES_URL,
          notes:
            [
              channel === "e-service"
                ? "Filed through PRV's e-service."
                : channel
                  ? "Filed other than through PRV's e-service (paper, e-mail)."
                  : null,
              `Section: ${heading}.`,
              rule?.year === 10
                ? "Registrations renew every 10 years; stored as year 10."
                : null,
            ]
              .filter(Boolean)
              .join(" ") || null,
        });
      }
    });
  }
  return { fees, unmapped };
}
function designFees(doc: Document): LabelPage {
  const fees: FeeItem[] = [];
  const unmapped: string[] = [];
  const seen = new Set<string>();
  const keys = new Set<string>();
  for (const { heading, tables } of sections(doc))
    for (const table of tables)
      for (const [raw = "", value = ""] of rowsOf(table)) {
        const parsed = parsePrvAmount(value);
        if (!raw || parsed.kind === "none") continue;
        // One surcharge row repeats with its amount pasted into the label.
        const label = raw
          .replace(/\s+\d[\d ]*\s*SEK$/, ".")
          .replace(/\.\.$/, ".");
        const key = [heading, label.replace(/\.$/, "").slice(0, 60)].join("|");
        if (keys.has(key)) continue;
        keys.add(key);
        const rule = DESIGN_RULES.find((r) => r.match.test(label));
        const channel = /electronic services/.test(label)
          ? "e-service"
          : /via paper|paper och e-mail/.test(label)
            ? "paper-or-other"
            : "";
        const other =
          channel === "paper-or-other" || /^Other renewal/.test(label);
        const code = unique(
          slug("se", "des", channel, label.slice(0, 50)),
          seen,
        );
        if (!rule) unmapped.push(code);
        fees.push({
          code,
          label,
          category: rule?.category ?? "other",
          rights: ["design"],
          amount: parsed.amount,
          currency: "SEK",
          tier: "none",
          year: rule?.year ?? null,
          condition: rule?.condition ?? (other ? paper : null),
          source_url: PRV_DESIGN_FEES_URL,
          notes:
            [
              `Section: ${heading}.`,
              rule?.year === 5
                ? "Registrations renew every five years; stored as year 5 for each renewal."
                : null,
            ]
              .filter(Boolean)
              .join(" ") || null,
        });
      }
  return { fees, unmapped };
}

// Client ----------------------------------------------------------------------

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

/** Fetches the PRV patent, trademark and design fee pages. */
export class PrvFeesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.prv.se",
      sourceName: PRV_FEES_SOURCE,
      cache: { name: "prv_se_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  private async page(url: string, options: TransportRequestOptions) {
    const result = await this.http.text("GET", new URL(url).pathname, options);
    const doc = document(result.data);
    const revised = edited(doc);
    return {
      doc,
      revised,
      provenance: {
        ...result.provenance,
        as_of_status: revised
          ? `effective date not published; page last edited ${revised}`
          : "effective date not published",
        effective_date: null,
      },
    };
  }
  private schedule(
    right: "patent" | "trademark" | "design",
    url: string,
    page: Awaited<ReturnType<PrvFeesClient["page"]>>,
    fees: FeeItem[],
    extra: {
      statutory_basis: string;
      coverage: RecurringFeeCoverage;
      unmapped: string[];
      notes: string;
    },
  ): FeeSchedule {
    if (!fees.length) throw invalid(`no ${right} fees parsed.`);
    const revised = page.revised
      ? ` The page was last edited ${page.revised}; that is a revision date, not an effective date.`
      : "";
    return FeeScheduleSchema.parse({
      key: `SE/PRV/${right}`,
      jurisdiction: "SE",
      issuing_body: "Patent- och registreringsverket (PRV)",
      office_code: "PRV",
      right,
      currency: "SEK",
      effective_date: null,
      source_url: url,
      statutory_basis: extra.statutory_basis,
      fees,
      recurring_fee_coverage: extra.coverage,
      unmapped_codes: extra.unmapped,
      notes: `${extra.notes} No entity-size tiers.${revised}`,
      provenance: page.provenance,
    });
  }
  /** National, PCT and European-validation patent fees, the annuity ladder and SPC fees. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page(PRV_PATENT_FEES_URL, options);
    const { fees, omitted, unmapped } = patentFees(page.doc);
    const grant = /From 1 December 2025 the fee for grant/.test(
      squash(page.doc.body?.textContent),
    )
      ? " The page states that the grant fee (SE-8) applies from 1 December 2025."
      : "";
    return this.schedule("patent", PRV_PATENT_FEES_URL, page, fees, {
      statutory_basis:
        "Patents Act (Patentlagen) and Patent Decree, with PRV fee regulations (PRVFS).",
      coverage: coverage(
        fees,
        Array.from({ length: 20 }, (_, i) => i + 1),
        "Annual fees for years 1-20 present; years 1 and 2 are SEK 0 and fall due with year 3.",
      ),
      unmapped,
      notes: `Fee IDs are PRV's own. Annual fees N-1 to N-20 are renewals by year, each with an increased fee for late payment as a late_fee of the same year. SPC annual fees (NT-2) are not patent annuities and carry no year. Reductions (PCT-3, PCT-4, PCT-9, PCT-10) are listed as reductions, not charges. Rows priced only by quotation, by formula or with no amount are omitted: ${omitted.join(", ")}.${grant}`,
    });
  }
  /** Trademark fees, with the e-service and other-channel rates as separate rows. */
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page(PRV_TRADEMARK_FEES_URL, options);
    const { fees, unmapped } = trademarkFees(page.doc);
    return this.schedule("trademark", PRV_TRADEMARK_FEES_URL, page, fees, {
      statutory_basis:
        "Trade Marks Act (Varumärkeslagen 2010:1877) and Trade Marks Ordinance, with PRV fee regulations (PRVFS).",
      coverage: coverage(
        fees,
        [10],
        "Registrations renew every 10 years; year 10 stands for each renewal.",
      ),
      unmapped,
      notes:
        "The Swedish application and renewal sections each publish an e-service table and an other-channel (paper, e-mail) table; other-channel rows carry a paper_filing condition. Per-class fees in the renewal section are renewal fees for year 10. Fees paid to WIPO for international registrations are in the WIPO-MADRID schedule.",
    });
  }
  /** Design fees; renewals are per five-year period. */
  async getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page(PRV_DESIGN_FEES_URL, options);
    const { fees, unmapped } = designFees(page.doc);
    return this.schedule("design", PRV_DESIGN_FEES_URL, page, fees, {
      statutory_basis:
        "Designs Protection Act (Mönsterskyddslagen 1970:485) and Designs Protection Ordinance (Mönsterskyddsförordningen 1970:486), with PRV fee regulations (PRVFS).",
      coverage: coverage(
        fees,
        [5],
        "Registrations renew every five years up to 25 years; year 5 stands for each renewal.",
      ),
      unmapped,
      notes:
        "The e-service and other-channel rates are distinguished in the row labels; other-channel rows carry a paper_filing condition. Renewal fees and the late-renewal surcharge are stored as year 5.",
    });
  }
}

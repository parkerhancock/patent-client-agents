import { parseHTML } from "linkedom";
import { CachedClient } from "../cache/client.js";
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
 * TIPO publishes its English patent fees as one HTML table and its trademark
 * fees as a bilingual (Chinese and English) PDF linked from a landing page.
 * Taiwan has three patent kinds under the Patent Act (invention, utility
 * model, design); all three share the patent schedule, as in Python.
 */
export const TIPO_FEES_SOURCE = "TIPO fee schedules";
export const TIPO_PATENT_FEES_URL = "https://www.tipo.gov.tw/en/tipo2/326.html";
export const TIPO_TRADEMARK_FEES_URL =
  "https://www.tipo.gov.tw/en/tipo2/342.html";
const tipoKey = (right: "patent" | "trademark") => `TW/TIPO/${right}`;
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`TIPO fee schedule: ${message}`, 200, "INVALID_RESPONSE");
const squash = (value: string | null | undefined) =>
  (value ?? "").replace(/\s+/g, " ").trim();

/** "NT$3,500" -> "3500.00". A stray trailing mark (TIPO's row 24 has a backtick) is tolerated; anything else fails. */
export function parseNtAmount(raw: string): string {
  const match = /^NT\$\s*(\d{1,3}(?:,\d{3})+|\d+)[^\d\w]*$/.exec(raw.trim());
  if (!match) throw invalid(`unrecognized amount ${raw.slice(0, 30)}`);
  return `${(match[1] as string).replaceAll(",", "")}.00`;
}

/** Python's `_slugify`: lowercase kebab-case parts joined with "-". */
const slug = (...parts: (string | number)[]) =>
  parts
    .map((part) =>
      String(part)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 40),
    )
    .filter(Boolean)
    .join("-");

/** "Update： 2025/04/07" on TIPO pages -> "2025-04-07". */
function pageUpdated(text: string): string | null {
  const match = /Update[：:]\s*(\d{4})\/(\d{2})\/(\d{2})/.exec(text);
  return match ? `${match[1]}-${match[2]}-${match[3]}` : null;
}

// ── Patents ─────────────────────────────────────────────────────────────

type PatentKind = "invention" | "utility model" | "design";
/** Term caps used to expand "Nth year and beyond" annuity rows. */
const TERM: Record<PatentKind, number> = {
  invention: 20,
  "utility model": 10,
  design: 15,
};
const ANNUITY =
  /annuity for a granted (invention|utility model|design) patent(?: or a granted (invention|utility model|design) patent)?\s*\(?\s*(?:(\d+)(?:st|nd|rd|th)?\s*-\s*(\d+)(?:st|nd|rd|th)?\s*year|(\d+)(?:st|nd|rd|th)?\s*year(?:\s+and beyond)?)/i;
const SMALL_ENTITY = /natural person.{0,20}school.{0,30}small and medium/i;

interface Annuity {
  kinds: PatentKind[];
  years: number[];
}
function annuity(description: string): Annuity | null {
  const match = ANNUITY.exec(description);
  if (!match) return null;
  const kinds = [match[1], match[2]]
    .filter((kind): kind is string => Boolean(kind))
    .map((kind) => kind.toLowerCase() as PatentKind);
  const from = Number(match[3] ?? match[5]);
  const to = match[4]
    ? Number(match[4])
    : Math.max(...kinds.map((kind) => TERM[kind]));
  return {
    kinds,
    years: Array.from({ length: to - from + 1 }, (_, i) => from + i),
  };
}

const claimsOver10: FeeCondition = {
  trigger: "claims_over",
  threshold: 10,
  per_unit: true,
  description: "Per claim over 10.",
};
const pagesOver50: FeeCondition = {
  trigger: "pages_over",
  threshold: 50,
  per_unit: true,
  description:
    "Per additional 50 pages (or part of 50) over 50 pages of description, claims, abstract and drawings.",
};
/** Keyword rules for non-annuity rows, most specific first. TIPO publishes row numbers, not fee codes. */
const PATENT_RULES: [RegExp, FeeCategory, FeeCondition?][] = [
  [/each additional claim|claims exceeds? 10/i, "excess_claims", claimsOver10],
  [/additional fee.*\bpages?\b/i, "excess_pages", pagesOver50],
  [
    /substantive examination|re-examination of an invention|technical evaluation report|accelerated examination/i,
    "examination",
  ],
  [
    /filing of (?:an invention|a utility model|a design)|conversion of .*application|division of .*application/i,
    "filing",
  ],
  [/adding supplementary reasons|post-grant amendment/i, "other"],
  [/invalidation/i, "cancellation"],
  [/early laying-open|interview/i, "other"],
  [/compulsory license/i, "petition"],
  [/recordation of changes/i, "other"],
  [/(?:attorney|agent) license/i, "other"],
  [/recordation|assignment|licens|pledge/i, "transfer"],
];
function patentCategory(description: string) {
  const rule = PATENT_RULES.find(([pattern]) => pattern.test(description));
  return { category: rule?.[1] ?? "other", condition: rule?.[2] ?? null };
}

interface PatentRow {
  row: number;
  description: string;
  amount: string;
}
function patentRows(html: string): PatentRow[] {
  const document = parseHTML(html).document as unknown as Document;
  const table = document.querySelector("table");
  if (!table) throw invalid("the patent fee table is missing.");
  const rows = Array.from(table.querySelectorAll("tr")).map((tr) =>
    Array.from(tr.querySelectorAll("th, td")).map((cell) =>
      squash(cell.textContent),
    ),
  );
  const [header, ...body] = rows;
  if (header?.[1] !== "Description" || header[2] !== "Fee")
    throw invalid("the patent fee table header changed.");
  const parsed = body.map((cells, index) => {
    if (cells.length !== 3 || !/^\d+$/.test(cells[0] as string))
      throw invalid(`patent fee row ${index + 1} changed shape.`);
    if (Number(cells[0]) !== index + 1)
      throw invalid("patent fee rows are not numbered consecutively.");
    return {
      row: Number(cells[0]),
      description: cells[1] as string,
      amount: parseNtAmount(cells[2] as string),
    };
  });
  if (parsed.length < 30) throw invalid("too few patent fee rows.");
  return parsed;
}

const PATENT_NOTE = (row: number, description: string) =>
  `TIPO Schedule of Patent Fees row ${row}. Source row: ${description}`;

function patentFees(rows: PatentRow[]): FeeItem[] {
  const fees: FeeItem[] = [];
  for (let index = 0; index < rows.length; index++) {
    const row = rows[index] as PatentRow;
    const band = annuity(row.description);
    if (!band) {
      if (SMALL_ENTITY.test(row.description))
        throw invalid(
          `row ${row.row} is a reduction with no annuity before it.`,
        );
      const { category, condition } = patentCategory(row.description);
      fees.push({
        code: slug("tipo", "patent", row.row),
        label: row.description,
        category,
        rights: ["patent"],
        amount: row.amount,
        currency: "TWD",
        tier: "none",
        year: null,
        condition,
        source_url: TIPO_PATENT_FEES_URL,
        notes: PATENT_NOTE(row.row, row.description),
      });
      continue;
    }
    const next = rows[index + 1];
    const reduced = next && SMALL_ENTITY.test(next.description) ? next : null;
    if (reduced) {
      // The reduction row restates the band and the reduced amount; check both.
      const [from, to] = [band.years[0], band.years.at(-1)];
      const stated = new RegExp(
        `for the ${from}(?:st|nd|rd|th)-${to}(?:st|nd|rd|th) year, cutting the annuity down to NT\\$([\\d,]+)`,
        "i",
      ).exec(reduced.description);
      if (!stated || `${stated[1]?.replaceAll(",", "")}.00` !== reduced.amount)
        throw invalid(
          `reduction row ${reduced.row} does not match annuity row ${row.row}.`,
        );
      index++;
    }
    for (const kind of band.kinds)
      for (const year of band.years)
        for (const tier of ["large", "small"] as const) {
          const amount =
            tier === "small" && reduced ? reduced.amount : row.amount;
          const notes = [PATENT_NOTE(row.row, row.description)];
          if (tier === "small")
            notes.push(
              reduced
                ? `Reduced annuity for a natural person, school or small and medium-sized enterprise (row ${reduced.row}).`
                : "No reduction for this year band; natural persons, schools and small and medium-sized enterprises pay the standard annuity.",
            );
          fees.push({
            code: slug("tipo", "annuity", kind, year, tier),
            label: `Annuity for granted ${kind} patent, year ${year}`,
            category: "renewal",
            rights: ["patent"],
            amount,
            currency: "TWD",
            tier,
            year,
            condition: null,
            source_url: TIPO_PATENT_FEES_URL,
            notes: notes.join(" "),
          });
        }
  }
  return fees;
}

function patentCoverage(fees: FeeItem[]): RecurringFeeCoverage {
  const missing: string[] = [];
  const years = new Set<number>();
  for (const kind of Object.keys(TERM) as PatentKind[]) {
    const present = new Set(
      fees
        .filter((fee) => fee.code.startsWith(slug("tipo", "annuity", kind, "")))
        .map((fee) => fee.year),
    );
    for (let year = 1; year <= TERM[kind]; year++)
      if (!present.has(year)) {
        missing.push(`${kind} ${year}`);
        years.add(year);
      }
  }
  return missing.length
    ? {
        status: "partial",
        missing_categories: [],
        missing_years: [...years].sort((a, b) => a - b),
        notes: `Annuities missing: ${missing.join(", ")}.`,
      }
    : {
        status: "complete",
        missing_categories: [],
        missing_years: [],
        notes:
          "Annuities for invention years 1-20, utility model years 1-10 and design years 1-15, at both tiers. The annuity for a prolonged (extended) invention term is not itemized by year.",
      };
}

// ── Trademarks ──────────────────────────────────────────────────────────

const perClass = (description: string): FeeCondition => ({
  trigger: "classes_over",
  threshold: 0,
  per_unit: true,
  description,
});
interface CatalogEntry {
  code: string;
  label: string;
  category: FeeCategory;
  amount: number;
  /** English text that must appear in the PDF within 300 characters of the amount. */
  phrase: string;
  condition?: FeeCondition;
  year?: number;
  notes?: string;
}
/**
 * The bilingual PDF interleaves Chinese and English, so rows can't be read
 * positionally; as in Python, a curated catalog is verified against it. Each
 * entry's phrase must occur with "NT$<amount>" nearby, or the parse fails.
 */
const TRADEMARK_CATALOG: CatalogEntry[] = [
  {
    code: "app-class-1to34",
    label:
      "Trademark or collective trademark — application, per class in Classes 1-34 (20 designated goods or fewer)",
    category: "filing",
    amount: 3000,
    phrase: "20 designated goods or less in a",
    condition: perClass("Per class in Nice Classes 1-34."),
  },
  {
    code: "app-class-1to34-over20-goods",
    label:
      "Trademark application — additional fee per designated good over 20 in a single class (Classes 1-34)",
    category: "filing",
    amount: 200,
    phrase: "Additional NT$200 per designate",
    notes:
      "Charged per designated good beyond 20 in one class; the condition vocabulary has no per-good trigger.",
  },
  {
    code: "app-class-35to45",
    label:
      "Trademark or collective trademark — application, per class in Classes 35-45",
    category: "filing",
    amount: 3000,
    phrase: "For a class in Classes 35 to 45",
    condition: perClass("Per class in Nice Classes 35-45."),
  },
  {
    code: "app-class-35-retail-over5",
    label:
      "Trademark application — additional fee per retail service of specific goods over 5 in Class 35",
    category: "filing",
    amount: 500,
    phrase: "Additional NT$500 per designate",
    notes:
      "Charged per designated retail service of specific goods beyond 5 in Class 35; the condition vocabulary has no per-service trigger.",
  },
  {
    code: "app-accelerated",
    label: "Trademark accelerated examination — additional fee per class",
    category: "examination",
    amount: 6000,
    phrase: "Trademark Accelerated Examination Additional NT$6,000 per class",
    condition: perClass("Per class, in addition to the application fee."),
  },
  {
    code: "app-collective-cert-mark",
    label: "Collective membership mark or certification mark — application",
    category: "filing",
    amount: 5000,
    phrase:
      "Collective membership mark or certification mark NT$5,000 per application",
  },
  {
    code: "app-efile-discount",
    label: "Trademark application — e-filing discount per application",
    category: "other",
    amount: 300,
    phrase: "A discount of NT$300 per application",
    notes: "A reduction of the application fee, not a charge.",
  },
  {
    code: "app-efile-matched-terms",
    label:
      "Trademark application — additional e-filing discount per class when every designated good or service matches the recommended terms",
    category: "other",
    amount: 300,
    phrase: "An additional discount of NT$300",
    notes: "A reduction of the application fee, not a charge.",
  },
  {
    code: "reg-trademark",
    label: "Trademark or collective trademark — registration, per class",
    category: "grant",
    amount: 2500,
    phrase: "NT$2,500 per class",
    condition: perClass("Per class."),
  },
  {
    code: "reg-collective-cert-mark",
    label: "Collective membership mark or certification mark — registration",
    category: "grant",
    amount: 2500,
    phrase: "NT$2,500 per registration",
  },
  {
    code: "renewal-trademark",
    label:
      "Trademark or collective trademark — renewal, per class (10-year cycle)",
    category: "renewal",
    amount: 4000,
    phrase: "Trademark or collective trademark NT$4,000 per class",
    condition: perClass("Per class."),
    year: 10,
  },
  {
    code: "renewal-collective-cert-mark",
    label:
      "Collective membership mark or certification mark — renewal (10-year cycle)",
    category: "renewal",
    amount: 4000,
    phrase:
      "Collective membership mark or certification mark NT$4,000 per renewal",
    year: 10,
  },
  {
    code: "division-application",
    label:
      "Division of an application for registration — per additional application after division",
    category: "other",
    amount: 2000,
    phrase: "Division of an application for registration NT$2,000",
  },
  {
    code: "division-registration",
    label:
      "Division of a trademark, certification mark, or collective trademark registration — per additional registration after division",
    category: "other",
    amount: 2000,
    phrase: "Division of a trademark, certification mar",
  },
  {
    code: "division-pre-disposition-surcharge",
    label:
      "Division surcharge — request made before the final disposition of an opposition, invalidation or revocation",
    category: "other",
    amount: 2000,
    phrase:
      "Prior to the final disposition of an opposition, invalidation, NT$2,000 in addition",
  },
  {
    code: "amend-particulars",
    label:
      "Amendment or change to particulars in a registration or application — per request",
    category: "other",
    amount: 500,
    phrase: "Amendment or chan",
  },
  {
    code: "restrict-goods-services",
    label:
      "Restriction of designated goods or services of a registered trademark — per request",
    category: "other",
    amount: 500,
    phrase:
      "Restriction of designated goods or services of a registered trademark NT$500 per request",
  },
  {
    code: "license-entry",
    label: "Entry of a license or sub-license — per entry",
    category: "transfer",
    amount: 2000,
    phrase: "Entry of a license o",
  },
  {
    code: "license-removal",
    label: "Entry of license or sub-license removal — per entry",
    category: "transfer",
    amount: 1000,
    phrase: "Entry of license or sub-license removal NT$1,000 per entry",
  },
  {
    code: "transfer-entry",
    label: "Registration transfer entry — per entry",
    category: "transfer",
    amount: 2000,
    phrase: "Registration transfer entry",
  },
  {
    code: "pledge-creation",
    label: "Pledge creation entry — per entry",
    category: "transfer",
    amount: 2000,
    phrase: "Pledge creation entry NT$2,000 per entry",
  },
  {
    code: "pledge-extinguishment",
    label: "Pledge extinguishment entry — per entry",
    category: "transfer",
    amount: 1000,
    phrase: "Pledge extinguishment entry NT$1,000 per entry",
  },
  {
    code: "opposition",
    label: "Opposition — per class",
    category: "opposition",
    amount: 4000,
    phrase: "Opposition NT$4,000 per class",
    condition: perClass("Per class opposed."),
  },
  {
    code: "invalidation",
    label: "Invalidation — per class",
    category: "cancellation",
    amount: 7000,
    phrase: "Invalidation NT$7,000 per class",
    condition: perClass("Per class."),
  },
  {
    code: "revocation",
    label: "Revocation — per class",
    category: "cancellation",
    amount: 7000,
    phrase: "Revocation NT$7,000 per class",
    condition: perClass("Per class."),
  },
  {
    code: "intervene",
    label:
      "Request to intervene in an opposition, invalidation, or revocation — per request",
    category: "other",
    amount: 2000,
    phrase:
      "Request to intervene in an opposition, invalidation or revocation NT$2,000 per request",
  },
  {
    code: "certified-copy",
    label: "Request to issue a certified copy of a document — per copy",
    category: "other",
    amount: 500,
    phrase: "Request to issue a certified copy of a document NT$500 per copy",
  },
  {
    code: "file-review",
    label: "Request to review official files of a case — per request",
    category: "other",
    amount: 500,
    phrase: "Request to review official files of a case NT$500 per request",
  },
  {
    code: "tm-agent-registration",
    label: "Trademark agent registration or change thereto — per request",
    category: "other",
    amount: 500,
    phrase:
      "trademark agent registrations or change thereto, NT$500 per request",
  },
  {
    code: "replacement-registration-cert",
    label:
      "Request to issue a replacement registration certificate or re-issue a registration certificate — per request",
    category: "other",
    amount: 500,
    phrase:
      "Request to issue a replacement registration certificate or re-issue a registration certificate of NT$500 per request",
  },
];

/** Python's `_normalize_for_match`: lowercase ASCII letters and digits only, so split words still match. */
export const normalizeForMatch = (value: string) =>
  value
    .replace(/[^ -~]+/g, " ")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");

function trademarkFees(pdfText: string): FeeItem[] {
  const haystack = normalizeForMatch(pdfText);
  return TRADEMARK_CATALOG.map((entry) => {
    const phrase = normalizeForMatch(entry.phrase);
    const needle = `nt${entry.amount}`;
    let found = false;
    for (
      let at = haystack.indexOf(phrase);
      at >= 0 && !found;
      at = haystack.indexOf(phrase, at + 1)
    )
      found = haystack
        .slice(Math.max(0, at - 300), at + phrase.length + 300)
        .includes(needle);
    if (!found)
      throw invalid(
        `trademark entry ${entry.code} (${entry.phrase}, NT$${entry.amount}) is not in the PDF; the schedule may have changed.`,
      );
    return {
      code: slug("tipo", "tm", entry.code),
      label: entry.label,
      category: entry.category,
      rights: ["trademark"],
      amount: `${entry.amount}.00`,
      currency: "TWD",
      tier: "none",
      year: entry.year ?? null,
      condition: entry.condition ?? null,
      source_url: TIPO_TRADEMARK_FEES_URL,
      notes: [
        `Verified against the bilingual Trademark Fee Standards PDF: "${entry.phrase}".`,
        entry.notes,
      ]
        .filter(Boolean)
        .join(" "),
    };
  });
}

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
/** "Enforced on May 1, 20 24" (pdf.js splits the year) -> "2024-05-01". */
export function trademarkEnforcedDate(pdfText: string): string | null {
  const match = /Enforced on ([A-Za-z]+) (\d{1,2}),\s*((?:\d\s*){4})\)/.exec(
    pdfText,
  );
  const month = match
    ? MONTHS.indexOf((match[1] as string).toLowerCase()) + 1
    : 0;
  if (!match || !month) return null;
  return `${(match[3] as string).replace(/\s/g, "")}-${String(month).padStart(2, "0")}-${(match[2] as string).padStart(2, "0")}`;
}

/** Fetches TIPO's patent fee page and trademark fee PDF. */
export class TipoFeesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.tipo.gov.tw",
      sourceName: TIPO_FEES_SOURCE,
      cache: { name: "tipo_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: {
        accept: "text/html,application/pdf",
        "user-agent": USER_AGENT,
      },
    });
  }
  /** Invention, utility model and design patent fees in TWD; annuities at large and small tiers. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const result = await this.http.text("GET", "/en/tipo2/326.html", options);
    const fees = patentFees(patentRows(result.data));
    const updated = pageUpdated(result.data);
    return FeeScheduleSchema.parse({
      key: tipoKey("patent"),
      jurisdiction: "TW",
      issuing_body: "Taiwan Intellectual Property Office",
      office_code: "TIPO",
      right: "patent",
      currency: "TWD",
      effective_date: null,
      source_url: TIPO_PATENT_FEES_URL,
      statutory_basis:
        "Patent Act (專利法) and the Regulations Governing Patent Fees; Schedule of Patent Fees on the TIPO English site.",
      fees,
      recurring_fee_coverage: patentCoverage(fees),
      unmapped_codes: [],
      notes:
        "Covers Taiwan's three patent kinds: invention (20-year term), utility model (10 years) and design (15 years). TIPO publishes row numbers, not fee codes; codes are tipo-patent-<row> and tipo-annuity-<kind>-<year>-<tier>. Annuity bands are expanded per year. Annuities carry a large and a small tier: the small tier is the reduced annuity for natural persons, schools and small and medium-sized enterprises in years 1-6, and equals the standard annuity from year 7. Procedural fees have no tier. Rows bundling several procedures under one amount keep the full text in the label.",
      provenance: {
        ...result.provenance,
        as_of_status: `effective date not published by the office${updated ? `; page updated ${updated}` : ""}`,
        effective_date: null,
      },
    });
  }
  /** Trademark fees in TWD from the Trademark Fee Standards PDF linked on the landing page. */
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const landing = await this.http.text("GET", "/en/tipo2/342.html", options);
    const document = parseHTML(landing.data).document as unknown as Document;
    const href = Array.from(document.querySelectorAll("a[href]"))
      .map((a) => a.getAttribute("href") ?? "")
      .find((value) => /\.pdf$/i.test(value));
    if (!href) throw invalid("the trademark landing page has no PDF link.");
    const pdf = await this.http.bytes(
      "GET",
      new URL(href, TIPO_TRADEMARK_FEES_URL).pathname,
      options,
    );
    const text = (await pdfPageTexts(pdf.data)).join("\n");
    const fees = trademarkFees(text);
    const enforced = trademarkEnforcedDate(text);
    const updated = pageUpdated(landing.data);
    return FeeScheduleSchema.parse({
      key: tipoKey("trademark"),
      jurisdiction: "TW",
      issuing_body: "Taiwan Intellectual Property Office",
      office_code: "TIPO",
      right: "trademark",
      currency: "TWD",
      effective_date: enforced,
      source_url: TIPO_TRADEMARK_FEES_URL,
      statutory_basis:
        "Trademark Act (商標法) Article 104 and the Trademark Fee Standards.",
      fees,
      recurring_fee_coverage: {
        status: "complete",
        missing_categories: [],
        missing_years: [],
        notes:
          "Registrations renew every 10 years (Trademark Act Article 33); year 10 stands for each renewal.",
      },
      unmapped_codes: [],
      notes:
        "From the bilingual Trademark Fee Standards PDF. Its interleaved Chinese and English text can't be read row by row, so a curated catalog of 30 fees is verified against it: each entry's English phrase must appear with its NT$ amount nearby, or the parse fails. Application, registration, renewal, opposition, invalidation and revocation fees are per class (threshold 0). The two e-filing discounts are reductions, not charges.",
      provenance: {
        ...pdf.provenance,
        as_of_status: [
          enforced
            ? `enforced ${enforced} per the PDF`
            : "effective date not stated in the PDF",
          updated ? `landing page updated ${updated}` : null,
        ]
          .filter(Boolean)
          .join("; "),
        effective_date: enforced,
      },
    });
  }
}

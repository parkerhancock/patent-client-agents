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
  type RightType,
} from "./models.js";

/**
 * The JPO publishes every official fee on one English HTML page. Numbered
 * h2 sections (1. Application ... 6. After Registration) hold h3
 * sub-sections per right ((1)Patents ... (4)Trademarks) with one table
 * each; sections 5 and 6 are single tables shared by every right. Patent
 * fees are mostly "¥X + ¥Y per claim" and trademark fees "per
 * classification". The JPO publishes no fee codes, so codes are slugs.
 * Utility-model tables are not routed (as in Python).
 */
export const JPO_FEES_SOURCE = "JPO schedule of fees";
export const JPO_FEES_URL =
  "https://www.jpo.go.jp/e/system/process/tesuryo/hyou.html";
const PAGE_PATH = "/e/system/process/tesuryo/hyou.html";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`JPO fee page: ${message}`, 200, "INVALID_RESPONSE");

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
const squash = (value: string | null | undefined) =>
  (value ?? "").replace(/[\s　]+/g, " ").trim();

/** "¥4,300 + ¥300 per claim" -> { base: "4300", per: "300", unit: "claim" }. */
export interface YenCell {
  base: string | null;
  per: string | null;
  unit: "claim" | "classification" | "sheet" | null;
}
export function parseYenCell(raw: string): YenCell {
  const value = squash(raw);
  const yen = String.raw`¥\s?(\d{1,3}(?:,\d{3})*)`;
  const match = new RegExp(
    `^(?:${yen}(?:\\s?\\+\\s?${yen} per (claim|classification|sheet))?|${yen} per (classification))$`,
  ).exec(value);
  if (!match) throw invalid(`unrecognized fee ${value.slice(0, 40)}`);
  const amount = (text: string | undefined) =>
    text === undefined ? null : text.replaceAll(",", "");
  if (match[4] !== undefined)
    return { base: null, per: amount(match[4]), unit: "classification" };
  return {
    base: amount(match[1]),
    per: amount(match[2]),
    unit: (match[3] as YenCell["unit"]) ?? null,
  };
}

interface Table {
  h2: string;
  h3: string;
  h4: string;
  caption: string;
  /** Data rows after rowspan/colspan expansion: descriptive cells, then the fee. */
  rows: { description: string; fee: string }[];
}

/** Expand rowspan and colspan into a grid so continuation rows keep their labels. */
function grid(table: Element): string[][] {
  const out: string[][] = [];
  const carry: { text: string; left: number }[] = [];
  for (const tr of Array.from(table.querySelectorAll("tr"))) {
    const row: string[] = [];
    const cells = Array.from(tr.children).filter((cell) =>
      ["TD", "TH"].includes(cell.tagName.toUpperCase()),
    );
    let column = 0;
    const take = () => {
      while (carry[column] && (carry[column]?.left ?? 0) > 0) {
        const spanned = carry[column] as { text: string; left: number };
        row.push(spanned.text);
        spanned.left--;
        column++;
      }
    };
    for (const cell of cells) {
      take();
      const text = squash(cell.textContent);
      const rowspan = Number(cell.getAttribute("rowspan") ?? 1);
      const colspan = Number(cell.getAttribute("colspan") ?? 1);
      for (let i = 0; i < colspan; i++) {
        row.push(text);
        carry[column] = { text, left: rowspan - 1 };
        column++;
      }
    }
    take();
    out.push(row);
  }
  return out;
}

function tables(html: string) {
  const document = parseHTML(html).document as unknown as Document;
  const text = squash(document.body?.textContent);
  const effective =
    /Schedule of fees \(on or after ([A-Z][a-z]+) (\d{1,2}), (\d{4})\)/.exec(
      text,
    );
  if (!effective) throw invalid("the effective-date heading was not found.");
  const month = MONTHS.indexOf(effective[1] as string) + 1;
  if (!month) throw invalid("unrecognized effective date.");
  const updated = /Last updated (\d{1,2}) ([A-Z][a-z]+) (\d{4})/.exec(text);
  const found: Table[] = [];
  let h2 = "";
  let h3 = "";
  let h4 = "";
  for (const node of Array.from(
    document.querySelectorAll("h2, h3, h4, table"),
  )) {
    const tag = node.tagName.toUpperCase();
    if (tag === "H2") [h2, h3, h4] = [squash(node.textContent), "", ""];
    else if (tag === "H3") [h3, h4] = [squash(node.textContent), ""];
    else if (tag === "H4") h4 = squash(node.textContent);
    else {
      const rows = grid(node)
        .filter((row) => !/^Fees$/i.test(row.at(-1) ?? ""))
        .map((row) => {
          const labels = row
            .slice(0, -1)
            .filter((cell, i, all) => cell && cell !== all[i - 1]);
          return { description: labels.join(" "), fee: row.at(-1) ?? "" };
        });
      found.push({
        h2,
        h3,
        h4,
        caption: squash(node.querySelector("caption")?.textContent),
        rows,
      });
    }
  }
  return {
    found,
    effectiveDate: `${effective[3]}-${String(month).padStart(2, "0")}-${(effective[2] as string).padStart(2, "0")}`,
    updated: updated
      ? `${updated[3]}-${String(MONTHS.indexOf(updated[2] as string) + 1).padStart(2, "0")}-${(updated[1] as string).padStart(2, "0")}`
      : null,
  };
}

type Draft = Pick<FeeItem, "code" | "label" | "category" | "amount"> & {
  rights?: RightType[];
  year?: number;
  condition?: FeeCondition;
  notes?: string;
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
  description: "Per classification, including the first.",
};
const PER_SHEET: FeeCondition = {
  trigger: "sheets_over",
  threshold: 0,
  per_unit: true,
  description: "Per sheet.",
};
const ALL_RIGHTS: RightType[] = [
  "patent",
  "utility_model",
  "design",
  "trademark",
];

/** A base fee plus, when the cell has one, its per-claim/classification/sheet part. */
function split(
  code: string,
  label: string,
  category: FeeCategory,
  cell: YenCell,
  extra: Omit<Draft, "code" | "label" | "category" | "amount"> = {},
): Draft[] {
  const out: Draft[] = [];
  if (cell.base !== null)
    out.push({ code, label, category, amount: cell.base, ...extra });
  if (cell.per !== null) {
    const condition =
      cell.unit === "claim"
        ? PER_CLAIM
        : cell.unit === "sheet"
          ? PER_SHEET
          : PER_CLASS;
    if (cell.base === null)
      out.push({
        code,
        label,
        category,
        amount: cell.per,
        ...extra,
        condition,
      });
    else
      out.push({
        code: `${code}-per-${cell.unit === "classification" ? "class" : cell.unit}`,
        label: `${label} - per ${cell.unit}`,
        category:
          cell.unit === "claim"
            ? "excess_claims"
            : cell.unit === "sheet"
              ? "excess_pages"
              : "excess_classes",
        amount: cell.per,
        ...extra,
        condition,
      });
  }
  return out;
}

const range = (from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, i) => from + i);
const band = (description: string) => {
  const match = /^(\d+)-(\d+)(?:st|nd|rd|th) year: annually,/.exec(description);
  return match ? ([Number(match[1]), Number(match[2])] as const) : null;
};
const slug = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 50)
    .replace(/-$/, "");
const clean = (description: string) =>
  description.replace(/\s?※\d/g, "").replace(/:$/, "");

interface Row {
  table: Table;
  description: string;
  cell: YenCell;
}
type Mapper = (row: Row) => Draft[] | null;

const section = (table: Table) => Number(/^(\d)\./.exec(table.h2)?.[1] ?? 0);
const right = (table: Table): RightType | null => {
  const sub = /^\((\d)\)/.exec(table.h3)?.[1];
  return sub
    ? (
        {
          "1": "patent",
          "2": "utility_model",
          "3": "design",
          "4": "trademark",
        } as const
      )[sub as "1" | "2" | "3" | "4"]
    : null;
};

/** Section 2 (1988+ filings) and section 3 cohorts, as code suffixes and notes. */
function cohort(table: Table): { suffix: string; note: string } | null {
  const caption = table.caption.toLowerCase();
  const filedBefore1988 = /on or before december 31, 1987/i.test(table.h4);
  const filedAfter1988 = /on or after january 1, 1988/i.test(table.h4);
  if (section(table) === 2) {
    if (/on or after april 1, 2019/.test(caption))
      return {
        suffix: "",
        note: "Applications filed on or after April 1, 2019.",
      };
    if (/on or before march 31, 2019/.test(caption))
      return {
        suffix: "-pre-2019",
        note: "Applications filed on or before March 31, 2019.",
      };
    return null;
  }
  if (!filedBefore1988 && !filedAfter1988) return null;
  const examAfter = /requested for examination on or after april 1, 2004/.test(
    caption,
  );
  const examBefore =
    /requested for examination on or before march 31, 2004/.test(caption);
  if (examAfter === examBefore) return null;
  const parts = [
    filedBefore1988 ? "-filed-pre-1988" : "",
    examBefore ? "-exam-pre-2004" : "",
  ];
  return {
    suffix: parts.join(""),
    note: `Applications filed ${filedBefore1988 ? "on or before December 31, 1987" : "on or after January 1, 1988"} and requested for examination ${examBefore ? "on or before March 31, 2004" : "on or after April 1, 2004"}.`,
  };
}

const EXAMINATION: Record<string, [string, string]> = {
  "Request for examination": ["jp-examination", "Request for examination"],
  "-where the international search report has been established by the JPO (under the PCT)":
    [
      "jp-examination-pct-jpo-isr",
      "Request for examination, PCT national phase where the JPO established the international search report",
    ],
  "-where the international search report has been established by an International Searching Authority other than the JPO (under the PCT)":
    [
      "jp-examination-pct-other-isr",
      "Request for examination, PCT national phase where another International Searching Authority established the international search report",
    ],
  "-where the search report has been established by a designated searching organization":
    [
      "jp-examination-designated-search",
      "Request for examination where a designated searching organization established the search report",
    ],
};

/** Patent rows of sections 1-4, by section. */
const patent: Mapper = (row) => {
  const { table, description, cell } = row;
  const label = clean(description);
  switch (section(table)) {
    case 1: {
      const map: Record<string, [string, FeeCategory, string?]> = {
        "Patent application": ["jp-application", "filing"],
        "Application in foreign language": [
          "jp-application-foreign-language",
          "filing",
        ],
        "Submission of a description and drawings for a patent application containing a reference to a previously filed application":
          ["jp-application-by-reference", "filing"],
        "Entry into the national phase in Japan (under the PCT)": [
          "jp-pct-national-phase",
          "filing",
        ],
        "Application for registration of an extension of the term of patent right":
          [
            "jp-term-extension",
            "other",
            "Patent term extension, not an extension of time.",
          ],
      };
      const hit = map[description];
      if (!hit) return null;
      return split(
        hit[0],
        label,
        hit[1],
        cell,
        hit[2] ? { notes: hit[2] } : {},
      );
    }
    case 2: {
      const which = cohort(table);
      const hit = EXAMINATION[description];
      if (!which || !hit) return null;
      return split(`${hit[0]}${which.suffix}`, hit[1], "examination", cell, {
        notes: which.note,
      });
    }
    case 3: {
      const which = cohort(table);
      const years = band(description);
      if (!which || !years || cell.base === null) return null;
      return range(years[0], years[1]).flatMap((year) =>
        split(
          `jp-annual-fee${which.suffix}-y${year}`,
          `Annual fee, year ${year}`,
          "renewal",
          cell,
          {
            year,
            notes: `Band ${years[0]}-${years[1]} years. ${which.note}`,
          },
        ),
      );
    }
    case 4: {
      const map: Record<string, [string, FeeCategory]> = {
        Opposition: ["jp-opposition", "opposition"],
        "Request for correction": ["jp-correction", "petition"],
        Appeal: ["jp-appeal", "appeal"],
        "Trial / Retrial": ["jp-trial", "trial"],
        "Trial / Retrial for registration of an extension of the term of patent right":
          ["jp-trial-term-extension", "trial"],
      };
      const hit = map[description];
      return hit ? split(hit[0], label, hit[1], cell) : null;
    }
    default:
      return null;
  }
};

const trademark: Mapper = ({ table, description, cell }) => {
  const label = clean(description).replace(/^-/, "");
  const renewal = {
    year: 10,
    notes:
      "Registrations renew every 10 years; year 10 stands for each renewal.",
  };
  const installment =
    "Paid in two five-year installments; the amount is per installment.";
  const map: Record<string, Draft[] | null> = {
    "Trademark application": split("jp-tm-application", label, "filing", cell),
    "Defensive mark application": split(
      "jp-tm-defensive-mark-application",
      label,
      "filing",
      cell,
    ),
    "Registration fee:": split("jp-tm-registration", label, "grant", cell),
    "-Payment of registration fee by installments": split(
      "jp-tm-registration-installment",
      label,
      "grant",
      cell,
      { notes: installment },
    ),
    "Renewal fee:": split("jp-tm-renewal", label, "renewal", cell, renewal),
    "-Payment of renewal fee by installments": split(
      "jp-tm-renewal-installment",
      label,
      "renewal",
      cell,
      { ...renewal, notes: `${renewal.notes} ${installment}` },
    ),
    "Defensive mark registration fee:": split(
      "jp-tm-defensive-mark-registration",
      label,
      "grant",
      cell,
    ),
    "Defensive mark renewal fee:": split(
      "jp-tm-defensive-mark-renewal",
      label,
      "renewal",
      cell,
      renewal,
    ),
    Opposition: split("jp-tm-opposition", label, "opposition", cell),
    Appeal: split("jp-tm-appeal", label, "appeal", cell),
    "Trial / Retrial": split("jp-tm-trial", label, "trial", cell),
  };
  return [1, 3, 4].includes(section(table)) ? (map[description] ?? null) : null;
};

const design: Mapper = ({ table, description, cell }) => {
  const label = clean(description);
  if (section(table) === 3) {
    const years = band(description);
    if (!years || cell.base === null) return null;
    // The 4-15, 4-20 and 4-25 rows share one amount; each year is listed once.
    return range(years[0], years[1]).map((year) => ({
      code: `jp-des-annual-fee-y${year}`,
      label: `Annual fee, year ${year}`,
      category: "renewal" as const,
      amount: cell.base as string,
      year,
      notes: [
        `Band ${years[0]}-${years[1]} years.`,
        year > 20
          ? "Only designs filed on or after April 1, 2020."
          : year > 15
            ? "Only designs filed on or after April 1, 2007."
            : null,
      ]
        .filter(Boolean)
        .join(" "),
    }));
  }
  const map: Record<string, [string, FeeCategory, string?]> = {
    "Design application ※1": ["jp-des-application", "filing"],
    "Request for secret design ※2": [
      "jp-des-secret-design",
      "other",
      "Request to keep the registered design secret for up to three years.",
    ],
    Appeal: ["jp-des-appeal", "appeal"],
    "Trial / Retrial": ["jp-des-trial", "trial"],
  };
  const hit = [1, 4].includes(section(table)) ? map[description] : undefined;
  return hit
    ? split(hit[0], label, hit[1], cell, hit[2] ? { notes: hit[2] } : {})
    : null;
};

/** Section 5 (procedural fees for every right) and section 6 (registration after grant). */
function shared(
  row: Row,
  schedule: "patent" | "design" | "trademark",
): Draft[] | null {
  const { table, description, cell } = row;
  const label = description.replace(/: -/, " -").replace(/:$/, "");
  const all = { rights: ALL_RIGHTS };
  if (section(table) === 5) {
    if (
      /^Request for extension of the time limit specified under the Article 50 of the Patent Act as applied mutatis mutandis in Article 19 of the Design Act/.test(
        description,
      )
    )
      return schedule === "design"
        ? split("jp-des-extension-article-50-late", label, "extension", cell)
        : [];
    if (
      /^Request for extension of the time limit specified under the Article 50 of the Patent Act after/.test(
        description,
      )
    )
      return schedule === "patent"
        ? split("jp-extension-article-50-late", label, "extension", cell)
        : [];
    const map: [RegExp, string, FeeCategory][] = [
      [
        /^Request for extension of a period$/,
        "jp-extension-of-period",
        "extension",
      ],
      [
        /^Request for extension of a specified time limit after the expiration/,
        "jp-extension-late",
        "extension",
      ],
      [
        /^Notification of succession/,
        "jp-notification-of-succession",
        "transfer",
      ],
      [
        /^Fee for rewriting data into electronic format$/,
        "jp-electronic-conversion",
        "other",
      ],
    ];
    const hit = map.find(([pattern]) => pattern.test(description));
    if (hit) return split(hit[1], label, hit[2], cell, all);
    const service =
      /^Request for (other certificates|inspection of documents|inspection of the Register|copy of documents|issue of documents|copy of the Register|issue of the Register)(?: \((paper|digital)\))?:? ?(?:-(on-line|over the counter))?$/.exec(
        description,
      );
    if (!service) return null;
    return split(`jp-${slug(description)}`, label, "other", cell, all);
  }
  if (section(table) === 6) {
    const transfer = /^Registration of transfer of right: -(.+)$/.exec(
      description,
    )?.[1];
    if (transfer) {
      const target = {
        Patents: "patent",
        Designs: "design",
        Trademarks: "trademark",
        "Utility models": "utility_model",
      }[transfer];
      if (target === schedule)
        return split(
          `jp-${{ patent: "", design: "des-", trademark: "tm-" }[schedule]}transfer-of-right`,
          `Registration of transfer of right - ${transfer.toLowerCase()}`,
          "transfer",
          cell,
        );
      if (target) return [];
      if (/^General successions/.test(transfer))
        return split(
          "jp-general-succession",
          "Registration of transfer of right - general successions (inheritance, etc.)",
          "transfer",
          cell,
          all,
        );
      return null;
    }
    if (
      /^Change in the name of owner \(excluding transfer\)$/.test(description)
    )
      return split("jp-change-of-owner-name", label, "other", cell, all);
  }
  return null;
}

const MAPPERS: Record<"patent" | "design" | "trademark", Mapper> = {
  patent,
  design,
  trademark,
};

function build(
  found: Table[],
  schedule: "patent" | "design" | "trademark",
): { drafts: Draft[]; unmapped: string[] } {
  const drafts: Draft[] = [];
  const unmapped: string[] = [];
  const seen = new Map<string, string>();
  for (const table of found) {
    const sectionNumber = section(table);
    if (!sectionNumber)
      throw invalid(
        `a table sits outside the numbered sections (${table.h2 || "no heading"}).`,
      );
    const tableRight = right(table);
    if (sectionNumber <= 4 && !tableRight)
      throw invalid(`a section ${sectionNumber} table has no right heading.`);
    if (sectionNumber <= 4 && tableRight !== schedule) continue;
    for (const { description, fee } of table.rows) {
      if (!description) throw invalid("a fee row has no description.");
      const row = { table, description, cell: parseYenCell(fee) };
      const mapped =
        sectionNumber >= 5 ? shared(row, schedule) : MAPPERS[schedule](row);
      if (mapped === null) {
        const code = `jp-${{ patent: "", design: "des-", trademark: "tm-" }[schedule]}${slug(description)}`;
        unmapped.push(code);
        drafts.push(
          ...split(code, description, "other", row.cell, {
            notes: `Unrecognized JPO row under ${table.h2}${table.h3 ? ` ${table.h3}` : ""}.`,
          }),
        );
        continue;
      }
      for (const draft of mapped) {
        // The page repeats rows with identical fees (e.g. "Request for correction" under opposition and appeal).
        const signature = `${draft.label}|${draft.amount}|${draft.year}`;
        const previous = seen.get(draft.code);
        if (previous === signature) continue;
        if (previous) throw invalid(`conflicting rows for ${draft.code}.`);
        seen.set(draft.code, signature);
        drafts.push(draft);
      }
    }
  }
  return { drafts, unmapped };
}

function coverage(
  drafts: Draft[],
  years: number[],
  notes: string,
): RecurringFeeCoverage {
  const present = new Set(
    drafts.filter((d) => d.category === "renewal").map((d) => d.year),
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

interface Page {
  found: Table[];
  effectiveDate: string;
  provenance: FeeSchedule["provenance"];
}

/**
 * Fetches the JPO schedule of fees page and projects the patent, trademark
 * and design schedules. The JPO's CloudFront edge answered plain requests
 * with HTTP 403 when this port was recorded; see docs/fees.md.
 */
export class JpoFeesClient {
  private readonly http: GenericHttpTransport;
  private pending: Promise<Page> | null = null;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.jpo.go.jp",
      sourceName: JPO_FEES_SOURCE,
      headers: { accept: "text/html", "user-agent": USER_AGENT },
    });
  }
  private page(options: TransportRequestOptions): Promise<Page> {
    this.pending ??= (async () => {
      const result = await this.http.text("GET", PAGE_PATH, options);
      const parsed = tables(result.data);
      return {
        found: parsed.found,
        effectiveDate: parsed.effectiveDate,
        provenance: {
          ...result.provenance,
          as_of_status: [
            `schedule of fees on or after ${parsed.effectiveDate}`,
            parsed.updated ? `page last updated ${parsed.updated}` : null,
          ]
            .filter(Boolean)
            .join("; "),
          effective_date: parsed.effectiveDate,
        },
      };
    })().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }
  private async schedule(
    schedule: "patent" | "design" | "trademark",
    options: TransportRequestOptions,
    extra: {
      statutory_basis: string;
      years: number[];
      coverage: string;
      notes: string;
    },
  ): Promise<FeeSchedule> {
    const page = await this.page(options);
    const built = build(page.found, schedule);
    if (!built.drafts.length) throw invalid(`no ${schedule} fees parsed.`);
    return FeeScheduleSchema.parse({
      key: `JP/JPO/${schedule}`,
      jurisdiction: "JP",
      issuing_body: "Japan Patent Office",
      office_code: "JPO",
      right: schedule,
      currency: "JPY",
      effective_date: page.effectiveDate,
      source_url: JPO_FEES_URL,
      statutory_basis: extra.statutory_basis,
      fees: built.drafts.map((draft) => ({
        code: draft.code,
        label: draft.label,
        category: draft.category,
        rights: draft.rights ?? [schedule],
        amount: draft.amount,
        currency: "JPY",
        tier: "none",
        year: draft.year ?? null,
        condition: draft.condition ?? null,
        source_url: JPO_FEES_URL,
        notes: draft.notes || null,
      })),
      recurring_fee_coverage: coverage(
        built.drafts,
        extra.years,
        extra.coverage,
      ),
      unmapped_codes: built.unmapped,
      notes: `${extra.notes} Procedural fees from sections 5 and 6 of the page apply to every right and list all four rights. The JPO's fee reductions (SMEs, universities and others) are separate programs and not on this schedule, so every fee has tier none.`,
      provenance: page.provenance,
    });
  }
  /** Patent fees: filing, examination by cohort, annual fees years 1-25 by cohort, trials and procedural fees. */
  getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("patent", options, {
      statutory_basis:
        "Patent Act (Act No. 121 of 1959), Article 107 and Article 195 and the appended tables.",
      years: range(1, 25),
      coverage:
        "Annual fees for years 1-25 present (years 21-25 apply to extended terms).",
      notes:
        "Most patent fees are a base amount plus an amount per claim; the per-claim part is a separate excess_claims row (claims_over, threshold 0). Examination fees differ for applications filed before and after April 1, 2019, and annual fees by filing date (before or after January 1, 1988) and examination request date (before or after April 1, 2004); each cohort is listed, the current one with no code suffix.",
    });
  }
  /** Trademark fees: per-classification application, registration, renewal, opposition and trial fees. */
  getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("trademark", options, {
      statutory_basis:
        "Trademark Act (Act No. 127 of 1959), Articles 40 and 76.",
      years: [10],
      coverage:
        "Registrations renew every 10 years; year 10 stands for each renewal.",
      notes:
        "Application, opposition and trial fees are a base amount plus an amount per classification (a separate excess_classes row); registration and renewal fees are per classification only. Registration and renewal can be paid in full or in two five-year installments; both are listed.",
    });
  }
  /** Design fees: application, annual fees years 1-25, appeals and procedural fees. */
  getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("design", options, {
      statutory_basis: "Design Act (Act No. 125 of 1959), Articles 42 and 67.",
      years: range(1, 25),
      coverage:
        "Annual fees for years 1-25 present; the term depends on the filing date.",
      notes:
        "Annual fees are ¥8,500 for years 1-3 and ¥16,900 from year 4 to the end of the term: year 15 for designs filed before April 1, 2007, year 20 for designs filed from then to March 31, 2020, and year 25 after that.",
    });
  }
}

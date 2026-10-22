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
  type RecurringFeeCoverage,
} from "./models.js";

/**
 * The USPTO publishes patent and trademark fees on one HTML page, a table per
 * section. Patent rows carry one fee code per entity size (large/small/micro,
 * e.g. 1011/2011/3011); trademark rows carry an electronic and a paper code.
 * USPTO publishes no structured (JSON/CSV) fee feed.
 */
export const USPTO_FEES_SOURCE = "USPTO Fee Schedule";
export const USPTO_FEES_URL =
  "https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule";
const PAGE_PATH = "/learning-and-resources/fees-and-payment/uspto-fee-schedule";

const invalid = (message: string) =>
  new ApiError(`USPTO fee schedule: ${message}`, 200, "INVALID_RESPONSE");

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
/** "January 19, 2025" -> "2025-01-19". */
function isoDate(value: string): string {
  const match = /^([A-Z][a-z]+) (\d{1,2}), (\d{4})$/.exec(value.trim());
  const month = match ? MONTHS.indexOf(match[1] as string) + 1 : 0;
  if (!match || month === 0) throw invalid(`unrecognized date ${value}`);
  return `${match[3]}-${String(month).padStart(2, "0")}-${(match[2] as string).padStart(2, "0")}`;
}

/** "2,150.00" -> "2150.00"; "n/a" -> null. Anything else fails. */
export function parseUsdAmount(raw: string): string | null {
  const value = raw.trim();
  if (/^n\/a$/i.test(value)) return null;
  if (!/^(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}$/.test(value))
    throw invalid(`unrecognized amount ${value.slice(0, 30)}`);
  return value.replaceAll(",", "");
}

type Route = "patent" | "design" | "both" | "plant";
interface CodeRule {
  category: FeeCategory;
  route?: Route;
  year?: number;
  condition?: FeeCondition;
  notes?: string;
}
const rules = (codes: string[], rule: CodeRule): [string, CodeRule][] =>
  codes.map((code) => [code, rule]);
const span = (from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, i) => String(from + i));
const claimsOver = (threshold: number, independent = false): FeeCondition => ({
  trigger: independent ? "independent_claims_over" : "claims_over",
  threshold,
  per_unit: true,
  description: `Per ${independent ? "independent claim" : "claim"} over ${threshold}.`,
});
const sizeFee: FeeCondition = {
  trigger: "sheets_over",
  threshold: 100,
  per_unit: true,
  description: "Per additional 50 sheets (or fraction) over 100.",
};
const paper: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description: "Applies when the application is filed on paper.",
};
const grace: FeeCondition = {
  trigger: "late_days",
  threshold: 0,
  per_unit: false,
  description: "Paid in the six-month grace period after the due date.",
};
const maintenanceNote = (due: string, year: number) =>
  `Due ${due} years after grant; stored as year ${year}.`;
const multipleDependent =
  "Charged once per application containing a multiple dependent claim.";

/**
 * Patent fee codes keyed by the large-entity code (or the only code). Codes
 * without a code in the source are keyed by their 37 CFR paragraph. Routes:
 * `design` rows go to the design schedule only, `both` to both schedules,
 * `plant` rows are dropped (no plant schedule), the rest are utility and
 * shared procedural fees in the patent schedule.
 */
const PATENT_RULES: Record<string, CodeRule> = Object.fromEntries([
  // Application filing fees
  ...rules(["1011", "4011", "1005", "1631"], { category: "filing" }),
  ...rules(["1012", "1017", "1781"], { category: "filing", route: "design" }),
  ...rules(["1013", "1083", "1113", "1313", "1503", "8003"], {
    category: "other",
    route: "plant",
  }),
  ["1014", { category: "reissue" }],
  ["1019", { category: "reissue", route: "design" }],
  ...rules(["1051", "1052", "1617", "1627"], { category: "late_fee" }),
  ...rules(["1201", "1204", "1614", "1821"], {
    category: "excess_claims",
    condition: claimsOver(3, true),
  }),
  ...rules(["1202", "1205", "1615", "1822"], {
    category: "excess_claims",
    condition: claimsOver(20),
  }),
  ...rules(["1203", "1616"], {
    category: "excess_claims",
    notes: multipleDependent,
  }),
  ...rules(["1081", "1084", "1085", "1681"], {
    category: "application_size",
    condition: sizeFee,
  }),
  [
    "1082",
    { category: "application_size", route: "design", condition: sizeFee },
  ],
  ...rules(["1090", "1690"], { category: "filing", condition: paper }),
  ...rules(["1054", "1055", "1056"], { category: "other" }),
  ...rules(["1053", "1618"], { category: "translation" }),
  ...rules(["1091", "1092"], { category: "application_size" }),
  // Search and examination
  ...rules(
    ["1111", "1641", "1642", "1632", "1602", "1604", "37 CFR 1.492(b)(1)"],
    { category: "search" },
  ),
  ["1112", { category: "search", route: "design" }],
  ["1114", { category: "search", route: "both" }],
  ...rules(
    ["1311", "1633", "1605", "1606", "1607", "1810", "37 CFR 1.492(c)(1)"],
    { category: "examination" },
  ),
  [
    "1817",
    {
      category: "examination",
      notes: "Track One prioritized examination request.",
    },
  ],
  ["1312", { category: "examination", route: "design" }],
  ["1314", { category: "examination", route: "both" }],
  // Issue and publication
  ...rules(["1501", "1511"], { category: "grant" }),
  ...rules(["1502", "1509"], { category: "grant", route: "design" }),
  ...rules(["1505", "1808", "1803", "37 CFR 1.18(d)(1)"], {
    category: "publication",
  }),
  // Extensions of time
  ...rules([...span(1251, 1255), ...span(1261, 1265)], {
    category: "extension",
  }),
  // Maintenance: due at 3.5, 7.5 and 11.5 years, stored as 4, 8 and 12.
  ...(
    [
      ["1551", "1554", "3.5", 4],
      ["1552", "1555", "7.5", 8],
      ["1553", "1556", "11.5", 12],
    ] as const
  ).flatMap(([fee, surcharge, due, year]): [string, CodeRule][] => [
    [fee, { category: "maintenance", year, notes: maintenanceNote(due, year) }],
    [
      surcharge,
      {
        category: "late_fee",
        year,
        condition: grace,
        notes: maintenanceNote(due, year),
      },
    ],
  ]),
  // Miscellaneous and post-issuance
  ...rules(["1801", "1820"], { category: "rce" }),
  ...rules(
    [
      "1819",
      "1830",
      "1818",
      "1806",
      "1807",
      "1809",
      "1832",
      "1833",
      "1834",
      "1811",
      "1816",
      "1831",
      "1812",
      "1814",
      "1826",
      "1827",
      "1621",
      "1705",
      "1706",
    ],
    { category: "other" },
  ),
  [
    "1828",
    {
      category: "excess_pages",
      condition: {
        trigger: "sheets_over",
        threshold: 20,
        per_unit: false,
        description: "Nonpatent document of 21 to 50 sheets.",
      },
    },
  ],
  [
    "1829",
    {
      category: "excess_pages",
      condition: {
        trigger: "sheets_over",
        threshold: 50,
        per_unit: true,
        description: "Per additional 50 sheets (or fraction) over 50.",
      },
    },
  ],
  // PTAB
  ["1405", { category: "ptab" }],
  ...rules(["1401", "1404", "1403", "1413", "37 CFR 41.20(b)(2)(i)"], {
    category: "appeal",
  }),
  ...rules(
    ["1406", "1414", "1408", "1416", "1412", "1411", "1418"].concat(
      span(1419, 1421),
    ),
    { category: "trial" },
  ),
  ...rules(["1407", "1415", "1409", "1417"], {
    category: "trial",
    condition: claimsOver(20),
  }),
  // Petitions
  ...rules(
    [
      "1462",
      "1463",
      "1466",
      "1467",
      "1464",
      "1453",
      "1468",
      "1454",
      "1469",
      "1628",
      "1455",
      "1456",
      "1824",
      "1457",
      "1458",
      "1459",
      "1465",
      "1558",
      "1560",
    ],
    { category: "petition" },
  ),
  ...rules(["1783", "1784", "1785"], { category: "petition", route: "design" }),
  // PCT fees collected for the International Bureau and foreign ISAs
  ...rules(["1601", "1701", "1710", "1702"], { category: "filing" }),
  [
    "1703",
    {
      category: "excess_pages",
      condition: {
        trigger: "pages_over",
        threshold: 30,
        per_unit: true,
        description: "Per page over 30.",
      },
    },
  ],
  ...rules(["1704", "1709", "1712", "1715", "1716", "1717", "1718"], {
    category: "search",
  }),
  // Service fees
  ...rules(
    [
      "8001",
      "8005",
      "8007",
      "8051",
      "8010",
      "8052",
      "8013",
      "8014",
      "8017",
      "8020",
      "8022",
      "8026",
      "8053",
      "8054",
    ],
    { category: "other" },
  ),
  ...rules(["8021", "37 CFR 1.21(h)(1)"], { category: "transfer" }),
]);

/** Trademark codes keyed by the electronic code (paper code when there is none); combined filings join codes with "+". */
const TRADEMARK_RULES: Record<string, CodeRule> = Object.fromEntries([
  ...rules(["6001", "7017", "7018", "7019", "7020"], { category: "filing" }),
  ...rules(["7931", "7933", "7901", "7902", "7907", "7903", "7904"], {
    category: "madrid",
  }),
  ...rules(["7002", "7003"], { category: "statement_of_use" }),
  ...rules(
    ["7004", "7016", "7015", "7407", "7404", "7405"].concat([
      "37 CFR 2.6(a)(18)(iii)",
      "37 CFR 2.102(c)(1)(i)",
    ]),
    { category: "extension" },
  ),
  ...rules(["7005", "7010", "7011", "7014"], { category: "petition" }),
  ...rules(["7201", "7932", "7201+7205"], { category: "renewal", year: 10 }),
  ...rules(["7203", "7201+7203+7205+7206"], {
    category: "late_fee",
    year: 10,
    condition: {
      trigger: "late_days",
      threshold: 0,
      per_unit: false,
      description: "Renewal filed in the six-month grace period.",
    },
  }),
  ...rules(["7205", "7905", "7205+7208", "7205+7206+7208", "7905+7208"], {
    category: "declaration_of_use",
  }),
  ["7905+7906+7208", { category: "declaration_of_use" }],
  ...rules(["7206", "7906"], { category: "late_fee" }),
  ...rules(
    [
      "7006",
      "7204",
      "7207",
      "7208",
      "7210",
      "7211",
      "7212",
      "7213",
      "7214",
      "7012",
      "7013",
      "7408",
      "7908",
      "37 CFR 2.6(a)(11)(iii)",
      "8501",
      "8503",
      "8504",
      "8507",
      "8508",
      "8513",
      "8514",
      "8534",
      "8533",
    ],
    { category: "other" },
  ),
  ...rules(["8521", "8522"], { category: "transfer" }),
  ["7401", { category: "cancellation" }],
  ["7402", { category: "opposition" }],
  ...rules(["7403", "7406"], { category: "appeal" }),
]);

/** Fees the page states only as "variable" or "paid to WIPO"; omitted, and named in the notes. */
const VARIABLE_CODES = new Set([
  "1619",
  "1782",
  "7951",
  "7952",
  "7953",
  "7954",
]);
const PATENT_TABLES = [
  "Patent application filing fees",
  "Patent search fees",
  "Patent examination fees",
  "Patent issue and publication fees",
  "Patent extension of time fees",
  "Patent maintenance fees",
  "Miscellaneous patent fees",
  "Post issuance fees",
  "Patent trial and appeal fees",
  "Patent petition fees",
  "PCT fees - national stage",
  "PCT fees - international stage",
  "PCT fees to foreign offices",
  "Hague - international design application fees",
  "Patent service fees",
];
const TRADEMARK_TABLES = [
  "Trademark application-related fees",
  "Trademark petition and letter of protest fees",
  "Trademark post registration fees",
  "Trademark Trial and Appeal Board (TTAB) fees",
  "Trademark Madrid Protocol fees",
  "Trademark service fees",
];
/** Practitioner enrollment, penalties, Fastener Quality Act and general service fees are not IP-right fees. */
const SKIPPED_TABLES = [
  "Patent enrollment fees",
  "Patent penalty fines",
  "Fastener Quality Act fees",
  "General service fees",
];
const PATENT_HEADER = [
  "Fee code",
  "37 CFR §",
  "Description",
  "Fee",
  "Small entity fee",
  "Micro entity fee",
];
const TRADEMARK_HEADER = [
  "37 CFR §",
  "Description",
  "Fee amount",
  "Fee code",
  "Fee amount",
  "Fee code",
];
const TIERS = ["large", "small", "micro"] as const;
const CREDIT = /, less any amount previously paid$/;

const squash = (value: string | null | undefined) =>
  (value ?? "").replace(/\s+/g, " ").trim();
/** Split a trailing footnote marker ("344.00*", "4011†") from a cell. */
function marked(cell: string): [string, string] {
  const match = /^(.*?)\s*([*†]+)$/.exec(cell);
  return match ? [match[1] as string, match[2] as string] : [cell, ""];
}

interface Row {
  code: string;
  rule: CodeRule | undefined;
  label: string;
  cfr: string;
  amount: string;
  tier: EntityTier;
  condition: FeeCondition | null;
  notes: string[];
}
interface Page {
  effectiveDate: string;
  revisedDate: string | null;
  patent: Row[];
  trademark: Row[];
}

function tables(html: string) {
  const document = parseHTML(html).document as unknown as Document;
  const text = squash(document.body?.textContent);
  const header =
    /Effective ([A-Z][a-z]+ \d{1,2}, \d{4})(?: \(Last revised ([A-Z][a-z]+ \d{1,2}, \d{4})\))?/.exec(
      text,
    );
  if (!header) throw invalid("the effective-date header was not found.");
  const found = Array.from(document.querySelectorAll("table")).map((table) => {
    const heads = Array.from(table.querySelectorAll("thead th")).map((th) =>
      squash(th.textContent),
    );
    const caption = marked(heads[0] ?? "")[0];
    const rows = Array.from(table.querySelectorAll("tbody tr")).map((tr) =>
      Array.from(tr.querySelectorAll("td")).map((td) => squash(td.textContent)),
    );
    return { caption, heads, rows };
  });
  const known = [...PATENT_TABLES, ...TRADEMARK_TABLES, ...SKIPPED_TABLES];
  const unknown = found.filter((table) => !known.includes(table.caption));
  if (unknown.length)
    throw invalid(
      `unrecognized sections: ${unknown.map((table) => table.caption || "(no caption)").join(", ")}.`,
    );
  const missing = known.filter(
    (caption) => !found.some((table) => table.caption === caption),
  );
  if (missing.length) throw invalid(`missing sections: ${missing.join(", ")}.`);
  return {
    effectiveDate: isoDate(header[1] as string),
    revisedDate: header[2] ? isoDate(header[2]) : null,
    found,
  };
}

function footnotes(rows: string[][]): Map<string, string> {
  const notes = new Map<string, string>();
  for (const row of rows) {
    const match =
      row.length === 1 ? /^([*†]+)\s*(.+)$/.exec(row[0] ?? "") : null;
    if (match) notes.set(match[1] as string, match[2] as string);
  }
  return notes;
}

function patentRows(caption: string, rows: string[][]): Row[] {
  const notes = footnotes(rows);
  const out: Row[] = [];
  for (const cells of rows) {
    if (cells.length === 1 && /^[*†]/.test(cells[0] ?? "")) continue;
    if (cells.length !== 6)
      throw invalid(`a ${caption} row has ${cells.length} cells.`);
    const [codeMarked, cfr, labelMarked, ...amountCells] = cells as [
      string,
      string,
      string,
      string,
      string,
      string,
    ];
    const [codeCell, codeMark] = marked(codeMarked);
    const [label, labelMark] = marked(labelMarked);
    const rowNotes = [notes.get(codeMark), notes.get(labelMark)].filter(
      (note): note is string => Boolean(note),
    );
    const codes = /^n\/a$/i.test(codeCell) ? [] : codeCell.split("/");
    if (codes.some((code) => VARIABLE_CODES.has(code))) continue;
    if (codes.length > 3 || codes.some((code) => !/^\d{4}$/.test(code)))
      throw invalid(`unrecognized fee code ${codeCell.slice(0, 30)}.`);
    const amounts = amountCells.map((cell) => {
      // The IDS size fees (1.17(v)) are cumulative: "500.00, less any amount previously paid".
      const [value, mark] = marked(cell.replace(CREDIT, ""));
      return {
        amount: parseUsdAmount(value),
        note: CREDIT.test(cell)
          ? "Less any IDS size fee previously paid in the application."
          : notes.get(mark),
      };
    });
    const key = codes[0] ?? `37 CFR ${cfr}`;
    const base = { rule: PATENT_RULES[key], label, cfr, condition: null };
    const present = amounts.flatMap((entry, index) =>
      entry.amount === null ? [] : [{ ...entry, tier: TIERS[index] }],
    );
    if (codes.length >= 2) {
      amounts.forEach((entry, index) => {
        const code = codes[index];
        if (entry.amount === null) return;
        if (!code)
          throw invalid(`${codeCell} has no code for the ${TIERS[index]} fee.`);
        out.push({
          ...base,
          code,
          amount: entry.amount,
          tier: TIERS[index] as EntityTier,
          notes: [...rowNotes, ...(entry.note ? [entry.note] : [])],
        });
      });
      continue;
    }
    const [only] = present;
    if (!only) throw invalid(`${key} has no amount.`);
    // One code: a single-tier fee (4011, small entities only) or one fee for everyone.
    const tier: EntityTier =
      present.length === 1 && only.tier !== "large"
        ? (only.tier as EntityTier)
        : "none";
    if (
      tier === "none" &&
      present.some((entry) => entry.amount !== only.amount)
    )
      throw invalid(`${key} has one code but different tier amounts.`);
    out.push({
      ...base,
      code: key,
      amount: only.amount as string,
      tier,
      notes: [
        ...rowNotes,
        ...present.flatMap((entry) => (entry.note ? [entry.note] : [])),
      ],
    });
  }
  return out;
}

const tmCode = (cell: string) =>
  /^n\/a$/i.test(cell) ? null : cell.split(/\s*,\s*/).join("+");

function trademarkRows(caption: string, rows: string[][]): Row[] {
  const out: Row[] = [];
  for (const cells of rows) {
    if (cells.some((cell) => VARIABLE_CODES.has(cell))) continue;
    if (cells.length !== 6)
      throw invalid(`a ${caption} row has ${cells.length} cells.`);
    const [cfr, label, eFee, eCell, pFee, pCell] = cells as [
      string,
      string,
      string,
      string,
      string,
      string,
    ];
    const eCode = tmCode(eCell);
    const pCode = tmCode(pCell);
    if (
      [eCode, pCode].some(
        (code) => code !== null && !/^\d{4}(?:\+\d{4})*$/.test(code),
      )
    )
      throw invalid(`unrecognized fee code ${eCell} / ${pCell}.`);
    const electronic = parseUsdAmount(eFee);
    const paperAmount = parseUsdAmount(pFee);
    const key = eCode ?? pCode ?? `37 CFR ${cfr}`;
    const rule = TRADEMARK_RULES[key];
    const perClass: FeeCondition | null = /\bper class\b/.test(label)
      ? {
          trigger: "classes_over",
          threshold: 0,
          per_unit: true,
          description: "Per class, including the first.",
        }
      : null;
    const base = { rule, cfr, tier: "none" as const, notes: [] };
    const sameFee =
      eCode !== null && eCode === pCode && electronic === paperAmount;
    if (electronic !== null) {
      if (eCode === null && electronic !== "0.00")
        throw invalid(`${label.slice(0, 40)} has an amount but no code.`);
      out.push({
        ...base,
        code: eCode ?? key,
        label,
        amount: electronic,
        condition: rule?.condition ?? perClass,
      });
    }
    if (paperAmount !== null && !sameFee) {
      if (pCode === null)
        throw invalid(`${label.slice(0, 40)} has a paper amount but no code.`);
      out.push({
        ...base,
        code: pCode,
        label: `${label} (paper)`,
        amount: paperAmount,
        condition: {
          ...paper,
          description: "Applies when the filing is made on paper.",
        },
      });
    }
  }
  return out;
}

function parsePage(html: string): Page {
  const { effectiveDate, revisedDate, found } = tables(html);
  const patent: Row[] = [];
  const trademark: Row[] = [];
  for (const table of found) {
    if (PATENT_TABLES.includes(table.caption)) {
      if (table.heads.slice(2).join("|") !== PATENT_HEADER.join("|"))
        throw invalid(`${table.caption} columns changed.`);
      patent.push(...patentRows(table.caption, table.rows));
    } else if (TRADEMARK_TABLES.includes(table.caption)) {
      if (table.heads.slice(3).join("|") !== TRADEMARK_HEADER.join("|"))
        throw invalid(`${table.caption} columns changed.`);
      trademark.push(...trademarkRows(table.caption, table.rows));
    }
  }
  return { effectiveDate, revisedDate, patent, trademark };
}

function item(row: Row, right: "patent" | "design" | "trademark"): FeeItem {
  const notes = [
    row.cfr ? `37 CFR ${row.cfr}.` : null,
    row.rule?.notes,
    ...row.notes,
  ].filter(Boolean);
  return {
    code: row.code,
    label: row.label,
    category: row.rule?.category ?? "other",
    rights: [right],
    amount: row.amount,
    currency: "USD",
    tier: row.tier,
    year: row.rule?.year ?? null,
    condition: row.condition ?? row.rule?.condition ?? null,
    source_url: USPTO_FEES_URL,
    notes: notes.join(" ") || null,
  };
}
/** Drop exact repeats (1628 appears under both petitions and PCT). */
function unique(fees: FeeItem[]): FeeItem[] {
  const seen = new Set<string>();
  return fees.filter((fee) => {
    const key = [fee.code, fee.tier, fee.amount, fee.label].join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
function recurringCoverage(
  fees: FeeItem[],
  category: "maintenance" | "renewal",
  years: number[],
  notes: string,
): RecurringFeeCoverage {
  const present = new Set(
    fees.filter((fee) => fee.category === category).map((fee) => fee.year),
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

const OMITTED = `Fees stated only as variable or paid to WIPO (${[...VARIABLE_CODES].join(", ")}) are omitted.`;

/** Fetches the USPTO fee schedule page and projects the patent, design and trademark schedules. */
export class UsptoFeesClient {
  private readonly http: GenericHttpTransport;
  private pending: Promise<
    Page & { provenance: FeeSchedule["provenance"] }
  > | null = null;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.uspto.gov",
      sourceName: USPTO_FEES_SOURCE,
      headers: { accept: "text/html" },
    });
  }
  /** One page fetch serves concurrent schedule requests (listSchedules). */
  private page(options: TransportRequestOptions) {
    this.pending ??= (async () => {
      const result = await this.http.text("GET", PAGE_PATH, options);
      const page = parsePage(result.data);
      const retrieved = result.provenance.retrieved_at.slice(0, 10);
      const status = [
        page.effectiveDate > retrieved
          ? `scheduled to take effect ${page.effectiveDate}`
          : `effective ${page.effectiveDate}`,
        page.revisedDate ? `page last revised ${page.revisedDate}` : null,
      ]
        .filter(Boolean)
        .join("; ");
      return {
        ...page,
        provenance: {
          ...result.provenance,
          as_of_status: status,
          effective_date: page.effectiveDate,
        },
      };
    })().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }
  private schedule(
    right: "patent" | "design" | "trademark",
    page: Awaited<ReturnType<UsptoFeesClient["page"]>>,
    rows: Row[],
    extra: {
      statutory_basis: string;
      coverage: RecurringFeeCoverage;
      notes: string;
      unmapped: string[];
    },
  ): FeeSchedule {
    const fees = unique(rows.map((row) => item(row, right)));
    if (!fees.length) throw invalid(`no ${right} fees parsed.`);
    const revised = page.revisedDate
      ? ` The page was last revised ${page.revisedDate}; the effective date is the one the page states.`
      : "";
    return FeeScheduleSchema.parse({
      key: `US/USPTO/${right}`,
      jurisdiction: "US",
      issuing_body: "United States Patent and Trademark Office",
      office_code: "USPTO",
      right,
      currency: "USD",
      effective_date: page.effectiveDate,
      source_url: USPTO_FEES_URL,
      statutory_basis: extra.statutory_basis,
      fees,
      recurring_fee_coverage: extra.coverage,
      unmapped_codes: extra.unmapped,
      notes: `${extra.notes}${revised}`,
      provenance: page.provenance,
    });
  }
  /** Utility patent fees and the procedural, PCT and service fees shared by all applications. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page(options);
    const rows = page.patent.filter((row) => {
      const route = row.rule?.route ?? "patent";
      return route === "patent" || route === "both";
    });
    const fees = rows.map((row) => item(row, "patent"));
    return this.schedule("patent", page, rows, {
      statutory_basis:
        "35 U.S.C. 41 and 376; 37 CFR 1.16-1.21, 1.445, 1.482, 1.492, 41.20 and 42.15.",
      coverage: recurringCoverage(
        fees,
        "maintenance",
        [4, 8, 12],
        "Maintenance fees at 3.5, 7.5 and 11.5 years present (years 4, 8 and 12).",
      ),
      unmapped: [
        ...new Set(rows.filter((row) => !row.rule).map((row) => row.code)),
      ],
      notes: `Tiers: large, small and micro entity, one fee code each (1xxx/2xxx/3xxx); 4011 is the small-entity electronic filing fee. Maintenance fees are due 3.5, 7.5 and 11.5 years after grant and are stored as years 4, 8 and 12. Design-specific fees are in the USPTO design schedule; plant-specific fees are omitted. ${OMITTED}`,
    });
  }
  /** Fees specific to design applications and patents, including Hague international design applications. */
  async getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page(options);
    const rows = page.patent.filter(
      (row) => row.rule?.route === "design" || row.rule?.route === "both",
    );
    return this.schedule("design", page, rows, {
      statutory_basis: "35 U.S.C. 41; 37 CFR 1.16-1.18 and 1.1031.",
      coverage: {
        status: "not_applicable",
        missing_categories: [],
        missing_years: [],
        notes: "Design patents carry no maintenance fees (35 U.S.C. 41(b)(1)).",
      },
      unmapped: [],
      notes: `Only fees specific to design applications. Extensions, petitions, appeals and other procedural fees that apply to every application are in the USPTO patent schedule. ${OMITTED}`,
    });
  }
  /** Trademark fees: electronic and paper filing, post-registration, TTAB and Madrid Protocol. */
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const page = await this.page(options);
    const fees = page.trademark.map((row) => item(row, "trademark"));
    return this.schedule("trademark", page, page.trademark, {
      statutory_basis: "15 U.S.C. 1113; 37 CFR 2.6 and 7.6.",
      coverage: recurringCoverage(
        fees,
        "renewal",
        [10],
        "Registrations renew every 10 years; year 10 stands for each renewal.",
      ),
      unmapped: [
        ...new Set(
          page.trademark.filter((row) => !row.rule).map((row) => row.code),
        ),
      ],
      notes: `No entity tiers. Each fee has an electronic code (7xxx) and, where paper filing is allowed, a paper code (6xxx) carrying a paper_filing condition. Combined filings (for example Section 8 and 9) list their component codes joined by "+". ${OMITTED}`,
    });
  }
}

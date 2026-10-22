import { CachedClient } from "../cache/client.js";
import { pdfPageItems } from "../runtime/pdf.js";
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
 * The Office of the Controller General of Patents, Designs and Trade Marks
 * publishes patent fees as First Schedule to the Patents Rules, 2003, in a
 * PDF table with seven columns: entry number, what the fee is for, form
 * number, then four rates in rupees. The rate columns are e-filing (natural
 * persons, startups, small entities and educational institutions; then
 * others) followed by physical filing (the same two groups). Entries with
 * sub-items ((i), (ii), ...) carry a rate row per sub-item.
 */
export const IPINDIA_FEES_SOURCE = "IPO India First Schedule (Patents Rules)";
export const IPINDIA_FEES_PDF_URL =
  "https://ipindia.gov.in/frontend/pdf/forms_and_official_fees/Schedule_1.pdf";
const PDF_PATH = "/frontend/pdf/forms_and_official_fees/Schedule_1.pdf";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`IPO India Schedule 1: ${message}`, 200, "INVALID_RESPONSE");

/** Rate columns in page order. */
const RATE_COLUMNS = [
  { tier: "small", mode: "efile" },
  { tier: "large", mode: "efile" },
  { tier: "small", mode: "paper" },
  { tier: "large", mode: "paper" },
] as const;

/** A rate cell: an amount with trailing qualifiers, or a stated absence. */
export type RateCell =
  | { kind: "fee"; amount: string; extra: string }
  | { kind: "no_fee" | "not_allowed" | "not_applicable" | "as_applicable" };

const ROMAN = /^\(?([ivx]+)\)\s*/;
const RATE_START =
  /^(?:\([ivx]+\)\s*)?(?:\d[\d,]*(?:\s|$)|No\s*fee|Not\s+allowed|Not\s+applicable|As\s+Applicable)/i;

/** "(ii) 1600" -> fee 1600; "No fee" -> no_fee; "8,000 (In respect of each patent)" -> fee 8000 with extra. */
export function parseRateCell(raw: string): RateCell {
  const text = raw.replace(ROMAN, "").replace(/\s+/g, " ").trim();
  if (/^No\s*fee$/i.test(text)) return { kind: "no_fee" };
  if (/^Not allowed$/i.test(text)) return { kind: "not_allowed" };
  if (/^Not applicable$/i.test(text)) return { kind: "not_applicable" };
  if (/^As Applicable$/i.test(text)) return { kind: "as_applicable" };
  const match = /^(\d{1,3}(?:,\d{3})+|\d+)(?:\s+(.*))?$/.exec(text);
  if (!match) throw invalid(`unrecognized rate ${text.slice(0, 40)}`);
  return {
    kind: "fee",
    amount: (match[1] as string).replaceAll(",", ""),
    extra: match[2] ?? "",
  };
}

interface Line {
  /** Increases down the document, across pages. */
  depth: number;
  column: number;
  text: string;
}
/** Group positioned text into per-column lines. Columns: 1 entry, 2 description, 3 form, 4-7 rates. */
function lines(pages: Awaited<ReturnType<typeof pdfPageItems>>): Line[] {
  const first = pages[0] ?? [];
  // Column edges come from the header on page 1; the table keeps them on every page.
  const headerY = first.find((item) => item.str.trim() === "Natural")?.y;
  const edges = first
    .filter(
      (item) =>
        headerY !== undefined &&
        Math.abs(item.y - headerY) < 2 &&
        /^(Natural|Other\(s\),)$/.test(item.str.trim()),
    )
    .map((item) => item.x - 6)
    .sort((a, b) => a - b);
  const formX = first.find(
    (item) => item.str.trim() === "Number" && item.x > 150,
  )?.x;
  if (edges.length !== 4 || formX === undefined)
    throw invalid("the column header was not found.");
  const column = (x: number) => {
    if (x < 100) return 1;
    if (x < formX - 3) return 2;
    if (x < (edges[0] as number)) return 3;
    return 4 + edges.filter((edge) => x >= edge).length - 1;
  };
  const out: Line[] = [];
  pages.forEach((items, page) => {
    const pageLines: {
      y: number;
      column: number;
      parts: { x: number; s: string }[];
    }[] = [];
    for (const item of items) {
      const s = item.str.trim();
      if (!s) continue;
      const col = column(item.x);
      const line = pageLines.find(
        (l) => l.column === col && Math.abs(l.y - item.y) <= 3,
      );
      if (line) line.parts.push({ x: item.x, s });
      else
        pageLines.push({ y: item.y, column: col, parts: [{ x: item.x, s }] });
    }
    for (const line of pageLines)
      out.push({
        depth: page * 1000 + (1000 - line.y),
        column: line.column,
        text: line.parts
          .sort((a, b) => a.x - b.x)
          .map((part) => part.s)
          .join(" ")
          .replace(/\s+/g, " "),
      });
  });
  return out.sort((a, b) => a.depth - b.depth || a.column - b.column);
}

export interface ScheduleRow {
  entry: number;
  sub: string | null;
  heading: string;
  /** For rate-labelled sub-items ("(ii) 320"), the description of the entry's first row. */
  parent: string;
  description: string;
  notes: string[];
  cells: RateCell[];
  cellNotes: string[];
}

const tidy = (text: string) =>
  text
    .replace(/\s\*(?=\s|$)/g, "")
    .replace(/(\w) - (\w)/g, "$1-$2")
    .replace(/\s+/g, " ")
    .trim();

/** Rebuild the table: entries by number, one row per line of four rates. */
export function scheduleRows(pages: Awaited<ReturnType<typeof pdfPageItems>>): {
  rows: ScheduleRow[];
  withoutRates: number[];
} {
  const all = lines(pages);
  const markers = all
    .filter((line) => line.column === 1 && /^\d+\.$/.test(line.text))
    .map((line) => ({
      entry: Number.parseInt(line.text, 10),
      depth: line.depth,
    }));
  if (!markers.length) throw invalid("no numbered entries found.");
  markers.forEach((marker, index) => {
    if (marker.entry !== index + 1)
      throw invalid(`entry ${index + 1} is missing or out of order.`);
  });
  const at = (column: number, depth: number) =>
    all.find(
      (line) => line.column === column && Math.abs(line.depth - depth) <= 3,
    );
  const rows: ScheduleRow[] = [];
  const withoutRates: number[] = [];
  markers.forEach((marker, index) => {
    const end = markers[index + 1]?.depth ?? Number.POSITIVE_INFINITY;
    const inEntry = all.filter(
      (line) => line.depth >= marker.depth - 3 && line.depth < end - 3,
    );
    // A rate line has a rate token at the same height in all four rate columns.
    const rateLines = inEntry
      .filter((line) => line.column === 4 && RATE_START.test(line.text))
      .filter((line) =>
        [5, 6, 7].every((column) =>
          RATE_START.test(at(column, line.depth)?.text ?? ""),
        ),
      )
      .map((line) => line.depth);
    if (!rateLines.length) {
      withoutRates.push(marker.entry);
      return;
    }
    const description = inEntry.filter((line) => line.column === 2);
    const labels = rateLines.map(
      (depth) => ROMAN.exec(at(4, depth)?.text ?? "")?.[1] ?? null,
    );
    // Description regions start at the matching "(ii)" line for labelled rates, else at the rate line.
    const starts: number[] = [];
    rateLines.forEach((depth, i) => {
      const label = labels[i];
      const labelled = label
        ? description.find(
            (line) =>
              line.depth >= (starts[i - 1] ?? marker.depth - 3) &&
              new RegExp(`^\\(?${label}\\)\\s`).test(line.text),
          )
        : undefined;
      starts.push(labelled ? labelled.depth : depth - 3);
    });
    const heading = tidy(
      description
        .filter((line) => line.depth < (starts[0] as number))
        .map((line) => line.text)
        .join(" "),
    );
    const unlabelled = labels.filter((label) => label === null).length;
    let first = "";
    rateLines.forEach((depth, i) => {
      const regionEnd = starts[i + 1] ?? end - 3;
      const text: string[] = [];
      const notes: string[] = [];
      for (const line of description) {
        if (line.depth < (starts[i] as number) || line.depth >= regionEnd)
          continue;
        if (line.text === "*") continue;
        if (notes.length || /^(Note:|\*\S)/.test(line.text))
          notes.push(line.text);
        else text.push(line.text);
      }
      const rateEnd = rateLines[i + 1] ?? end;
      const cells: RateCell[] = [];
      const cellNotes: string[] = [];
      for (const column of [4, 5, 6, 7]) {
        const cellText = inEntry
          .filter(
            (line) =>
              line.column === column &&
              line.depth >= depth - 3 &&
              line.depth < rateEnd - 3,
          )
          .map((line) => line.text)
          .join(" ");
        const cell = parseRateCell(cellText);
        cells.push(cell);
        if (cell.kind === "fee" && cell.extra) cellNotes.push(tidy(cell.extra));
      }
      const own = tidy(text.join(" "));
      if (i === 0) first = own;
      const descLabel =
        ROMAN.exec(own)?.[1] ??
        ROMAN.exec(at(1, depth)?.text ?? "")?.[1] ??
        null;
      rows.push({
        entry: marker.entry,
        sub:
          labels[i] ??
          descLabel ??
          (rateLines.length > 1 && unlabelled > 1 ? String(i + 1) : null),
        heading,
        parent: i > 0 && labels[i] ? first : "",
        description: own,
        notes: notes.length
          ? [tidy(notes.join(" ")).replace(/^(Note:\s*|\*)/, "")]
          : [],
        cells,
        cellNotes,
      });
    });
  });
  return { rows, withoutRates };
}

interface EntryRule {
  match: RegExp;
  category: FeeCategory;
}
/** Statutory entry numbers of the First Schedule, with the wording each must still match. */
const ENTRIES: Record<number, EntryRule> = {
  1: { match: /^On application for a patent/, category: "filing" },
  2: {
    match: /^On filing complete specification after provisional/,
    category: "filing",
  },
  3: { match: /^On filing a statement and undertaking/, category: "other" },
  4: { match: /request for extension of time/, category: "extension" },
  5: {
    match: /^On filing a declaration as to inventorship/,
    category: "other",
  },
  6: { match: /^On application for postdating/, category: "other" },
  7: { match: /^On application for deletion of reference/, category: "other" },
  8: { match: /On claim under section 20\(1\)/, category: "other" },
  9: {
    match: /notice of opposition to grant of patent/,
    category: "opposition",
  },
  10: { match: /^On giving notice that hearing/, category: "other" },
  11: { match: /^On application under section 28\(2\)/, category: "other" },
  12: { match: /^Certificate of inventorship/, category: "other" },
  13: { match: /^Request for publication/, category: "publication" },
  14: { match: /for amendment of patent/, category: "other" },
  15: { match: /^On application for directions/, category: "other" },
  16: { match: /^On request for grant of a patent/, category: "other" },
  17: {
    match: /^On request for converting a patent of addition/,
    category: "other",
  },
  18: {
    match: /^For renewal of a patent under section 53/,
    category: "renewal",
  },
  19: {
    match: /^On application for amendment of application/,
    category: "other",
  },
  20: {
    match: /^On notice of opposition to an application under sections 57\(4\)/,
    category: "opposition",
  },
  21: {
    match: /^On application for restoration of a patent/,
    category: "petition",
  },
  22: { match: /^Additional fee for restoration/, category: "petition" },
  23: { match: /^On notice of offer to surrender/, category: "other" },
  24: {
    match: /^On application for the entry in the register of patents/,
    category: "transfer",
  },
  25: {
    match: /^On application for alteration of an entry/,
    category: "other",
  },
  26: {
    match: /^On request for entry of an additional address/,
    category: "other",
  },
  27: { match: /^On application for compulsory licen/, category: "other" },
  28: { match: /^On request for examination/, category: "examination" },
  29: {
    match: /^On request for expedited or delayed examination/,
    category: "examination",
  },
  30: {
    match: /^Conversion of the request for examination/,
    category: "examination",
  },
  31: {
    match: /^On application for revocation of a patent/,
    category: "cancellation",
  },
  32: {
    match: /^On application for revision of terms and conditions of licence/,
    category: "other",
  },
  33: {
    match: /^On request for termination of compulsory licence/,
    category: "other",
  },
  39: {
    match: /^On a request for correction of clerical error/,
    category: "other",
  },
  40: {
    match: /^On application for review or setting aside/,
    category: "petition",
  },
  41: {
    match: /^On application for permission for applying patent outside India/,
    category: "other",
  },
  42: { match: /^On application for duplicate patent/, category: "other" },
  43: { match: /certified copies/, category: "other" },
  44: { match: /^For certifying office copies/, category: "other" },
  45: { match: /^On request for inspection of register/, category: "other" },
  46: { match: /^On request for information/, category: "other" },
  47: {
    match: /^On form of authorization of a patent agent/,
    category: "other",
  },
  48: {
    match: /^On petition not otherwise provided for/,
    category: "petition",
  },
  49: { match: /^For supplying of photocopies/, category: "other" },
  50: {
    match: /^Transmittal fee for international application\.$/,
    category: "other",
  },
  51: {
    match: /^Transmittal fee for international application \(for ePCT filing\)/,
    category: "other",
  },
  52: {
    match: /^For preparation of certified copy of priority document/,
    category: "other",
  },
  53: {
    match:
      /^For preparation of certified copy of priority document and e-transmission/,
    category: "other",
  },
  54: {
    match: /^On statement regarding working of a patented invention/,
    category: "other",
  },
  55: {
    match: /^To be submitted for claiming the status of a small entity/,
    category: "other",
  },
  56: {
    match: /^Application for withdrawing the application/,
    category: "other",
  },
  57: { match: /^Request for adjournment of hearing/, category: "other" },
  59: { match: /^Grace period/, category: "other" },
};
/** Patent-agent register fees (entries 34-38) are not fees on a patent right and are left out, as the USPTO enrollment fees are. */
const AGENT_ENTRIES = new Set([34, 35, 36, 37, 38]);

const PAPER: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description: "Applies to physical (paper) filing.",
};

/** Sub-item surcharges of entries 1 and 2, read from their wording. */
function surcharge(
  description: string,
): { category: FeeCategory; condition: FeeCondition } | null {
  const sheets = /for each sheet of specification in addition to (\d+)/.exec(
    description,
  );
  if (sheets)
    return {
      category: "excess_pages",
      condition: {
        trigger: "pages_over",
        threshold: Number(sheets[1]),
        per_unit: true,
        description: `Per sheet of specification over ${sheets[1]}, excluding sequence listings.`,
      },
    };
  const claims = /for each claim in addition to (\d+)/.exec(description);
  if (claims)
    return {
      category: "excess_claims",
      condition: {
        trigger: "claims_over",
        threshold: Number(claims[1]),
        per_unit: true,
        description: `Per claim over ${claims[1]}.`,
      },
    };
  if (/for each page of sequence listing/.test(description))
    return {
      category: "excess_pages",
      condition: {
        trigger: "pages_over",
        threshold: 0,
        per_unit: true,
        description: "Per page of sequence listing, up to the stated maximum.",
      },
    };
  return null;
}

const ABSENT = {
  not_allowed: "not allowed",
  not_applicable: "not applicable",
  no_fee: "no fee",
  as_applicable: "as applicable",
} as const;

function build(rows: ScheduleRow[]): { fees: FeeItem[]; unmapped: string[] } {
  const fees: FeeItem[] = [];
  const unmapped = new Set<string>();
  const codes = new Set<string>();
  const entryText = new Map<number, string>();
  const entryNotes = new Map<number, string[]>();
  for (const row of rows) {
    if (!entryText.has(row.entry))
      entryText.set(
        row.entry,
        [row.heading, row.description].filter(Boolean).join(" "),
      );
    entryNotes.set(row.entry, [
      ...(entryNotes.get(row.entry) ?? []),
      ...row.notes,
    ]);
  }
  const sentence = (text: string) => (/[.)]$/.test(text) ? text : `${text}.`);
  for (const row of rows) {
    if (AGENT_ENTRIES.has(row.entry)) continue;
    const rule = ENTRIES[row.entry];
    const label = [row.heading, row.parent, row.description]
      .filter(Boolean)
      .join(" ");
    const recognized =
      rule?.match.test(entryText.get(row.entry) ?? "") ?? false;
    let category: FeeCategory = recognized
      ? (rule?.category ?? "other")
      : "other";
    let condition: FeeCondition | null = null;
    let year: number | null = null;
    if (category === "renewal") {
      const match = /in respect of (?:the )?(\d+)(?:st|nd|rd|th) year/.exec(
        row.description,
      );
      if (!match) throw invalid(`renewal sub-item ${row.sub} has no year.`);
      year = Number(match[1]);
    } else if ((row.entry === 1 || row.entry === 2) && row.sub) {
      const extra = surcharge(row.description);
      if (!extra)
        throw invalid(
          `entry ${row.entry}(${row.sub}) is not a recognized surcharge.`,
        );
      ({ category, condition } = extra);
    }
    const base = `in-${row.entry}${year ? `-y${year}` : row.sub ? `-${row.sub}` : ""}`;
    if (!recognized) unmapped.add(base);
    // Paper rates are never below the e-filing rate for the same applicant group.
    for (const [efile, paper] of [
      [0, 2],
      [1, 3],
    ] as const) {
      const a = row.cells[efile];
      const b = row.cells[paper];
      if (
        a?.kind === "fee" &&
        b?.kind === "fee" &&
        Number(b.amount) < Number(a.amount)
      )
        throw invalid(
          `${base} physical-filing rate is below the e-filing rate.`,
        );
    }
    const absences = row.cells.flatMap((cell, i) => {
      const column = RATE_COLUMNS[i] as (typeof RATE_COLUMNS)[number];
      return cell.kind === "not_allowed" || cell.kind === "not_applicable"
        ? [
            `${column.mode === "paper" ? "Physical filing" : "E-filing"} for ${column.tier === "small" ? "natural persons, startups, small entities and educational institutions" : "other applicants"}: ${ABSENT[cell.kind]}.`,
          ]
        : [];
    });
    row.cells.forEach((cell, i) => {
      if (cell.kind !== "fee" && cell.kind !== "no_fee") return;
      const column = RATE_COLUMNS[i] as (typeof RATE_COLUMNS)[number];
      const code = `${base}-${column.tier}-${column.mode}`;
      if (codes.has(code)) throw invalid(`duplicate code ${code}.`);
      codes.add(code);
      const notes = [
        `Patents Rules 2003, First Schedule, entry ${row.entry}${row.sub ? `(${row.sub})` : ""}.`,
        cell.kind === "no_fee" ? "No fee." : null,
        cell.kind === "fee" && cell.extra ? sentence(tidy(cell.extra)) : null,
        ...(entryNotes.get(row.entry) ?? []).map(sentence),
        ...absences,
        recognized
          ? null
          : "Entry wording not recognized; categorized as other.",
      ].filter(Boolean);
      fees.push({
        code,
        label: `${label}${column.mode === "paper" ? " (physical filing)" : " (e-filing)"}`,
        category,
        rights: ["patent"],
        amount: cell.kind === "fee" ? cell.amount : "0",
        currency: "INR",
        tier: column.tier as EntityTier,
        year,
        condition: column.mode === "paper" ? PAPER : condition,
        source_url: IPINDIA_FEES_PDF_URL,
        notes: [
          ...notes,
          column.mode === "paper" && condition ? condition.description : null,
        ]
          .filter(Boolean)
          .join(" "),
      });
    });
  }
  return { fees, unmapped: [...unmapped] };
}

function coverage(fees: FeeItem[]): RecurringFeeCoverage {
  const present = new Set(
    fees.filter((fee) => fee.category === "renewal").map((fee) => fee.year),
  );
  const missing = Array.from({ length: 18 }, (_, i) => i + 3).filter(
    (year) => !present.has(year),
  );
  return missing.length
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
          "Renewal fees for years 3-20 present for both applicant groups and both filing modes.",
      };
}

/** Fetches the First Schedule PDF and projects the patent schedule. */
export class IpIndiaFeesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://ipindia.gov.in",
      sourceName: IPINDIA_FEES_SOURCE,
      cache: { name: "ipindia_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: { accept: "application/pdf", "user-agent": USER_AGENT },
    });
  }
  /** Every fee of the First Schedule except patent-agent register fees, by applicant group and filing mode. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const result = await this.http.bytes("GET", PDF_PATH, options);
    let pages: Awaited<ReturnType<typeof pdfPageItems>>;
    try {
      pages = await pdfPageItems(result.data);
    } catch {
      throw invalid("the response is not a readable PDF.");
    }
    const { rows, withoutRates } = scheduleRows(pages);
    const { fees, unmapped } = build(rows);
    if (!fees.length) throw invalid("no fees parsed.");
    const skipped = withoutRates.length
      ? ` Entries without rates (${withoutRates.join(", ")}; entry 58 is charged "as applicable") are omitted.`
      : "";
    return FeeScheduleSchema.parse({
      key: "IN/IPIN/patent",
      jurisdiction: "IN",
      issuing_body:
        "Office of the Controller General of Patents, Designs and Trade Marks (CGPDTM)",
      office_code: "IPIN",
      right: "patent",
      currency: "INR",
      effective_date: null,
      source_url: IPINDIA_FEES_PDF_URL,
      statutory_basis: "Patents Rules, 2003, First Schedule (as amended).",
      fees,
      recurring_fee_coverage: coverage(fees),
      unmapped_codes: unmapped,
      notes: `Each entry has four rates: e-filing and physical filing, each for natural persons, startups, small entities and educational institutions (tier small) and for other applicants (tier large). Physical-filing rows carry a paper_filing condition. Entries stated as "No fee" appear with amount 0. Codes are in-<entry>[-<sub-item>|-y<year>]-<tier>-<mode>. Patent-agent register fees (entries 34-38) are omitted.${skipped} The PDF states no effective date; it includes the certificate of inventorship (Form 8A) and grace-period (Form 31) fees introduced by the Patents (Amendment) Rules, 2024.`,
      provenance: {
        ...result.provenance,
        as_of_status: "effective date not published by the office",
        effective_date: null,
      },
    });
  }
}

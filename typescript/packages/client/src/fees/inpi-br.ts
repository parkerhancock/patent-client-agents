import { CachedClient } from "../cache/client.js";
import { type PdfTextItem, pdfPageItems } from "../runtime/pdf.js";
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
 * INPI Brazil publishes English fee tables as PDFs under
 * gov.br/inpi/en/costs-and-payment; the Portuguese tables sit behind a login.
 * Each table has four columns: code, service, amount and the discounted
 * amount (up to 60% off for individuals, small companies, cooperatives,
 * educational and research institutions, nonprofits and public bodies).
 * A code's cell can hold several priced lines (electronic and paper
 * filing, claim bands), and the code is printed at the cell's vertical
 * center, so rows are read by position.
 */
export const INPI_BR_FEES_SOURCE = "INPI Brazil schedule of fees";
const PATENT_PATH =
  "/inpi/en/costs-and-payment/TabelaPatentesinglsapsalteraesCGRECincpapelpct.pdf";
const TRADEMARK_PATH =
  "/inpi/en/costs-and-payment/schedule-of-fees-trademarks.pdf";
export const INPI_BR_PATENT_PDF_URL = `https://www.gov.br${PATENT_PATH}`;
export const INPI_BR_TM_PDF_URL = `https://www.gov.br${TRADEMARK_PATH}`;
export const INPI_BR_LANDING_URL =
  "https://www.gov.br/inpi/en/costs-and-payment";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`INPI Brazil fee table: ${message}`, 200, "INVALID_RESPONSE");

/** Brazilian notation: "1.595,00" -> "1595.00". */
export function parseBrlAmount(raw: string): string {
  const value = raw.trim();
  if (!/^\d{1,3}(?:\.\d{3})*,\d{2}$/.test(value))
    throw invalid(`unrecognized amount ${value.slice(0, 20)}`);
  return value.replaceAll(".", "").replace(",", ".");
}
const AMOUNT = /^(?:\d{1,3}(?:\.\d{3})*,\d{2}|No charge|Variable|Isento)$/;
const CODE = /^\d{3,4}(?:-\d)?$/;
const FURNITURE =
  /^(?:MINISTRY OF ECONOMY|NATIONAL INSTITUTE OF INDUSTRIAL PROPERTY|SCHEDULE OF FEES FOR SERVICES|Ordinance No\. 39|and INPI Resolution|9\/24\/2019, and INPI|PATENT-RELATED SERVICES|TRADEMARK-RELATED SERVICES|Code Service|Página \d)/;

interface Line {
  page: number;
  y: number;
  section: number;
  code: string | null;
  desc: string;
  amounts: string[];
  /** Prose in the amount column and in the discounted-amount column. */
  prose: [string, string];
}

/** Group positioned text into table lines, classifying each item by column. */
export function tableLines(pages: PdfTextItem[][]): Line[] {
  const lines: Line[] = [];
  let section = 0;
  // A page without a header row (a table's last page) keeps the previous columns.
  let codeLimit = Number.NaN;
  let split = Number.POSITIVE_INFINITY;
  pages.forEach((items, index) => {
    const header = (label: string) =>
      items.find((item) => item.str.trim() === label);
    const codeHeader = header("Code");
    const amountHeader = header("Amount (in R$)");
    const discountHeader = header("Discounted amount (*)");
    if (codeHeader && amountHeader) {
      codeLimit = codeHeader.x + 20;
      if (discountHeader) split = (amountHeader.x + discountHeader.x) / 2;
    } else if (Number.isNaN(codeLimit))
      throw invalid(`page ${index + 1} has no column header.`);
    const rows: { y: number; items: PdfTextItem[] }[] = [];
    for (const item of items) {
      if (!item.str.trim()) continue;
      const row = rows.find((r) => Math.abs(r.y - item.y) <= 2);
      if (row) row.items.push(item);
      else rows.push({ y: item.y, items: [item] });
    }
    for (const row of rows.sort((a, b) => b.y - a.y)) {
      const sorted = row.items.sort((a, b) => a.x - b.x);
      const text = sorted.map((item) => item.str.trim()).join(" ");
      if (FURNITURE.test(text)) continue;
      if (/^\(\*\)/.test(text)) return;
      const line: Line = {
        page: index + 1,
        y: row.y,
        section,
        code: null,
        desc: "",
        amounts: [],
        prose: ["", ""],
      };
      const desc: string[] = [];
      for (const item of sorted) {
        const value = item.str.trim();
        if (item.x < codeLimit && CODE.test(value) && !line.code)
          line.code = value;
        else if (item.x >= 290 && AMOUNT.test(value)) line.amounts.push(value);
        else if (item.x >= 290) {
          const column = item.x < split ? 0 : 1;
          line.prose[column] = `${line.prose[column]} ${value}`.trim();
        } else desc.push(value);
      }
      line.desc = desc.join(" ").replace(/\s+/g, " ");
      if (/^\([IVXL]+\)/.test(line.desc)) {
        section++;
        continue;
      }
      if (line.amounts.length > 2)
        throw invalid(`a line on page ${line.page} has more than two amounts.`);
      lines.push(line);
    }
  });
  return lines;
}

interface Row {
  code: string;
  label: string;
  /** The line's own text, without the heading, used for sibling suffixes. */
  own: string;
  amounts: string[];
  prose: [string, string];
}
/** Where a row's cell sits on the page, to judge whether the next line still belongs to it. */
interface Cell {
  row: Row;
  page: number;
  codeY: number;
  top: number;
  bottom: number;
}

const unbalanced = (text: string) =>
  (text.match(/\(/g) ?? []).length > (text.match(/\)/g) ?? []).length;
/**
 * A text line after a priced row continues that row when it starts in
 * lowercase, closes an open parenthesis, or moves the cell's middle closer
 * to its code (codes are printed at the vertical center of their cell).
 */
function continues(cell: Cell, line: Line) {
  if (/^[a-z(\d–]/.test(line.desc) || unbalanced(cell.row.label)) return true;
  if (cell.page !== line.page) return false;
  const without = Math.abs((cell.top + cell.bottom) / 2 - cell.codeY);
  const withLine = Math.abs((cell.top + line.y) / 2 - cell.codeY);
  return withLine + 0.5 < without;
}

/**
 * Turn lines into priced rows. A line with its own code owns its amounts;
 * otherwise the amounts go to the nearest code in the same section on the
 * same page whose line is bare or is itself a "- " sub-line.
 */
export function tableRows(lines: Line[]): Row[] {
  const anchors = lines.filter(
    (line) => line.code && (!line.amounts.length || line.desc.startsWith("- ")),
  );
  const anchorFor = (line: Line): Line => {
    if (line.code) return line;
    let best: Line | null = null;
    for (const anchor of anchors)
      if (
        anchor.page === line.page &&
        anchor.section === line.section &&
        (!best || Math.abs(anchor.y - line.y) < Math.abs(best.y - line.y))
      )
        best = anchor;
    if (!best)
      throw invalid(`no code for "${line.desc}" on page ${line.page}.`);
    return best;
  };
  const rows: Row[] = [];
  let title = "";
  let titleTop = 0;
  let titleOpen = false;
  let cell: Cell | null = null;
  let section = -1;
  for (const line of lines) {
    if (line.section !== section) {
      section = line.section;
      title = "";
      titleOpen = false;
      cell = null;
    }
    const sub = line.desc.startsWith("- ");
    const priced = line.amounts.length > 0;
    const prosed = Boolean(line.prose[0] || line.prose[1]);
    if (!priced && !line.desc && prosed && cell) {
      // Wrapped prose belongs to the sub-line above it.
      cell.row.prose = [
        `${cell.row.prose[0]} ${line.prose[0]}`.trim(),
        `${cell.row.prose[1]} ${line.prose[1]}`.trim(),
      ];
      continue;
    }
    if (priced || sub) {
      const own = line.desc;
      // Bare and "- " lines take the heading; so does any line while the heading is still open.
      const nested = !own || sub || titleOpen;
      const anchor = anchorFor(line);
      const row: Row = {
        code: anchor.code as string,
        label: nested && title ? `${title} ${own}`.trim() : own || title,
        own: own.replace(/^- /, ""),
        amounts: line.amounts,
        prose: line.prose,
      };
      rows.push(row);
      cell = {
        row,
        page: line.page,
        codeY: anchor.y,
        top: titleOpen ? titleTop : line.y,
        bottom: line.y,
      };
      titleOpen = false;
      continue;
    }
    if (!line.desc) continue;
    if (cell && continues(cell, line)) {
      cell.row.label = `${cell.row.label} ${line.desc}`;
      cell.bottom = line.y;
      if (!cell.row.own) title = `${title} ${line.desc}`;
      continue;
    }
    if (titleOpen) title = `${title} ${line.desc}`;
    else {
      title = line.desc;
      titleTop = line.y;
      titleOpen = true;
      cell = null;
    }
  }
  return rows;
}

interface Rule {
  category: FeeCategory;
  perClass?: boolean;
  notes?: string;
}
const PER_CLASS: FeeCondition = {
  trigger: "classes_over",
  threshold: 0,
  per_unit: true,
  description: "Per class.",
};
const PAPER: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description: "Filed on paper, by mail only.",
};
const rules = (codes: string[], rule: Rule) =>
  codes.map((code) => [code, rule] as const);

/** Annual-fee bands (Lei 9.279/1996 art. 84): invention patents run 20 years, utility models 15. */
const BANDS: Record<
  string,
  { years: [number, number]; kind: string; late: boolean }
> = {};
for (const [codes, kind, cap] of [
  [["222", "224", "226", "228"], "patent of invention", 20],
  [["232", "234", "236", "238"], "certificate of addition of invention", 20],
  [["242", "244", "246"], "utility model patent", 15],
] as const) {
  const starts = codes.length === 4 ? [3, 7, 11, 16] : [3, 7, 11];
  codes.forEach((code, i) => {
    const years: [number, number] = [
      starts[i] as number,
      (starts[i + 1] ?? cap + 1) - 1,
    ];
    BANDS[code] = { years, kind, late: false };
    BANDS[String(Number(code) + 1)] = { years, kind, late: true };
  });
}

const PATENT_RULES: Record<string, Rule> = Object.fromEntries([
  ...rules(["200", "201"], { category: "filing" }),
  ["202", { category: "publication" }],
  ...rules(["203", "204", "205", "284", "285"], { category: "examination" }),
  ...rules(
    [
      "206",
      "207",
      "210",
      "216",
      "217",
      "218",
      "219",
      "250",
      "251",
      "252",
      "253",
      "258",
      "259",
      "260",
      "261",
      "264",
      "265",
      "270",
      "272",
      "273",
      "275",
      "280",
      "281",
      "282",
      "283",
      "290",
      "291",
      "292",
      "295",
      "296",
      "801",
      "824-4",
      "825-4",
    ],
    { category: "other" },
  ),
  ["212", { category: "grant" }],
  [
    "213",
    { category: "late_fee", notes: "Issue fee paid within the extended term." },
  ],
  ...rules(["220", "230", "240"], {
    category: "other",
    notes:
      "Annual fee while the application is pending; due each year from the third, at one amount for every year.",
  }),
  ...rules(["221", "231", "241"], {
    category: "late_fee",
    notes: "Pending-application annual fee paid within the extended term.",
  }),
  ["214", { category: "appeal" }],
  ...rules(["215", "294"], { category: "cancellation" }),
  ...rules(["208", "209", "271"], { category: "petition" }),
  ...rules(["248", "249"], { category: "transfer" }),
  ...rules(["263", "277", "278", "279"], { category: "examination" }),
  ...rules(["256", "257"], { category: "extension" }),
  ...rules(["266", "267", "276", "286", "288", "289"], { category: "search" }),
  ...rules(["268", "269"], { category: "examination" }),
]);
const TRADEMARK_RULES: Record<string, Rule> = Object.fromEntries([
  ...rules(["389", "394"], { category: "filing", perClass: true }),
  ["332", { category: "opposition", perClass: true }],
  ["372", { category: "grant", perClass: true }],
  [
    "373",
    {
      category: "late_fee",
      perClass: true,
      notes: "First-term fee paid within the extended term.",
    },
  ],
  ["374", { category: "renewal", perClass: true }],
  [
    "375",
    {
      category: "late_fee",
      perClass: true,
      notes: "Renewal fee paid within the extended term.",
    },
  ],
  ...rules(["333", "362"], { category: "appeal" }),
  ["3000", { category: "appeal", perClass: true }],
  ["3003", { category: "appeal" }],
  ["3015", { category: "appeal" }],
  ...rules(["336", "337"], { category: "cancellation", perClass: true }),
  ...rules(["348", "349", "380", "3002"], { category: "transfer" }),
  ...rules(["341", "342"], { category: "extension" }),
  ...rules(["3004", "3011", "3012", "3013"], {
    category: "madrid",
    perClass: true,
  }),
  ...rules(["3005", "3006", "3007", "3008", "3009", "3010", "3014"], {
    category: "madrid",
  }),
  ...rules(
    [
      "338",
      "339",
      "340",
      "347",
      "350",
      "351",
      "352",
      "357",
      "358",
      "361",
      "366",
      "376",
      "377",
      "378",
      "379",
      "381",
      "382",
      "383",
      "384",
      "385",
      "386",
      "387",
      "388",
      "393",
      "801",
      "824",
      "825",
      "3001",
      "3016",
      "3017",
      "3018",
    ],
    { category: "other" },
  ),
]);

const slugWords = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .split(" ")
    .slice(0, 3)
    .join("-");
const ordinal = (n: number) =>
  `${n}${n % 10 === 1 && n !== 11 ? "st" : n % 10 === 2 && n !== 12 ? "nd" : n % 10 === 3 && n !== 13 ? "rd" : "th"}`;
/** "R$100.00 per claim from the 11th to the 15th one; ... from the 31st on." */
function claimBands(prose: string) {
  const bands = [
    ...prose.matchAll(
      /R\$([\d,]+\.\d{2}) per claim from the (\d+)(?:st|nd|rd|th)(?: to the (\d+)(?:st|nd|rd|th))?/g,
    ),
  ].map((match) => ({
    amount: (match[1] as string).replaceAll(",", ""),
    from: Number(match[2]),
    to: match[3] ? Number(match[3]) : null,
  }));
  return bands;
}

interface Built {
  fees: FeeItem[];
  omitted: string[];
  unmapped: string[];
  skippedProse: string[];
}
function buildFees(
  rows: Row[],
  right: "patent" | "trademark",
  table: Record<string, Rule>,
  sourceUrl: string,
): Built {
  const prefix = right === "patent" ? "inpi-br" : "inpi-br-tm";
  const fees: FeeItem[] = [];
  const omitted = new Set<string>();
  const unmapped = new Set<string>();
  const skippedProse = new Set<string>();
  let previous: Row | null = null;
  let sibling = 0;
  const noteBase = `INPI BR${right === "trademark" ? " TM" : ""} fee code`;
  /** Codes repeated in later sections of the table are the same fee; keep the first. */
  const push = (fee: FeeItem) => {
    const existing = fees.find((item) => item.code === fee.code);
    if (existing && existing.amount !== fee.amount)
      throw invalid(`code ${fee.code} appears with two amounts.`);
    if (!existing) fees.push(fee);
  };
  for (const row of rows) {
    const band = right === "patent" ? BANDS[row.code] : undefined;
    const rule: Rule | undefined = band
      ? band.late
        ? {
            category: "late_fee",
            notes: `Annual fee for a ${band.kind} paid within the extended term.`,
          }
        : { category: "renewal" }
      : table[row.code];
    // Lines of one cell share a code; the first is the base fee and later ones get a suffix.
    sibling = previous?.code === row.code ? sibling + 1 : 0;
    previous = row;
    if (row.amounts.includes("Variable")) {
      omitted.add(row.code);
      continue;
    }
    if (!rule) unmapped.add(row.code);
    const paper = /^On paper/i.test(row.own);
    const suffix = sibling ? (paper ? "paper" : slugWords(row.own)) : "";
    const condition = paper ? PAPER : rule?.perClass ? PER_CLASS : null;
    const label = `INPI BR code ${row.code}: ${row.label}`;
    const notes = (extra?: string) =>
      [
        `${noteBase} ${row.code}.`,
        rule?.notes,
        band
          ? `Covers years ${band.years[0]}-${band.years[1]} of a ${band.kind}.`
          : undefined,
        extra,
      ]
        .filter(Boolean)
        .join(" ");
    if (!row.amounts.length) {
      // A sub-line priced in prose: claim bands, or an additional-class amount.
      const [standard, discounted] = row.prose;
      const bands = claimBands(standard);
      const reduced = claimBands(discounted);
      const extraClass = /For each additional class, R\$([\d,]+\.\d{2})/.exec(
        standard,
      );
      if (bands.length) {
        if (bands.length !== 3 || reduced.length !== 3)
          throw invalid(`code ${row.code} claim bands changed.`);
        bands.forEach((claimBand, i) => {
          const range = `${claimBand.from}-${claimBand.to ?? "plus"}`;
          const description = claimBand.to
            ? `Per claim from the ${ordinal(claimBand.from)} to the ${ordinal(claimBand.to)}.`
            : `Per claim from the ${ordinal(claimBand.from)} on.`;
          for (const [tier, amount] of [
            ["large", claimBand.amount],
            ["small", reduced[i]?.amount as string],
          ] as const)
            push({
              code: `${prefix}-${row.code}-${tier[0]}-claims-${range}`,
              label: `${label} (claims ${claimBand.to ? range : `${claimBand.from}+`})`,
              category: "excess_claims",
              rights: [right],
              amount,
              currency: "BRL",
              tier,
              year: null,
              condition: {
                trigger: "claims_over",
                threshold: claimBand.from - 1,
                per_unit: true,
                description,
              },
              source_url: sourceUrl,
              notes: notes(),
            });
        });
      } else if (extraClass) {
        push({
          code: `${prefix}-${row.code}-n-additional-class`,
          label,
          category: "excess_classes",
          rights: [right],
          amount: (extraClass[1] as string).replaceAll(",", ""),
          currency: "BRL",
          tier: "none",
          year: null,
          condition: {
            trigger: "classes_over",
            threshold: 1,
            per_unit: true,
            description: "Per class after the first.",
          },
          source_url: sourceUrl,
          notes: notes(),
        });
      } else if (standard || discounted)
        skippedProse.add(`${row.code} (${row.own})`);
      continue;
    }
    const free =
      row.amounts.length === 1 &&
      /^(?:No charge|Isento)$/.test(row.amounts[0] as string);
    const tiers: [EntityTier, string][] =
      row.amounts.length === 2
        ? [
            ["large", parseBrlAmount(row.amounts[0] as string)],
            ["small", parseBrlAmount(row.amounts[1] as string)],
          ]
        : [["none", free ? "0.00" : parseBrlAmount(row.amounts[0] as string)]];
    const years: (number | null)[] = band
      ? Array.from(
          { length: band.years[1] - band.years[0] + 1 },
          (_, i) => band.years[0] + i,
        )
      : [
          right === "trademark" && ["374", "375"].includes(row.code)
            ? 10
            : null,
        ];
    for (const year of years)
      for (const [tier, amount] of tiers)
        push({
          code: `${prefix}-${row.code}-${tier[0]}${suffix ? `-${suffix}` : ""}${band && year !== null ? `-y${year}` : ""}`,
          label,
          category: rule?.category ?? "other",
          rights: [right],
          amount,
          currency: "BRL",
          tier,
          year,
          condition,
          source_url: sourceUrl,
          notes: notes(
            free
              ? "No charge."
              : tier === "none"
                ? "No discounted amount is published; the discount does not apply."
                : undefined,
          ),
        });
  }
  return {
    fees,
    omitted: [...omitted],
    unmapped: [...unmapped],
    skippedProse: [...skippedProse],
  };
}

const DISCOUNT =
  "The discounted amount (tier small) is a reduction of up to 60% for individuals without a corporate interest in the field, micro-enterprises, sole proprietors and small companies (Complementary Law 123/2006), cooperatives (Law 5,764/1971), educational and research institutions, nonprofits and public bodies acting on their own account (INPI Resolution 251/2019). Rows with one amount carry no discount and use tier none; free services are listed at 0.00.";
const STATUTORY =
  "Lei 9.279/1996 (Brazilian IP Law); Ordinance MDIC 39/2014; ME Ordinance 516/2019; INPI Resolution 251/2019.";

/** Fetches INPI Brazil's English fee tables (patents, trademarks). */
export class InpiBrFeesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.gov.br",
      sourceName: INPI_BR_FEES_SOURCE,
      cache: { name: "inpi_br_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: { accept: "application/pdf", "user-agent": USER_AGENT },
    });
  }
  private async table(path: string, options: TransportRequestOptions) {
    const result = await this.http.bytes("GET", path, options);
    const pages = await pdfPageItems(result.data);
    const text = pages
      .flat()
      .map((item) => item.str)
      .join(" ");
    if (
      !/INPI Resolution No\. 251 of 10\/2\/2019/.test(text.replace(/\s+/g, " "))
    )
      throw invalid(
        "the table no longer cites INPI Resolution 251/2019; review the schedule before use.",
      );
    return {
      rows: tableRows(tableLines(pages)),
      provenance: {
        ...result.provenance,
        as_of_status:
          "effective date not published by the office; the table cites Ordinance MDIC 39/2014, ME Ordinance 516/2019 and INPI Resolution 251 of 2 October 2019",
        effective_date: null,
      },
    };
  }
  private schedule(
    right: "patent" | "trademark",
    built: Built,
    provenance: FeeSchedule["provenance"],
    sourceUrl: string,
    coverage: FeeSchedule["recurring_fee_coverage"],
    notes: string,
  ): FeeSchedule {
    if (!built.fees.length) throw invalid(`no ${right} fees parsed.`);
    const omitted = built.omitted.length
      ? ` Fees given only as "Variable" are omitted (${built.omitted.join(", ")}).`
      : "";
    const prose = built.skippedProse.length
      ? ` Per-page and per-item add-ons stated only in prose are not itemized (${built.skippedProse.join("; ")}).`
      : "";
    return FeeScheduleSchema.parse({
      key: `BR/INPI-BR/${right}`,
      jurisdiction: "BR",
      issuing_body: "Instituto Nacional da Propriedade Industrial (INPI)",
      office_code: "INPI-BR",
      right,
      currency: "BRL",
      effective_date: null,
      source_url: sourceUrl,
      statutory_basis: STATUTORY,
      fees: built.fees,
      recurring_fee_coverage: coverage,
      unmapped_codes: built.unmapped,
      notes: `${notes} ${DISCOUNT}${omitted}${prose} INPI's English tables date from 2020-2021 (landing page ${INPI_BR_LANDING_URL}); the Portuguese tables, which would carry any later update, require a login and were not checked.`,
      provenance,
    });
  }
  /** Invention patents, utility models and certificates of addition, including PCT fees. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const { rows, provenance } = await this.table(PATENT_PATH, options);
    const built = buildFees(
      rows,
      "patent",
      PATENT_RULES,
      INPI_BR_PATENT_PDF_URL,
    );
    const present = new Set(
      built.fees
        .filter(
          (fee) =>
            fee.category === "renewal" && /^inpi-br-22[2468]-l-/.test(fee.code),
        )
        .map((fee) => fee.year),
    );
    const missing = Array.from({ length: 18 }, (_, i) => i + 3).filter(
      (year) => !present.has(year),
    );
    return this.schedule(
      "patent",
      built,
      provenance,
      INPI_BR_PATENT_PDF_URL,
      missing.length
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
              "Invention patent annual fees for years 3-20 (codes 222-228) present; utility models (242-246, years 3-15) and certificates of addition (232-238) too.",
          },
      "Covers invention patents (20-year term), utility model patents (15 years) and certificates of addition, which share one table, plus PCT international-phase fees; renewal rows for the three share years and differ by code and label. Annual-fee bands are expanded per year. Fees paid within the extended (late) term are late fees with the same years. Examination fees for more than ten claims are three per-claim bands (11-15, 16-30, 31+). Electronic and paper rows of one code are separate fees; paper rows end -paper and carry a paper_filing condition. Source: the April 2021 English patent table, the newest on the landing page.",
    );
  }
  /** Trademark fees, including Madrid Protocol services. */
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const { rows, provenance } = await this.table(TRADEMARK_PATH, options);
    const built = buildFees(
      rows,
      "trademark",
      TRADEMARK_RULES,
      INPI_BR_TM_PDF_URL,
    );
    const renewal = built.fees.some(
      (fee) => fee.category === "renewal" && fee.year === 10,
    );
    return this.schedule(
      "trademark",
      built,
      provenance,
      INPI_BR_TM_PDF_URL,
      renewal
        ? {
            status: "complete",
            missing_categories: [],
            missing_years: [],
            notes:
              "Registrations renew every 10 years; year 10 stands for each renewal (code 374).",
          }
        : {
            status: "partial",
            missing_categories: [],
            missing_years: [10],
            notes: null,
          },
      'Fees stated "amount per class" carry a classes_over condition with threshold 0 (every class). The first ten-year term (372) is a grant fee and renewal (374) a renewal at year 10; both paid within the extended term (373, 375) are late fees. Codes repeated in several sections of the table appear once. Madrid Protocol services are madrid.',
    );
  }
}

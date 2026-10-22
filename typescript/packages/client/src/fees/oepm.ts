import { pdfPageTexts } from "../runtime/pdf.js";
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
 * OEPM (Spain) publishes every fee in one PDF, "Tasas y precios públicos".
 * Most rows pair a paper code (second letter T, M or similar) with an
 * electronic code (E, I, ...); OEPM's fee codes are kept as `oepm-<code>`.
 * Multi-column tables (annuities, renewals, multi-design bands) are parsed
 * as blocks whose codes and widths are checked. The public prices (precios
 * públicos: publications, database services, merchandise) are not IP-right
 * fees and are not parsed.
 */
export const OEPM_FEES_SOURCE = "OEPM Tasas y precios públicos";
export const OEPM_FEES_PDF_URL =
  "https://www.oepm.es/export/sites/portal/comun/documentos_relacionados/PDF/TASAS_y_PRECIOS_PUBLICOS.pdf";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`OEPM fee schedule: ${message}`, 200, "INVALID_RESPONSE");
const AMOUNT = /\d{1,3}(?:\.\d{3})*,\d{2}/g;
/** "7.329,17" -> "7329.17". Spanish notation: dot thousands, comma decimal. */
export function parseOepmAmount(raw: string): string {
  if (!/^\d{1,3}(?:\.\d{3})*,\d{2}$/.test(raw))
    throw invalid(`unrecognized amount ${raw.slice(0, 20)}`);
  return raw.replaceAll(".", "").replace(",", ".");
}
const amountsIn = (line: string) =>
  [...line.matchAll(AMOUNT)].map((m) => parseOepmAmount(m[0]));
const CODE_SHAPE = /^(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{4}$/;
const codesIn = (line: string) =>
  [...line.matchAll(/(?<![A-Z0-9+])([A-Z0-9]{4})(?![A-Z0-9+])/g)]
    .map((m) => m[1] as string)
    .filter((code) => CODE_SHAPE.test(code));
const MONTHS = [
  "ENERO",
  "FEBRERO",
  "MARZO",
  "ABRIL",
  "MAYO",
  "JUNIO",
  "JULIO",
  "AGOSTO",
  "SEPTIEMBRE",
  "OCTUBRE",
  "NOVIEMBRE",
  "DICIEMBRE",
];

type Right = "patent" | "trademark" | "design";
interface Row {
  code: string;
  label: string;
  category: FeeCategory;
  rights: Right[];
  amount: string;
  tier: EntityTier;
  year: number | null;
  condition: FeeCondition | null;
  notes: string | null;
}

// Code catalog -------------------------------------------------------------------

const paper: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description:
    "Paper filing or non-electronic payment (trámite o pago no electrónicos).",
};
const ELECTRONIC = "Electronic filing and payment.";
/** Patent and utility model rows: IT/IE (full), YT/YE (SMEs), UT/UE (public universities). */
const PATENT_ROWS: Record<string, [string, FeeCategory]> = {
  "01": ["Patent or utility model application", "filing"],
  "02": ["Request to change the type of protection", "other"],
  "03": ["Request for urgent resolution of a file", "petition"],
  "04": ["Request for the search report (IET)", "search"],
  "05": [
    "Prior examination (applications filed before 1 April 2017)",
    "examination",
  ],
  "06": ["Priority claim, per priority claimed", "other"],
  "08": ["Response to a suspension for formal defects", "other"],
  "11": [
    "Recordal of a licence-of-right offer or compulsory licence",
    "transfer",
  ],
  "13": ["Certification or certified copy", "other"],
  "14": ["Semiconductor topography registration application", "filing"],
  "15": ["Semiconductor topography material deposit", "other"],
  "16": ["Supplementary protection certificate (SPC) application", "filing"],
  "20": [
    "Recordal, cancellation or amendment of assignments, licences, rights in rem or purchase options, per registration",
    "transfer",
  ],
  "22": ["Request for substantive examination", "examination"],
  "23": ["Request for revocation or limitation", "cancellation"],
  "24": ["Request for expert reports (art. 120.7 Patents Act)", "other"],
};
/** Procedural rows shared by every right: CM/CI (trademarks, designs), I3/I5 and I7/I8 (patents). */
const COMMON_ROWS: Record<string, [string, FeeCategory]> = {
  "01": ["Restoration of rights", "petition"],
  "02": ["Appeal (request for review)", "appeal"],
  "03": ["Inspection of a file", "other"],
  "04": ["Copy of documents from a file (up to ten pages)", "other"],
  "05": ["BOPI notice of an administrative-court appeal", "publication"],
  "06": ["BOPI notice of an administrative-court judgment", "publication"],
  "07": ["Amendments", "other"],
  "08": ["Opposition", "opposition"],
  "09": [
    "Recordal of a change of the holder's name (not a transfer), per registration",
    "transfer",
  ],
};
const TRADEMARK_CODES: Record<string, [string, FeeCategory]> = {
  MT17: ["Class not paid with the application, per class", "late_fee"],
  ME17: ["Class not paid with the application, per class", "late_fee"],
  MT18: [
    "Collective or guarantee mark: class not paid with the application, per class",
    "late_fee",
  ],
  ME18: [
    "Collective or guarantee mark: class not paid with the application, per class",
    "late_fee",
  ],
  MT03: [
    "International registration request (national fee only; WIPO fees are separate)",
    "madrid",
  ],
  ME06: [
    "International registration request (national fee only; WIPO fees are separate)",
    "madrid",
  ],
  MT05: [
    "Division of an application, per resulting divisional application",
    "other",
  ],
  ME03: [
    "Division of an application, per resulting divisional application",
    "other",
  ],
  MT07: ["Request for urgent resolution", "petition"],
  ME08: ["Request for urgent resolution", "petition"],
  MT08: [
    "Paris Convention or exhibition priority, per priority claimed",
    "other",
  ],
  ME09: [
    "Paris Convention or exhibition priority, per priority claimed",
    "other",
  ],
  MT15: [
    "Recordal, cancellation or amendment of assignments, licences, rights in rem or purchase options, per registration",
    "transfer",
  ],
  ME10: [
    "Recordal, cancellation or amendment of assignments, licences, rights in rem or purchase options, per registration",
    "transfer",
  ],
  MX15: ["Maximum payable for recordals (pago máximo)", "other"],
  XM10: ["Maximum payable for recordals (pago máximo)", "other"],
  MT20: ["Certification or certified copy", "other"],
  ME11: ["Certification or certified copy", "other"],
  MT25: [
    "Request for invalidity or revocation of a mark or trade name",
    "cancellation",
  ],
  ME25: [
    "Request for invalidity or revocation of a mark or trade name",
    "cancellation",
  ],
};
const DESIGN_CODES: Record<string, [string, FeeCategory]> = {
  DT25: ["Division, per resulting application", "other"],
  DE26: ["Division, per resulting application", "other"],
  DT27: [
    "Paris Convention or exhibition priority, per priority claimed",
    "other",
  ],
  DE27: [
    "Paris Convention or exhibition priority, per priority claimed",
    "other",
  ],
  DT36: [
    "Recordal, cancellation or amendment of assignments, licences, rights in rem or purchase options, per registration",
    "transfer",
  ],
  DE24: [
    "Recordal, cancellation or amendment of assignments, licences, rights in rem or purchase options, per registration",
    "transfer",
  ],
  DX36: ["Maximum payable for recordals (pago registro máximo)", "other"],
  XD24: ["Maximum payable for recordals (pago registro máximo)", "other"],
  DT38: ["Certification or certified copy", "other"],
  DE25: ["Certification or certified copy", "other"],
  DQR0: ["Renewal title (transitional regime)", "other"],
};
/** Old-law (E.P.I.) design renewals: [surcharge, paper code, electronic code]. */
const EPI_RENEWALS: [string, string, string][] = [
  ["without surcharge", "DT35", "DE21"],
  ["with 25% surcharge", "D235", "D625"],
  ["with 50% surcharge", "D535", "D650"],
];

interface Coded {
  right: Right | "common" | null;
  tier: EntityTier;
  paper: boolean | null;
  label: string;
  category: FeeCategory;
  year?: number;
  condition?: FeeCondition;
  notes?: string;
}
const TIER_NOTES: Record<string, string> = {
  Y: "Rate for applicants that declared themselves SMEs or individual entrepreneurs (applications from 1 April 2017).",
  U: "Rate for public universities (applications from 1 April 2017).",
};
const SURCHARGE: Record<string, string> = {
  "2": "with 25% surcharge (first three months late)",
  "5": "with 50% surcharge (following three months)",
};

/** Classify a code that the generic `CODE amount` pass found. */
function classify(code: string): Coded | undefined {
  const head = code.slice(0, 2);
  const nn = code.slice(2);
  // Patent and utility model fees at three applicant tiers.
  if (/^[IYU][TE]\d\d$/.test(code)) {
    const row = PATENT_ROWS[nn];
    if (!row) return undefined;
    const tier = code[0] === "I" ? "large" : "small";
    return {
      right: "patent",
      tier,
      paper: code[1] === "T",
      label: row[0],
      category: row[1],
      ...(TIER_NOTES[code[0] as string]
        ? { notes: TIER_NOTES[code[0] as string] }
        : {}),
    };
  }
  // Procedural fees inside the patent sections: I3/I5 full rate, I7/I8 universities.
  if (/^I[3578]\d\d$/.test(code)) {
    const row = COMMON_ROWS[nn];
    if (!row) return undefined;
    return {
      right: "patent",
      tier: code[1] === "3" || code[1] === "5" ? "large" : "small",
      paper: code[1] === "3" || code[1] === "7",
      label: row[0],
      category: row[1],
      ...(code[1] === "7" || code[1] === "8" ? { notes: TIER_NOTES.U } : {}),
    };
  }
  // Procedural fees for trademarks and designs.
  if (/^C[MI]\d\d$/.test(code)) {
    const row = COMMON_ROWS[nn];
    if (!row) return undefined;
    return {
      right: "common",
      tier: "large",
      paper: head === "CM",
      label: row[0],
      category: row[1],
    };
  }
  if (code === "CX09" || code === "XC09")
    return {
      right: "common",
      tier: "large",
      paper: code === "CX09",
      label: "Maximum payable for change-of-name recordals (pago máximo)",
      category: "other",
    };
  const trademark = TRADEMARK_CODES[code];
  if (trademark)
    return {
      right: "trademark",
      tier: "large",
      paper: /^M[TX]/.test(code),
      label: trademark[0],
      category: trademark[1],
    };
  const design = DESIGN_CODES[code];
  if (design)
    return {
      right: "design",
      tier: "large",
      paper: code === "DQR0" ? null : /^D[TX]/.test(code),
      label: design[0],
      category: design[1],
      ...(code === "DQR0"
        ? {
            notes:
              "Transitional regime for designs granted under the former Industrial Property Statute.",
          }
        : {}),
    };
  const epi = EPI_RENEWALS.findIndex(([, p, e]) => p === code || e === code);
  if (epi >= 0) {
    const [surcharge, paperCode] = EPI_RENEWALS[epi] as [
      string,
      string,
      string,
    ];
    return {
      right: "design",
      tier: "large",
      paper: code === paperCode,
      label: `Renewal of a design under the former Industrial Property Statute (E.P.I.), ${surcharge}`,
      category: "other",
      notes:
        "Old-law (E.P.I.) designs only; current-law design renewals are the DT41-DT43 and DE41-DE43 rows.",
    };
  }
  if (code === "PT16" || code === "PE16")
    return {
      right: "patent",
      tier: "large",
      paper: code === "PT16",
      label: "Request for an extension (prórroga) of a medicinal-product SPC",
      category: "extension",
    };
  if (code === "ET01" || code === "ET02")
    return {
      right: "patent",
      tier: "large",
      paper: code === "ET01",
      label:
        "European patent: publication of the translated claims (provisional protection)",
      category: "translation",
    };
  if (code === "IP00")
    return {
      right: "patent",
      tier: "large",
      paper: null,
      label:
        "Grant fee (patents and utility models applied for before 1 April 2017)",
      category: "grant",
    };
  if (code === "I100")
    return {
      right: "patent",
      tier: "large",
      paper: null,
      label:
        "Regularisation of annual fee payments under art. 184.3 Patents Act",
      category: "late_fee",
    };
  if (code === "CP00" || code === "CPR0")
    return {
      right: "patent",
      tier: "large",
      paper: null,
      label: `SPC${code === "CPR0" ? " extension" : ""} grant fee (applications before 1 April 2017)`,
      category: "grant",
    };
  // SPC maintenance by SPC term: CP01-05 (term up to N years), +20 / +50 for 25% / 50% surcharges.
  const spc = /^CP(\d)(\d)$/.exec(code);
  if (spc && ["0", "2", "5"].includes(spc[1] as string)) {
    const years = Number(spc[2]);
    const band = spc[1] === "0" ? "" : `, ${SURCHARGE[spc[1] as string]}`;
    return {
      right: "patent",
      tier: "large",
      paper: null,
      label: `SPC maintenance fee, SPC term up to ${years} year${years > 1 ? "s" : ""}${band}`,
      category: spc[1] === "0" ? "other" : "late_fee",
      notes:
        "A single fee set by the length of the SPC term, not an annual fee; not a patent renewal.",
    };
  }
  const spcExtension = { CPR1: "", CPR2: "2", CPR5: "5" }[code];
  if (spcExtension !== undefined)
    return {
      right: "patent",
      tier: "large",
      paper: null,
      label: `SPC extension maintenance fee, up to 1 year${spcExtension ? `, ${SURCHARGE[spcExtension]}` : ""}`,
      category: spcExtension ? "late_fee" : "other",
    };
  // Annual fees (anualidades), years 3-20.
  const annuity = /^(IP|2P|5P|IR|2R|5R|YP|Y2|Y5|UP|U2|U5)(\d\d)$/.exec(code);
  if (annuity) {
    const family = annuity[1] as string;
    const year = Number(annuity[2]);
    if (year < 3 || year > 20) return undefined;
    const late = /[25]/.test(family)
      ? SURCHARGE[family.replace(/\D/g, "")]
      : undefined;
    const licence = family.endsWith("R");
    const tierLetter = family.startsWith("Y")
      ? "Y"
      : family.startsWith("U")
        ? "U"
        : "";
    return {
      right: "patent",
      tier: tierLetter ? "small" : "large",
      paper: null,
      label: `Annual fee, year ${year}${licence ? ", reduced for a licence-of-right offer" : ""}${late ? `, ${late}` : ""}`,
      category: licence ? "other" : late ? "late_fee" : "renewal",
      year,
      notes: [
        TIER_NOTES[tierLetter],
        licence
          ? "Licence-of-right rate for all applicants; listed with its year but outside the renewal category so that renewal lookups return the ordinary rate."
          : null,
      ]
        .filter(Boolean)
        .join(" "),
    };
  }
  if (code === "BB01" || code === "BB02")
    return {
      right: null,
      tier: "none",
      paper: null,
      label: "",
      category: "other",
    };
  return undefined;
}

// Pages ---------------------------------------------------------------------------

interface Parsed {
  rows: Row[];
  unmapped: string[];
  effective: string;
}
function effectiveDate(pages: string[]): string {
  const first = pages[0] ?? "";
  const match =
    /DESDE EL (\d{1,2}) DE ([A-ZÁÉÍÓÚ]+) DE (\d{4})/i.exec(first) ??
    /Actualizado a fecha:? (\d{1,2}) de ([a-záéíóú]+) de (\d{4})/i.exec(first);
  const month = match
    ? MONTHS.indexOf((match[2] as string).toUpperCase()) + 1
    : 0;
  if (!match || !month)
    throw invalid("the effective date on page 1 is missing.");
  return `${match[3]}-${String(month).padStart(2, "0")}-${(match[1] as string).padStart(2, "0")}`;
}

/** Collects rows, refusing one code with two different amounts. */
class Collector {
  readonly rows = new Map<string, Row>();
  readonly unmapped = new Set<string>();
  add(
    row: Omit<Row, "code" | "label" | "notes"> & {
      code: string;
      label: string;
      notes?: string | null;
    },
  ) {
    const code = `oepm-${row.code}`;
    const seen = this.rows.get(code);
    if (seen) {
      if (seen.amount !== row.amount)
        throw invalid(
          `${row.code} is listed at ${seen.amount} and ${row.amount}.`,
        );
      return;
    }
    this.rows.set(code, { ...row, code, notes: row.notes ?? null });
  }
}
const noteOf = (...parts: (string | null | undefined)[]) =>
  parts.filter(Boolean).join(" ") || null;

/** The `count` lines with amounts from `start`, and the codes printed among them. */
function block(
  lines: string[],
  start: number,
  count: number,
  width: number,
  codes: string[],
) {
  const amounts: string[][] = [];
  const found: string[] = [];
  let i = start;
  for (; i < lines.length && amounts.length < count; i++) {
    const line = lines[i] as string;
    found.push(...codesIn(line));
    const values = amountsIn(line);
    if (values.length) {
      if (values.length !== width)
        throw invalid(`expected ${width} amounts in "${line.slice(0, 40)}".`);
      amounts.push(values);
    }
  }
  // Codes printed just below the last amount line (DE41-DE43 style) are part of the block.
  for (
    ;
    i < lines.length &&
    !amountsIn(lines[i] as string).length &&
    codesIn(lines[i] as string).length;
    i++
  )
    found.push(...codesIn(lines[i] as string));
  if (amounts.length !== count)
    throw invalid(`a ${codes[0]} table is incomplete.`);
  if ([...found].sort().join() !== [...codes].sort().join())
    throw invalid(`the ${codes[0]} table codes changed: ${found.join(" ")}.`);
  return amounts;
}
const findLine = (lines: string[], pattern: RegExp, from = 0) => {
  const index = lines.findIndex((line, i) => i >= from && pattern.test(line));
  if (index < 0) throw invalid(`missing line ${pattern.source}.`);
  return index;
};

function trademarkBlocks(lines: string[], out: Collector) {
  const apps: [RegExp, string, string, string][] = [
    [
      /^SOLICITUD DE MARCA O NOMBRE 1ª Clase/,
      "MT01",
      "ME01",
      "Trademark or trade name application",
    ],
    [
      /^SOLICITUD DE MARCA COLECTIVA O 1ª Clase/,
      "MT02",
      "ME02",
      "Collective or guarantee mark application",
    ],
  ];
  for (const [pattern, paperCode, electronicCode, label] of apps) {
    const [first, further] = block(lines, findLine(lines, pattern), 2, 2, [
      paperCode,
      electronicCode,
    ]) as [string[], string[]];
    for (const [index, code] of [paperCode, electronicCode].entries()) {
      const condition = index === 0 ? paper : null;
      out.add({
        code,
        label: `${label}, first class`,
        category: "filing",
        rights: ["trademark"],
        amount: first[index] as string,
        tier: "large",
        year: null,
        condition,
        notes: index === 0 ? null : ELECTRONIC,
      });
      out.add({
        code: `${code}-class`,
        label: `${label}, each further class`,
        category: "excess_classes",
        rights: ["trademark"],
        amount: further[index] as string,
        tier: "large",
        year: null,
        condition: {
          trigger: "classes_over",
          threshold: 1,
          per_unit: true,
          description: "Per class beyond the first.",
        },
        notes: noteOf(
          `Paid with fee code ${code}.`,
          index === 0 ? "Paper filing." : ELECTRONIC,
        ),
      });
    }
  }
  // Renewals: [no surcharge, 25%, 50%] paper then electronic, for the first and each further class.
  const renewals: [string[], string][] = [
    [
      ["MT11", "MC25", "MC50", "ME04", "EC25", "EC50"],
      "Trademark or trade name renewal",
    ],
    [
      ["MT12", "MG25", "MG50", "ME05", "EG25", "EG50"],
      "Collective or guarantee mark renewal",
    ],
  ];
  let from = 0;
  for (const [codes, label] of renewals) {
    const start = findLine(lines, /^1ª Clase \d/, from);
    from = start + 1;
    const [first, further] = block(lines, start, 2, 6, codes) as [
      string[],
      string[],
    ];
    codes.forEach((code, index) => {
      const band = index % 3;
      const surcharge =
        band === 0 ? "" : `, ${SURCHARGE[band === 1 ? "2" : "5"]}`;
      const base = {
        rights: ["trademark"] as Right[],
        tier: "large" as const,
        year: 10,
        notes: noteOf(
          index < 3 ? "Paper filing." : ELECTRONIC,
          "Registrations renew every 10 years; stored as year 10.",
        ),
      };
      out.add({
        ...base,
        code,
        label: `${label}, first class${surcharge}`,
        category: band ? "late_fee" : "renewal",
        amount: first[index] as string,
        condition: index < 3 ? paper : null,
      });
      out.add({
        ...base,
        code: `${code}-class`,
        label: `${label}, each further class${surcharge}`,
        category: band ? "late_fee" : "renewal",
        amount: further[index] as string,
        condition: {
          trigger: "classes_over",
          threshold: 1,
          per_unit: true,
          description: "Per class beyond the first.",
        },
      });
    });
  }
}

const BANDS = ["1-10", "11-20", "21-30", "31-40", "41-50"];
function designBlocks(lines: string[], out: Collector) {
  const banded = (
    pattern: RegExp,
    codes: string[],
    label: string,
    category: FeeCategory,
    year: number | null,
    lateCategory?: FeeCategory,
  ) => {
    const rows = block(lines, findLine(lines, pattern), 5, codes.length, codes);
    rows.forEach((amounts, band) => {
      const range = BANDS[band] as string;
      codes.forEach((code, index) => {
        const isPaper = index < codes.length / 2;
        const surcharge = codes.length === 6 ? index % 3 : 0;
        out.add({
          code: band === 0 ? code : `${code}-${range}`,
          label: `${label}${surcharge ? `, ${SURCHARGE[surcharge === 1 ? "2" : "5"]}` : ""}, rate per design for designs ${range.replace("-", " to ")}`,
          category: surcharge && lateCategory ? lateCategory : category,
          rights: ["design"],
          amount: amounts[index] as string,
          tier: "large",
          year,
          condition: {
            trigger: "multi_design",
            threshold: band * 10,
            per_unit: true,
            description: `Per design numbered ${range.replace("-", " to ")} in the same application or registration.`,
          },
          notes: noteOf(
            isPaper ? "Paper filing." : ELECTRONIC,
            band ? `Same fee code as the designs 1-10 row (${code}).` : null,
            year
              ? "Registrations renew every five years up to 25; stored as year 5 for each renewal."
              : null,
          ),
        });
      });
    });
  };
  banded(
    /^SOLICITUD DE REGISTRO \d/,
    ["DT40", "DE40"],
    "Design registration application",
    "filing",
    null,
  );
  banded(
    /^FORMULACIÓN DE OPOSICIÓN/,
    ["DT45", "DE45"],
    "Opposition",
    "opposition",
    null,
  );
  banded(
    /^RENOVACIÓN \d/,
    ["DT41", "DT42", "DT43", "DE41", "DE42", "DE43"],
    "Design renewal",
    "renewal",
    5,
    "late_fee",
  );
  // Transitional quinquennia: one code, three amounts (no surcharge, 25%, 50%).
  for (const [pattern, code, label] of [
    [/^1ER QUINQUENIO RENOVACIÓN DQR1/, "DQR1", "First five-year renewal"],
    [/^2º QUINQUENIO RENOVACIÓN.*DQR2/, "DQR2", "Second five-year renewal"],
  ] as const) {
    const amounts = amountsIn(lines[findLine(lines, pattern)] as string);
    if (amounts.length !== 3)
      throw invalid(`${code} no longer has three amounts.`);
    amounts.forEach((amount, band) => {
      out.add({
        code: band ? `${code}-${band === 1 ? "25" : "50"}` : code,
        label: `${label} (transitional regime)${band ? `, ${SURCHARGE[band === 1 ? "2" : "5"]}` : ""}`,
        category: "other",
        rights: ["design"],
        amount,
        tier: "large",
        year: null,
        condition: null,
        notes:
          "Transitional regime for designs granted under the former Industrial Property Statute; not a current-law renewal.",
      });
    });
  }
}

function patentBlocks(lines: string[], out: Collector) {
  const start = findLine(lines, /^PUBL\. FASCÍCULO/);
  const [fascicle, page] = block(lines, start, 2, 2, ["ET03", "ET04"]) as [
    string[],
    string[],
  ];
  for (const [index, code] of ["ET03", "ET04"].entries()) {
    const note = index === 0 ? null : ELECTRONIC;
    out.add({
      code,
      label:
        "European patent: publication of the translation of the patent specification (definitive protection)",
      category: "translation",
      rights: ["patent"],
      amount: fascicle[index] as string,
      tier: "large",
      year: null,
      condition: index === 0 ? paper : null,
      notes: note,
    });
    out.add({
      code: `${code}-page`,
      label:
        "European patent: publication of the translation, each page from page 23",
      category: "translation",
      rights: ["patent"],
      amount: page[index] as string,
      tier: "large",
      year: null,
      condition: {
        trigger: "pages_over",
        threshold: 22,
        per_unit: true,
        description: "Per page of the translation from page 23.",
      },
      notes: noteOf(
        `Paid with fee code ${code}.`,
        index === 0 ? "Paper filing." : ELECTRONIC,
      ),
    });
  }
}

/** PCT fees payable to OEPM as receiving office and ISA; listed without codes except PCT1. */
const PCT_ROWS: [RegExp, string, string, FeeCategory, FeeCondition?][] = [
  [/^TASA DE TRANSMISION /, "pct-transmittal", "PCT transmittal fee", "filing"],
  [
    /^TRANSMISION DEL DOCUMENTO DE PRIORIDAD/,
    "pct-priority-document",
    "PCT transmittal of the priority document",
    "other",
  ],
  [
    /^TASA DE PRESENTACIÓN INTERNACIONAL/,
    "pct-international-filing",
    "PCT international filing fee (first 30 sheets)",
    "filing",
  ],
  [
    /^POR HOJA ADICIONAL/,
    "pct-international-filing-sheet",
    "PCT international filing fee, each sheet from sheet 31",
    "excess_pages",
    {
      trigger: "sheets_over",
      threshold: 30,
      per_unit: true,
      description: "Per sheet over 30.",
    },
  ],
  [
    /^TASA DE BÚSQUEDA PCT1 /,
    "PCT1",
    "PCT international search fee (OEPM as ISA)",
    "search",
  ],
  [
    /^TASA ADICIONAL DE BÚSQUEDA/,
    "pct-additional-search",
    "PCT additional search fee",
    "search",
  ],
  [
    /^TASA DE TRAMITACIÓN/,
    "pct-handling",
    "PCT handling fee (international preliminary examination)",
    "examination",
  ],
  [
    /^TASA DE EXAMEN PRELIMINAR INTERNACIONAL/,
    "pct-preliminary-examination",
    "PCT international preliminary examination fee",
    "examination",
  ],
  [
    /^TASA ADICIONAL DE EXAMEN PRELIMINAR/,
    "pct-additional-preliminary-examination",
    "PCT additional preliminary examination fee",
    "examination",
  ],
];
function pctPage(lines: string[], out: Collector) {
  const start = findLine(lines, /^SOLICITUDES INTERNACIONALES PCT/);
  const end = findLine(
    lines,
    /^REDUCCIONES APLICABLES A LA TASA DE PRESENTACIÓN/,
    start,
  );
  const seen = new Set<string>();
  for (const line of lines.slice(start + 1, end)) {
    const amounts = amountsIn(line);
    if (!amounts.length) continue;
    const rule = PCT_ROWS.find(([pattern]) => pattern.test(line));
    if (!rule) throw invalid(`unrecognized PCT row "${line.slice(0, 40)}".`);
    const [, code, label, category, condition] = rule;
    seen.add(code);
    out.add({
      code,
      label,
      category,
      rights: ["patent"],
      amount: amounts[0] as string,
      tier: "none",
      year: null,
      condition: condition ?? null,
    });
  }
  if (seen.size !== PCT_ROWS.length) throw invalid("PCT fee rows are missing.");
  // Reductions: amounts sit on their own lines between wrapped descriptions.
  const handling = findLine(
    lines,
    /^REDUCCIONES APLICABLES A LA TASA DE TRAMITACIÓN/,
    end,
  );
  const close = findLine(lines, /^TRÁMITE O PAGO/, handling);
  const filingText = lines.slice(end + 1, handling).join(" ");
  const filing = lines.slice(end + 1, handling).flatMap(amountsIn);
  const handlingAmounts = lines.slice(handling + 1, close).flatMap(amountsIn);
  if (
    filing.length !== 2 ||
    !/PDF/.test(filingText) ||
    !/XML/.test(filingText) ||
    handlingAmounts.length !== 1
  )
    throw invalid("the PCT reductions changed.");
  const reductions: [string, string, string][] = [
    [
      "pct-reduction-pdf",
      "Reduction of the international filing fee for electronic filing (non-character-coded PDF)",
      filing[0] as string,
    ],
    [
      "pct-reduction-xml",
      "Reduction of the international filing fee for electronic filing (character-coded XML)",
      filing[1] as string,
    ],
    [
      "pct-reduction-handling",
      "90% reduction of the handling fee for qualifying natural persons",
      handlingAmounts[0] as string,
    ],
  ];
  for (const [code, label, amount] of reductions)
    out.add({
      code,
      label,
      category: "other",
      rights: ["patent"],
      amount,
      tier: "none",
      year: null,
      condition: null,
      notes: "A reduction of another fee, not a charge.",
    });
}

const EXTRA_PAGE =
  /^Por cada página que exceda de diez\.? (\d{1,3}(?:\.\d{3})*,\d{2})/;
export async function parseOepmPdf(bytes: Uint8Array): Promise<Parsed> {
  const pages = await pdfPageTexts(bytes);
  const effective = effectiveDate(pages);
  const end = pages.findIndex((page) => /^PRECIOS PÚBLICOS/.test(page));
  if (end < 0) throw invalid("the public-prices section marker is missing.");
  const feePages = pages.slice(0, end).map((page) => page.split("\n"));
  const all = feePages.flat();
  const out = new Collector();
  trademarkBlocks(feePages[0] ?? [], out);
  designBlocks(all, out);
  patentBlocks(all, out);
  pctPage(
    feePages.find((lines) =>
      lines.some((line) => /^SOLICITUDES INTERNACIONALES PCT/.test(line)),
    ) ?? [],
    out,
  );
  // Every remaining "CODE amount" pair.
  for (const lines of feePages) {
    let previous: string | null = null;
    for (const line of lines) {
      const extra = EXTRA_PAGE.exec(line);
      if (extra && previous) {
        const coded = classify(previous);
        if (coded?.right)
          out.add({
            code: `${previous}-page`,
            label: `${coded.label}: each page over ten`,
            category: "other",
            rights:
              coded.right === "common"
                ? ["trademark", "design"]
                : [coded.right],
            amount: parseOepmAmount(extra[1] as string),
            tier: coded.tier,
            year: null,
            condition: {
              trigger: "pages_over",
              threshold: 10,
              per_unit: true,
              description: "Per page over ten.",
            },
            notes: `Paid with fee code ${previous}.`,
          });
        continue;
      }
      const pairs = [
        ...line.matchAll(
          /(?<![A-Z0-9+])([A-Z0-9]{4})(?:\s*\(\*\))?\s+(\d{1,3}(?:\.\d{3})*,\d{2})(?![\d+])/g,
        ),
      ];
      if (pairs.length) previous = null;
      for (const pair of pairs) {
        const code = pair[1] as string;
        if (
          !CODE_SHAPE.test(code) ||
          code === "PCT1" ||
          out.rows.has(`oepm-${code}`)
        )
          continue;
        previous ??= code;
        const coded = classify(code);
        if (!coded) {
          out.unmapped.add(code);
          continue;
        }
        if (!coded.right) continue;
        out.add({
          code,
          label: coded.label,
          category: coded.category,
          rights:
            coded.right === "common" ? ["trademark", "design"] : [coded.right],
          amount: parseOepmAmount(pair[2] as string),
          tier: coded.tier,
          year: coded.year ?? null,
          condition: coded.condition ?? (coded.paper ? paper : null),
          notes: noteOf(coded.notes, coded.paper === false ? ELECTRONIC : null),
        });
      }
    }
  }
  return {
    rows: [...out.rows.values()],
    unmapped: [...out.unmapped],
    effective,
  };
}

// Client ------------------------------------------------------------------------------

function renewalCoverage(
  fees: FeeItem[],
  years: number[],
  notes: string,
): RecurringFeeCoverage {
  const present = new Set(
    fees
      .filter((fee) => fee.category === "renewal" && fee.tier !== "small")
      .map((fee) => fee.year),
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
const COMMON_NOTES =
  "From OEPM's consolidated PDF of fees and public prices. Fee codes are OEPM's own (oepm-<code>); rows without their own code (further classes, multi-design bands, surcharge columns) extend the code they are printed with. Paper rows (trámite o pago no electrónicos) carry a paper_filing condition; electronic rows say so in the notes. Agent registration fees (BB01, BB02) and the public prices (precios públicos) are not IP-right fees and are omitted.";

/** Fetches OEPM's fee PDF and projects the patent, trademark and design schedules. */
export class OepmFeesClient {
  private readonly http: GenericHttpTransport;
  private pending: Promise<
    Parsed & { provenance: FeeSchedule["provenance"] }
  > | null = null;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      timeoutMs: options.timeoutMs ?? 60_000,
      baseUrl: options.baseUrl ?? "https://www.oepm.es",
      sourceName: OEPM_FEES_SOURCE,
      headers: { accept: "application/pdf", "user-agent": USER_AGENT },
    });
  }
  /** One PDF fetch serves concurrent schedule requests. */
  private pdf(options: TransportRequestOptions) {
    this.pending ??= (async () => {
      const result = await this.http.bytes(
        "GET",
        new URL(OEPM_FEES_PDF_URL).pathname,
        options,
      );
      const parsed = await parseOepmPdf(result.data);
      return {
        ...parsed,
        provenance: {
          ...result.provenance,
          as_of_status: `in force from ${parsed.effective}, as the PDF states`,
          effective_date: parsed.effective,
        },
      };
    })().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }
  private async schedule(
    right: Right,
    options: TransportRequestOptions,
    extra: {
      statutory_basis: string;
      coverage: (fees: FeeItem[]) => RecurringFeeCoverage;
      notes: string;
    },
  ): Promise<FeeSchedule> {
    const parsed = await this.pdf(options);
    const fees: FeeItem[] = parsed.rows
      .filter((row) => row.rights.includes(right))
      .map((row) => ({
        ...row,
        rights: [right],
        currency: "EUR",
        source_url: OEPM_FEES_PDF_URL,
      }));
    if (!fees.length) throw invalid(`no ${right} fees parsed.`);
    return FeeScheduleSchema.parse({
      key: `ES/OEPM/${right}`,
      jurisdiction: "ES",
      issuing_body: "Oficina Española de Patentes y Marcas (OEPM)",
      office_code: "OEPM",
      right,
      currency: "EUR",
      effective_date: parsed.effective,
      source_url: OEPM_FEES_PDF_URL,
      statutory_basis: extra.statutory_basis,
      fees,
      recurring_fee_coverage: extra.coverage(fees),
      unmapped_codes: parsed.unmapped,
      notes: `${extra.notes} ${COMMON_NOTES}`,
      provenance: parsed.provenance,
    });
  }
  /** Patent and utility model fees at three applicant tiers, annual fees, SPC, EP validation and PCT fees. */
  getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("patent", options, {
      statutory_basis:
        "Ley 24/2015, de 24 de julio, de Patentes (annex; art. 186 reductions for SMEs, individual entrepreneurs and public universities); amounts updated by the annual Ley de Presupuestos Generales del Estado.",
      coverage: (fees) =>
        renewalCoverage(
          fees,
          Array.from({ length: 18 }, (_, i) => i + 3),
          "Annual fees for years 3-20 at the full rate, with SME and public-university rates as tier small.",
        ),
      notes:
        "Tiers: full rate (IT/IE, I3/I5, IP) is large; the SME and individual-entrepreneur rate (YT/YE, YP) and the public-university rate (UT/UE, I7/I8, UP) are both small and are told apart by their notes. Annual fees run from year 3; 2P/5P (and Y2/Y5, U2/U5) are the 25% and 50% late surcharges. Licence-of-right annual fees (IR, 2R, 5R) are listed as other with their year. The regularisation totals printed as code sums (5P03+I100) are omitted; they equal the two fees added. SPC maintenance fees are set by SPC term, not by year. PCT fees are those payable to OEPM as receiving office and ISA.",
    });
  }
  /** Trademark and trade name fees with the procedural fees for distinctive signs. */
  getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("trademark", options, {
      statutory_basis:
        "Ley 17/2001, de 7 de diciembre, de Marcas (annex); amounts updated by the annual Ley de Presupuestos Generales del Estado.",
      coverage: (fees) =>
        renewalCoverage(
          fees,
          [10],
          "Registrations renew every 10 years; year 10 stands for each renewal.",
        ),
      notes:
        "Application and renewal fees are per class: the first class under the printed code and each further class as <code>-class. Renewal surcharges (25% in the first three months late, 50% in the next three) are late fees for year 10. MX15/XM10 cap the total payable for recordals. Procedural fees (CM/CI) are shared with designs.",
    });
  }
  /** Industrial design fees, with multi-design rate bands. */
  getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("design", options, {
      statutory_basis:
        "Ley 20/2003, de 7 de julio, de Protección Jurídica del Diseño Industrial (annex); amounts updated by the annual Ley de Presupuestos Generales del Estado.",
      coverage: (fees) =>
        renewalCoverage(
          fees,
          [5],
          "Registrations renew every five years up to 25; year 5 stands for each renewal.",
        ),
      notes:
        "Application, opposition and renewal fees are per design at falling rates for designs 1-10, 11-20, 21-30, 31-40 and 41-50; the first band carries the printed code and the others extend it (DT40-11-20). Renewal surcharges are late fees for year 5. Renewals of old-law (E.P.I.) designs and the transitional quinquennia (DQR) are listed as other. Procedural fees (CM/CI) are shared with trademarks.",
    });
  }
}

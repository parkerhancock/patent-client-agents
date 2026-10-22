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
 * PRH (Finland) fees are set by the Ministry of Economic Affairs and
 * Employment in a fee regulation (maksuasetus) published in the Statutes of
 * Finland. PRH's English price-list pages are script-rendered shells, so the
 * regulation PDF is the parsed source, as in Python. One PDF serves the
 * patent, trademark and design schedules.
 */
export const PRH_FEES_SOURCE = "PRH fee regulation (maksuasetus)";
const PDF_PATH =
  "/material/sites/prh/attachments/tietoaprhsta/maksuasetusl-llehikoinen/5o12dsujn/Maksuasetus_171_2026.pdf";
export const PRH_FEES_PDF_URL = `https://www.prh.fi${PDF_PATH}`;
export const PRH_PATENTS_URL =
  "https://www.prh.fi/en/price-lists/pathakmaks.html";
export const PRH_TRADEMARKS_URL =
  "https://www.prh.fi/en/price-lists/trademark_fees.html";
export const PRH_DESIGNS_URL =
  "https://www.prh.fi/en/price-lists/hinnasto_2.html";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

const invalid = (message: string) =>
  new ApiError(`PRH fee regulation: ${message}`, 200, "INVALID_RESPONSE");

/** "1 010" -> "1010.00"; "0,60" -> "0.60". Space (or no-break space) thousands, comma decimals. */
export function parsePrhAmount(raw: string): string {
  const value = raw.replace(/ /g, " ").trim();
  if (!/^\d{1,3}(?: \d{3})*(?:,\d{1,2})?$/.test(value))
    throw invalid(`unrecognized amount ${value.slice(0, 20)}`);
  const [whole = "0", fraction = ""] = value.replaceAll(" ", "").split(",");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}

const SECTION =
  /^(\d{1,2})\.\s+(Kansalliset patenttiasiat|Kansalliset hyödyllisyysmallioikeusasiat|Patenttiyhteistyösopimuksen.*?asiat|Eurooppapatenttiasiat|Lisäsuojatodistusasiat|Integroidun piirin piirimalliasiat|Teollisoikeusasiamiesasiat|Tavaramerkkiasiat|Mallioikeusasiat|Kaupparekisteriasiat)\s*$/;
const TM_ELECTRONIC = "Maksut sähköistä järjestelmää käyttäen";
const TM_PAPER = "Maksut muuta kuin sähköistä järjestelmää käyttäen";
const INLINE = /^(.+?)\s+(\d{1,3}(?: \d{3})*(?:,\d{1,2})?)\s*€(.*)$/;
const UNIT_ONLY = /^\d+(?:,\d+)?\s*€\s*\/\s*\S+$/;
const PAGE_FURNITURE =
  /^(?:\d{1,4}\/20\d{2}|\d{1,2}|Liite|MAKSUTAULUKKO \(PRH\))$/;
const LOWER_START = /^[a-zäöå(§\d]/;

type Channel = "electronic" | "paper" | "default";
interface Row {
  section: number;
  channel: Channel;
  /** The label text on the amount's own line; Python derives codes from it. */
  inline: string;
  label: string;
  amount: string;
  unit: string | null;
  /** The sub-heading the row sits under, if any. */
  heading: string | null;
}

/** Walk the regulation's lines from section 1 to section 9. Wrapped labels are joined; sub-headings prefix lowercase rows. */
export function prhRows(lines: string[]): Row[] {
  const rows: Row[] = [];
  let section = 0;
  let channel: Channel = "electronic";
  let last: Row | null = null;
  let heading: string | null = null;
  for (const raw of lines) {
    const line = raw.replace(/ /g, " ").replace(/\s+/g, " ").trim();
    if (!line || PAGE_FURNITURE.test(line)) continue;
    const header = SECTION.exec(line);
    if (header) {
      section = Number(header[1]);
      if (section >= 10) break;
      channel = "electronic";
      last = null;
      heading = null;
      continue;
    }
    if (section === 0) continue;
    if (section === 8 && (line === TM_ELECTRONIC || line === TM_PAPER)) {
      channel = line === TM_PAPER ? "paper" : "electronic";
      last = null;
      heading = null;
      continue;
    }
    if (UNIT_ONLY.test(line)) {
      if (last) last.unit = [last.unit, line].filter(Boolean).join(" ");
      continue;
    }
    const match = INLINE.exec(line);
    if (match) {
      const inline = (match[1] as string).replace(/^[ .,:;]+|[ .,:;]+$/g, "");
      if (!inline) continue;
      const nested =
        heading &&
        ((LOWER_START.test(inline) && !/^\d/.test(inline)) ||
          /^\d{1,2}\. vuosi$/.test(inline));
      last = {
        section,
        channel: section === 8 ? channel : "default",
        inline,
        label: nested
          ? `${heading}${heading?.endsWith(":") ? " " : ", "}${inline}`
          : inline,
        amount: parsePrhAmount(match[2] as string),
        unit: (match[3] as string).trim() || null,
        heading,
      };
      rows.push(last);
      continue;
    }
    if (LOWER_START.test(line)) {
      if (last) last.label = `${last.label} ${line}`;
      else if (heading) heading = `${heading} ${line}`;
      continue;
    }
    heading = line;
    last = null;
  }
  if (section < 9) throw invalid("sections 1-9 were not all found.");
  return rows;
}

/** Python's `_slug`: Finnish letters folded to ASCII, kebab-case, each part capped at 60. */
const slug = (...parts: string[]) =>
  parts
    .map((part) =>
      part
        .slice(0, 60)
        .toLowerCase()
        .replaceAll("å", "a")
        .replaceAll("ä", "a")
        .replaceAll("ö", "o")
        .replaceAll("ü", "u")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 60),
    )
    .filter(Boolean)
    .join("-");
function uniqueCodes() {
  const seen = new Set<string>();
  return (code: string) => {
    let candidate = code;
    for (let n = 2; seen.has(candidate); n++) candidate = `${code}-${n}`;
    seen.add(candidate);
    return candidate;
  };
}

const paper: FeeCondition = {
  trigger: "paper_filing",
  threshold: null,
  per_unit: false,
  description: "Filed other than through the electronic system.",
};
const classesAfterFirst: FeeCondition = {
  trigger: "classes_over",
  threshold: 1,
  per_unit: true,
  description: "Per class after the first.",
};
const claimsOver = (threshold: number): FeeCondition => ({
  trigger: "claims_over",
  threshold,
  per_unit: true,
  description: `Per claim in excess of ${threshold}.`,
});
const ANNUITY_YEAR = /(?:^|\s)(\d{1,2})\.\s*vuosi$/;

interface Mapped {
  category: FeeCategory;
  year?: number | null;
  condition?: FeeCondition | null;
  notes?: string;
}
const SECTION_NOTES: Record<number, string> = {
  2: "§2 Utility model (hyödyllisyysmalli).",
  3: "§3 PCT international phase.",
  4: "§4 European patent validated in Finland.",
  5: "§5 Supplementary protection certificate (SPC).",
};
const PREFIX: Record<number, string> = {
  1: "pat",
  2: "um",
  3: "pct",
  4: "ep",
  5: "spc",
};

/** Sections 1-5 (patents, utility models, PCT, European patents, SPCs). */
function patentRule(row: Row, umRenewalYear: number | null): Mapped {
  const label = row.label.toLowerCase();
  const year = ANNUITY_YEAR.exec(row.inline)?.[1];
  if (year) return { category: "renewal", year: Number(year) };
  if (/uudistamismaksun korotus/.test(label))
    return {
      category: "late_fee",
      year: umRenewalYear,
      notes:
        "Surcharge on the utility model renewal fee above it when paid late.",
    };
  if (/uudistamismaksu/.test(label)) {
    if (/neljäksi vuodeksi/.test(label))
      return {
        category: "renewal",
        year: 4,
        notes:
          "Renews the registration for four years (years 5-8); due at the end of year 4.",
      };
    if (/kahdeksi vuodeksi/.test(label))
      return {
        category: "renewal",
        year: 8,
        notes:
          "Renews the registration for two years (years 9-10); due at the end of year 8.",
      };
    throw invalid(`unrecognized utility model renewal period: ${row.inline}`);
  }
  if (/^palautus/.test(label))
    return {
      category: "other",
      notes: "A refund of the search fee, not a charge.",
    };
  if (/^erityinen lisämaksu/.test(label)) return { category: "other" };
  if (/viisitoista ylittävästä/.test(label))
    return { category: "excess_claims", condition: claimsOver(15) };
  if (/viisi ylittävästä/.test(label))
    return { category: "excess_claims", condition: claimsOver(5) };
  if (/^lisämaksu patenttivaatimuksesta/.test(label))
    return {
      category: "excess_claims",
      notes:
        "Per claim filed after the application date when the total exceeds the claims paid for.",
    };
  if (/lisäaja/.test(label)) return { category: "extension" };
  if (/myöhästymismaksu|viivästysmaksu/.test(label))
    return { category: "late_fee" };
  // Finnish inflects stems ("uutuustutkimuksesta"), so match stems.
  if (/esitutkimu/.test(label)) return { category: "examination" };
  if (/uutuustutkimu|tutkimusmaksu|kaltainen tutkimus/.test(label))
    return { category: "search" };
  if (/hakemusmaksu|rekisteröintimaksu/.test(label))
    return { category: "filing" };
  if (/uudelleenkäsittely/.test(label)) return { category: "examination" };
  if (/julkaisumaksu/.test(label)) return { category: "publication" };
  if (/väitemaksu/.test(label)) return { category: "opposition" };
  if (/mitätöinti|mitättömäksi/.test(label))
    return { category: "cancellation" };
  if (/ratkaisumaksu/.test(label)) return { category: "appeal" };
  if (/merkinnä/.test(label)) return { category: "transfer" };
  if (/käännösmaksu/.test(label)) return { category: "translation" };
  if (/lykkäysmaksu/.test(label)) return { category: "extension" };
  if (/lausunto/.test(label)) return { category: "search" };
  return { category: "other" };
}

function trademarkRule(row: Row): Mapped {
  const label = row.label.toLowerCase();
  if (/uudistamismaksu/.test(label) && /päättymisen jälkeen/.test(label))
    return {
      category: "late_fee",
      year: 10,
      notes: "Renewal applied for after the registration period ended.",
    };
  if (/luokkamaksu/.test(label))
    return {
      category: "excess_classes",
      condition: classesAfterFirst,
      notes: /uudistettaessa/.test(label)
        ? "Charged with a renewal."
        : "Charged with an application.",
    };
  if (/uudistamismaksu/.test(label)) return { category: "renewal", year: 10 };
  if (/vastaanottomaksu|korvaamisesta kansainvälisellä/.test(label))
    return { category: "madrid" };
  if (/muuttamishakemus/.test(label)) return { category: "other" };
  if (/menettämis|mitätöinti/.test(label)) return { category: "cancellation" };
  if (/hakemusmaksu/.test(label)) return { category: "filing" };
  if (/jatkamismaksu|määräajan pidentäm/.test(label))
    return { category: "extension" };
  if (/väit/.test(label)) return { category: "opposition" };
  if (/merkinnä/.test(label)) return { category: "transfer" };
  return { category: "other" };
}

/** Design registrations last five years and renew in five-year periods up to 25 years. */
const DESIGN_RENEWAL_YEARS = [5, 10, 15, 20];
function designRule(row: Row): Mapped {
  const label = row.label.toLowerCase();
  const atRenewal = /uudistamis/.test(row.heading?.toLowerCase() ?? "");
  const renewalNote = atRenewal ? "Charged with a renewal." : undefined;
  if (/^jos uudistamismaksu suoritetaan/.test(label))
    return {
      category: "late_fee",
      notes:
        "Surcharge when the renewal fee is paid after the registration period ends.",
    };
  if (/^uudistamismaksu$/.test(label)) return { category: "renewal" };
  if (/luokkamaksu/.test(label))
    return {
      category: "excess_classes",
      condition: classesAfterFirst,
      ...(renewalNote ? { notes: renewalNote } : {}),
    };
  if (/yhteisrekisteröintimaksu/.test(label))
    return {
      category: atRenewal ? "other" : "filing",
      condition: {
        trigger: "multi_design",
        threshold: 1,
        per_unit: true,
        description: "Per design after the first in a multiple registration.",
      },
      ...(renewalNote ? { notes: renewalNote } : {}),
    };
  if (/säilytysmaksu/.test(label))
    return {
      category: "other",
      notes: [
        "Storage fee for each specimen (mallikappale), not a deferment fee.",
        renewalNote,
      ]
        .filter(Boolean)
        .join(" "),
    };
  if (/^hakemusmaksu$/.test(label))
    return { category: "filing", condition: paper };
  if (/hakemusmaksu/.test(label)) return { category: "filing" };
  if (/merkinnä/.test(label)) return { category: "transfer" };
  if (/muuttamis/.test(label)) return { category: "other" };
  if (/uudelleenkäsittely/.test(label)) return { category: "examination" };
  return { category: "other" };
}

const item = (
  row: Row,
  code: string,
  right: "patent" | "trademark" | "design",
  sourceUrl: string,
  mapped: Mapped,
  extraNotes: (string | undefined)[] = [],
): FeeItem => ({
  code,
  label: row.label,
  category: mapped.category,
  rights: [right],
  amount: row.amount,
  currency: "EUR",
  tier: "none",
  year: mapped.year ?? null,
  condition:
    mapped.condition ??
    (row.channel === "paper" || /muuta kuin sähköistä/.test(row.label)
      ? paper
      : null),
  source_url: sourceUrl,
  notes:
    [
      ...extraNotes,
      mapped.notes,
      row.unit
        ? `Unit: ${row.amount.replace(/\.00$/, "")} €${row.unit.startsWith("/") ? "" : " "}${row.unit.replace(/\/\s+/, "/")}.`
        : undefined,
    ]
      .filter(Boolean)
      .join(" ") || null,
});

function patentFees(rows: Row[]): FeeItem[] {
  const code = uniqueCodes();
  let umRenewalYear: number | null = null;
  return rows
    .filter((row) => row.section >= 1 && row.section <= 5)
    .map((row) => {
      const mapped = patentRule(row, umRenewalYear);
      if (row.section === 2 && mapped.category === "renewal")
        umRenewalYear = mapped.year ?? null;
      return item(
        row,
        code(slug("fi-prh", PREFIX[row.section] as string, row.inline)),
        "patent",
        PRH_PATENTS_URL,
        mapped,
        [SECTION_NOTES[row.section]],
      );
    });
}
function trademarkFees(rows: Row[]): FeeItem[] {
  const code = uniqueCodes();
  const section = rows.filter((row) => row.section === 8);
  const electronic = new Set(
    section
      .filter((row) => row.channel === "electronic")
      .map((row) => row.inline),
  );
  return section.map((row) => {
    // Rows after the paper block with no electronic twin apply to both channels.
    const shared = row.channel === "paper" && !electronic.has(row.inline);
    const channel: Channel = shared ? "default" : row.channel;
    return item(
      { ...row, channel },
      code(slug("fi-prh-tm", channel === "default" ? "" : channel, row.inline)),
      "trademark",
      PRH_TRADEMARKS_URL,
      trademarkRule(row),
      [
        shared
          ? "Listed once, after the paper-filing block, with no electronic counterpart; treated as applying to both channels."
          : `Channel: ${channel}.`,
      ],
    );
  });
}
function designFees(rows: Row[]): FeeItem[] {
  const code = uniqueCodes();
  return rows
    .filter((row) => row.section === 9)
    .flatMap((row) => {
      const mapped = designRule(row);
      const base = code(slug("fi-prh-des", row.inline));
      if (mapped.category !== "renewal")
        return [item(row, base, "design", PRH_DESIGNS_URL, mapped)];
      return DESIGN_RENEWAL_YEARS.map((year) =>
        item(row, `${base}-year-${year}`, "design", PRH_DESIGNS_URL, {
          ...mapped,
          year,
          notes: `Renewal for the five years after year ${year}; the same fee applies at each renewal up to the 25-year maximum.`,
        }),
      );
    });
}

function coverage(
  fees: FeeItem[],
  years: number[],
  prefix: string,
  notes: string,
): RecurringFeeCoverage {
  const present = new Set(
    fees
      .filter(
        (fee) => fee.category === "renewal" && fee.code.startsWith(prefix),
      )
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

const FINNISH_MONTHS = [
  "tammikuuta",
  "helmikuuta",
  "maaliskuuta",
  "huhtikuuta",
  "toukokuuta",
  "kesäkuuta",
  "heinäkuuta",
  "elokuuta",
  "syyskuuta",
  "lokakuuta",
  "marraskuuta",
  "joulukuuta",
];
/** "Tämä asetus tulee voimaan 1 päivänä huhtikuuta 2026." -> "2026-04-01". */
export function prhEffectiveDate(text: string): string | null {
  const match = /tulee voimaan (\d{1,2}) päivänä (\p{L}+) (\d{4})/u.exec(text);
  const month = match ? FINNISH_MONTHS.indexOf(match[2] as string) + 1 : 0;
  if (!match || !month) return null;
  return `${match[3]}-${String(month).padStart(2, "0")}-${(match[1] as string).padStart(2, "0")}`;
}

interface Parsed {
  rows: Row[];
  effectiveDate: string | null;
  regulation: string | null;
  amends: string | null;
  provenance: FeeSchedule["provenance"];
}

/** Fetches the PRH fee regulation PDF and projects the patent, trademark and design schedules. */
export class PrhFeesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private pending: Promise<Parsed> | null = null;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://www.prh.fi",
      sourceName: PRH_FEES_SOURCE,
      cache: { name: "prh_fi_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: { accept: "application/pdf", "user-agent": USER_AGENT },
    });
  }
  /** One PDF fetch serves concurrent schedule requests. */
  private parsed(options: TransportRequestOptions): Promise<Parsed> {
    this.pending ??= (async () => {
      const result = await this.http.bytes("GET", PDF_PATH, options);
      const pages = await pdfPageTexts(result.data);
      const text = pages.join("\n");
      const effectiveDate = prhEffectiveDate(text);
      const regulation = /^(\d{1,4}\/20\d{2})$/m.exec(text)?.[1] ?? null;
      const amends =
        /asetuksen \((\d{1,4}\/20\d{2})\) liite/.exec(text)?.[1] ?? null;
      const retrieved = result.provenance.retrieved_at.slice(0, 10);
      return {
        rows: prhRows(text.split("\n")),
        effectiveDate,
        regulation,
        amends,
        provenance: {
          ...result.provenance,
          as_of_status: [
            effectiveDate
              ? `${effectiveDate > retrieved ? "scheduled to take effect" : "in force from"} ${effectiveDate} per the regulation`
              : "effective date not stated in the regulation",
            regulation ? `regulation ${regulation}` : null,
          ]
            .filter(Boolean)
            .join("; "),
          effective_date: effectiveDate,
        },
      };
    })().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }
  private schedule(
    right: "patent" | "trademark" | "design",
    parsed: Parsed,
    fees: FeeItem[],
    extra: {
      source_url: string;
      act: string;
      coverage: RecurringFeeCoverage;
      notes: string;
    },
  ): FeeSchedule {
    if (!fees.length) throw invalid(`no ${right} fees parsed.`);
    const regulation = parsed.amends
      ? `TEM fee regulation ${parsed.amends}${parsed.regulation ? `, as amended by ${parsed.regulation}` : ""}`
      : `TEM fee regulation ${parsed.regulation ?? "(number not stated)"}`;
    return FeeScheduleSchema.parse({
      key: `FI/PRH/${right}`,
      jurisdiction: "FI",
      issuing_body: "Patentti- ja rekisterihallitus (PRH)",
      office_code: "PRH",
      right,
      currency: "EUR",
      effective_date: parsed.effectiveDate,
      source_url: extra.source_url,
      statutory_basis: `${extra.act} Fees set by ${regulation}${parsed.effectiveDate ? ` (in force ${parsed.effectiveDate})` : ""}.`,
      fees,
      recurring_fee_coverage: extra.coverage,
      unmapped_codes: [],
      notes: `${extra.notes} Parsed from the fee regulation PDF (${PRH_FEES_PDF_URL}); the schedule URL is PRH's English price list for the right. Finland has no entity tiers. Labels are the regulation's Finnish text.`,
      provenance: parsed.provenance,
    });
  }
  /** Sections 1-5: national patents, utility models, PCT, European patents and SPCs. */
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const parsed = await this.parsed(options);
    const fees = patentFees(parsed.rows);
    return this.schedule("patent", parsed, fees, {
      source_url: PRH_PATENTS_URL,
      act: "Patenttilaki (550/1967) (Patents Act); Hyödyllisyysmallilaki (800/1991) (Utility Models Act).",
      coverage: coverage(
        fees,
        Array.from({ length: 20 }, (_, i) => i + 1),
        "fi-prh-pat-",
        "National patent annuities for years 1-20 present (year 1 is free).",
      ),
      notes:
        "Bundles §1 national patents, §2 utility models, §3 PCT, §4 European patents validated in Finland and §5 supplementary protection certificates, as in Python; codes are prefixed fi-prh-pat, -um, -pct, -ep and -spc. Patent annuities are years 1-20; SPC annuities are years 1-6 (code prefix fi-prh-spc). Utility model renewals are stored as years 4 and 8, when they fall due. Annuities paid late carry a 20% surcharge, which the regulation states as a percentage and is not itemized; so are the PCT translation and payment late fees. §6 integrated-circuit topographies and §7 patent attorney fees are not included.",
    });
  }
  /** Section 8: trademark fees, electronic and paper channels. */
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const parsed = await this.parsed(options);
    const fees = trademarkFees(parsed.rows);
    return this.schedule("trademark", parsed, fees, {
      source_url: PRH_TRADEMARKS_URL,
      act: "Tavaramerkkilaki (544/2019) (Trademarks Act).",
      coverage: coverage(
        fees,
        [10],
        "fi-prh-tm-",
        "Registrations renew every 10 years; year 10 stands for each renewal.",
      ),
      notes:
        "The regulation lists the trademark fees twice, for electronic and for paper filing; codes carry -electronic or -paper and paper rows a paper_filing condition. Renewals applied for after the registration period ends are late fees. Per-class fees apply to each class after the first.",
    });
  }
  /** Section 9: design fees. */
  async getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const parsed = await this.parsed(options);
    const fees = designFees(parsed.rows);
    return this.schedule("design", parsed, fees, {
      source_url: PRH_DESIGNS_URL,
      act: "Mallioikeuslaki (221/1971) (Registered Designs Act).",
      coverage: coverage(
        fees,
        DESIGN_RENEWAL_YEARS,
        "fi-prh-des-",
        "Registrations last five years and renew for five-year periods up to 25 years; the renewal fee is stored at years 5, 10, 15 and 20.",
      ),
      notes:
        "The non-electronic application fee (Hakemusmaksu, without the electronic qualifier) carries a paper_filing condition. Class, multiple-registration and storage fees appear once for applications and once for renewals.",
    });
  }
}

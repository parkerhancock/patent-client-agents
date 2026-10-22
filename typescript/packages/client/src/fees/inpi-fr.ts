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
 * INPI France publishes its procedural fees as a two-page PDF ("Tarifs des
 * procédures applicables au <date>") linked from the Tarifs landing page.
 * Rows are matched in document order against a catalog of known fees and
 * their amounts read from the PDF, so a changed amount flows through and a
 * missing or reordered row fails. Amount lines the catalog does not know
 * still appear, as `other`, and are listed in `unmapped_codes`.
 */
export const INPI_FR_FEES_SOURCE = "INPI Tarifs des procédures";
const INPI_BASE = "https://www.inpi.fr";
const LANDING_PATH =
  "/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi";
export const INPI_FR_TARIFS_PAGE = `${INPI_BASE}${LANDING_PATH}`;
/** Python's fixed fallback when the landing page no longer links the PDF. */
const FALLBACK_PDF_PATH = "/inpi-block/download-document?id=20516";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

type Right = "patent" | "trademark" | "design";
const invalid = (message: string) =>
  new ApiError(`INPI France fee schedule: ${message}`, 200, "INVALID_RESPONSE");

/** Lowercase ASCII letters and digits only, so PDF splits ("annuit é", "D épôt") still match. */
function squash(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}
/** Join digit groups the PDF splits ("19 0 €", "20 2 6"). */
const joinDigits = (line: string) => line.replace(/(\d) (?=\d)/g, "$1");
const AMOUNT = /(\d+(?:[.,]\d{1,2})?) €/g;
/** "190" -> "190.00"; "0.75" or "0,75" -> "0.75". */
export function parseEurAmount(raw: string): string {
  const value = raw.replace(",", ".");
  if (!/^\d+(?:\.\d{1,2})?$/.test(value))
    throw invalid(`unrecognized amount ${raw.slice(0, 20)}`);
  const [whole = "0", fraction = ""] = value.split(".");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}

interface Line {
  text: string;
  key: string;
  amounts: string[];
  page: number;
}
function lines(pages: string[]): Line[] {
  return pages.flatMap((page, index) =>
    page.split("\n").map((raw) => {
      const text = joinDigits(raw);
      return {
        text,
        key: squash(text.replace(AMOUNT, "")),
        amounts: [...text.matchAll(AMOUNT)].map((m) =>
          parseEurAmount(m[1] as string),
        ),
        page: index + 1,
      };
    }),
  );
}

interface Entry {
  /** Python's code stem; codes are inpi-fr-<suffix>-l, plus -s for the reduced rate. */
  suffix: string;
  label: string;
  /** Squashed text of the row's first line; `exact` requires the whole line. */
  phrase: string;
  exact?: boolean;
  right: Right;
  category: FeeCategory;
  year?: number;
  /** Renewal years one amount covers (design extensions). */
  years?: number[];
  condition?: FeeCondition;
  notes?: string;
  /** Rows read but not emitted (percentage surcharges with a minimum). */
  skip?: boolean;
}
const perPage: FeeCondition = {
  trigger: "pages_over",
  threshold: 0,
  per_unit: true,
  description: "Per page and per copy.",
};
const extraClass = (description: string): FeeCondition => ({
  trigger: "classes_over",
  threshold: 1,
  per_unit: true,
  description,
});
const ORDINALS = [
  "deuxieme",
  "troisieme",
  "quatrieme",
  "cinquieme",
  "sixieme",
  "septieme",
  "huitieme",
  "neuvieme",
  "dixieme",
  "onzieme",
  "douzieme",
  "treizieme",
  "quatorzieme",
  "quinzieme",
  "seizieme",
  "dixseptieme",
  "dixhuitieme",
  "dixneuvieme",
  "vingtieme",
];
const FRENCH_ORDINAL_LABELS = [
  "Deuxième",
  "Troisième",
  "Quatrième",
  "Cinquième",
  "Sixième",
  "Septième",
  "Huitième",
  "Neuvième",
  "Dixième",
  "Onzième",
  "Douzième",
  "Treizième",
  "Quatorzième",
  "Quinzième",
  "Seizième",
  "Dix-septième",
  "Dix-huitième",
  "Dix-neuvième",
  "Vingtième",
];

/** Every fee row of the procedures PDF in document order. */
const CATALOG: Entry[] = [
  {
    suffix: "patent-filing",
    label:
      "Dépôt d'une demande de brevet ou de certificat d'utilité (inclut la première annuité)",
    phrase: "depotdunedemandedebrevetoudecertificatdutilite",
    right: "patent",
    category: "filing",
  },
  {
    suffix: "spc-filing",
    label:
      "Dépôt d'une demande de certificat complémentaire de protection (n'inclut pas la première annuité)",
    phrase: "depotdunedemandedecertificatcomplementairedeprotection",
    right: "patent",
    category: "filing",
  },
  {
    suffix: "spc-pediatric",
    label:
      "Dépôt d'une demande de prorogation d'un certificat complémentaire de protection (usage pédiatrique)",
    phrase: "depotdunedemandedeprorogationduncertificatcomplementaire",
    right: "patent",
    category: "other",
  },
  {
    suffix: "patent-search",
    label: "Rapport de recherche",
    phrase: "rapportderecherche",
    exact: true,
    right: "patent",
    category: "search",
  },
  {
    suffix: "patent-search-equivalent",
    label:
      "Rapport de recherche sous priorité étrangère accompagnée d'un rapport reconnu équivalent",
    phrase: "rapportderechercheconcernantunedemandesousprioriteetrangere",
    right: "patent",
    category: "search",
  },
  {
    suffix: "patent-new-claims-search",
    label:
      "Nouvelles revendications entraînant rapport de recherche complémentaire",
    phrase: "nouvellesrevendicationsentrainantrapportderecherchecomplementaire",
    right: "patent",
    category: "search",
  },
  {
    suffix: "patent-claim-over-11",
    label:
      "Revendication à partir de la 11e, au dépôt ou à la modification (par revendication)",
    phrase: "revendicationsoitaumomentdudepotsoitalamodification",
    right: "patent",
    category: "excess_claims",
    condition: {
      trigger: "claims_over",
      threshold: 10,
      per_unit: true,
      description: "Per claim from the 11th.",
    },
  },
  {
    suffix: "patent-rectification",
    label: "Rectification d'erreurs matérielles par requête",
    phrase: "rectificationderreursmateriellesparrequete",
    right: "patent",
    category: "other",
  },
  {
    suffix: "patent-continuation",
    label: "Requête en poursuite de procédure",
    phrase: "requeteenpoursuitedeprocedure",
    right: "patent",
    category: "petition",
  },
  {
    suffix: "patent-grant",
    label: "Délivrance",
    phrase: "delivrance",
    exact: true,
    right: "patent",
    category: "grant",
  },
  {
    suffix: "patent-limitation",
    label: "Requête en limitation",
    phrase: "requeteenlimitation",
    exact: true,
    right: "patent",
    category: "other",
  },
  {
    suffix: "patent-opposition",
    label: "Opposition à un brevet",
    phrase: "opposition",
    exact: true,
    right: "patent",
    category: "opposition",
  },
  ...ORDINALS.map(
    (ordinal, i): Entry => ({
      suffix: `annuity-y${String(i + 2).padStart(2, "0")}`,
      label: `Redevance annuelle de maintien en vigueur d'un brevet ou d'un certificat d'utilité — ${FRENCH_ORDINAL_LABELS[i]} annuité`,
      phrase: `${ordinal}annuite`,
      exact: true,
      right: "patent",
      category: "renewal",
      year: i + 2,
    }),
  ),
  {
    suffix: "patent-spc-annual",
    label:
      "Redevance annuelle de maintien en vigueur d'un certificat complémentaire de protection et de sa prorogation",
    phrase: "redevanceannuelledemaintienenvigueurduncertificatcomplementaire",
    right: "patent",
    category: "renewal",
    year: 21,
    notes:
      "Each year of a supplementary protection certificate and its extension; stored as year 21, the first year after the 20-year patent term, as in Python.",
  },
  {
    suffix: "patent-restoration",
    label: "Recours en restauration",
    phrase: "recoursenrestauration",
    exact: true,
    right: "patent",
    category: "petition",
  },
  {
    suffix: "ep-translation-publication",
    label:
      "Publication de traduction ou de traduction révisée des revendications d'une demande de brevet européen ou d'un brevet européen",
    phrase: "publicationdetraductionoudetraductionrevisee",
    right: "patent",
    category: "translation",
  },
  {
    suffix: "ep-transmission",
    label:
      "Établissement et transmission de copies de la demande de brevet européen aux États destinataires",
    phrase: "etablissementettransmissiondecopiesdelademandedebreveteuropeen",
    right: "patent",
    category: "other",
  },
  {
    suffix: "ep-transmission-per-page",
    label:
      "Transmission de copies d'une demande de brevet européen — en plus, par page et par exemplaire",
    phrase: "enplusparpageetparexemplaire",
    exact: true,
    right: "patent",
    category: "other",
    condition: perPage,
  },
  {
    suffix: "pct-transmission",
    label: "Transmission d'une demande internationale (PCT)",
    phrase: "transmissiondunedemandeinternationale",
    exact: true,
    right: "patent",
    category: "other",
  },
  {
    suffix: "pct-copies-per-page",
    label:
      "Demande internationale (PCT) — préparation d'exemplaires complémentaires, par page et par exemplaire",
    phrase: "preparationdexemplairescomplementairesparpageetparexemplaire",
    exact: true,
    right: "patent",
    category: "other",
    condition: perPage,
  },
  {
    suffix: "pct-late-payment",
    label: "Supplément pour paiement tardif (PCT)",
    phrase: "supplementpourpaiementtardifetunmaxcorrespondanta50dela",
    right: "patent",
    category: "late_fee",
    skip: true,
  },
  {
    suffix: "tm-filing-1class",
    label: "Dépôt de marque pour une classe",
    phrase: "depotpouruneclasse",
    exact: true,
    right: "trademark",
    category: "filing",
  },
  {
    suffix: "tm-filing-collective-1class",
    label: "Dépôt pour une classe (marque collective ou marque de garantie)",
    phrase: "depotpouruneclassemarquecollectiveoumarquedegarantie",
    exact: true,
    right: "trademark",
    category: "filing",
  },
  {
    suffix: "tm-class-additional",
    label:
      "Dépôt — par classe de produits ou de services au-delà de la première",
    phrase: "parclassedeproduitoudeservicesaudeladelapremiere",
    exact: true,
    right: "trademark",
    category: "excess_classes",
    condition: extraClass("Per class beyond the first, at filing."),
  },
  {
    suffix: "tm-regularisation",
    label: "Régularisation, rectification d'erreur matérielle (marques)",
    phrase: "regularisationrectificationderreurmaterielle",
    exact: true,
    right: "trademark",
    category: "other",
  },
  {
    suffix: "tm-opposition",
    label: "Opposition à une marque",
    phrase: "opposition",
    exact: true,
    right: "trademark",
    category: "opposition",
  },
  {
    suffix: "tm-opposition-additional-right",
    label: "Opposition — par droit supplémentaire invoqué au-delà du premier",
    phrase: "pardroitsupplementaireinvoqueaudeladupremier",
    exact: true,
    right: "trademark",
    category: "opposition",
    notes: "Per earlier right invoked beyond the first.",
  },
  {
    suffix: "tm-nullity",
    label: "Requête en nullité ou déchéance d'une marque",
    phrase: "requeteennulliteoudecheance",
    exact: true,
    right: "trademark",
    category: "cancellation",
  },
  {
    suffix: "tm-nullity-additional-right",
    label:
      "Nullité — par droit supplémentaire invoqué en nullité au-delà du premier",
    phrase: "pardroitsupplementaireinvoqueennulliteaudeladupremier",
    exact: true,
    right: "trademark",
    category: "cancellation",
    notes: "Per earlier right invoked beyond the first.",
  },
  {
    suffix: "tm-renewal-1class",
    label: "Renouvellement de marque pour une classe",
    phrase: "renouvellementpouruneclasse",
    exact: true,
    right: "trademark",
    category: "renewal",
    year: 10,
  },
  {
    suffix: "tm-renewal-collective-1class",
    label:
      "Renouvellement pour une classe (marque collective ou marque de garantie)",
    phrase: "renouvellementpouruneclassemarquecollectiveoumarquedegarantie",
    exact: true,
    right: "trademark",
    category: "renewal",
    year: 10,
    notes:
      "Collective and guarantee marks; ordinary marks renew at the tm-renewal-1class rate.",
  },
  {
    suffix: "tm-renewal-class-additional",
    label:
      "Renouvellement — par classe de produits ou de services au-delà de la première",
    phrase: "parclassedeproduitoudeservicesaudeladelapremiere",
    exact: true,
    right: "trademark",
    category: "excess_classes",
    year: 10,
    condition: extraClass("Per class beyond the first, at renewal."),
  },
  {
    suffix: "tm-international-registration",
    label: "Demande d'inscription au registre international des marques",
    phrase: "demandedinscriptionauregistreinternationaldesmarques",
    exact: true,
    right: "trademark",
    category: "madrid",
    notes: "Fee payable to INPI; WIPO's Madrid fees are separate.",
  },
  {
    suffix: "tm-relevé-déchéance",
    label: "Requête en relevé de déchéance (marques)",
    phrase: "requeteenrelevededecheance2",
    exact: true,
    right: "trademark",
    category: "petition",
    notes:
      "Not payable when the delay was caused by an error other than the applicant's or its representative's (footnote 2).",
  },
  {
    suffix: "tm-division",
    label: "Division d'une marque",
    phrase: "division",
    exact: true,
    right: "trademark",
    category: "other",
  },
  {
    suffix: "design-filing",
    label: "Dépôt du dossier de demande d'enregistrement (dessins et modèles)",
    phrase: "depotdudossierdedemandedenregistrement",
    exact: true,
    right: "design",
    category: "filing",
  },
  {
    suffix: "design-bw-reproduction",
    label: "Supplément par reproduction déposée en noir et blanc",
    phrase: "supplementparreproductiondeposeeennoiretblanc",
    exact: true,
    right: "design",
    category: "filing",
    notes: "Per reproduction.",
  },
  {
    suffix: "design-color-reproduction",
    label: "Supplément par reproduction déposée en couleur",
    phrase: "supplementparreproductiondeposeeencouleur",
    exact: true,
    right: "design",
    category: "filing",
    notes: "Per reproduction.",
  },
  {
    suffix: "design-renewal",
    label: "Prorogation de protection d'un dessin ou modèle (par dépôt)",
    phrase: "prorogationpardepot",
    exact: true,
    right: "design",
    category: "renewal",
    years: [10, 15, 20, 25],
  },
  {
    suffix: "design-regularisation",
    label:
      "Régularisation, rectification d'erreur matérielle, requête en relevé de déchéance (dessins et modèles)",
    phrase:
      "regularisationrectificationderreurmateriellerequeteenrelevededecheance",
    exact: true,
    right: "design",
    category: "other",
  },
];

/** Section headings in document order; rows after REGISTRES NATIONAUX are not modeled. */
const SECTIONS: [string, Right | null][] = [
  ["brevetsdinventioncertificatsdutiliteet", "patent"],
  ["brevetseuropeens", "patent"],
  ["demandesinternationalespct", "patent"],
  ["marquesdefabriquedecommerceoudeservice", "trademark"],
  ["dessinsetmodeles", "design"],
  ["registresnationauxdesbrevetsmarquesdessinsetmodeles", null],
];

interface Parsed {
  rows: {
    entry: Entry | null;
    label: string;
    amounts: string[];
    right: Right;
  }[];
  effectiveDate: string;
  reducedEmployees: string;
}
const MONTHS = [
  "janvier",
  "fevrier",
  "mars",
  "avril",
  "mai",
  "juin",
  "juillet",
  "aout",
  "septembre",
  "octobre",
  "novembre",
  "decembre",
];

function parse(pages: string[]): Parsed {
  const all = lines(pages);
  const header = /TARIFS APPLICABLES AU (\d{1,2}) (\S+) (\d{4})/.exec(
    all[0]?.text ?? "",
  );
  const month = header ? MONTHS.indexOf(squash(header[2] as string)) + 1 : 0;
  if (!header || month === 0)
    throw invalid("the 'TARIFS APPLICABLES AU' date line is missing.");
  const effectiveDate = `${header[3]}-${String(month).padStart(2, "0")}-${(header[1] as string).padStart(2, "0")}`;
  const reduced = /inférieur à (\d+)/.exec(pages[0] ?? "");
  if (!reduced || !squash(pages[0] ?? "").includes("tarifsreduits"))
    throw invalid("the reduced-rate column or its footnote is missing.");

  // Section of every line, from the headings.
  const sectionOf: (Right | null | undefined)[] = [];
  let section: Right | null | undefined;
  let next = 0;
  for (const line of all) {
    const heading = SECTIONS[next];
    if (heading && line.key.startsWith(heading[0])) {
      section = heading[1];
      next++;
    }
    sectionOf.push(section);
  }
  if (next !== SECTIONS.length)
    throw invalid(`section heading ${SECTIONS[next]?.[0]} not found.`);

  const consumed = new Set<number>();
  const rows: Parsed["rows"] = [];
  let cursor = 0;
  for (const entry of CATALOG) {
    let found = -1;
    for (let i = cursor; i < all.length; i++) {
      const line = all[i] as Line;
      if (sectionOf[i] !== entry.right) continue;
      if (
        entry.exact
          ? line.key === entry.phrase
          : line.key.includes(entry.phrase)
      ) {
        found = i;
        break;
      }
    }
    if (found < 0) throw invalid(`row ${entry.suffix} not found in order.`);
    // The amount sits on the row's first line or on one of the next two (wrapped descriptions).
    let at = -1;
    for (let i = found; i <= found + 2 && i < all.length; i++)
      if ((all[i] as Line).amounts.length) {
        at = i;
        break;
      }
    if (at < 0) throw invalid(`row ${entry.suffix} has no amount.`);
    consumed.add(at);
    cursor = at + 1;
    const amounts = (all[at] as Line).amounts;
    if (amounts.length > 2 || (amounts.length === 2 && all[at]?.page !== 1))
      throw invalid(`row ${entry.suffix} has unexpected amounts.`);
    if (!entry.skip)
      rows.push({ entry, label: entry.label, amounts, right: entry.right });
  }
  // Amount lines in modeled sections that no catalog row claimed.
  all.forEach((line, i) => {
    const right = sectionOf[i];
    if (!right || !line.amounts.length || consumed.has(i)) return;
    rows.push({
      entry: null,
      label: line.text.replace(AMOUNT, "").trim(),
      amounts: line.amounts,
      right,
    });
  });
  return {
    rows,
    effectiveDate,
    reducedEmployees: reduced[1] as string,
  };
}

const slug = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50) || "row";

function items(parsed: Parsed, right: Right, pdfUrl: string): FeeItem[] {
  const reducedNote = `Reduced rate (tarif réduit): natural persons, non-profit teaching or research bodies, and companies with fewer than ${parsed.reducedEmployees} employees of which at most 25% of the capital is held by an entity not meeting the same condition.`;
  const out: FeeItem[] = [];
  for (const row of parsed.rows) {
    if (row.right !== right) continue;
    const entry = row.entry;
    const [standard, reduced] = row.amounts as [string, string | undefined];
    const years = entry?.years ?? [entry?.year ?? null];
    for (const year of years) {
      const stem = entry
        ? `inpi-fr-${entry.suffix}${entry.years ? `-y${year}` : ""}`
        : `inpi-fr-unmapped-${slug(row.label)}`;
      const base = {
        category: entry?.category ?? "other",
        rights: [right],
        currency: "EUR",
        year,
        condition: entry?.condition ?? null,
        source_url: pdfUrl,
      };
      const notes = [
        entry?.notes,
        entry?.years
          ? `One fee per 5-year extension; stored as year ${year}, the last year it covers.`
          : null,
      ].filter(Boolean);
      out.push({
        ...base,
        code: `${stem}-l`,
        label: row.label,
        amount: standard,
        tier: reduced ? "large" : "none",
        notes: notes.join(" ") || null,
      });
      if (reduced)
        out.push({
          ...base,
          code: `${stem}-s`,
          label: `${row.label} (tarif réduit)`,
          amount: reduced,
          tier: "small",
          notes: [...notes, reducedNote].join(" "),
        });
    }
  }
  return out;
}
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

const STATUTORY: Record<Right, string> = {
  patent:
    "Code de la propriété intellectuelle, articles R. 411-17 et seq.; arrêté fixant les redevances perçues par l'INPI.",
  trademark:
    "Code de la propriété intellectuelle, livre VII; arrêté fixant les redevances perçues par l'INPI.",
  design:
    "Code de la propriété intellectuelle, livre V; arrêté fixant les redevances perçues par l'INPI.",
};
const NOTES: Record<Right, string> = {
  patent:
    "Patents, utility certificates and supplementary protection certificates, plus the EP and PCT procedures INPI handles. The filing fee includes the first annuity; annuities run from year 2 to year 20. The reduced rate (tier small, standard rate tier large) exists for the filing, search, claim, continuation, grant and limitation fees and for annuities 2-7 only; annuities 8-20 have one rate (tier none). Late-payment surcharges are 50% of the fee due (rounded down to the euro) and are not listed as amounts.",
  trademark:
    "Filing and renewal fees cover one class; each further class is a separate excess_classes row. Registrations renew every 10 years (year 10). The late-renewal surcharge is 50% of the fee due and is not listed as an amount. Madrid fees payable to WIPO are in a separate INPI PDF and not included.",
  design:
    "Filing fee plus a supplement per reproduction (black and white or colour). Protection runs in 5-year periods to 25 years; the extension fee (prorogation, per filing) is stored at years 10, 15, 20 and 25. The late-extension surcharge is 50% of the fee due and is not listed as an amount.",
};
const RENEWAL_YEARS: Record<Right, number[]> = {
  patent: Array.from({ length: 19 }, (_, i) => i + 2),
  trademark: [10],
  design: [10, 15, 20, 25],
};
const COVERAGE_NOTE: Record<Right, string> = {
  patent: "Annuities 2-20 present; the first annuity is in the filing fee.",
  trademark:
    "Registrations renew every 10 years; year 10 stands for each renewal.",
  design: "Extensions for years 10, 15, 20 and 25 present.",
};

/** Fetches the INPI procedures PDF (found through the Tarifs page) and projects the patent, trademark and design schedules. */
export class InpiFrFeesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private pending: Promise<{
    parsed: Parsed;
    pdfUrl: string;
    provenance: FeeSchedule["provenance"];
  }> | null = null;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? INPI_BASE,
      sourceName: INPI_FR_FEES_SOURCE,
      cache: { name: "inpi_fr_fees" },
      // Python's DEFAULT_TTL_SECONDS: the default age for cacheClearExpired, not freshness.
      ttlSeconds: options.ttlSeconds ?? 7 * 24 * 3600,
      headers: {
        accept: "text/html,application/pdf",
        "user-agent": USER_AGENT,
      },
    });
  }
  /** One landing-page and PDF fetch serves concurrent schedule requests. */
  private document(options: TransportRequestOptions) {
    this.pending ??= (async () => {
      const landing = await this.http.text("GET", LANDING_PATH, options);
      const { document } = parseHTML(landing.data);
      const anchor = [...document.querySelectorAll("a[href]")].find(
        (a) =>
          (a.getAttribute("href") ?? "").includes("download-document") &&
          /tarifs des procédures/i.test(a.textContent),
      );
      const path = anchor?.getAttribute("href") ?? FALLBACK_PDF_PATH;
      const pdf = await this.http.bytes("GET", path, {
        ...options,
        maxBytes: 10 * 1024 * 1024,
      });
      const parsed = parse(await pdfPageTexts(pdf.data));
      const named = /applicables au (\d{1,2} \S+ \d{4})/i.exec(
        anchor?.textContent ?? "",
      );
      return {
        parsed,
        pdfUrl: pdf.provenance.source_url,
        provenance: {
          ...pdf.provenance,
          as_of_status: [
            `effective ${parsed.effectiveDate} per the PDF heading`,
            named
              ? `linked from the Tarifs page as applicable from ${named[1]}`
              : "PDF not linked from the Tarifs page; fetched from the known address",
          ].join("; "),
          effective_date: parsed.effectiveDate,
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
  ): Promise<FeeSchedule> {
    const { parsed, pdfUrl, provenance } = await this.document(options);
    const fees = items(parsed, right, pdfUrl);
    if (!fees.length) throw invalid(`no ${right} fees parsed.`);
    return FeeScheduleSchema.parse({
      key: `FR/INPI-FR/${right}`,
      jurisdiction: "FR",
      issuing_body: "Institut national de la propriété industrielle",
      office_code: "INPI-FR",
      right,
      currency: "EUR",
      effective_date: parsed.effectiveDate,
      source_url: INPI_FR_TARIFS_PAGE,
      statutory_basis: STATUTORY[right],
      fees,
      recurring_fee_coverage: coverage(
        fees,
        RENEWAL_YEARS[right],
        COVERAGE_NOTE[right],
      ),
      unmapped_codes: fees
        .filter((fee) => fee.code.startsWith("inpi-fr-unmapped-"))
        .map((fee) => fee.code),
      notes: NOTES[right],
      provenance,
    });
  }
  async getPatentSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("patent", options);
  }
  async getTrademarkSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("trademark", options);
  }
  async getDesignSchedule(
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    return this.schedule("design", options);
  }
}

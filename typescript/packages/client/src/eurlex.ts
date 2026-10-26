import { DOMParser } from "linkedom";
import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * EU case law and legislation from CELLAR, the Publications Office's
 * repository behind EUR-Lex: metadata by SPARQL
 * (publications.europa.eu/webapi/rdf/sparql) and documents by content
 * negotiation on publications.europa.eu/resource/celex/{CELEX}. No
 * credentials. eur-lex.europa.eu itself answers plain requests with a bot
 * challenge (HTTP 202); CELLAR does not.
 */
export const CELLAR_HOST = "https://publications.europa.eu";
export const EURLEX_SOURCE =
  "EUR-Lex (Publications Office of the European Union, CELLAR)";
const CDM = "http://publications.europa.eu/ontology/cdm#";
const AUTHORITY = "http://publications.europa.eu/resource/authority";
const XSD_STRING = "http://www.w3.org/2001/XMLSchema#string";

/** CELLAR's case-law subject matters for IP, with judgment counts on October 27, 2026. */
export const EURLEX_IP_SUBJECTS = {
  trade_marks: "MARQ", // 5,665
  designs: "DEMO", // 339
  copyright: "DADV", // 151
  patents: "BREV", // 119
  intellectual_property: "PIIC", // 88
  plant_varieties: "OBVE", // 65
} as const;
export type EurlexSubject = keyof typeof EURLEX_IP_SUBJECTS;
/** Court and document type, from a case-law CELEX number (62025TJ0786: General Court judgment). */
const COURTS = { court_of_justice: "C", general_court: "T" } as const;
const DOCUMENT_TYPES = { judgment: "J", order: "O", opinion: "C" } as const;

/** The core EU IP acts, checked against CELLAR on October 27, 2026. */
export const EU_IP_LEGISLATION = [
  {
    celex: "32017R1001",
    topic: "trade marks",
    short: "EU Trade Mark Regulation (EUTMR)",
  },
  { celex: "32015L2436", topic: "trade marks", short: "Trade Marks Directive" },
  {
    celex: "32002R0006",
    topic: "designs",
    short: "EU Designs Regulation (Community Designs Regulation as amended)",
  },
  {
    celex: "32024R2822",
    topic: "designs",
    short: "Regulation amending the Community Designs Regulation (2024)",
  },
  {
    celex: "32024L2823",
    topic: "designs",
    short: "Designs Directive (recast, 2024)",
  },
  { celex: "32012R1257", topic: "patents", short: "Unitary Patent Regulation" },
  {
    celex: "32012R1260",
    topic: "patents",
    short: "Unitary Patent translation arrangements",
  },
  {
    celex: "32009R0469",
    topic: "patents",
    short: "SPC Regulation (medicinal products)",
  },
  {
    celex: "31996R1610",
    topic: "patents",
    short: "SPC Regulation (plant protection products)",
  },
  { celex: "31998L0044", topic: "patents", short: "Biotech Directive" },
  {
    celex: "32016L0943",
    topic: "trade secrets",
    short: "Trade Secrets Directive",
  },
  {
    celex: "32004L0048",
    topic: "enforcement",
    short: "IP Enforcement Directive",
  },
  {
    celex: "32013R0608",
    topic: "enforcement",
    short: "Customs enforcement of IP rights",
  },
  { celex: "32001L0029", topic: "copyright", short: "InfoSoc Directive" },
  {
    celex: "32019L0790",
    topic: "copyright",
    short: "Digital Single Market Copyright Directive",
  },
  { celex: "32009L0024", topic: "copyright", short: "Software Directive" },
  { celex: "31996L0009", topic: "copyright", short: "Database Directive" },
  {
    celex: "32023R2411",
    topic: "geographical indications",
    short: "Craft and industrial GIs",
  },
  {
    celex: "32024R1143",
    topic: "geographical indications",
    short: "GIs for wine, spirits and agricultural products",
  },
  {
    celex: "31994R2100",
    topic: "plant varieties",
    short: "Community Plant Variety Rights Regulation",
  },
] as const;

const LANGUAGES: Record<string, string> = {
  en: "ENG",
  fr: "FRA",
  de: "DEU",
  es: "SPA",
  it: "ITA",
  nl: "NLD",
  pt: "POR",
  pl: "POL",
  sv: "SWE",
  da: "DAN",
  fi: "FIN",
  el: "ELL",
  cs: "CES",
  hu: "HUN",
  ro: "RON",
  bg: "BUL",
  sk: "SLK",
  sl: "SLV",
  hr: "HRV",
  et: "EST",
  lv: "LAV",
  lt: "LIT",
  mt: "MLT",
  ga: "GLE",
};
export type EurlexLanguage = keyof typeof LANGUAGES;
/** A CELEX number: sector digit, year, type letters and number, with an optional consolidation date. */
const CELEX =
  /^[0-9CE][0-9]{4}[A-Z]{1,2}[0-9]{1,5}(?:\([0-9]{1,2}\))?(?:-[0-9]{8})?$/;
export function celexNumber(value: string): string {
  const celex = value
    .trim()
    .toUpperCase()
    .replace(/^CELEX:/, "");
  if (!CELEX.test(celex)) throw new TypeError(`Not a CELEX number: ${value}`);
  return celex;
}

export interface EurlexCase {
  celex: string;
  ecli: string | null;
  date: string;
  court: "court_of_justice" | "general_court" | null;
  document_type: "judgment" | "order" | "opinion" | null;
  /** The full English title, which CELLAR separates into heading, parties and keywords with "#". */
  title: string | null;
  heading: string | null;
  parties: string | null;
  keywords: string | null;
}
export interface EurlexDocument {
  celex: string;
  title: string | null;
  date: string | null;
  ecli: string | null;
  in_force: boolean | null;
  language: EurlexLanguage;
  /** Plain text of the document, one paragraph per line. */
  text: string;
  /** For legislation: the latest consolidated version's CELEX, when CELLAR has one. */
  latest_consolidated: { celex: string; date: string | null } | null;
}
export interface EurlexCaseSearch extends TransportRequestOptions {
  subjects?: EurlexSubject[] | null;
  /** Words that must all appear in the English title (heading, parties or keywords). */
  words?: string | null;
  court?: keyof typeof COURTS | null;
  documentType?: keyof typeof DOCUMENT_TYPES | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  limit?: number;
  offset?: number;
}

export type EurlexErrorCode =
  | "NOT_FOUND"
  | "UPSTREAM_ERROR"
  | "INVALID_RESPONSE";
export class EurlexError extends ApiError {
  override name = "EurlexError";
  constructor(message: string, status: number, code: EurlexErrorCode) {
    super(message, status, code);
  }
}

const bindingsSchema = z.looseObject({
  results: z.looseObject({
    bindings: z.array(
      z.record(z.string(), z.looseObject({ value: z.string() })),
    ),
  }),
});
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const literal = (value: string) =>
  `"${value.replace(/["\\]/g, "")}"^^<${XSD_STRING}>`;

/** Block-level text of an HTML or XHTML document; scripts, styles and navigation are dropped. */
export function documentText(html: string): string {
  const document = new DOMParser().parseFromString(html, "text/html");
  for (const node of Array.from(
    document.querySelectorAll("script, style, head, nav"),
  ) as Element[])
    node.remove();
  const blocks =
    "p, div, li, tr, h1, h2, h3, h4, h5, h6, table, br, dt, dd, caption";
  for (const node of Array.from(document.querySelectorAll(blocks)) as Element[])
    node.insertAdjacentText?.("beforebegin", "\n");
  for (const cell of Array.from(
    document.querySelectorAll("td, th"),
  ) as Element[])
    cell.insertAdjacentText?.("afterend", " ");
  const text = (document.body ?? document.documentElement)?.textContent ?? "";
  return text
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export class EurlexClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey" | "baseUrl"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      timeoutMs: 90_000,
      ...options,
      baseUrl: CELLAR_HOST,
      sourceName: EURLEX_SOURCE,
      cache: { name: "eurlex" },
      headers: {
        "user-agent": "patent-client-agents/0 (+https://patentclient.com)",
      },
    });
  }

  /** One SPARQL SELECT; the query is built from validated parts only. */
  private async sparql(query: string, options: TransportRequestOptions = {}) {
    let result: Awaited<ReturnType<GenericHttpTransport["json"]>>;
    try {
      result = await this.http.json("POST", "/webapi/rdf/sparql", {
        ...options,
        form: { query },
        headers: { accept: "application/sparql-results+json" },
      });
    } catch (error) {
      if (error instanceof ApiError)
        throw new EurlexError(
          `CELLAR SPARQL returned HTTP ${error.status}.`,
          error.status,
          "UPSTREAM_ERROR",
        );
      throw error;
    }
    const parsed = bindingsSchema.safeParse(result.data);
    if (!parsed.success)
      throw new EurlexError(
        "CELLAR SPARQL returned an unexpected response.",
        result.status,
        "INVALID_RESPONSE",
      );
    return {
      rows: parsed.data.results.bindings.map((binding) =>
        Object.fromEntries(
          Object.entries(binding).map(([key, cell]) => [key, cell.value]),
        ),
      ),
      provenance: result.provenance,
    };
  }

  /**
   * Court of Justice and General Court case law by IP subject matter (all
   * six by default), newest first. Title words narrow it; they are matched
   * in the English title, so judgments without one only match without words.
   */
  async searchCaseLaw(search: EurlexCaseSearch = {}) {
    const subjects = z
      .array(
        z.enum(
          Object.keys(EURLEX_IP_SUBJECTS) as [
            EurlexSubject,
            ...EurlexSubject[],
          ],
        ),
      )
      .min(1)
      .parse(
        search.subjects?.length
          ? search.subjects
          : Object.keys(EURLEX_IP_SUBJECTS),
      );
    const limit = z
      .number()
      .int()
      .min(1)
      .max(100)
      .parse(search.limit ?? 25);
    const offset = z
      .number()
      .int()
      .min(0)
      .parse(search.offset ?? 0);
    for (const date of [search.dateFrom, search.dateTo])
      if (date && !DATE.test(date))
        throw new TypeError(`Dates must be YYYY-MM-DD: ${date}`);
    const words =
      (search.words ?? "").toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
    const filters = [
      search.court
        ? `SUBSTR(STR(?celex), 6, 1) = "${COURTS[search.court]}"`
        : "",
      search.documentType
        ? `SUBSTR(STR(?celex), 7, 1) = "${DOCUMENT_TYPES[search.documentType]}"`
        : "",
      search.dateFrom
        ? `?date >= "${search.dateFrom}"^^<http://www.w3.org/2001/XMLSchema#date>`
        : "",
      search.dateTo
        ? `?date <= "${search.dateTo}"^^<http://www.w3.org/2001/XMLSchema#date>`
        : "",
      ...words
        .slice(0, 8)
        .map((word) => `CONTAINS(LCASE(STR(?title)), "${word}")`),
    ].filter(Boolean);
    const title = `?expr cdm:expression_belongs_to_work ?work ; cdm:expression_uses_language <${AUTHORITY}/language/ENG> ; cdm:expression_title ?title .`;
    const where = `
  VALUES ?subject { ${subjects.map((s) => `<${AUTHORITY}/case-law-subject-matter/${EURLEX_IP_SUBJECTS[s]}>`).join(" ")} }
  ?work cdm:case-law_is-about_case-law-subject-matter ?subject ;
        cdm:resource_legal_id_celex ?celex ;
        cdm:work_date_document ?date .
  OPTIONAL { ?work cdm:case-law_ecli ?ecli }
  ${words.length ? title : `OPTIONAL { ${title} }`}
  ${filters.map((filter) => `FILTER(${filter})`).join("\n  ")}`;
    const prefix = `PREFIX cdm: <${CDM}>\n`;
    const [page, total] = await Promise.all([
      this.sparql(
        `${prefix}SELECT DISTINCT ?celex ?ecli ?date ?title WHERE {${where}\n} ORDER BY DESC(?date) ?celex LIMIT ${limit} OFFSET ${offset}`,
        search,
      ),
      this.sparql(
        `${prefix}SELECT (COUNT(DISTINCT ?celex) AS ?n) WHERE {${where}\n}`,
        search,
      ),
    ]);
    const count = Number(total.rows[0]?.n ?? 0);
    const cases: EurlexCase[] = page.rows.map((row) => {
      const celex = row.celex as string;
      const [heading, parties, ...keywords] = (row.title ?? "")
        .split("#")
        .map((part) => part.trim());
      return {
        celex,
        ecli: row.ecli ?? null,
        date: row.date as string,
        court:
          celex[5] === "C"
            ? "court_of_justice"
            : celex[5] === "T"
              ? "general_court"
              : null,
        document_type:
          celex[6] === "J"
            ? "judgment"
            : celex[6] === "O"
              ? "order"
              : celex[6] === "C"
                ? "opinion"
                : null,
        title: row.title ?? null,
        heading: heading || null,
        parties: parties || null,
        keywords: keywords.filter(Boolean).join(" ") || null,
      };
    });
    return {
      cases,
      total: count,
      offset,
      more_available: offset + cases.length < count,
      provenance: {
        ...page.provenance,
        source_url: `${CELLAR_HOST}/webapi/rdf/sparql`,
      },
    };
  }

  /**
   * The core EU IP acts with CELLAR's English title, date, in-force flag and
   * latest consolidated version. CELLAR links an act to consolidations of the
   * acts it amends too (the GI regulation 2023/2411 to the trade mark
   * regulation's), so only consolidations of the act itself, CELEX "0" plus
   * the act's number, count.
   */
  async listLegislation(
    topic?: (typeof EU_IP_LEGISLATION)[number]["topic"] | null,
    options: TransportRequestOptions = {},
  ) {
    const acts = EU_IP_LEGISLATION.filter(
      (act) => !topic || act.topic === topic,
    );
    const { rows, provenance } = await this.sparql(
      `PREFIX cdm: <${CDM}>
SELECT ?celex (SAMPLE(?t) AS ?title) (SAMPLE(?d) AS ?date) (SAMPLE(?f) AS ?inforce) (MAX(?c) AS ?consolidated) WHERE {
  VALUES ?celex { ${acts.map((act) => literal(act.celex)).join(" ")} }
  ?work cdm:resource_legal_id_celex ?celex .
  OPTIONAL { ?work cdm:work_date_document ?d }
  OPTIONAL { ?work cdm:resource_legal_in-force ?f }
  OPTIONAL { ?expr cdm:expression_belongs_to_work ?work ; cdm:expression_uses_language <${AUTHORITY}/language/ENG> ; cdm:expression_title ?t }
  OPTIONAL { ?cw cdm:act_consolidated_consolidates_resource_legal ?work ; cdm:resource_legal_id_celex ?c . FILTER(STRSTARTS(STR(?c), CONCAT("0", SUBSTR(STR(?celex), 2), "-"))) }
} GROUP BY ?celex`,
      options,
    );
    const byCelex = new Map(rows.map((row) => [row.celex, row]));
    return {
      acts: acts.map((act) => {
        const row = byCelex.get(act.celex);
        return {
          ...act,
          title: row?.title ?? null,
          date: row?.date ?? null,
          in_force:
            row?.inforce === undefined
              ? null
              : row.inforce === "1" || row.inforce === "true",
          latest_consolidated: row?.consolidated ?? null,
        };
      }),
      provenance: {
        ...provenance,
        source_url: `${CELLAR_HOST}/webapi/rdf/sparql`,
      },
    };
  }

  /** CELLAR's metadata for one work: English title, date, ECLI, in-force flag and latest consolidation. */
  private async metadata(celex: string, options: TransportRequestOptions) {
    const { rows } = await this.sparql(
      `PREFIX cdm: <${CDM}>
SELECT ?title ?date ?ecli ?inforce ?consolidated ?consolidatedDate WHERE {
  ?work cdm:resource_legal_id_celex ${literal(celex)} .
  OPTIONAL { ?work cdm:work_date_document ?date }
  OPTIONAL { ?work cdm:case-law_ecli ?ecli }
  OPTIONAL { ?work cdm:resource_legal_in-force ?inforce }
  OPTIONAL { ?expr cdm:expression_belongs_to_work ?work ; cdm:expression_uses_language <${AUTHORITY}/language/ENG> ; cdm:expression_title ?title }
  OPTIONAL { ?c cdm:act_consolidated_consolidates_resource_legal ?work ; cdm:resource_legal_id_celex ?consolidated . FILTER(STRSTARTS(STR(?consolidated), "0${celex.slice(1)}-")) OPTIONAL { ?c cdm:act_consolidated_date ?consolidatedDate } }
} ORDER BY DESC(?consolidated) LIMIT 1`,
      options,
    );
    return rows[0];
  }

  /**
   * One document by CELEX number: a judgment, opinion, order or act, or a
   * consolidated version (02002R0006-20260701). XHTML is preferred, HTML
   * accepted: legislation tends to have the first, case law the second.
   */
  async getDocument(
    celexValue: string,
    language: EurlexLanguage = "en",
    options: TransportRequestOptions = {},
  ): Promise<{ data: EurlexDocument; provenance: Provenance }> {
    const celex = celexNumber(celexValue);
    const code = LANGUAGES[language];
    if (!code) throw new TypeError(`Unsupported EUR-Lex language: ${language}`);
    // Settle both, so a missing document reports its 404 rather than racing
    // the metadata query.
    const [metaResult, contentResult] = await Promise.allSettled([
      this.metadata(celex, options),
      this.http
        .text("GET", `/resource/celex/${encodeURIComponent(celex)}`, {
          ...options,
          headers: {
            accept: "application/xhtml+xml, text/html;q=0.9",
            "accept-language": code.toLowerCase(),
          },
          allowedHosts: ["publications.europa.eu"],
          upgradeRedirects: true,
        })
        .catch((error) => {
          if (error instanceof ApiError && error.status === 404)
            throw new EurlexError(
              `CELLAR has no HTML text of ${celex} in ${language}.`,
              404,
              "NOT_FOUND",
            );
          throw error instanceof ApiError
            ? new EurlexError(
                `CELLAR returned HTTP ${error.status} for ${celex}.`,
                error.status,
                "UPSTREAM_ERROR",
              )
            : error;
        }),
    ]);
    if (contentResult.status === "rejected") throw contentResult.reason;
    if (metaResult.status === "rejected") throw metaResult.reason;
    const meta = metaResult.value;
    const content = contentResult.value;
    const consolidated =
      meta?.consolidated && meta.consolidated !== celex
        ? { celex: meta.consolidated, date: meta.consolidatedDate ?? null }
        : null;
    return {
      data: {
        celex,
        title: meta?.title ?? null,
        date: meta?.date ?? null,
        ecli: meta?.ecli ?? null,
        in_force:
          meta?.inforce === undefined
            ? null
            : meta.inforce === "1" || meta.inforce === "true",
        language,
        text: documentText(content.data),
        latest_consolidated: consolidated,
      },
      provenance: content.provenance,
    };
  }
}

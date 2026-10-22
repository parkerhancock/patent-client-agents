import { z } from "zod";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * Federal Court of Canada (and Federal Court of Appeal) public Court Files
 * service (https://www-u.fct-cf.gc.ca/en/court-files-and-decisions/court-files).
 * The page's own scripts call keyless JSON endpoints under
 * /CourtFilesAndDecisions/; each answers `{ Count, data: [...] }`.
 */
export const CANADA_FEDERAL_COURT_SOURCE =
  "Federal Court of Canada — Court Files";
export const CANADA_FEDERAL_COURT_ORIGIN = "https://www-u.fct-cf.gc.ca";
export const CANADA_FEDERAL_COURT_FILES_URL = `${CANADA_FEDERAL_COURT_ORIGIN}/en/court-files-and-decisions/court-files`;
const API = "/CourtFilesAndDecisions";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

/** "t" Federal Court, "a" Federal Court of Appeal, "b" both. */
export const CourtDivisionSchema = z.enum(["t", "a", "b"]);
export type CourtDivision = z.infer<typeof CourtDivisionSchema>;
export type StatusAssessment = "likely_pending" | "likely_closed" | "unknown";

/** A deliberately conservative, non-authoritative docket-status assessment. */
export interface DocketStatus {
  assessment: StatusAssessment;
  basis: string;
  inferred: true;
}

/** One Federal Court or Federal Court of Appeal case-file record. */
export interface FederalCourtCase {
  court_number: string;
  court_sequence: string | null;
  style_of_cause: string;
  nature_code: string | null;
  nature_en: string | null;
  nature_fr: string | null;
  division: string;
  /** ISO date in Eastern time, the Registry's own calendar. */
  filed_date: string | null;
  office_code: string | null;
  city_en: string | null;
  city_fr: string | null;
  proceeding_type_en: string | null;
  proceeding_type_fr: string | null;
  proceeding_class_en: string | null;
  proceeding_class_fr: string | null;
  language_code: string | null;
  language_en: string | null;
  language_fr: string | null;
  parties: string[];
}
/** Party and public counsel information for a court file. */
export interface FederalCourtParty {
  name: string;
  solicitor_firm: string | null;
  solicitor_contact: string | null;
}
/** IP name or registration/application number associated with a court file. */
export interface FederalCourtIntellectualProperty {
  title: string | null;
  number: string | null;
}
export interface FederalCourtRelatedCase {
  court_number: string;
  style_of_cause: string | null;
  nature_en: string | null;
  nature_fr: string | null;
}
/** One recorded entry from a case history. */
export interface FederalCourtDocketEntry {
  court_number: string;
  style_of_cause: string | null;
  filing_date: string | null;
  nature_code: string | null;
  nature_en: string | null;
  track_en: string | null;
  office_en: string | null;
  document_number: number | null;
  entry_number: number;
  document_id: string | null;
  summary: string;
  document_date: string | null;
  registry_notes: string | null;
  command_phrase_en: string | null;
  command_phrase_fr: string | null;
  can_download: boolean;
  is_confidential: boolean;
  download_url: string | null;
}

export interface FederalCourtCaseSearchResponse {
  query: string;
  /** Party-name hits before patent filtering. */
  upstream_count: number;
  filtered_count: number;
  cases: FederalCourtCase[];
  provenance: Provenance;
}
export interface FederalCourtCaseRecord {
  case: FederalCourtCase;
  parties: FederalCourtParty[];
  intellectual_property: FederalCourtIntellectualProperty[];
  related_cases: FederalCourtRelatedCase[];
  provenance: Provenance;
}
export interface FederalCourtDocketResponse {
  court_number: string;
  total_count: number;
  status: DocketStatus;
  entries: FederalCourtDocketEntry[];
  provenance: Provenance;
}

export interface PartyCaseSearchOptions {
  partyName: string;
  division?: CourtDivision;
  /** Inclusive YYYY-MM-DD bounds; supply both or neither. */
  filedFrom?: string;
  filedTo?: string;
  /** Keep explicit patent/brevet nature labels only (default true). */
  patentOnly?: boolean;
  /** 1-100, default 25. */
  limit?: number;
}

const text = z.string().nullable().optional();
const PayloadSchema = z.looseObject({
  Count: z.number().int().nonnegative().optional(),
  data: z.array(z.record(z.string(), z.unknown())),
});
const CaseRowSchema = z.looseObject({
  COURT_NO: z.string(),
  COURT_SEQ: text,
  STYLE_OF_CAUSE: z.string(),
  NATURE_CD: text,
  ENGLISH_NATURE_DESC: text,
  FRENCH_NATURE_DESC: text,
  DIVISION: z.string(),
  FILE_DT: text,
  OFF_CD: text,
  ENGLISH_CITY_NAME: text,
  FRENCH_CITY_NAME: text,
  ENGLISH_PROCEEDING_TYPE: text,
  FRENCH_PROCEEDING_TYPE: text,
  ENGLISH_PROCEEDING_CLASS: text,
  FRENCH_PROCEEDING_CLASS: text,
  LANG_CD: text,
  ENGLISH_LANGUAGE_NAME: text,
  FRENCH_LANGUAGE_NAME: text,
  Party: z.array(z.string().nullable()).nullable().optional(),
});
const PartyRowSchema = z.looseObject({
  PARTY_NAME: z.string(),
  SOLCTR_FIRM: text,
  SOLCTR_CONTACT: text,
});
const IpRowSchema = z.looseObject({
  INT_PROPERTY_TITLE: text,
  INT_PROPERTY_NUMBER: z.union([z.string(), z.number()]).nullable().optional(),
});
const RelatedRowSchema = z.looseObject({
  RELATED_COURT_NO: z.string(),
  STYLE_OF_CAUSE: text,
  ENGLISH_NATURE_DESC: text,
  FRENCH_NATURE_DESC: text,
});
const flag = z
  .union([z.string(), z.boolean()])
  .nullable()
  .optional()
  .transform((value) => value === "Y" || value === true);
const DocketRowSchema = z.looseObject({
  COURT_NO: z.string(),
  STYLE_OF_CAUSE: text,
  FILING_DATE: text,
  NATURE_CD: text,
  ENGLISH_NATURE_DESC: text,
  ENGLISH_TRACK_NAME: text,
  ENGLISH_OFFICE_NAME: text,
  DOCNO: z.number().int().nullable().optional(),
  RE_NO: z.number().int(),
  FOREMOST_NUMBER: z.union([z.string(), z.number()]).nullable().optional(),
  RECORDED_ENTRY: z.string(),
  DOC_DT: text,
  REGISTRY_NOTES_EXTERNAL: text,
  COMMAND_PHRASE_EN: text,
  COMMAND_PHRASE_FR: text,
  CAN_PUBLISH_DOCUMENT: flag,
  IS_CONFIDENTIAL: flag,
});

/** UTC milliseconds of the nth Sunday of a month at the given UTC hour. */
function nthSunday(year: number, month: number, n: number, utcHour: number) {
  const first = new Date(Date.UTC(year, month, 1)).getUTCDay();
  const day = 1 + ((7 - first) % 7) + (n - 1) * 7;
  return Date.UTC(year, month, day, utcHour);
}
/**
 * The Registry's servers store local Eastern times and serialize them as UTC
 * instants (`/Date(ms)/`) using the current daylight-saving rule (second Sunday
 * of March to first Sunday of November) for every year: a 1982 filing at
 * local midnight on April 16 arrives as 04:00Z. Inverting that conversion
 * recovers the Registry's calendar date; the UTC date is a day late for
 * evening filings.
 */
function easternDate(ms: number): string {
  const year = new Date(ms - 5 * 3_600_000).getUTCFullYear();
  const daylight =
    ms >= nthSunday(year, 2, 2, 7) && ms < nthSunday(year, 10, 1, 6);
  return new Date(ms - (daylight ? 4 : 5) * 3_600_000)
    .toISOString()
    .slice(0, 10);
}

/** Parse the Court's Microsoft-JSON (`/Date(ms)/`) or ISO date representation to YYYY-MM-DD. */
export function parseCourtDate(
  value: string | null | undefined,
): string | null {
  if (!value) return null;
  const microsoft = /^\/Date\((-?\d+)(?:[+-]\d{4})?\)\/$/.exec(value);
  if (microsoft) return easternDate(Number(microsoft[1]));
  const iso = /^(\d{4}-\d{2}-\d{2})(?:[T ]|$)/.exec(value);
  if (iso && !Number.isNaN(Date.parse(iso[1] as string)))
    return iso[1] as string;
  throw invalid(`Unsupported Federal Court date value: ${value}`);
}

const invalid = (message: string, status = 200) =>
  new ApiError(message, status, "INVALID_RESPONSE");
const badInput = (message: string) =>
  new ApiError(message, 400, "INVALID_INPUT");
const nullable = (value: string | null | undefined) => value ?? null;

function parseCase(row: Record<string, unknown>): FederalCourtCase {
  const r = CaseRowSchema.parse(row);
  return {
    court_number: r.COURT_NO,
    court_sequence: nullable(r.COURT_SEQ),
    style_of_cause: r.STYLE_OF_CAUSE,
    nature_code: nullable(r.NATURE_CD),
    nature_en: nullable(r.ENGLISH_NATURE_DESC),
    nature_fr: nullable(r.FRENCH_NATURE_DESC),
    division: r.DIVISION,
    filed_date: parseCourtDate(r.FILE_DT),
    office_code: nullable(r.OFF_CD),
    city_en: nullable(r.ENGLISH_CITY_NAME),
    city_fr: nullable(r.FRENCH_CITY_NAME),
    proceeding_type_en: nullable(r.ENGLISH_PROCEEDING_TYPE),
    proceeding_type_fr: nullable(r.FRENCH_PROCEEDING_TYPE),
    proceeding_class_en: nullable(r.ENGLISH_PROCEEDING_CLASS),
    proceeding_class_fr: nullable(r.FRENCH_PROCEEDING_CLASS),
    language_code: nullable(r.LANG_CD),
    language_en: nullable(r.ENGLISH_LANGUAGE_NAME),
    language_fr: nullable(r.FRENCH_LANGUAGE_NAME),
    parties: (r.Party ?? []).filter((p): p is string => typeof p === "string"),
  };
}
function parseDocketEntry(
  row: Record<string, unknown>,
): FederalCourtDocketEntry {
  const r = DocketRowSchema.parse(row);
  return {
    court_number: r.COURT_NO,
    style_of_cause: nullable(r.STYLE_OF_CAUSE),
    filing_date: parseCourtDate(r.FILING_DATE),
    nature_code: nullable(r.NATURE_CD),
    nature_en: nullable(r.ENGLISH_NATURE_DESC),
    track_en: nullable(r.ENGLISH_TRACK_NAME),
    office_en: nullable(r.ENGLISH_OFFICE_NAME),
    document_number: r.DOCNO ?? null,
    entry_number: r.RE_NO,
    document_id:
      r.FOREMOST_NUMBER === null || r.FOREMOST_NUMBER === undefined
        ? null
        : String(r.FOREMOST_NUMBER),
    summary: r.RECORDED_ENTRY.trim(),
    document_date: parseCourtDate(r.DOC_DT),
    registry_notes: r.REGISTRY_NOTES_EXTERNAL?.trim() || null,
    command_phrase_en: nullable(r.COMMAND_PHRASE_EN),
    command_phrase_fr: nullable(r.COMMAND_PHRASE_FR),
    can_download: r.CAN_PUBLISH_DOCUMENT,
    is_confidential: r.IS_CONFIDENTIAL,
    download_url: null,
  };
}

/**
 * The party search sometimes returns one file twice (seen October 22, 2026:
 * 28 rows for a 27-file answer). Keep the first row and merge party names.
 */
function dedupeCases(cases: FederalCourtCase[]): FederalCourtCase[] {
  const seen = new Map<string, FederalCourtCase>();
  for (const item of cases) {
    const key = `${item.division}|${item.court_number}`;
    const first = seen.get(key);
    if (!first) seen.set(key, item);
    else
      for (const party of item.parties)
        if (!first.parties.includes(party)) first.parties.push(party);
  }
  return [...seen.values()];
}

/** True when the English or French nature label names a patent ("patent" / "brevet"). */
export function isPatentCase(
  value: Pick<FederalCourtCase, "nature_en" | "nature_fr">,
): boolean {
  const description =
    `${value.nature_en ?? ""} ${value.nature_fr ?? ""}`.toLowerCase();
  return description.includes("patent") || description.includes("brevet");
}

const CLOSED_MARKERS = [
  "notice of discontinuance",
  "proceeding is discontinued",
  "action is discontinued",
  "application is discontinued",
  "proceeding is dismissed",
  "action is dismissed",
  "application is dismissed",
  "final decision",
  "final judgment",
];
const PENDING_MARKERS = [
  "trial scheduled",
  "hearing scheduled",
  "case management conference scheduled",
  "case management conference to be held",
  "case management conference will be held",
  "seeking first case management conference",
  "will proceed to trial",
];
/** Whitespace is collapsed: the Registry writes "seeking  first case management conference". */
const entryText = (entry: FederalCourtDocketEntry) =>
  [entry.summary, entry.registry_notes, entry.command_phrase_en]
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .toLowerCase();

/** Infer a cautious status from explicit language in the ten most recent docket entries. */
export function assessDocketStatus(
  entries: readonly FederalCourtDocketEntry[],
): DocketStatus {
  if (!entries.length)
    return {
      assessment: "unknown",
      basis:
        "The Registry returned no recorded entries and no official status field.",
      inferred: true,
    };
  const recent = [...entries]
    .sort((a, b) => b.entry_number - a.entry_number)
    .slice(0, 10);
  const combined = recent.map(entryText).join("\n");
  const closed = CLOSED_MARKERS.find((marker) => combined.includes(marker));
  if (closed)
    return {
      assessment: "likely_closed",
      basis: `A recent recorded entry contains the terminal phrase '${closed}'.`,
      inferred: true,
    };
  const latest = entryText(recent[0] as FederalCourtDocketEntry);
  const pending = PENDING_MARKERS.find((marker) => latest.includes(marker));
  if (pending)
    return {
      assessment: "likely_pending",
      basis: `The latest recorded entry contains the prospective phrase '${pending}'.`,
      inferred: true,
    };
  return {
    assessment: "unknown",
    basis:
      "The Court does not publish an official status field and recent entries are not dispositive.",
    inferred: true,
  };
}

const isoDate = (value: string, label: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(value)))
    throw badInput(`${label} must be ISO date YYYY-MM-DD; got ${value}`);
  return value;
};
/** YYYY-MM-DD -> MM-DD-YYYY, the format of the site's date pickers. */
const courtDate = (value: string) => {
  const [y, m, d] = value.split("-");
  return `${m}-${d}-${y}`;
};
const normalizeCourtNumber = (value: string) => {
  const number = value.trim().toUpperCase();
  if (number.length < 3)
    throw badInput("court_number must contain at least 3 characters");
  return number;
};
const division = (value: CourtDivision | undefined): CourtDivision => {
  const parsed = CourtDivisionSchema.safeParse(value ?? "t");
  if (!parsed.success) throw badInput("division must be 't', 'a', or 'b'");
  return parsed.data;
};

/** Read-only client for the official Federal Court Court Files JSON endpoints. */
export class CanadaFederalCourtClient {
  private readonly http: GenericHttpTransport;
  private readonly origin: string;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.origin = (options.baseUrl ?? CANADA_FEDERAL_COURT_ORIGIN).replace(
      /\/+$/,
      "",
    );
    this.http = new GenericHttpTransport({
      ...options,
      timeoutMs: options.timeoutMs ?? 60_000,
      baseUrl: this.origin,
      sourceName: CANADA_FEDERAL_COURT_SOURCE,
      headers: { accept: "application/json", "user-agent": USER_AGENT },
    });
  }

  private async data(
    path: string,
    searchParams: Record<string, string>,
    options: TransportRequestOptions,
  ) {
    const result = await this.http.json("GET", `${API}/${path}`, {
      ...options,
      searchParams,
    });
    const parsed = PayloadSchema.safeParse(result.data);
    if (!parsed.success)
      throw invalid(
        `Unexpected Federal Court response shape from ${path}.`,
        result.status,
      );
    const rows = parsed.data.data;
    const count = parsed.data.Count ?? rows.length;
    return {
      count,
      rows,
      provenance: result.provenance,
      status: result.status,
    };
  }

  private parseRows<T>(
    rows: Record<string, unknown>[],
    parse: (row: Record<string, unknown>) => T,
    path: string,
    status: number,
  ): T[] {
    try {
      return rows.map(parse);
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw invalid(`Malformed Federal Court row from ${path}.`, status);
    }
  }

  /**
   * Search case files by party or corporation name (either side), newest
   * filings first. The name is sent as typed: the Registry stores most
   * corporate names without periods ("APOTEX INC"), so "Apotex Inc." finds
   * far fewer files than "Apotex Inc".
   */
  async searchPartyCases(
    search: PartyCaseSearchOptions,
    options: TransportRequestOptions = {},
  ): Promise<FederalCourtCaseSearchResponse> {
    const query = search.partyName.trim();
    if (query.length < 2)
      throw badInput("party_name must contain at least 2 characters");
    const limit = search.limit ?? 25;
    if (!Number.isInteger(limit) || limit < 1 || limit > 100)
      throw badInput("limit must be between 1 and 100");
    if ((search.filedFrom === undefined) !== (search.filedTo === undefined))
      throw badInput("filed_from and filed_to must be supplied together");
    let path = "ProceedingsQueriesPartyInfo";
    const params: Record<string, string> = {
      division: division(search.division),
      name: query,
    };
    if (search.filedFrom !== undefined && search.filedTo !== undefined) {
      const from = isoDate(search.filedFrom, "filed_from");
      const to = isoDate(search.filedTo, "filed_to");
      if (from > to) throw badInput("filed_from must be on or before filed_to");
      path += "Dates";
      params.from = courtDate(from);
      params.to = courtDate(to);
    }
    const result = await this.data(path, params, options);
    let cases = dedupeCases(
      this.parseRows(result.rows, parseCase, path, result.status),
    );
    if (search.patentOnly ?? true) cases = cases.filter(isPatentCase);
    cases.sort((a, b) =>
      (b.filed_date ?? "").localeCompare(a.filed_date ?? ""),
    );
    return {
      query,
      upstream_count: result.count,
      filtered_count: cases.length,
      cases: cases.slice(0, limit),
      provenance: result.provenance,
    };
  }

  /** Case metadata, public parties and counsel, IP names and numbers, and related files. */
  async getCase(
    courtNumber: string,
    divisionCode?: CourtDivision,
    options: TransportRequestOptions = {},
  ): Promise<FederalCourtCaseRecord> {
    const number = normalizeCourtNumber(courtNumber);
    const params = { division: division(divisionCode), courtnumber: number };
    const [caseRows, partyRows, ipRows, relatedRows] = await Promise.all([
      this.data("proceedingQueriesAddInfo", params, options),
      this.data("PublicPartiesListInfo", { courtnumber: number }, options),
      this.data("PartyInfoIntlProp", params, options),
      this.data("RelatedListInfo", { courtnumber: number }, options),
    ]);
    const [first] = this.parseRows(
      caseRows.rows.slice(0, 1),
      parseCase,
      "proceedingQueriesAddInfo",
      caseRows.status,
    );
    if (!first)
      throw new ApiError(
        `Federal Court file not found: ${number}`,
        404,
        "NOT_FOUND",
      );
    return {
      case: first,
      parties: this.parseRows(
        partyRows.rows,
        (row) => {
          const r = PartyRowSchema.parse(row);
          return {
            name: r.PARTY_NAME,
            solicitor_firm: nullable(r.SOLCTR_FIRM),
            solicitor_contact: nullable(r.SOLCTR_CONTACT),
          };
        },
        "PublicPartiesListInfo",
        partyRows.status,
      ),
      intellectual_property: this.parseRows(
        ipRows.rows,
        (row) => {
          const r = IpRowSchema.parse(row);
          return {
            title: nullable(r.INT_PROPERTY_TITLE),
            number:
              r.INT_PROPERTY_NUMBER === null ||
              r.INT_PROPERTY_NUMBER === undefined
                ? null
                : String(r.INT_PROPERTY_NUMBER),
          };
        },
        "PartyInfoIntlProp",
        ipRows.status,
      ),
      related_cases: this.parseRows(
        relatedRows.rows,
        (row) => {
          const r = RelatedRowSchema.parse(row);
          return {
            court_number: r.RELATED_COURT_NO,
            style_of_cause: nullable(r.STYLE_OF_CAUSE),
            nature_en: nullable(r.ENGLISH_NATURE_DESC),
            nature_fr: nullable(r.FRENCH_NATURE_DESC),
          };
        },
        "RelatedListInfo",
        relatedRows.status,
      ),
      provenance: caseRows.provenance,
    };
  }

  /**
   * Recorded docket entries, newest first, with a conservative inferred
   * status computed over every entry (not only the first `limit`).
   */
  async listDocketEntries(
    courtNumber: string,
    search: { division?: CourtDivision; limit?: number } = {},
    options: TransportRequestOptions = {},
  ): Promise<FederalCourtDocketResponse> {
    const limit = search.limit ?? 100;
    if (!Number.isInteger(limit) || limit < 1 || limit > 500)
      throw badInput("limit must be between 1 and 500");
    const number = normalizeCourtNumber(courtNumber);
    const path = "proceedingQueriesRE";
    const result = await this.data(
      path,
      { division: division(search.division), courtnumber: number },
      options,
    );
    const entries = this.parseRows(
      result.rows,
      parseDocketEntry,
      path,
      result.status,
    );
    for (const entry of entries)
      if (entry.can_download && !entry.is_confidential && entry.document_id)
        entry.download_url = `${this.origin}${API}/downloadFileFromAlfresco?foremostNum=${encodeURIComponent(entry.document_id)}`;
    entries.sort((a, b) => b.entry_number - a.entry_number);
    return {
      court_number: number,
      total_count: result.count,
      status: assessDocketStatus(entries),
      entries: entries.slice(0, limit),
      provenance: result.provenance,
    };
  }
}

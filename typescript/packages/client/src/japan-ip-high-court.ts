import { z } from "zod";
import type { Provenance } from "./models.js";
import {
  readXls,
  type XlsCell,
  XlsError,
  xlsSerialDate,
} from "./runtime/xls.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * The Japan Intellectual Property High Court's weekly case lists: one legacy
 * Excel workbook with a sheet of pending and a sheet of recently closed suits
 * against JPO patent and utility-model decisions. No API and no auth.
 */
export const JAPAN_IP_HIGH_COURT_SOURCE =
  "Japan Intellectual Property High Court — Patent and Utility-Model Case Lists";
export const JAPAN_IP_HIGH_COURT_ORIGIN = "https://www.courts.go.jp";
export const JAPAN_IP_HIGH_COURT_WORKBOOK_PATH =
  "/ip/vc-files/ip/jikenitiran.xls";
export const JAPAN_IP_HIGH_COURT_WORKBOOK_URL = `${JAPAN_IP_HIGH_COURT_ORIGIN}${JAPAN_IP_HIGH_COURT_WORKBOOK_PATH}`;
export const JAPAN_IP_HIGH_COURT_PENDING_SHEET = "係属中事件一覧表";
export const JAPAN_IP_HIGH_COURT_CLOSED_SHEET = "終局事件一覧表";
const HEADERS = {
  accept: "application/vnd.ms-excel,application/octet-stream;q=0.9,*/*;q=0.8",
  "accept-language": "ja,en-US;q=0.8,en;q=0.7",
  referer: `${JAPAN_IP_HIGH_COURT_ORIGIN}/ip/`,
  "user-agent":
    "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)",
};
const ERA_START_YEAR: Record<string, number> = {
  令和: 2018,
  平成: 1988,
  昭和: 1925,
};
const CASE_TYPE = /年[（(]([^）)]+)[）)]第$/;

export const JapanIpHighCourtCaseStatusSchema = z.enum(["pending", "closed"]);
export type JapanIpHighCourtCaseStatus = z.infer<
  typeof JapanIpHighCourtCaseStatusSchema
>;
export type JapanIpHighCourtCaseStatusFilter =
  | JapanIpHighCourtCaseStatus
  | "all";

export const JapanIpHighCourtCaseSchema = z.object({
  case_status: JapanIpHighCourtCaseStatusSchema,
  /** e.g. 令和7年（行ケ）第10011号 */
  case_number: z.string(),
  /** Gregorian year from the era year; null for an unknown era. */
  filing_year: z.number().int().nullable(),
  era_name: z.string(),
  era_year: z.number().int(),
  /** The bracketed case-type mark, e.g. 行ケ. */
  case_type: z.string(),
  serial_number: z.number().int(),
  proceeding_type: z.string(),
  /** 特許…, 特願…, 実用新案…, 実願… or 異議… as the court writes it. */
  subject_identifier: z.string(),
  subject_identifier_type: z.enum([
    "patent",
    "patent_application",
    "utility_model",
    "utility_model_application",
    "patent_opposition",
    "other",
  ]),
  division: z.string(),
  /** ISO date; pending cases only, null when not yet scheduled. */
  scheduled_judgment_date: z.iso.date().nullable(),
  /** ISO date; closed cases only. */
  termination_date: z.iso.date().nullable(),
  disposition: z.string().nullable(),
  /** Whether a further appeal was filed (有/無); null when the cell is blank. */
  appeal_filed: z.boolean().nullable(),
  appeal_result: z.string().nullable(),
});
export type JapanIpHighCourtCase = z.infer<typeof JapanIpHighCourtCaseSchema>;

export const JapanIpHighCourtCaseListSchema = z.object({
  /** Latest of the two sheets' as-of dates. */
  as_of_date: z.iso.date().nullable(),
  pending_count: z.number().int(),
  closed_count: z.number().int(),
  cases: z.array(JapanIpHighCourtCaseSchema),
});
export type JapanIpHighCourtCaseList = z.infer<
  typeof JapanIpHighCourtCaseListSchema
>;
export interface JapanIpHighCourtCaseListResult
  extends JapanIpHighCourtCaseList {
  provenance: Provenance;
}

const parseError = (message: string) =>
  new ApiError(message, 200, "INVALID_RESPONSE");

/** Normalize width variants, whitespace and case for exact case-number matching. */
export function normalizeJapanCaseNumber(value: string): string {
  return value.normalize("NFKC").replace(/\s+/gu, "").toLowerCase();
}

/** Python's str() of an xlrd cell value: floats print with a trailing .0. */
const text = (value: XlsCell | undefined): string =>
  typeof value === "number" && Number.isInteger(value)
    ? `${value}.0`
    : String(value ?? "");

function integer(value: XlsCell | undefined, field: string): number {
  if (typeof value === "boolean")
    throw parseError(`Unexpected boolean in ${field}`);
  const number =
    typeof value === "number"
      ? value
      : typeof value === "string" && /^\s*[+-]?\d+\s*$/.test(value)
        ? Number(value)
        : Number.NaN;
  if (!Number.isFinite(number))
    throw parseError(`Could not parse ${field}: ${JSON.stringify(value)}`);
  if (!Number.isInteger(number))
    throw parseError(`Expected an integer in ${field}: ${value}`);
  return number;
}

function excelDate(value: XlsCell | undefined, datemode: 0 | 1): string | null {
  if (value === undefined || value === "") return null;
  const number =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim() !== ""
        ? Number(value)
        : Number.NaN;
  try {
    return xlsSerialDate(number, datemode);
  } catch {
    throw parseError(`Could not parse workbook date: ${JSON.stringify(value)}`);
  }
}

function subjectIdentifierType(
  value: string,
): JapanIpHighCourtCase["subject_identifier_type"] {
  if (value.startsWith("特許")) return "patent";
  if (value.startsWith("特願")) return "patent_application";
  if (value.startsWith("実用新案")) return "utility_model";
  if (value.startsWith("実願")) return "utility_model_application";
  if (value.startsWith("異議")) return "patent_opposition";
  return "other";
}

function caseFields(values: XlsCell[], offset: number) {
  const eraName = text(values[offset]).trim();
  const eraYear = integer(values[offset + 1], "era year");
  const prefix = text(values[offset + 2]).trim();
  const serialNumber = integer(values[offset + 3], "case serial number");
  const suffix = text(values[offset + 4]).trim();
  const start = ERA_START_YEAR[eraName];
  return {
    case_number: `${eraName}${eraYear}${prefix}${serialNumber}${suffix}`,
    filing_year: start === undefined ? null : start + eraYear,
    era_name: eraName,
    era_year: eraYear,
    case_type: CASE_TYPE.exec(prefix)?.[1] ?? prefix.trim(),
    serial_number: serialNumber,
  };
}

function pendingCase(values: XlsCell[], datemode: 0 | 1): JapanIpHighCourtCase {
  const subject = text(values[6]).trim();
  return {
    case_status: "pending",
    ...caseFields(values, 0),
    proceeding_type: text(values[5]).trim(),
    subject_identifier: subject,
    subject_identifier_type: subjectIdentifierType(subject),
    division: `${text(values[7])}${text(values[8])}`.trim(),
    scheduled_judgment_date: excelDate(values[9], datemode),
    termination_date: null,
    disposition: null,
    appeal_filed: null,
    appeal_result: null,
  };
}

function closedCase(values: XlsCell[], datemode: 0 | 1): JapanIpHighCourtCase {
  const subject = text(values[7]).trim();
  const appeal = text(values[11]).trim();
  return {
    case_status: "closed",
    ...caseFields(values, 1),
    proceeding_type: text(values[6]).trim(),
    subject_identifier: subject,
    subject_identifier_type: subjectIdentifierType(subject),
    division: `${text(values[8])}${text(values[9])}`.trim(),
    scheduled_judgment_date: null,
    termination_date: excelDate(values[0], datemode),
    disposition: text(values[10]).trim() || null,
    appeal_filed: appeal === "有" ? true : appeal === "無" ? false : null,
    appeal_result: text(values[12]).trim() || null,
  };
}

/** Parse both sheets of the official workbook into typed case records. */
export function parseJapanIpHighCourtWorkbook(
  data: Uint8Array,
): JapanIpHighCourtCaseList {
  let workbook: ReturnType<typeof readXls>;
  try {
    workbook = readXls(data);
  } catch (error) {
    throw parseError(
      `Could not open Japan IP High Court case workbook${error instanceof XlsError ? `: ${error.message}` : ""}`,
    );
  }
  const sheet = (name: string) =>
    workbook.sheets.find((candidate) => candidate.name === name);
  const pendingSheet = sheet(JAPAN_IP_HIGH_COURT_PENDING_SHEET);
  const closedSheet = sheet(JAPAN_IP_HIGH_COURT_CLOSED_SHEET);
  const missing = [
    JAPAN_IP_HIGH_COURT_CLOSED_SHEET,
    JAPAN_IP_HIGH_COURT_PENDING_SHEET,
  ].filter((name) => !sheet(name));
  if (!pendingSheet || !closedSheet)
    throw parseError(
      `Japan IP High Court workbook is missing sheet(s): ${missing.join(", ")}`,
    );
  const { datemode } = workbook;
  const pending = pendingSheet.rows
    .slice(3)
    .filter((row) => row.length >= 10 && typeof row[3] === "number")
    .map((row) => pendingCase(row, datemode));
  const closed = closedSheet.rows
    .slice(3)
    .filter((row) => row.length >= 13 && typeof row[4] === "number")
    .map((row) => closedCase(row, datemode));
  const asOf = [
    excelDate(pendingSheet.rows[1]?.[8], datemode),
    excelDate(closedSheet.rows[1]?.[11], datemode),
  ].filter((value): value is string => value !== null);
  return {
    as_of_date: asOf.length ? (asOf.sort().at(-1) as string) : null,
    pending_count: pending.length,
    closed_count: closed.length,
    cases: [...pending, ...closed],
  };
}

/** Find one case by normalized case number, or throw NOT_FOUND. */
export function findJapanIpHighCourtCase(
  caseList: JapanIpHighCourtCaseList,
  caseNumber: string,
  caseStatus: JapanIpHighCourtCaseStatusFilter = "all",
): JapanIpHighCourtCase {
  const target = normalizeJapanCaseNumber(caseNumber);
  const found = caseList.cases.find(
    (item) =>
      (caseStatus === "all" || item.case_status === caseStatus) &&
      normalizeJapanCaseNumber(item.case_number) === target,
  );
  if (!found)
    throw new ApiError(
      `Japan IP High Court case not found: ${caseNumber}`,
      404,
      "NOT_FOUND",
    );
  return found;
}

export class JapanIpHighCourtClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      timeoutMs: options.timeoutMs ?? 60_000,
      baseUrl: options.baseUrl ?? JAPAN_IP_HIGH_COURT_ORIGIN,
      sourceName: JAPAN_IP_HIGH_COURT_SOURCE,
      headers: HEADERS,
    });
  }

  /** Download and parse the weekly workbook (both sheets). */
  async listCases(
    options: TransportRequestOptions = {},
  ): Promise<JapanIpHighCourtCaseListResult> {
    const result = await this.http.bytes(
      "GET",
      JAPAN_IP_HIGH_COURT_WORKBOOK_PATH,
      options,
    );
    const parsed = parseJapanIpHighCourtWorkbook(result.data);
    const asOf = parsed.as_of_date ?? "date not published";
    return {
      ...parsed,
      provenance: {
        ...result.provenance,
        as_of_status: `official weekly workbook as of ${asOf}; party names are not published`,
      },
    };
  }

  /** One case by exact (normalized) case number. */
  async getCase(
    caseNumber: string,
    caseStatus: JapanIpHighCourtCaseStatusFilter = "all",
    options: TransportRequestOptions = {},
  ): Promise<JapanIpHighCourtCase> {
    return findJapanIpHighCourtCase(
      await this.listCases(options),
      caseNumber,
      caseStatus,
    );
  }
}

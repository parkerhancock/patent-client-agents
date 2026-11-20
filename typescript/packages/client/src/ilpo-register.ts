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
 * The Israeli trade-mark and patent registers, queried through the CKAN
 * datastore on data.gov.il, where the Ministry of Justice republishes them
 * daily as open data. `datastore_search` answers filters, full-text and
 * field-scoped queries over every row; nothing is downloaded. Column names
 * are Hebrew: the client maps them to English keys and dates to ISO.
 */
export const ILPO_DATASTORE_HOST = "https://data.gov.il";
export const ILPO_REGISTER_SOURCE =
  "Israel Patent Office registers (Ministry of Justice, data.gov.il)";
/** datastore_search accepts larger pages; this bounds one request. */
export const ILPO_MAX_ROWS = 1000;

type Columns = Record<string, string>;
interface Table {
  /** CKAN resource id (stable across the daily refreshes). */
  resource: string;
  /** The parent dataset, for provenance. */
  dataset: string;
  /** The column joining the table to its mark or application. */
  key: string;
  columns: Columns;
}

const TRADEMARK_DATASET = "simaneymisahr";
/** The ten register tables, by Ministry of Justice resource id. */
export const ILPO_TABLES = {
  trademarks: {
    resource: "6284d4a9-fdd4-45c9-a1d6-58143c7d8127",
    dataset: TRADEMARK_DATASET,
    key: "מספר הסימן",
    columns: {
      "מספר הסימן": "mark_number",
      דמות: "has_image",
      "קישור לנסח": "extract_url",
      מצב: "status",
      "לאומי/בינלאומי": "route",
      "מספר הסימן הבינלאומי": "international_registration_number",
      "תיאור סימן עברית": "mark_text_he",
      "תיאור סימן אנגלית": "mark_text_en",
      "תאריך בקשה": "application_date",
      "תאריך רישום": "registration_date",
      "סוג רישום": "mark_type",
      "סוגי ניצה לבקשה": "nice_classes",
      "סוגי וינה לבקשה": "vienna_classes",
      "רשימת סחורות בעברית": "goods_he",
      "רשימת סחורות באנגלית": "goods_en",
      "דין קדימה": "priority_claimed",
      "תאריך תום תוקף": "expiry_date",
      "שם מיופה כח": "agent_name_he",
      "שם מיופה כח אנגלית": "agent_name_en",
      "שם בעל הסימן בעברית": "owner_name_he",
      "שם בעל הסימן באנגלית": "owner_name_en",
      "שם בעל הרשות בעברית": "licensee_name_he",
      "שם בעל הרשות באנגלית": "licensee_name_en",
      "שם מייצג לעניין אכיפת מכס": "customs_representative",
      "מען למכס תאריך התחלה": "customs_address_start_date",
      "כתובת אימייל מייצג מכס": "customs_representative_email",
      "טלפון מייצג מכס": "customs_representative_phone",
      "רישום חיצוני": "foreign_registration",
      "תאריך עדכון אחרון": "last_updated",
    },
  },
  trademarkPriorities: {
    resource: "9ad7f669-ff09-4d43-8d72-7d33b5cba0c9",
    dataset: TRADEMARK_DATASET,
    key: "מספר סימן לאומי",
    columns: {
      "מספר סימן לאומי": "mark_number",
      "סוג דין קדימה": "priority_type",
      "מספר דין קדימה": "priority_number",
      "תאריך דין קדימה": "priority_date",
      סיווג: "class",
      "שם מדינה": "country_he",
      "שם מדינה אנגלית": "country_en",
      "רשימת סחורות בעברית": "goods_he",
      "רשימת סחורות באנגלית": "goods_en",
      "תוצאת הבחינה": "examination_result",
      "הערות הבחינה": "examination_notes",
    },
  },
  trademarkEvents: {
    resource: "118b06b5-3504-4007-b43f-c197fdc5e466",
    dataset: TRADEMARK_DATASET,
    key: "מספר סימן לאומי",
    columns: {
      "מספר סימן לאומי": "mark_number",
      "תאריך אירוע": "event_date",
      "תיאור האירוע בעברית": "event_he",
      "תיאור האירוע באנגלית": "event_en",
      "תאריך פרסום": "publication_date",
    },
  },
  trademarkParties: {
    resource: "d4a365c7-357a-4172-8815-1a6650e848e2",
    dataset: TRADEMARK_DATASET,
    key: "מספר סימן לאומי",
    columns: {
      "מספר סימן לאומי": "mark_number",
      "סוג לקוח": "party_type",
      "מספר לקוח": "party_number",
      "שם לקוח בעברית": "name_he",
      "שם לקוח באנגלית": "name_en",
      "מעמד לקוח": "role",
      "לקוח מוביל בתיק": "lead_party",
    },
  },
  trademarkForeignRegistrations: {
    resource: "d45b945c-7031-42fa-b7f2-a60b96db8c0e",
    dataset: TRADEMARK_DATASET,
    key: "מספר סימן לאומי",
    columns: {
      "מספר סימן לאומי": "mark_number",
      "מספר רישום חיצוני": "foreign_registration_number",
      "תאריך רישום חיצוני": "foreign_registration_date",
      "שם מדינה עברית": "country_he",
      "שם מדינה אנגלית": "country_en",
    },
  },
  trademarkConditions: {
    resource: "ed88a79f-0b17-4cc6-aae4-36047370a69d",
    dataset: TRADEMARK_DATASET,
    key: "מספר סימן לאומי",
    columns: {
      "מספר סימן לאומי": "mark_number",
      "סוג תנאי/הודעה": "condition_type",
      "תיאור בעברית": "text_he",
      "תיאור באנגלית": "text_en",
    },
  },
  patents: {
    resource: "adca9a88-bf91-462a-8a49-62381af9b588",
    dataset: "bakashot_patents",
    key: "מספר בקשה",
    columns: {
      "מספר בקשה": "application_number",
      "תאריך הבקשה": "application_date",
      "תאריך הגשה": "filing_date",
      "שם האמצאה בעברית": "title_he",
      "שם האמצאה באנגלית": "title_en",
      "מספר בקשה בינלאומי": "pct_application_number",
      "מספר פרסום בינלאומי": "pct_publication_number",
      "תאריך פרסום ראשון": "first_publication_date",
      "תאריך פרסום שני": "second_publication_date",
      "תאריך מתן פטנט": "grant_date",
      "סטטוס בקשה/פטנט": "status",
    },
  },
  patentApplicants: {
    resource: "b2b87f6c-832c-410d-a753-c52ec15cd793",
    dataset: "mevakshimpatents",
    key: "מספר בקשה",
    columns: {
      "מספר בקשה": "application_number",
      "שם מבקש בעברית": "name_he",
      "כתובת מבקש בעברית": "address_he",
      "שם מבקש באנגלית": "name_en",
      "כתובת מבקש באנגלית": "address_en",
    },
  },
  patentInventors: {
    resource: "abd0e8c3-0b0d-4581-9166-923a3b21bdda",
    dataset: "mamtziim_patents",
    key: "מספר בקשה",
    columns: {
      "מספר בקשה": "application_number",
      "שם ממציא בעברית": "name_he",
      "שם ממציא באנגלית": "name_en",
      "כתובת ממציא באנגלית": "address_en",
      "כתובת ממציא בעברית": "address_he",
    },
  },
  patentClassifications: {
    resource: "3343e150-79b5-4927-adad-50ebe14925b5",
    dataset: "bakashot_ipc",
    key: "מספר בקשה",
    columns: {
      "מספר בקשה": "application_number",
      "IPC סיווג": "ipc",
      ראשי: "main",
    },
  },
} as const satisfies Record<string, Table>;
export type IlpoTable = keyof typeof ILPO_TABLES;

/** Working English renderings of the register's status values; the Hebrew stays in `status`. */
export const ILPO_STATUS_EN: Record<string, string> = {
  רשום: "registered",
  סגור: "closed",
  "אי תשלום": "not paid",
  "בחינה ראשונה": "first examination",
  "בחינה שנייה": "second examination",
  "ממתין לבחינה": "awaiting examination",
  "ממתין לקבלת החלטה בתיק אחר": "awaiting a decision in another file",
  קובל: "opposed",
  במיון: "being classified",
  "בקשה חדשה": "new application",
  "פרסום שני": "accepted (second publication)",
  פטנט: "granted",
  "בקשה הוזנחה": "abandoned",
  "בקשה סורבה": "refused",
  "פג תוקף": "expired",
  "פקיעת תוקף": "lapsed",
  "פטנט בוטל": "revoked",
  "צו ארכה": "extension order",
  "צו ארכה פג תוקף": "extension order expired",
};
const YES: Record<string, boolean> = {
  כן: true,
  לא: false,
  ראשי: true,
  "": false,
};
const BOOLEAN_COLUMNS = new Set([
  "has_image",
  "priority_claimed",
  "foreign_registration",
  "lead_party",
  "main",
]);
const DATE = /^(\d{2})\/(\d{2})\/(\d{4})$/;

export type IlpoRow = Record<string, unknown>;
/**
 * The export writes "~" for the characters CSV quoting would need: the
 * gershayim of Hebrew abbreviations (בע~מ for בע"מ, ד~ר for ד"ר) and the
 * commas of goods lists ("software~ computers"). Restore both.
 */
export function restorePunctuation(text: string): string {
  return text.replace(/(?<=[א-ת])~(?=[א-ת])/g, '"').replace(/~(?=\s)/g, ",");
}
/** One register row in English: DD/MM/YYYY dates become ISO (the 01/01/1900 placeholder becomes null), כן/לא flags booleans, statuses gain `status_en`, the export's "~" placeholders are restored, and PCT publication numbers regain their WO prefix. */
export function ilpoRow(
  table: IlpoTable,
  raw: Record<string, unknown>,
): IlpoRow {
  const columns: Columns = ILPO_TABLES[table].columns;
  const row: IlpoRow = {};
  for (const [hebrew, english] of Object.entries(columns)) {
    let value = raw[hebrew];
    if (typeof value === "string") {
      const text = restorePunctuation(value.trim());
      value =
        english === "pct_publication_number" && /^\/\d{4}\//.test(text)
          ? `WO${text}`
          : text;
      const date = DATE.exec(value as string);
      if (date)
        value =
          date[3] === "1900" && date[1] === "01" && date[2] === "01"
            ? null
            : `${date[3]}-${date[2]}-${date[1]}`;
      else if (BOOLEAN_COLUMNS.has(english))
        value = YES[value as string] ?? value;
      else if (value === "") value = null;
    }
    row[english] = value ?? null;
    if (english === "status" && typeof value === "string")
      row.status_en = ILPO_STATUS_EN[value] ?? null;
  }
  return row;
}

/**
 * A prefix full-text query over words (Hebrew or Latin letters and digits):
 * each word must begin some token. Plain datastore search misses English
 * words in patent titles ("battery" finds none), while prefix queries find
 * them; anything but letters and digits is dropped, so no query syntax
 * passes through.
 */
export function ilpoPrefixQuery(text: string): string {
  const words = text.match(/[\p{L}\p{N}]+/gu) ?? [];
  if (!words.length)
    throw new TypeError("The query has no words to search for.");
  return words
    .slice(0, 10)
    .map((word) => `${word}:*`)
    .join(" & ");
}

export interface IlpoPage {
  rows: IlpoRow[];
  total: number;
  offset: number;
  more_available: boolean;
  provenance: Provenance;
}
export interface IlpoQuery extends TransportRequestOptions {
  /** Exact matches, by English column name; an array matches any of its values. */
  filters?: Record<
    string,
    string | number | (string | number)[] | null | undefined
  >;
  /** Prefix word search, by English column name. */
  words?: Record<string, string | null | undefined>;
  /** Whole-token matches, by English column name (Nice class "3" must not match "32"). */
  tokens?: Record<string, string | number | null | undefined>;
  /** Prefix word search across every column. */
  text?: string | null;
  /** English column name, with " desc" for descending. */
  sort?: string;
  limit?: number;
  offset?: number;
}

export type IlpoErrorCode = "UPSTREAM_ERROR" | "INVALID_RESPONSE";
export class IlpoRegisterError extends ApiError {
  override name = "IlpoRegisterError";
  constructor(message: string, status: number, code: IlpoErrorCode) {
    super(message, status, code);
  }
}

const resultSchema = z.looseObject({
  success: z.literal(true),
  result: z.looseObject({
    total: z.number().int().nonnegative(),
    records: z.array(z.looseObject({})),
  }),
});

function hebrew(table: IlpoTable, english: string): string {
  const entry = Object.entries(ILPO_TABLES[table].columns as Columns).find(
    ([, name]) => name === english,
  );
  if (!entry)
    throw new TypeError(
      `${table} has no column "${english}". Columns: ${Object.values(ILPO_TABLES[table].columns).join(", ")}.`,
    );
  return entry[0];
}

/** Israel's trade-mark and patent registers, searched in place on data.gov.il. */
export class IlpoRegisterClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey" | "baseUrl"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      timeoutMs: 60_000,
      ...options,
      baseUrl: ILPO_DATASTORE_HOST,
      sourceName: ILPO_REGISTER_SOURCE,
      cache: { name: "ilpo_register" },
      headers: {
        accept: "application/json",
        "user-agent": "patent-client-agents/0 (+https://patentclient.com)",
      },
    });
  }

  /** One page of a table. Column names are the English ones; values are as the register writes them. */
  async query(table: IlpoTable, query: IlpoQuery = {}): Promise<IlpoPage> {
    const spec = ILPO_TABLES[table];
    if (!spec) throw new TypeError(`Unknown ILPO table: ${table}`);
    const limit = z
      .number()
      .int()
      .min(1)
      .max(ILPO_MAX_ROWS)
      .parse(query.limit ?? 25);
    const offset = z
      .number()
      .int()
      .min(0)
      .parse(query.offset ?? 0);
    const filters = Object.fromEntries(
      Object.entries(query.filters ?? {})
        .filter(
          ([, value]) => value !== undefined && value !== null && value !== "",
        )
        .map(([name, value]) => [hebrew(table, name), value]),
    );
    const words = Object.fromEntries(
      Object.entries(query.words ?? {})
        .filter(([, value]) => value?.trim())
        .map(([name, value]) => [
          hebrew(table, name),
          ilpoPrefixQuery(value as string),
        ]),
    );
    for (const [name, value] of Object.entries(query.tokens ?? {})) {
      const parts = String(value ?? "").match(/[\p{L}\p{N}]+/gu) ?? [];
      if (parts.length) words[hebrew(table, name)] = parts.join(" & ");
    }
    if (query.text?.trim() && Object.keys(words).length)
      throw new TypeError(
        "Search either all columns (text) or named columns (words), not both.",
      );
    const q = query.text?.trim()
      ? ilpoPrefixQuery(query.text)
      : Object.keys(words).length
        ? JSON.stringify(words)
        : undefined;
    const [sortColumn, direction] = (query.sort ?? "").trim().split(/\s+/);
    const params: Record<string, string> = {
      resource_id: spec.resource,
      limit: String(limit),
      offset: String(offset),
    };
    if (Object.keys(filters).length) params.filters = JSON.stringify(filters);
    if (q) {
      params.q = q;
      params.plain = "false";
    }
    if (sortColumn)
      params.sort = `"${hebrew(table, sortColumn)}" ${direction === "desc" ? "desc" : "asc"}`;
    const {
      filters: _f,
      words: _w,
      text: _t,
      sort: _s,
      limit: _l,
      offset: _o,
      ...request
    } = query;
    let result: Awaited<ReturnType<GenericHttpTransport["json"]>>;
    try {
      result = await this.http.json("GET", "/api/3/action/datastore_search", {
        ...request,
        searchParams: params,
      });
    } catch (error) {
      if (error instanceof ApiError)
        throw new IlpoRegisterError(
          `data.gov.il returned HTTP ${error.status} for ${table}.`,
          error.status,
          "UPSTREAM_ERROR",
        );
      throw error;
    }
    const parsed = resultSchema.safeParse(result.data);
    if (!parsed.success)
      throw new IlpoRegisterError(
        `data.gov.il returned an unexpected response for ${table}.`,
        result.status,
        "INVALID_RESPONSE",
      );
    const rows = parsed.data.result.records.map((raw) => ilpoRow(table, raw));
    return {
      rows,
      total: parsed.data.result.total,
      offset,
      more_available: offset + rows.length < parsed.data.result.total,
      provenance: {
        ...result.provenance,
        source_url: `${ILPO_DATASTORE_HOST}/dataset/${spec.dataset}`,
      },
    };
  }

  /**
   * Every row of `table` for the given marks or applications, in one request
   * per page of ILPO_MAX_ROWS. Rows keep the table's order.
   */
  async rowsFor(
    table: IlpoTable,
    keys: number[],
    options: TransportRequestOptions = {},
  ): Promise<IlpoRow[]> {
    if (!keys.length) return [];
    const keyColumn = (ILPO_TABLES[table].columns as Columns)[
      ILPO_TABLES[table].key
    ] as string;
    const rows: IlpoRow[] = [];
    for (let offset = 0; ; offset += ILPO_MAX_ROWS) {
      const page = await this.query(table, {
        ...options,
        filters: { [keyColumn]: keys },
        limit: ILPO_MAX_ROWS,
        offset,
      });
      rows.push(...page.rows);
      if (!page.more_available) return rows;
    }
  }
}

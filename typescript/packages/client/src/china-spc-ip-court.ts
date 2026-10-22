import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import { all, first, parseDocument, squash } from "./google-patents/dom.js";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  HttpResponseError,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * Public hearing notices and full-site search on the website of China's
 * Supreme People's Court Intellectual Property Court (最高人民法院知识产权法庭),
 * https://ipc.court.gov.cn. The site publishes no API; these are HTML pages.
 */
export const CHINA_SPC_IP_COURT_SOURCE =
  "Supreme People's Court Intellectual Property Court";
export const CHINA_SPC_IP_COURT_ORIGIN = "https://ipc.court.gov.cn";
export const CHINA_SPC_HEARING_INDEX_PATH = "/zh-cn/news/more-4-15.html";
export const CHINA_SPC_HEARING_INDEX_URL = `${CHINA_SPC_IP_COURT_ORIGIN}${CHINA_SPC_HEARING_INDEX_PATH}`;
export const CHINA_SPC_SEARCH_PATH = "/zh-cn/search.html";
const USER_AGENT =
  "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)";

export const ChinaSpcIpPartySchema = z.object({
  role_zh: z.string(),
  role_en: z.string(),
  name: z.string(),
});
export type ChinaSpcIpParty = z.infer<typeof ChinaSpcIpPartySchema>;

export const ChinaSpcIpHearingIndexItemSchema = z.object({
  notice_id: z.string(),
  title: z.string(),
  /** YYYY-MM-DD the notice was posted, or null when unparseable. */
  published_date: z.iso.date().nullable(),
  notice_url: z.string(),
});
export type ChinaSpcIpHearingIndexItem = z.infer<
  typeof ChinaSpcIpHearingIndexItemSchema
>;

export const ChinaSpcIpHearingIndexResponseSchema = z.object({
  page: z.number().int().positive(),
  total_pages: z.number().int().positive(),
  notices: z.array(ChinaSpcIpHearingIndexItemSchema),
});
export type ChinaSpcIpHearingIndexResponse = z.infer<
  typeof ChinaSpcIpHearingIndexResponseSchema
>;

export const ChinaSpcIpHearingNoticeSchema = z.object({
  notice_id: z.string(),
  title: z.string(),
  /** Site-local (China Standard Time) timestamp, YYYY-MM-DDTHH:MM:SS, without offset. */
  published_at: z.iso.datetime({ local: true }).nullable(),
  /** YYYY-MM-DD from the notice title. */
  hearing_date: z.iso.date().nullable(),
  /** The Chinese time phrase, e.g. 上午九时三十分. */
  hearing_time_text: z.string().nullable(),
  venue: z.string().nullable(),
  /** Cause of action, e.g. 侵害发明专利权纠纷. */
  dispute_type: z.string().nullable(),
  party_clause: z.string().nullable(),
  parties: z.array(ChinaSpcIpPartySchema),
  body_text: z.string(),
  notice_url: z.string(),
});
export type ChinaSpcIpHearingNotice = z.infer<
  typeof ChinaSpcIpHearingNoticeSchema
>;

export const ChinaSpcIpSiteSearchHitSchema = z.object({
  title: z.string(),
  snippet: z.string().nullable(),
  /** Site-local timestamp, YYYY-MM-DDTHH:MM:SS, without offset. */
  published_at: z.iso.datetime({ local: true }).nullable(),
  url: z.string(),
  is_hearing_notice: z.boolean(),
});
export type ChinaSpcIpSiteSearchHit = z.infer<
  typeof ChinaSpcIpSiteSearchHitSchema
>;

export const ChinaSpcIpSiteSearchResponseSchema = z.object({
  query: z.string(),
  page: z.number().int().positive(),
  total_count: z.number().int().nonnegative(),
  total_pages: z.number().int().positive(),
  hits: z.array(ChinaSpcIpSiteSearchHitSchema),
});
export type ChinaSpcIpSiteSearchResponse = z.infer<
  typeof ChinaSpcIpSiteSearchResponseSchema
>;

export interface ChinaSpcIpResult<T> {
  data: T;
  provenance: Provenance;
}

const NOTICE_ID = /view-(\d+)\.html/;
const ARABIC_DATE = /(20\d{2})年(\d{1,2})月(\d{1,2})日/;
const PUBLISHED =
  /发布时间[：:]\s*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?)/;
// Notices before about 2021 write the hour with 点 (上午九点) rather than 时.
const TIME =
  /(?:上午|下午|晚间|中午)?[〇零一二三四五六七八九十百两0-9]+[时点](?:[〇零一二三四五六七八九十百两0-9]+分)?/;
const VENUE = /(?:时|分|点)在(.+?)公开开庭审理/;
/** The case clause; notices hearing several related cases end 两案, 四案 and so on. */
const CASE_CLAUSE = /公开开庭审理(.+?)[一二两三四五六七八九十0-9]+案/;
const ROLES =
  "上诉人|被上诉人|一审原告|一审被告|一审第三人|原审原告|原审被告|原审第三人|再审申请人|申请再审人|被申请人|原告|被告|第三人";
const ROLE = new RegExp(`(${ROLES})(.+?)(?=(?:与|及)?(?:${ROLES})|$)`, "g");
const ROLE_EN: Record<string, string> = {
  上诉人: "appellant",
  被上诉人: "appellee",
  一审原告: "first_instance_plaintiff",
  一审被告: "first_instance_defendant",
  一审第三人: "first_instance_third_party",
  原审原告: "original_plaintiff",
  原审被告: "original_defendant",
  原审第三人: "original_third_party",
  再审申请人: "retrial_applicant",
  申请再审人: "retrial_applicant",
  被申请人: "respondent",
  原告: "plaintiff",
  被告: "defendant",
  第三人: "third_party",
};
const DISPUTE_STARTERS = [
  "确认不侵害",
  "侵害",
  "发明专利",
  "实用新型",
  "外观设计",
  "专利权",
  "集成电路",
  "计算机软件",
  "技术合同",
  "技术秘密",
  "商业秘密",
  "标准必要专利",
  "垄断",
  "植物新品种",
];
const PAGER_PAGE = /(?:[?&]page=|\/page\/)(\d+)/;

/**
 * Remove whitespace from Chinese notice text. Python strips every space,
 * which glues Latin party names together ("Koninklijke Philips N.V." becomes
 * "KoninklijkePhilipsN.V."); this keeps one space between two ASCII
 * characters and removes the rest.
 */
export function normalizeNoticeText(value: string): string {
  return value
    .replace(/\s+/g, " ")
    .replace(/ (?=[^\x21-\x7e])|(?<=[^\x21-\x7e]) /g, "")
    .trim();
}

const trimChars = (value: string, chars: string) => {
  let start = 0;
  let end = value.length;
  while (start < end && chars.includes(value[start] as string)) start++;
  while (end > start && chars.includes(value[end - 1] as string)) end--;
  return value.slice(start, end);
};

/** "2026-10-20 14:27:27" or "2026-10-20" -> local ISO datetime, else null. */
function localDateTime(value: string | undefined): string | null {
  const match = /^\s*(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}:\d{2}))?\s*$/.exec(
    value ?? "",
  );
  if (!match || !validDate(match[1] as string)) return null;
  return `${match[1]}T${match[2] ?? "00:00:00"}`;
}
function validDate(value: string): boolean {
  const date = new Date(`${value}T00:00:00Z`);
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(date.getTime()) &&
    date.toISOString().slice(0, 10) === value
  );
}

/** The numeric notice ID in a /zh-cn/news/view-<id>.html URL. */
export function chinaSpcNoticeId(url: string): string {
  const match = NOTICE_ID.exec(url);
  if (!match)
    throw new ApiError(
      `Could not parse hearing-notice ID from ${url}`,
      200,
      "INVALID_RESPONSE",
    );
  return match[1] as string;
}

/** Highest page number the pager names, counting the current page; 1 without a pager. */
function pagerTotal(root: Document): number {
  let total = 1;
  for (const element of all(
    root,
    ".pagination a[href], .pagination .current",
  )) {
    const href = element.getAttribute("href");
    const value = href
      ? PAGER_PAGE.exec(href)?.[1]
      : /^\d+$/.exec(element.textContent?.trim() ?? "")?.[0];
    if (value) total = Math.max(total, Number(value));
  }
  return total;
}

const absolute = (href: string, baseUrl: string) => new URL(href, baseUrl).href;

/**
 * Parse one page of the hearing-notice index (开庭公告). `total_pages` comes
 * from the pager; a page beyond it is answered upstream with the last page,
 * so its notices are dropped.
 */
export function parseHearingIndex(
  html: string,
  options: { page?: number; baseUrl?: string } = {},
): ChinaSpcIpHearingIndexResponse {
  const page = options.page ?? 1;
  const baseUrl = options.baseUrl ?? CHINA_SPC_IP_COURT_ORIGIN;
  const document = parseDocument(html);
  const list = first(document, "div.listing");
  if (!list)
    throw new ApiError(
      "SPC IP Court hearing index has no notice listing; the page layout may have changed.",
      200,
      "INVALID_RESPONSE",
    );
  const notices: ChinaSpcIpHearingIndexItem[] = [];
  for (const row of all(list, "li")) {
    const anchor = all(row, "a[href]").find((a) =>
      (a.getAttribute("href") ?? "").includes("/news/view-"),
    );
    if (!anchor) continue;
    const url = absolute(anchor.getAttribute("href") ?? "", baseUrl);
    const dateText = all(row, "span.right")
      .map((span) => span.textContent ?? "")
      .join("")
      .trim();
    notices.push({
      notice_id: chinaSpcNoticeId(url),
      title: squash(anchor.textContent ?? ""),
      published_date: validDate(dateText) ? dateText : null,
      notice_url: url,
    });
  }
  const totalPages = pagerTotal(document);
  return {
    page,
    total_pages: totalPages,
    notices: page > totalPages ? [] : notices,
  };
}

/**
 * Split "上诉人甲与被上诉人乙侵害发明专利权纠纷" into the party clause and the
 * cause of action, as Python's _split_case_clause does.
 */
export function splitCaseClause(
  caseClause: string,
): [string | null, string | null] {
  for (const starter of DISPUTE_STARTERS) {
    const index = caseClause.lastIndexOf(starter);
    if (index >= 0 && caseClause.endsWith("纠纷"))
      return [
        caseClause.slice(0, index).replace(/[，,]+$/, ""),
        caseClause.slice(index),
      ];
  }
  return [caseClause || null, null];
}

/** Party roles and names from a party clause, in order. */
export function parseParties(partyClause: string | null): ChinaSpcIpParty[] {
  if (!partyClause) return [];
  const parties: ChinaSpcIpParty[] = [];
  for (const match of partyClause.matchAll(ROLE)) {
    const role = match[1] as string;
    const name = trimChars(match[2] as string, "与及、，, ");
    if (name)
      parties.push({ role_zh: role, role_en: ROLE_EN[role] as string, name });
  }
  return parties;
}

/** True when the page is a hearing notice: its title, not just the site menu, names 开庭公告. */
export function isHearingNoticePage(html: string): boolean {
  const title = first(parseDocument(html), "div.detail h2");
  return (title?.textContent ?? "").includes("开庭公告");
}

/** Parse one official scheduled-hearing notice page. */
export function parseHearingNotice(
  html: string,
  options: { noticeUrl: string },
): ChinaSpcIpHearingNotice {
  const document = parseDocument(html);
  const title = first(document, "div.detail h2");
  const body = first(document, "div.detail div.txt");
  if (!title || !body)
    throw new ApiError(
      `Unexpected SPC IP Court hearing-notice shape: ${options.noticeUrl}`,
      200,
      "INVALID_RESPONSE",
    );
  const titleText = squash(title.textContent ?? "");
  const bodyText = normalizeNoticeText(body.textContent ?? "");
  const message = all(document, "div.detail div.message")
    .map((element) => element.textContent ?? "")
    .join(" ");
  const published = PUBLISHED.exec(message)?.[1];

  let hearingDate: string | null = null;
  const dateMatch = ARABIC_DATE.exec(titleText);
  if (dateMatch) {
    const [, y, m, d] = dateMatch as unknown as [
      string,
      string,
      string,
      string,
    ];
    const iso = `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
    hearingDate = validDate(iso) ? iso : null;
  }
  const caseClause = CASE_CLAUSE.exec(bodyText)?.[1];
  const [partyClause, disputeType] = caseClause
    ? splitCaseClause(caseClause)
    : [null, null];
  return {
    notice_id: chinaSpcNoticeId(options.noticeUrl),
    title: titleText,
    published_at: localDateTime(published),
    hearing_date: hearingDate,
    hearing_time_text: TIME.exec(bodyText)?.[0] ?? null,
    venue: VENUE.exec(bodyText)?.[1] ?? null,
    dispute_type: disputeType,
    party_clause: partyClause,
    parties: parseParties(partyClause),
    body_text: bodyText,
    notice_url: options.noticeUrl,
  };
}

/**
 * Parse one page of the site's full-text search. The pager uses path-style
 * links (/search/index/content/<q>/lang/zh-cn/page/28.html); a page beyond
 * the last is answered upstream with another page, so its hits are dropped.
 */
export function parseSiteSearch(
  html: string,
  options: { query: string; page?: number; baseUrl?: string },
): ChinaSpcIpSiteSearchResponse {
  const page = options.page ?? 1;
  const baseUrl = options.baseUrl ?? CHINA_SPC_IP_COURT_ORIGIN;
  const document = parseDocument(html);
  const container = first(document, "div.search_list");
  if (!container)
    throw new ApiError(
      "SPC IP Court search page has no result list; the page layout may have changed.",
      200,
      "INVALID_RESPONSE",
    );
  const hits: ChinaSpcIpSiteSearchHit[] = [];
  for (const row of all(container, "ul.list > li")) {
    const anchor = Array.from(row.children).find(
      (child) => child.tagName === "A" && child.hasAttribute("href"),
    );
    if (!anchor) continue;
    const title = squash(anchor.textContent ?? "");
    const snippet = Array.from(row.children).find(
      (child) => child.tagName === "SPAN",
    );
    const date = Array.from(row.children).find(
      (child) => child.tagName === "I" && child.classList.contains("date"),
    );
    hits.push({
      title,
      snippet: snippet ? squash(snippet.textContent ?? "") : null,
      published_at: localDateTime(date?.textContent ?? undefined),
      url: absolute(anchor.getAttribute("href") ?? "", baseUrl),
      is_hearing_notice: title.includes("开庭公告"),
    });
  }
  const count = (first(container, ".count .num")?.textContent ?? "").trim();
  const totalPages = pagerTotal(document);
  return {
    query: options.query,
    page,
    total_count: /^\d+$/.test(count) ? Number(count) : hits.length,
    total_pages: totalPages,
    hits: page > totalPages ? [] : hits,
  };
}

const invalidInput = (message: string) =>
  new ApiError(message, 400, "INVALID_INPUT");
const positivePage = (page: number) => {
  if (!Number.isSafeInteger(page) || page < 1)
    throw invalidInput("page must be at least 1");
  return page;
};

export class ChinaSpcIpCourtClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private readonly baseUrl: string;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    super();
    this.baseUrl = (options.baseUrl ?? CHINA_SPC_IP_COURT_ORIGIN).replace(
      /\/+$/,
      "",
    );
    this.http = new GenericHttpTransport({
      ...options,
      timeoutMs: options.timeoutMs ?? 60_000,
      baseUrl: this.baseUrl,
      sourceName: CHINA_SPC_IP_COURT_SOURCE,
      cache: { name: "china_spc_ip_court" },
      headers: {
        accept: "text/html,application/xhtml+xml",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "user-agent": USER_AGENT,
      },
    });
  }

  /** One page of the hearing-notice index, newest first, five notices a page. */
  async listHearingIndex(
    page = 1,
    options: TransportRequestOptions = {},
  ): Promise<ChinaSpcIpResult<ChinaSpcIpHearingIndexResponse>> {
    positivePage(page);
    const result = await this.http.text("GET", CHINA_SPC_HEARING_INDEX_PATH, {
      ...options,
      ...(page > 1 ? { searchParams: { page } } : {}),
    });
    return {
      data: parseHearingIndex(result.data, { page, baseUrl: this.baseUrl }),
      provenance: result.provenance,
    };
  }

  /**
   * One scheduled-hearing notice by numeric ID ("6173"), official URL
   * (https://ipc.court.gov.cn/zh-cn/news/view-6173.html) or view path.
   * Pages that exist but are not hearing notices, and the site's error page,
   * raise NOT_FOUND.
   */
  async getHearingNotice(
    notice: string,
    options: TransportRequestOptions = {},
  ): Promise<ChinaSpcIpResult<ChinaSpcIpHearingNotice>> {
    const value = notice.trim();
    let id: string;
    if (/^\d+$/.test(value)) id = value;
    else if (/^https?:/i.test(value)) {
      const match = new RegExp(
        `^${this.baseUrl.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/zh-cn/news/view-(\\d+)\\.html$`,
      ).exec(value);
      if (!match)
        throw invalidInput(
          "notice URL must use the official SPC IP Court host",
        );
      id = match[1] as string;
    } else {
      const match = NOTICE_ID.exec(value);
      if (!match)
        throw invalidInput(
          "notice must be a numeric notice ID or official notice URL",
        );
      id = match[1] as string;
    }
    const path = `/zh-cn/news/view-${id}.html`;
    const notFound = () =>
      new ApiError(
        `SPC IP Court hearing notice not found: ${value}`,
        404,
        "NOT_FOUND",
      );
    let result: Awaited<ReturnType<GenericHttpTransport["text"]>>;
    try {
      result = await this.http.text("GET", path, {
        ...options,
        readErrorBody: true,
      });
    } catch (error) {
      // A missing article is served as the site's error page (哎呀,出错了) with HTTP 451.
      if (
        error instanceof HttpResponseError &&
        (error.status === 404 ||
          (error.status === 451 && error.bodyText.includes("出错了")))
      )
        throw notFound();
      throw error;
    }
    if (!isHearingNoticePage(result.data)) throw notFound();
    return {
      data: parseHearingNotice(result.data, {
        noticeUrl: `${this.baseUrl}${path}`,
      }),
      provenance: result.provenance,
    };
  }

  /**
   * One page of the site's full-text search (20 results a page, oldest
   * first). Covers news, case write-ups and hearing notices.
   */
  async searchSite(
    query: string,
    page = 1,
    options: TransportRequestOptions = {},
  ): Promise<ChinaSpcIpResult<ChinaSpcIpSiteSearchResponse>> {
    const term = query.trim();
    if ([...term].length < 2)
      throw invalidInput("query must contain at least 2 characters");
    positivePage(page);
    const result = await this.http.text("GET", CHINA_SPC_SEARCH_PATH, {
      ...options,
      searchParams: page > 1 ? { content: term, page } : { content: term },
    });
    return {
      data: parseSiteSearch(result.data, {
        query: term,
        page,
        baseUrl: this.baseUrl,
      }),
      provenance: result.provenance,
    };
  }
}

import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  ChinaSpcIpCourtClient,
  type ChinaSpcIpHearingIndexResponse,
  type ChinaSpcIpHearingNotice,
  type ChinaSpcIpResult,
  type ChinaSpcIpSiteSearchResponse,
} from "../packages/client/src/index.js";
import {
  getChinaSpcHearingNotices,
  searchChinaSpcCourtSite,
  searchChinaSpcHearingNotices,
} from "../packages/mcp/src/china-spc-ip-court.js";

export const chinaSpcCassette = resolve(
  import.meta.dir,
  "cassettes",
  "china-spc-ip-court.yaml",
);

export interface ChinaSpcRecording {
  /** Index pages 1 and 2, as fetched by the hearing search tool. */
  indexes: ChinaSpcIpResult<ChinaSpcIpHearingIndexResponse>[];
  /** Every notice on those two pages, in index order. */
  notices: ChinaSpcIpResult<ChinaSpcIpHearingNotice>[];
  /** search_china_spc_ip_hearing_notices(pages=2, future_only=false, full=true). */
  hearingSearch: Awaited<ReturnType<typeof searchChinaSpcHearingNotices>>;
  /** Index page 9999, which the site answers with its last page. */
  beyondIndex: ChinaSpcIpResult<ChinaSpcIpHearingIndexResponse>;
  /** get_china_spc_ip_hearing_notice with an official URL, a non-notice article (48) and a missing ID. */
  get: Awaited<ReturnType<typeof getChinaSpcHearingNotices>>;
  /** search_china_spc_ip_court_site for 芯片 (one page of 12). */
  siteSearch: Awaited<ReturnType<typeof searchChinaSpcCourtSite>>;
  /** Page 2 of the 专利 search (28 pages). */
  patentPage2: ChinaSpcIpResult<ChinaSpcIpSiteSearchResponse>;
  /** Page 99 of 芯片, which the site answers with page 1. */
  beyondSearch: ChinaSpcIpResult<ChinaSpcIpSiteSearchResponse>;
}

/** Wrap a client so the hearing search tool's index and notice fetches are kept. */
function capturing(client: ChinaSpcIpCourtClient) {
  const indexes: ChinaSpcIpResult<ChinaSpcIpHearingIndexResponse>[] = [];
  const notices = new Map<string, ChinaSpcIpResult<ChinaSpcIpHearingNotice>>();
  const proxy = {
    listHearingIndex: async (page: number) => {
      const result = await client.listHearingIndex(page);
      indexes[page - 1] = result;
      return result;
    },
    getHearingNotice: async (id: string) => {
      const result = await client.getHearingNotice(id);
      notices.set(id, result);
      return result;
    },
  } as unknown as ChinaSpcIpCourtClient;
  return { proxy, indexes, notices };
}

/**
 * Replay (default) or record one session against ipc.court.gov.cn with the
 * project's honest user agent. No URL is requested twice.
 */
export async function chinaSpcRecording(
  record = false,
): Promise<ChinaSpcRecording> {
  if (!record && !existsSync(chinaSpcCassette))
    throw new Error("Missing China SPC IP Court cassette.");
  let result: ChinaSpcRecording | undefined;
  await useCassette(
    chinaSpcCassette,
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
      filterHeaders: ["set-cookie"],
    },
    async () => {
      const client = new ChinaSpcIpCourtClient({ retryLimit: 0 });
      const capture = capturing(client);
      const hearingSearch = await searchChinaSpcHearingNotices(capture.proxy, {
        query: null,
        pages: 2,
        future_only: false,
        limit: 100,
        full: true,
      });
      const notices = capture.indexes
        .flatMap((index) => index.data.notices)
        .map((stub) => capture.notices.get(stub.notice_id))
        .filter((notice) => notice !== undefined);
      const beyondIndex = await client.listHearingIndex(9999);
      const get = await getChinaSpcHearingNotices(
        client,
        ["https://ipc.court.gov.cn/zh-cn/news/view-5999.html", "48", "999999"],
        true,
      );
      const siteSearch = await searchChinaSpcCourtSite(client, {
        query: "芯片",
        page: 1,
        hearing_notices_only: false,
        limit: 25,
      });
      const patentPage2 = await client.searchSite("专利", 2);
      const beyondSearch = await client.searchSite("芯片", 99);
      result = {
        indexes: capture.indexes,
        notices,
        hearingSearch,
        beyondIndex,
        get,
        siteSearch,
        patentPage2,
        beyondSearch,
      };
    },
  );
  return result as ChinaSpcRecording;
}

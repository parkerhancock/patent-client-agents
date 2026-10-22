import { beforeAll, expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import {
  ChinaSpcIpCourtClient,
  type ChinaSpcIpHearingNotice,
  ChinaSpcIpHearingNoticeSchema,
  normalizeNoticeText,
  parseHearingIndex,
  parseHearingNotice,
  parseSiteSearch,
  splitCaseClause,
} from "../packages/client/src/index.js";
import {
  chinaToday,
  searchChinaSpcHearingNotices,
} from "../packages/mcp/src/china-spc-ip-court.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  type ChinaSpcRecording,
  chinaSpcRecording,
} from "./china-spc-ip-court-recordings.js";

let recording: ChinaSpcRecording;
beforeAll(async () => {
  recording = await chinaSpcRecording();
});

test("the recorded hearing index pages and notices parse", () => {
  const [first, second] = recording.indexes;
  expect(first?.data).toMatchObject({ page: 1, total_pages: 394 });
  expect(second?.data.page).toBe(2);
  expect(first?.data.notices).toHaveLength(5);
  expect(first?.data.notices[0]).toEqual({
    notice_id: "6173",
    title: "最高人民法院知识产权法庭2026年10月22日开庭公告",
    published_date: "2026-10-20",
    notice_url: "https://ipc.court.gov.cn/zh-cn/news/view-6173.html",
  });
  expect(first?.provenance.source_url).toBe(
    "https://ipc.court.gov.cn/zh-cn/news/more-4-15.html",
  );
  expect(second?.provenance.source_url).toBe(
    "https://ipc.court.gov.cn/zh-cn/news/more-4-15.html?page=2",
  );
  expect(recording.notices).toHaveLength(10);
  for (const notice of recording.notices) {
    ChinaSpcIpHearingNoticeSchema.parse(notice.data);
    expect(notice.data.dispute_type).toEndWith("纠纷");
    expect(notice.data.parties.length).toBeGreaterThanOrEqual(2);
    expect(notice.data.hearing_time_text).toBeString();
    expect(notice.data.venue).toContain("法庭");
  }
  expect(recording.notices[0]?.data).toMatchObject({
    notice_id: "6173",
    published_at: "2026-10-20T14:27:27",
    hearing_date: "2026-10-22",
    hearing_time_text: "上午十时十五分",
    venue: "济南知识产权法庭第一法庭",
    dispute_type: "侵害植物新品种权纠纷",
    parties: [
      {
        role_zh: "上诉人",
        role_en: "appellant",
        name: "菏泽市定陶区崇垒农业技术服务部、夏红光",
      },
      {
        role_zh: "被上诉人",
        role_en: "appellee",
        name: "河北冀青农业科技有限公司",
      },
    ],
  });
});

test("the hearing search tool returns every recorded notice, newest hearing first", () => {
  const { hearingSearch } = recording;
  expect(hearingSearch.items).toHaveLength(10);
  const dates = hearingSearch.items.map((item) => String(item.hearing_date));
  expect(dates).toEqual([...dates].sort().reverse());
  expect(hearingSearch.items[0]).toHaveProperty("body_text");
  expect(hearingSearch.more_available).toBe(true);
  expect(hearingSearch.provenance).toMatchObject({
    source_name:
      "Supreme People's Court Intellectual Property Court — Hearing Notices",
    as_of_status: "scheduled hearings; not authoritative case status",
    connector_version: "0.1.0",
  });
});

test("a page past the end, which the site answers with its last page, is empty", () => {
  expect(recording.beyondIndex.data).toEqual({
    page: 9999,
    total_pages: 394,
    notices: [],
  });
  expect(recording.beyondSearch.data.hits).toEqual([]);
  expect(recording.beyondSearch.data.total_pages).toBe(1);
});

test("a non-notice article and a missing ID are not found", () => {
  const { get } = recording;
  expect(get.items.map((item) => item.notice_id)).toEqual(["5999"]);
  expect(get.items[0]).toMatchObject({
    hearing_date: "2026-08-21",
    dispute_type: "发明专利权无效行政纠纷",
  });
  expect(get.not_found).toEqual(["48", "999999"]);
  expect(get.summary).toBe(
    "Fetched 1 of 3 official China SPC IP Court hearing notices. Not found: 48, 999999.",
  );
});

test("site search reads counts and the path-style pager", () => {
  const { siteSearch, patentPage2 } = recording;
  expect(siteSearch.items).toHaveLength(12);
  expect(siteSearch.more_available).toBe(false);
  expect(siteSearch.next_cursor).toBeNull();
  expect(siteSearch.items[0]).toMatchObject({
    url: "https://ipc.court.gov.cn/zh-cn/news/view-1161.html",
    published_at: "2021-04-07T11:11:13",
    is_hearing_notice: false,
  });
  expect(siteSearch.provenance.source_url).toBe(
    "https://ipc.court.gov.cn/zh-cn/search.html?content=%E8%8A%AF%E7%89%87",
  );
  expect(patentPage2.data).toMatchObject({
    query: "专利",
    page: 2,
    total_count: 556,
    total_pages: 28,
  });
  expect(patentPage2.data.hits).toHaveLength(20);
});

interface FixtureNotice {
  html: string;
  python: ChinaSpcIpHearingNotice;
}
const fixture = JSON.parse(
  readFileSync(
    join(import.meta.dir, "fixtures", "china-spc-ip-court", "notices.json"),
    "utf8",
  ),
) as { notices: Record<string, FixtureNotice> };
const parseFixture = (id: string) =>
  parseHearingNotice((fixture.notices[id] as FixtureNotice).html, {
    noticeUrl: `https://ipc.court.gov.cn/zh-cn/news/view-${id}.html`,
  });

test("real notices parse as Python does, apart from the documented fixes", () => {
  for (const [id, { python }] of Object.entries(fixture.notices)) {
    const notice = parseFixture(id);
    const same = [
      "notice_id",
      "title",
      "published_at",
      "hearing_date",
      "notice_url",
    ] as const;
    for (const key of same) expect(notice[key]).toEqual(python[key]);
  }
  // Older notices write the hour with 点.
  expect(parseFixture("997")).toMatchObject({
    hearing_time_text: "上午九点",
    venue: "最高人民法院知产法庭第九法庭",
    dispute_type: "计算机软件开发合同纠纷",
  });
  expect(fixture.notices["997"]?.python.venue).toBeNull();
  // Two related cases in one notice.
  expect(parseFixture("4008").dispute_type).toBe("侵害发明专利权纠纷");
  expect(fixture.notices["4008"]?.python.dispute_type).toBeNull();
  // 一审第三人 is a role of its own, not 第三人 with 一审 left on the name before it.
  expect(parseFixture("6106").parties).toEqual([
    {
      role_zh: "上诉人",
      role_en: "appellant",
      name: "国家知识产权局、福建镁孚科技有限公司",
    },
    { role_zh: "被上诉人", role_en: "appellee", name: "特维斯股份有限公司" },
    {
      role_zh: "一审第三人",
      role_en: "first_instance_third_party",
      name: "胡耀波",
    },
  ]);
  expect(fixture.notices["6106"]?.python.parties[1]?.name).toBe(
    "特维斯股份有限公司及一审",
  );
  // Latin party names keep their spaces.
  expect(parseFixture("6078").parties[0]?.name).toContain(
    "THE REGENTS OF THE UNIVERSITY OF CALIFORNIA",
  );
  expect(fixture.notices["6078"]?.python.parties[0]?.name).toContain(
    "THEREGENTSOFTHEUNIVERSITYOFCALIFORNIA",
  );
});

test("Chinese text loses its whitespace but Latin words stay apart", () => {
  expect(normalizeNoticeText("　　最高 人民法院\n特此公告。 ")).toBe(
    "最高人民法院特此公告。",
  );
  expect(normalizeNoticeText("（UNIVERSITY  OF\tVIENNA）与")).toBe(
    "（UNIVERSITY OF VIENNA）与",
  );
});

// Python's representative markup from tests/china_spc_ip_court/test_parsers.py.
const INDEX_HTML = `<div class="listing"><ul><li>
  <span class="left"><a href="/zh-cn/news/view-5999.html">最高人民法院知识产权法庭2026年8月21日开庭公告</a></span>
  <span class="right">2026-08-19</span>
</li></ul></div>
<div class="pagination"><a href="/zh-cn/news/more-4-15.html?page=2">下一页</a>
<a href="/zh-cn/news/more-4-15.html?page=388">尾页</a></div>`;
const DETAIL_HTML = `<div class="detail">
 <h2>最高人民法院知识产权法庭2026年8月21日开庭公告</h2>
 <div class="message"><span>发布时间：2026-08-19 16:05:44</span><span>来源：最高人民法院知识产权法庭</span></div>
 <div class="txt">最高人民法院知识产权法庭定于二〇二六年八月二十一日上午九时在最高人民法院知识产权法庭第五法庭公开开庭审理上诉人宁波奥美利合科技有限公司与被上诉人重庆能能科技有限公司及一审被告国家知识产权局发明专利权无效行政纠纷一案。<br/>特此公告。</div>
</div>`;
const SEARCH_HTML = `<div class="work search_list"><ul class="list"><li>
 <a href="/zh-cn/news/view-5143.html">“锂电池保护芯片”集成电路布图设计侵权案</a>
 <span>集成电路布图设计专有权保护范围的确定</span>
 <i class="date">2025-12-23 04:28:05</i>
</li></ul>
<div class="btm_row pagination"><div class="count">共<span class="num">12</span>篇文章</div>
<a href="/zh-cn/search.html?content=芯片&page=2">2</a></div></div>`;

test("Python's parser fixtures give Python's results", () => {
  const index = parseHearingIndex(INDEX_HTML);
  expect(index.total_pages).toBe(388);
  expect(index.notices[0]?.notice_id).toBe("5999");
  expect(index.notices[0]?.published_date).toBe("2026-08-19");
  const notice = parseHearingNotice(DETAIL_HTML, {
    noticeUrl: "https://ipc.court.gov.cn/zh-cn/news/view-5999.html",
  });
  expect(notice).toMatchObject({
    hearing_date: "2026-08-21",
    hearing_time_text: "上午九时",
    venue: "最高人民法院知识产权法庭第五法庭",
    dispute_type: "发明专利权无效行政纠纷",
    published_at: "2026-08-19T16:05:44",
  });
  expect(notice.parties.map((p) => p.role_en)).toEqual([
    "appellant",
    "appellee",
    "first_instance_defendant",
  ]);
  expect(notice.parties[0]?.name).toBe("宁波奥美利合科技有限公司");
  const search = parseSiteSearch(SEARCH_HTML, { query: "芯片" });
  expect(search).toMatchObject({ total_count: 12, total_pages: 2 });
  expect(search.hits[0]?.url).toEndWith("view-5143.html");
  expect(search.hits[0]?.published_at).toBe("2025-12-23T04:28:05");
  expect(splitCaseClause("原告甲公司与被告乙公司确认不侵害专利权纠纷")).toEqual(
    ["原告甲公司与被告乙公司", "确认不侵害专利权纠纷"],
  );
  expect(() => parseHearingIndex("<html></html>")).toThrow("no notice listing");
  expect(() => parseSiteSearch("<html></html>", { query: "芯片" })).toThrow(
    "no result list",
  );
});

test("the future filter uses the China calendar date", () => {
  expect(chinaToday(new Date("2026-08-20T16:30:00Z"))).toBe("2026-08-21");
  expect(chinaToday(new Date("2026-08-20T15:59:59Z"))).toBe("2026-08-20");
});

function fakeSite(respond: (url: URL) => Response) {
  const requests: Request[] = [];
  const client = new ChinaSpcIpCourtClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = new Request(input, init);
      requests.push(request);
      return respond(new URL(request.url));
    }) as typeof fetch,
  });
  return { client, requests };
}
const html = (body: string, status = 200) =>
  new Response(body, {
    status,
    headers: { "content-type": "text/html; charset=UTF-8" },
  });

test("requests use the official paths, parameters and an honest user agent", async () => {
  const site = fakeSite((url) =>
    html(url.pathname.includes("search") ? SEARCH_HTML : INDEX_HTML),
  );
  await site.client.listHearingIndex(2);
  await site.client.searchSite(" 芯片 ");
  const [index, search] = site.requests.map((r) => new URL(r.url));
  expect(index?.pathname).toBe("/zh-cn/news/more-4-15.html");
  expect(index?.searchParams.get("page")).toBe("2");
  expect(search?.searchParams.get("content")).toBe("芯片");
  expect(search?.searchParams.has("page")).toBe(false);
  expect(site.requests[0]?.headers.get("user-agent")).toBe(
    "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)",
  );
});

test("notice references are checked before any request", async () => {
  const site = fakeSite(() => html(DETAIL_HTML));
  for (const bad of [
    "https://example.com/zh-cn/news/view-5999.html",
    "http://ipc.court.gov.cn/zh-cn/news/view-5999.html",
    "https://ipc.court.gov.cn/zh-cn/news/view-5999.html?x=1",
  ])
    await expect(site.client.getHearingNotice(bad)).rejects.toThrow(
      "official SPC IP Court host",
    );
  await expect(site.client.getHearingNotice("abc")).rejects.toThrow(
    "numeric notice ID",
  );
  await expect(site.client.searchSite("芯")).rejects.toThrow(
    "at least 2 characters",
  );
  await expect(site.client.listHearingIndex(0)).rejects.toThrow(
    "page must be at least 1",
  );
  expect(site.requests).toHaveLength(0);
  const byPath = await site.client.getHearingNotice(
    "/zh-cn/news/view-5999.html",
  );
  expect(byPath.data.notice_id).toBe("5999");
});

test("the site's error page and non-notice articles raise NOT_FOUND; other failures do not", async () => {
  const errorPage = fakeSite(() =>
    html("<title>哎呀,出错了！ - 最高人民法院知识产权法庭</title>", 451),
  );
  await expect(errorPage.client.getHearingNotice("1")).rejects.toMatchObject({
    code: "NOT_FOUND",
    status: 404,
  });
  const article = fakeSite(() =>
    html(
      `<a href="/zh-cn/news/more-4-15.html">开庭公告</a><div class="detail"><h2>最高人民法院知识产权法庭简介</h2><div class="txt">x</div></div>`,
    ),
  );
  await expect(article.client.getHearingNotice("48")).rejects.toMatchObject({
    code: "NOT_FOUND",
  });
  const blocked = fakeSite(() => html("blocked", 451));
  await expect(blocked.client.getHearingNotice("1")).rejects.toMatchObject({
    code: "HTTP_ERROR",
    status: 451,
  });
});

const notice = (
  id: string,
  hearingDate: string,
  parties: string,
): ChinaSpcIpHearingNotice => ({
  notice_id: id,
  title: `最高人民法院知识产权法庭${hearingDate.replace(/^(\d+)-0?(\d+)-0?(\d+)$/, "$1年$2月$3日")}开庭公告`,
  published_at: null,
  hearing_date: hearingDate,
  hearing_time_text: "上午九时",
  venue: "第五法庭",
  dispute_type: "侵害发明专利权纠纷",
  party_clause: parties,
  parties: [{ role_zh: "上诉人", role_en: "appellant", name: parties }],
  body_text: `公开开庭审理上诉人${parties}侵害发明专利权纠纷一案。`,
  notice_url: `https://ipc.court.gov.cn/zh-cn/news/view-${id}.html`,
});
function fakeClient(notices: ChinaSpcIpHearingNotice[]) {
  const fetched: string[] = [];
  const provenance = {
    source_url: "https://ipc.court.gov.cn/zh-cn/news/more-4-15.html",
    source_name: "Supreme People's Court Intellectual Property Court",
    retrieved_at: "2026-10-22T00:00:00.000Z",
    cache_hit: false,
  };
  const client = {
    listHearingIndex: async (page: number) => ({
      data: {
        page,
        total_pages: 1,
        notices:
          page === 1
            ? notices.map((n) => ({ ...n, published_date: null }))
            : [],
      },
      provenance,
    }),
    getHearingNotice: async (id: string) => {
      fetched.push(id);
      const found = notices.find((n) => n.notice_id === id);
      if (!found)
        throw Object.assign(new Error("missing"), { code: "NOT_FOUND" });
      return { data: found, provenance };
    },
  } as unknown as ChinaSpcIpCourtClient;
  return { client, fetched };
}

test("future_only and query terms filter, and past hearings are not fetched", async () => {
  const { client, fetched } = fakeClient([
    notice("3", "2099-08-21", "某芯片公司"),
    notice("2", "2099-08-20", "某电池公司"),
    notice("1", "2020-01-01", "某芯片公司"),
  ]);
  const result = await searchChinaSpcHearingNotices(
    client,
    {
      query: ["芯片", "集成电路"],
      pages: 2,
      future_only: true,
      limit: 25,
      full: false,
    },
    new Date("2026-10-22T00:00:00Z"),
  );
  expect(result.items.map((item) => item.notice_id)).toEqual(["3"]);
  expect(result.items[0]).not.toHaveProperty("body_text");
  expect(fetched.sort()).toEqual(["2", "3"]);
  expect(result.more_available).toBe(false);
  await expect(
    searchChinaSpcHearingNotices(client, {
      query: [" "],
      pages: 1,
      future_only: false,
      limit: 1,
      full: false,
    }),
  ).rejects.toThrow("at least one non-empty term");
});

test("the full toolset serves the China SPC IP Court tools", async () => {
  const site = fakeSite((url) =>
    url.pathname.includes("search")
      ? html(SEARCH_HTML)
      : url.pathname.includes("view-1.")
        ? html("<title>哎呀,出错了！</title>", 451)
        : html(DETAIL_HTML),
  );
  const server = createServer({
    clients: { chinaSpcIpCourt: site.client },
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    for (const name of [
      "search_china_spc_ip_hearing_notices",
      "get_china_spc_ip_hearing_notice",
      "search_china_spc_ip_court_site",
    ])
      expect(names).toContain(name);
    const got = (
      await client.callTool<{
        items: { notice_id: string }[];
        not_found: string[];
      }>("get_china_spc_ip_hearing_notice", {
        notice: ["5999", "1"],
        full: false,
      })
    ).structuredContent;
    expect(got?.items.map((item) => item.notice_id)).toEqual(["5999"]);
    expect(got?.not_found).toEqual(["1"]);
    await expect(
      client.callTool("get_china_spc_ip_hearing_notice", { notice: "1" }),
    ).rejects.toThrow("not found");
    const search = (
      await client.callTool<{
        items: unknown[];
        next_cursor: string | null;
        more_available: boolean;
      }>("search_china_spc_ip_court_site", { query: "芯片" })
    ).structuredContent;
    expect(search?.items).toHaveLength(1);
    expect(search?.next_cursor).toBe("2");
    expect(search?.more_available).toBe(true);
    await expect(
      client.callTool("search_china_spc_ip_hearing_notices", { pages: 51 }),
    ).rejects.toThrow();
  } finally {
    await client.close();
    await server.close();
  }
});

test("Bun HTTP serves the China SPC IP Court tools only to tokens with spc:read", async () => {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
  });
  const jwk = {
    ...publicKey.export({ format: "jwk" }),
    kid: "test-key",
    alg: "RS256",
    use: "sig",
  };
  const identity = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch: () => Response.json({ keys: [jwk] }),
  });
  const issuer = "https://identity.test";
  const audience = "patent-client-agents";
  const site = fakeSite(() => html(DETAIL_HTML));
  const server = createServer({
    clients: { chinaSpcIpCourt: site.client },
    auth: {
      jwksUri: `http://127.0.0.1:${identity.port}/jwks`,
      issuer,
      audience,
    },
  });
  await server.run({
    transport: "http",
    host: "127.0.0.1",
    port: 0,
    stateless: true,
  });
  const url = `http://127.0.0.1:${server.address?.port}/mcp`;
  const token = (scope: string) => {
    const encode = (value: object) =>
      Buffer.from(JSON.stringify(value)).toString("base64url");
    const unsigned = `${encode({ alg: "RS256", kid: "test-key", typ: "JWT" })}.${encode({ iss: issuer, aud: audience, sub: "test-user", exp: Math.floor(Date.now() / 1000) + 120, scope })}`;
    return `${unsigned}.${sign("RSA-SHA256", Buffer.from(unsigned), privateKey).toString("base64url")}`;
  };
  try {
    const other = await Client.connect(url, {
      auth: new BearerAuth(token("cafc:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names).toContain("search_cafc_opinions");
      expect(names.filter((name) => name.includes("china_spc"))).toEqual([]);
      await expect(
        other.callTool("get_china_spc_ip_hearing_notice", { notice: "5999" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const spc = await Client.connect(url, {
      auth: new BearerAuth(token("spc:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const result = await spc.callTool<{ items: { notice_id: string }[] }>(
        "get_china_spc_ip_hearing_notice",
        { notice: "5999" },
      );
      expect(result.structuredContent?.items[0]?.notice_id).toBe("5999");
    } finally {
      await spc.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

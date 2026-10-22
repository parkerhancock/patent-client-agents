import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { Client } from "@prefecthq/fastmcp-ts/client";
import {
  ApiError,
  ConfigurationError,
  KIPRIS_BASE_URL,
  KiprisClient,
  type KiprisPatentRow,
  kiprisDate,
  parseKiprisResponse,
} from "../packages/client/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";
import { kiprisCassette, kiprisRecording } from "./kipris-recordings.js";

/**
 * Fixtures in tests/fixtures/kipris are doc-derived, not recorded: the sample
 * responses printed on the KIPRIS Plus Open API pages (archived in
 * references/kipris), trimmed to two items. The two error envelopes have the
 * shape observed live without a registered key. Small inline responses below
 * are synthetic edge cases. Nothing touches the network.
 */
const FIXTURES = join(import.meta.dir, "fixtures", "kipris");
const fixture = (name: string) => readFileSync(join(FIXTURES, name), "utf8");
const KEY = "test-service-key";
const KIPO_VARS = ["KIPO_KIPRIS_API_KEY", "KIPO_KIPRIS_BASE_URL"];
const PATENTS = `${KIPRIS_BASE_URL}/patUtiModInfoSearchSevice`;
/** Synthetic: a documented envelope with no hits. */
const EMPTY =
  "<response><header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header><body><items/></body><count><numOfRows>10</numOfRows><pageNo>1</pageNo><totalCount>0</totalCount></count></response>";
/** Synthetic: one page of a three-row result, `rows` items long. */
const paged = (page: number, rows: number) =>
  `<response><header><resultCode>00</resultCode></header><body><items>${Array.from(
    { length: rows },
    (_, i) =>
      `<item><applicationNumber>10202300000${page}${i}</applicationNumber><inventionTitle>Row ${page}.${i}</inventionTitle></item>`,
  ).join(
    "",
  )}</items></body><count><numOfRows>2</numOfRows><pageNo>${page}</pageNo><totalCount>3</totalCount></count></response>`;

interface Seen {
  path: string;
  query: Record<string, string>;
}
/** Routes by service, operation and query, the way KIPRIS would answer. */
function fakeKipris(overrides: Record<string, string | Response> = {}) {
  const seen: Seen[] = [];
  const xml = (body: string) =>
    new Response(body, { headers: { "content-type": "text/xml" } });
  const fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(new Request(input, init).url);
    const query = Object.fromEntries(url.searchParams);
    seen.push({ path: url.pathname, query });
    const [service = "", operation = ""] = url.pathname.split("/").slice(-2);
    const term =
      query.word ??
      query.searchString ??
      (operation === "getWordSearch" ? query.articleName : undefined) ??
      query.applicationNumber;
    const override =
      (term === undefined ? undefined : overrides[term]) ??
      overrides[`${service}/${operation}`];
    if (override instanceof Response) return override;
    if (override !== undefined) return xml(override);
    if (term === "paged")
      return xml(paged(Number(query.pageNo), query.pageNo === "1" ? 2 : 1));
    if (term === "missing" || term === "1029999999999") return xml(EMPTY);
    const kind = {
      patUtiModInfoSearchSevice: "patent",
      trademarkInfoSearchService: "trademark",
      designInfoSearchService: "design",
    }[service];
    if (!kind) return new Response("not found", { status: 404 });
    return xml(fixture(`${kind}-${operation}.xml`));
  };
  return {
    seen,
    client: new KiprisClient({
      serviceKey: KEY,
      fetch: fetch as typeof globalThis.fetch,
      retryLimit: 0,
    }),
  };
}

/** Run with the KIPRIS variables unset, restoring them afterwards. */
async function withoutKipoEnv<T>(run: () => Promise<T> | T): Promise<T> {
  const saved = KIPO_VARS.map((name) => [name, process.env[name]] as const);
  for (const name of KIPO_VARS) delete process.env[name];
  try {
    return await run();
  } finally {
    for (const [name, value] of saved)
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
  }
}

describe("client configuration", () => {
  test("a key alone selects the documented HTTPS endpoint; overrides must be HTTPS", async () => {
    await withoutKipoEnv(() => {
      expect(() => new KiprisClient()).toThrow(/KIPO_KIPRIS_API_KEY/);
      expect(
        new KiprisClient({ serviceKey: KEY }).operationUrl(
          "patUtiModInfoSearchSevice",
          "getWordSearch",
        ),
      ).toBe(`${PATENTS}/getWordSearch`);
      expect(
        () =>
          new KiprisClient({
            serviceKey: KEY,
            baseUrl: "http://plus.kipris.or.kr/kipo-api/kipi",
          }),
      ).toThrow(ConfigurationError);
      process.env.KIPO_KIPRIS_API_KEY = KEY;
      process.env.KIPO_KIPRIS_BASE_URL = "https://mirror.example.test/api";
      expect(
        new KiprisClient().operationUrl("designInfoSearchService", "x"),
      ).toBe("https://mirror.example.test/api/designInfoSearchService/x");
    });
  });
});

describe("client requests and parsing", () => {
  test("patent word search sends the documented parameters", async () => {
    const { client, seen } = fakeKipris();
    const page = await client.searchPatentsWord("센서", {
      utility: false,
      numOfRows: 5000,
    });
    expect(seen[0]?.path).toBe(
      "/kipo-api/kipi/patUtiModInfoSearchSevice/getWordSearch",
    );
    expect(seen[0]?.query).toEqual({
      word: "센서",
      patent: "true",
      utility: "false",
      numOfRows: "500",
      pageNo: "1",
      ServiceKey: KEY,
    });
    expect(page.pagination).toEqual({
      resultCode: "00",
      resultMsg: "NORMAL SERVICE.",
      numOfRows: 10,
      pageNo: 1,
      totalCount: 414120,
    });
    expect(page.items).toHaveLength(2);
    expect(page.items[0]).toMatchObject({
      applicationNumber: "1019850010013",
      applicationDate: "1985-12-30",
      openDate: "1987-07-11",
      registerDate: "1990-02-28",
      registerStatus: "소멸",
      indexNo: "1",
      drawing: null,
    });
    expect(page.items[1]?.ipcNumber).toBe("B60R 25/00 | B60R 25/01");
    expect(page.provenance.source_url).toBe(`${PATENTS}/getWordSearch`);
    expect(JSON.stringify(page)).not.toContain(KEY);
  });

  test("advanced searches map options to the documented parameter names", async () => {
    const { client, seen } = fakeKipris();
    const patents = await client.searchPatentsAdvanced({
      inventionTitle: "센서",
      inventor: "홍길동",
      ipc: "H04Q",
      applicationDate: "20060101~20061231",
      extra: { ServiceKey: "override", sortSpec: "AD" },
    });
    expect(seen[0]?.query).toEqual({
      inventionTitle: "센서",
      inventors: "홍길동",
      ipcNumber: "H04Q",
      applicationDate: "20060101~20061231",
      patent: "true",
      utility: "true",
      numOfRows: "10",
      pageNo: "1",
      sortSpec: "AD",
      ServiceKey: KEY,
    });
    expect(patents.pagination.totalCount).toBe(22251);
    expect(patents.items[0]).toMatchObject({
      applicantName: "한국전자통신연구원",
      applicationDate: "2006-06-16",
    });
    const marks = await client.searchTrademarksAdvanced({
      title: "NUTRIMACY",
      applicant: "(주)아모레퍼시픽",
      registrationDate: "20200101~20201231",
    });
    expect(seen[1]?.query).toMatchObject({
      trademarkName: "NUTRIMACY",
      applicantName: "(주)아모레퍼시픽",
      registerDate: "20200101~20201231",
      application: "true",
      abandonment: "true",
      trademark: "true",
      geoCertMark: "true",
      character: "true",
      invisible: "true",
    });
    expect(Object.keys(seen[1]?.query ?? {})).toHaveLength(36);
    expect(marks.items[0]).toMatchObject({
      title: "NUTRIMACY",
      applicationStatus: "출원",
      classificationCode: "32",
      registrationDate: null,
    });
    const designs = await client.searchDesignsAdvanced({
      applicant: "김민수",
      designClassification: "M1110",
      pageNo: 2,
    });
    expect(seen[2]?.query).toMatchObject({
      applicantName: "김민수",
      designMainClassification: "M1110",
      cancle: "true",
      simi: "true",
      pageNo: "2",
    });
    expect(designs.items[0]).toMatchObject({
      articleName: "직물지",
      designMainClassification: "M1110",
      registrationDate: "2013-11-26",
    });
  });

  test("trademark and design word searches use their documented parameters", async () => {
    const { client, seen } = fakeKipris();
    const marks = await client.searchTrademarksWord("롯데");
    expect(seen[0]?.query).toEqual({
      searchString: "롯데",
      numOfRows: "10",
      pageNo: "1",
      ServiceKey: KEY,
    });
    expect(marks.items[0]).toMatchObject({
      title: "롯데푸드 하이쿡",
      classificationCode: "29 30",
      registrationPublicDate: "2017-02-01",
      bigDrawing: expect.stringMatching(
        /^http:\/\/plus\.kipris\.or\.kr\/kiprisplusws\/fileToss\.jsp/,
      ),
      viennaCode: null,
    });
    const designs = await client.searchDesignsWord("한국");
    expect(seen[1]?.query).toMatchObject({ articleName: "한국" });
    expect(designs.pagination.totalCount).toBe(935);
    expect(designs.items[1]).toMatchObject({
      openNumber: "3020140000424",
      openDate: "2014-05-19",
    });
  });

  test("by-number lookups use advanced search; bibliography detail keeps the nested record", async () => {
    const { client, seen } = fakeKipris();
    await client.getPatent("1020060054155");
    expect(seen[0]?.query).toMatchObject({
      applicationNumber: "1020060054155",
      patent: "true",
      utility: "true",
    });
    await client.getTrademark("4020200228156");
    expect(seen[1]?.query).toMatchObject({
      applicationNumber: "4020200228156",
      trademark: "true",
    });
    const patent = await client.getPatentBibliography("1020050050026");
    expect(seen[2]?.path).toBe(
      "/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch",
    );
    expect(seen[2]?.query).toEqual({
      applicationNumber: "1020050050026",
      ServiceKey: KEY,
    });
    expect(patent.item).toMatchObject({
      abstractInfoArray: {
        abstractInfo: { astrtCont: expect.stringContaining("결빙") },
      },
    });
    const design = await client.getDesignBibliography("3020110022388");
    expect(design.item).toMatchObject({
      applicantInfoArray: { applicantInfo: { applicantName: "안준상" } },
    });
    const mark = await client.getTrademarkBibliography("4020230168937");
    const products = (
      mark.item?.asignProductArray as { asignProduct?: unknown } | undefined
    )?.asignProduct;
    expect(Array.isArray(products)).toBe(true);
    expect(mark.provenance.source_url).toBe(
      `${KIPRIS_BASE_URL}/trademarkInfoSearchService/getBibliographyDetailInfoSearch`,
    );
    const none = await fakeKipris({
      "1020000000000":
        "<response><header><resultCode>00</resultCode></header><body/></response>",
    }).client.getPatentBibliography("1020000000000");
    expect(none.item).toBeNull();
  });

  test("result codes become clear errors that never echo the key", async () => {
    const { client } = fakeKipris({
      bad: fixture("result-10-invalid-parameter.xml"),
      unregistered: fixture("result-30-unregistered-key.xml"),
      quota:
        "<response><header><resultCode>22</resultCode><resultMsg>LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR</resultMsg></header></response>",
      odd: "<response><header><resultCode>77</resultCode></header></response>",
    });
    const error = await client
      .searchPatentsWord("unregistered")
      .catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 401, code: "UNAUTHORIZED" });
    expect(error.message).toStartWith(
      "KIPRIS Plus result 30: SERVICE_KEY_IS_NOT_REGISTERED_ERROR. KIPO_KIPRIS_API_KEY is not a registered",
    );
    expect(error.message).not.toContain(KEY);
    await expect(client.searchPatentsWord("bad")).rejects.toMatchObject({
      status: 400,
      code: "INVALID_INPUT",
    });
    await expect(client.searchPatentsWord("quota")).rejects.toMatchObject({
      status: 429,
      code: "RATE_LIMITED",
    });
    await expect(client.searchPatentsWord("odd")).rejects.toMatchObject({
      status: 502,
      code: "UPSTREAM_ERROR",
      message: "KIPRIS Plus result 77: unknown error.",
    });
  });

  test("an empty result is empty, but malformed bodies are errors", async () => {
    const { client } = fakeKipris({
      nobody:
        "<response><header><resultCode>00</resultCode></header></response>",
      html: "<html><body>oops",
      entity: '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x "y">]><response/>',
      items: "<response><header/><body><items>text</items></body></response>",
    });
    const empty = await client.searchPatentsWord("missing");
    expect(empty.items).toEqual([]);
    expect(empty.pagination.totalCount).toBe(0);
    for (const word of ["nobody", "html", "entity", "items"])
      await expect(client.searchPatentsWord(word)).rejects.toMatchObject({
        code: "INVALID_RESPONSE",
      });
  });

  test("HTTP failures surface as ApiError without the request URL", async () => {
    const { client } = fakeKipris({
      down: new Response("boom", { status: 503 }),
    });
    const error = await client.searchPatentsWord("down").catch((e) => e);
    expect(error).toMatchObject({ status: 503 });
    expect(error.message).not.toContain(KEY);
  });

  test("paginate stops at the short page", async () => {
    const { client, seen } = fakeKipris();
    const rows: KiprisPatentRow[] = [];
    for await (const row of client.paginate(
      (page) => client.searchPatentsWord("paged", page),
      { numOfRows: 2 },
    ))
      rows.push(row);
    expect(rows.map((row) => row.inventionTitle)).toEqual([
      "Row 1.0",
      "Row 1.1",
      "Row 2.0",
    ]);
    expect(seen.map((s) => s.query.pageNo)).toEqual(["1", "2"]);
    const capped: KiprisPatentRow[] = [];
    for await (const row of client.paginate(
      (page) => client.searchPatentsWord("paged", page),
      { numOfRows: 2, maxPages: 1 },
    ))
      capped.push(row);
    expect(capped).toHaveLength(2);
  });

  test("dates accept every documented form", () => {
    expect(kiprisDate("20240310")).toBe("2024-03-10");
    expect(kiprisDate("2024-03-10")).toBe("2024-03-10");
    expect(kiprisDate("2011.05.31")).toBe("2011-05-31");
    expect(kiprisDate("1985/12/30 00:00:00")).toBe("1985-12-30");
    expect(kiprisDate("00000000")).toBeNull();
    expect(kiprisDate("20230230")).toBeNull();
    expect(kiprisDate("2024")).toBeNull();
    expect(kiprisDate(" ")).toBeNull();
  });

  test("unmodeled elements are kept and nested elements lose their text", () => {
    const { items } = parseKiprisResponse(
      "<response><header><resultCode>00</resultCode></header><body><items><item><applicationNumber>1</applicationNumber><extra>7</extra><nested><a>x</a></nested></item></items></body></response>",
    );
    expect(items).toEqual([
      { applicationNumber: "1", extra: "7", nested: null },
    ]);
  });
});

const KIPO_TOOLS = [
  "search_kipo_patents",
  "search_kipo_patents_advanced",
  "get_kipo_patent",
  "search_kipo_trademarks",
  "search_kipo_trademarks_advanced",
  "get_kipo_trademark",
  "search_kipo_designs",
  "search_kipo_designs_advanced",
  "get_kipo_design",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  more_available: boolean;
  next_cursor: string | null;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

describe("MCP tools", () => {
  let mcp: Client;
  let server: ReturnType<typeof createServer>;
  let fake: ReturnType<typeof fakeKipris>;
  const call = async (name: string, args: Record<string, unknown>) =>
    (await mcp.callTool<Envelope>(name, args)).structuredContent as Envelope;
  beforeAll(async () => {
    fake = fakeKipris();
    server = createServer({ clients: { kipris: fake.client } });
    mcp = await Client.connect(server, {
      versionNegotiation: { mode: "legacy" },
    });
  });
  afterAll(async () => {
    await mcp.close();
    await server.close();
  });

  test("the nine Python tools are registered with Python's parameters", async () => {
    const tools = await mcp.listTools();
    const byName = new Map(tools.map((tool) => [tool.name, tool]));
    for (const name of KIPO_TOOLS) expect(byName.has(name)).toBe(true);
    const params = (name: string) =>
      Object.keys(
        (byName.get(name)?.inputSchema as { properties?: object } | undefined)
          ?.properties ?? {},
      ).sort();
    expect(params("search_kipo_patents")).toEqual(
      ["full", "num_of_rows", "page_no", "query", "right_type"].sort(),
    );
    expect(params("search_kipo_patents_advanced")).toEqual(
      [
        "invention_title",
        "astrt_cont",
        "claim_scope",
        "applicant",
        "inventor",
        "ipc",
        "application_date",
        "publication_date",
        "right_type",
        "num_of_rows",
        "page_no",
        "full",
      ].sort(),
    );
    expect(params("search_kipo_trademarks_advanced")).toEqual(
      [
        "title",
        "applicant",
        "classification",
        "vienna_code",
        "application_date",
        "registration_date",
        "num_of_rows",
        "page_no",
        "full",
      ].sort(),
    );
    expect(params("search_kipo_designs_advanced")).toEqual(
      [
        "article_name",
        "applicant",
        "loc_code",
        "application_date",
        "registration_date",
        "num_of_rows",
        "page_no",
        "full",
      ].sort(),
    );
    for (const name of [
      "get_kipo_patent",
      "get_kipo_trademark",
      "get_kipo_design",
    ])
      expect(params(name)).toEqual(["application_number", "full"]);
  });

  test("search_kipo_patents returns the lean stub and Python's summary", async () => {
    const result = await call("search_kipo_patents", {
      query: "센서",
      right_type: "patent",
    });
    expect(fake.seen.at(-1)?.query).toMatchObject({
      patent: "true",
      utility: "false",
    });
    expect(result.summary).toBe("KIPO patents/UM — `센서`: 2 of 414120 hits.");
    expect(result.more_available).toBe(true);
    expect(result.next_cursor).toBeNull();
    expect(result.items[0]).toEqual({
      application_number: "1019850010013",
      application_date: "1985-12-30",
      publication_number: "1019890002319",
      publication_date: "1989-06-30",
      register_number: "1000319440000",
      register_status: "소멸",
      invention_title: expect.stringContaining("SENSOR AND SENSOR ENCODER"),
      applicant_name: "이두수",
      ipc_number: "G01D 5/00",
    });
    expect(result.provenance).toMatchObject({
      source_url: `${PATENTS}/getWordSearch`,
      source_name: expect.stringContaining("ToS §11"),
      connector_version: "0.1.0",
    });
    const full = await call("search_kipo_patents", {
      query: "센서",
      full: true,
    });
    expect(full.items[0]).toMatchObject({
      astrtCont: "내용 없음.",
      openNumber: "1019870006388",
      indexNo: "1",
    });
  });

  test("more_available follows Python's page arithmetic", async () => {
    const result = await call("search_kipo_patents", {
      query: "paged",
      num_of_rows: 2,
      page_no: 2,
    });
    expect(result.summary).toBe("KIPO patents/UM — `paged`: 1 of 3 hits.");
    expect(result.more_available).toBe(false);
  });

  test("advanced searches forward every option", async () => {
    const patents = await call("search_kipo_patents_advanced", {
      applicant: "한국전자통신연구원",
      claim_scope: "센서",
      right_type: "utility_model",
      num_of_rows: 3,
      page_no: 2,
    });
    expect(fake.seen.at(-1)?.query).toEqual({
      claimScope: "센서",
      applicant: "한국전자통신연구원",
      patent: "false",
      utility: "true",
      numOfRows: "3",
      pageNo: "2",
      ServiceKey: KEY,
    });
    expect(patents.summary).toBe(
      "KIPO advanced patent/UM search: 2 of 22251 hits.",
    );
    const marks = await call("search_kipo_trademarks_advanced", {
      title: "NUTRIMACY",
      classification: "32",
      registration_date: "20200101~20201231",
    });
    expect(fake.seen.at(-1)?.query).toMatchObject({
      trademarkName: "NUTRIMACY",
      classification: "32",
      registerDate: "20200101~20201231",
    });
    expect(marks.items[0]).toEqual({
      application_number: "4020200228156",
      application_date: "2020-12-14",
      registration_number: null,
      registration_date: null,
      title: "NUTRIMACY",
      classification_code: "32",
      vienna_code: null,
      applicant_name: "(주)아모레퍼시픽",
      big_drawing: expect.stringMatching(
        /^http:\/\/plus\.kipris\.or\.kr\/kiprisplusws\/fileToss\.jsp\?arg=/,
      ),
    });
    const designs = await call("search_kipo_designs_advanced", {
      article_name: "직물지",
      applicant: "김민수",
      loc_code: "M1110",
    });
    expect(fake.seen.at(-1)?.query).toMatchObject({
      articleName: "직물지",
      applicantName: "김민수",
      designMainClassification: "M1110",
    });
    expect(designs.items[0]).toEqual({
      application_number: "3020130041948",
      application_date: "2013-08-14",
      registration_number: "3007186540000",
      registration_date: "2013-11-26",
      register_status: "등록",
      article_name: "직물지",
      design_classification: "M1110",
      applicant_name: "김민수",
      inventor_name: null,
      drawing: null,
    });
    const word = await call("search_kipo_designs", { query: "한국" });
    expect(word.summary).toBe("KIPO designs — `한국`: 2 of 935 hits.");
    const tm = await call("search_kipo_trademarks", { query: "롯데" });
    expect(tm.summary).toBe("KIPO trademarks — `롯데`: 2 of 4431 hits.");
  });

  test("get tools fetch serially and name numbers with no rows", async () => {
    const before = fake.seen.length;
    const result = await call("get_kipo_patent", {
      application_number: ["1020060054155", "1029999999999"],
    });
    expect(
      fake.seen.slice(before).map((s) => s.query.applicationNumber),
    ).toEqual(["1020060054155", "1029999999999"]);
    expect(result.summary).toBe(
      "Fetched 1 of 2 KIPO patent/UM records. Not found: 1029999999999.",
    );
    expect(result.not_found).toEqual(["1029999999999"]);
    expect(result.items).toHaveLength(2);
    const one = await call("get_kipo_patent", {
      application_number: "1029999999999",
    });
    expect(one.summary).toBe(
      "Fetched 0 KIPO patent/UM record(s) for 1 number(s).",
    );
    expect(one.not_found).toEqual(["1029999999999"]);
    const mark = await call("get_kipo_trademark", {
      application_number: "4020200228156",
      full: true,
    });
    expect(mark.summary).toBe(
      "Fetched 2 KIPO trademark record(s) for 1 number(s).",
    );
    expect(mark.items[0]).toMatchObject({ fullText: "N" });
    const design = await call("get_kipo_design", {
      application_number: ["3020130041948"],
    });
    expect(design.summary).toBe(
      "Fetched 2 KIPO design record(s) for 1 number(s).",
    );
    await expect(
      call("get_kipo_design", {
        application_number: Array.from({ length: 51 }, (_, i) => `${i}`),
      }),
    ).rejects.toThrow();
  });

  test("tools register with a key alone, but not without one or with an HTTP override", async () => {
    for (const [env, present] of [
      [{}, false],
      [{ KIPO_KIPRIS_BASE_URL: "https://mirror.example.test" }, false],
      [
        { KIPO_KIPRIS_API_KEY: KEY, KIPO_KIPRIS_BASE_URL: "http://x.test" },
        false,
      ],
      [{ KIPO_KIPRIS_API_KEY: KEY }, true],
    ] as const) {
      const names = await withoutKipoEnv(async () => {
        Object.assign(process.env, env);
        const plain = createServer();
        const client = await Client.connect(plain, {
          versionNegotiation: { mode: "legacy" },
        });
        try {
          return (await client.listTools()).map((tool) => tool.name);
        } finally {
          await client.close();
          await plain.close();
        }
      });
      for (const name of KIPO_TOOLS) expect(names.includes(name)).toBe(present);
    }
  });
});

describe("curated facade KR routing", () => {
  async function facade(kipris?: KiprisClient) {
    return withoutKipoEnv(async () => {
      const server = createServer({
        toolset: "curated",
        clients: kipris ? { kipris } : {},
      });
      const client = await Client.connect(server, {
        versionNegotiation: { mode: "legacy" },
      });
      return {
        call: async (name: string, args: Record<string, unknown>) =>
          (await client.callTool<Envelope>(name, args))
            .structuredContent as Envelope,
        async close() {
          await client.close();
          await server.close();
        },
      };
    });
  }

  test("search_patents(kr) and KR biblio route to KIPRIS", async () => {
    const fake = fakeKipris();
    const mcp = await facade(fake.client);
    try {
      const search = await mcp.call("search_patents", {
        query: "센서",
        jurisdiction: "kr",
        limit: 5,
      });
      expect(fake.seen.at(-1)?.query).toMatchObject({
        word: "센서",
        numOfRows: "5",
        patent: "true",
        utility: "true",
      });
      expect(search.summary).toBe(
        "KIPO patents/UM — `센서`: 2 of 414120 hits.",
      );
      expect(search.items[0]).not.toHaveProperty("astrt_cont");
      const biblio = await mcp.call("get_patent", {
        view: "biblio",
        identifier: ["KR10-2006-0054155", "KR1029999999999"],
      });
      expect(fake.seen.slice(-2).map((s) => s.query.applicationNumber)).toEqual(
        ["1020060054155", "1029999999999"],
      );
      expect(biblio.not_found).toEqual(["1029999999999"]);
      expect(biblio.items[0]).toMatchObject({
        application_number: "1020060054155",
      });
    } finally {
      await mcp.close();
    }
  });

  test("without KIPRIS the KR branches report the missing key", async () => {
    const mcp = await facade();
    try {
      await expect(
        mcp.call("search_patents", { query: "x", jurisdiction: "kr" }),
      ).rejects.toThrow(
        "Korean (KR) patent search is not enabled on this server (KIPO_KIPRIS_API_KEY is not configured).",
      );
      await expect(
        mcp.call("get_patent", {
          view: "biblio",
          identifier: "KR1020230012345",
        }),
      ).rejects.toThrow(
        /Korean \(KR\) bibliographic retrieval is not enabled.*get_epo/,
      );
    } finally {
      await mcp.close();
    }
  });
});

test.skipIf(!existsSync(kiprisCassette))(
  "recorded KIPRIS session replays offline",
  async () => {
    const recording = await kiprisRecording();
    expect(recording.patents.pagination.resultCode).toBe("00");
    expect(recording.patents.items.length).toBeGreaterThan(0);
    expect(readFileSync(kiprisCassette, "utf8")).not.toMatch(
      /ServiceKey=(?!REDACTED)[^&\s"']+/i,
    );
  },
);

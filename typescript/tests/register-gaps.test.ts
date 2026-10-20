import { expect, test } from "bun:test";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { AssignmentCenterClient } from "../packages/client/src/assignments.js";
import { TrademarkAssignmentClient } from "../packages/client/src/trademark-assignments.js";
import { ApiError } from "../packages/client/src/transport.js";
import {
  formatTsdrCaseId,
  parseTrademarkStatus,
  TsdrClient,
} from "../packages/client/src/tsdr.js";
import { registerRegisterTools } from "../packages/mcp/src/registers.js";

function mock(
  handler: (request: Request) => Response | Promise<Response>,
): typeof fetch {
  return (async (input, init) =>
    handler(new Request(input, init))) as typeof fetch;
}
const record = (n: number, conveyance: string | null = "ASSIGNMENT") => ({
  reelNumber: 1,
  frameNumber: n,
  conveyance,
  futureField: "x".repeat(5000),
});
test("TSDR goods class normalization matches decimal Python parsing without inventing class zero", () => {
  const status = parseTrademarkStatus(
    {
      trademarks: [
        {
          gsList: [null, "", " ", "0x10", "9.0", "009", 0].map(
            (primeClassCode) => ({ primeClassCode }),
          ),
        },
      ],
    },
    "12345678",
  );
  expect(status.goodsServices.map((item) => item.classNumber)).toEqual([
    null,
    null,
    null,
    null,
    null,
    9,
    0,
  ]);
});
test("malformed nested TSDR records fail instead of disappearing from normalized data", () => {
  for (const trademark of [
    { status: "bad" },
    { parties: { ownerGroups: { current: "bad" } } },
    { gsList: "bad" },
    { prosecutionHistory: [null] },
  ])
    expect(() =>
      parseTrademarkStatus({ trademarks: [trademark] }, "12345678"),
    ).toThrow(ApiError);
  expect(parseTrademarkStatus({ trademarks: null }, "12345678").owners).toEqual(
    [],
  );
});
test("current TSDR numeric queries strip matching case prefixes and preserve documented parameter names", async () => {
  const requests: Request[] = [];
  const api = new TsdrClient({
    apiKey: "synthetic-key",
    retryLimit: 0,
    fetch: mock((request) => {
      requests.push(request);
      return request.url.includes(".json") ||
        request.url.includes("caseMultiStatus")
        ? Response.json({})
        : new Response("document");
    }),
  });
  await api.getStatusJson("SN12-345 678");
  await api.getLastUpdateXml("sn12345678");
  await api.getImage("SN12345678");
  await api.batchStatus(["RN12345", "67890"], {
    idType: "rn",
    from: "1",
    to: "2",
  });
  await api.getBundleXml(["ir12345", "67890"], { idType: "ir" });
  await api.downloadBundle(["ref12345"], { idType: "ref", format: "zip" });
  expect(
    requests.map(
      (request) => new URL(request.url).pathname + new URL(request.url).search,
    ),
  ).toEqual([
    "/last-update/info.json?sn=12345678",
    "/last-update/info.xml?sn=12345678",
    "/ts/cd/rawImage/12345678",
    "/ts/cd/caseMultiStatus/rn?ids=12345%2C67890&from=1&to=2",
    "/ts/cd/casedocs/bundle.xml?ir=12345%2C67890",
    "/ts/cd/casedocs/bundle.zip?ref=12345",
  ]);
  expect(
    requests.every(
      (request) => request.headers.get("USPTO-API-KEY") === "synthetic-key",
    ),
  ).toBe(true);
});
test("mismatched prefixes and runtime-invalid TSDR types fail before HTTP", async () => {
  let calls = 0;
  const api = new TsdrClient({
    apiKey: "test",
    fetch: mock(() => {
      calls++;
      return Response.json({});
    }),
  });
  expect(() => api.getStatusJson("rn1234")).toThrow("Expected sn");
  expect(() => api.batchStatus(["rn1234"])).toThrow("Expected sn");
  expect(() => api.getBundleXml(["sn1234"], { idType: "rn" })).toThrow(
    "Expected rn",
  );
  expect(() =>
    api.batchStatus(["1234"], { idType: "../../unexpected" as "sn" }),
  ).toThrow();
  expect(() => formatTsdrCaseId("1234", "../../unexpected" as "sn")).toThrow();
  expect(calls).toBe(0);
});
test("assignment detail maps property aliases and rejects absent recordations", async () => {
  const api = new AssignmentCenterClient({
    fetch: mock(() =>
      Response.json({
        successResponse: {
          data: {
            assignment: { recorded: "2026-01-02" },
            properties: [
              {
                propertySequenceNumber: "3",
                fillingDate: "2020-01-02",
                future: "retained",
              },
            ],
          },
        },
      }),
    ),
  });
  expect((await api.details(1, 2)).data.properties[0]).toMatchObject({
    sequenceNumber: 3,
    propertySequenceNumber: 3,
    filingDate: "2020-01-02",
    fillingDate: "2020-01-02",
    future: "retained",
  });
  for (const assignment of [null, {}, []]) {
    const missing = new AssignmentCenterClient({
      fetch: mock(() =>
        Response.json({ successResponse: { data: { assignment } } }),
      ),
    });
    await expect(missing.details(1, 2)).rejects.toMatchObject({ status: 404 });
  }
});
test("an explicitly empty conveyance filter retains only records with conveyance text", async () => {
  const api = new AssignmentCenterClient({
    fetch: mock(() =>
      Response.json({
        successResponse: {
          totalRows: 2,
          data: [record(1, null), record(2)],
          backendPagination: false,
        },
      }),
    ),
  });
  const response = await api.search({
    query: "Acme",
    by: "assignee",
    conveyance: "",
  });
  expect(response.records.map((item) => item.frameNumber)).toEqual([2]);
  expect(response.total).toBe(1);
});
test("actual MCP register searches and document listings expose query-bound usable cursors", async () => {
  const assignments = new AssignmentCenterClient({
    fetch: mock(() =>
      Response.json({
        successResponse: {
          data: [record(1), record(2), record(3)],
          totalRows: 3,
          backendPagination: false,
        },
      }),
    ),
  });
  const trademarks = new TrademarkAssignmentClient({
    fetch: mock(() =>
      Response.json({
        successResponse: {
          data: [record(1), record(2), record(3)],
          totalRows: 3,
        },
      }),
    ),
  });
  const tsdr = new TsdrClient({
    apiKey: "test",
    fetch: mock((request) =>
      request.url.includes("casedocs")
        ? new Response(
            "<DocumentList><Document><SerialNumber>12345678</SerialNumber><DocumentTypeCode>ONE</DocumentTypeCode></Document><Document><SerialNumber>12345678</SerialNumber><DocumentTypeCode>TWO</DocumentTypeCode></Document></DocumentList>",
          )
        : Response.json({ trademarks: [{ status: { markElement: "ACME" } }] }),
    ),
  });
  const server = new FastMCP({ name: "register-gap-test", version: "1" });
  registerRegisterTools(server, {
    assignments,
    trademarkAssignments: trademarks,
    tsdr,
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    for (const right of ["patent", "trademark"]) {
      const parameters = { right, by: "assignee", query: "Acme", limit: 1 };
      const first = await client.callTool<{
        items: unknown[];
        next_cursor: string;
      }>("search_assignments", parameters);
      expect(first.structuredContent?.next_cursor).toBeString();
      expect(first.structuredContent?.items[0]).not.toHaveProperty(
        "futureField",
      );
      const full = await client.callTool<{ items: { futureField: string }[] }>(
        "search_assignments",
        { ...parameters, full: true },
      );
      expect(full.structuredContent?.items[0]?.futureField).toHaveLength(4000);
      const second = await client.callTool<{
        items: { frameNumber: number | string }[];
      }>("search_assignments", {
        ...parameters,
        cursor: first.structuredContent?.next_cursor,
      });
      expect(Number(second.structuredContent?.items[0]?.frameNumber)).toBe(2);
      await expect(
        client.callTool("search_assignments", {
          ...parameters,
          query: "Other",
          cursor: first.structuredContent?.next_cursor,
        }),
      ).rejects.toThrow();
      await expect(
        client.callTool("search_assignments", {
          ...parameters,
          offset: 1,
          cursor: first.structuredContent?.next_cursor,
        }),
      ).rejects.toThrow();
      await expect(
        client.callTool("search_assignments", {
          ...parameters,
          full: true,
          cursor: first.structuredContent?.next_cursor,
        }),
      ).rejects.toThrow();
    }
    const first = await client.callTool<{ next_cursor: string }>(
      "list_trademark_documents",
      { serial_number: "12345678", limit: 1 },
    );
    const second = await client.callTool<{ items: { docType: string }[] }>(
      "list_trademark_documents",
      {
        serial_number: "12345678",
        limit: 1,
        cursor: first.structuredContent?.next_cursor,
      },
    );
    expect(second.structuredContent?.items[0]?.docType).toBe("TWO");
    await expect(
      client.callTool("list_trademark_documents", {
        serial_number: "87654321",
        limit: 1,
        cursor: first.structuredContent?.next_cursor,
      }),
    ).rejects.toThrow();
    const scalar = await client.callTool<{ items: { markText: string }[] }>(
      "get_trademark",
      { serial_number: "12345678" },
    );
    expect(scalar.structuredContent?.items[0]?.markText).toBe("ACME");
    expect(scalar.structuredContent).not.toHaveProperty("details");
  } finally {
    await client.close();
    await server.close();
  }
});

test("assignment records expose reel/frame helpers while preserving trademark frame padding", async () => {
  const patent = new AssignmentCenterClient({
    fetch: mock(() =>
      Response.json({ successResponse: { data: [record(93)], totalRows: 1 } }),
    ),
  });
  expect(
    (await patent.search({ query: "x", by: "assignee" })).records[0]?.reelFrame,
  ).toBe("1/93");
  const trademark = new TrademarkAssignmentClient({
    fetch: mock(() =>
      Response.json({
        successResponse: {
          data: [{ ...record(93), frameNumber: "0093" }],
          totalRows: 1,
        },
      }),
    ),
  });
  expect((await trademark.searchByAssignee("x")).data[0]?.reelFrame).toBe(
    "1/0093",
  );
});

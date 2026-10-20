import { describe, expect, test } from "bun:test";
import {
  OFFICE_ACTION_ANALYTICS_DATASETS,
  OfficeActionAnalyticsClient,
} from "../packages/client/src/office-action-analytics.js";
import {
  OfficeActionSearchOptionsSchema,
  OfficeActionsClient,
} from "../packages/client/src/office-actions.js";

function mockFetch(
  handler: (request: Request) => Response | Promise<Response>,
): typeof fetch {
  return (async (input: string | URL | Request, init?: RequestInit) =>
    handler(new Request(input, init))) as typeof fetch;
}
const record = {
  officeActionRecordIdentifier: "abc",
  applicationNumberText: "15569871",
  groupArtUnitNumber: 1646,
  lastModifiedDateTime: "2026-08-10 20:50:02",
  futureField: false,
};
function client(handler: (request: Request) => Response | Promise<Response>) {
  return new OfficeActionsClient({
    apiKey: "synthetic-secret",
    retryLimit: 0,
    fetch: mockFetch(handler),
  });
}
describe("Office Actions API 5.0 contract", () => {
  test("POST supports art unit ranges, lowercase sort, facets and lean projection", async () => {
    const api = client(async (request) => {
      expect(request.method).toBe("POST");
      const body = await request.json();
      expect(body.rangeFilters).toEqual([
        { field: "groupArtUnitNumber", valueFrom: "1640", valueTo: "1699" },
      ]);
      expect(body.sort).toEqual([{ field: "submissionDate", order: "desc" }]);
      expect(body.facets).toEqual(["documentCode"]);
      expect(body.fields).not.toContain("officeActionText");
      return Response.json({ count: 18, officeActionDataBag: [record] });
    });
    const response = await api.search({
      rangeFilters: [
        { field: "groupArtUnitNumber", valueFrom: "1640", valueTo: "1699" },
      ],
      sort: [{ field: "submissionDate", order: "DESC" }],
      facets: ["documentCode"],
    });
    expect(response.count).toBe(18);
    expect(response.officeActionDataBag[0]?.futureField).toBe(false);
  });
  test("GET uses documented query grammar", async () => {
    const api = client((request) => {
      const params = new URL(request.url).searchParams;
      expect(request.method).toBe("GET");
      expect(params.get("filters")).toBe("documentCode CTNF,CTFR");
      expect(params.get("rangeFilters")).toBe(
        "submissionDate 2020-01-01:2026-01-01",
      );
      expect(params.get("sort")).toBe("submissionDate asc");
      return Response.json({ officeActionDataBag: [] });
    });
    expect(
      (
        await api.search({
          method: "GET",
          filters: [{ name: "documentCode", value: ["CTNF", "CTFR"] }],
          rangeFilters: [
            {
              field: "submissionDate",
              valueFrom: "2020-01-01",
              valueTo: "2026-01-01",
            },
          ],
          sort: [{ field: "submissionDate", order: "asc" }],
          full: true,
        })
      ).officeActionDataBag,
    ).toEqual([]);
  });
  test("get encodes identifiers and preserves highlighted excerpt", async () => {
    const api = client((request) => {
      expect(new URL(request.url).pathname).toEndWith("/office-action/a%2Fb");
      return Response.json({
        officeActionDataBag: [
          { ...record, officeActionText: "<em>Claim</em> excerpt" },
        ],
      });
    });
    expect(
      (await api.get("a/b")).officeActionDataBag[0]?.officeActionText,
    ).toBe("<em>Claim</em> excerpt");
  });
  for (const method of ["GET", "POST"] as const)
    for (const format of ["csv", "json"] as const)
      test(`${method} ${format} download accepts count-free response`, async () => {
        const payload =
          format === "json"
            ? JSON.stringify({ officeActionDataBag: [record] })
            : "applicationNumberText\n15569871\n";
        const api = client(async (request) => {
          expect(request.url.split("?")[0]).toEndWith("/search/download");
          expect(request.method).toBe(method);
          expect(
            method === "GET"
              ? new URL(request.url).searchParams.get("format")
              : (await request.json()).format,
          ).toBe(format);
          return new Response(payload);
        });
        expect(
          new TextDecoder().decode(
            (await api.download({ method, format })).data,
          ),
        ).toBe(payload);
      });
  test("full text uses separate endpoint and preserves all text", async () => {
    const api = client((request) => {
      expect(request.url).toEndWith("/abc/download/officeActionText");
      expect(request.headers.get("accept")).toBe("text/plain");
      return new Response("X".repeat(2000));
    });
    expect((await api.downloadText("abc")).data.length).toBe(2000);
  });
  test("invalid bounds and pagination fail before network", () => {
    for (const range of [
      { field: "groupArtUnitNumber", valueFrom: "2020-01-01" },
      { field: "groupArtUnitNumber", valueFrom: "4", valueTo: "3" },
      { field: "filingDate", valueFrom: "2024-02-30" },
    ])
      expect(
        OfficeActionSearchOptionsSchema.safeParse({ rangeFilters: [range] })
          .success,
      ).toBe(false);
    expect(
      OfficeActionSearchOptionsSchema.safeParse({ limit: 501 }).success,
    ).toBe(false);
  });
  test("malformed success and HTTP errors are not silently empty", async () => {
    await expect(
      client(() => Response.json({ count: 1 })).search(),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    await expect(
      client(() =>
        Response.json({ error: "secret error" }, { status: 403 }),
      ).get("abc"),
    ).rejects.toMatchObject({ status: 403 });
  });
});
describe("legacy analytics parity", () => {
  const paths = [
    "oa_rejections/v2",
    "oa_citations/v2",
    "oa_actions/v1",
    "enriched_cited_reference_metadata/v3",
  ];
  OFFICE_ACTION_ANALYTICS_DATASETS.forEach((dataset, index) => {
    test(`${dataset} posts form data and preserves Solr records`, async () => {
      const api = new OfficeActionAnalyticsClient({
        apiKey: "synthetic-secret",
        retryLimit: 0,
        fetch: mockFetch(async (request) => {
          expect(request.url).toEndWith(`/oa/${paths[index]}/records`);
          expect(request.headers.get("content-type")).toContain(
            "application/x-www-form-urlencoded",
          );
          expect(
            new URLSearchParams(await request.text()).get("criteria"),
          ).toBe("patentApplicationNumber:15569871");
          return Response.json({
            response: {
              numFound: 100,
              start: 5,
              docs: [{ id: "one", bodyText: ["real text"], futureField: [3] }],
            },
          });
        }),
      });
      const result = await api.search(
        dataset,
        "patentApplicationNumber:15569871",
        { start: 5, rows: 10 },
      );
      expect(result.numFound).toBe(100);
      expect(result.results[0]?.futureField).toEqual([3]);
    });
  });
  test("malformed Solr response fails explicitly", async () => {
    const api = new OfficeActionAnalyticsClient({
      apiKey: "synthetic-secret",
      retryLimit: 0,
      fetch: mockFetch(() => Response.json({ response: { docs: [] } })),
    });
    await expect(api.searchRejections("*:*")).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  });
});

test("MCP office action schemas initialize and keep full text out of responses", async () => {
  const { FastMCP } = await import("@prefecthq/fastmcp-ts/server");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const { registerOfficeActionTools } = await import(
    "../packages/mcp/src/office-actions.js"
  );
  const officeActions = client(() =>
    Response.json({
      count: 2,
      officeActionDataBag: [{ ...record, officeActionText: "A".repeat(2000) }],
    }),
  );
  const analytics = new OfficeActionAnalyticsClient({
    apiKey: "synthetic-secret",
    retryLimit: 0,
    fetch: mockFetch(() =>
      Response.json({
        response: {
          numFound: 1,
          start: 0,
          docs: [
            {
              id: "one",
              bodyText: ["SECRET DOCUMENT"],
              sections: [{ text: "SECRET DOCUMENT" }],
            },
          ],
        },
      }),
    ),
  });
  const server = new FastMCP({ name: "office-action-test", version: "0.1.0" });
  registerOfficeActionTools(server, { officeActions, analytics });
  const connection = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    expect(
      (await connection.listTools()).map((tool) => tool.name),
    ).toHaveLength(7);
    const result = await connection.callTool<{
      items: Record<string, unknown>[];
    }>("search_office_actions", {
      full: true,
      sort: [{ field: "submissionDate", order: "dEsC" }],
    });
    expect(
      String(result.structuredContent?.items[0]?.officeActionText).length,
    ).toBe(500);
    const analytical = await connection.callTool<{
      items: Record<string, unknown>[];
    }>("search_office_action_analytics", {
      dataset: "text",
      criteria: "*:*",
      full: true,
    });
    expect(analytical.structuredContent?.items[0]?.bodyText).toBeUndefined();
    expect(analytical.structuredContent?.items[0]?.sections).toBeUndefined();
  } finally {
    await connection.close();
    await server.close();
  }
});

test("real ODP office action recording replays offline", async () => {
  const { recorded } = await import("./cassettes.js");
  const api = new OfficeActionsClient({
    apiKey: "replay-placeholder",
    retryLimit: 0,
  });
  const result = await recorded("office-actions", () =>
    api.search({ limit: 1 }),
  );
  expect(result.officeActionDataBag).toHaveLength(1);
  expect(result.count).toBeGreaterThan(0);
  expect(
    result.officeActionDataBag[0]?.officeActionRecordIdentifier,
  ).toBeString();
});

test("all four legacy dataset field discovery endpoints are available", async () => {
  for (const dataset of OFFICE_ACTION_ANALYTICS_DATASETS) {
    const api = new OfficeActionAnalyticsClient({
      apiKey: "synthetic-secret",
      retryLimit: 0,
      fetch: mockFetch((request) => {
        expect(request.method).toBe("GET");
        expect(request.url).toEndWith("/fields");
        return Response.json({
          fields: ["patentApplicationNumber", "id"],
          version: "upstream",
        });
      }),
    });
    expect((await api.getFields(dataset)).data).toEqual({
      fields: ["patentApplicationNumber", "id"],
      version: "upstream",
    });
  }
});

test("MCP office action and analytics cursors advance pages and bind to the original query", async () => {
  const { FastMCP } = await import("@prefecthq/fastmcp-ts/server");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const { registerOfficeActionTools } = await import(
    "../packages/mcp/src/office-actions.js"
  );
  const officeActions = client(async (request) => {
    const body = await request.json();
    expect(body.q).toBe("documentCode:CTNF");
    expect(body.filters).toEqual([{ name: "documentCode", value: ["CTNF"] }]);
    return Response.json({
      count: 2,
      officeActionDataBag: [
        { officeActionRecordIdentifier: String(body.pagination.offset) },
      ],
    });
  });
  const analytics = new OfficeActionAnalyticsClient({
    apiKey: "synthetic-secret",
    retryLimit: 0,
    fetch: mockFetch(async (request) => {
      const body = new URLSearchParams(await request.text());
      expect(body.get("criteria")).toBe("patentApplicationNumber:15569871");
      const start = Number(body.get("start"));
      return Response.json({
        response: {
          numFound: 2,
          start,
          docs: [{ id: String(start), bodyText: ["omitted"] }],
        },
      });
    }),
  });
  const server = new FastMCP({
    name: "office-action-cursor-test",
    version: "0.1.0",
  });
  registerOfficeActionTools(server, { officeActions, analytics });
  const connection = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  type Page = {
    items: Record<string, unknown>[];
    next_cursor: string | null;
    more_available: boolean;
  };
  try {
    const search = {
      query: "documentCode:CTNF",
      limit: 1,
      filters: [{ name: "documentCode", value: ["CTNF"] }],
    };
    const first = (
      await connection.callTool<Page>("search_office_actions", search)
    ).structuredContent;
    expect(first?.items[0]?.officeActionRecordIdentifier).toBe("0");
    expect(first?.next_cursor).toBeString();
    const second = (
      await connection.callTool<Page>("search_office_actions", {
        ...search,
        cursor: first?.next_cursor,
      })
    ).structuredContent;
    expect(second?.items[0]?.officeActionRecordIdentifier).toBe("1");
    expect(second?.next_cursor).toBeNull();
    expect(second?.more_available).toBe(false);
    await expect(
      connection.callTool("search_office_actions", {
        ...search,
        cursor: first?.next_cursor,
        query: "other",
      }),
    ).rejects.toThrow("different query");
    await expect(
      connection.callTool("search_office_actions", {
        ...search,
        cursor: first?.next_cursor,
        offset: 1,
      }),
    ).rejects.toThrow("not both");
    await expect(
      connection.callTool("search_office_actions", {
        ...search,
        cursor: "not-a-cursor",
      }),
    ).rejects.toThrow("Invalid pagination cursor");
    const criteria = {
      dataset: "text",
      criteria: "patentApplicationNumber:15569871",
      rows: 1,
    };
    const analytical = (
      await connection.callTool<Page>(
        "search_office_action_analytics",
        criteria,
      )
    ).structuredContent;
    expect(analytical?.next_cursor).toBeString();
    const analyticalNext = (
      await connection.callTool<Page>("search_office_action_analytics", {
        ...criteria,
        cursor: analytical?.next_cursor,
      })
    ).structuredContent;
    expect(analyticalNext?.items[0]?.id).toBe("1");
    expect(analyticalNext?.items[0]?.bodyText).toBeUndefined();
    expect(analyticalNext?.next_cursor).toBeNull();
    await expect(
      connection.callTool("search_office_action_analytics", {
        ...criteria,
        cursor: analytical?.next_cursor,
        dataset: "rejections",
      }),
    ).rejects.toThrow("different query");
    await expect(
      connection.callTool("search_office_action_analytics", {
        ...criteria,
        cursor: analytical?.next_cursor,
        start: 1,
      }),
    ).rejects.toThrow("not both");
  } finally {
    await connection.close();
    await server.close();
  }
});

test("OA search no-match 404 is empty while retrieval and exports propagate missing records", async () => {
  const api = client(() =>
    Response.json({ code: 404, error: "Not Found" }, { status: 404 }),
  );
  expect(
    await api.search({ query: "applicationNumberText:00000000" }),
  ).toMatchObject({ count: 0, officeActionDataBag: [] });
  await expect(api.get("missing")).rejects.toMatchObject({ status: 404 });
  await expect(
    api.download({ query: "applicationNumberText:00000000" }),
  ).rejects.toMatchObject({ status: 404 });
});

test("OA export default projections exclude fields rejected by the live service without changing explicit fields", async () => {
  for (const format of ["csv", "json"] as const) {
    const api = client(async (request) => {
      const body = await request.json();
      expect(body.fields).not.toContain("filingDate");
      expect(body.fields.includes("rejectionTypeBag")).toBe(format === "json");
      return new Response(
        format === "csv"
          ? "officeActionRecordIdentifier\nabc\n"
          : JSON.stringify({ officeActionDataBag: [record] }),
      );
    });
    await api.download({ format });
  }
  const explicit = client(async (request) => {
    expect((await request.json()).fields).toEqual(["filingDate"]);
    return new Response("unsupported", { status: 400 });
  });
  await expect(
    explicit.download({ fields: ["filingDate"] }),
  ).rejects.toMatchObject({ status: 400 });
});

test("OA MCP preserves requested facets and downloads complete legacy text outside context", async () => {
  const { FastMCP } = await import("@prefecthq/fastmcp-ts/server");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const { readFile } = await import("node:fs/promises");
  const { DownloadStore, downloadContext } = await import(
    "../packages/mcp/src/downloads.js"
  );
  const { registerOfficeActionTools } = await import(
    "../packages/mcp/src/office-actions.js"
  );
  const facets = { documentCode: [{ value: "CTNF", count: 3 }] };
  const text = "complete office action ".repeat(3000);
  const officeActions = client(() =>
    Response.json({ count: 3, officeActionDataBag: [record], facets }),
  );
  const analytics = new OfficeActionAnalyticsClient({
    apiKey: "synthetic",
    retryLimit: 0,
    fetch: mockFetch(async (request) => {
      const body = new URLSearchParams(await request.text());
      expect(body.get("criteria")).toBe("id:legacy-record");
      expect(body.get("rows")).toBe("1");
      return Response.json({
        response: {
          numFound: 1,
          start: 0,
          docs: [
            { id: "legacy-record", bodyText: [text], sections: [{ text }] },
          ],
        },
      });
    }),
  });
  const store = new DownloadStore();
  const server = new FastMCP({ name: "oa-gap-test", version: "0.1.0" });
  server.use({
    onCallTool: (_context, next) => downloadContext.run({ store }, next),
  });
  registerOfficeActionTools(server, { officeActions, analytics });
  const connection = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await connection.callTool<{ facets?: typeof facets }>(
      "search_office_actions",
      { facets: ["documentCode"] },
    );
    expect(result.structuredContent?.facets).toEqual(facets);
    const noFacets = await connection.callTool<{ facets?: typeof facets }>(
      "search_office_actions",
      {},
    );
    expect(noFacets.structuredContent?.facets).toBeUndefined();
    const download = await connection.callTool<{
      file_path: string;
      size: number;
    }>("download_office_action_analytics", {
      dataset: "text",
      criteria: "id:legacy-record",
      rows: 1,
    });
    expect(download.structuredContent?.file_path).toBeString();
    expect(JSON.stringify(download)).not.toContain(text.slice(0, 300));
    const saved = JSON.parse(
      await readFile(download.structuredContent?.file_path as string, "utf8"),
    );
    expect(saved.results[0].bodyText).toEqual([text]);
    expect(saved.results[0].sections).toEqual([{ text }]);
    await expect(
      connection.callTool("download_office_action_analytics", {
        dataset: "text",
        criteria: "*:*",
        rows: 101,
      }),
    ).rejects.toThrow();
  } finally {
    await connection.close();
    await server.close();
    await store.close();
  }
});

test("legacy field discovery rejects malformed success metadata", async () => {
  for (const data of [{}, { fields: "not an array" }, "not metadata"]) {
    const api = new OfficeActionAnalyticsClient({
      apiKey: "synthetic",
      retryLimit: 0,
      fetch: mockFetch(() => Response.json(data)),
    });
    await expect(api.getFields("text")).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  }
});

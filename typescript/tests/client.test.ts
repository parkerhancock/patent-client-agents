import { describe, expect, test } from "bun:test";
import {
  ApplicationsClient,
  ConfigurationError,
  OdpApiError,
  STUB_APPLICATION_FIELDS,
} from "@patent-client-agents/client";

// Synthetic contracts derived from the Python clients, not live USPTO recordings.
const upstream = {
  count: 1,
  requestIdentifier: "request-1",
  facetResults: { applicationType: ["Utility"] },
  patentFileWrapperDataBag: [
    {
      applicationNumberText: "16123456",
      inventionTitle: "Top-level title",
      parentContinuityBag: [{ parentApplicationNumberText: "12345678" }],
      applicationMetaData: {
        inventionTitle: "Nested title",
        filingDate: "2020-01-02",
        applicationStatusCode: 150,
        entityStatusData: {
          businessEntityStatusCategory: "SMALL",
          smallEntityStatusIndicator: false,
        },
        futureField: 0,
      },
    },
  ],
};

function mockFetch(
  handler: (request: Request) => Response | Promise<Response>,
): typeof fetch {
  return (async (input: string | URL | Request, init?: RequestInit) =>
    handler(new Request(input, init))) as typeof fetch;
}

function client(handler: (request: Request) => Response | Promise<Response>) {
  return new ApplicationsClient({
    apiKey: "synthetic-secret",
    fetch: mockFetch(handler),
    retryLimit: 0,
  });
}

describe("ODP application contracts", () => {
  test("search sends auth, lean projection, query filters and complete date ranges", async () => {
    const api = client(async (request) => {
      expect(request.url).toBe(
        "https://api.uspto.gov/api/v1/patent/applications/search",
      );
      expect(request.method).toBe("POST");
      expect(request.headers.get("x-api-key")).toBe("synthetic-secret");
      const body = await request.json();
      expect(body).toEqual({
        q: "applicationMetaData.inventionTitle:widget",
        fields: [...STUB_APPLICATION_FIELDS],
        filters: [
          {
            name: "applicationMetaData.publicationCategoryBag",
            value: ["Granted/Issued"],
          },
        ],
        facets: ["applicationMetaData.applicationTypeCategory"],
        rangeFilters: [
          {
            field: "applicationMetaData.filingDate",
            valueFrom: "2020-01-01",
            valueTo: new Date().toISOString().slice(0, 10),
          },
          {
            field: "applicationMetaData.grantDate",
            valueFrom: "1776-01-01",
            valueTo: "2025-01-01",
          },
        ],
        sort: [{ field: "applicationMetaData.filingDate", order: "Desc" }],
        pagination: { offset: 0, limit: 25 },
      });
      return Response.json(upstream);
    });
    const result = await api.search({
      query: "applicationMetaData.inventionTitle:widget",
      filters: [
        {
          name: "applicationMetaData.publicationCategoryBag",
          value: ["Granted/Issued"],
        },
      ],
      facets: ["applicationMetaData.applicationTypeCategory"],
      rangeFilters: [
        { field: "applicationMetaData.filingDate", valueFrom: "2020-01-01" },
        { field: "applicationMetaData.grantDate", valueTo: "2025-01-01" },
      ],
      sort: [{ field: "applicationMetaData.filingDate", order: "Desc" }],
    });
    expect(result.patentBag[0]).toMatchObject({
      inventionTitle: "Top-level title",
      futureField: 0,
      smallEntityStatusIndicator: false,
    });
    expect(result.patentBag[0]).not.toHaveProperty("applicationMetaData");
    expect(result.patentBag[0]?.continuityBag).toEqual({
      parentContinuityBag:
        upstream.patentFileWrapperDataBag[0]?.parentContinuityBag,
      childContinuityBag: [],
    });
    expect(result.facetResults).toEqual(upstream.facetResults);
    expect(result.provenance.cache_hit).toBe(false);
    expect(result.provenance.source_url).toContain("/applications/search");
    expect(Date.parse(result.provenance.retrieved_at)).not.toBeNaN();
  });

  test("full results and normalize=false retain upstream record shape", async () => {
    const api = client(async (request) => {
      expect(await request.json()).toEqual({
        pagination: { offset: 50, limit: 10 },
      });
      return Response.json(upstream);
    });
    expect(
      (
        await api.search({
          full: true,
          normalize: false,
          offset: 50,
          limit: 10,
        })
      ).patentBag,
    ).toEqual(upstream.patentFileWrapperDataBag);
  });

  test("explicit projection overrides full and missing count falls back to record length", async () => {
    const api = client(async (request) => {
      expect((await request.json()).fields).toEqual(["applicationNumberText"]);
      return Response.json({
        patentFileWrapperDataBag: [{ applicationNumberText: "16123456" }],
      });
    });
    expect(
      (await api.search({ full: true, fields: ["applicationNumberText"] }))
        .count,
    ).toBe(1);
  });

  test("invalid pagination and range bounds fail before any HTTP request", async () => {
    let calls = 0;
    const api = client(() => {
      calls++;
      return Response.json(upstream);
    });
    for (const options of [
      { limit: 0 },
      { offset: -1 },
      { limit: 1.5 },
      { rangeFilters: [{ field: "filingDate" }] },
    ]) {
      await expect(api.search(options)).rejects.toThrow();
    }
    expect(calls).toBe(0);
  });

  test("normalizes application separators without changing leading zeros", async () => {
    const api = client((request) => {
      expect(request.url).toEndWith("/applications/01234567");
      return Response.json(upstream);
    });
    expect((await api.get(" 01/234,567 ")).count).toBe(1);
    await expect(api.get("../../credentials")).rejects.toThrow(TypeError);
  });

  test("search 404 is empty, while retrieval and document 404 are errors", async () => {
    const api = client(() => new Response("not found", { status: 404 }));
    expect(await api.search()).toMatchObject({ count: 0, patentBag: [] });
    await expect(api.get("16123456")).rejects.toMatchObject({
      status: 404,
      code: "HTTP_ERROR",
    });
    await expect(api.getDocuments("16123456")).rejects.toMatchObject({
      status: 404,
    });
  });

  test("documents include associated metadata by default and allow code filtering", async () => {
    const paths: string[] = [];
    const api = client((request) => {
      paths.push(new URL(request.url).pathname + new URL(request.url).search);
      return request.url.includes("associated-documents")
        ? new Response("not found", { status: 404 })
        : Response.json({
            documentBag: [
              {
                documentIdentifier: "doc-1",
                documentCode: "CTRS",
                pageCount: 0,
                futureField: "retained",
              },
            ],
          });
    });
    const result = await api.getDocuments("16/123,456", {
      documentCodes: ["CTRS", "SOL.NTC.SUIT"],
    });
    expect(paths).toEqual([
      "/api/v1/patent/applications/16123456/documents?documentCodes=CTRS%2CSOL.NTC.SUIT",
      "/api/v1/patent/applications/16123456/associated-documents",
    ]);
    expect(result).toMatchObject({
      documents: [{ pageCount: 0, futureField: "retained" }],
      associatedDocuments: [],
    });
    paths.length = 0;
    expect(
      await api.getDocuments("16123456", { includeAssociated: false }),
    ).not.toHaveProperty("associatedDocuments");
    expect(paths).toHaveLength(1);
  });

  test("malformed or unexpected upstream envelopes fail rather than returning empty records", async () => {
    for (const body of [
      {},
      { count: "1", patentFileWrapperDataBag: [] },
      { patentFileWrapperDataBag: [null] },
      { patentFileWrapperDataBag: [{ applicationMetaData: "invalid" }] },
    ]) {
      await expect(
        client(() => Response.json(body)).search(),
      ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    }
    await expect(
      client(() => new Response("<html>login</html>")).search(),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    await expect(
      client(() => Response.json({})).getDocuments("16123456"),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });

  test("credentials stay out of HTTP and network error objects", async () => {
    for (const handler of [
      () => new Response("synthetic-secret", { status: 403 }),
      () => {
        throw new Error("synthetic-secret");
      },
    ]) {
      try {
        await client(handler).get("16123456");
        throw new Error("expected request failure");
      } catch (error) {
        expect(error).toBeInstanceOf(OdpApiError);
        expect(String(error)).not.toContain("synthetic-secret");
        expect(error).not.toHaveProperty("cause");
        expect(error).not.toHaveProperty("request");
      }
    }
  });

  test("retryable read-only POST searches retry, while auth failures do not", async () => {
    let attempts = 0;
    const api = new ApplicationsClient({
      apiKey: "test",
      retryLimit: 1,
      fetch: mockFetch(() => {
        attempts++;
        return attempts === 1
          ? new Response("busy", {
              status: 503,
              headers: { "Retry-After": "0" },
            })
          : Response.json(upstream);
      }),
    });
    expect((await api.search()).count).toBe(1);
    expect(attempts).toBe(2);
    attempts = 0;
    const denied = new ApplicationsClient({
      apiKey: "test",
      retryLimit: 3,
      fetch: mockFetch(() => {
        attempts++;
        return new Response("denied", { status: 403 });
      }),
    });
    await expect(denied.search()).rejects.toMatchObject({ status: 403 });
    expect(attempts).toBe(1);
  });

  test("timeouts and explicit cancellation stop requests", async () => {
    const server = Bun.serve({
      port: 0,
      hostname: "127.0.0.1",
      async fetch() {
        await Bun.sleep(100);
        return Response.json(upstream);
      },
    });
    try {
      const api = new ApplicationsClient({
        apiKey: "test",
        baseUrl: server.url.href,
        timeoutMs: 10,
        retryLimit: 0,
      });
      await expect(api.search()).rejects.toMatchObject({ code: "TIMEOUT" });
      const controller = new AbortController();
      controller.abort();
      await expect(
        api.get("16123456", { signal: controller.signal }),
      ).rejects.toMatchObject({ code: "ABORTED" });
    } finally {
      await server.stop(true);
    }
  });

  test("redirects cannot forward the API key to a different origin", async () => {
    let forwarded = false;
    const destination = Bun.serve({
      port: 0,
      hostname: "127.0.0.1",
      fetch() {
        forwarded = true;
        return Response.json(upstream);
      },
    });
    const source = Bun.serve({
      port: 0,
      hostname: "127.0.0.1",
      fetch() {
        return Response.redirect(destination.url);
      },
    });
    try {
      const api = new ApplicationsClient({
        apiKey: "test",
        baseUrl: source.url.href,
        retryLimit: 0,
      });
      await expect(api.search()).rejects.toMatchObject({
        code: "NETWORK_ERROR",
      });
      expect(forwarded).toBe(false);
    } finally {
      await source.stop(true);
      await destination.stop(true);
    }
  });

  test("configuration requires credentials and secure remote URLs", () => {
    expect(() => new ApplicationsClient({ apiKey: " " })).toThrow(
      ConfigurationError,
    );
    expect(
      () =>
        new ApplicationsClient({
          apiKey: "test",
          baseUrl: "http://example.com",
        }),
    ).toThrow(ConfigurationError);
    expect(
      () =>
        new ApplicationsClient({
          apiKey: "test",
          baseUrl: "https://user:pass@example.com",
        }),
    ).toThrow(ConfigurationError);
  });
});

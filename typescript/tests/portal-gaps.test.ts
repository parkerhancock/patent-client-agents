import { expect, test } from "bun:test";
import { PublicationsClient } from "../packages/client/src/publications.js";
import {
  convertBiblio,
  convertDocument,
  htmlToText,
} from "../packages/client/src/publications-models.js";
import { TrademarkSearchClient } from "../packages/client/src/trademark-search.js";

const token = () => ({
  token: "synthetic-waf",
  expires: Date.now() / 1000 + 86400,
});
const json = (value: unknown) => Response.json(value);
function ppubs(
  overrides: (request: Request) => Response | undefined = () => undefined,
) {
  const paths: string[] = [];
  const fetcher = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init),
      path = new URL(request.url).pathname;
    paths.push(path);
    const override = overrides(request);
    if (override) return override;
    if (path === "/pubwebapp/") return new Response("landing");
    if (path.endsWith("/session")) return json({ userCase: { caseId: 1 } });
    if (path.endsWith("/counts")) return json({ numResults: 1 });
    if (path.endsWith("/searchWithBeFamily"))
      return json({
        numFound: 1,
        patents: [
          {
            guid: "US-1-B2",
            type: "USPAT",
            publicationReferenceDocumentNumber: "1",
          },
        ],
      });
    if (path.includes("/highlight/"))
      return json({
        guid: "US-1-B2",
        type: "USPAT",
        pubRefDocNumber: "1",
        inventionTitle: "Sample",
        pageCount: 1,
        imageLocation: "images/one",
      });
    if (path.endsWith("/imageviewer")) return new Response('"job"');
    if (path.endsWith("/print-process"))
      return json([{ printStatus: "COMPLETED", pdfName: "sample.pdf" }]);
    if (path.endsWith("/sample.pdf")) return new Response("%PDF-1.7 test");
    throw new Error(`Unexpected synthetic request ${path}`);
  }) as unknown as typeof fetch;
  return {
    client: new PublicationsClient({
      fetch: fetcher,
      retryLimit: 0,
      pollIntervalMs: 0,
    }),
    paths,
  };
}
test("pre-cancelled portal requests make no session or token-provider calls", async () => {
  const controller = new AbortController();
  controller.abort();
  const fake = ppubs();
  await expect(
    fake.client.searchBiblio({ query: "widget", signal: controller.signal }),
  ).rejects.toMatchObject({ code: "ABORTED" });
  expect(fake.paths).toEqual([]);
  let refreshes = 0;
  const tm = new TrademarkSearchClient({
    refreshToken: async () => {
      refreshes++;
      return token();
    },
  });
  await expect(
    tm.searchWordmark("widget", { signal: controller.signal }),
  ).rejects.toMatchObject({ code: "ABORTED" });
  expect(refreshes).toBe(0);
});
test("PPUBS rejects malformed counts/search/document/print responses instead of empty success", async () => {
  for (const [path, body] of [
    ["/counts", {}],
    ["/counts", null],
    ["/searchWithBeFamily", {}],
    ["/searchWithBeFamily", { numFound: 1, patents: [null] }],
  ] as const) {
    const { client, paths } = ppubs((request) =>
      new URL(request.url).pathname.endsWith(path) ? json(body) : undefined,
    );
    await expect(
      client.searchBiblio({ query: "widget" }),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    if (path === "/counts")
      expect(paths.some((path) => path.endsWith("/searchWithBeFamily"))).toBe(
        false,
      );
  }
  const badDocument = ppubs((request) =>
    request.url.includes("/highlight/") ? json({}) : undefined,
  );
  await expect(
    badDocument.client.getDocument("US-1-B2", { source: "USPAT" }),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  for (const body of [null, [], [{ printStatus: "COMPLETED" }]]) {
    const { client } = ppubs((request) =>
      request.url.endsWith("/print-process") ? json(body) : undefined,
    );
    await expect(
      client.downloadPdf({
        guid: "one",
        type: "USPAT",
        image_location: "images",
        document_structure: { page_count: 1 },
      }),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  }
});
test("resolve-and-download facade returns PDF plus publication metadata and rejects HTML bytes", async () => {
  const { client } = ppubs();
  const result = await client.resolveAndDownloadPdf("US1B2");
  expect(result.guid).toBe("US-1-B2");
  expect(result.publication_number).toBe("1");
  expect(result.patent_title).toBe("Sample");
  expect(Buffer.from(result.pdf_base64, "base64").toString()).toStartWith(
    "%PDF-",
  );
  const bad = ppubs((request) =>
    request.url.endsWith("/sample.pdf")
      ? new Response("<html>service unavailable</html>")
      : undefined,
  );
  await expect(bad.client.resolveAndDownloadPdf("US1B2")).rejects.toMatchObject(
    { code: "INVALID_RESPONSE" },
  );
});
test("PPUBS biblio retains Python fields and child dates preserve null normalization", () => {
  const record = convertBiblio({
    kindCode: ["B2"],
    cpcInventiveFlattened: "G06F; H04L",
    imageLocation: "images",
    documentSize: "123",
    familyIdentifierCur: "42",
    governmentInterest: ["Grant"],
  });
  expect(record).toMatchObject({
    kind_code: "B2",
    cpc_inventive: ["G06F", "H04L"],
    image_location: "images",
    document_size: 123,
    family_identifier_cur: 42,
    government_interest: ["Grant"],
  });
  const doc = convertDocument({
    relatedApplNumber: ["123"],
    relatedApplFilingDate: ["20230231"],
    cpcInventive: [null, "G06F 1/00  ignored 20200101"],
  });
  expect(
    (doc.related_apps as Record<string, unknown>[])[0]?.filing_date,
  ).toBeNull();
  expect(doc.cpc_inventive).toEqual([
    { cpc_class: null, cpc_subclass: null, version: null },
    { cpc_class: "G06F", cpc_subclass: "1/00", version: "2020-01-01" },
  ]);
  expect(
    htmlToText('<span title="a > b">A &amp; B</span><!-- private -->'),
  ).toBe("A & B");
  expect(htmlToText("A < 3 and B > 4")).toBe("A < 3 and B > 4");
});
test("near-expiry WAF sessions refresh once concurrently and provider errors stay secret-free", async () => {
  let refreshes = 0;
  const client = new TrademarkSearchClient({
    token: { token: "old", expires: Date.now() / 1000 + 3600 },
    refreshToken: async () => {
      refreshes++;
      await Bun.sleep(5);
      return token();
    },
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(new Request(input, init).headers.get("cookie")).toBe(
        "aws-waf-token=synthetic-waf",
      );
      return json({ hits: { totalValue: 0, hits: [] } });
    }) as unknown as typeof fetch,
  });
  await Promise.all([client.searchOwner("Acme"), client.searchOwner("Widget")]);
  expect(refreshes).toBe(1);
  const failure = new TrademarkSearchClient({
    refreshToken: async () => {
      throw new Error("sensitive-provider-secret");
    },
  });
  await expect(failure.searchOwner("Acme")).rejects.toThrow(
    "external WAF session refresh failed",
  );
  try {
    await failure.searchOwner("Acme");
  } catch (error) {
    expect(String(error)).not.toContain("sensitive-provider-secret");
    expect(error).not.toHaveProperty("cause");
  }
});
test("malformed trademark successes fail without refreshing, and real query errors do not refresh", async () => {
  for (const body of [
    "not json",
    {},
    { hits: {} },
    { hits: { totalValue: 1, hits: [null] } },
  ]) {
    let refreshes = 0;
    const client = new TrademarkSearchClient({
      token: token(),
      refreshToken: async () => {
        refreshes++;
        return token();
      },
      fetch: (async () =>
        typeof body === "string"
          ? new Response(body)
          : json(body)) as unknown as typeof fetch,
    });
    await expect(client.searchOwner("Acme")).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
    expect(refreshes).toBe(0);
  }
  let refreshes = 0;
  const client = new TrademarkSearchClient({
    token: token(),
    refreshToken: async () => {
      refreshes++;
      return token();
    },
    fetch: (async () =>
      new Response("bad query", { status: 400 })) as unknown as typeof fetch,
  });
  await expect(client.searchOwner("Acme")).rejects.toMatchObject({
    status: 400,
  });
  expect(refreshes).toBe(0);
});
test("trademark pagination never requests outside the upstream 10000-result window", async () => {
  const requests: { size: number; from: number }[] = [];
  const client = new TrademarkSearchClient({
    token: token(),
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      const body = await new Request(input, init).json();
      requests.push(body);
      return json({
        hits: {
          totalValue: 20000,
          hits: Array.from({ length: body.size }, (_, i) => ({
            id: String(body.from + i),
            source: { alive: true },
          })),
        },
      });
    }) as unknown as typeof fetch,
  });
  expect(
    (await client.searchOwner("Acme", { from: 9999, size: 500 })).results,
  ).toHaveLength(1);
  expect(requests[0]?.size).toBe(1);
  await expect(client.searchOwner("Acme", { from: 10000 })).rejects.toThrow(
    "pagination",
  );
  requests.length = 0;
  expect(
    await client.searchAll({ owner: "Acme", maxResults: 3, batchSize: 2 }),
  ).toHaveLength(3);
  expect(requests.map((r) => [r.from, r.size])).toEqual([
    [0, 2],
    [2, 1],
  ]);
});

test("cancellation stops waiting for a trusted WAF provider without exposing its credentials", async () => {
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  const controller = new AbortController();
  let calls = 0;
  const client = new TrademarkSearchClient({
    refreshToken: async () => {
      await waiting;
      return token();
    },
    fetch: (async () => {
      calls++;
      return json({ hits: { totalValue: 0, hits: [] } });
    }) as unknown as typeof fetch,
  });
  const request = client.searchOwner("Acme", { signal: controller.signal });
  controller.abort();
  await expect(request).rejects.toMatchObject({ code: "ABORTED" });
  release();
  await Bun.sleep(0);
  expect(calls).toBe(0);
  expect((await client.searchOwner("Acme")).total).toBe(0);
  expect(calls).toBe(1);
});

test("cancellation stops a PPUBS caller waiting for shared session initialization", async () => {
  let release!: (response: Response) => void;
  const landing = new Promise<Response>((resolve) => {
    release = resolve;
  });
  let calls = 0;
  const controller = new AbortController();
  const client = new PublicationsClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) => {
      const path = new URL(new Request(input).url).pathname;
      calls++;
      if (path === "/pubwebapp/") return landing;
      return json({ userCase: { caseId: 1 } });
    }) as typeof fetch,
  });
  const request = client.searchBiblio({
    query: "widget",
    signal: controller.signal,
  });
  controller.abort();
  await expect(request).rejects.toMatchObject({ code: "ABORTED" });
  release(new Response("landing"));
  await Bun.sleep(0);
  expect(calls).toBe(2); // Shared bootstrap finishes; the cancelled caller never sends a search.
});

test("PPUBS print deadline is a timeout rather than a caller cancellation", async () => {
  const client = new PublicationsClient({
    pollTimeoutMs: 15,
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) => {
      const request = new Request(input),
        path = new URL(request.url).pathname;
      if (path === "/pubwebapp/") return new Response("landing");
      if (path.endsWith("/session")) return json({ userCase: { caseId: 1 } });
      if (path.endsWith("/imageviewer")) return new Response('"job"');
      return new Promise<Response>((_resolve, reject) => {
        request.signal.addEventListener(
          "abort",
          () => reject(request.signal.reason),
          { once: true },
        );
        if (request.signal.aborted) reject(request.signal.reason);
      });
    }) as typeof fetch,
  });
  await expect(
    client.downloadPdf({
      guid: "one",
      type: "USPAT",
      image_location: "images",
      document_structure: { page_count: 1 },
    }),
  ).rejects.toMatchObject({ code: "TIMEOUT" });
});

test("portal MCP forwards the complete PPUBS query options", async () => {
  const { FastMCP } = await import("@prefecthq/fastmcp-ts/server");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const { registerPortalSearchTools } = await import(
    "../packages/mcp/src/search-portals.js"
  );
  let request: unknown;
  const publications = {
    async searchBiblio(options: unknown) {
      request = options;
      return {
        docs: [],
        num_found: 0,
        num_documents: 0,
        provenance: {
          source_url: "https://ppubs.uspto.gov",
          source_name: "USPTO PPUBS",
          retrieved_at: new Date().toISOString(),
          cache_hit: false as const,
        },
      };
    },
  } as unknown as PublicationsClient;
  const server = new FastMCP({ name: "portal-options", version: "1" });
  registerPortalSearchTools(server, {
    publications,
    trademarkSearch: {} as TrademarkSearchClient,
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    await client.callTool("search_patents", {
      query: "widget",
      default_operator: "AND",
      expand_plurals: false,
      british_equivalents: false,
    });
    expect(request).toMatchObject({
      query: "widget",
      defaultOperator: "AND",
      expandPlurals: false,
      britishEquivalents: false,
    });
  } finally {
    await client.close();
    await server.close();
  }
});

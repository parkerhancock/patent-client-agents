import { expect, test } from "bun:test";
import { parseGrantClaimsXml } from "../packages/client/src/application-xml.js";
import { ApplicationsClient } from "../packages/client/src/applications.js";

function api(handler: (request: Request) => Response | Promise<Response>) {
  return new ApplicationsClient({
    apiKey: "synthetic",
    retryLimit: 0,
    fetch: (async (input, init) =>
      handler(new Request(input, init))) as typeof fetch,
  });
}
const bag = (records: Record<string, unknown>[]) => ({
  count: records.length,
  patentFileWrapperDataBag: records,
});

test("application library permits source-supported page sizes above the MCP cap", async () => {
  const requests: Request[] = [];
  const client = api((request) => {
    requests.push(request);
    return Response.json(bag([]));
  });
  await client.search({ limit: 250 });
  const payload = await requests[0]?.json();
  expect(payload?.pagination.limit).toBe(250);
  await client.search({ method: "GET", limit: 250 });
  expect(new URL(requests[1]?.url ?? "").searchParams.get("limit")).toBe("250");
});

test("grant fallback claim numbers count parsed claims rather than empty source elements", () => {
  const claims = parseGrantClaimsXml(
    "<us-patent-grant><claim/><claim><claim-text>A device.</claim-text></claim><claim/><claim><claim-text>Another device.</claim-text></claim></us-patent-grant>",
  );
  expect(claims.map((claim) => claim.claim_number)).toEqual([1, 2]);
});

test("grant claim text decodes numeric character references", () => {
  const [claim] = parseGrantClaimsXml(
    "<us-patent-grant><claim><claim-text>A 5&#x3bc;m film &#956; &amp; &#x26;lt;</claim-text></claim></us-patent-grant>",
  );
  expect(JSON.stringify(claim)).toContain("A 5μm film μ & &lt;");
  expect(JSON.stringify(claim)).not.toContain("&#");
});

test("batch document download lists history once and follows each advertised format URL", async () => {
  const paths: string[] = [];
  const client = api((request) => {
    const path = new URL(request.url).pathname;
    paths.push(path);
    return path.endsWith("/documents")
      ? Response.json({
          documentBag: [
            {
              documentIdentifier: "AAA",
              documentCode: "CLM",
              downloadOptionBag: [
                {
                  mimeTypeIdentifier: "MS_WORD",
                  downloadUrl: "/document-a.docx",
                },
              ],
            },
            {
              documentIdentifier: "BBB",
              documentCode: "SPEC",
              downloadOptionBag: [
                {
                  mimeTypeIdentifier: "MS_WORD",
                  downloadUrl: "/document-b.docx",
                },
              ],
            },
          ],
        })
      : new Response(path);
  });
  const results = await client.downloadDocuments("16123456", {
    format: "docx",
  });
  expect(paths).toEqual([
    "/api/v1/patent/applications/16123456/documents",
    "/document-a.docx",
    "/document-b.docx",
  ]);
  expect(
    results.map((result) => new TextDecoder().decode(result.data)),
  ).toEqual(["/document-a.docx", "/document-b.docx"]);
});

test("application GET search serializes the documented query grammar without a body", async () => {
  const client = api(async (request) => {
    const query = new URL(request.url).searchParams;
    expect(request.method).toBe("GET");
    expect(await request.text()).toBe("");
    expect(Object.fromEntries(query)).toEqual({
      q: "applicationNumberText:14412875",
      offset: "2",
      limit: "3",
      fields: "applicationNumberText",
      facets: "applicationMetaData.applicationStatusCode",
      filters: "applicationMetaData.applicationTypeCode UTL,DES",
      rangeFilters: "applicationMetaData.applicationStatusCode 150:160",
      sort: "applicationMetaData.filingDate desc",
    });
    return Response.json(bag([{ applicationNumberText: "14412875" }]));
  });
  expect(
    (
      await client.search({
        method: "GET",
        query: "applicationNumberText:14412875",
        offset: 2,
        limit: 3,
        fields: ["applicationNumberText"],
        facets: ["applicationMetaData.applicationStatusCode"],
        filters: [
          {
            name: "applicationMetaData.applicationTypeCode",
            value: ["UTL", "DES"],
          },
        ],
        rangeFilters: [
          {
            field: "applicationMetaData.applicationStatusCode",
            valueFrom: 150,
            valueTo: 160,
          },
        ],
        sort: [{ field: "applicationMetaData.filingDate", order: "Desc" }],
      })
    ).count,
  ).toBe(1);
});

test("numeric POST ranges retain zero bounds and never acquire invented date bounds", async () => {
  const client = api(async (request) => {
    const body = await request.json();
    expect(body.rangeFilters).toEqual([
      {
        field: "applicationMetaData.applicationStatusCode",
        valueFrom: "0",
        valueTo: "160",
      },
    ]);
    return Response.json(bag([]));
  });
  await client.search({
    rangeFilters: [
      {
        field: "applicationMetaData.applicationStatusCode",
        valueFrom: 0,
        valueTo: "160",
      },
    ],
  });
});

test("unsupported GET combinations and invalid ranges fail before HTTP", async () => {
  let calls = 0;
  const client = api(() => {
    calls++;
    return Response.json(bag([]));
  });
  for (const options of [
    { method: "GET" as const, rawPayload: { q: "query" } },
    {
      method: "GET" as const,
      filters: [
        { name: "one", value: ["1"] },
        { name: "two", value: ["2"] },
      ],
    },
    {
      rangeFilters: [
        { field: "applicationMetaData.applicationStatusCode", valueFrom: 150 },
      ],
    },
    {
      rangeFilters: [
        {
          field: "applicationMetaData.applicationStatusCode",
          valueFrom: 160,
          valueTo: 150,
        },
      ],
    },
    {
      rangeFilters: [
        { field: "applicationMetaData.filingDate", valueFrom: "2026-02-30" },
      ],
    },
    {
      rangeFilters: [
        {
          field: "applicationMetaData.filingDate",
          valueFrom: "2025-01-01",
          valueTo: "2020-01-01",
        },
      ],
    },
  ])
    await expect(client.search(options)).rejects.toThrow();
  expect(calls).toBe(0);
});

test("GET search downloads and status-code lookups expose all three previously missing operations", async () => {
  const client = api(async (request) => {
    const url = new URL(request.url);
    expect(request.method).toBe("GET");
    expect(await request.text()).toBe("");
    if (url.pathname.endsWith("/download")) {
      expect(Object.fromEntries(url.searchParams)).toEqual({
        q: "applicationNumberText:14412875",
        fields: "applicationNumberText",
        format: "csv",
        offset: "0",
        limit: "1",
      });
      return new Response("applicationNumberText\n14412875", {
        headers: { "content-type": "text/csv" },
      });
    }
    expect(Object.fromEntries(url.searchParams)).toEqual({
      q: "applicationStatusCode:150",
      offset: "0",
      limit: "1",
    });
    return Response.json({
      count: 1,
      statusCodeBag: [{ applicationStatusCode: 150 }],
    });
  });
  expect(
    new TextDecoder().decode(
      (
        await client.downloadSearch(
          {
            q: "applicationNumberText:14412875",
            fields: ["applicationNumberText"],
            format: "csv",
            offset: 0,
            limit: 1,
          },
          { method: "GET" },
        )
      ).data,
    ),
  ).toContain("14412875");
  expect(
    (
      await client.getStatusCodes(
        { q: "applicationStatusCode:150", offset: 0, limit: 1 },
        { method: "GET" },
      )
    ).data.count,
  ).toBe(1);
});

test("raw POST payload overrides validation of unused generated-search parameters", async () => {
  const client = api(async (request) => {
    expect(await request.json()).toEqual({
      q: "source-specific",
      fields: ["customField"],
    });
    return Response.json(bag([]));
  });
  await client.search({
    limit: 0,
    rawPayload: { q: "source-specific", fields: ["customField"] },
  });
});

test("batch file-history filters AND identifiers, codes and inclusive dates", async () => {
  const docs = [
    {
      documentIdentifier: "AAA",
      documentCode: "CLM",
      officialDate: "2020-01-02T00:00:00Z",
    },
    {
      documentIdentifier: "BBB",
      documentCode: "SPEC",
      officialDate: "2020-01-03",
    },
    {
      documentIdentifier: "CCC",
      documentCode: "CLM",
      officialDate: "2020-02-04",
    },
    { documentIdentifier: "DDD", documentCode: "CLM", officialDate: "unknown" },
    {
      documentIdentifier: "EEE",
      documentCode: "CLM",
      documentDate: "2020-01-05",
    },
  ];
  const calls: string[] = [];
  const client = api((request) => {
    const url = new URL(request.url);
    calls.push(url.pathname);
    return url.pathname.endsWith("/documents")
      ? Response.json({ documentBag: docs })
      : new Response("PDF");
  });
  const results = await client.downloadDocuments("16123456", {
    documentIdentifiers: ["AAA", "BBB", "EEE"],
    documentCodes: ["CLM"],
    officialDateFrom: "2020-01-02",
    officialDateTo: "2020-01-05",
    maxDocuments: 50,
  });
  expect(results.map((result) => result.document.documentIdentifier)).toEqual([
    "AAA",
    "EEE",
  ]);
  expect(calls).toHaveLength(3);
});

test("batch count guard refuses selections above50 before any document download", async () => {
  let binaries = 0;
  const client = api((request) => {
    if (new URL(request.url).pathname.endsWith("/documents"))
      return Response.json({
        documentBag: Array.from({ length: 51 }, (_, index) => ({
          documentIdentifier: `DOC${index}`,
        })),
      });
    binaries++;
    return new Response("PDF");
  });
  await expect(
    client.downloadDocuments("16123456", { maxDocuments: 50 }),
  ).rejects.toThrow("51 matching documents; max 50");
  expect(binaries).toBe(0);
});

test("batch download bounds concurrency at4 and preserves listing order", async () => {
  let active = 0,
    peak = 0;
  const client = api(async (request) => {
    const path = new URL(request.url).pathname;
    if (path.endsWith("/documents"))
      return Response.json({
        documentBag: Array.from({ length: 9 }, (_, index) => ({
          documentIdentifier: `DOC${index}`,
        })),
      });
    active++;
    peak = Math.max(peak, active);
    await Bun.sleep(5);
    active--;
    return new Response(path);
  });
  const results = await client.downloadDocuments("16123456", {
    maxDocuments: 50,
  });
  expect(peak).toBe(4);
  expect(results.map((result) => result.document.documentIdentifier)).toEqual(
    Array.from({ length: 9 }, (_, index) => `DOC${index}`),
  );
});

test("batch aggregate byte budget rejects combined files even when each file fits", async () => {
  const client = api((request) =>
    new URL(request.url).pathname.endsWith("/documents")
      ? Response.json({
          documentBag: [
            { documentIdentifier: "AAA" },
            { documentIdentifier: "BBB" },
          ],
        })
      : new Response("1234"),
  );
  await expect(
    client.downloadDocuments("16123456", { maxTotalBytes: 5 }),
  ).rejects.toThrow("combined byte limit");
});

test("MCP file-history download publishes a real ZIP and manifest without document bodies", async () => {
  const { createServer } = await import("../packages/mcp/src/index.js");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const { readFile } = await import("node:fs/promises");
  const { unzipSync } = await import("fflate");
  const client = api((request) =>
    new URL(request.url).pathname.endsWith("/documents")
      ? Response.json({
          documentBag: [
            {
              documentIdentifier: "AAA",
              documentCode: "CLM",
              officialDate: "2020-01-02",
            },
            {
              documentIdentifier: "BBB",
              documentCode: "SPEC",
              officialDate: "2020-01-03",
            },
          ],
        })
      : new Response("%PDF-do-not-inline"),
  );
  const server = createServer({ clients: { applications: client } });
  const rpc = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await rpc.callTool<{
      file_path: string;
      content_type: string;
    }>("download_file_history", {
      application_number: "16123456",
      document_codes: ["CLM"],
      after: "2020-01-01",
      before: "2020-01-02",
    });
    expect(result.structuredContent?.content_type).toBe("application/zip");
    const files = unzipSync(
      await readFile(result.structuredContent?.file_path as string),
    );
    expect(Object.keys(files).sort()).toEqual([
      "2020-01-02_CLM_AAA.pdf",
      "manifest.json",
    ]);
    expect(new TextDecoder().decode(files["2020-01-02_CLM_AAA.pdf"])).toBe(
      "%PDF-do-not-inline",
    );
    const manifest = JSON.parse(
      new TextDecoder().decode(files["manifest.json"]),
    );
    expect(manifest.documents[0]).toMatchObject({
      document_identifier: "AAA",
      document_code: "CLM",
      size: 18,
    });
    expect(manifest.documents[0].sha256).toHaveLength(64);
    expect(JSON.stringify(result)).not.toContain("%PDF-do-not-inline");
    await expect(
      rpc.callTool("download_file_history", {
        application_number: "16123456",
        document_codes: ["NOA"],
      }),
    ).rejects.toThrow("No file-history documents");
  } finally {
    await rpc.close();
    await server.close();
  }
});

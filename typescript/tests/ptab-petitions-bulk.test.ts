import { describe, expect, test } from "bun:test";
import { BulkDataClient } from "../packages/client/src/bulkdata.js";
import { PetitionsClient } from "../packages/client/src/petitions.js";
import {
  PtabAppealsClient,
  PtabInterferencesClient,
  PtabTrialsClient,
} from "../packages/client/src/ptab.js";

function mock(data: unknown, status = 200) {
  const requests: Request[] = [];
  const fetch = Object.assign(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push(new Request(input, init));
      return Response.json(data, { status });
    },
    { preconnect: globalThis.fetch.preconnect },
  ) as typeof globalThis.fetch;
  return { options: { apiKey: "fixture-key", fetch, retryLimit: 0 }, requests };
}
describe("PTAB payloads and response contracts", () => {
  test("all trial search routes use source-specific bags and preserve unknown data", async () => {
    for (const [method, key, path] of [
      ["searchProceedings", "patentTrialProceedingDataBag", "proceedings"],
      ["searchDecisions", "patentTrialDocumentDataBag", "decisions"],
      ["searchDocuments", "patentTrialDocumentDataBag", "documents"],
    ] as const) {
      const m = mock({
        count: 1,
        [key]: [{ trialNumber: "IPR2025-00001", futureField: "retained" }],
        futureTop: true,
      });
      const response = await new PtabTrialsClient(m.options)[method]({
        query: "trialNumber:IPR*",
        sort: { field: "trialNumber", order: "Desc" },
        limit: 1,
        offset: 0,
        rangeFilters: [
          { field: "documentNumber", valueFrom: "1", valueTo: "20" },
        ],
      });
      expect(
        (response[key] as Array<Record<string, unknown>>)[0]?.futureField,
      ).toBe("retained");
      expect(response.futureTop).toBe(true);
      expect(m.requests[0]?.url).toEndWith(`/trials/${path}/search`);
      expect(await m.requests[0]?.json()).toEqual({
        q: "trialNumber:IPR*",
        sort: [{ field: "trialNumber", order: "Desc" }],
        pagination: { limit: 1, offset: 0 },
        rangeFilters: [
          { field: "documentNumber", valueFrom: "1", valueTo: "20" },
        ],
      });
    }
  });
  test("search404empty and get404failure, with single-record wrapping", async () => {
    const m = mock({}, 404),
      client = new PtabTrialsClient(m.options);
    expect((await client.searchDecisions()).patentTrialDocumentDataBag).toEqual(
      [],
    );
    await expect(client.getDecision("missing")).rejects.toMatchObject({
      status: 404,
    });
    const single = mock({
      documentData: { documentIdentifier: "doc" },
      unknown: 3,
    });
    expect(
      (await new PtabTrialsClient(single.options).getDocument("doc"))
        .patentTrialDocumentDataBag[0]?.unknown,
    ).toBe(3);
  });
  test("all download bags normalize with derived count", async () => {
    for (const [Class, source, key] of [
      [PtabAppealsClient, "patentTrialData", "patentAppealDataBag"],
      [
        PtabInterferencesClient,
        "interferenceData",
        "patentInterferenceDataBag",
      ],
    ] as const) {
      const m = mock({
        [source]: [{ documentData: { documentIdentifier: "record" } }],
      });
      const r = await new Class(m.options).download({ limit: 1 });
      expect(r.count).toBe(1);
      expect(r[key]).toHaveLength(1);
      expect((await m.requests[0]?.json())?.pagination).toEqual({ limit: 1 });
    }
    const m = mock({ patentTrialData: [{ trialNumber: "IPR2024-00001" }] });
    expect(
      (await new PtabTrialsClient(m.options).downloadProceedings()).count,
    ).toBe(1);
  });
  test("identifier encoding and decisions-by-number routes", async () => {
    for (const [Class, family] of [
      [PtabAppealsClient, "appeals"],
      [PtabInterferencesClient, "interferences"],
    ] as const) {
      const m = mock({});
      await new Class(m.options).getDecisionsByNumber(" 123/4 ");
      expect(m.requests[0]?.url).toEndWith(`/${family}/123%2F4/decisions`);
    }
    const m = mock({});
    const c = new PtabTrialsClient(m.options);
    await c.getDocumentsByTrial("IPR2025-1");
    await c.getDecisionsByTrial("IPR2025-1");
    expect(m.requests[0]?.url).toEndWith("/trials/IPR2025-1/documents");
    expect(m.requests[1]?.url).toEndWith("/trials/IPR2025-1/decisions");
    expect(() => c.getProceeding(" ")).toThrow();
  });
  test("CSV download returns raw bytes", async () => {
    const requests: Request[] = [];
    const fetch = Object.assign(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        requests.push(new Request(input, init));
        return new Response("trialNumber\nIPR2025-1\n", {
          headers: { "content-type": "text/csv" },
        });
      },
      { preconnect: globalThis.fetch.preconnect },
    ) as typeof globalThis.fetch;
    const result = await new PtabTrialsClient({
      apiKey: "fixture-key",
      fetch,
    }).downloadDecisionsFile({ fileFormat: "csv", limit: 1 });
    expect(new TextDecoder().decode(result.data)).toContain("trialNumber");
    expect((await requests[0]?.json())?.format).toBe("csv");
  });
});
describe("Petition decisions", () => {
  test("preserves new decision outcome/text fields and includes documents only on request", async () => {
    const m = mock({
      count: 1,
      petitionDecisionDataBag: [
        {
          petitionDecisionRecordIdentifier: "p1",
          decisionTypeCode: "denied",
          petitionText: "new searchable text",
          documentBag: [
            {
              documentIdentifier: "d1",
              downloadOptionBag: [{ downloadUrl: "/download" }],
            },
          ],
        },
      ],
    });
    const c = new PetitionsClient(m.options);
    const result = await c.search({ query: "petitionText:revival" });
    expect(result.petitionDecisionDataBag[0]?.petitionText).toBe(
      "new searchable text",
    );
    await c.get("p1", { includeDocuments: true });
    await c.get("p1", { includeDocuments: false });
    expect(m.requests[1]?.url).toEndWith("/p1?includeDocuments=true");
    expect(m.requests[2]?.url).toEndWith("/p1");
  });
  test("search/download404empty; identifier404propagates", async () => {
    const m = mock({}, 404),
      c = new PetitionsClient(m.options);
    expect((await c.search()).count).toBe(0);
    expect((await c.download()).petitionDecisionDataBag).toEqual([]);
    await expect(c.get("missing")).rejects.toMatchObject({ status: 404 });
  });
});
describe("Bulk products", () => {
  test("GET search joins fields; get preservesfalse/zero and exact datequerynames", async () => {
    const m = mock({
      count: 1,
      bulkDataProductBag: [
        {
          productIdentifier: "PTGRXML",
          productFileBag: {
            fileDataBag: [{ fileName: "file.zip", fileSize: 4 }],
          },
        },
      ],
    });
    const c = new BulkDataClient(m.options);
    expect(
      (
        await c.search({
          fields: [" productIdentifier ", "productTitleText"],
          facets: "a, b",
        })
      ).bulkDataProductBag[0]?.productFileBag?.fileDataBag[0]?.fileSize,
    ).toBe(4);
    expect(
      new URL(m.requests[0]?.url ?? "https://invalid.test").searchParams.get(
        "fields",
      ),
    ).toBe("productIdentifier,productTitleText");
    await c.getProduct("PTGRXML", {
      includeFiles: false,
      latestOnly: false,
      offset: 0,
      fileFromDate: "2026-01-01",
      fileToDate: "2026-02-01",
    });
    expect(
      Object.fromEntries(
        new URL(m.requests[1]?.url ?? "https://invalid.test").searchParams,
      ),
    ).toEqual({
      includeFiles: "false",
      latest: "false",
      offset: "0",
      fileDataFromDate: "2026-01-01",
      fileDataToDate: "2026-02-01",
    });
  });
  test("product404 is empty and bulk file path is encoded", async () => {
    const m = mock({}, 404);
    expect(
      (await new BulkDataClient(m.options).getProduct("missing"))
        .bulkDataProductBag,
    ).toEqual([]);
    const binary = mock({});
    await new BulkDataClient(binary.options).downloadFile(
      "PROD",
      "some file.zip",
    );
    expect(binary.requests[0]?.url).toEndWith(
      "/products/files/PROD/some%20file.zip",
    );
  });
});

test("records MCP advertises constrained tools, uses library, and returns metadata envelopes", async () => {
  const { FastMCP } = await import("@prefecthq/fastmcp-ts/server");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const { registerOdpRecordTools } = await import(
    "../packages/mcp/src/odp-records.js"
  );
  const m = mock({
    count: 2,
    patentTrialDocumentDataBag: [{ trialNumber: "IPR2025-00001" }],
  });
  const server = new FastMCP({
    name: "records-test",
    version: "0.1.0",
    logLevel: "error",
  });
  registerOdpRecordTools(server, {
    trials: new PtabTrialsClient(m.options),
    appeals: new PtabAppealsClient(m.options),
    interferences: new PtabInterferencesClient(m.options),
    petitions: new PetitionsClient(m.options),
    bulk: new BulkDataClient(m.options),
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const tools = await client.listTools();
    expect(tools).toHaveLength(9);
    expect(
      tools.every((t) => t.annotations?.readOnlyHint && t.outputSchema),
    ).toBe(true);
    const result = await client.callTool<{
      items: Array<{ trialNumber: string }>;
      next_cursor: string;
    }>("search_ptab", { dataset: "trials", entity: "decisions", limit: 1 });
    expect(result.structuredContent?.items[0]?.trialNumber).toBe(
      "IPR2025-00001",
    );
    expect(result.structuredContent?.next_cursor).toBeString();
    await client.callTool("search_ptab", {
      dataset: "trials",
      entity: "decisions",
      limit: 1,
      cursor: result.structuredContent?.next_cursor,
    });
    expect((await m.requests[1]?.json())?.pagination.offset).toBe(1);
    await expect(
      client.callTool("search_ptab", {
        dataset: "trials",
        entity: "decisions",
        limit: 1,
        query: "different",
        cursor: result.structuredContent?.next_cursor,
      }),
    ).rejects.toThrow("different query");
    const download = await client.callTool<{
      file_path?: string;
      download_url?: string;
      size: number;
    }>("download_ptab", { dataset: "trials", entity: "decisions", limit: 1 });
    expect(
      download.structuredContent?.file_path ??
        download.structuredContent?.download_url,
    ).toBeString();
    expect(download.structuredContent?.size).toBeGreaterThan(0);
    await expect(
      client.callTool("search_ptab", {
        dataset: "appeals",
        entity: "documents",
      }),
    ).rejects.toThrow("decisions only");
  } finally {
    await client.close();
  }
});

test("PTAB, petition and bulk live recordings replay through actual clients", async () => {
  const { recorded } = await import("./cassettes.js");
  const options = { apiKey: "replay-placeholder", retryLimit: 0 };
  const trials = new PtabTrialsClient(options);
  for (const [name, run, key] of [
    [
      "ptab-proceedings",
      () => trials.searchProceedings({ limit: 1 }),
      "patentTrialProceedingDataBag",
    ],
    [
      "ptab-decisions",
      () => trials.searchDecisions({ limit: 1 }),
      "patentTrialDocumentDataBag",
    ],
    [
      "ptab-documents",
      () => trials.searchDocuments({ limit: 1 }),
      "patentTrialDocumentDataBag",
    ],
    [
      "ptab-appeals",
      () => new PtabAppealsClient(options).search({ limit: 1 }),
      "patentAppealDataBag",
    ],
    [
      "ptab-interferences",
      () => new PtabInterferencesClient(options).search({ limit: 1 }),
      "patentInterferenceDataBag",
    ],
    [
      "petitions",
      () => new PetitionsClient(options).search({ limit: 1 }),
      "petitionDecisionDataBag",
    ],
    [
      "bulk-products",
      () => new BulkDataClient(options).search({ limit: 1 }),
      "bulkDataProductBag",
    ],
  ] as const) {
    const response = await recorded<{
      count: number;
      provenance: { source_url: string };
      [key: string]: unknown;
    }>(name, run);
    expect(Array.isArray(response[key])).toBe(true);
    expect(response.count).toBeGreaterThanOrEqual(0);
    expect(response.provenance.source_url).toStartWith(
      "https://api.uspto.gov/",
    );
  }
});

test("bulk file recording replays official redirect chain without credentials", async () => {
  const { useCassette } = await import("cassetter");
  await useCassette(
    new URL("./cassettes/odp-bulk-file.yaml", import.meta.url).pathname,
    {
      recordMode: "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri", "json_body"],
      filterQueryParameters: ["Expires", "Signature", "Key-Pair-Id"],
    },
    async () => {
      const response = await new BulkDataClient({
        apiKey: "replay-placeholder",
        retryLimit: 0,
      }).downloadFile("TRTDXFAG", "asb261018.zip");
      expect(response.data.length).toBe(1635);
      expect(Array.from(response.data.slice(0, 4))).toEqual([80, 75, 3, 4]);
    },
  );
});

test("MCP searches default to lean metadata, opt into bounded full rows, and expose requested facets", async () => {
  const { FastMCP } = await import("@prefecthq/fastmcp-ts/server");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const { registerOdpRecordTools } = await import(
    "../packages/mcp/src/odp-records.js"
  );
  const future = {
    futureAttribute: "retained in full",
    longMetadata: "a".repeat(5000),
    documentOCRText: "do not place document text in search results",
  };
  const m = mock({
    count: 1,
    facets: { status: [{ value: "OPEN", count: 1 }] },
    patentTrialDocumentDataBag: [
      {
        trialNumber: "IPR2025-00001",
        ...future,
        documentData: {
          documentIdentifier: "d1",
          documentOCRText: "excluded",
          futureNested: "keep full",
        },
      },
    ],
    petitionDecisionDataBag: [
      {
        petitionDecisionRecordIdentifier: "p1",
        decidedPetitionTypeCodeDescriptionText: "DENIED",
        ...future,
        petitionText: "excluded",
      },
    ],
    bulkDataProductBag: [
      {
        productIdentifier: "PROD",
        productTitleText: "Example",
        ...future,
        productFileBag: { fileDataBag: [{ fileName: "example.zip" }] },
      },
    ],
  });
  const server = new FastMCP({
    name: "records-projections",
    version: "0.1.0",
    logLevel: "error",
  });
  registerOdpRecordTools(server, {
    trials: new PtabTrialsClient(m.options),
    appeals: new PtabAppealsClient(m.options),
    interferences: new PtabInterferencesClient(m.options),
    petitions: new PetitionsClient(m.options),
    bulk: new BulkDataClient(m.options),
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    for (const [name, parameters, identifier] of [
      [
        "search_ptab",
        { dataset: "trials", entity: "decisions" },
        "trialNumber",
      ],
      ["search_petition_decisions", {}, "petitionDecisionRecordIdentifier"],
      ["search_bulk_products", {}, "productIdentifier"],
    ] as const) {
      const lean = await client.callTool<{
        items: Record<string, unknown>[];
        facets?: unknown;
      }>(name, { ...parameters, limit: 1 });
      const row = lean.structuredContent?.items[0];
      expect(row?.[identifier]).toBeString();
      expect(row?.futureAttribute).toBeUndefined();
      expect(row?.documentOCRText).toBeUndefined();
      expect(lean.structuredContent?.facets).toBeUndefined();
      const full = await client.callTool<{
        items: Record<string, unknown>[];
        facets: unknown;
      }>(name, { ...parameters, limit: 1, full: true, facets: ["status"] });
      const fullRow = full.structuredContent?.items[0];
      expect(fullRow?.futureAttribute).toBe("retained in full");
      expect(String(fullRow?.longMetadata).length).toBe(4001);
      expect(fullRow?.documentOCRText).toBeUndefined();
      expect(fullRow?.petitionText).toBeUndefined();
      expect(
        (fullRow?.documentData as Record<string, unknown> | undefined)
          ?.documentOCRText,
      ).toBeUndefined();
      expect(full.structuredContent?.facets).toEqual({
        status: [{ value: "OPEN", count: 1 }],
      });
    }
  } finally {
    await client.close();
  }
});

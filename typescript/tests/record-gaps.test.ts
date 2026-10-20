import { expect, test } from "bun:test";
import { BulkDataClient } from "../packages/client/src/bulkdata.js";
import { PetitionsClient } from "../packages/client/src/petitions.js";
import {
  PtabAppealsClient,
  PtabInterferencesClient,
  PtabTrialsClient,
} from "../packages/client/src/ptab.js";

function mock(data: unknown) {
  const requests: Request[] = [];
  const fetch = (async (input, init) => {
    requests.push(new Request(input, init));
    return Response.json(data);
  }) as typeof globalThis.fetch;
  return {
    requests,
    options: { apiKey: "synthetic-fixture-key", retryLimit: 0, fetch },
  };
}
test("PTAB and petition search/export support every documented GET variant", async () => {
  for (const [Class, method, key] of [
    [PtabTrialsClient, "searchProceedings", "patentTrialProceedingDataBag"],
    [PtabTrialsClient, "searchDecisions", "patentTrialDocumentDataBag"],
    [PtabTrialsClient, "searchDocuments", "patentTrialDocumentDataBag"],
    [PtabAppealsClient, "search", "patentAppealDataBag"],
    [PtabInterferencesClient, "search", "patentInterferenceDataBag"],
    [PetitionsClient, "search", "petitionDecisionDataBag"],
  ] as const) {
    const m = mock({ [key]: [] });
    const client = new Class(m.options);
    const run = client[method as keyof typeof client] as (
      options: object,
    ) => Promise<unknown>;
    await run.call(client, {
      method: "GET",
      query: "status:OPEN",
      fields: ["documentData.documentIdentifier"],
      facets: ["status"],
      filters: [{ name: "status", value: ["OPEN", "CLOSED"] }],
      rangeFilters: [
        {
          field: "decisionDate",
          valueFrom: "2025-01-01",
          valueTo: "2026-01-01",
        },
      ],
      sort: { field: "decisionDate", order: "desc" },
      limit: 2,
      offset: 3,
    });
    const request = m.requests[0];
    expect(request?.method).toBe("GET");
    expect(await request?.text()).toBe("");
    expect(
      Object.fromEntries(
        new URL(request?.url ?? "https://invalid.test").searchParams,
      ),
    ).toEqual({
      q: "status:OPEN",
      fields: "documentData.documentIdentifier",
      facets: "status",
      filters: "status OPEN,CLOSED",
      rangeFilters: "decisionDate 2025-01-01:2026-01-01",
      sort: "decisionDate desc",
      limit: "2",
      offset: "3",
    });
  }
  const trials = new PtabTrialsClient(mock({ patentTrialData: [] }).options);
  for (const method of [
    "downloadProceedings",
    "downloadDecisions",
    "downloadDocuments",
  ] as const)
    expect((await trials[method]({ method: "GET", limit: 1 })).count).toBe(0);
  for (const Class of [
    PtabAppealsClient,
    PtabInterferencesClient,
    PetitionsClient,
  ]) {
    const key =
      Class === PtabInterferencesClient
        ? "interferenceData"
        : Class === PetitionsClient
          ? "petitionDecisionDataBag"
          : "patentTrialData";
    const m = mock({ [key]: [] });
    await new Class(m.options).downloadFile({
      method: "GET",
      fileFormat: "csv",
      limit: 2,
      facets: ["omitted"],
    });
    const params = new URL(m.requests[0]?.url ?? "https://invalid.test")
      .searchParams;
    expect(m.requests[0]?.method).toBe("GET");
    expect(params.get("format")).toBe("csv");
    expect(params.has("facets")).toBe(false);
  }
});
test("GET multiple clauses fail before HTTP while POST preserves them", async () => {
  const m = mock({ count: 0 });
  const client = new PetitionsClient(m.options);
  expect(() =>
    client.search({
      method: "GET",
      filters: [
        { name: "a", value: ["1"] },
        { name: "b", value: ["2"] },
      ],
    }),
  ).toThrow("Use POST");
  expect(m.requests).toHaveLength(0);
  await client.search({
    filters: [
      { name: "a", value: ["1"] },
      { name: "b", value: ["2"] },
    ],
  });
  const body = await m.requests[0]?.text();
  expect(JSON.parse(body ?? "{}").filters).toHaveLength(2);
  expect(body).not.toContain('"method"');
});
test("malformed success data cannot become empty searches or phantom identifier records", async () => {
  for (const payload of [
    {},
    { error: "failure" },
    { count: 4 },
    { patentTrialDocumentDataBag: null },
    { count: "1", patentTrialDocumentDataBag: [] },
  ]) {
    const client = new PtabTrialsClient(mock(payload).options);
    await expect(client.searchDecisions()).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  }
  for (const payload of [{}, { message: "upstream failed" }])
    await expect(
      new PetitionsClient(mock(payload).options).get("record"),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  const projected = await new PtabTrialsClient(
    mock({ patentTrialDocumentDataBag: [{ trialNumber: "IPR2026-1" }] })
      .options,
  ).searchDecisions();
  expect(projected.count).toBe(1);
  expect(
    (await new PtabTrialsClient(mock({ count: 0 }).options).searchDecisions())
      .count,
  ).toBe(0);
});
test("petition JSON download normalizes the current single-record schema and provenance identifies status", async () => {
  const result = await new PetitionsClient(
    mock({
      petitionDecisionRecordIdentifier: "p1",
      decidedPetitionTypeCodeDescriptionText: "DENIED",
    }).options,
  ).download();
  expect(result.count).toBe(1);
  expect(
    result.petitionDecisionDataBag[0]?.petitionDecisionRecordIdentifier,
  ).toBe("p1");
  expect(result.provenance.as_of_status).toBe("DENIED");
  const mixed = await new PtabTrialsClient(
    mock({
      patentTrialDocumentDataBag: [
        { trialNumber: "A", trialMetaData: { trialStatusCategory: "Open" } },
        {
          trialNumber: "B",
          trialMetaData: { trialStatusCategory: "Terminated" },
        },
      ],
    }).options,
  ).searchDecisions();
  expect(mixed.provenance.as_of_status).toBe("Multiple statuses");
  const unknown = await new PtabTrialsClient(
    mock({ count: 0 }).options,
  ).searchDecisions();
  expect(unknown.provenance.as_of_status).toBe("Not provided by source");
});
test("dot path segments, nested bulk filenames and malformed dates fail without HTTP", async () => {
  const m = mock({ count: 0 });
  const api = new BulkDataClient(m.options);
  for (const value of [".", "..", "../bad", "bad/file", "bad\\file"]) {
    expect(() => api.getProduct(value)).toThrow();
    expect(() => api.downloadFile("PRODUCT", value)).toThrow();
  }
  expect(() => new PtabTrialsClient(m.options).getDecision("..")).toThrow();
  expect(() =>
    api.getProduct("PRODUCT", { fileFromDate: "not-a-date" }),
  ).toThrow();
  expect(m.requests).toHaveLength(0);
  await api.getProduct("PRODUCT", { fileFromDate: " 2026-01-01 " });
  expect(
    new URL(m.requests[0]?.url ?? "https://invalid.test").searchParams.get(
      "fileDataFromDate",
    ),
  ).toBe("2026-01-01");
});

test("MCP by-number PTAB results paginate without returning full document text", async () => {
  const { FastMCP } = await import("@prefecthq/fastmcp-ts/server");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const { registerOdpRecordTools } = await import(
    "../packages/mcp/src/odp-records.js"
  );
  const m = mock({
    count: 2,
    patentTrialDocumentDataBag: [
      {
        trialNumber: "IPR2026-1",
        documentData: {
          documentIdentifier: "d1",
          documentOCRText: "secretly huge raw document",
        },
      },
      {
        trialNumber: "IPR2026-1",
        documentData: {
          documentIdentifier: "d2",
          documentOCRText: "second raw document",
        },
      },
    ],
  });
  const server = new FastMCP({
    name: "ptab-bynumber-contract",
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
    const input = {
      dataset: "trials",
      entity: "documents",
      identifier: "IPR2026-1",
      by_number: true,
      limit: 1,
    };
    const first = await client.callTool<{
      items: Record<string, unknown>[];
      next_cursor: string;
    }>("get_ptab", input);
    expect(first.structuredContent?.items).toHaveLength(1);
    expect(first.structuredContent?.next_cursor).toBeString();
    expect(JSON.stringify(first.structuredContent)).not.toContain(
      "raw document",
    );
    const next = await client.callTool<{
      items: { documentData: { documentIdentifier: string } }[];
      more_available: boolean;
    }>("get_ptab", { ...input, cursor: first.structuredContent?.next_cursor });
    expect(
      next.structuredContent?.items[0]?.documentData.documentIdentifier,
    ).toBe("d2");
    expect(next.structuredContent?.more_available).toBe(false);
    const detail = await client.callTool("get_ptab", {
      dataset: "trials",
      entity: "documents",
      identifier: "d1",
      full: true,
    });
    expect(JSON.stringify(detail.structuredContent)).not.toContain(
      "raw document",
    );
    await expect(
      client.callTool("get_ptab", { ...input, entity: "proceedings" }),
    ).rejects.toThrow("Proceedings");
    await expect(
      client.callTool("get_ptab", {
        ...input,
        identifier: "changed",
        cursor: first.structuredContent?.next_cursor,
      }),
    ).rejects.toThrow("different query");
  } finally {
    await client.close();
    await server.close();
  }
});

test("bulk field projection need not include productIdentifier", async () => {
  const result = await new BulkDataClient(
    mock({
      bulkDataProductBag: [{ productTitleText: "Title-only projection" }],
    }).options,
  ).search({ fields: ["productTitleText"] });
  expect(result.count).toBe(1);
  expect(result.bulkDataProductBag[0]?.productTitleText).toBe(
    "Title-only projection",
  );
});

test("PTAB PDF identifiers resolve advertised absolute URLs and reject HTML or foreign origins", async () => {
  const requests: Request[] = [];
  const fetch = (async (input, init) => {
    const request = new Request(input, init);
    requests.push(request);
    return request.url.endsWith("/documents/doc1")
      ? Response.json({
          documentData: {
            documentIdentifier: "doc1",
            fileDownloadURI:
              "https://api.uspto.gov/api/v1/patent/ptab-files/IPR/2025/00001/doc.pdf",
          },
        })
      : new Response("%PDF-1.7 fixture");
  }) as typeof globalThis.fetch;
  const client = new PtabTrialsClient({
    apiKey: "synthetic",
    retryLimit: 0,
    fetch,
  });
  expect(
    new TextDecoder().decode((await client.downloadDocumentPdf("doc1")).data),
  ).toStartWith("%PDF-");
  expect(requests).toHaveLength(2);
  expect(requests[1]?.url).toEndWith("/ptab-files/IPR/2025/00001/doc.pdf");
  await expect(
    client.downloadDocumentPdf("https://attacker.example/document.pdf"),
  ).rejects.toThrow("configured origin");
  expect(requests).toHaveLength(2);
  await expect(
    new PtabTrialsClient(mock("not a PDF").options).downloadDocumentPdf(
      "/api/v1/patent/ptab-files/doc.pdf",
    ),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});

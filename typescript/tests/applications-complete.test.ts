import { describe, expect, test } from "bun:test";
import {
  extractDocumentXml,
  parseClaimsXml,
  parseDocumentXml,
  parseGrantClaimsXml,
} from "../packages/client/src/application-xml.js";
import { ApplicationsClient } from "../packages/client/src/applications.js";

function client(
  handler: (
    url: URL,
    body: Record<string, unknown>,
  ) => unknown | Response | Promise<unknown | Response>,
) {
  return new ApplicationsClient({
    apiKey: "test-key",
    retryLimit: 0,
    fetch: (async (input, init) => {
      const request =
        input instanceof Request ? input : new Request(input, init);
      const body =
        request.method === "POST"
          ? ((await request.json()) as Record<string, unknown>)
          : {};
      const value = await handler(new URL(request.url), body);
      return value instanceof Response ? value : Response.json(value);
    }) as typeof fetch,
  });
}
const record = (
  applicationNumberText: string,
  other: Record<string, unknown> = {},
) => ({ applicationNumberText, ...other });
const bag = (records: Record<string, unknown>[]) => ({
  count: records.length,
  patentFileWrapperDataBag: records,
});
function tar(xml: string) {
  const bytes = new TextEncoder().encode(xml);
  const result = new Uint8Array(
    512 + Math.ceil(bytes.length / 512) * 512 + 1024,
  );
  const header = result.subarray(0, 512);
  header.set(new TextEncoder().encode("document.xml"));
  header.set(
    new TextEncoder().encode(`${bytes.length.toString(8).padStart(11, "0")}\0`),
    124,
  );
  header[156] = 48;
  result.set(bytes, 512);
  return result;
}
describe("complete applications client", () => {
  test("routes all application datasets and preserves source fields", async () => {
    const calls: string[] = [];
    const api = client((url) => {
      calls.push(url.pathname);
      return { patentFileWrapperDataBag: [{ newUpstreamField: 17 }] };
    });
    for (const dataset of [
      "meta-data",
      "adjustment",
      "assignment",
      "attorney",
      "continuity",
      "foreign-priority",
      "transactions",
      "associated-documents",
    ] as const) {
      expect(
        (await api.getData("16/123,456", dataset)).data
          .patentFileWrapperDataBag,
      ).toEqual([{ newUpstreamField: 17 }]);
    }
    expect(calls).toHaveLength(8);
    expect(calls[0]).toBe("/api/v1/patent/applications/16123456/meta-data");
  });
  test("normalizes wrapped assignments and correspondence addresses", async () => {
    const api = client(() =>
      bag([
        {
          assignmentBag: [
            {
              conveyanceText: "ASSIGNMENT",
              correspondenceAddress: { name: "Office" },
              newField: 4,
            },
          ],
        },
      ]),
    );
    expect((await api.getAssignment("16123456")).assignmentBag).toEqual([
      {
        conveyanceText: "ASSIGNMENT",
        correspondenceAddress: [{ name: "Office" }],
        newField: 4,
      },
    ]);
  });
  test("submits status search and raw source search export payload", async () => {
    const calls: unknown[] = [];
    const api = client((url, body) => {
      calls.push([url.pathname, body]);
      return url.pathname.endsWith("download")
        ? new Response("a,b\n1,2", { headers: { "content-type": "text/csv" } })
        : { statusCodeDataBag: [{ code: 150 }] };
    });
    expect(
      (await api.getStatusCodes({ q: "150" })).data.statusCodeDataBag,
    ).toEqual([{ code: 150 }]);
    expect(
      new TextDecoder().decode(
        (await api.downloadSearch({ q: "test", format: "csv" })).data,
      ),
    ).toBe("a,b\n1,2");
    expect(calls).toEqual([
      ["/api/v1/patent/status-codes", { q: "150" }],
      [
        "/api/v1/patent/applications/search/download",
        { q: "test", format: "csv" },
      ],
    ]);
  });
  test("filters document codes and official dates", async () => {
    const api = client((url) => {
      expect(url.searchParams.get("documentCodes")).toBe("CLM,SPEC");
      expect(url.searchParams.get("officialDateFrom")).toBe("2020-01-01");
      expect(url.searchParams.get("officialDateTo")).toBe("2021-01-01");
      return { documentBag: [] };
    });
    await api.getDocuments("16123456", {
      includeAssociated: false,
      documentCodes: ["CLM", "SPEC"],
      officialDateFrom: "2020-01-01",
      officialDateTo: "2021-01-01",
    });
  });
  test("downloads advertised PDF, DOCX, and extracts advertised XML tar", async () => {
    const api = client((url) =>
      url.pathname.endsWith("/documents")
        ? {
            documentBag: [
              {
                documentIdentifier: "ABC",
                downloadOptionBag: [
                  { mimeTypeIdentifier: "PDF", downloadUrl: "/custom.pdf" },
                  {
                    mimeTypeIdentifier: "MS_WORD",
                    downloadUrl: "/custom.docx",
                  },
                  { mimeTypeIdentifier: "XML", downloadUrl: "/custom.tar" },
                ],
              },
            ],
          }
        : url.pathname.endsWith(".tar")
          ? new Response(tar("<ClaimsDocument/>"))
          : new Response(url.pathname),
    );
    expect(
      new TextDecoder().decode(
        (await api.downloadDocument("16123456", "ABC")).data,
      ),
    ).toBe("/custom.pdf");
    expect(
      new TextDecoder().decode(
        (await api.downloadDocumentDocx("16123456", "ABC")).data,
      ),
    ).toBe("/custom.docx");
    expect((await api.downloadDocumentXml("16123456", "ABC")).data).toBe(
      "<ClaimsDocument/>",
    );
  });
  test("rejects unavailable formats, hostile download origins and path identifiers", async () => {
    const api = client(() => ({
      documentBag: [
        {
          documentIdentifier: "ABC",
          downloadOptionBag: [
            {
              mimeTypeIdentifier: "MS_WORD",
              downloadUrl: "https://evil.example/steal",
            },
          ],
        },
      ],
    }));
    await expect(api.downloadDocumentXml("16123456", "ABC")).rejects.toThrow(
      "no XML",
    );
    await expect(api.downloadDocumentDocx("16123456", "ABC")).rejects.toThrow();
    await expect(api.downloadDocument("16123456", "../ABC")).rejects.toThrow();
  });
  test("batch downloads retain document records and filter codes", async () => {
    const docs = [
      { documentIdentifier: "AAA", documentCode: "CLM" },
      { documentIdentifier: "BBB", documentCode: "SPEC" },
    ];
    const api = client((url) =>
      url.pathname.endsWith("documents")
        ? { documentBag: docs }
        : new Response("PDF"),
    );
    const results = await api.downloadDocuments("16123456", {
      documentCodes: ["CLM"],
    });
    expect(results).toHaveLength(1);
    expect(results[0]?.document).toEqual(docs[0]);
  });
  test("resolves patent kind codes and avoids application/patent ambiguity", async () => {
    const queries: unknown[] = [];
    const api = client((url, body) => {
      if (url.pathname.endsWith("search")) queries.push(body.q);
      return bag([record("16123456")]);
    });
    expect(
      (await api.resolveIdentifier("US 11,123,456 B2")).applicationNumber,
    ).toBe("16123456");
    await api.resolveIdentifier("US20200123456A1", "publication");
    await api.resolveIdentifier("16/123,456", "application");
    expect(queries).toEqual([
      'applicationMetaData.patentNumber:"11123456"',
      'applicationMetaData.publicationNumber:"20200123456"',
    ]);
  });
  test("traverses cycles, deduplicates links and records inaccessible relatives", async () => {
    const root = record("16123456", {
      applicationMetaData: { inventionTitle: "Family" },
      parentContinuityBag: [
        {
          parentApplicationNumberText: "15123456",
          claimParentageTypeCode: "CON",
        },
      ],
      childContinuityBag: [
        {
          childApplicationNumberText: "17123456",
          claimParentageTypeCode: "CON",
        },
      ],
    });
    const parent = record("15123456", {
      childContinuityBag: [
        {
          childApplicationNumberText: "16123456",
          claimParentageTypeCode: "CON",
        },
      ],
    });
    const api = client((url, body) => {
      if (url.pathname.endsWith("search")) {
        const query = String(body.q);
        return bag(
          [root, parent].filter((item) =>
            query.includes(item.applicationNumberText),
          ),
        );
      }
      if (url.pathname.endsWith("17123456"))
        return new Response("", { status: 404 });
      return bag([root]);
    });
    const family = await api.getFamily("16123456", {
      identifierType: "application",
      batchSize: 1,
    });
    expect(family.metadata).toEqual({
      nodeCount: 3,
      edgeCount: 2,
      missingCount: 1,
    });
    expect(family.missingApplications).toEqual(["17123456"]);
    expect(family.nodes[0]?.dataSource).toBe("uspto_odp");
    await expect(
      api.getFamily("16123456", {
        identifierType: "application",
        batchSize: 0,
      }),
    ).rejects.toThrow();
    await expect(
      api.getFamily("16123456", {
        identifierType: "application",
        maxApplications: 1,
      }),
    ).rejects.toThrow("exceeds");
  });
  test("retrieves granted claims or returns explicit no-XML result", async () => {
    const api = client((url) =>
      url.pathname.endsWith("search")
        ? bag([record("16123456")])
        : url.pathname.endsWith("associated-documents")
          ? bag([{ grantDocumentMetaData: { fileLocationURI: "/grant.xml" } }])
          : url.pathname.endsWith("documents")
            ? { documentBag: [] }
            : new Response(
                '<us-patent-grant><claims><claim num="1"><claim-text>A device.</claim-text></claim></claims></us-patent-grant>',
              ),
    );
    expect(
      (await api.getGrantedClaims("11123456")).claims?.[0]?.claim_text,
    ).toBe("A device.");
    const empty = client((url) =>
      url.pathname.endsWith("documents") &&
      !url.pathname.endsWith("associated-documents")
        ? { documentBag: [] }
        : url.pathname.endsWith("search")
          ? bag([record("16123456")])
          : bag([]),
    );
    expect((await empty.getGrantedClaims("11123456")).claims).toBeNull();
  });
});
describe("USPTO XML parsing", () => {
  test("preserves nested grant claims, references, inline punctuation and XML entities", () => {
    const xml =
      '<us-patent-grant><claims><claim num="00001"><claim-text>A device comprising:<claim-text>a &amp; b;</claim-text><claim-text>a sensor.</claim-text></claim-text></claim><claim id="CLM-00002"><claim-text>The device of <claim-ref idref="CLM-00001">claim 1</claim-ref>.</claim-text></claim></claims></us-patent-grant>';
    expect(parseGrantClaimsXml(xml)).toEqual([
      {
        claim_number: 1,
        claim_text: "A device comprising:\n    a & b;\n    a sensor.",
        claim_type: "independent",
        depends_on: null,
      },
      {
        claim_number: 2,
        claim_text: "The device of claim 1.",
        claim_type: "dependent",
        depends_on: 1,
      },
    ]);
  });
  test("parses namespaced ST.96 claims and specification headings", () => {
    const parsed = parseClaimsXml(
      '<pat:ClaimsDocument xmlns:pat="urn:test"><pat:DocumentMetadata><pat:ApplicationNumberText>16123456</pat:ApplicationNumberText></pat:DocumentMetadata><pat:Claim><pat:ClaimNumber>2</pat:ClaimNumber><pat:ClaimText>A <pat:ClaimReference idrefs="CLM-00001">claim 1</pat:ClaimReference> device.</pat:ClaimText></pat:Claim></pat:ClaimsDocument>',
    );
    expect(parsed.applicationNumber).toBe("16123456");
    expect(parsed.claims[0]?.depends_on).toBe(1);
    expect(
      parseDocumentXml(
        "<SpecificationDocument><Heading>FIELD</Heading><P>A device.</P><P>A device.</P><Image><FileName>Fig1.tif</FileName></Image></SpecificationDocument>",
      ).description,
    ).toBe("## FIELD\n\nA device.\n\n\n[Figure: Fig1.tif]");
  });
  test("rejects malformed XML and unsafe entity declarations; checks truncated tar", () => {
    expect(() => parseGrantClaimsXml("<bad>")).toThrow();
    expect(() =>
      parseGrantClaimsXml('<!DOCTYPE a [<!ENTITY x "evil">]><a/>'),
    ).toThrow();
    expect(() => extractDocumentXml(tar("<a/>").subarray(0, 513))).toThrow(
      "Truncated",
    );
    expect(() => extractDocumentXml(new Uint8Array(512))).toThrow("No XML");
  });
});

test("application raw payload overrides generated search fields", async () => {
  const api = client((_url, body) => {
    expect(body).toEqual({
      q: "source query",
      newSourceFeature: { enabled: true },
    });
    return bag([]);
  });
  await api.search({
    query: "ignored",
    rawPayload: {
      q: "source query",
      newSourceFeature: { enabled: true },
      empty: [],
    },
  });
});

test("application extra MCP tools call library and return document artifacts without inline bytes", async () => {
  const { FastMCP } = await import("@prefecthq/fastmcp-ts/server");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const { registerApplicationExtraTools } = await import(
    "../packages/mcp/src/applications-extra.js"
  );
  const api = client((url) =>
    url.pathname.endsWith("documents")
      ? { documentBag: [{ documentIdentifier: "ABC" }] }
      : url.pathname.endsWith(".pdf")
        ? new Response("%PDF-test")
        : url.pathname.endsWith("search")
          ? bag([record("16123456")])
          : { patentFileWrapperDataBag: [{ newSourceField: 8 }] },
  );
  const server = new FastMCP({
    name: "applications-extra-test",
    version: "1.0.0",
    logLevel: "silent",
  });
  registerApplicationExtraTools(server, api);
  const rpc = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    expect((await rpc.listTools()).map((tool) => tool.name).sort()).toEqual([
      "download_application_document",
      "download_application_search",
      "get_application_data",
      "get_application_family",
      "get_granted_claims",
      "resolve_application",
    ]);
    const resolved = await rpc.callTool<{
      details: { application_number: string };
    }>("resolve_application", { identifier: "11123456" });
    expect(resolved.structuredContent?.details).toEqual({
      application_number: "16123456",
    });
    const download = await rpc.callTool<{
      file_path?: string;
      download_url?: string;
      size: number;
      content_type: string;
    }>("download_application_document", {
      application_number: "16123456",
      document_identifier: "ABC",
    });
    expect(download.structuredContent?.size).toBe(9);
    expect(download.structuredContent?.content_type).toBe("application/pdf");
    expect(
      download.structuredContent?.file_path ??
        download.structuredContent?.download_url,
    ).toBeTruthy();
    expect(JSON.stringify(download)).not.toContain("%PDF-test");
  } finally {
    await rpc.close();
    await server.close();
  }
});

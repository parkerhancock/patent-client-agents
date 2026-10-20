import { describe, expect, test } from "bun:test";
import {
  normalizePublicationNumber,
  PublicationsClient,
  parseClaims,
  validatePublicationQuery,
} from "../packages/client/src/publications.js";
import { convertDocument } from "../packages/client/src/publications-models.js";
import {
  TrademarkSearchClient,
  WAF_USER_AGENT,
} from "../packages/client/src/trademark-search.js";
import liveDocument from "./fixtures/ppubs-7654321.json" with { type: "json" };

const json = (body: unknown, status = 200, headers: HeadersInit = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
function fakePpubs() {
  let session = 0;
  let expire = 0;
  const requests: Request[] = [];
  const handler = async (input: RequestInfo | URL, init?: RequestInit) => {
    const r = new Request(input, init);
    requests.push(r);
    const path = new URL(r.url).pathname;
    const body = r.method === "POST" ? await r.clone().json() : null;
    if (path === "/pubwebapp/")
      return new Response("<html>", {
        headers: { "Set-Cookie": "SESSION=browser; Path=/; Secure" },
      });
    if (path === "/api/users/me/session") {
      expect(body).toBe(-1);
      session++;
      return json({ userCase: { caseId: session } }, 200, {
        "X-Access-Token": `token-${session}`,
      });
    }
    if (expire) {
      expire--;
      return json({}, 403);
    }
    expect(r.headers.get("X-Access-Token")).toBe(`token-${session}`);
    expect(r.headers.get("cookie")).toContain("SESSION=browser");
    if (body && !Array.isArray(body))
      expect(body.query?.caseId ?? body.caseId ?? session).toBe(session);
    if (path.endsWith("/counts")) return json({ numResults: 4 });
    if (path.endsWith("searchWithBeFamily"))
      return json({
        numFound: 2,
        perPage: 20,
        page: 0,
        numberOfFamilies: 2,
        patents: [
          {
            guid: "US-X",
            publicationReferenceDocumentNumber: "20230123456",
            type: "US-PGPUB",
            inventionTitle: "Neural widget",
          },
        ],
      });
    if (path.includes("/highlight/"))
      return json({
        guid: "US-X",
        pubRefDocNumber: "20230123456",
        type: "US-PGPUB",
        pageCount: 2,
        imageLocation: "pgpub/x",
        claimsHtml: "1. A widget.\n2. The widget of claim 1.",
        inventorsName: ["Inventor"],
        inventorCountry: ["US"],
        applicationNumber: "D12/345",
        usRefIssueDate: ["202301"],
        urpn: ["123"],
        usRefGroup: ["examiner"],
      });
    if (path.endsWith("/imageviewer")) {
      expect(body.pageKeys).toEqual([
        "pgpub/x/00000001.tif",
        "pgpub/x/00000002.tif",
      ]);
      return new Response('"job-1"');
    }
    if (path.endsWith("/print-process"))
      return json([{ printStatus: "COMPLETED", pdfName: "doc.pdf" }]);
    if (path.endsWith("/doc.pdf"))
      return new Response("%PDF-1.4 fake ppubs pdf");
    return json({}, 404);
  };
  return {
    fetch: handler as typeof fetch,
    requests,
    expire: (count = 1) => {
      expire = count;
    },
    sessions: () => session,
  };
}
describe("PPUBS Python fake contract", () => {
  test("normalizes US grant, design, reissue and docdb publications", () => {
    expect(normalizePublicationNumber("US2016309324A1")).toBe("20160309324");
    expect(normalizePublicationNumber("USD1142829S")).toBe("D1142829");
    expect(normalizePublicationNumber("USRE46070E")).toBe("RE46070");
  });
  test("validates syntax and parses dependency ranges", () => {
    expect(() => validatePublicationQuery('"widget$"')).toThrow();
    expect(() => validatePublicationQuery("widget AND OR gear")).toThrow();
    const claims = parseClaims(
      ".Iadd.1-3. A method.\n4. The method of claim 2.",
    );
    expect(claims.map((c) => c.number)).toEqual([1, 2, 3, 4]);
    expect(claims[1]?.dependent_claims).toEqual([4]);
  });
  test("bootstraps once concurrently, refreshes expired session, resolves and prints PDF", async () => {
    const fake = fakePpubs();
    const client = new PublicationsClient({
      fetch: fake.fetch,
      retryLimit: 0,
      pollIntervalMs: 0,
    });
    await Promise.all([
      client.searchBiblio({ query: "widget" }),
      client.searchBiblio({ query: "gear" }),
    ]);
    expect(fake.sessions()).toBe(1);
    fake.expire(2);
    const [page] = await Promise.all([
      client.searchBiblio({ query: "widget", limit: 100 }),
      client.searchBiblio({ query: "gear" }),
    ]);
    expect(fake.sessions()).toBe(2);
    expect(page.num_documents).toBe(4);
    expect(page.num_found).toBe(2);
    const doc =
      await client.resolveDocumentByPublicationNumber("US20230123456A1");
    expect(doc.appl_id).toBe("2912345");
    expect(doc.inventors).toEqual([
      {
        name: "Inventor",
        city: null,
        country: "US",
        postal_code: null,
        state: null,
      },
    ]);
    expect((doc.us_references as Record<string, unknown>[])[0]?.pub_month).toBe(
      "2023-01-01",
    );
    const pdf = await client.downloadPdf(doc);
    expect(new TextDecoder().decode(pdf.data)).toStartWith("%PDF");
  });
  test("rejects a landing-page redirect to a foreign host without sending session secrets", async () => {
    let count = 0;
    const fetcher = (async (input: RequestInfo | URL) => {
      count++;
      const r = new Request(input);
      expect(new URL(r.url).origin).toBe("https://ppubs.uspto.gov");
      return new Response(null, {
        status: 302,
        headers: {
          location: "https://attacker.invalid/steal",
          "Set-Cookie": "session=secret",
        },
      });
    }) as unknown as typeof fetch;
    const client = new PublicationsClient({ fetch: fetcher, retryLimit: 0 });
    await expect(client.searchBiblio({ query: "widget" })).rejects.toThrow();
    expect(count).toBe(1);
  });
});
describe("Trademark Search Python response contract", () => {
  test("sends bound token+UA; ORs text and constrains status; maps actual source/id/totalValue", async () => {
    const client = new TrademarkSearchClient({
      token: { token: "opaque", expires: Date.now() / 1000 + 86400 },
      fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
        const r = new Request(input, init);
        expect(r.headers.get("cookie")).toBe("aws-waf-token=opaque");
        expect(r.headers.get("User-Agent")).toBe(WAF_USER_AGENT);
        const b = await r.json();
        expect(b.query.bool.must).toEqual([
          {
            bool: {
              should: [
                { match: { wordmark: "widget" } },
                { match: { ownerName: "Acme" } },
              ],
              minimum_should_match: 1,
            },
          },
          { term: { alive: false } },
        ]);
        return json({
          hits: {
            totalValue: 7,
            hits: [
              {
                id: "12345678",
                source: {
                  alive: false,
                  wordmark: "WIDGET",
                  ownerName: "Acme, Inc",
                  registrationNumber: "9876",
                  cancelDate: "bad",
                },
              },
            ],
          },
          took: 9,
        });
      }) as unknown as typeof fetch,
    });
    const r = await client.search({
      wordmark: "widget",
      owner: "Acme",
      status: "dead",
    });
    expect(r.total).toBe(7);
    expect(r.results[0]?.serial_number).toBe("12345678");
    expect(r.results[0]?.primary_owner).toBe("Acme");
    expect(r.query_time_ms).toBe(9);
  });
  test("refreshes a WAF challenge exactly once using supplied refresh callback", async () => {
    let calls = 0;
    const client = new TrademarkSearchClient({
      token: { token: "old", expires: Date.now() / 1000 + 86400 },
      refreshToken: async () => ({
        token: "new",
        expires: Date.now() / 1000 + 86400,
        userAgent: "bound-UA",
      }),
      fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
        calls++;
        if (calls === 1) return new Response("challenge", { status: 202 });
        const r = new Request(input, init);
        expect(r.headers.get("cookie")).toBe("aws-waf-token=new");
        expect(r.headers.get("User-Agent")).toBe("bound-UA");
        return json({ hits: { totalValue: 0, hits: [] } });
      }) as unknown as typeof fetch,
    });
    expect((await client.searchWordmark("widget")).total).toBe(0);
    expect(calls).toBe(2);
  });
  test("searchAll pages and honors maxResults without an extra request", async () => {
    let calls = 0;
    const client = new TrademarkSearchClient({
      token: { token: "opaque", expires: Date.now() / 1000 + 86400 },
      fetch: (async () => {
        calls++;
        return json({
          hits: {
            totalValue: 5,
            hits: [
              { id: `${calls}a`, source: { alive: true } },
              { id: `${calls}b`, source: { alive: true } },
            ],
          },
        });
      }) as unknown as typeof fetch,
    });
    expect(
      (await client.searchAll({ owner: "Acme", batchSize: 2, maxResults: 3 }))
        .length,
    ).toBe(3);
    expect(calls).toBe(2);
  });
});

test("transforms archived live PPUBS document with all 26 HTML-separated claims", () => {
  const d = convertDocument(liveDocument);
  expect(d.publication_number).toBe("7654321");
  expect(d.appl_id).toBe("11616583");
  expect(d.document_structure?.page_count).toBe(18);
  const document = d.document as {
    claims: { number: number; depends_on: number[] }[];
  };
  expect(document.claims.length).toBe(26);
  expect(document.claims[25]?.number).toBe(26);
  expect(document.claims[25]?.depends_on).toEqual([25]);
});

test("portal MCP cursors are query-bound and patent offsets count families", async () => {
  const { createServer } = await import("../packages/mcp/src/index.js");
  const { Client } = await import("@prefecthq/fastmcp-ts/client");
  const starts: number[] = [];
  const provenance = {
    source_url: "https://ppubs.uspto.gov/api/searches/searchWithBeFamily",
    source_name: "USPTO Patent Public Search",
    retrieved_at: "2026-10-20T12:00:00.000Z",
    cache_hit: false as const,
  };
  const publications = {
    async searchBiblio(options: { start: number }) {
      starts.push(options.start);
      return {
        docs: [
          {
            guid: "one",
            publication_number: "1",
            applicant_names: ["verbose"],
          },
          { guid: "two", publication_number: "2" },
        ],
        num_found: 2,
        num_documents: 4,
        per_page: 1,
        page: options.start,
        num_families: 2,
        provenance,
      };
    },
  } as unknown as PublicationsClient;
  const server = createServer({ clients: { publications } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const first = await client.callTool<{
      next_cursor: string;
      items: Record<string, unknown>[];
    }>("search_patents", { query: "widget", limit: 1 });
    expect(first.structuredContent?.next_cursor).toBeString();
    expect(first.structuredContent?.items[0]?.applicant_names).toBeUndefined();
    await client.callTool("search_patents", {
      query: "widget",
      limit: 1,
      cursor: first.structuredContent?.next_cursor,
    });
    expect(starts).toEqual([0, 1]);
    await expect(
      client.callTool("search_patents", {
        query: "different",
        limit: 1,
        cursor: first.structuredContent?.next_cursor,
      }),
    ).rejects.toThrow("different query");
    const full = await client.callTool<{ items: Record<string, unknown>[] }>(
      "search_patents",
      { query: "widget", limit: 1, full: true },
    );
    expect(full.structuredContent?.items[0]?.applicant_names).toEqual([
      "verbose",
    ]);
  } finally {
    await client.close();
    await server.close();
  }
});

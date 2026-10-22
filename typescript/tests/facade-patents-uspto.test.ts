import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import {
  ApplicationsClient,
  AssignmentCenterClient,
  EpoOpsClient,
  OfficeActionAnalyticsClient,
  PetitionsClient,
  PublicationsClient,
} from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { UNPORTED_FACADE_TOOLS } from "../packages/mcp/src/facade/index.js";
import { createServer } from "../packages/mcp/src/index.js";
import contract from "./fixtures/facade/python-facade-tools.json" with {
  type: "json",
};

const TOOLS = [
  "search_patents",
  "get_patent",
  "resolve_patent_number",
  "patent_client_status",
  "search_uspto",
  "get_uspto",
  "get_file_history",
  "search_office_actions",
  "search_patent_assignments",
];

type Envelope = {
  summary: string;
  items?: Record<string, unknown>[];
  details?: Record<string, unknown>;
  not_found?: string[];
  more_available?: boolean;
  download_url?: string;
  file_path?: string;
};
interface Seen {
  method: string;
  host: string;
  path: string;
  query: Record<string, string>;
  body: unknown;
}
const json = (body: unknown, status = 200, headers: HeadersInit = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
const bag = (records: Record<string, unknown>[], count = records.length) => ({
  count,
  patentFileWrapperDataBag: records,
});
const application = {
  applicationNumberText: "16123456",
  applicationMetaData: {
    inventionTitle: "Widget",
    filingDate: "2018-01-01",
    patentNumber: "10123456",
    grantDate: "2020-01-01",
    applicationStatusDescriptionText: "Patented Case",
  },
};
const grantXml =
  '<us-patent-grant><claims><claim num="00001"><claim-text>1. A widget comprising:<claim-text>a gear.</claim-text></claim-text></claim><claim id="CLM-00002" num="00002"><claim-text>2. The widget of <claim-ref idref="CLM-00001">claim 1</claim-ref>.</claim-text></claim></claims></us-patent-grant>';
const wpd = (body: string) =>
  `<ops:world-patent-data xmlns="http://www.epo.org/exchange" xmlns:ops="http://ops.epo.org" xmlns:ftxt="http://www.epo.org/fulltext">${body}</ops:world-patent-data>`;

/** One synthetic upstream for PPUBS, ODP, analytics, Assignment Center and EPO OPS. */
function fakeUpstreams() {
  const seen: Seen[] = [];
  let ppubsSession = 0;
  /** US numbers whose grant XML and PPUBS full text are missing. */
  const noGrant = new Set(["10000001"]);
  const handler = async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const url = new URL(request.url);
    const text = request.method === "POST" ? await request.clone().text() : "";
    let body: unknown = text;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = Object.fromEntries(new URLSearchParams(text));
    }
    seen.push({
      method: request.method,
      host: url.hostname,
      path: url.pathname,
      query: Object.fromEntries(url.searchParams),
      body,
    });
    const path = url.pathname;
    if (url.hostname === "ppubs.uspto.gov") {
      if (path === "/pubwebapp/")
        return new Response("<html>", {
          headers: { "Set-Cookie": "SESSION=browser; Path=/; Secure" },
        });
      if (path === "/api/users/me/session") {
        ppubsSession++;
        return json({ userCase: { caseId: ppubsSession } }, 200, {
          "X-Access-Token": `token-${ppubsSession}`,
        });
      }
      if (path.endsWith("/counts")) return json({ numResults: 5 });
      if (path.endsWith("searchWithBeFamily")) {
        const query = (body as { query: { q: string } }).query.q;
        if (query.includes("10000001"))
          return json({ numFound: 0, numberOfFamilies: 0, patents: [] });
        return json({
          numFound: 2,
          perPage: 20,
          page: 0,
          numberOfFamilies: 4,
          patents: [
            {
              guid: "US-20230123456-A1",
              publicationReferenceDocumentNumber: "20230123456",
              type: "US-PGPUB",
              inventionTitle: "Neural widget",
              applicantName: ["Acme Corp"],
              assigneeName: ["Acme Holdings"],
              datePublished: "2023-04-20",
            },
          ],
        });
      }
      if (path.includes("/highlight/"))
        return json({
          guid: "US-20230123456-A1",
          pubRefDocNumber: "20230123456",
          type: "US-PGPUB",
          inventionTitle: "Neural widget",
          datePublished: "2023-04-20",
          applicantName: ["Acme Corp"],
          claimsHtml:
            "1. A widget.<br/><br/>2. The widget of claim 1, wherein it spins.",
        });
    }
    if (url.hostname === "api.uspto.gov") {
      if (path === "/api/v1/patent/applications/search") {
        const q = String((body as { q?: string }).q ?? "");
        if (q.includes("patentNumber")) {
          const number = /"(\d+)"/.exec(q)?.[1] ?? "";
          return json(
            noGrant.has(number)
              ? bag([])
              : bag([{ applicationNumberText: "16123456" }]),
          );
        }
        if (q.startsWith("applicationNumberText:("))
          return json(bag([application]));
        return json(
          bag([application, { applicationNumberText: "17000000" }], 7),
        );
      }
      if (path === "/api/v1/patent/applications/16123456")
        return json(bag([application]));
      if (path === "/api/v1/patent/applications/99999999")
        return json({ error: "Not Found" }, 404);
      if (path === "/api/v1/patent/applications/16123456/documents")
        return json({
          documentBag: [
            {
              documentIdentifier: "DOC1",
              documentCode: "CTNF",
              documentCodeDescriptionText: "Non-Final Rejection",
              officialDate: "2019-05-01T00:00:00",
              directionCategory: "OUTGOING",
              pageCount: 7,
              downloadOptionBag: [{ mimeTypeIdentifier: "PDF" }],
            },
            {
              documentIdentifier: "DOC2",
              documentCode: "NOA",
              documentCodeDescriptionText: "Notice of Allowance",
              officialDate: "2019-11-01T00:00:00",
              downloadOptionBag: [
                { mimeTypeIdentifier: "PDF" },
                { mimeTypeIdentifier: "MS_WORD" },
              ],
            },
          ],
        });
      if (path === "/api/v1/patent/applications/16123456/associated-documents")
        return json(
          bag([{ grantDocumentMetaData: { fileLocationURI: "/grant.xml" } }]),
        );
      if (path === "/grant.xml") return new Response(grantXml);
      if (path === "/api/v1/patent/applications/16123456/assignment")
        return json(
          bag([
            {
              applicationNumberText: "16123456",
              assignmentBag: [
                {
                  reelAndFrameNumber: "500/1",
                  conveyanceText: "ASSIGNMENT",
                  assigneeBag: [{ assigneeNameText: "ACME" }],
                },
              ],
            },
          ]),
        );
      if (path.startsWith("/api/v1/download/applications/16123456/"))
        return new Response("%PDF-1.4 file history");
      if (path === "/api/v1/petition/decisions/search")
        return json({
          count: 3,
          petitionDecisionDataBag: [
            {
              petitionDecisionRecordIdentifier: "p-1",
              applicationNumberText: "16123456",
              decisionTypeCode: "GRANTED",
              decisionDate: "2020-02-02",
              decisionPetitionTypeCodeDescriptionText: "Revival",
              finalDecidingOfficeName: "OPET",
            },
          ],
        });
      if (path === "/api/v1/petition/decisions/p-1")
        return json({
          count: 1,
          petitionDecisionDataBag: [
            {
              petitionDecisionRecordIdentifier: "p-1",
              applicationNumberText: "16123456",
              decisionTypeCode: "GRANTED",
              decisionDate: "2020-02-02",
              decisionPetitionTypeCodeDescriptionText: "Revival",
            },
          ],
        });
      if (path.startsWith("/api/v1/petition/decisions/"))
        return json({ error: "Not Found" }, 404);
      if (path.startsWith("/api/v1/patent/oa/")) {
        const criteria = (body as { criteria: string }).criteria;
        if (criteria === "id:missing")
          return json({ response: { start: 0, numFound: 0, docs: [] } });
        return json({
          response: {
            start: Number((body as { start: string }).start),
            numFound: 30,
            docs: [
              {
                id: "oa-1",
                patentApplicationNumber: "16123456",
                submissionDate: "2019-05-01T00:00:00",
                legacyDocumentCodeIdentifier: "CTNF",
                groupArtUnitNumber: "1713",
                hasRej101: 0,
                hasRej103: 1,
                legalSectionCode: "103",
                nationalClass: "438",
                referenceIdentifier: "Smith US 20030201666 A1",
                parsedReferenceIdentifier: "20030201666",
                examinerCitedReferenceIndicator: true,
                techCenter: "1700",
                inventionTitle: "Widget",
                bodyText: "full text",
              },
            ],
          },
        });
      }
    }
    if (url.hostname === "assignmentcenter.uspto.gov")
      return json({
        successResponse: {
          totalRows: 12,
          data: [
            {
              reelNumber: 35130,
              frameNumber: 327,
              conveyance: "ASSIGNMENT OF ASSIGNOR'S INTEREST",
              assignorExecutionDate: "03/06/2015",
              assignors: [{ assignorName: "MARRON, JOSEPH" }],
              assignees: ["RAYTHEON COMPANY"],
              noOfProperties: 1,
              properties: [
                { applicationNumber: "14123456", patentNumber: "9000000" },
              ],
            },
          ],
        },
      });
    if (url.hostname === "ops.epo.org") {
      if (path.endsWith("/accesstoken"))
        return json({ access_token: "t", expires_in: 1200 });
      if (path.endsWith("/published-data/search"))
        return new Response(
          wpd(
            `<ops:biblio-search total-result-count="40"><ops:query>q</ops:query><ops:search-result><ops:publication-reference family-id="7"><document-id document-id-type="docdb"><country>EP</country><doc-number>1000000</doc-number><kind>A1</kind></document-id></ops:publication-reference></ops:search-result></ops:biblio-search>`,
          ),
        );
      if (path.includes("/EP9999999A1/"))
        return new Response(
          `<fault xmlns="http://ops.epo.org"><code>SERVER.EntityNotFound</code><message>No</message></fault>`,
          { status: 404 },
        );
      if (path.endsWith("/biblio"))
        return new Response(
          wpd(
            `<exchange-documents><exchange-document family-id="7"><bibliographic-data><publication-reference><document-id document-id-type="docdb"><country>EP</country><doc-number>1000000</doc-number><kind>A1</kind></document-id></publication-reference><invention-title lang="en">Bricks</invention-title><parties><applicants><applicant><applicant-name><name>BOER</name></applicant-name></applicant></applicants></parties></bibliographic-data></exchange-document></exchange-documents>`,
          ),
        );
      if (path.endsWith("/claims"))
        return new Response(
          wpd(
            `<ftxt:fulltext-documents><ftxt:fulltext-document><claims lang="DE"><claim><claim-text>1. Vorrichtung.</claim-text></claim></claims><claims lang="EN"><claim><claim-text>1. An apparatus.</claim-text><claim-text>2. The apparatus of claim 1.</claim-text></claim></claims></ftxt:fulltext-document></ftxt:fulltext-documents>`,
          ),
        );
      if (path.includes("/number-service/"))
        return new Response(
          wpd(
            `<ops:standardization><ops:input><document-id document-id-type="original"><doc-number>EP1000000A1</doc-number></document-id></ops:input><ops:output><document-id document-id-type="docdb"><country>EP</country><doc-number>1000000</doc-number><kind>A1</kind></document-id></ops:output></ops:standardization><ops:meta name="status" value="SUCCESS"/>`,
          ),
        );
    }
    return json({ error: `unexpected ${url.hostname}${path}` }, 500);
  };
  return { fetch: handler as typeof fetch, seen, noGrant };
}

const EPO_VARS = [
  "EPO_OPS_API_KEY",
  "EPO_OPS_API_SECRET",
  "EPO_API_KEY",
  "EPO_API_SECRET",
] as const;
async function connect(fake: ReturnType<typeof fakeUpstreams>, epo = true) {
  const options = { fetch: fake.fetch, retryLimit: 0 };
  const saved = EPO_VARS.map((name) => [name, process.env[name]] as const);
  for (const name of EPO_VARS) delete process.env[name];
  try {
    const server = createServer({
      toolset: "curated",
      clients: {
        applications: new ApplicationsClient({ ...options, apiKey: "k" }),
        petitions: new PetitionsClient({ ...options, apiKey: "k" }),
        analytics: new OfficeActionAnalyticsClient({ ...options, apiKey: "k" }),
        publications: new PublicationsClient(options),
        assignments: new AssignmentCenterClient(options),
        ...(epo
          ? {
              epoOps: new EpoOpsClient({
                ...options,
                apiKey: "k",
                apiSecret: "s",
              }),
            }
          : {}),
      },
    });
    const client = await Client.connect(server, {
      versionNegotiation: { mode: "legacy" },
    });
    return {
      client,
      call: async (name: string, args: Record<string, unknown>) =>
        (await client.callTool<Envelope>(name, args))
          .structuredContent as Envelope,
      async close() {
        await client.close();
        await server.close();
      },
    };
  } finally {
    for (const [name, value] of saved)
      if (value !== undefined) process.env[name] = value;
  }
}

let fake: ReturnType<typeof fakeUpstreams>;
let mcp: Awaited<ReturnType<typeof connect>>;
beforeAll(async () => {
  fake = fakeUpstreams();
  mcp = await connect(fake);
});
afterAll(async () => {
  await mcp.close();
});
const last = (host: string) => fake.seen.filter((s) => s.host === host).at(-1);

describe("facade contract", () => {
  test("the nine tools match the Python names and parameters", async () => {
    const tools = await mcp.client.listTools();
    const byName = new Map(tools.map((tool) => [tool.name, tool]));
    for (const name of TOOLS) {
      const tool = byName.get(name);
      expect(tool).toBeDefined();
      const python = contract.find((entry) => entry.name === name);
      const expected = Object.keys(python?.inputSchema.properties ?? {}).sort();
      const actual = Object.keys(
        (tool?.inputSchema as { properties?: object } | undefined)
          ?.properties ?? {},
      ).sort();
      expect(actual).toEqual(expected);
      expect(
        [
          ...((tool?.inputSchema as { required?: string[] } | undefined)
            ?.required ?? []),
        ].sort(),
      ).toEqual([...(python?.inputSchema.required ?? [])].sort());
    }
  });
});

describe("search_patents and search_uspto", () => {
  test("US searches PPUBS at family offset 0 with lean stubs", async () => {
    const result = await mcp.call("search_patents", {
      query: "widget",
      limit: 30,
    });
    const search = fake.seen.find((s) => s.path.endsWith("searchWithBeFamily"));
    expect(
      (search?.body as { pageCount: number; start: number } | undefined)
        ?.pageCount,
    ).toBe(20);
    expect((search?.body as { start: number } | undefined)?.start).toBe(0);
    expect(result.items?.[0]).toEqual({
      publication_number: "20230123456",
      patent_title: "Neural widget",
      type: "US-PGPUB",
      publication_date: "2023-04-20",
      app_filing_date: null,
      applicant: "Acme Corp",
      assignee: "Acme Holdings",
      main_classification_code: null,
    });
    expect(result.summary).toContain("in 2 of 4 families at family offset 0");
    expect(result.more_available).toBe(true);
  });
  test("EP/WO searches EPO OPS CQL with the requested range", async () => {
    const result = await mcp.call("search_patents", {
      query: "ta=bricks",
      jurisdiction: "ep_wo",
      limit: 5,
    });
    expect(last("ops.epo.org")?.query).toEqual({
      q: "ta=bricks",
      Range: "1-5",
    });
    expect(result.items?.[0]).toMatchObject({
      publication_number: "EP1000000A1",
      country: "EP",
      kind: "A1",
      family_id: "7",
    });
    expect(result.summary).toBe(
      "EPO OPS — `ta=bricks` (publication): 1 of 40 hits.",
    );
  });
  test("KR search is reported as not yet available", async () => {
    await expect(
      mcp.call("search_patents", { query: "x", jurisdiction: "kr" }),
    ).rejects.toThrow(
      /Korean \(KR\) patent search is not yet available.*jurisdiction='us'/,
    );
  });
  test("search_uspto routes applications, publications and petitions", async () => {
    const apps = await mcp.call("search_uspto", {
      dataset: "applications",
      query: "widget",
      limit: 2,
      offset: 3,
    });
    const body = last("api.uspto.gov")?.body as { pagination: unknown };
    expect(body.pagination).toEqual({ offset: 3, limit: 2 });
    expect(apps.summary).toBe("USPTO Applications — `widget`: 2 of 7 hits.");
    expect(apps.more_available).toBe(true);
    const pubs = await mcp.call("search_uspto", {
      dataset: "publications",
      query: "widget",
    });
    expect(pubs.items?.[0]?.publication_number).toBe("20230123456");
    const petitions = await mcp.call("search_uspto", {
      dataset: "petitions",
      query: "revival",
    });
    expect(last("api.uspto.gov")?.path).toBe(
      "/api/v1/petition/decisions/search",
    );
    expect(petitions.items?.[0]).toMatchObject({
      petition_decision_record_identifier: "p-1",
      decision_type_code: "GRANTED",
      deciding_office: "OPET",
    });
  });
});

describe("get_patent", () => {
  test("biblio routes US to PPUBS and others to EPO with not-found batches", async () => {
    const us = await mcp.call("get_patent", {
      view: "biblio",
      identifier: "US20230123456A1",
    });
    expect(us.summary).toStartWith(
      "**US publication 20230123456** — Neural widget",
    );
    const epo = await mcp.call("get_patent", {
      view: "biblio",
      identifier: ["EP1000000A1", "EP9999999A1", "US20230123456A1"],
    });
    expect(epo.not_found).toEqual(["EP9999999A1"]);
    expect(epo.summary).toBe(
      "Fetched 2 of 3 EPO OPS biblio records. Not found: EP9999999A1.",
    );
    await expect(
      mcp.call("get_patent", { view: "biblio", identifier: "KR1020230012345" }),
    ).rejects.toThrow(
      "Korean (KR) bibliographic retrieval is not yet available",
    );
  });
  test("claims cascade: ODP grant XML first", async () => {
    const result = await mcp.call("get_patent", {
      view: "claims",
      identifier: "US10123456B2",
    });
    expect(result.summary).toBe("2 claims for US10123456B2 from uspto_odp.");
    expect(result.items?.[0]).toEqual({
      claim_number: 1,
      limitations: [
        { text: "A widget comprising:", depth: 0 },
        { text: "a gear.", depth: 1 },
      ],
      claim_text: "1. A widget comprising:\n    a gear.",
      claim_type: "independent",
      depends_on: null,
    });
    expect(result.items?.[1]).toMatchObject({
      claim_type: "dependent",
      depends_on: 1,
    });
  });
  test("claims cascade falls through to PPUBS, then EPO", async () => {
    const ppubs = await mcp.call("get_patent", {
      view: "claims",
      identifier: "US10000001B2",
    });
    // ODP could not resolve the patent, and PPUBS returned no document for it.
    expect(ppubs.summary).toBe("2 claims for US10000001B2 from epo_ops.");
    expect(ppubs.items?.map((c) => c.claim_text)).toEqual([
      "1. An apparatus.",
      "2. The apparatus of claim 1.",
    ]);
    fake.noGrant.add("20230123456");
    const fromPpubs = await mcp.call("get_patent", {
      view: "claims",
      identifier: "US20230123456A1",
    });
    expect(fromPpubs.summary).toBe(
      "2 claims for US20230123456A1 from uspto_ppubs.",
    );
    expect(fromPpubs.items?.[1]).toMatchObject({
      depends_on: 1,
      claim_type: "dependent",
    });
    const ep = await mcp.call("get_patent", {
      view: "claims",
      identifier: "EP1000000B1",
    });
    expect(ep.summary).toBe("2 claims for EP1000000B1 from epo_ops.");
  });
  test("single-number views reject lists; family, figures and citations", async () => {
    await expect(
      mcp.call("get_patent", { view: "claims", identifier: ["US1", "US2"] }),
    ).rejects.toThrow("takes a single number, not a list");
    const family = await mcp.call("get_patent", {
      view: "family",
      identifier: "US10123456B2",
    });
    expect(family.details?.rootApplication ?? family.summary).toBeTruthy();
    expect(family.summary).toContain("USPTO family for US10123456B2");
    const figures = await mcp.call("get_patent", {
      view: "figures",
      identifier: "US10123456B2",
    });
    expect(figures.details).toMatchObject({
      results: [],
      callouts_available: false,
      pdf_source: "download_document(source='patent_pdf')",
    });
    const citations = await mcp.call("get_patent", {
      view: "citations",
      identifier: "US10123456B2",
    });
    // The patent is resolved to its application before the citations search.
    const oa = fake.seen.filter((s) => s.path.includes("/oa/")).at(-1);
    expect(oa?.path).toBe("/api/v1/patent/oa/oa_citations/v2/records");
    expect(
      (oa?.body as { criteria: string; rows: string } | undefined)?.criteria,
    ).toBe("patentApplicationNumber:16123456");
    expect((oa?.body as { rows: string } | undefined)?.rows).toBe("100");
    expect(citations.summary).toStartWith("NOTE: True forward citations");
    expect(
      (citations.details?.examiner_cited_references as unknown[] | undefined)
        ?.length,
    ).toBe(1);
    const foreign = await mcp.call("get_patent", {
      view: "citations",
      identifier: "EP1000000A1",
    });
    expect(foreign.details).toEqual({
      available: false,
      jurisdiction: "EP",
      reason: "no_clean_forward_citation_source",
    });
  });
});

describe("resolve_patent_number and patent_client_status", () => {
  test("resolve, convert_epo and cql_help", async () => {
    const resolved = await mcp.call("resolve_patent_number", {
      number: "US20230123456A1",
    });
    expect(resolved.details?.publication_number).toBe("20230123456");
    const converted = await mcp.call("resolve_patent_number", {
      mode: "convert_epo",
      number: "EP1000000A1",
    });
    expect(last("ops.epo.org")?.path).toBe(
      "/3.2/rest-services/number-service/publication/original/EP1000000A1/docdb",
    );
    expect(converted.summary).toBe(
      "**EPO number conversion `EP1000000A1`** → EP1000000A1.",
    );
    const before = fake.seen.length;
    const help = await mcp.call("resolve_patent_number", { mode: "cql_help" });
    expect(fake.seen.length).toBe(before);
    expect(help.details).toHaveProperty("fields.ta");
    await expect(mcp.call("resolve_patent_number", {})).rejects.toThrow(
      "resolve_patent_number(mode='resolve') requires number",
    );
    await expect(
      mcp.call("resolve_patent_number", {
        mode: "convert_epo",
        number: "EP1",
        input_format: "bogus",
      }),
    ).rejects.toThrow("input_format must be");
  });
  test("status lists configured families and gaps without network", async () => {
    const before = fake.seen.length;
    const status = await mcp.call("patent_client_status", {});
    expect(fake.seen.length).toBe(before);
    expect(status.details).toMatchObject({ version: "0.1.0" });
    expect(status.details?.unported_tools).toEqual([...UNPORTED_FACADE_TOOLS]);
    expect(status.details?.unported_modes).toContain(
      "search_patents(jurisdiction='kr')",
    );
    expect(
      Object.keys(status.details?.configured_families as object),
    ).toContain("epo");
  });
  test("EPO branches report missing credentials", async () => {
    const plain = await connect(fakeUpstreams(), false);
    try {
      await expect(
        plain.call("search_patents", { query: "x", jurisdiction: "ep_wo" }),
      ).rejects.toThrow(
        "EPO OPS is not enabled on this server (EPO_OPS_API_KEY/EPO_OPS_API_SECRET",
      );
      await expect(
        plain.call("resolve_patent_number", {
          mode: "convert_epo",
          number: "EP1",
        }),
      ).rejects.toThrow("EPO OPS is not enabled");
      await expect(
        plain.call("get_patent", { view: "claims", identifier: "EP1000000B1" }),
      ).rejects.toThrow("EPO OPS fallback is not configured");
      const help = await plain.call("resolve_patent_number", {
        mode: "cql_help",
      });
      expect(help.summary).toContain("CQL");
    } finally {
      await plain.close();
    }
  });
});

describe("get_uspto", () => {
  test("application and assignment reject patent-style numbers before any request", async () => {
    const before = fake.seen.length;
    await expect(
      mcp.call("get_uspto", {
        dataset: "application",
        identifier: "US10123456B2",
      }),
    ).rejects.toThrow("needs a numeric USPTO application number");
    await expect(
      mcp.call("get_uspto", {
        dataset: "assignment",
        identifier: ["16123456", "US1B2"],
      }),
    ).rejects.toThrow("1 patent/publication-style identifier(s): US1B2");
    expect(fake.seen.length).toBe(before);
  });
  test("application batches report not-found members; singles fail", async () => {
    const batch = await mcp.call("get_uspto", {
      dataset: "application",
      identifier: ["16123456", "99999999"],
    });
    expect(batch.not_found).toEqual(["99999999"]);
    expect(batch.summary).toBe(
      "Fetched 1 of 2 USPTO applications. Not found: 99999999.",
    );
    const single = await mcp.call("get_uspto", {
      dataset: "application",
      identifier: "16123456",
    });
    expect(single.summary).toBe(
      "**US application 16123456** — Widget\nStatus: Patented Case. Filed 2018-01-01; issued as US 10123456 on 2020-01-01.",
    );
    await expect(
      mcp.call("get_uspto", { dataset: "application", identifier: "99999999" }),
    ).rejects.toThrow();
  });
  test("assignment, petition, publication and office action", async () => {
    const assignment = await mcp.call("get_uspto", {
      dataset: "assignment",
      identifier: "16123456",
    });
    expect(assignment.summary).toBe(
      "**US application 16123456** — 1 assignment on record.\nLatest reel/frame 500/1: ASSIGNMENT → ACME.",
    );
    const petition = await mcp.call("get_uspto", {
      dataset: "petition",
      identifier: "p-1",
    });
    expect(petition.summary).toStartWith("**USPTO petition p-1** — Revival");
    const petitions = await mcp.call("get_uspto", {
      dataset: "petition",
      identifier: ["p-1", "p-404"],
    });
    expect(petitions.not_found).toEqual(["p-404"]);
    const publication = await mcp.call("get_uspto", {
      dataset: "publication",
      identifier: ["US20230123456A1"],
    });
    expect(publication.items).toHaveLength(1);
    const action = await mcp.call("get_uspto", {
      dataset: "office_action",
      identifier: "oa-1",
    });
    const oa = fake.seen.filter((s) => s.path.includes("/oa/")).at(-1);
    expect(oa?.path).toBe("/api/v1/patent/oa/oa_actions/v1/records");
    expect((oa?.body as { criteria: string } | undefined)?.criteria).toBe(
      "id:oa\\-1",
    );
    expect(action.summary).toStartWith(
      "**Office action oa-1** — application 16123456, type CTNF",
    );
    await expect(
      mcp.call("get_uspto", {
        dataset: "office_action",
        identifier: "missing",
      }),
    ).rejects.toThrow("Office action 'missing' not found");
  });
});

describe("get_file_history", () => {
  test("list maps document descriptors like Python", async () => {
    const result = await mcp.call("get_file_history", {
      application_number: "16123456",
    });
    expect(result.summary).toBe(
      "USPTO application 16123456 — 2 file-history documents.",
    );
    expect(result.items?.[1]).toEqual({
      document_identifier: "DOC2",
      code: "NOA",
      description: "Notice of Allowance",
      date: "2019-11-01T00:00:00",
      direction: null,
      page_count: null,
      formats: ["pdf", "docx"],
    });
  });
  test("item requires an identifier and explains missing formats or documents", async () => {
    await expect(
      mcp.call("get_file_history", {
        application_number: "16123456",
        mode: "item",
      }),
    ).rejects.toThrow("requires document_identifier");
    const pdf = await mcp.call("get_file_history", {
      application_number: "16123456",
      mode: "item",
      document_identifier: "DOC1",
    });
    expect(pdf.download_url ?? pdf.file_path).toBeTruthy();
    await expect(
      mcp.call("get_file_history", {
        application_number: "16123456",
        mode: "item",
        document_identifier: "DOC1",
        format: "xml",
      }),
    ).rejects.toThrow('has no XML version. Available formats: ["pdf"]');
    await expect(
      mcp.call("get_file_history", {
        application_number: "16123456",
        mode: "item",
        document_identifier: "NOPE",
      }),
    ).rejects.toThrow("Document 'NOPE' not found in application 16123456");
  });
  test("download filters and zips matching PDFs", async () => {
    const start = fake.seen.length;
    const zip = await mcp.call("get_file_history", {
      application_number: "16123456",
      mode: "download",
      document_codes: ["NOA"],
    });
    expect(zip.download_url ?? zip.file_path).toBeTruthy();
    const downloads = fake.seen
      .slice(start)
      .filter((s) => s.path.startsWith("/api/v1/download/"));
    expect(downloads.map((s) => s.path)).toContain(
      "/api/v1/download/applications/16123456/DOC2.pdf",
    );
    expect(downloads.map((s) => s.path)).not.toContain(
      "/api/v1/download/applications/16123456/DOC1.pdf",
    );
    await expect(
      mcp.call("get_file_history", {
        application_number: "16123456",
        mode: "download",
        after: "2030-01-01",
      }),
    ).rejects.toThrow("match the given filters");
    await expect(
      mcp.call("get_file_history", {
        application_number: "16123456",
        mode: "download",
        before: "01/01/2020",
      }),
    ).rejects.toThrow("before must be an ISO date");
  });
});

describe("search_office_actions and search_patent_assignments", () => {
  test("office actions route by result type with Python stubs", async () => {
    const rejections = await mcp.call("search_office_actions", {
      criteria: "patentApplicationNumber:16123456",
    });
    expect(last("api.uspto.gov")?.path).toBe(
      "/api/v1/patent/oa/oa_rejections/v2/records",
    );
    expect(rejections.items?.[0]).toEqual({
      document_identifier: "oa-1",
      application_number: "16123456",
      mail_date: "2019-05-01T00:00:00",
      document_code: "CTNF",
      art_unit: "1713",
      rejection_types: ["§103"],
      legal_section_code: "103",
      national_class: "438",
    });
    expect(rejections.summary).toBe(
      "USPTO office actions (rejections) — `patentApplicationNumber:16123456`: 1 of 30 hits.",
    );
    expect(rejections.more_available).toBe(true);
    const text = await mcp.call("search_office_actions", {
      criteria: "x",
      result_type: "TEXT",
      start: 5,
      rows: 10,
      full: true,
    });
    const body = last("api.uspto.gov")?.body as Record<string, string>;
    expect(last("api.uspto.gov")?.path).toBe(
      "/api/v1/patent/oa/oa_actions/v1/records",
    );
    expect([body.start, body.rows]).toEqual(["5", "10"]);
    expect(text.items?.[0]?.bodyText).toBe("full text");
    await expect(
      mcp.call("search_office_actions", {
        criteria: "x",
        result_type: "bogus",
      }),
    ).rejects.toThrow("result_type must be one of");
  });
  test("assignments validate the axis, close date ranges and project stubs", async () => {
    await expect(
      mcp.call("search_patent_assignments", { query: "x", by: "owner" }),
    ).rejects.toThrow("`by` must be one of");
    const result = await mcp.call("search_patent_assignments", {
      query: "Raytheon",
      by: "assignee",
      executed_after: "2015-01-01",
      limit: 1,
    });
    const body = last("assignmentcenter.uspto.gov")?.body as {
      dataFilter: { filterBy: { startDate: string; endDate: string }[] };
    };
    expect(body.dataFilter.filterBy[0]?.startDate).toBe("20150101");
    expect(body.dataFilter.filterBy[0]?.endDate).toBe(
      new Date().toISOString().slice(0, 10).replaceAll("-", ""),
    );
    expect(result.items?.[0]).toEqual({
      reel_frame: "35130/327",
      conveyance: "ASSIGNMENT OF ASSIGNOR'S INTEREST",
      assignor: "MARRON, JOSEPH",
      assignee: "RAYTHEON COMPANY",
      assignor_execution_date: "03/06/2015",
      number_of_properties: 1,
      application_number: "14123456",
      patent_number: "9000000",
      publication_number: null,
    });
    expect(result.summary).toBe(
      "USPTO patent assignments (by assignee) — `Raytheon`: 1 of 12 hits.",
    );
    await mcp.call("search_patent_assignments", {
      query: "x",
      by: "assignor",
      executed_before: "2000-01-01",
    });
    const closed = last("assignmentcenter.uspto.gov")?.body as {
      dataFilter: { filterBy: { startDate: string }[] };
    };
    expect(closed.dataFilter.filterBy[0]?.startDate).toBe("19800101");
  });
});

import { afterAll, beforeAll, expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  ApiError,
  BulkDataClient,
  CafcClient,
  EpcClient,
  EpoCaseLawClient,
  EpoGuidelinesClient,
  type EpoOpsClient,
  EpoPctGuidelinesClient,
  EpoUpGuidelinesClient,
  MpepClient,
  PtabAppealsClient,
  PtabInterferencesClient,
  PtabTrialsClient,
  type PublicationsClient,
  TmepClient,
} from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { unzipSync } from "fflate";
import { createServer } from "../packages/mcp/src/index.js";

const PDF = new TextEncoder().encode("%PDF-1.4 synthetic\n%%EOF");
const ODP = "https://api.uspto.gov";
const proceeding = {
  trialNumber: "IPR2024-00001",
  trialMetaData: {
    trialTypeCode: "IPR",
    trialStatusCategory: "Instituted",
    petitionFilingDate: "2024-01-02",
  },
  patentOwnerData: { patentNumber: "10123456", patentOwnerName: "Owner Co" },
  regularPetitionerData: { realPartyInInterestName: "Petitioner Inc" },
};
const decision = (
  id: string,
  date: string,
  type = "Final Written Decision",
) => ({
  documentData: {
    documentIdentifier: id,
    documentTitleText: `Decision ${id}`,
    documentFilingDate: date,
    fileDownloadURI: `${ODP}/api/v1/download/ptab/${id}.pdf`,
  },
  decisionData: { decisionTypeCategory: type, decisionIssueDate: date },
});

/** Synthetic ODP routes keyed by method and path. */
const odpRequests: string[] = [];
const odpFetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const request = new Request(input, init);
  const url = new URL(request.url);
  odpRequests.push(`${request.method} ${url.pathname}`);
  const json = (data: unknown, status = 200) => Response.json(data, { status });
  switch (`${request.method} ${url.pathname}`) {
    case "POST /api/v1/patent/trials/proceedings/search": {
      const body = (await request.json()) as { pagination: { offset: number } };
      const rows = [
        proceeding,
        { ...proceeding, trialNumber: "IPR2024-00002" },
      ];
      return json({
        count: 2,
        patentTrialProceedingDataBag: rows.slice(
          body.pagination.offset,
          body.pagination.offset + 1,
        ),
      });
    }
    case "POST /api/v1/patent/trials/decisions/search":
      return json({
        count: 1,
        patentTrialDocumentDataBag: [
          { trialNumber: "IPR2024-00001", ...decision("D1", "2025-03-01") },
        ],
      });
    case "POST /api/v1/patent/appeals/decisions/search":
      return json({
        count: 1,
        patentAppealDataBag: [
          {
            appealNumber: "2024-000123",
            documentData: { documentIdentifier: "A1" },
            decisionData: {
              appealOutcomeCategory: "Affirmed",
              decisionIssueDate: "2024-05-01",
            },
            appellantData: { applicationNumberText: "16123456" },
          },
        ],
      });
    case "GET /api/v1/patent/trials/proceedings/IPR2024-00001":
      return json(proceeding);
    case "GET /api/v1/patent/trials/proceedings/IPR2099-99999":
      return json({ message: "not found" }, 404);
    case "GET /api/v1/patent/trials/IPR2024-00001/decisions":
      return json({
        count: 2,
        patentTrialDocumentDataBag: [
          decision("D1", "2025-03-01"),
          decision("D2", "2024-07-01", "Institution"),
        ],
      });
    case "GET /api/v1/patent/trials/IPR2024-00001/documents":
      return json({
        count: 1,
        patentTrialDocumentDataBag: [
          {
            documentData: {
              documentIdentifier: "P1",
              documentTypeDescriptionText: "Petition",
              documentFilingDate: "2024-01-02",
              filingPartyCategory: "Petitioner",
              fileDownloadURI: `${ODP}/api/v1/download/ptab/P1.pdf`,
            },
          },
        ],
      });
    case "GET /api/v1/patent/appeals/16123456/decisions":
      return json({}, 404);
    case "GET /api/v1/patent/appeals/16999999/decisions":
      return json({
        count: 1,
        patentAppealDataBag: [
          {
            appealNumber: "2024-000999",
            documentData: {
              documentIdentifier: "A9",
              fileDownloadURI: `${ODP}/api/v1/download/ptab/A9.pdf`,
            },
            decisionData: {
              decisionIssueDate: "2024-02-02",
              decisionTypeCategory: "Decision",
            },
          },
        ],
      });
    case "GET /api/v1/patent/interferences/106001/decisions":
      return json({
        count: 1,
        patentInterferenceDataBag: [
          {
            interferenceNumber: "106001",
            decisionDocumentData: {
              documentIdentifier: "I1",
              interferenceOutcomeCategory: "Judgment",
            },
            seniorPartyData: { realPartyInInterestName: "Senior" },
          },
        ],
      });
    case "GET /api/v1/datasets/products/search":
      return json({
        count: 1,
        bulkDataProductBag: [
          {
            productIdentifier: "PTGRXML",
            productTitleText: "Patent Grant XML",
          },
        ],
      });
    case "GET /api/v1/datasets/products/PTGRXML":
      return json({
        count: 1,
        bulkDataProductBag: [
          {
            productIdentifier: "PTGRXML",
            productTitleText: "Patent Grant XML",
            productFileBag: {
              count: 1,
              fileDataBag: [
                {
                  fileName: "ipg251021.zip",
                  fileSize: 123,
                  fileDownloadURI: `${ODP}/api/v1/datasets/products/files/PTGRXML/ipg251021.zip`,
                },
              ],
            },
          },
        ],
      });
  }
  if (url.pathname.startsWith("/api/v1/download/ptab/"))
    return new Response(PDF, {
      headers: { "content-type": "application/pdf" },
    });
  return json({ message: "unexpected route" }, 500);
}) as unknown as typeof fetch;

const odp = { apiKey: "fixture-key", fetch: odpFetch, retryLimit: 0 };
const pdfCalls: string[] = [];
const publications = {
  async resolveDocumentByPublicationNumber(number: string) {
    pdfCalls.push(`ppubs:${number}`);
    if (number === "US404B1")
      throw new ApiError("Patent publication was not found.", 404, "NOT_FOUND");
    return {
      publication_number: number,
      document_structure: { page_count: 1 },
    };
  },
  async downloadPdf() {
    return {
      data: PDF,
      provenance: {
        source_url: "https://ppubs.uspto.gov/pdf",
        source_name: "USPTO Patent Public Search",
        retrieved_at: new Date().toISOString(),
        cache_hit: false,
      },
    };
  },
} as unknown as PublicationsClient;
const epoOps = {
  async downloadPdf(number: string) {
    pdfCalls.push(`epo:${number}`);
    if (number === "EP404A1") throw new ApiError("not found", 404, "NOT_FOUND");
    return {
      data: PDF,
      pages: 1,
      publicationNumber: number,
      provenance: {
        source_url: `https://ops.epo.org/3.2/rest-services/published-data/publication/docdb/${number}/images`,
        source_name: "EPO OPS",
        retrieved_at: new Date().toISOString(),
        cache_hit: false,
      },
    };
  },
} as unknown as EpoOpsClient;

const corpus = (name: string) =>
  join(import.meta.dir, "fixtures", "epo-legal", `${name}.db`);
let server: FastMCP;
let client: Client;
let mpep: MpepClient;
let tmep: TmepClient;
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  details?: Record<string, unknown>;
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  download_url?: string;
  file_path?: string;
  filename?: string;
  content_type?: string;
};
/** Synthetic CAFC opinions index: one page with a nonce, the DataTables endpoint and PDFs. */
const cafcRows = [
  [
    "10/19/2026",
    "24-1945",
    "PTO",
    "OPINION",
    `<a sort="GOOGLE LLC v. VALTRUS INNOVATIONS LTD. [OPINION]">`,
    "Precedential",
    "opinions-orders/24-1945.OPINION.pdf",
  ],
  [
    "10/18/2026",
    "25-1000",
    "MSPB",
    "ORDER",
    `<a sort="SMITH v. MSPB [ORDER]">`,
    "Nonprecedential",
    "opinions-orders/25-1000.ORDER.pdf",
  ],
  [
    "10/17/2026",
    "24-2000",
    "DCT",
    "OPINION",
    `<a sort="ACME v. WIDGET CO. [OPINION]">`,
    "Nonprecedential",
    "opinions-orders/24-2000.OPINION.pdf",
  ],
  [
    "10/16/2026",
    "24-2000",
    "DCT",
    "ORDER",
    `<a sort="ACME v. WIDGET CO. [ORDER]">`,
    "Nonprecedential",
    "opinions-orders/24-2000.ORDER.pdf",
  ],
];
const cafcFetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const request = new Request(input, init);
  const url = new URL(request.url);
  if (url.pathname.endsWith(".pdf")) return new Response(PDF);
  if (request.method === "GET")
    return new Response(
      '<input type="hidden" id="wdtNonceFrontendServerSide_1" value="0123456789" />',
    );
  const form = new URLSearchParams(await request.text());
  const query = form.get("search[value]")?.toLowerCase() ?? "";
  const origins = form.get("columns[2][search][value]")?.split("|");
  const rows = cafcRows.filter(
    (row) =>
      (row[1]?.includes(query) || row[4]?.toLowerCase().includes(query)) &&
      (!origins?.[0] || origins.includes(row[2] ?? "")),
  );
  const start = Number(form.get("start"));
  return Response.json({
    recordsFiltered: String(rows.length),
    recordsTotal: String(cafcRows.length),
    data: rows.slice(start, start + Number(form.get("length"))),
  });
}) as typeof fetch;

const call = async (name: string, args: Record<string, unknown>) =>
  (await client.callTool<Envelope>(name, args)).structuredContent as Envelope;

beforeAll(async () => {
  mpep = new MpepClient({
    corpusPath: join(import.meta.dir, "fixtures", "mpep", "plain.db"),
  });
  tmep = new TmepClient({
    corpusPath: join(import.meta.dir, "fixtures", "tmep", "tmep.db"),
  });
  server = createServer({
    toolset: "curated",
    clients: {
      trials: new PtabTrialsClient(odp),
      appeals: new PtabAppealsClient(odp),
      interferences: new PtabInterferencesClient(odp),
      bulk: new BulkDataClient(odp),
      cafc: new CafcClient({ fetch: cafcFetch, retryLimit: 0 }),
      publications,
      epoOps,
      mpep,
      tmep,
    },
    epoLegal: {
      epc: new EpcClient({ corpusPath: corpus("epc") }),
      caseLaw: new EpoCaseLawClient({ corpusPath: corpus("caselaw") }),
      guidelines: new EpoGuidelinesClient({ corpusPath: corpus("guidelines") }),
      pctGuidelines: new EpoPctGuidelinesClient({
        corpusPath: corpus("pct_guidelines"),
      }),
      upGuidelines: new EpoUpGuidelinesClient({
        corpusPath: corpus("up_guidelines"),
      }),
    },
  });
  client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
});
afterAll(async () => {
  await client.close();
  await server.close();
  mpep.close();
  tmep.close();
});

test("the group's tools are registered with the deployed parameter names", async () => {
  const tools = await client.listTools();
  const contract = JSON.parse(
    await readFile(
      join(import.meta.dir, "fixtures", "facade", "python-facade-tools.json"),
      "utf8",
    ),
  ) as { name: string; inputSchema: { properties: Record<string, unknown> } }[];
  for (const name of [
    "search_litigation",
    "get_litigation",
    "list_ptab_children",
    "search_legal_reference",
    "get_legal_reference",
    "search_bulk_data",
    "download_document",
  ]) {
    const tool = tools.find((t) => t.name === name);
    const python = contract.find((t) => t.name === name);
    expect(tool).toBeDefined();
    expect(Object.keys(tool?.inputSchema.properties ?? {}).sort()).toEqual(
      Object.keys(python?.inputSchema.properties ?? {}).sort(),
    );
  }
  for (const absent of ["search_upc_decisions"])
    expect(tools.map((t) => t.name)).not.toContain(absent);
});

test("search_litigation routes PTAB record kinds and pages by cursor", async () => {
  const first = await call("search_litigation", {
    forum: "ptab",
    query: "owner",
    limit: 1,
  });
  expect(first.items).toEqual([
    expect.objectContaining({
      type: "proceeding",
      trial_number: "IPR2024-00001",
      status: "Instituted",
      patent_owner: "Owner Co",
      petitioner: "Petitioner Inc",
    }),
  ]);
  expect(first.more_available).toBe(true);
  const second = await call("search_litigation", {
    forum: "ptab",
    query: "owner",
    next_cursor: first.next_cursor,
  });
  expect(second.items[0]?.trial_number).toBe("IPR2024-00002");
  expect(second.more_available).toBe(false);
  const decisions = await call("search_litigation", {
    forum: "ptab",
    query: "x",
    ptab_type: "trial_decision",
  });
  expect(decisions.items[0]).toMatchObject({
    document_identifier: "D1",
    decision_type: "Final Written Decision",
  });
  const appeals = await call("search_litigation", {
    forum: "ptab",
    query: "x",
    ptab_type: "appeal_decision",
  });
  expect(appeals.items[0]).toMatchObject({
    appeal_outcome: "Affirmed",
    application_number: "16123456",
  });
});

test("search_litigation(forum='cafc') and search_cafc_patent_opinions search the CAFC index", async () => {
  const first = await call("search_litigation", {
    forum: "cafc",
    query: "v.",
    limit: 2,
  });
  expect(first.items).toEqual([
    {
      appeal_number: "24-1945",
      case_name_short: "GOOGLE LLC v. VALTRUS INNOVATIONS LTD.",
      release_date: "2026-10-19",
      origin: "PTO",
      document_type: "OPINION",
      precedential_status: "Precedential",
      is_patent_case: false,
      pdf_url:
        "https://www.cafc.uscourts.gov/opinions-orders/24-1945.OPINION.pdf",
    },
    expect.objectContaining({ appeal_number: "25-1000" }),
  ]);
  expect(first.more_available).toBe(true);
  const second = await call("search_litigation", {
    forum: "cafc",
    query: "v.",
    next_cursor: first.next_cursor,
  });
  expect(second.items.map((o) => o.document_type)).toEqual([
    "OPINION",
    "ORDER",
  ]);
  expect(second.more_available).toBe(false);
  const full = await call("search_litigation", {
    forum: "cafc",
    query: "valtrus",
    full: true,
  });
  expect(full.items[0]).toHaveProperty("patent_confidence", 0);
  const patentOnly = await call("search_litigation", {
    forum: "cafc",
    query: "v.",
    patent_only: true,
  });
  expect(patentOnly.items).toEqual([]);
  expect(patentOnly.summary).toContain("Inspected 4 of 4 source rows");
  const byOrigin = await call("search_cafc_patent_opinions", {
    date_from: "2026-10-01",
  });
  expect(byOrigin.items.map((o) => o.origin)).toEqual(["PTO", "DCT", "DCT"]);
  await expect(
    client.callTool("search_cafc_patent_opinions", { date_to: "2026-10-01" }),
  ).rejects.toThrow("date_to requires date_from");
});

test("get_litigation fetches PTAB records, reports missing list members, and refuses UPC", async () => {
  const one = await call("get_litigation", {
    forum: "ptab",
    identifier: "IPR2024-00001",
  });
  expect(one.summary).toContain("IPR2024-00001");
  expect(one.items[0]?.trialNumber).toBe("IPR2024-00001");
  const batch = await call("get_litigation", {
    forum: "ptab",
    identifier: ["IPR2024-00001", "IPR2099-99999"],
  });
  expect(batch.items).toHaveLength(1);
  expect(batch.not_found).toEqual(["IPR2099-99999"]);
  await expect(
    client.callTool("get_litigation", {
      forum: "ptab",
      identifier: "IPR2099-99999",
    }),
  ).rejects.toThrow();
  await expect(
    client.callTool("get_litigation", {
      forum: "upc",
      identifier: "UPC_CFI_1/2025",
    }),
  ).rejects.toThrow("not yet available");
});

test("list_ptab_children covers trials, appeals with no decisions, and interferences", async () => {
  const both = await call("list_ptab_children", {
    parent_type: "trial",
    parent_identifier: "IPR2024-00001",
    include: "both",
  });
  expect(both.items.map((i) => [i.type, i.document_identifier])).toEqual([
    ["trial_decision", "D1"],
    ["trial_decision", "D2"],
    ["trial_document", "P1"],
  ]);
  expect(both.items[0]?.trial_number).toBe("IPR2024-00001");
  const none = await call("list_ptab_children", {
    parent_type: "application",
    parent_identifier: "16123456",
  });
  expect(none.items).toEqual([]);
  const interference = await call("list_ptab_children", {
    parent_type: "interference",
    parent_identifier: "106001",
  });
  expect(interference.items[0]).toMatchObject({
    interference_outcome: "Judgment",
    senior_party: "Senior",
  });
  await expect(
    client.callTool("list_ptab_children", {
      parent_type: "court",
      parent_identifier: "x",
    }),
  ).rejects.toThrow("parent_type");
});

test("legal references route MPEP, TMEP and every EPO corpus, and refuse unported corpora", async () => {
  const mpepHits = await call("search_legal_reference", {
    corpus: "uspto_mpep",
    query: "patent",
    limit: 2,
  });
  expect(mpepHits.items.length).toBeGreaterThan(0);
  expect(Object.keys(mpepHits.items[0] ?? {}).sort()).toEqual([
    "href",
    "section_number",
    "snippet",
    "title",
  ]);
  for (const name of [
    "uspto_tmep",
    "epc",
    "epo_case_law",
    "epo_guidelines",
    "epo_pct_guidelines",
    "epo_up_guidelines",
  ]) {
    const hits = await call("search_legal_reference", {
      corpus: name,
      query: "the",
      syntax: "and",
      limit: 1,
    });
    expect(hits.items.length).toBe(1);
  }
  const article = await call("get_legal_reference", {
    corpus: "epc",
    identifier: "Article 54",
  });
  expect(article.items[0]).toMatchObject({
    citation: { kind: "article", number: "54" },
  });
  expect(String(article.items[0]?.text).length).toBeGreaterThan(20);
  const first = mpepHits.items[0];
  const section = await call("get_legal_reference", {
    corpus: "uspto_mpep",
    identifier: String(first?.section_number ?? first?.href),
  });
  expect(section.items).toHaveLength(1);
  await expect(
    client.callTool("get_legal_reference", {
      corpus: "epc",
      identifier: "Article 9999",
    }),
  ).rejects.toThrow("not found");
  await expect(
    client.callTool("search_legal_reference", {
      corpus: "epc",
      query: "x",
      version: "2020",
    }),
  ).rejects.toThrow("only for uspto_mpep");
  for (const name of ["india_statutes", "india_mppp", "tw_trade_secrets"])
    await expect(
      client.callTool("search_legal_reference", { corpus: name, query: "x" }),
    ).rejects.toThrow("not yet available");
});

test("bulk data search and product listings drop key-gated URLs; IPA is not ported", async () => {
  const datasets = await call("search_bulk_data", {
    mode: "datasets",
    query: "grant",
  });
  expect(datasets.items[0]).toMatchObject({ productIdentifier: "PTGRXML" });
  const product = await call("search_bulk_data", {
    mode: "dataset",
    product_id: "PTGRXML",
    latest_only: true,
  });
  expect(JSON.stringify(product.details)).toContain("ipg251021.zip");
  expect(JSON.stringify(product.details)).not.toContain("fileDownloadURI");
  expect(odpRequests).toContain("GET /api/v1/datasets/products/PTGRXML");
  await expect(
    client.callTool("search_bulk_data", { mode: "datasets" }),
  ).rejects.toThrow("requires query");
  await expect(
    client.callTool("search_bulk_data", { mode: "ipa_releases" }),
  ).rejects.toThrow("not yet available");
});

test("patent PDFs cascade from PPUBS to EPO and stop on the first source that has them", async () => {
  pdfCalls.length = 0;
  const us = await call("download_document", {
    source: "patent_pdf",
    identifier: "US10123456B2",
  });
  expect(us.content_type).toBe("application/pdf");
  expect(pdfCalls).toEqual(["ppubs:US10123456B2"]);
  pdfCalls.length = 0;
  await call("download_document", {
    source: "patent_pdf",
    identifier: "US404B1",
  });
  expect(pdfCalls).toEqual(["ppubs:US404B1", "epo:US404B1"]);
  pdfCalls.length = 0;
  const ep = await call("download_document", {
    source: "patent_pdf",
    identifier: "EP3456789A1",
  });
  expect(ep.filename).toBe("EP3456789A1.pdf");
  expect(pdfCalls).toEqual(["epo:EP3456789A1"]);
  await expect(
    client.callTool("download_document", {
      source: "patent_pdf",
      identifier: "EP404A1",
    }),
  ).rejects.toThrow("No PDF found");
});

test("PTAB downloads return one PDF or a ZIP with a manifest, honoring filters and caps", async () => {
  const zipped = await call("download_document", {
    source: "ptab_trial",
    identifier: "IPR2024-00001",
  });
  expect(zipped.content_type).toBe("application/zip");
  const archive = unzipSync(
    new Uint8Array(await readFile(String(zipped.file_path))),
  );
  const manifest = JSON.parse(
    new TextDecoder().decode(archive["manifest.json"]),
  );
  expect(
    manifest.documents.map(
      (d: { document_identifier: string }) => d.document_identifier,
    ),
  ).toEqual(["D1", "D2"]);
  const one = await call("download_document", {
    source: "ptab_trial",
    identifier: "IPR2024-00001",
    after: "2025-01-01",
  });
  expect(one.content_type).toBe("application/pdf");
  const docs = await call("download_document", {
    source: "ptab_trial_docs",
    identifier: "IPR2024-00001",
  });
  expect(docs.filename).toContain("P1");
  const appeal = await call("download_document", {
    source: "ptab_appeal",
    identifier: "16999999",
  });
  expect(appeal.content_type).toBe("application/pdf");
  await expect(
    client.callTool("download_document", {
      source: "ptab_trial",
      identifier: "IPR2024-00001",
      item_ids: ["nope"],
    }),
  ).rejects.toThrow("No PTAB trial decisions");
  await expect(
    client.callTool("download_document", {
      source: "ipa_bulk",
      identifier: "x",
    }),
  ).rejects.toThrow("not yet available");
  const cafc = await call("download_document", {
    source: "cafc",
    identifier: "2024-1945",
  });
  expect(cafc).toMatchObject({
    filename: "24-1945.OPINION.pdf",
    content_type: "application/pdf",
  });
  await expect(
    client.callTool("download_document", {
      source: "cafc",
      identifier: "24-2000",
    }),
  ).rejects.toThrow("has 2 documents");
  const chosen = await call("download_document", {
    source: "cafc",
    identifier:
      "https://www.cafc.uscourts.gov/opinions-orders/24-2000.ORDER.pdf",
  });
  expect(chosen.filename).toBe("24-2000.ORDER.pdf");
  await expect(
    client.callTool("download_document", {
      source: "cafc",
      identifier: "99-9999",
    }),
  ).rejects.toThrow("No Federal Circuit opinion");
  await expect(
    client.callTool("download_document", { source: "ptab_trial" }),
  ).rejects.toThrow("requires identifier");
});

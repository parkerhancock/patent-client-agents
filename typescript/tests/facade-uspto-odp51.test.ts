import { afterAll, beforeAll, expect, test } from "bun:test";
import {
  ApplicationsClient,
  OfficeActionAnalyticsClient,
  OfficeActionsClient,
  TrademarkDecisionsClient,
} from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";

/**
 * The ODP 5.1 additions to the Python facade: get_uspto's section parameter
 * and trademark_decision dataset, three search_uspto datasets, and the
 * trademark_decision download source. Record shapes follow live responses of
 * November 20, 2026.
 */
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available?: boolean;
  filename?: string;
  content_type?: string;
  size?: number;
};
interface Seen {
  method: string;
  path: string;
  body: unknown;
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const order = {
  documentIdentifier: "order1",
  decisionProceedingCategory: "Administrative",
  documentTypeDescriptionText: "Show-cause",
  decisionActionDate: "2026-11-18",
  partyName: "In re Example LLC",
  precedentialIndicator: false,
  fileName: "Show Cause Order.pdf",
  fileDownloadURI:
    "https://data.uspto.gov/api/v1/trademark/decision-proceeding/download/order1.pdf",
};
const reexam = {
  documentIdentifier: "reexam1",
  decisionProceedingCategory: "ExpungReexam",
  proceedingTypeCategory: "REEXAMINATION",
  documentTypeDescriptionText: "PROCEEDING INSTITUTED - REEXAMINATION",
  decisionActionDate: "2026-11-19",
  serialNumber: 98212302,
  registrationNumber: "7798155",
  markLiteralText: "SE NOU",
  registrantName: "SE NOU SPORTS APPAREL LLC",
  documentURI: "https://tsdr.uspto.gov/#caseNumber=98212302",
};
const decisions = "/api/v1/trademark/decision-proceeding/search";

const seen: Seen[] = [];
const upstream = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const request = new Request(input, init);
  const path = new URL(request.url).pathname;
  const text = request.method === "POST" ? await request.clone().text() : "";
  seen.push({
    method: request.method,
    path,
    // The legacy analytics dataset posts a form, not JSON.
    body: text.startsWith("{") ? JSON.parse(text) : null,
  });
  if (path === "/api/v1/patent/applications/16123456/continuity")
    return json({
      count: 1,
      patentFileWrapperDataBag: [
        {
          applicationNumberText: "16123456",
          childContinuityBag: [{ childApplicationNumberText: "17000001" }],
        },
      ],
    });
  if (path.startsWith("/api/v1/patent/applications/"))
    return json({ message: "Not Found" }, 404);
  if (path === "/api/v1/patent/status-codes")
    return json({
      count: 2,
      statusCodeBag: [
        {
          applicationStatusCode: 150,
          applicationStatusDescriptionText: "Patented Case",
        },
      ],
    });
  // The legacy analytics dataset knows none of the new API's identifiers.
  if (path.startsWith("/api/v1/patent/oa/"))
    return json({ response: { numFound: 0, start: 0, docs: [] } });
  if (path === "/api/v1/patent/office-action/oa1/download/officeActionText")
    return new Response("The whole action text.", {
      headers: { "Content-Type": "text/plain" },
    });
  if (path === "/api/v1/patent/office-action/oa1")
    return json({
      count: 1,
      officeActionDataBag: [
        {
          officeActionRecordIdentifier: "oa1",
          applicationNumberText: "17950760",
          documentCode: "CTFR",
          submissionDate: "2026-10-09",
          officeActionText: "The whole",
        },
      ],
    });
  if (
    path.startsWith("/api/v1/patent/office-action/") &&
    path !== "/api/v1/patent/office-action/search"
  )
    return json({ message: "Not Found" }, 404);
  if (path === "/api/v1/patent/office-action/search")
    return json({
      count: 9,
      officeActionDataBag: [
        {
          officeActionRecordIdentifier: "oa1",
          applicationNumberText: "17950760",
          documentCode: "CTFR",
          documentCodeDescriptionText: "Final Rejections",
          submissionDate: "2026-10-09",
          rejectionTypeBag: ["101"],
          inventionTitle: "Widget",
          groupArtUnitNumber: 3681,
        },
      ],
    });
  if (path === decisions)
    return json({ count: 5, trademarkDecisionsDataBag: [order, reexam] });
  // The get-by-identifier endpoint answers with one object, not a list.
  if (path === `${decisions}/order1`)
    return json({ count: 1, trademarkDecisionsDataBag: order });
  if (path === `${decisions}/reexam1`)
    return json({ count: 1, trademarkDecisionsDataBag: reexam });
  if (path.startsWith(`${decisions}/`))
    return json({ message: "Not Found" }, 404);
  if (path.endsWith("/download/order1.pdf"))
    return new Response("%PDF-1.7 order", {
      headers: { "Content-Type": "application/pdf" },
    });
  return json({ error: `unexpected ${path}` }, 500);
}) as typeof fetch;

let client: Client;
let close: () => Promise<void>;
const call = async (name: string, args: Record<string, unknown>) =>
  (await client.callTool<Envelope>(name, args)).structuredContent as Envelope;
beforeAll(async () => {
  const options = { fetch: upstream, retryLimit: 0, apiKey: "k" };
  const server = createServer({
    toolset: "curated",
    clients: {
      applications: new ApplicationsClient(options),
      officeActions: new OfficeActionsClient(options),
      analytics: new OfficeActionAnalyticsClient(options),
      trademarkDecisions: new TrademarkDecisionsClient(options),
    },
  });
  client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  close = async () => {
    await client.close();
    await server.close();
  };
});
afterAll(() => close());
const last = () => seen.at(-1);
const lastFields = () => (last()?.body as { fields?: string[] } | null)?.fields;

test("get_uspto returns one application section and rejects section elsewhere", async () => {
  const result = await call("get_uspto", {
    dataset: "application",
    identifier: "16123456",
    section: "continuity",
  });
  expect(result.summary).toBe(
    "Fetched 1 of 1 USPTO application continuity sections.",
  );
  expect(result.items[0]?.patentFileWrapperDataBag).toHaveLength(1);
  expect(last()?.path).toEndWith("/16123456/continuity");
  const batch = await call("get_uspto", {
    dataset: "application",
    identifier: ["16123456", "16999999"],
    section: "continuity",
  });
  expect(batch.not_found).toEqual(["16999999"]);
  await expect(
    call("get_uspto", {
      dataset: "petition",
      identifier: "p1",
      section: "continuity",
    }),
  ).rejects.toThrow("applies only to dataset='application'");
});

test("search_uspto decodes status codes", async () => {
  const result = await call("search_uspto", {
    dataset: "status_codes",
    query: "Patented",
    limit: 1,
  });
  expect(result.items).toEqual([
    { status_code: 150, description: "Patented Case" },
  ]);
  expect(result.more_available).toBe(true);
  expect(last()?.body).toEqual({
    q: "Patented",
    pagination: { limit: 1, offset: 0 },
  });
});

test("search_uspto searches office-action full text with lean stubs", async () => {
  const result = await call("search_uspto", {
    dataset: "office_actions",
    query: "documentCode:CTFR",
  });
  expect(result.summary).toContain("1 of 9 hits");
  expect(result.items[0]).toEqual({
    document_identifier: "oa1",
    application_number: "17950760",
    patent_number: null,
    mail_date: "2026-10-09",
    document_code: "CTFR",
    document_description: "Final Rejections",
    rejection_types: ["101"],
    invention_title: "Widget",
    art_unit: 3681,
  });
  expect(lastFields()).toContain("inventionTitle");
  const full = await call("search_uspto", {
    dataset: "office_actions",
    query: "documentCode:CTFR",
    full: true,
  });
  expect(full.items[0]?.officeActionRecordIdentifier).toBe("oa1");
  expect(lastFields()).toBeUndefined();
});

test("trademark decisions: search stubs, get, and key-gated URL removal", async () => {
  const result = await call("search_uspto", {
    dataset: "trademark_decisions",
    query: "decisionProceedingCategory:Administrative",
  });
  expect(result.summary).toContain("2 of 5 hits");
  expect(result.items[0]).toMatchObject({
    document_identifier: "order1",
    category: "Administrative",
    party: "In re Example LLC",
    pdf_available: true,
  });
  expect(result.items[1]).toMatchObject({
    serial_number: "98212302",
    party: "SE NOU SPORTS APPAREL LLC",
    tsdr_url: reexam.documentURI,
    pdf_available: false,
  });
  const one = await call("get_uspto", {
    dataset: "trademark_decision",
    identifier: "order1",
  });
  expect(one.summary).toBe(
    "**USPTO trademark decision** — Show-cause\nIn re Example LLC. Category Administrative; dated 2026-11-18.",
  );
  expect(one.items[0]?.pdf_available).toBe(true);
  expect(one.items[0]).not.toHaveProperty("fileDownloadURI");
  const batch = await call("get_uspto", {
    dataset: "trademark_decision",
    identifier: ["reexam1", "missing"],
  });
  expect(batch.items).toHaveLength(1);
  expect(batch.not_found).toEqual(["missing"]);
  await expect(
    call("get_uspto", { dataset: "trademark_decision", identifier: "missing" }),
  ).rejects.toThrow("was not found");
});

test("download_document fetches an administrative order and explains the rest", async () => {
  const pdf = await call("download_document", {
    source: "trademark_decision",
    identifier: "order1",
  });
  expect(pdf.content_type).toBe("application/pdf");
  expect(pdf.size).toBe(14);
  await expect(
    call("download_document", {
      source: "trademark_decision",
      identifier: "reexam1",
    }),
  ).rejects.toThrow("only 'Administrative' records have one");
});

test("get_uspto reads an office action found by the full-text search", async () => {
  const result = await call("get_uspto", {
    dataset: "office_action",
    identifier: "oa1",
  });
  expect(result.summary).toStartWith(
    "**Office action oa1** — application 17950760, type CTFR",
  );
  expect(result.items[0]?.officeActionText).toBe("The whole action text.");
  await expect(
    call("get_uspto", { dataset: "office_action", identifier: "nope" }),
  ).rejects.toThrow("search_uspto(dataset='office_actions')");
});

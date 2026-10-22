import { beforeAll, expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { unzipSync } from "fflate";
import {
  buildDataWebQuery,
  DataWebClient,
  dispositionFilename,
  EdisClient,
  HtsClient,
  IdsClient,
  jwtExpiry,
  USITC_USER_AGENT,
} from "../packages/client/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";
import { usitcTokenFromEnv } from "../packages/mcp/src/usitc.js";
import { type UsitcRecording, usitcRecording } from "./usitc-recordings.js";

let recording: UsitcRecording;
beforeAll(async () => {
  recording = await usitcRecording();
});

const jwt = (exp: number) =>
  `e30.${Buffer.from(JSON.stringify({ sub: "x", exp })).toString("base64url")}.sig`;
const FUTURE = jwt(Math.floor(Date.now() / 1000) + 3600);
const PAST = jwt(Math.floor(Date.now() / 1000) - 3600);

type Handler = (url: URL, request: Request) => Response | Promise<Response>;
function fakeFetch(handler: Handler) {
  const requests: Request[] = [];
  const fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    requests.push(request);
    return handler(new URL(request.url), request);
  }) as typeof globalThis.fetch;
  return { fetch, requests };
}
const xml = (body: string) =>
  new Response(body, { headers: { "content-type": "application/xml" } });
const doc = (id: number, type = "Order", date = "2025/07/16 00:00:00") =>
  `<document><id>${id}</id><documentType>${type}</documentType><documentTitle>Doc ${id}</documentTitle><securityLevel>Public</securityLevel><investigationNumber>337-1</investigationNumber><documentDate>${date}</documentDate><officialReceivedDate>${date}</officialReceivedDate><attachmentListUri>https://edis.usitc.gov/data/attachment/${id}</attachmentListUri></document>`;
const attachmentXml = (documentId: number, ids: number[]) =>
  `<results><attachments>${ids.map((id) => `<attachment><id>${id}</id><documentId>${documentId}</documentId><title>Att ${id}</title><fileSize>10</fileSize><pageCount>1</pageCount><downloadUri>https://edis.usitc.gov/data/download/${documentId}/${id}</downloadUri></attachment>`).join("")}</attachments></results>`;
const pdf = (id: string) =>
  new Response(new TextEncoder().encode(`%PDF-1.7 ${id}`), {
    headers: {
      "content-type": "application/pdf",
      "content-disposition": `attachment; filename="file-${id}.pdf"`,
    },
  });

// ---------------------------------------------------------------------------
// Recorded EDIS and HTS responses
// ---------------------------------------------------------------------------

test("EDIS investigation lookups parse every phase row", () => {
  const rows = recording.investigation.data;
  expect(rows.map((row) => row.investigation_phase)).toEqual([
    "Other1",
    "Violation",
  ]);
  expect(rows[1]).toMatchObject({
    investigation_number: "337-1380",
    investigation_status: "Inactive",
    investigation_type: "Sec 337",
    docket_number: "3706",
  });
  expect(String(rows[1]?.title)).toContain("Inv. No. 337-TA-1380");
  expect(recording.phase.data).toHaveLength(1);
  expect(recording.phase.data[0]?.investigation_phase).toBe("Violation");
  expect(recording.missing.data).toEqual([]);
  expect(recording.investigation.provenance.source_url).toBe(
    "https://edis.usitc.gov/data/investigation/337-1380",
  );
});

test("EDIS documents and attachments parse with integer ids and decoded titles", () => {
  const docs = recording.documents.data;
  // 337-1380 has 20 documents; a page holds up to 100.
  expect(docs).toHaveLength(20);
  expect(recording.emptyPage.data).toEqual([]);
  for (const document of docs) {
    expect(Number.isSafeInteger(document.id)).toBe(true);
    expect(document.investigation_number).toBe("337-1380");
  }
  // EDIS double-escapes apostrophes ("Nokia&amp;#39;s").
  expect(docs.map((d) => d.title).join(" ")).not.toContain("&#39;");
  expect(docs.find((d) => d.id === 856966)).toMatchObject({
    document_type: "Order",
    security_level: "Public",
    filed_by: "Cameron R. Elliot",
    document_date: "2025/07/16 00:00:00",
    action_jacket_control_number: null,
  });
  const attachments = recording.attachments.data;
  expect(attachments.map((a) => a.id)).toEqual([2404585, 2404616]);
  expect(attachments[0]).toMatchObject({
    document_id: 856966,
    file_size: 116283,
    page_count: 2,
    download_uri: "https://edis.usitc.gov/data/download/856966/2404585",
  });
});

test("HTS search keeps upstream fields and derives heading and chapter", () => {
  const hit = recording.hts.data.find((h) => h.hts_number === "3923.10.20.00");
  expect(hit).toMatchObject({
    heading: "3923",
    chapter: "39",
    general: "Free",
    units: ["kg"],
  });
  expect(recording.hts.data.length).toBeGreaterThan(10);
  expect(recording.export.entries[0]).toMatchObject({
    htsno: "0101",
    description: "Live horses, asses, mules and hinnies:",
  });
});

// ---------------------------------------------------------------------------
// Client behavior with synthetic responses
// ---------------------------------------------------------------------------

test("EDIS sends the programmatic user agent and a fresh token, but not an expired one", async () => {
  for (const [token, expectAuth] of [
    [FUTURE, true],
    [PAST, false],
  ] as const) {
    const site = fakeFetch(() => xml("<results><investigations/></results>"));
    const edis = new EdisClient({ token, fetch: site.fetch, retryLimit: 0 });
    await edis.listInvestigations({ investigationPhase: "Violation" });
    const request = site.requests[0] as Request;
    expect(request.headers.get("user-agent")).toBe(USITC_USER_AGENT);
    expect(request.headers.has("authorization")).toBe(expectAuth);
    // A phase without a number is a query filter, not dropped.
    expect(new URL(request.url).searchParams.get("investigationPhase")).toBe(
      "Violation",
    );
  }
  expect(jwtExpiry(PAST)).toBeLessThan(Date.now());
  expect(jwtExpiry("not-a-jwt")).toBeNull();
});

test("EDIS downloads need an unexpired token and read the filename", async () => {
  const site = fakeFetch((url) => pdf(url.pathname.split("/").pop() ?? ""));
  await expect(
    new EdisClient({ token: "", fetch: site.fetch }).downloadAttachment(1, 2),
  ).rejects.toMatchObject({ code: "AUTH_REQUIRED" });
  await expect(
    new EdisClient({ token: PAST, fetch: site.fetch }).downloadAttachment(1, 2),
  ).rejects.toMatchObject({ code: "AUTH_EXPIRED" });
  expect(site.requests).toHaveLength(0);
  const file = await new EdisClient({
    token: FUTURE,
    fetch: site.fetch,
  }).downloadAttachment(856966, 2404585);
  expect(file.filename).toBe("file-2404585.pdf");
  expect(file.content_type).toBe("application/pdf");
  expect(site.requests[0]?.headers.get("authorization")).toBe(
    `Bearer ${FUTURE}`,
  );
  expect(new URL(site.requests[0]?.url ?? "").pathname).toBe(
    "/data/download/856966/2404585",
  );
  expect(file.provenance.source_url).not.toContain(FUTURE);
  expect(dispositionFilename("attachment; filename*=UTF-8''a%20b.pdf")).toBe(
    "a b.pdf",
  );
  expect(dispositionFilename(null)).toBeNull();
});

test("EDIS rejects malformed responses and unsafe path segments", async () => {
  const html = fakeFetch(() => xml("<html><body>maintenance</body></html>"));
  await expect(
    new EdisClient({ fetch: html.fetch, token: "" }).listDocuments(),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  const badId = fakeFetch(() =>
    xml(
      "<results><documents><document><id>abc</id></document></documents></results>",
    ),
  );
  await expect(
    new EdisClient({ fetch: badId.fetch, token: "" }).listDocuments(),
  ).rejects.toThrow("not an integer");
  await expect(
    new EdisClient({ fetch: badId.fetch, token: "" }).listInvestigations({
      investigationNumber: "../download/1/2",
    }),
  ).rejects.toMatchObject({ code: "INVALID_INPUT" });
});

test("DataWeb fails closed, sends the query, and unwraps saved queries", async () => {
  await expect(
    new DataWebClient({ token: "" }).runReport({}),
  ).rejects.toMatchObject({ code: "AUTH_REQUIRED" });
  await expect(
    new DataWebClient({ token: PAST }).runReport({}),
  ).rejects.toMatchObject({ code: "AUTH_EXPIRED" });
  const site = fakeFetch(async (url, request) => {
    if (url.pathname.endsWith("/runReport")) {
      const body = (await request.json()) as Record<string, unknown>;
      expect(body.reportOptions).toEqual({
        tradeType: "Import",
        classificationSystem: "HTS",
      });
      return Response.json({
        dto: {
          tables: [{ row_groups: [{ rowsNew: [{}, {}] }, { rowsNew: [{}] }] }],
        },
      });
    }
    return Response.json({
      list: [{ id: 7, name: "Chips", createdDate: "2026-01-01" }],
    });
  });
  const dataweb = new DataWebClient({ token: FUTURE, fetch: site.fetch });
  const report = await dataweb.runReport(buildDataWebQuery());
  expect(report.dto.tables).toBeArray();
  expect(site.requests[0]?.headers.get("authorization")).toBe(
    `Bearer ${FUTURE}`,
  );
  expect(await dataweb.listSavedQueries()).toEqual([
    {
      id: 7,
      name: "Chips",
      createdDate: "2026-01-01",
      description: null,
      created_at: "2026-01-01",
    },
  ]);
});

test("buildDataWebQuery matches Python's build_dataweb_query", async () => {
  const cases = JSON.parse(
    await readFile(
      join(import.meta.dir, "fixtures", "usitc", "dataweb-query-parity.json"),
      "utf8",
    ),
  ) as { args: Record<string, unknown>; query: unknown }[];
  for (const { args, query } of cases)
    expect(
      buildDataWebQuery({
        ...(args.trade_type ? { tradeType: args.trade_type as string } : {}),
        ...(args.classification
          ? { classification: args.classification as string }
          : {}),
        ...(args.years ? { years: args.years as string[] } : {}),
        ...(args.timeline ? { timeline: args.timeline as string } : {}),
        ...(args.data_metrics
          ? { dataMetrics: args.data_metrics as string[] }
          : {}),
        ...(args.scale ? { scale: args.scale as string } : {}),
        ...(args.commodities
          ? { commodities: args.commodities as string[] }
          : {}),
        ...(args.granularity
          ? { granularity: args.granularity as string }
          : {}),
        ...(args.countries
          ? { countries: args.countries as { name: string; value: string }[] }
          : {}),
        ...(args.aggregate_countries === false
          ? { aggregateCountries: false }
          : {}),
        ...(args.aggregate_commodities === false
          ? { aggregateCommodities: false }
          : {}),
        ...(args.max_rows ? { maxRows: args.max_rows as string } : {}),
      }),
    ).toEqual(query as Record<string, unknown>);
});

test("IDS rows map Python's column names and keep the rest", async () => {
  const sample = await readFile(
    join(import.meta.dir, "fixtures", "usitc", "ids-sample.json"),
    "utf8",
  );
  const site = fakeFetch(
    () =>
      new Response(sample, { headers: { "content-type": "application/json" } }),
  );
  const ids = new IdsClient({ fetch: site.fetch });
  const { data } = await ids.listInvestigations();
  expect(data.length).toBeGreaterThan(0);
  for (const row of data) {
    expect(Number.isSafeInteger(row.investigation_id)).toBe(true);
    expect(row.investigation_number).toBeString();
    expect("Investigation ID" in row).toBe(false);
  }
  const bad = fakeFetch(() => Response.json({ rows: [] }));
  await expect(
    new IdsClient({ fetch: bad.fetch }).listInvestigations(),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});

test("tokens come from the variable or its _FILE companion", () => {
  expect(
    usitcTokenFromEnv("USITC_EDIS_TOKEN", { USITC_EDIS_TOKEN: " t " }),
  ).toBe("t");
  expect(
    usitcTokenFromEnv("USITC_EDIS_TOKEN", {
      USITC_EDIS_TOKEN: " ",
      USITC_EDIS_TOKEN_FILE: "/nonexistent/token",
    }),
  ).toBeUndefined();
});

// ---------------------------------------------------------------------------
// MCP tools
// ---------------------------------------------------------------------------

/** A fake EDIS: investigation 337-1 has three documents with two attachments each. */
function fakeEdis(documentCount = 3) {
  return fakeFetch((url) => {
    const path = url.pathname;
    if (path.startsWith("/data/investigation"))
      return xml(
        "<results><investigations><investigation><investigationNumber>337-1</investigationNumber><investigationPhase>Violation</investigationPhase><investigationStatus>Active</investigationStatus><investigationTitle>Certain Widgets</investigationTitle><investigationType>Sec 337</investigationType><docketNumber>1</docketNumber><documentListUri>https://edis.usitc.gov/data/document?investigationNumber=337-1</documentListUri></investigation></investigations></results>",
      );
    if (path === "/data/document") {
      const page = Number(url.searchParams.get("pageNumber") ?? 1);
      const docs =
        page === 1
          ? Array.from({ length: documentCount }, (_, i) =>
              doc(
                100 + i,
                i === 0 ? "Motion" : "Order",
                `2025/0${i + 1}/10 00:00:00`,
              ),
            ).join("")
          : "";
      return xml(`<results><documents>${docs}</documents></results>`);
    }
    const attachment = /^\/data\/attachment\/(\d+)$/.exec(path);
    if (attachment) {
      const id = Number(attachment[1]);
      return xml(attachmentXml(id, [id * 10, id * 10 + 1]));
    }
    const download = /^\/data\/download\/(\d+)\/(\d+)$/.exec(path);
    if (download) return pdf(`${download[1]}-${download[2]}`);
    return new Response("not found", { status: 404 });
  });
}

async function connect(edis?: EdisClient, toolset?: "curated") {
  const server = createServer({
    ...(toolset ? { toolset } : {}),
    clients: edis ? { edis } : {},
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    call: async <T = Record<string, unknown>>(
      name: string,
      args: Record<string, unknown>,
    ) => (await client.callTool<T>(name, args)).structuredContent as T,
    async close() {
      await client.close();
      await server.close();
    },
  };
}

test("EDIS tools are served only with an EDIS client; HTS, IDS and DataWeb always", async () => {
  const without = await connect();
  try {
    const names = (await without.client.listTools()).map((t) => t.name);
    expect(names).toContain("search_hts_tariffs");
    expect(names).toContain("run_dataweb_report");
    expect(names).toContain("list_ids_investigations");
    expect(names.filter((n) => n.includes("usitc"))).toEqual([]);
  } finally {
    await without.close();
  }
  const site = fakeEdis();
  const withEdis = await connect(
    new EdisClient({ token: FUTURE, fetch: site.fetch, retryLimit: 0 }),
  );
  try {
    const names = (await withEdis.client.listTools()).map((t) => t.name);
    for (const name of [
      "search_usitc_investigations",
      "get_usitc_investigation",
      "search_usitc_documents",
      "list_usitc_attachments",
      "download_usitc_investigation_documents",
      "download_usitc_attachment",
    ])
      expect(names).toContain(name);
  } finally {
    await withEdis.close();
  }
});

test("EDIS MCP tools return Python's lean stubs and strip token-gated URLs", async () => {
  const site = fakeEdis();
  const mcp = await connect(
    new EdisClient({ token: FUTURE, fetch: site.fetch, retryLimit: 0 }),
  );
  try {
    const search = await mcp.call<{ items: Record<string, unknown>[] }>(
      "search_usitc_investigations",
      { investigation_number: "337-1" },
    );
    expect(Object.keys(search.items[0] ?? {})).toEqual([
      "investigation_number",
      "title",
      "investigation_status",
      "investigation_phase",
      "investigation_type",
      "docket_number",
    ]);
    const got = await mcp.call<{
      items: Record<string, unknown>[];
      not_found: string[];
      summary: string;
      provenance: { as_of_status?: string; source_name: string };
    }>("get_usitc_investigation", { investigation_number: ["337-1"] });
    expect(got.items[0]?.title).toBe("Certain Widgets");
    expect(got.provenance.as_of_status).toBe("Active");
    expect(got.provenance.source_name).toBe(
      "U.S. International Trade Commission (USITC)",
    );
    const docs = await mcp.call<{
      items: Record<string, unknown>[];
      more_available: boolean;
    }>("search_usitc_documents", { investigation_number: "337-1", full: true });
    expect(docs.items).toHaveLength(3);
    expect(docs.items[0]).not.toHaveProperty("attachment_list_uri");
    expect(docs.more_available).toBe(false);
    const dated = await mcp.call<{ items: Record<string, unknown>[] }>(
      "search_usitc_documents",
      { investigation_number: "337-1", date_from: "2025-02-01" },
    );
    expect(dated.items.map((d) => d.id)).toEqual([101, 102]);
    await expect(
      mcp.call("search_usitc_documents", { date_from: "Feb 2025" }),
    ).rejects.toThrow("YYYY-MM-DD");
    const attachments = await mcp.call<{ items: Record<string, unknown>[] }>(
      "list_usitc_attachments",
      { document_id: 100 },
    );
    expect(attachments.items.map((a) => a.id)).toEqual([1000, 1001]);
    expect(attachments.items[0]).not.toHaveProperty("download_uri");
  } finally {
    await mcp.close();
  }
});

test("investigation downloads filter, cap at 25 attachments, and zip several", async () => {
  const site = fakeEdis();
  const mcp = await connect(
    new EdisClient({ token: FUTURE, fetch: site.fetch, retryLimit: 0 }),
  );
  try {
    const single = await mcp.call<{ filename: string; file_path: string }>(
      "download_usitc_attachment",
      { document_id: 100, attachment_id: 1000 },
    );
    expect(single.filename).toBe("document-100_att1000.pdf");
    const zipped = await mcp.call<{ filename: string; file_path: string }>(
      "download_usitc_investigation_documents",
      { investigation_number: "337-1", document_types: ["Order"] },
    );
    expect(zipped.filename).toBe("337-1_documents.zip");
    const files = unzipSync(new Uint8Array(await readFile(zipped.file_path)));
    expect(Object.keys(files).sort()).toEqual([
      "337-1_101_att1010.pdf",
      "337-1_101_att1011.pdf",
      "337-1_102_att1020.pdf",
      "337-1_102_att1021.pdf",
      "manifest.json",
    ]);
    const manifest = JSON.parse(
      new TextDecoder().decode(files["manifest.json"]),
    ) as { items: { item_id: string; document_type: string }[] };
    expect(manifest.items.map((i) => i.document_type)).toEqual([
      "Order",
      "Order",
      "Order",
      "Order",
    ]);
    const picked = await mcp.call<{ filename: string }>(
      "download_usitc_investigation_documents",
      { investigation_number: "337-1", item_ids: ["100/attachments/1000"] },
    );
    expect(picked.filename).toBe("337-1_100_att1000.pdf");
    await expect(
      mcp.call("download_usitc_investigation_documents", {
        investigation_number: "337-1",
        item_ids: ["100-1000"],
      }),
    ).rejects.toThrow("<doc_id>/attachments/<att_id>");
  } finally {
    await mcp.close();
  }
  const big = fakeEdis(13);
  const capped = await connect(
    new EdisClient({ token: FUTURE, fetch: big.fetch, retryLimit: 0 }),
  );
  try {
    await expect(
      capped.call("download_usitc_investigation_documents", {
        investigation_number: "337-1",
      }),
    ).rejects.toThrow("26 attachments matching the filters; max 25");
    expect(
      big.requests.some((r) =>
        new URL(r.url).pathname.startsWith("/data/download"),
      ),
    ).toBe(false);
  } finally {
    await capped.close();
  }
});

test("the curated facade routes forum='usitc' and the usitc download sources", async () => {
  const site = fakeEdis();
  const mcp = await connect(
    new EdisClient({ token: FUTURE, fetch: site.fetch, retryLimit: 0 }),
    "curated",
  );
  try {
    const got = await mcp.call<{ items: Record<string, unknown>[] }>(
      "get_litigation",
      { forum: "usitc", identifier: "337-1" },
    );
    expect(got.items[0]?.investigation_number).toBe("337-1");
    await expect(
      mcp.call("download_document", { source: "usitc_attachment" }),
    ).rejects.toThrow("requires document_id and attachment_id");
    const file = await mcp.call<{ filename: string }>("download_document", {
      source: "usitc_attachment",
      document_id: 100,
      attachment_id: 1001,
    });
    expect(file.filename).toBe("document-100_att1001.pdf");
    const bulk = await mcp.call<{ filename: string }>("download_document", {
      source: "usitc_investigation",
      identifier: "337-1",
      after: "2025-03-01",
    });
    expect(bulk.filename).toBe("337-1_documents.zip");
    const docs = await mcp.call<{ items: unknown[] }>(
      "search_usitc_documents",
      {
        investigation_number: "337-1",
      },
    );
    expect(docs.items).toHaveLength(3);
  } finally {
    await mcp.close();
  }
});

test("HTS and DataWeb tools work through MCP", async () => {
  const hts = fakeFetch(() =>
    Response.json([
      { htsno: "8542.31.00.01", description: "Processors", general: "Free" },
    ]),
  );
  const dataweb = fakeFetch(() => Response.json({ dto: { tables: [] } }));
  const server = createServer({
    clients: {
      hts: new HtsClient({ fetch: hts.fetch }),
      dataweb: new DataWebClient({ token: "", fetch: dataweb.fetch }),
    },
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = (
      await client.callTool<{ items: Record<string, unknown>[] }>(
        "search_hts_tariffs",
        { query: "processor" },
      )
    ).structuredContent;
    expect(result?.items).toEqual([
      {
        hts_number: "8542.31.00.01",
        description: "Processors",
        heading: "8542",
        chapter: "85",
      },
    ]);
    await expect(
      client.callTool("run_dataweb_report", { years: "2024" }),
    ).rejects.toThrow("USITC_DATAWEB_TOKEN is required");
    expect(dataweb.requests).toHaveLength(0);
  } finally {
    await client.close();
    await server.close();
  }
});

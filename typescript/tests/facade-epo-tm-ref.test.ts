import { expect, test } from "bun:test";
import {
  EpoOpsClient,
  FeesClient,
  TrademarkAssignmentClient,
  TrademarkSearchClient,
  TsdrClient,
} from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";

type Envelope = {
  summary: string;
  items?: Record<string, unknown>[];
  details?: Record<string, unknown>;
  next_cursor?: string | null;
  more_available?: boolean;
  not_found?: string[];
  source_metadata?: Record<string, unknown>;
};
const wpd = (body: string) =>
  `<ops:world-patent-data xmlns="http://www.epo.org/exchange" xmlns:ops="http://ops.epo.org" xmlns:reg="http://www.epo.org/register">${body}</ops:world-patent-data>`;
const searchXml = (begin: number, end: number) =>
  wpd(
    `<ops:biblio-search total-result-count="60"><ops:query>q</ops:query><ops:range begin="${begin}" end="${end}"/><ops:search-result>${Array.from(
      { length: end - begin + 1 },
      (_, i) =>
        `<ops:publication-reference family-id="${Math.floor((begin + i) / 2)}"><document-id document-id-type="docdb"><country>EP</country><doc-number>${begin + i}</doc-number><kind>A1</kind></document-id></ops:publication-reference>`,
    ).join("")}</ops:search-result></ops:biblio-search>`,
  );
const biblioXml = (number: string) =>
  wpd(
    `<exchange-documents><exchange-document family-id="7"><bibliographic-data><publication-reference><document-id document-id-type="docdb"><country>EP</country><doc-number>${number}</doc-number><kind>A1</kind></document-id></publication-reference><invention-title lang="en">Widget</invention-title><parties><applicants><applicant><applicant-name><name>ACME</name></applicant-name></applicant></applicants></parties></bibliographic-data></exchange-document></exchange-documents>`,
  );

function epoClient() {
  const paths: string[] = [];
  const fetcher = (async (input, init) => {
    const url = new URL(new Request(input, init).url);
    if (url.pathname.endsWith("/accesstoken"))
      return Response.json({ access_token: "t", expires_in: 1200 });
    paths.push(decodeURIComponent(url.pathname + url.search));
    const path = url.pathname;
    if (path.includes("EP404"))
      return new Response(
        `<fault xmlns="http://ops.epo.org"><code>SERVER.EntityNotFound</code><message>No</message></fault>`,
        { status: 404 },
      );
    if (path.endsWith("/published-data/search")) {
      const [begin, end] = (url.searchParams.get("Range") ?? "1-1")
        .split("-")
        .map(Number);
      return new Response(searchXml(begin ?? 1, Math.min(end ?? 1, 60)));
    }
    if (path.endsWith("/biblio"))
      return new Response(biblioXml(/\/EP(\d+)/.exec(path)?.[1] ?? "1"));
    if (path.endsWith("/upp"))
      return new Response(wpd("<reg:register-documents/>"));
    if (path.endsWith("/classification/cpc/search"))
      return new Response(
        wpd(
          `<ops:classification-search total-result-count="30"><ops:search-result><ops:classification-statistics classification-symbol="H04L9/32" percentage="9.5"><class-title xmlns="http://www.epo.org/cpcexport"><title-part><text>verifying</text></title-part></class-title></ops:classification-statistics></ops:search-result></ops:classification-search>`,
        ),
      );
    if (path.includes("/classification/cpc/"))
      return new Response(
        wpd(
          `<class-scheme xmlns="http://www.epo.org/cpcexport" scheme-type="cpc"><classification-item level="8"><classification-symbol>H04L9/32</classification-symbol><class-title><title-part><text>verifying</text></title-part></class-title></classification-item></class-scheme>`,
        ),
      );
    if (path.includes("/classification/map/"))
      return new Response(
        wpd(
          `<ops:mappings inputSchema="CPC" outputSchema="IPC"><ops:mapping><ops:cpc>H04L9/32</ops:cpc><ops:ipc>H04L9/32</ops:ipc></ops:mapping></ops:mappings>`,
        ),
      );
    return new Response(wpd(""));
  }) as typeof fetch;
  return {
    paths,
    client: new EpoOpsClient({
      apiKey: "k",
      apiSecret: "s",
      retryLimit: 0,
      fetch: fetcher,
    }),
  };
}
function trademarkSearch() {
  const bodies: unknown[] = [];
  const client = new TrademarkSearchClient({
    token: { token: "opaque", expires: Date.now() / 1000 + 86400 },
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      const body = await new Request(input, init).json();
      bodies.push(body);
      const serial = JSON.stringify(body).includes("00000000")
        ? null
        : "97123456";
      return Response.json({
        hits: {
          totalValue: serial ? 1 : 0,
          hits: serial
            ? [
                {
                  id: serial,
                  source: {
                    alive: true,
                    serialNumber: serial,
                    registrationNumber: "1234567",
                    wordmark: "WIDGET",
                    ownerName: ["Acme Inc"],
                    filedDate: "2020-01-02",
                    registrationDate: "2021-03-04",
                  },
                },
              ]
            : [],
        },
      });
    }) as unknown as typeof fetch,
  });
  return { client, bodies };
}
function tsdrClient() {
  const paths: string[] = [];
  const client = new TsdrClient({
    apiKey: "synthetic",
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(new Request(input, init).url);
      paths.push(url.pathname);
      if (url.pathname.includes("99999999"))
        return new Response("", { status: 404 });
      if (url.pathname.includes("casedocs"))
        return new Response(
          "<DocumentList><Document><SerialNumber>97123456</SerialNumber><DocumentTypeCode>NOA</DocumentTypeCode><ScanDateTime>2020-01-02T03:04:05</ScanDateTime><MailRoomDate>2020-01-02</MailRoomDate><DocumentTypeDescriptionText>Notice</DocumentTypeDescriptionText><TotalPageQuantity>2</TotalPageQuantity></Document></DocumentList>",
        );
      return Response.json({
        trademarks: [{ status: { markElement: "SYNTHETIC" } }],
      });
    }) as unknown as typeof fetch,
  });
  return { client, paths };
}
function trademarkAssignments() {
  const bodies: unknown[] = [];
  const client = new TrademarkAssignmentClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      bodies.push(await new Request(input, init).json());
      return Response.json({
        successResponse: {
          totalRows: 1,
          data: [
            {
              reelNumber: 9006,
              frameNumber: "93",
              assignorExecutionDate: "2020-01-01",
              assignors: [{ assignorName: "OLD CO" }],
              assignees: ["NEW CO"],
              noOfProperties: 1,
              properties: [
                {
                  serialNumber: 97123456,
                  registrationNumber: 1234567,
                  mark: "WIDGET",
                },
              ],
            },
          ],
        },
      });
    }) as unknown as typeof fetch,
  });
  return { client, bodies };
}
function feesClient() {
  return new FeesClient({
    retryLimit: 0,
    fetch: (async () =>
      Response.json([
        {
          data: { feeCode: "001", feeDescription: "Filing fee", amount: null },
          children: [
            {
              data: {
                feeCode: null,
                feeDescription: "online",
                amount: "135,00",
              },
              children: [],
            },
          ],
        },
        ...Array.from({ length: 18 }, (_, i) => ({
          data: {
            feeCode: String(33 + i).padStart(3, "0"),
            feeDescription: `Renewal fee for the ${i + 3}th year`,
            amount: "1.000,00",
          },
          children: [],
        })),
        {
          data: {
            feeCode: "732",
            feeDescription: "Renewal fee for the 2nd year",
            amount: "35,00",
          },
          children: [],
        },
      ])) as unknown as typeof fetch,
  });
}

async function connect(
  clients: Parameters<typeof createServer>[0] extends infer O
    ? O extends { clients?: infer C }
      ? C
      : never
    : never,
) {
  const server = createServer({ toolset: "curated", clients });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    call: async (name: string, args: Record<string, unknown>) =>
      (await client.callTool<Envelope>(name, args))
        .structuredContent as Envelope,
    client,
    async close() {
      await client.close();
      await server.close();
    },
  };
}

test("curated toolset lists the EPO, trademark and reference facade tools", async () => {
  const mcp = await connect({ epoOps: epoClient().client });
  try {
    const names = (await mcp.client.listTools()).map((tool) => tool.name);
    expect(names).toEqual(
      expect.arrayContaining([
        "get_epo",
        "search_epo",
        "search_trademarks",
        "get_trademark",
        "search_trademark_assignments",
        "classify_cpc",
        "get_fees",
        "copyright",
      ]),
    );
    // The full toolset's names stay out of the curated surface.
    expect(names).not.toContain("search_cpc");
    expect(names).not.toContain("lookup_fee");
  } finally {
    await mcp.close();
  }
});

test("get_epo routes every view and batch-reports not-found members", async () => {
  const epo = epoClient();
  const mcp = await connect({ epoOps: epo.client });
  try {
    for (const view of [
      "biblio",
      "citations",
      "equivalents",
      "family",
      "fulltext",
      "legal_events",
      "procedural_steps",
      "register_biblio",
      "register_events",
    ])
      await mcp.call("get_epo", { view, identifier: "EP1A1" });
    expect(epo.paths).toEqual([
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/biblio",
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/biblio",
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/equivalents",
      "/3.2/rest-services/family/publication/docdb/EP1A1",
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/claims",
      "/3.2/rest-services/legal/publication/docdb/EP1A1",
      "/3.2/rest-services/register/publication/epodoc/EP1A1/procedural-steps",
      "/3.2/rest-services/register/publication/epodoc/EP1A1/biblio",
      "/3.2/rest-services/register/publication/epodoc/EP1A1/events",
    ]);
    const single = await mcp.call("get_epo", {
      view: "biblio",
      identifier: "ep 5 a1",
    });
    expect(single.summary).toStartWith("**EPO EP5A1** — Widget");
    expect(single.items?.[0]).toHaveProperty("documents");
    const batch = await mcp.call("get_epo", {
      view: "biblio",
      identifier: ["EP1A1", "EP404A1"],
    });
    expect(batch.items).toHaveLength(1);
    expect(batch.not_found).toEqual(["EP404A1"]);
    await expect(
      mcp.client.callTool("get_epo", { view: "biblio", identifier: "EP404A1" }),
    ).rejects.toThrow("found no matching record");
  } finally {
    await mcp.close();
  }
});

test("get_epo single-number views reject lists and report an empty unitary record", async () => {
  const epo = epoClient();
  const mcp = await connect({ epoOps: epo.client });
  try {
    for (const view of ["family_intelligence", "unitary_status"])
      await expect(
        mcp.client.callTool("get_epo", {
          view,
          identifier: ["EP1A1", "EP2A1"],
        }),
      ).rejects.toThrow("single");
    const upp = await mcp.call("get_epo", {
      view: "unitary_status",
      identifier: "EP1000000",
    });
    expect(upp.details).toEqual({});
    expect(upp.summary).toContain("no unitary-effect record on file");
    expect(epo.paths.at(-1)).toBe(
      "/3.2/rest-services/register/publication/epodoc/EP1000000/upp",
    );
  } finally {
    await mcp.close();
  }
});

test("search_epo applies jurisdiction recipes, the query alias and range cursors", async () => {
  const epo = epoClient();
  const mcp = await connect({ epoOps: epo.client });
  try {
    const first = await mcp.call("search_epo", {
      query: "ta=battery",
      jurisdiction: "DE",
      range_begin: 1,
      range_end: 10,
    });
    expect(first.items).toHaveLength(10);
    expect(first.items?.[0]).toEqual({
      publication_number: "EP1A1",
      application_number: null,
      publication_date: null,
      country: "EP",
      kind: "A1",
      family_id: "0",
    });
    expect(first.more_available).toBe(true);
    const second = await mcp.call("search_epo", {
      cql_query: "ta=battery",
      next_cursor: first.next_cursor,
    });
    expect(second.items?.[0]?.publication_number).toBe("EP11A1");
    expect(epo.paths).toEqual([
      "/3.2/rest-services/published-data/search?q=(ta=battery)+and+pn=DE&Range=1-10",
      "/3.2/rest-services/published-data/search?q=ta=battery&Range=11-20",
    ]);
    const families = await mcp.call("search_epo", {
      cql_query: "ta=battery",
      group_by: "family",
      range_end: 4,
    });
    expect(families.items?.map((item) => item.member_count)).toEqual([1, 2, 1]);
    await expect(mcp.client.callTool("search_epo", {})).rejects.toThrow(
      "requires cql_query",
    );
    await expect(
      mcp.client.callTool("search_epo", {
        cql_query: "x",
        group_by: "country",
      }),
    ).rejects.toThrow("group_by");
  } finally {
    await mcp.close();
  }
});

test("EPO and CPC branches explain missing OPS credentials", async () => {
  const saved = { ...process.env };
  for (const name of [
    "EPO_OPS_API_KEY",
    "EPO_OPS_API_SECRET",
    "EPO_API_KEY",
    "EPO_API_SECRET",
  ])
    delete process.env[name];
  const mcp = await connect({});
  try {
    await expect(
      mcp.client.callTool("get_epo", { view: "biblio", identifier: "EP1A1" }),
    ).rejects.toThrow("EPO OPS is not enabled on this server");
    await expect(
      mcp.client.callTool("search_epo", { cql_query: "ta=x" }),
    ).rejects.toThrow("EPO_OPS_API_KEY");
    await expect(
      mcp.client.callTool("classify_cpc", {
        mode: "lookup",
        symbol: "H04L9/32",
      }),
    ).rejects.toThrow("EPO OPS is not enabled");
  } finally {
    await mcp.close();
    Object.assign(process.env, saved);
  }
});

test("classify_cpc routes search, lookup and map, and rejects USCLS", async () => {
  const epo = epoClient();
  const mcp = await connect({ epoOps: epo.client });
  try {
    const search = await mcp.call("classify_cpc", {
      mode: "search",
      query: "battery",
      range_begin: 1,
      range_end: 5,
    });
    expect(search.items).toEqual([
      { symbol: "H04L9/32", title: "verifying", parent_symbol: "H04L9/00" },
    ]);
    expect(search.more_available).toBe(true);
    const lookup = await mcp.call("classify_cpc", {
      mode: "lookup",
      symbol: "h04l9/32",
    });
    expect(lookup.summary).toBe("**CPC H04L9/32** — verifying (level 8).");
    const map = await mcp.call("classify_cpc", {
      mode: "map",
      symbol: "H04L9/32",
    });
    expect(map.summary).toBe("**CPC mapping H04L9/32** (CPC → IPC): H04L9/32.");
    expect(epo.paths).toEqual([
      "/3.2/rest-services/classification/cpc/search?q=battery",
      "/3.2/rest-services/classification/cpc/H04L9/32",
      "/3.2/rest-services/classification/map/cpc/H04L9/32/ipc",
    ]);
    await expect(
      mcp.client.callTool("classify_cpc", {
        mode: "map",
        symbol: "H04L9/32",
        to_scheme: "uscls",
      }),
    ).rejects.toThrow("USCLS");
    await expect(
      mcp.client.callTool("classify_cpc", { mode: "search" }),
    ).rejects.toThrow("requires query");
  } finally {
    await mcp.close();
  }
});

test("trademark search, records and assignments use the Python lean stubs", async () => {
  const search = trademarkSearch();
  const assignments = trademarkAssignments();
  const mcp = await connect({
    trademarkSearch: search.client,
    trademarkAssignments: assignments.client,
  });
  try {
    const hits = await mcp.call("search_trademarks", { query: "widget" });
    expect(hits.items?.[0]).toEqual({
      serial_number: "97123456",
      registration_number: "1234567",
      wordmark: "WIDGET",
      owner_name: ["Acme Inc"],
      filing_date: "2020-01-02",
      registration_date: "2021-03-04",
      status: "live",
    });
    await mcp.call("search_trademarks", { query: "Acme", search_by: "owner" });
    expect(JSON.stringify(search.bodies[1])).toContain("ownerName");
    await expect(
      mcp.client.callTool("search_trademarks", {
        query: "x",
        search_by: "goods_services",
        paginate_all: true,
      }),
    ).rejects.toThrow("paginate_all");
    const records = await mcp.call("get_trademark", {
      identifier: ["97123456", "1234567", "00000000"],
    });
    expect(records.items).toHaveLength(2);
    expect(records.not_found).toEqual(["00000000"]);
    expect(JSON.stringify(search.bodies.at(-2))).toContain(
      "registrationNumber",
    );
    const one = await mcp.call("get_trademark", { identifier: "97123456" });
    expect(one.summary).toContain(
      "**US trademark 97123456** — WIDGET (owner: Acme Inc)",
    );
    await expect(
      mcp.client.callTool("get_trademark", { identifier: "12345" }),
    ).rejects.toThrow("expected 8 (serial) or 6-7 (registration)");
    const assigned = await mcp.call("search_trademark_assignments", {
      query: "NEW CO",
      by: "assignee",
    });
    expect(assigned.items?.[0]).toEqual({
      reel_frame: "9006/93",
      assignor: "OLD CO",
      assignee: "NEW CO",
      assignor_execution_date: "2020-01-01",
      number_of_properties: 1,
      serial_number: 97123456,
      registration_number: 1234567,
      mark: "WIDGET",
    });
    expect(JSON.stringify(assignments.bodies[0])).toContain("assigneeName");
    await expect(
      mcp.client.callTool("search_trademark_assignments", {
        query: "x",
        by: "owner",
      }),
    ).rejects.toThrow("`by` must be one of");
  } finally {
    await mcp.close();
  }
});

test("TSDR views route by facet and require a TSDR key", async () => {
  const tsdr = tsdrClient();
  const mcp = await connect({ tsdr: tsdr.client });
  try {
    const status = await mcp.call("get_trademark", {
      identifier: ["97123456", "99999999"],
      view: "status",
    });
    expect(status.items).toHaveLength(1);
    expect(status.not_found).toEqual(["99999999"]);
    const documents = await mcp.call("get_trademark", {
      identifier: "97123456",
      view: "documents",
    });
    expect(documents.items?.[0]).toMatchObject({
      docType: "NOA",
      pageCount: 2,
    });
    await expect(
      mcp.client.callTool("get_trademark", {
        identifier: ["97123456"],
        view: "documents",
      }),
    ).rejects.toThrow("single serial number");
    const updated = await mcp.call("get_trademark", {
      identifier: "97123456",
      view: "last_update",
    });
    expect(updated.items?.[0]).toHaveProperty("serialNumber", "97123456");
    expect(tsdr.paths).toContain("/ts/cd/casedocs/sn97123456/info");
  } finally {
    await mcp.close();
  }
  const saved = process.env.USPTO_TSDR_API_KEY;
  delete process.env.USPTO_TSDR_API_KEY;
  const bare = await connect({});
  try {
    await expect(
      bare.client.callTool("get_trademark", {
        identifier: "97123456",
        view: "status",
      }),
    ).rejects.toThrow("TSDR is not enabled on this server (USPTO_TSDR_API_KEY");
  } finally {
    await bare.close();
    if (saved !== undefined) process.env.USPTO_TSDR_API_KEY = saved;
  }
});

test("get_fees covers schedule, lookup and jurisdictions, and names unported offices", async () => {
  const mcp = await connect({ fees: feesClient() });
  try {
    const schedule = await mcp.call("get_fees", {
      mode: "schedule",
      jurisdiction: "EPO",
    });
    expect(schedule.summary).toContain(
      "effective date not published by the office",
    );
    expect(schedule.details).toMatchObject({ key: "EP/EPO/patent" });
    const lookup = await mcp.call("get_fees", {
      mode: "lookup",
      jurisdiction: "EP",
      category: "renewal",
      year: 10,
    });
    expect(lookup.items).toEqual([
      expect.objectContaining({ code: "040", amount: "1000.00", year: 10 }),
    ]);
    expect(lookup.source_metadata).toMatchObject({ office_code: "EPO" });
    expect(lookup.source_metadata).not.toHaveProperty("fees");
    const none = await mcp.call("get_fees", {
      mode: "lookup",
      jurisdiction: "EPO",
      category: "renewal",
      year: 25,
    });
    expect(none.summary).toContain(
      "No matching fees found. Recurring-fee coverage: complete",
    );
    const list = await mcp.call("get_fees", { mode: "jurisdictions" });
    expect(list.items?.map((item) => item.key)).toEqual([
      "EP/EPO/patent",
      "UP/EPO-UP/patent",
    ]);
    expect(list.summary).toContain("Not yet ported: USPTO patent");
    await expect(
      mcp.client.callTool("get_fees", {
        mode: "schedule",
        jurisdiction: "USPTO",
      }),
    ).rejects.toThrow("not yet ported");
    await expect(
      mcp.client.callTool("get_fees", {
        mode: "lookup",
        jurisdiction: "EPO",
        tier: "huge",
      }),
    ).rejects.toThrow("unknown tier");
    await expect(
      mcp.client.callTool("get_fees", {
        mode: "lookup",
        jurisdiction: "EPO",
        refresh: true,
      }),
    ).rejects.toThrow("refresh");
    await expect(
      mcp.client.callTool("get_fees", { mode: "lookup" }),
    ).rejects.toThrow("requires jurisdiction");
  } finally {
    await mcp.close();
  }
});

import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Client } from "@prefecthq/fastmcp-ts/client";
import {
  ApiError,
  canonicalUpcCaseId,
  parseUpcDecisionsPage,
  parseUpcDivisions,
  parseUpcLanguages,
  UPC_DECISIONS_ORIGIN,
  UpcDecisionSchema,
  UpcDecisionsClient,
} from "../packages/client/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";

/**
 * The UPC listing changes daily and now sits behind a Cloudflare challenge,
 * so, like the Python tests, these use an inline Drupal Views fixture (the
 * same rows as tests/upc_decisions/test_parser.py) and a stub fetch.
 */
const LISTING = `<!DOCTYPE html><html><body>
<table>
  <tbody>
    <tr>
      <td headers="view-field-judgement-application-no-1-table-column">
        UPC_CFI_1747/2025<br/>UPC_CFI_1747/2025<br/>
        <a href="/en/node/183235" class="btn btn--compact btn--primary">Full Details</a>
      </td>
      <td headers="view-field-location-table-column">Düsseldorf (DE) Local Division</td>
      <td headers="view-field-upc-case-type-table-column">Application for provisional measures</td>
      <td headers="view-field-judgement-parties-long-table-column">Align Technology, Inc. <br/>v.<br/>Angelalign France Technology SASU a. o.</td>
      <td headers="view-field-upc-document-table-column">
        <div class="item-list"><ul><li><article class="media media--type-cms-api-document">
          <a href="/sites/default/files/files/api_order/Final%20Order_UPC_CFI_1747_2025.pdf">Final Order</a>
        </article></li></ul></div>
      </td>
    </tr>
    <tr>
      <td headers="view-field-judgement-application-no-1-table-column">
        UPC-CFI-478/2025<br/>UPC-CFI-478/2025<br/>
        <a href="/en/node/183250" class="btn btn--compact btn--primary">Full Details</a>
      </td>
      <td headers="view-field-location-table-column">The Hague (NL) Local Division</td>
      <td headers="view-field-upc-case-type-table-column">Infringement Action</td>
      <td headers="view-field-judgement-parties-long-table-column">Avient Protective Materials B.V. <br/>v.<br/>Xingi Technology Co., Ltd et al</td>
      <td headers="view-field-upc-document-table-column">
        <a href="/sites/default/files/files/api_order/CFI-478-2025-decision.pdf">Decision</a>
        <a href="/sites/default/files/files/api_order/CFI-478-2025-decision.pdf">Decision (duplicate)</a>
      </td>
    </tr>
    <tr>
      <td headers="view-field-judgement-application-no-1-table-column">
        UPC-COA-0000053/2026<br/>UPC-COA-0000053/2026<br/>
        <a href="/en/node/183265" class="btn btn--compact btn--primary">Full Details</a>
      </td>
      <td headers="view-field-location-table-column">Luxembourg (LU)</td>
      <td headers="view-field-upc-case-type-table-column">Request for a discretionary review (RoP 220.3)</td>
      <td headers="view-field-judgement-parties-long-table-column">Huawei Technologies Co. Ltd. <br/>v.<br/>Quinn Emanuel Urquhart &amp; Sullivan, LLP</td>
      <td headers="view-field-upc-document-table-column">
        <a href="https://www.unifiedpatentcourt.org/sites/default/files/files/api_order/CoA-53-2026.pdf">Order</a>
      </td>
    </tr>
    <tr>
      <td headers="view-field-judgement-application-no-1-table-column">
        ACT_551054/2023<br/>UPC_CFI_159/2023<br/>
        <a href="/en/node/100001" class="btn btn--compact btn--primary">Full Details</a>
      </td>
      <td headers="view-field-location-table-column">Stockholm (SE) - Seat of the Regional Division</td>
      <td headers="view-field-upc-case-type-table-column">Infringement Action</td>
      <td headers="view-field-judgement-parties-long-table-column">Edwards Lifesciences Corporation<br/>v.<br/>Meril Life Sciences Pvt Limited</td>
      <td headers="view-field-upc-document-table-column">
        <a href="/sites/default/files/files/api_order/551054-2023%20Final%20order.pdf">Final order</a>
      </td>
    </tr>
    <tr>
      <td headers="view-field-judgement-application-no-1-table-column">
        UPC_CFI_1747/2025<br/><a href="/en/node/183236" class="btn btn--primary">Full Details</a>
      </td>
    </tr>
  </tbody>
</table>
<nav class="pager"><ul class="pager__items js-pager__items">
  <li class="pager__item is-active"><a href="?page=0">1</a></li>
  <li class="pager__item"><a href="?page=1">2</a></li>
  <li class="pager__item pager__item--last"><a href="?page=37">Last page</a></li>
</ul></nav>
<select name="proceedings_lang">
  <option value="All">All</option>
  <option value="33">English</option>
  <option value="34">French</option>
  <option value="35">German</option>
</select>
<select name="division_1">
  <option value="All">All</option>
  <option value="125">Luxembourg (LU)</option>
  <option value="134">Düsseldorf (DE) Local Division</option>
</select>
<select name="division_2">
  <option value="134">Düsseldorf (DE) Local Division</option>
  <option value="140">Milan (IT) Central Division</option>
</select>
</body></html>`;

const CHALLENGE =
  '<!DOCTYPE html><html><head><title>Just a moment...</title></head><body><script src="https://challenges.cloudflare.com/x.js"></script></body></html>';

function stubSite(body = LISTING, status = 200) {
  const urls: URL[] = [];
  const client = new UpcDecisionsClient({
    useCache: false,
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) => {
      urls.push(new URL(input instanceof Request ? input.url : input));
      return new Response(body, {
        status,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }) as typeof fetch,
  });
  return { client, urls };
}

test("the listing parses as Python's parser does", () => {
  const { hits, total_pages } = parseUpcDecisionsPage(LISTING);
  expect(total_pages).toBe(38);
  expect(hits.map((hit) => hit.case_id)).toEqual([
    "UPC_CFI_1747/2025",
    "UPC_CFI_478/2025",
    "UPC_CoA_0000053/2026",
    "ACT_551054/2023",
  ]);
  for (const hit of hits) UpcDecisionSchema.parse(hit);
  expect(hits[0]).toEqual({
    case_id: "UPC_CFI_1747/2025",
    raw_references: ["UPC_CFI_1747/2025", "UPC_CFI_1747/2025"],
    detail_url: `${UPC_DECISIONS_ORIGIN}/en/node/183235`,
    court: "Düsseldorf (DE) Local Division",
    type_of_action: "Application for provisional measures",
    parties: [
      "Align Technology, Inc.",
      "Angelalign France Technology SASU a. o.",
    ],
    pdf_urls: [
      `${UPC_DECISIONS_ORIGIN}/sites/default/files/files/api_order/Final%20Order_UPC_CFI_1747_2025.pdf`,
    ],
  });
  expect(hits[1]?.pdf_urls).toHaveLength(1);
  expect(hits[2]?.parties).toEqual([
    "Huawei Technologies Co. Ltd.",
    "Quinn Emanuel Urquhart & Sullivan, LLP",
  ]);
  expect(hits[2]?.pdf_urls[0]).toBe(
    "https://www.unifiedpatentcourt.org/sites/default/files/files/api_order/CoA-53-2026.pdf",
  );
  expect(hits[3]?.raw_references).toEqual([
    "ACT_551054/2023",
    "UPC_CFI_159/2023",
  ]);
});

test("case ids canonicalize like Python's helper", () => {
  expect(canonicalUpcCaseId("UPC-COA-35/2026")).toBe("UPC_CoA_35/2026");
  expect(canonicalUpcCaseId("UPC_CFI_0001695/2025")).toBe(
    "UPC_CFI_0001695/2025",
  );
  expect(canonicalUpcCaseId("ACT_12345/2024")).toBe("ACT_12345/2024");
  expect(canonicalUpcCaseId(" not-a-case-id ")).toBe("not-a-case-id");
});

test("an empty table is one empty page; a page without a table fails loudly", () => {
  expect(
    parseUpcDecisionsPage(
      "<html><body><table><tbody></tbody></table></body></html>",
    ),
  ).toEqual({ hits: [], total_pages: 1 });
  expect(() => parseUpcDecisionsPage("<html><body></body></html>")).toThrow(
    ApiError,
  );
});

test("filter options parse and divisions deduplicate across selects", () => {
  expect(parseUpcLanguages(LISTING)).toEqual([
    { id: "33", name: "English" },
    { id: "34", name: "French" },
    { id: "35", name: "German" },
  ]);
  expect(parseUpcDivisions(LISTING).map((option) => option.id)).toEqual([
    "125",
    "134",
    "140",
  ]);
});

test("search sends Python's query parameters and omits page=0", async () => {
  const site = stubSite();
  const first = await site.client.search();
  expect(first.data.page).toBe(0);
  expect(site.urls[0]?.pathname).toBe("/en/decisions-and-orders");
  expect(site.urls[0]?.search).toBe("");
  await site.client.search({
    page: 2,
    judgement_type: "order",
    court_type: "3",
    division: "134",
    proceedings_lang: "33",
  });
  expect(Object.fromEntries(site.urls[1]?.searchParams ?? [])).toEqual({
    page: "2",
    judgement_type: "order",
    court_type: "3",
    division_1: "134",
    proceedings_lang: "33",
  });
  expect(() => new UpcDecisionsClient({ language: "xx" as "en" })).toThrow(
    "language must be",
  );
});

test("a Cloudflare challenge is UPSTREAM_BLOCKED, not an empty page", async () => {
  const site = stubSite(CHALLENGE, 403);
  const error = await site.client.search().catch((caught) => caught);
  expect(error).toBeInstanceOf(ApiError);
  expect(error.code).toBe("UPSTREAM_BLOCKED");
});

async function curated(site: ReturnType<typeof stubSite>) {
  const server = createServer({
    toolset: "curated",
    clients: { upcDecisions: site.client },
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    async close() {
      await client.close();
      await server.close();
    },
  };
}

test("search_upc_decisions publishes the Python tool's schema exactly", async () => {
  const expected = JSON.parse(
    readFileSync(
      join(
        import.meta.dir,
        "fixtures",
        "facade",
        "law-tools-search-upc-decisions.json",
      ),
      "utf8",
    ),
  );
  const session = await curated(stubSite());
  try {
    const tool = (await session.client.listTools()).find(
      (candidate) => candidate.name === "search_upc_decisions",
    );
    expect(tool?.description).toBe(expected.description);
    expect(tool?.inputSchema).toEqual(expected.inputSchema);
    expect(tool?.outputSchema).toEqual(expected.outputSchema);
    expect(tool?.annotations).toEqual(expected.annotations);
  } finally {
    await session.close();
  }
});

test("search_upc_decisions returns Python's lean envelope and full rows", async () => {
  const site = stubSite();
  const session = await curated(site);
  try {
    const lean = (
      await session.client.callTool("search_upc_decisions", {
        judgement_type: "order",
        court_type: "1",
      })
    ).structuredContent as Record<string, unknown> & {
      items: Record<string, unknown>[];
      provenance: Record<string, unknown>;
    };
    expect(lean.summary).toBe(
      "UPC decisions — type=order court_type=1: 4 hits (page 0/38).",
    );
    expect(lean.more_available).toBe(true);
    expect(lean.next_cursor).toBeNull();
    expect(Object.keys(lean.items[0] ?? {}).sort()).toEqual([
      "case_id",
      "court",
      "detail_url",
      "parties",
      "primary_pdf_url",
      "type_of_action",
    ]);
    expect(lean.provenance).toMatchObject({
      source_url: "https://www.unifiedpatentcourt.org/en/decisions-and-orders",
      source_name: "Unified Patent Court",
      connector_version: "0.1.0",
    });
    expect(typeof lean.provenance.retrieved_at).toBe("string");

    const full = (
      await session.client.callTool("search_upc_decisions", {
        page: 37,
        full: true,
      })
    ).structuredContent as {
      summary: string;
      items: Record<string, unknown>[];
      more_available: boolean;
    };
    expect(full.summary).toBe(
      "UPC decisions — (no filters): 4 hits (page 37/38).",
    );
    expect(full.items[0]).toHaveProperty("pdf_urls");
    expect(full.items[0]).toHaveProperty("raw_references");
    expect(full.more_available).toBe(false);
    expect(site.urls[1]?.searchParams.get("page")).toBe("37");
  } finally {
    await session.close();
  }
});

/** Page 0 is LISTING; page n (1..37) holds one row, UPC_CFI_<1000+n>/2024. */
function pagedSite() {
  const pages: number[] = [];
  const client = new UpcDecisionsClient({
    useCache: false,
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) => {
      const url = new URL(input instanceof Request ? input.url : input);
      const page = Number(url.searchParams.get("page") ?? 0);
      pages.push(page);
      const body =
        page === 0
          ? LISTING
          : `<table><tbody><tr><td headers="view-field-judgement-application-no-1">UPC_CFI_${1000 + page}/2024</td><td headers="view-field-location">Munich (DE) Local Division</td></tr></tbody></table><li class="pager__item--last"><a href="?page=37">Last</a></li>`;
      return new Response(body, {
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }) as typeof fetch,
  });
  return { client, pages };
}

test("getDecisions walks the listing once, canonicalizes ids and stops when all are found", async () => {
  const site = pagedSite();
  const { data } = await site.client.getDecisions([
    "UPC-CFI-478/2025",
    "UPC_CFI_1003/2024",
  ]);
  expect(data.get("UPC-CFI-478/2025")?.case_id).toBe("UPC_CFI_478/2025");
  expect(data.get("UPC_CFI_1003/2024")?.court).toBe(
    "Munich (DE) Local Division",
  );
  expect(site.pages).toEqual([0, 1, 2, 3]);

  const missing = pagedSite();
  expect((await missing.client.getDecision("UPC_CFI_9999/2099")).data).toBe(
    null,
  );
  expect(missing.pages).toHaveLength(38);
});

test("get_litigation(forum='upc') returns Python's get_upc_decision envelope", async () => {
  const site = pagedSite();
  const server = createServer({
    toolset: "curated",
    clients: { upcDecisions: site.client },
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  type Envelope = {
    summary: string;
    items: Record<string, unknown>[];
    not_found: string[];
    more_available: boolean;
    provenance: Record<string, unknown>;
  };
  const call = async (identifier: string | string[]) =>
    (await client.callTool("get_litigation", { forum: "upc", identifier }))
      .structuredContent as Envelope;
  try {
    const one = await call("UPC_CoA_0000053/2026");
    expect(one.summary).toBe(
      "**UPC UPC_CoA_0000053/2026** — Luxembourg (LU)\nType: Request for a discretionary review (RoP 220.3). Parties: Huawei Technologies Co. Ltd. v. Quinn Emanuel Urquhart & Sullivan, LLP.",
    );
    expect(one.items[0]).toHaveProperty("pdf_urls");
    expect(one.items[0]).toHaveProperty("raw_references");
    expect(one.not_found).toEqual([]);
    expect(one.provenance).toMatchObject({
      source_url:
        "https://www.unifiedpatentcourt.org/en/decisions-and-orders?case_id=UPC_CoA_0000053/2026",
      source_name: "Unified Patent Court",
    });

    const batch = await call([
      "ACT_551054/2023",
      "UPC_CFI_9999/2099",
      "UPC_CFI_1747/2025",
    ]);
    expect(batch.items.map((item) => item.case_id)).toEqual([
      "ACT_551054/2023",
      "UPC_CFI_1747/2025",
    ]);
    expect(batch.not_found).toEqual(["UPC_CFI_9999/2099"]);
    expect(batch.summary).toBe(
      "Fetched 2 of 3 UPC decisions. Not found: UPC_CFI_9999/2099.",
    );
    expect(batch.more_available).toBe(false);
    expect(batch.provenance.source_url).toBe(
      "https://www.unifiedpatentcourt.org/en/decisions-and-orders",
    );

    const absent = await call("UPC_CFI_9999/2099");
    expect(absent.summary).toBe("UPC decision UPC_CFI_9999/2099 — not found.");
    expect(absent.items).toEqual([]);
    expect(absent.not_found).toEqual(["UPC_CFI_9999/2099"]);
  } finally {
    await client.close();
    await server.close();
  }
});

test("get_litigation's description and parameter docs match Python's", async () => {
  const python = (
    JSON.parse(
      readFileSync(
        join(import.meta.dir, "fixtures", "facade", "python-facade-tools.json"),
        "utf8",
      ),
    ) as {
      name: string;
      description: string;
      inputSchema: { properties: Record<string, { description?: string }> };
    }[]
  ).find((tool) => tool.name === "get_litigation");
  const session = await curated(stubSite());
  try {
    const tool = (await session.client.listTools()).find(
      (candidate) => candidate.name === "get_litigation",
    );
    expect(tool?.description).toBe(python?.description);
    const properties = tool?.inputSchema.properties as Record<
      string,
      { description?: string }
    >;
    for (const [name, schema] of Object.entries(
      python?.inputSchema.properties ?? {},
    ))
      expect([name, properties[name]?.description]).toEqual([
        name,
        schema.description,
      ]);
  } finally {
    await session.close();
  }
});

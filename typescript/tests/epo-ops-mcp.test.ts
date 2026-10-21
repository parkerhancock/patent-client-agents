import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { EpoOpsClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { PDFDocument } from "pdf-lib";
import { createServer } from "../packages/mcp/src/index.js";

const epoTools = [
  "search_epo",
  "get_epo_publication",
  "get_ep_register",
  "get_epo_family_evidence",
  "convert_epo_number",
  "download_epo_pdf",
  "search_cpc",
  "lookup_cpc",
];
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

type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  details?: Record<string, unknown>;
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  download_url?: string;
};

async function onePagePdf() {
  const pdf = await PDFDocument.create();
  pdf.addPage([200, 200]).setRotation({ type: "degrees", angle: 90 } as never);
  return pdf.save();
}

/** Route-based synthetic OPS that records every data path. */
async function fakeClient() {
  const paths: string[] = [];
  const page = await onePagePdf();
  const fetcher = (async (input, init) => {
    const url = new URL(new Request(input, init).url);
    if (url.pathname.endsWith("/accesstoken"))
      return Response.json({ access_token: "t", expires_in: 1200 });
    paths.push(decodeURIComponent(url.pathname + url.search));
    const path = url.pathname;
    if (path.endsWith("/published-data/search")) {
      const [begin, end] = (url.searchParams.get("Range") ?? "1-1")
        .split("-")
        .map(Number);
      return new Response(searchXml(begin ?? 1, Math.min(end ?? 1, 60)));
    }
    if (path.includes("EP404"))
      return new Response(
        `<fault xmlns="http://ops.epo.org"><code>SERVER.EntityNotFound</code><message>No</message></fault>`,
        { status: 404 },
      );
    if (path.endsWith("/upp"))
      return new Response(wpd(`<reg:register-documents/>`));
    if (path.endsWith("/images"))
      return new Response(
        wpd(
          `<ops:document-inquiry><ops:inquiry-result><ops:document-instance desc="FullDocument" link="published-data/images/EP/1/A1/fullimage" number-of-pages="1"/></ops:inquiry-result></ops:document-inquiry>`,
        ),
      );
    if (path.endsWith("fullimage.pdf"))
      return new Response(new Blob([new Uint8Array(page)]));
    if (path.includes("/classification/cpc/") && !path.endsWith("search"))
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

async function connect(epoOps: EpoOpsClient) {
  const server = createServer({ clients: { epoOps } });
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

test("EPO OPS tools appear only with credentials or an injected client", async () => {
  const saved = { ...process.env };
  for (const name of [
    "EPO_OPS_API_KEY",
    "EPO_OPS_API_SECRET",
    "EPO_API_KEY",
    "EPO_API_SECRET",
  ])
    delete process.env[name];
  try {
    const bare = createServer();
    const client = await Client.connect(bare, {
      versionNegotiation: { mode: "legacy" },
    });
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => epoTools.includes(name))).toEqual([]);
    await client.close();
    await bare.close();
  } finally {
    Object.assign(process.env, saved);
  }
  const { client } = await fakeClient();
  const mcp = await connect(client);
  try {
    expect((await mcp.client.listTools()).map((tool) => tool.name)).toEqual(
      expect.arrayContaining(epoTools),
    );
    const resources = (await mcp.client.listResources()).map((r) => r.uri);
    expect(resources).toContain("resource://epo-ops/cql-query-guide");
  } finally {
    await mcp.close();
  }
});

test("search_epo forwards range, jurisdiction and query-bound cursors", async () => {
  const fake = await fakeClient();
  const mcp = await connect(fake.client);
  try {
    const first = await mcp.client.callTool<Envelope>("search_epo", {
      cql_query: "ta=battery",
      jurisdiction: "DE",
      limit: 10,
    });
    const page = first.structuredContent;
    expect(page?.items).toHaveLength(10);
    expect(page?.items[0]).toEqual({
      publication_number: "EP1A1",
      publication_date: null,
      country: "EP",
      kind: "A1",
      family_id: "0",
    });
    expect(page?.more_available).toBe(true);
    const second = await mcp.client.callTool<Envelope>("search_epo", {
      cql_query: "ta=battery",
      jurisdiction: "DE",
      limit: 10,
      cursor: page?.next_cursor,
    });
    expect(second.structuredContent?.items[0]?.publication_number).toBe(
      "EP11A1",
    );
    expect(fake.paths).toEqual([
      "/3.2/rest-services/published-data/search?q=(ta=battery)+and+pn=DE&Range=1-10",
      "/3.2/rest-services/published-data/search?q=(ta=battery)+and+pn=DE&Range=11-20",
    ]);
    await expect(
      mcp.client.callTool("search_epo", {
        cql_query: "ta=other",
        limit: 10,
        cursor: page?.next_cursor,
      }),
    ).rejects.toThrow("different query");
    const families = await mcp.client.callTool<Envelope>("search_epo", {
      cql_query: "ta=battery",
      group_by: "family",
      limit: 4,
    });
    expect(
      families.structuredContent?.items.map((i) => i.member_count),
    ).toEqual([1, 2, 1]);
    expect(families.structuredContent?.next_cursor).not.toBeNull();
  } finally {
    await mcp.close();
  }
});

test("get_epo_publication maps each view to its OPS route and reports not-found batch members", async () => {
  const fake = await fakeClient();
  const mcp = await connect(fake.client);
  try {
    for (const view of [
      "biblio",
      "claims",
      "description",
      "citations",
      "equivalents",
      "family",
      "legal_events",
      "cpci",
    ])
      expect(
        (
          await mcp.client.callTool("get_epo_publication", {
            publication_numbers: "EP1A1",
            view,
          })
        ).isError,
      ).toBe(false);
    expect(fake.paths).toEqual([
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/biblio",
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/claims",
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/description",
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/biblio",
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/equivalents",
      "/3.2/rest-services/family/publication/docdb/EP1A1",
      "/3.2/rest-services/legal/publication/docdb/EP1A1",
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/biblio",
    ]);
    const batch = await mcp.client.callTool<Envelope>("get_epo_publication", {
      publication_numbers: ["ep1a1", "EP404A1"],
    });
    expect(batch.structuredContent?.items).toHaveLength(1);
    expect(batch.structuredContent?.not_found).toEqual(["EP404A1"]);
    await expect(
      mcp.client.callTool("get_epo_publication", {
        publication_numbers: "EP404A1",
      }),
    ).rejects.toThrow("found no matching record");
  } finally {
    await mcp.close();
  }
});

test("register, CPC, conversion and PDF tools forward their options", async () => {
  const fake = await fakeClient();
  const mcp = await connect(fake.client);
  try {
    const upp = await mcp.client.callTool<Envelope>("get_ep_register", {
      epo_numbers: "EP1000000",
      view: "unitary_patent",
    });
    expect(upp.structuredContent?.items[0]).toMatchObject({
      epo_number: "EP1000000",
      statuses: [],
      is_registered: false,
    });
    const cpc = await mcp.client.callTool<Envelope>("lookup_cpc", {
      symbol: "h04l9/32",
      depth: 1,
      ancestors: true,
      map_to: "ipc",
    });
    expect(cpc.structuredContent?.summary).toContain("1 IPC mappings");
    await mcp.client.callTool("convert_epo_number", {
      number: "EP1000000",
      input_format: "epodoc",
      output_format: "original",
    });
    const pdf = await mcp.client.callTool<Envelope>("download_epo_pdf", {
      publication_number: "EP1A1",
    });
    expect(pdf.isError).toBe(false);
    expect(
      pdf.structuredContent?.download_url ??
        (pdf.structuredContent as { file_path?: string })?.file_path,
    ).toBeTruthy();
    expect(fake.paths).toEqual([
      "/3.2/rest-services/register/publication/epodoc/EP1000000/upp",
      "/3.2/rest-services/classification/cpc/H04L9/32?depth=1&ancestors=true",
      "/3.2/rest-services/classification/map/cpc/H04L9/32/ipc",
      "/3.2/rest-services/number-service/publication/epodoc/EP1000000/original",
      "/3.2/rest-services/published-data/publication/docdb/EP1A1/images",
      "/3.2/rest-services/published-data/images/EP/1/A1/fullimage.pdf?Range=1",
    ]);
  } finally {
    await mcp.close();
  }
});

test("Bun HTTP serves EPO OPS tools only to tokens with epo:read", async () => {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
  });
  const jwk = {
    ...publicKey.export({ format: "jwk" }),
    kid: "test-key",
    alg: "RS256",
    use: "sig",
  };
  const identity = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch: () => Response.json({ keys: [jwk] }),
  });
  const issuer = "https://identity.test";
  const audience = "patent-client-agents";
  const { client: epoOps } = await fakeClient();
  const server = createServer({
    clients: { epoOps },
    auth: {
      jwksUri: `http://127.0.0.1:${identity.port}/jwks`,
      issuer,
      audience,
    },
  });
  await server.run({
    transport: "http",
    host: "127.0.0.1",
    port: 0,
    stateless: true,
  });
  const url = `http://127.0.0.1:${server.address?.port}/mcp`;
  const token = (scope: string) => {
    const encode = (value: object) =>
      Buffer.from(JSON.stringify(value)).toString("base64url");
    const unsigned = `${encode({ alg: "RS256", kid: "test-key", typ: "JWT" })}.${encode({ iss: issuer, aud: audience, sub: "test-user", exp: Math.floor(Date.now() / 1000) + 120, scope })}`;
    return `${unsigned}.${sign("RSA-SHA256", Buffer.from(unsigned), privateKey).toString("base64url")}`;
  };
  try {
    const uspto = await Client.connect(url, {
      auth: new BearerAuth(token("odp:read uspto:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await uspto.listTools()).map((tool) => tool.name);
      expect(names.filter((name) => epoTools.includes(name))).toEqual([]);
      await expect(
        uspto.callTool("search_epo", { cql_query: "ta=x" }),
      ).rejects.toThrow();
    } finally {
      await uspto.close();
    }
    const epo = await Client.connect(url, {
      auth: new BearerAuth(token("epo:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const result = await epo.callTool<Envelope>("search_epo", {
        cql_query: "ta=x",
        limit: 2,
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items).toHaveLength(2);
    } finally {
      await epo.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

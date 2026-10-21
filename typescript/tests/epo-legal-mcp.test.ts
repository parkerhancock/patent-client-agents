import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  EpcClient,
  EpoCaseLawClient,
  EpoGuidelinesClient,
  EpoPctGuidelinesClient,
  EpoUpGuidelinesClient,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { EPO_LEGAL_STATUS_URIS } from "../packages/mcp/src/epo-legal.js";
import { createServer } from "../packages/mcp/src/index.js";

const fixture = (name: string) =>
  join(import.meta.dir, "fixtures", "epo-legal", `${name}.db`);
const epoTools = [
  "search_epc",
  "get_epc_section",
  "search_epo_case_law",
  "get_epo_case_law_section",
  "search_epo_guidelines",
  "get_epo_guidelines_section",
  "search_epo_pct_guidelines",
  "get_epo_pct_guidelines_section",
  "search_epo_up_guidelines",
  "get_epo_up_guidelines_section",
];

function fixtureClients() {
  return {
    epc: new EpcClient({ corpusPath: fixture("epc") }),
    caseLaw: new EpoCaseLawClient({ corpusPath: fixture("caselaw") }),
    guidelines: new EpoGuidelinesClient({ corpusPath: fixture("guidelines") }),
    pctGuidelines: new EpoPctGuidelinesClient({
      corpusPath: fixture("pct_guidelines"),
    }),
    upGuidelines: new EpoUpGuidelinesClient({
      corpusPath: fixture("up_guidelines"),
    }),
  };
}
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  provenance: Record<string, unknown>;
};

test("EPO legal MCP tools search real fixture rows with lean projections and snapshot-bound cursors", async () => {
  const clients = fixtureClients();
  const server = createServer({ epoLegal: clients });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(epoTools),
    );
    expect(
      tools
        .filter((tool) => epoTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const first = await client.callTool<Envelope>("search_epo_guidelines", {
      query: "patent",
      sort: "outline",
      limit: 1,
    });
    const page = first.structuredContent;
    expect(page?.items).toEqual([
      {
        section_number: "G-II, 3",
        title: "G-II, 3 - 3. List of exclusions",
        snippet: expect.stringContaining("<mark>"),
        href: "g_ii_3",
      },
    ]);
    expect(page?.more_available).toBe(true);
    expect(page?.summary).toContain("edition 2024");
    expect(page?.summary).toContain("not verified against the current EPO");
    expect(page?.provenance).toMatchObject({
      source_name: "EPO Guidelines for Examination",
      source_url: "https://www.epo.org/en/legal/guidelines-epc/2024",
      cache_hit: true,
      retrieved_at: "2026-05-14T00:00:00.000Z",
      corpus_synced_at: "2026-05-14T00:00:00.000Z",
      corpus_version: "2024",
      connector_version: "0.1.0",
    });
    const second = await client.callTool<Envelope>("search_epo_guidelines", {
      query: "patent",
      sort: "outline",
      limit: 1,
      cursor: page?.next_cursor,
    });
    expect(second.structuredContent?.items[0]?.href).toBe("g_ii_3_1");
    // A cursor is bound to the exact query options.
    await expect(
      client.callTool("search_epo_guidelines", {
        query: "patent",
        sort: "relevance",
        limit: 1,
        cursor: page?.next_cursor,
      }),
    ).rejects.toThrow("different query or corpus");

    const full = await client.callTool<Envelope>("search_epc", {
      query: "inventive step",
      full: true,
    });
    expect(full.structuredContent?.items[0]).toMatchObject({
      href: "a52",
      section_number: "Article 52",
      chapter: "Article",
      path: ["Article", "Article 52"],
      result_url: "https://www.epo.org/en/legal/epc/2020/a52.html",
    });

    for (const [tool, query, href] of [
      ["search_epo_case_law", "inventive step", "clr_i_d_9_1"],
      ["search_epo_pct_guidelines", "scope", "b_iii_1"],
      ["search_epo_up_guidelines", "new", "section_2_4"],
    ] as const) {
      const result = await client.callTool<Envelope>(tool, { query });
      expect([tool, result.structuredContent?.items[0]?.href]).toEqual([
        tool,
        href,
      ]);
    }
  } finally {
    await client.close();
    await server.close();
    for (const reader of Object.values(clients)) reader.close();
  }
});

test("EPO legal MCP section fetches keep order, mark missing entries and deliver HTML as artifacts", async () => {
  const clients = fixtureClients();
  const server = createServer({ epoLegal: clients });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await client.callTool<Envelope>("get_epc_section", {
      section: ["R. 71", "Article 999", "Art. 54"],
    });
    const items = result.structuredContent?.items ?? [];
    expect(items.map((item) => item.href ?? item.section)).toEqual([
      "r71",
      "Article 999",
      "a54",
    ]);
    expect(items[0]).toMatchObject({
      section_number: "Rule 71",
      citation: { kind: "rule", number: "71" },
      edition: "2020",
      version: "2020",
      source_url: "https://www.epo.org/en/legal/epc/2020/r71.html",
      text: expect.stringContaining("Rule 71"),
    });
    expect(items[0]).not.toHaveProperty("html");
    expect(items[1]).toEqual({
      section: "Article 999",
      error: {
        code: "NOT_FOUND",
        message: "EPC section was not found in the installed corpus.",
      },
    });
    expect(result.structuredContent?.provenance).toMatchObject({
      source_url: "https://www.epo.org/en/legal/epc/2020/r71.html",
      corpus_version: "2020",
    });

    const html = await client.callTool<Envelope>(
      "get_epo_up_guidelines_section",
      { section: "1.2.1", format: "html" },
    );
    const document = html.structuredContent?.items[0]?.document as {
      file_path: string;
      filename: string;
      content_type: string;
    };
    expect(document).toMatchObject({
      filename: "epo-up-guidelines-section_1_2_1.html",
      content_type: "text/html",
    });
    expect(await readFile(document.file_path, "utf8")).toContain(
      "Show modifications",
    );
    expect(html.structuredContent?.items[0]).not.toHaveProperty("text");

    await expect(
      client.callTool("get_epo_case_law_section", { section: "IX.Z.99" }),
    ).rejects.toThrow("EPO Case Law section was not found");

    const content = (await client.readResource("epc://corpus/status"))[0];
    const parsed = JSON.parse(
      content && "text" in content ? content.text : "{}",
    ) as Record<string, unknown>;
    expect(parsed).toMatchObject({
      available: true,
      edition: "2020",
      release_verified: false,
      section_count: 4,
    });
    const resources = (await client.listResources()).map(
      (resource) => resource.uri,
    );
    expect(resources).toEqual(expect.arrayContaining(EPO_LEGAL_STATUS_URIS));
  } finally {
    await client.close();
    await server.close();
    for (const reader of Object.values(clients)) reader.close();
  }
});

test("Bun HTTP serves EPO legal tools only to tokens with epo:read", async () => {
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
  const clients = fixtureClients();
  const server = createServer({
    epoLegal: clients,
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
      expect(names).toContain("search_mpep");
      expect(names.filter((name) => epoTools.includes(name))).toEqual([]);
      await expect(
        uspto.callTool("search_epc", { query: "patent" }),
      ).rejects.toThrow();
    } finally {
      await uspto.close();
    }
    const epo = await Client.connect(url, {
      auth: new BearerAuth(token("epo:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await epo.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(epoTools),
      );
      const result = await epo.callTool<Envelope>(
        "get_epo_guidelines_section",
        {
          section: "G-II, 3.1",
        },
      );
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.href).toBe("g_ii_3_1");
    } finally {
      await epo.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
    for (const reader of Object.values(clients)) reader.close();
  }
});

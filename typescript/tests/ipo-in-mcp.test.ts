import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { join } from "node:path";
import {
  IpoInMpppClient,
  IpoInStatutesClient,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import {
  IPO_IN_MPPP_STATUS_URI,
  IPO_IN_STATUTES_STATUS_URI,
} from "../packages/mcp/src/ipo-in.js";

const dir = join(import.meta.dir, "fixtures", "ipo-in");
const ipoTools = [
  "search_ipo_in_statutes",
  "get_ipo_in_section",
  "search_ipo_in_mppp",
  "get_ipo_in_mppp_section",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

function readers() {
  return {
    ipoInStatutes: new IpoInStatutesClient({
      corpusPath: join(dir, "ipo_in_statutes.db"),
    }),
    ipoInMppp: new IpoInMpppClient({ corpusPath: join(dir, "ipo_in_mppp.db") }),
  };
}
async function connect(toolset: "full" | "curated") {
  const corpora = readers();
  const server = createServer({ toolset, ...corpora });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    async close() {
      await client.close();
      await server.close();
      corpora.ipoInStatutes.close();
      corpora.ipoInMppp.close();
    },
  };
}

test("IPO India statutes MCP tools keep Python's envelopes, lean stubs and not_found", async () => {
  const { client, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(ipoTools),
    );
    expect(
      tools
        .filter((tool) => ipoTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const search = await client.callTool<Envelope>("search_ipo_in_statutes", {
      query: "compulsory licence",
      statute: "patents act 1970",
    });
    expect(search.structuredContent).toMatchObject({
      summary:
        "IPO India statutes (Patents Act) — `compulsory licence`: 1 hit (corpus snapshot-2026-10-22).",
      next_cursor: null,
      more_available: false,
      provenance: {
        source_url: "https://ipindia.gov.in/pages/home/acts-rules-ipr",
        source_name: "IPO India — IP statutes",
        corpus_version: "snapshot-2026-10-22",
        corpus_synced_at: "2026-10-22T00:00:00.000Z",
      },
    });
    expect(
      Object.keys(search.structuredContent?.items[0] ?? {}).sort(),
    ).toEqual(["section_number", "snippet", "statute_name", "title"]);
    const full = await client.callTool<Envelope>("search_ipo_in_statutes", {
      query: "the",
      limit: 2,
      full: true,
    });
    expect(full.structuredContent?.items[0]?.rank).toEqual(expect.any(Number));
    expect(full.structuredContent?.more_available).toBe(true);
    expect(full.structuredContent?.summary).toEndWith("(more available).");

    const one = await client.callTool<Envelope>("get_ipo_in_section", {
      citation: "Section 3(d) Patents Act",
    });
    expect(one.structuredContent?.summary).toBe(
      "**Patents Act §3** — What are not inventions\nCited (d) is within this section's text.\nSource: IPO India statutes corpus (snapshot-2026-10-22)",
    );
    expect(one.structuredContent?.provenance.source_url).toBe(
      "https://ipindia.gov.in/storage/uploads/docs-operator/73b5bf10-b04e-4f45-abef-87ff117315dc.pdf#page=9",
    );
    expect(one.structuredContent?.items[0]).toMatchObject({
      statute_name: "Patents Act",
      section_number: "3",
      subdivision: "(d)",
      text: expect.stringContaining("enhancement of the known efficacy"),
    });
    const many = await client.callTool<Envelope>("get_ipo_in_section", {
      citation: [
        "Section 84 Patents Act",
        "Section 999",
        "Section 9 Trade Marks Act",
      ],
    });
    expect(many.structuredContent).toMatchObject({
      summary:
        "Fetched 2 of 3 IPO India statute sections. Not found: Section 999.",
      not_found: ["Section 999"],
      provenance: {
        source_url: "https://ipindia.gov.in/pages/home/acts-rules-ipr",
      },
    });
    expect(
      many.structuredContent?.items.map((item) => item.section_number),
    ).toEqual(["84", "9"]);
    // A plain string propagates not-found; ambiguity fails the call, as in Python.
    await expect(
      client.callTool("get_ipo_in_section", { citation: "Section 999" }),
    ).rejects.toThrow("not found");
    await expect(
      client.callTool("get_ipo_in_section", { citation: ["Section 2"] }),
    ).rejects.toThrow("ambiguous");

    const status = await client.readResource(IPO_IN_STATUTES_STATUS_URI);
    expect(
      JSON.parse(status[0] && "text" in status[0] ? status[0].text : "{}"),
    ).toMatchObject({
      available: true,
      section_count: 37,
    });
  } finally {
    await close();
  }
});

test("IPO India MPPP MCP tools search and fetch sections", async () => {
  const { client, close } = await connect("full");
  try {
    const search = await client.callTool<Envelope>("search_ipo_in_mppp", {
      query: "working",
    });
    expect(search.structuredContent).toMatchObject({
      summary: "IPO India MPPP — `working`: 1 hit (corpus v3.0 (2019-11-26)).",
      items: [
        {
          section_number: "14.01",
          chapter: "Chapter 14: Compulsory Licensing",
          title: "Working of patents - General principles",
          snippet: expect.stringContaining("<mark>"),
        },
      ],
      provenance: {
        source_name: "IPO India Manual of Patent Practice & Procedure (MPPP)",
        corpus_version: "v3.0 (2019-11-26)",
      },
    });
    const get = await client.callTool<Envelope>("get_ipo_in_mppp_section", {
      citation: ["MPPP 9.3.5.4", "99.01"],
    });
    expect(get.structuredContent).toMatchObject({
      summary: "Fetched 1 of 2 MPPP sections. Not found: 99.01.",
      not_found: ["99.01"],
    });
    const single = await client.callTool<Envelope>("get_ipo_in_mppp_section", {
      citation: "09.03",
    });
    expect(single.structuredContent?.summary).toStartWith(
      "**MPPP Chapter 09.03** — Examination of application",
    );
    expect(single.structuredContent?.provenance.source_url).toBe(
      "https://ipindia.gov.in/storage/uploads/docs-operator/e1adfe40-7af3-4180-ba04-2e0099c6dca5.pdf#page=81",
    );
    const status = await client.readResource(IPO_IN_MPPP_STATUS_URI);
    expect(
      JSON.parse(status[0] && "text" in status[0] ? status[0].text : "{}"),
    ).toMatchObject({
      corpus_version: "v3.0 (2019-11-26)",
    });
  } finally {
    await close();
  }
});

test("the curated facade routes india_statutes and india_mppp with the statute filter", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => ipoTools.includes(name))).toEqual([]);
    // No syntax given: statutes default to all-terms matching.
    const search = await client.callTool<Envelope>("search_legal_reference", {
      corpus: "india_statutes",
      query: "registration refusal",
      statute: "Trade Marks Act",
    });
    expect(
      search.structuredContent?.items.map((item) => item.section_number),
    ).toEqual(expect.arrayContaining(["9", "11"]));
    expect(
      search.structuredContent?.items.every(
        (item) => item.statute_name === "Trade Marks Act",
      ),
    ).toBe(true);
    const phrase = await client.callTool<Envelope>("search_legal_reference", {
      corpus: "india_statutes",
      query: "registration refusal",
      syntax: "adj",
    });
    expect(phrase.structuredContent?.items).toEqual([]);
    const mppp = await client.callTool<Envelope>("search_legal_reference", {
      corpus: "india_mppp",
      query: "pre-grant opposition",
    });
    expect(
      mppp.structuredContent?.items.map((item) => item.section_number),
    ).toEqual(["09.04", "01"]);

    const get = await client.callTool<Envelope>("get_legal_reference", {
      corpus: "india_statutes",
      identifier: "Section 3 Patents Act",
    });
    expect(get.structuredContent?.items).toHaveLength(1);
    expect(get.structuredContent?.items[0]?.title).toBe(
      "What are not inventions",
    );
    const section = await client.callTool<Envelope>("get_legal_reference", {
      corpus: "india_mppp",
      identifier: "Chapter 09.03.05.04",
    });
    expect(section.structuredContent?.items[0]?.section_number).toBe(
      "09.03.05.04",
    );
    await expect(
      client.callTool("get_legal_reference", {
        corpus: "india_mppp",
        identifier: "99.99",
      }),
    ).rejects.toThrow("not found");
    await expect(
      client.callTool("search_legal_reference", {
        corpus: "india_mppp",
        query: "x",
        version: "2019",
      }),
    ).rejects.toThrow("only for uspto_mpep");
  } finally {
    await close();
  }
});

test("Bun HTTP serves IPO India tools only to tokens with ipoin:read", async () => {
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
  const corpora = readers();
  const server = createServer({
    ...corpora,
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
    const other = await Client.connect(url, {
      auth: new BearerAuth(token("upc:read uspto:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names).toContain("search_upc_statutes");
      expect(names.filter((name) => ipoTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_ipo_in_statutes", { query: "patent" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const india = await Client.connect(url, {
      auth: new BearerAuth(token("ipoin:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await india.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(ipoTools),
      );
      const result = await india.callTool<Envelope>("search_ipo_in_mppp", {
        query: "opposition",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items).toHaveLength(2);
    } finally {
      await india.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
    corpora.ipoInStatutes.close();
    corpora.ipoInMppp.close();
  }
});

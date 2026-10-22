import { expect, test } from "bun:test";
import { createHash, generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { TmepClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { TMEP_CORPUS_STATUS_URI } from "../packages/mcp/src/tmep.js";

const fixture = join(import.meta.dir, "fixtures", "tmep", "tmep.db");
const tmepTools = ["search_tmep", "get_tmep_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const tmep = new TmepClient({ corpusPath: fixture });
  const server = createServer({ toolset, clients: { tmep } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    async close() {
      await client.close();
      await server.close();
      tmep.close();
    },
  };
}

test("search_tmep returns Python's lean stubs, cursors and corpus provenance", async () => {
  const { client, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(tmepTools),
    );
    const search = tools.find((tool) => tool.name === "search_tmep");
    expect(
      Object.keys(
        (search?.inputSchema as { properties?: object } | undefined)
          ?.properties ?? {},
      ).sort(),
    ).toEqual(["cursor", "full", "limit", "offset", "query", "sort", "syntax"]);
    expect(
      tools
        .filter((tool) => tmepTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const first = await client.callTool<Envelope>("search_tmep", {
      query: "mark",
      syntax: "and",
      sort: "outline",
      limit: 4,
    });
    const page = first.structuredContent;
    expect(page?.summary).toBe(
      "TMEP (unknown) — `mark`: 4 hits (more available).",
    );
    expect(page?.items[0]).toEqual({
      section_number: "1207",
      title:
        "Refusal on Basis of Likelihood of Confusion, Mistake, or Deception",
      snippet: expect.any(String),
      href: "TMEP-1200d1e5036.html",
    });
    expect(page?.more_available).toBe(true);
    expect(page?.provenance).toMatchObject({
      source_url: "https://tmep.uspto.gov/RDMS/TMEP/search",
      source_name: "USPTO TMEP (Trademark Manual of Examining Procedure)",
      cache_hit: true,
      corpus_synced_at: "2026-05-13T00:00:00.000Z",
      corpus_version: "unknown",
      connector_version: "0.1.0",
    });
    const next = await client.callTool<Envelope>("search_tmep", {
      query: "mark",
      syntax: "and",
      sort: "outline",
      limit: 4,
      cursor: page?.next_cursor,
    });
    expect(
      next.structuredContent?.items.map((item) => item.section_number),
    ).toEqual(["1301.04(i)", "1401.02(a)", "904"]);
    expect(next.structuredContent?.next_cursor).toBeNull();
    await expect(
      client.callTool("search_tmep", {
        query: "specimen",
        cursor: page?.next_cursor,
      }),
    ).rejects.toThrow("different query");

    const full = await client.callTool<Envelope>("search_tmep", {
      query: "punctuation",
      full: true,
    });
    expect(full.structuredContent?.items).toEqual([
      {
        title: "1209.03(u) - Punctuation",
        section_number: "1209.03(u)",
        href: "TMEP-1200d1e8145.html",
        path: ["Chapter 1200", "1209.03(u)"],
        result_url:
          "https://tmep.uspto.gov/RDMS/TMEP/result?href=TMEP-1200d1e8145.html",
        snippet: expect.stringContaining("<mark>Punctuation</mark>"),
      },
    ]);

    const content = (await client.readResource(TMEP_CORPUS_STATUS_URI))[0];
    expect(
      JSON.parse(content && "text" in content ? content.text : "{}"),
    ).toMatchObject({ available: true, section_count: 7 });
  } finally {
    await close();
  }
});

test("get_tmep_section keeps order, reports not_found and moves long or HTML content to artifacts", async () => {
  const { client, close } = await connect("full");
  try {
    const one = await client.callTool<Envelope>("get_tmep_section", {
      section: "TMEP-1200d1e8145.html",
    });
    expect(one.structuredContent?.summary).toBe(
      "**TMEP unknown — §1209.03(u): Punctuation**\nSource: https://tmep.uspto.gov/RDMS/TMEP/result?href=TMEP-1200d1e8145.html",
    );
    expect(one.structuredContent?.items[0]).toMatchObject({
      section_number: "1209.03(u)",
      href: "TMEP-1200d1e8145.html",
      text: expect.stringContaining("Punctuation"),
    });
    expect(one.structuredContent?.not_found).toEqual([]);
    expect(one.structuredContent?.provenance.source_url).toBe(
      "https://tmep.uspto.gov/RDMS/TMEP/result?href=TMEP-1200d1e8145.html",
    );

    const many = await client.callTool<Envelope>("get_tmep_section", {
      section: ["1207.01", "9999", "1401.02(a)", "904"],
    });
    const result = many.structuredContent;
    expect(result?.summary).toBe(
      "Fetched 3 of 4 TMEP sections (unknown). Not found: 9999.",
    );
    expect(result?.not_found).toEqual(["9999"]);
    expect(result?.items.map((item) => item.section_number)).toEqual([
      "1207.01",
      "1401.02(a)",
      "904",
    ]);
    expect(result?.items[0]?.text).toBeString();
    // 1401.02(a) is 80,980 characters: past the 32,000 inline budget.
    expect(result?.items[1]).not.toHaveProperty("text");
    const document = result?.items[1]?.document as {
      file_path: string;
      filename: string;
    };
    expect(document.filename).toBe("tmep-1401.02_a_.txt");
    expect(await readFile(document.file_path, "utf8")).toHaveLength(80_980);

    const html = await client.callTool<Envelope>("get_tmep_section", {
      section: "1207.01",
      format: "html",
    });
    const item = html.structuredContent?.items[0];
    const artifact = item?.document as { file_path: string };
    expect(
      createHash("sha256")
        .update(await readFile(artifact.file_path))
        .digest("hex"),
    ).toBe(String(item?.content_sha256));

    const none = await client.callTool<Envelope>("get_tmep_section", {
      section: ["9999"],
    });
    expect(none.structuredContent).toMatchObject({
      summary: "Fetched 0 of 1 TMEP sections (unknown). Not found: 9999.",
      items: [],
      not_found: ["9999"],
      provenance: { corpus_version: "unknown" },
    });
    await expect(
      client.callTool("get_tmep_section", { section: "9999" }),
    ).rejects.toThrow("Could not find TMEP section '9999'");
  } finally {
    await close();
  }
});

test("the curated facade routes corpus='uspto_tmep' to the TMEP reader", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names).not.toContain("search_tmep");
    const hits = await client.callTool<Envelope>("search_legal_reference", {
      corpus: "uspto_tmep",
      query: "likelihood of confusion",
      limit: 2,
    });
    expect(hits.structuredContent?.summary).toBe(
      "TMEP — `likelihood of confusion`: 2 hits at offset 0; more available from offset 2.",
    );
    expect(hits.structuredContent?.items[0]).toMatchObject({
      section_number: "1207.01",
      title: "Likelihood of Confusion",
    });
    const section = await client.callTool<Envelope>("get_legal_reference", {
      corpus: "uspto_tmep",
      identifier: "1207.01(a)",
    });
    expect(section.structuredContent?.items[0]).toMatchObject({
      section_number: "1207.01(a)",
      title: "Relatedness of the Goods or Services",
      text: expect.stringContaining("Relatedness"),
    });
    expect(section.structuredContent?.provenance).toMatchObject({
      source_name: "USPTO TMEP (Trademark Manual of Examining Procedure)",
      corpus_synced_at: "2026-05-13T00:00:00.000Z",
    });
    await expect(
      client.callTool("get_legal_reference", {
        corpus: "uspto_tmep",
        identifier: "9999",
      }),
    ).rejects.toThrow("TMEP section '9999' was not found");
    await expect(
      client.callTool("search_legal_reference", {
        corpus: "uspto_tmep",
        query: "mark",
        version: "2024",
      }),
    ).rejects.toThrow("only for uspto_mpep");
  } finally {
    await close();
  }
});

test("Bun HTTP serves TMEP tools only to tokens with uspto:read", async () => {
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
  const tmep = new TmepClient({ corpusPath: fixture });
  const server = createServer({
    clients: { tmep },
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
      auth: new BearerAuth(token("epo:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names.filter((name) => tmepTools.includes(name))).toEqual([]);
    } finally {
      await other.close();
    }
    const uspto = await Client.connect(url, {
      auth: new BearerAuth(token("uspto:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await uspto.listTools()).map((tool) => tool.name);
      expect(names).toEqual(expect.arrayContaining(tmepTools));
      expect(names).toContain("search_mpep");
      const result = await uspto.callTool<Envelope>("get_tmep_section", {
        section: "904",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.title).toBe("Specimens");
    } finally {
      await uspto.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
    tmep.close();
  }
});

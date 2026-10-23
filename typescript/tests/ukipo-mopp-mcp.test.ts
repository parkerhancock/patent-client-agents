import { expect, test } from "bun:test";
import { createHash, generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { MoppClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { MOPP_CORPUS_STATUS_URI } from "../packages/mcp/src/ukipo-mopp.js";

const fixture = join(import.meta.dir, "fixtures", "ukipo-mopp", "mopp.db");
const moppTools = ["search_mopp", "get_mopp_section"];
const INDEX = "https://www.gov.uk/guidance/manual-of-patent-practice-mopp";
const S4A = "-section-4a-methods-of-treatment-or-diagnosis";
const VERSION = "snapshot-2026-05-14";
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const mopp = new MoppClient({ corpusPath: fixture });
  const server = createServer({ toolset, clients: { mopp } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    async close() {
      await client.close();
      await server.close();
      mopp.close();
    },
  };
}

test("search_mopp returns Python's lean stubs, cursors and corpus provenance", async () => {
  const { client, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(moppTools),
    );
    const search = tools.find((tool) => tool.name === "search_mopp");
    expect(
      Object.keys(
        (search?.inputSchema as { properties?: object } | undefined)
          ?.properties ?? {},
      ).sort(),
    ).toEqual(["cursor", "full", "limit", "offset", "query", "sort", "syntax"]);
    expect(
      tools
        .filter((tool) => moppTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const first = await client.callTool<Envelope>("search_mopp", {
      query: "comptroller",
      syntax: "and",
      sort: "outline",
      limit: 3,
    });
    const page = first.structuredContent;
    expect(page?.summary).toBe(
      `MoPP (${VERSION}) — \`comptroller\`: 3 hits (more available).`,
    );
    expect(page?.items[1]).toEqual({
      section_number: "11",
      title: "Sections 11 effect of transfer of application under s 8 or 10",
      snippet: expect.any(String),
      href: "sections-11-effect-of-transfer-of-application-under-s-8-or-10",
    });
    expect(page?.provenance).toMatchObject({
      source_url: INDEX,
      source_name: "UKIPO Manual of Patent Practice (MoPP)",
      cache_hit: true,
      corpus_synced_at: "2026-05-14T00:00:00.000Z",
      corpus_version: VERSION,
      connector_version: "0.1.0",
    });
    const next = await client.callTool<Envelope>("search_mopp", {
      query: "comptroller",
      syntax: "and",
      sort: "outline",
      limit: 3,
      cursor: page?.next_cursor,
    });
    expect(
      next.structuredContent?.items.map((item) => item.section_number),
    ).toEqual(["4", "73"]);
    expect(next.structuredContent?.next_cursor).toBeNull();
    await expect(
      client.callTool("search_mopp", {
        query: "patent",
        cursor: page?.next_cursor,
      }),
    ).rejects.toThrow("different query");

    const full = await client.callTool<Envelope>("search_mopp", {
      query: "methods of treatment",
      full: true,
      limit: 1,
    });
    expect(full.structuredContent?.items).toEqual([
      {
        title: "4A - Section 4A: methods of treatment or diagnosis",
        section_number: "4A",
        href: S4A,
        path: ["4A"],
        result_url: `${INDEX}/${S4A}`,
        snippet: expect.stringContaining("<mark>"),
      },
    ]);

    const content = (await client.readResource(MOPP_CORPUS_STATUS_URI))[0];
    expect(
      JSON.parse(content && "text" in content ? content.text : "{}"),
    ).toMatchObject({
      available: true,
      section_count: 6,
      corpus_version: VERSION,
    });
  } finally {
    await close();
  }
});

test("get_mopp_section keeps order, reports not_found and moves long or HTML content to artifacts", async () => {
  const { client, close } = await connect("full");
  try {
    const one = await client.callTool<Envelope>("get_mopp_section", {
      section: "4a",
    });
    // Python's summary drops the slug's leading dash, a URL that 404s on gov.uk.
    expect(one.structuredContent?.summary).toBe(
      `**MoPP ${VERSION} — Section 4A: methods of treatment or diagnosis**\nSource: ${INDEX}/${S4A}`,
    );
    expect(one.structuredContent?.items[0]).toMatchObject({
      section_number: "4A",
      href: S4A,
      document: { filename: "mopp-4A.txt" },
    });
    expect(one.structuredContent?.not_found).toEqual([]);
    expect(one.structuredContent?.provenance.source_url).toBe(
      `${INDEX}/${S4A}`,
    );

    const many = await client.callTool<Envelope>("get_mopp_section", {
      section: ["4A", "9999", "73", "11", "4.02"],
    });
    const result = many.structuredContent;
    expect(result?.summary).toBe(
      `Fetched 4 of 5 MoPP sections (${VERSION}). Not found: 9999.`,
    );
    expect(result?.not_found).toEqual(["9999"]);
    expect(result?.items.map((item) => item.section_number)).toEqual([
      "4A",
      "73",
      "11",
      "4",
    ]);
    // 4A is 52,724 characters: past the 32,000 inline budget on its own.
    expect(result?.items[0]).not.toHaveProperty("text");
    const document = result?.items[0]?.document as {
      file_path: string;
      filename: string;
    };
    expect(document.filename).toBe("mopp-4A.txt");
    expect(await readFile(document.file_path, "utf8")).toHaveLength(52_724);
    // 73 (33,235 characters) is past the budget too; 11 and 4 fit inline.
    expect(result?.items[1]).toHaveProperty("document");
    expect(result?.items[2]?.text).toBeString();
    expect(result?.items[3]?.text).toBeString();

    const html = await client.callTool<Envelope>("get_mopp_section", {
      section: "glossary-of-terms-and-abbreviations-used-in-this-manual",
      format: "html",
    });
    const item = html.structuredContent?.items[0];
    const artifact = item?.document as { file_path: string; filename: string };
    expect(artifact.filename).toBe(
      "mopp-glossary-of-terms-and-abbreviations-used-in-this-manual.html",
    );
    expect(
      createHash("sha256")
        .update(await readFile(artifact.file_path))
        .digest("hex"),
    ).toBe(String(item?.content_sha256));

    const none = await client.callTool<Envelope>("get_mopp_section", {
      section: ["9999"],
    });
    expect(none.structuredContent).toMatchObject({
      summary: `Fetched 0 of 1 MoPP sections (${VERSION}). Not found: 9999.`,
      items: [],
      not_found: ["9999"],
      provenance: { corpus_version: VERSION, source_url: INDEX },
    });
    await expect(
      client.callTool("get_mopp_section", { section: "9999" }),
    ).rejects.toThrow("Could not find MoPP section '9999'");
  } finally {
    await close();
  }
});

test("the curated facade routes corpus='ukipo_mopp' to the MoPP reader", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names).not.toContain("search_mopp");
    const hits = await client.callTool<Envelope>("search_legal_reference", {
      corpus: "ukipo_mopp",
      query: "industrial application",
      limit: 1,
    });
    expect(hits.structuredContent?.summary).toBe(
      "UKIPO MoPP — `industrial application`: 1 hits at offset 0; more available from offset 1.",
    );
    expect(hits.structuredContent?.items[0]).toMatchObject({
      section_number: "4",
      title: "Section 4: industrial application",
    });
    const section = await client.callTool<Envelope>("get_legal_reference", {
      corpus: "ukipo_mopp",
      identifier: "4A",
    });
    // 52,724 characters: delivered as an artifact rather than inline.
    expect(section.structuredContent?.items[0]).toMatchObject({
      section_number: "4A",
      href: S4A,
      document: { filename: "ukipo_mopp-4A.txt" },
    });
    expect(section.structuredContent?.summary.split("\n")[0]).toBe(
      "**UKIPO MoPP 4A: methods of treatment or diagnosis**",
    );
    expect(section.structuredContent?.provenance).toMatchObject({
      source_name: "UKIPO Manual of Patent Practice (MoPP)",
      corpus_synced_at: "2026-05-14T00:00:00.000Z",
      corpus_version: VERSION,
    });
    const small = await client.callTool<Envelope>("get_legal_reference", {
      corpus: "ukipo_mopp",
      identifier: "11",
    });
    expect(small.structuredContent?.items[0]?.text).toBeString();
    await expect(
      client.callTool("get_legal_reference", {
        corpus: "ukipo_mopp",
        identifier: "9999",
      }),
    ).rejects.toThrow("UKIPO MoPP section '9999' was not found");
    await expect(
      client.callTool("search_legal_reference", {
        corpus: "ukipo_mopp",
        query: "patent",
        version: "2024",
      }),
    ).rejects.toThrow("only for uspto_mpep");
  } finally {
    await close();
  }
});

test("Bun HTTP serves MoPP tools only to tokens with ukipo:read", async () => {
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
  const mopp = new MoppClient({ corpusPath: fixture });
  const server = createServer({
    clients: { mopp },
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
      auth: new BearerAuth(token("uspto:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names.filter((name) => moppTools.includes(name))).toEqual([]);
    } finally {
      await other.close();
    }
    const ukipo = await Client.connect(url, {
      auth: new BearerAuth(token("ukipo:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await ukipo.listTools()).map((tool) => tool.name);
      expect(names).toEqual(expect.arrayContaining(moppTools));
      expect(names).not.toContain("search_tmep");
      const result = await ukipo.callTool<Envelope>("get_mopp_section", {
        section: "4",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.title).toBe(
        "Section 4: industrial application",
      );
    } finally {
      await ukipo.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
    mopp.close();
  }
});

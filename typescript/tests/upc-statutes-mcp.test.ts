import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { UpcStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { UPC_STATUTES_STATUS_URI } from "../packages/mcp/src/upc-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "upc-statutes",
  "upc_statutes.db",
);
const upcTools = [
  "search_upc_statutes",
  "get_upc_section",
  "list_upc_instruments",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const reader = new UpcStatutesClient({ corpusPath: fixture });
  const server = createServer({ toolset, upcStatutes: reader });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    async close() {
      await client.close();
      await server.close();
      reader.close();
    },
  };
}

test("UPC statutes MCP search pages by Python's page/per_page with corpus provenance", async () => {
  const { client, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(upcTools),
    );
    expect(
      tools
        .filter((tool) => upcTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const first = await client.callTool<Envelope>("search_upc_statutes", {
      query: "fee",
      per_page: 1,
    });
    const page = first.structuredContent;
    expect(page?.summary).toBe(
      "UPC statutes — `fee` (instrument=all, lang=en): 1 hits (page 1).",
    );
    expect(Object.keys(page?.items[0] ?? {}).sort()).toEqual([
      "instrument",
      "language",
      "rank",
      "short_name",
      "snippet",
    ]);
    expect(page?.more_available).toBe(true);
    expect(page?.next_cursor).toBeNull();
    expect(page?.provenance).toMatchObject({
      source_url: "https://www.unifiedpatentcourt.org/en/court/legal-documents",
      source_name: "Unified Patent Court",
      cache_hit: true,
      corpus_synced_at: "2026-05-14T00:00:00.000Z",
      corpus_version: "snapshot 2026-05-14",
      connector_version: "0.1.0",
    });
    const second = await client.callTool<Envelope>("search_upc_statutes", {
      query: "fee",
      per_page: 1,
      page: 2,
    });
    expect(second.structuredContent?.more_available).toBe(false);
    expect(
      [page, second.structuredContent]
        .map((result) => result?.items[0]?.instrument)
        .sort(),
    ).toEqual(["fees", "upca"]);

    const german = await client.callTool<Envelope>("search_upc_statutes", {
      query: "Streitwert",
      instrument: "court fees",
      language: "de",
    });
    expect(german.structuredContent?.summary).toContain(
      "(instrument=court fees, lang=de): 1 hits",
    );
    expect(german.structuredContent?.items[0]).toMatchObject({
      instrument: "fees",
      language: "de",
      snippet: expect.stringContaining("<mark>Streitwert</mark>"),
    });

    const listed = await client.callTool<Envelope>("list_upc_instruments", {});
    expect(listed.structuredContent?.summary).toBe(
      "UPC statutes instruments (lang=all) — 4 entries.",
    );
    const english = await client.callTool<Envelope>("list_upc_instruments", {
      language: "en",
    });
    expect(
      english.structuredContent?.items.map((item) => item.instrument),
    ).toEqual(["fees", "upca"]);

    const content = (await client.readResource(UPC_STATUTES_STATUS_URI))[0];
    expect(
      JSON.parse(content && "text" in content ? content.text : "{}"),
    ).toMatchObject({
      available: true,
      corpus_version: "snapshot 2026-05-14",
      instrument_count: 4,
    });
  } finally {
    await close();
  }
});

test("get_upc_section keeps order, reports not_found and delivers long texts as artifacts", async () => {
  const { client, close } = await connect("full");
  try {
    const one = await client.callTool<Envelope>("get_upc_section", {
      instrument: "fees",
      language: "fr",
    });
    expect(one.structuredContent?.summary).toBe(
      "**UPC Fees** (fr) — Tableau consolidé des frais de procédure et des dépens recouvrables\n8 page(s).",
    );
    expect(one.structuredContent?.items[0]).toMatchObject({
      instrument: "fees",
      language: "fr",
      text: expect.stringContaining("Tableau"),
    });
    expect(one.structuredContent?.provenance.source_url).toBe(
      "https://www.unifiedpatentcourt.org/sites/default/files/upc_documents/Consolidated%20Table%20of%20Court%20fees_FR.pdf",
    );

    const many = await client.callTool<Envelope>("get_upc_section", {
      instrument: ["fees", "rop", "statute", "coc"],
    });
    const result = many.structuredContent;
    expect(result?.summary).toBe(
      "Fetched 2 of 4 UPC instruments. Not found: rop, coc.",
    );
    expect(result?.not_found).toEqual(["rop", "coc"]);
    expect(result?.items.map((item) => item.instrument)).toEqual([
      "fees",
      "upca",
    ]);
    expect(result?.items[0]?.text).toBeString();
    // UPCA is 125,255 characters: past the 32,000 inline budget.
    expect(result?.items[1]).not.toHaveProperty("text");
    const document = result?.items[1]?.document as {
      file_path: string;
      filename: string;
      content_type: string;
    };
    expect(document).toMatchObject({
      filename: "upc-upca-en.txt",
      content_type: "text/plain",
    });
    expect(await readFile(document.file_path, "utf8")).toHaveLength(125_255);
    expect(result?.items[1]?.content_sha256).toBe(
      "98e59e5145eeeade781586178311ab249dae77a5b8fe2ab5ec8230fe37fe21be",
    );

    const missing = await client.callTool<Envelope>("get_upc_section", {
      instrument: "rules of procedure",
    });
    expect(missing.structuredContent).toMatchObject({
      summary: "UPC instrument rules of procedure — not found.",
      items: [],
      not_found: ["rules of procedure"],
      provenance: { corpus_version: "snapshot 2026-05-14" },
    });
    await expect(
      client.callTool("get_upc_section", { instrument: [] }),
    ).rejects.toThrow();
  } finally {
    await close();
  }
});

test("the curated facade re-exposes search_upc_statutes and get_upc_section with Python's parameters", async () => {
  const contract = JSON.parse(
    await readFile(
      join(import.meta.dir, "fixtures", "facade", "python-facade-tools.json"),
      "utf8",
    ),
  ) as {
    name: string;
    inputSchema: {
      properties: Record<string, { default?: unknown }>;
      required?: string[];
    };
  }[];
  const { client, close } = await connect("curated");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).not.toContain(
      "list_upc_instruments",
    );
    for (const name of ["search_upc_statutes", "get_upc_section"]) {
      const tool = tools.find((t) => t.name === name);
      const python = contract.find((t) => t.name === name);
      const schema = tool?.inputSchema as {
        properties: Record<string, { default?: unknown }>;
        required?: string[];
      };
      expect(Object.keys(schema.properties).sort()).toEqual(
        Object.keys(python?.inputSchema.properties ?? {}).sort(),
      );
      expect(schema.required ?? []).toEqual(python?.inputSchema.required ?? []);
      for (const [key, value] of Object.entries(
        python?.inputSchema.properties ?? {},
      ))
        if ("default" in value)
          expect([name, key, schema.properties[key]?.default]).toEqual([
            name,
            key,
            value.default,
          ]);
    }
    const hits = await client.callTool<Envelope>("search_upc_statutes", {
      query: "opt-out",
    });
    expect(hits.structuredContent?.items[0]?.instrument).toBe("upca");
    const section = await client.callTool<Envelope>("get_upc_section", {
      instrument: ["fees", "coc"],
    });
    expect(section.structuredContent?.not_found).toEqual(["coc"]);
    expect(section.structuredContent?.items[0]?.short_name).toBe("Fees");
  } finally {
    await close();
  }
});

test("Bun HTTP serves UPC statutes tools only to tokens with upc:read", async () => {
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
  const reader = new UpcStatutesClient({ corpusPath: fixture });
  const server = createServer({
    upcStatutes: reader,
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
    const epo = await Client.connect(url, {
      auth: new BearerAuth(token("epo:read uspto:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await epo.listTools()).map((tool) => tool.name);
      expect(names).toContain("search_epc");
      expect(names.filter((name) => upcTools.includes(name))).toEqual([]);
      await expect(
        epo.callTool("search_upc_statutes", { query: "fee" }),
      ).rejects.toThrow();
    } finally {
      await epo.close();
    }
    const upc = await Client.connect(url, {
      auth: new BearerAuth(token("upc:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await upc.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(upcTools),
      );
      const result = await upc.callTool<Envelope>("search_upc_statutes", {
        query: "opt-out",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.instrument).toBe("upca");
    } finally {
      await upc.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
    reader.close();
  }
});

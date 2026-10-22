import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { IlpoStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { ILPO_STATUTES_STATUS_URI } from "../packages/mcp/src/ilpo-statutes.js";
import { createServer } from "../packages/mcp/src/index.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "ilpo-statutes",
  "ilpo_statutes.db",
);
const ilpoTools = ["search_ilpo_statutes", "get_ilpo_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const reader = new IlpoStatutesClient({ corpusPath: fixture });
  const server = createServer({ toolset, ilpoStatutes: reader });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  const call = async (name: string, args: Record<string, unknown>) =>
    (await client.callTool<Envelope>(name, args)).structuredContent as Envelope;
  return {
    client,
    call,
    async close() {
      await client.close();
      await server.close();
      reader.close();
    },
  };
}

test("search_ilpo_statutes keeps Python's parameters, hits and summary", async () => {
  const { client, call, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(ilpoTools),
    );
    const search = tools.find((tool) => tool.name === "search_ilpo_statutes");
    expect(Object.keys(search?.inputSchema.properties ?? {}).sort()).toEqual([
      "page",
      "per_page",
      "query",
      "sort",
      "statute",
      "syntax",
    ]);
    expect(
      tools
        .filter((tool) => ilpoTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const result = await call("search_ilpo_statutes", {
      query: "trade secret",
      statute: "trade secrets",
      per_page: 1,
    });
    expect(result.summary).toBe(
      "ILPO Israel statutes — `trade secret` (statute=trade secrets): 1 hit (page 1).",
    );
    expect(result.more_available).toBe(true);
    expect(result.items[0]).toMatchObject({
      statute: "commercial_torts",
      section_label: expect.stringMatching(
        /^Section \d+ Commercial Torts Law$/,
      ),
      snippet: expect.stringContaining("<mark>"),
      rank: expect.any(Number),
    });
    expect(result.provenance).toMatchObject({
      source_name: "ILPO Israel — Statutes (WIPO Lex)",
      source_url: "https://www.wipo.int/wipolex/en/profile.jsp?code=IL",
      corpus_version: "WIPO Lex English translations, 2026-10-22",
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
    });
    const all = await call("search_ilpo_statutes", { query: "fair use" });
    expect(all.summary).toBe(
      "ILPO Israel statutes — `fair use` (statute=all): 1 hit (page 1).",
    );
  } finally {
    await close();
  }
});

test("get_ilpo_section reads one citation or a list, reporting misses", async () => {
  const { call, client, close } = await connect("full");
  try {
    const single = await call("get_ilpo_section", {
      citation: "Article 13 Commercial Torts Law",
    });
    expect(single.summary).toBe(
      "**Section 13 Commercial Torts Law** — Statutory damages",
    );
    expect(single.items).toHaveLength(1);
    expect(single.items[0]).toMatchObject({
      statute: "commercial_torts",
      section_number: "13",
      title: "Statutory damages",
      text: expect.stringContaining("NIS 100,000"),
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/2375",
    });
    expect(single.items[0]).not.toHaveProperty("provenance");
    expect(single.not_found).toEqual([]);

    const many = await call("get_ilpo_section", {
      citation: [
        "Section 6 Commercial Torts Law",
        "Patents Law §3",
        "Section 999 Patents Law",
        "nonsense",
      ],
    });
    expect(many.summary).toBe(
      "Fetched 2 of 4 ILPO sections. Not found: Section 999 Patents Law, nonsense.",
    );
    expect(many.items.map((item) => item.section_label)).toEqual([
      "Section 6 Commercial Torts Law",
      "Section 3 Patents Law",
    ]);
    expect(many.not_found).toEqual(["Section 999 Patents Law", "nonsense"]);

    const missing = await call("get_ilpo_section", {
      citation: "Section 999 Patents Law",
    });
    expect(missing.summary).toBe(
      "ILPO Israel section 'Section 999 Patents Law' — not found.",
    );
    expect(missing.items).toEqual([]);
    expect(missing.provenance.corpus_version).toBe(
      "WIPO Lex English translations, 2026-10-22",
    );

    const content = (await client.readResource(ILPO_STATUTES_STATUS_URI))[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    ) as { available: boolean; statutes: { statute: string }[] };
    expect(status.available).toBe(true);
    expect(status.statutes.map((item) => item.statute)).toEqual([
      "patents",
      "trademarks",
      "designs",
      "copyright",
      "commercial_torts",
    ]);
  } finally {
    await close();
  }
});

test("the curated toolset does not expose the ILPO statutes tools", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => ilpoTools.includes(name))).toEqual([]);
  } finally {
    await close();
  }
});

test("Bun HTTP serves ILPO statutes tools only to tokens with ilpo:read", async () => {
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
  const reader = new IlpoStatutesClient({ corpusPath: fixture });
  const server = createServer({
    ilpoStatutes: reader,
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
      auth: new BearerAuth(token("dpma:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names).toContain("search_dpma_statutes");
      expect(names.filter((name) => ilpoTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_ilpo_statutes", { query: "patent" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const ilpo = await Client.connect(url, {
      auth: new BearerAuth(token("ilpo:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await ilpo.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(ilpoTools),
      );
      const result = await ilpo.callTool<Envelope>("get_ilpo_section", {
        citation: "Section 46A Trade Marks Ordinance",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.statute).toBe("trademarks");
    } finally {
      await ilpo.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
    reader.close();
  }
});

test("the fixture is the builder's subset output, byte for byte", async () => {
  const bytes = await readFile(fixture);
  expect(new Bun.CryptoHasher("sha256").update(bytes).digest("hex")).toBe(
    "2345ccc3b8c04f35decbd13165e96ff5f9760bed6df41022d4cc60777319285e",
  );
});

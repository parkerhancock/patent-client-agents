import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ThaiDipStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { THAI_DIP_STATUTES_STATUS_URI } from "../packages/mcp/src/thai-dip-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "thai-dip-statutes",
  "thai_dip_statutes.db",
);
const thaiTools = ["search_thai_dip_statutes", "get_thai_dip_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const reader = new ThaiDipStatutesClient({ corpusPath: fixture });
  const server = createServer({ toolset, thaiDipStatutes: reader });
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

test("search_thai_dip_statutes takes the statute-corpus parameters and returns hits", async () => {
  const { client, call, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(thaiTools),
    );
    const search = tools.find(
      (tool) => tool.name === "search_thai_dip_statutes",
    );
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
        .filter((tool) => thaiTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const result = await call("search_thai_dip_statutes", {
      query: "trade secrets",
      statute: "trade secrets",
      per_page: 1,
    });
    expect(result.summary).toBe(
      "Thailand IP statutes — `trade secrets` (statute=trade secrets): 1 hit (page 1). Unofficial English translations; the Thai text controls.",
    );
    expect(result.more_available).toBe(true);
    expect(result.items[0]).toMatchObject({
      statute: "trade_secrets",
      section_label: expect.stringMatching(/^Section \d+ Trade Secrets Act$/),
      snippet: expect.stringContaining("<mark>"),
      rank: expect.any(Number),
    });
    expect(result.provenance).toMatchObject({
      source_name: "Thailand DIP — IP statutes in English (WIPO Lex)",
      source_url: "https://www.wipo.int/wipolex/en/members/profile/TH",
      corpus_version: "WIPO Lex English translations, 2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
    });
    const all = await call("search_thai_dip_statutes", {
      query: "registrable distinctive",
    });
    expect(all.summary).toStartWith(
      "Thailand IP statutes — `registrable distinctive` (statute=all): 1 hit (page 1).",
    );
  } finally {
    await close();
  }
});

test("get_thai_dip_section reads one citation or a list, reporting misses", async () => {
  const { call, client, close } = await connect("full");
  try {
    const single = await call("get_thai_dip_section", {
      citation: "Section 6 Trade Secrets Act",
    });
    expect(single.summary).toBe(
      "**Section 6 Trade Secrets Act** (unofficial English translation; the Thai text controls)",
    );
    expect(single.items).toHaveLength(1);
    expect(single.items[0]).toMatchObject({
      statute: "trade_secrets",
      section_number: "6",
      title: null,
      text: expect.stringContaining("contrary to honest trade practices"),
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/17163",
      authority: expect.stringContaining("Thai text"),
    });
    expect(single.items[0]).not.toHaveProperty("provenance");
    expect(single.not_found).toEqual([]);

    const many = await call("get_thai_dip_section", {
      citation: [
        "Section 36 bis Patent Act",
        "Patent Act s. 36",
        "Section 109/1 Trademark Act",
        "Section 999 Patent Act",
        "nonsense",
      ],
    });
    expect(many.summary).toBe(
      "Fetched 3 of 5 Thai sections. Not found: Section 999 Patent Act, nonsense.",
    );
    expect(many.items.map((item) => item.section_label)).toEqual([
      "Section 36bis Patent Act",
      "Section 36 Patent Act",
      "Section 109/1 Trademark Act",
    ]);
    expect(many.not_found).toEqual(["Section 999 Patent Act", "nonsense"]);

    const missing = await call("get_thai_dip_section", {
      citation: "Section 999 Patent Act",
    });
    expect(missing.summary).toBe(
      "Thailand section 'Section 999 Patent Act' — not found.",
    );
    expect(missing.items).toEqual([]);
    expect(missing.provenance.corpus_version).toBe(
      "WIPO Lex English translations, 2026-10-26",
    );

    const content = (
      await client.readResource(THAI_DIP_STATUTES_STATUS_URI)
    )[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    ) as {
      available: boolean;
      authority: string;
      statutes: { statute: string; version: string }[];
    };
    expect(status.available).toBe(true);
    expect(status.authority).toContain("only authoritative version");
    expect(status.statutes.map((item) => item.statute)).toEqual([
      "patent",
      "trademark",
      "copyright",
      "trade_secrets",
    ]);
    expect(status.statutes[3]?.version).toContain(
      "Trade Secrets Act (No. 2) B.E. 2558 (2015)",
    );
  } finally {
    await close();
  }
});

test("the curated toolset does not expose the Thailand statutes tools", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => thaiTools.includes(name))).toEqual([]);
  } finally {
    await close();
  }
});

test("Bun HTTP serves Thailand statutes tools only to tokens with thai_dip:read", async () => {
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
  const reader = new ThaiDipStatutesClient({ corpusPath: fixture });
  const server = createServer({
    thaiDipStatutes: reader,
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
      expect(names.filter((name) => thaiTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_thai_dip_statutes", { query: "patent" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const thai = await Client.connect(url, {
      auth: new BearerAuth(token("thai_dip:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await thai.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(thaiTools),
      );
      const result = await thai.callTool<Envelope>("get_thai_dip_section", {
        citation: "Section 28bis Trademark Act",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.statute).toBe("trademark");
    } finally {
      await thai.close();
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
    "b8cbb3671b86ea3ec4e542a35d77634923bd6b177bf0bfe219764c78e71d175d",
  );
});

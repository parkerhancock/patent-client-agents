import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { IpophlStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { IPOPHL_STATUTES_STATUS_URI } from "../packages/mcp/src/ipophl-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "ipophl-statutes",
  "ipophl_statutes.db",
);
const ipophlTools = ["search_ipophl_statutes", "get_ipophl_section"];
const VERSION = "LawPhil, Acts as enacted, 2026-10-26";
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const reader = new IpophlStatutesClient({ corpusPath: fixture });
  const server = createServer({ toolset, ipophlStatutes: reader });
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

test("search_ipophl_statutes returns ranked hits and says the text is as enacted", async () => {
  const { client, call, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(ipophlTools),
    );
    const search = tools.find((tool) => tool.name === "search_ipophl_statutes");
    expect(Object.keys(search?.inputSchema.properties ?? {}).sort()).toEqual([
      "page",
      "per_page",
      "query",
      "sort",
      "statute",
      "syntax",
    ]);
    for (const tool of tools.filter((item) => ipophlTools.includes(item.name)))
      expect(tool.description).toContain("not consolidated into the Code");
    expect(
      tools
        .filter((tool) => ipophlTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const result = await call("search_ipophl_statutes", {
      query: "patent",
      statute: "IP Code",
      per_page: 1,
    });
    expect(result.summary).toBe(
      "IPOPHL Philippines statutes — `patent` (statute=IP Code): 1 hit (page 1).",
    );
    expect(result.more_available).toBe(true);
    expect(result.items[0]).toMatchObject({
      statute: "ra8293",
      section_label: expect.stringMatching(/^Section \d+ RA 8293$/),
      snippet: expect.stringContaining("<mark>"),
      rank: expect.any(Number),
    });
    expect(result.provenance).toMatchObject({
      source_name: "IPOPHL Philippines — IP Code and amending Acts (LawPhil)",
      source_url:
        "https://lawphil.net/statutes/repacts/ra1997/ra_8293_1997.html",
      corpus_version: VERSION,
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
    });
    const all = await call("search_ipophl_statutes", {
      query: "Bureau of Copyright",
      syntax: "adj",
    });
    expect(all.summary).toBe(
      "IPOPHL Philippines statutes — `Bureau of Copyright` (statute=all): 1 hit (page 1).",
    );
    expect(all.items[0]?.section_label).toBe("Section 3 RA 10372");
  } finally {
    await close();
  }
});

test("get_ipophl_section reads one citation or a list, with amendment pointers and misses", async () => {
  const { call, client, close } = await connect("full");
  try {
    const single = await call("get_ipophl_section", {
      citation: "Section 22 IP Code",
    });
    expect(single.summary).toBe(
      "**Section 22 RA 8293** — Non-Patentable Inventions (as enacted; see Section 5 RA 9502)",
    );
    expect(single.items).toHaveLength(1);
    expect(single.items[0]).toMatchObject({
      statute: "ra8293",
      section_number: "22",
      title: "Non-Patentable Inventions",
      amended_by: ["Section 5 RA 9502"],
      text: expect.stringContaining("22.1. Discoveries"),
      source_url:
        "https://lawphil.net/statutes/repacts/ra1997/ra_8293_1997.html",
    });
    expect(single.items[0]).not.toHaveProperty("provenance");
    expect(single.not_found).toEqual([]);

    const plain = await call("get_ipophl_section", {
      citation: "Sec. 21 RA 8293",
    });
    expect(plain.summary).toBe(
      "**Section 21 RA 8293** — Patentable Inventions",
    );

    const many = await call("get_ipophl_section", {
      citation: [
        "Section 22 IP Code",
        "Section 5 RA 9502",
        "Section 93-A IP Code",
        "nonsense",
      ],
    });
    expect(many.summary).toBe(
      "Fetched 2 of 4 IPOPHL sections. Not found: Section 93-A IP Code, nonsense.",
    );
    expect(many.items.map((item) => item.section_label)).toEqual([
      "Section 22 RA 8293",
      "Section 5 RA 9502",
    ]);
    expect(many.items[1]?.title).toBeNull();
    expect(many.not_found).toEqual(["Section 93-A IP Code", "nonsense"]);

    const missing = await call("get_ipophl_section", {
      citation: "Section 999 IP Code",
    });
    expect(missing.summary).toBe(
      "IPOPHL Philippines section 'Section 999 IP Code' — not found.",
    );
    expect(missing.items).toEqual([]);
    expect(missing.provenance.corpus_version).toBe(VERSION);

    const content = (await client.readResource(IPOPHL_STATUTES_STATUS_URI))[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    ) as {
      available: boolean;
      text_status: string;
      statutes: { statute: string }[];
    };
    expect(status.available).toBe(true);
    expect(status.text_status).toContain("as enacted");
    expect(status.statutes.map((item) => item.statute)).toEqual([
      "ra8293",
      "ra9150",
      "ra9502",
      "ra10372",
    ]);
  } finally {
    await close();
  }
});

test("the curated toolset does not expose the IPOPHL statutes tools", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => ipophlTools.includes(name))).toEqual([]);
  } finally {
    await close();
  }
});

test("Bun HTTP serves IPOPHL statutes tools only to tokens with ipophl:read", async () => {
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
  const reader = new IpophlStatutesClient({ corpusPath: fixture });
  const server = createServer({
    ipophlStatutes: reader,
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
      auth: new BearerAuth(token("ilpo:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names).toContain("search_ilpo_statutes");
      expect(names.filter((name) => ipophlTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_ipophl_statutes", { query: "patent" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const ipophl = await Client.connect(url, {
      auth: new BearerAuth(token("ipophl:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await ipophl.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(ipophlTools),
      );
      const result = await ipophl.callTool<Envelope>("get_ipophl_section", {
        citation: "Section 3 RA 10372",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.statute).toBe("ra10372");
    } finally {
      await ipophl.close();
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
    "e279c6e4ff6bd71c563d78ddc96a5ecb707bf5fcd6567d0e395e00b6a93ea4f7",
  );
});

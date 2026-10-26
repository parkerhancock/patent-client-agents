import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { KipoStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { KIPO_STATUTES_STATUS_URI } from "../packages/mcp/src/kipo-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "kipo-statutes",
  "kipo_statutes.db",
);
const kipoTools = ["search_kipo_statutes", "get_kipo_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const reader = new KipoStatutesClient({ corpusPath: fixture });
  const server = createServer({ toolset, kipoStatutes: reader });
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

test("search_kipo_statutes takes the statute-search parameters and returns marked hits", async () => {
  const { client, call, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(kipoTools),
    );
    const search = tools.find((tool) => tool.name === "search_kipo_statutes");
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
        .filter((tool) => kipoTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);
    expect(search?.description).toContain("Korean text controls");

    const result = await call("search_kipo_statutes", {
      query: "trade secret",
      statute: "trade secrets",
      per_page: 1,
    });
    expect(result.summary).toBe(
      "KIPO Korea statutes — `trade secret` (statute=trade secrets): 1 hit (page 1).",
    );
    expect(result.more_available).toBe(true);
    expect(result.items[0]).toMatchObject({
      statute: "unfair_competition",
      section_label: expect.stringMatching(
        /^Article \d+ Unfair Competition Prevention and Trade Secret Protection Act$/,
      ),
      snippet: expect.stringContaining("<mark>"),
      rank: expect.any(Number),
    });
    expect(result.provenance).toMatchObject({
      source_name: "KIPO Korea — Statutes (KLRI English translations)",
      source_url: "https://elaw.klri.re.kr/eng_service/main.do",
      corpus_version: "KLRI English translations (elaw.klri.re.kr), 2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
    });
    const all = await call("search_kipo_statutes", { query: "fair use" });
    expect(all.summary).toBe(
      "KIPO Korea statutes — `fair use` (statute=all): 2 hits (page 1).",
    );
  } finally {
    await close();
  }
});

test("get_kipo_section reads one citation or a list, reporting misses", async () => {
  const { call, client, close } = await connect("full");
  try {
    const single = await call("get_kipo_section", {
      citation: "Patent Act Art. 29(1)",
    });
    expect(single.summary).toBe(
      "**Article 29 Patent Act** — Requirements for Patent Registration",
    );
    expect(single.items).toHaveLength(1);
    expect(single.items[0]).toMatchObject({
      statute: "patent",
      section_number: "29",
      title: "Requirements for Patent Registration",
      text: expect.stringContaining("industrial applicability"),
      source_url:
        "https://elaw.klri.re.kr/eng_service/lawView.do?hseq=68595&lang=ENG",
    });
    expect(single.items[0]).not.toHaveProperty("provenance");
    expect(single.not_found).toEqual([]);

    const many = await call("get_kipo_section", {
      citation: [
        "Article 7-2 Patent Act",
        "Article 35-5 Copyright Act",
        "Article 999 Patent Act",
        "nonsense",
      ],
    });
    expect(many.summary).toBe(
      "Fetched 2 of 4 KIPO articles. Not found: Article 999 Patent Act, nonsense.",
    );
    expect(many.items.map((item) => item.section_label)).toEqual([
      "Article 7-2 Patent Act",
      "Article 35-5 Copyright Act",
    ]);
    expect(many.not_found).toEqual(["Article 999 Patent Act", "nonsense"]);

    const deleted = await call("get_kipo_section", {
      citation: "Article 26 Patent Act",
    });
    expect(deleted.summary).toBe("**Article 26 Patent Act** — (no title)");

    const missing = await call("get_kipo_section", {
      citation: "Article 999 Patent Act",
    });
    expect(missing.summary).toBe(
      "KIPO Korea article 'Article 999 Patent Act' — not found.",
    );
    expect(missing.items).toEqual([]);
    expect(missing.provenance.corpus_version).toBe(
      "KLRI English translations (elaw.klri.re.kr), 2026-10-26",
    );

    const content = (await client.readResource(KIPO_STATUTES_STATUS_URI))[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    ) as {
      available: boolean;
      authority_note: string;
      statutes: { statute: string; version: string }[];
    };
    expect(status.available).toBe(true);
    expect(status.authority_note).toContain("Korean text controls");
    expect(status.statutes.map((item) => item.statute)).toEqual([
      "patent",
      "utility_model",
      "design",
      "trademark",
      "unfair_competition",
      "invention_promotion",
      "copyright",
    ]);
    expect(status.statutes[0]?.version).toBe("Act No. 20322, Feb. 20, 2024");
  } finally {
    await close();
  }
});

test("the curated toolset does not expose the KIPO statutes tools", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => kipoTools.includes(name))).toEqual([]);
  } finally {
    await close();
  }
});

test("Bun HTTP serves KIPO statutes tools only to tokens with kipo:read", async () => {
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
  const reader = new KipoStatutesClient({ corpusPath: fixture });
  const server = createServer({
    kipoStatutes: reader,
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
      expect(names.filter((name) => kipoTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_kipo_statutes", { query: "patent" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const kipo = await Client.connect(url, {
      auth: new BearerAuth(token("kipo:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await kipo.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(kipoTools),
      );
      const result = await kipo.callTool<Envelope>("get_kipo_section", {
        citation: "Article 34 Trademark Act",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.statute).toBe("trademark");
    } finally {
      await kipo.close();
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
    "b0adf0ef56b2190faa0da9ddf70de85b19fac328a587c31649bca1020f54bbba",
  );
});

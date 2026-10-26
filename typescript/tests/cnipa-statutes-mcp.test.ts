import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { CnipaStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { CNIPA_STATUTES_STATUS_URI } from "../packages/mcp/src/cnipa-statutes.js";
import { createServer } from "../packages/mcp/src/index.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "cnipa-statutes",
  "cnipa_statutes.db",
);
const cnipaTools = ["search_cnipa_statutes", "get_cnipa_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const reader = new CnipaStatutesClient({ corpusPath: fixture });
  const server = createServer({ toolset, cnipaStatutes: reader });
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

test("search_cnipa_statutes keeps the statute tools' parameters, hits and summary", async () => {
  const { client, call, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(cnipaTools),
    );
    const search = tools.find((tool) => tool.name === "search_cnipa_statutes");
    expect(Object.keys(search?.inputSchema.properties ?? {}).sort()).toEqual([
      "page",
      "per_page",
      "query",
      "sort",
      "statute",
      "syntax",
    ]);
    expect(search?.description).toContain("the Chinese text controls");
    expect(
      tools
        .filter((tool) => cnipaTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const result = await call("search_cnipa_statutes", {
      query: "trade secret",
      statute: "trade secrets",
      per_page: 1,
    });
    expect(result.summary).toBe(
      "CNIPA China statutes — `trade secret` (statute=trade secrets): 1 hit (page 1).",
    );
    expect(result.more_available).toBe(true);
    expect(result.items[0]).toMatchObject({
      statute: "anti_unfair_competition",
      section_label: expect.stringMatching(
        /^Article \d+ Anti-Unfair Competition Law$/,
      ),
      snippet: expect.stringContaining("<mark>"),
      rank: expect.any(Number),
    });
    expect(result.provenance).toMatchObject({
      source_name: "CNIPA China — Statutes (WIPO Lex)",
      source_url: "https://www.wipo.int/wipolex/en/members/profile/CN",
      corpus_version: "WIPO Lex English translations, 2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
    });
    const all = await call("search_cnipa_statutes", {
      query: "dyslexics",
    });
    expect(all.summary).toBe(
      "CNIPA China statutes — `dyslexics` (statute=all): 1 hit (page 1).",
    );
  } finally {
    await close();
  }
});

test("get_cnipa_section reads one citation or a list, reporting misses", async () => {
  const { call, client, close } = await connect("full");
  try {
    const single = await call("get_cnipa_section", {
      citation: "Patent Law Art. 22(3)",
    });
    expect(single.summary).toBe(
      "**Article 22 Patent Law** — Chapter II Requirements for Granting Patent Rights",
    );
    expect(single.items).toHaveLength(1);
    expect(single.items[0]).toMatchObject({
      statute: "patent_law",
      section_number: "22",
      text: expect.stringContaining("prominent substantive features"),
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/21027",
    });
    expect(single.items[0]).not.toHaveProperty("provenance");
    expect(single.not_found).toEqual([]);

    const many = await call("get_cnipa_section", {
      citation: [
        "Article 9 AUCL",
        "Rule 20 Implementing Regulations",
        "Article 20 Implementing Regulations",
        "Article 999 Patent Law",
      ],
    });
    expect(many.summary).toBe(
      "Fetched 2 of 4 CNIPA provisions. Not found: Article 20 Implementing Regulations, Article 999 Patent Law.",
    );
    expect(many.items.map((item) => item.section_label)).toEqual([
      "Article 9 Anti-Unfair Competition Law",
      "Rule 20 Patent Implementing Regulations",
    ]);

    const missing = await call("get_cnipa_section", {
      citation: "Article 999 Patent Law",
    });
    expect(missing.summary).toBe(
      "CNIPA China provision 'Article 999 Patent Law' — not found.",
    );
    expect(missing.items).toEqual([]);
    expect(missing.provenance.corpus_version).toBe(
      "WIPO Lex English translations, 2026-10-26",
    );

    const content = (await client.readResource(CNIPA_STATUTES_STATUS_URI))[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    ) as {
      available: boolean;
      notice: string;
      statutes: { statute: string; translation_version: string }[];
    };
    expect(status.available).toBe(true);
    expect(status.notice).toContain("the Chinese text controls");
    expect(status.statutes.map((item) => item.statute)).toEqual([
      "patent_law",
      "patent_regulations",
      "trademark_law",
      "trademark_regulations",
      "anti_unfair_competition",
      "copyright_law",
    ]);
    expect(status.statutes[2]?.translation_version).toContain("2019");
  } finally {
    await close();
  }
});

test("the curated toolset does not expose the CNIPA statutes tools", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => cnipaTools.includes(name))).toEqual([]);
  } finally {
    await close();
  }
});

test("Bun HTTP serves CNIPA statutes tools only to tokens with cnipa:read", async () => {
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
  const reader = new CnipaStatutesClient({ corpusPath: fixture });
  const server = createServer({
    cnipaStatutes: reader,
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
      expect(names.filter((name) => cnipaTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_cnipa_statutes", { query: "patent" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    // The China SPC IP Court scope does not grant the statutes either.
    const court = await Client.connect(url, {
      auth: new BearerAuth(token("spc:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await court.listTools()).map((tool) => tool.name);
      expect(names.filter((name) => cnipaTools.includes(name))).toEqual([]);
    } finally {
      await court.close();
    }
    const cnipa = await Client.connect(url, {
      auth: new BearerAuth(token("cnipa:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await cnipa.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(cnipaTools),
      );
      const result = await cnipa.callTool<Envelope>("get_cnipa_section", {
        citation: "Article 13 Trademark Law",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.statute).toBe("trademark_law");
    } finally {
      await cnipa.close();
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
    "55faf434518fb0e5c1fb9709f276f5abf2c1560f2313c94d13068f96a265fa28",
  );
});

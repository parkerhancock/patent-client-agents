import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";
import {
  CorpusError,
  parseTwTradeSecretsCitation,
  TW_TRADE_SECRETS_ARTICLES,
  TW_TRADE_SECRETS_SOURCE,
  TwTradeSecretsClient,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { TW_TRADE_SECRETS_STATUS_URI } from "../packages/mcp/src/tw-trade-secrets.js";
import { parseLawAll, sha256 } from "../scripts/build-tw-trade-secrets-data.js";

const fixtureDir = join(import.meta.dir, "fixtures", "tw-trade-secrets");
const tools = ["search_tw_trade_secrets", "get_tw_trade_secrets_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

test("the bundled module is exactly what the archived official page generates", async () => {
  const bytes = new Uint8Array(
    gunzipSync(await readFile(join(fixtureDir, "J0080028-en.html.gz"))),
  );
  const source = JSON.parse(
    await readFile(join(fixtureDir, "source.json"), "utf8"),
  ) as { retrieved_at: string; html_sha256: string };
  expect(sha256(bytes)).toBe(source.html_sha256);
  expect(source.html_sha256).toBe(TW_TRADE_SECRETS_SOURCE.html_sha256);
  const law = parseLawAll(new TextDecoder().decode(bytes));
  expect(law.articles).toEqual(
    TW_TRADE_SECRETS_ARTICLES.map((article) => ({ ...article })),
  );
  expect(source.retrieved_at).toBe(TW_TRADE_SECRETS_SOURCE.retrieved_at);
  expect(law.amended_date).toBe("2020-01-15");
  expect(TW_TRADE_SECRETS_ARTICLES.map((row) => row.section)).toEqual([
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "13-1",
    "13-2",
    "13-3",
    "13-4",
    "13-5",
    "14",
    "14-1",
    "14-2",
    "14-3",
    "14-4",
    "15",
    "16",
  ]);
  expect(() => parseLawAll("<html></html>")).toThrow("expected LawAll");
});

test("citations parse in Python's forms and the common ones Python rejected", () => {
  const cases: [string, string][] = [
    ["Art. 2 Trade Secrets Act", "2"],
    ["Section 13 Trade Secrets Act", "13"],
    ["Art. 13-1", "13-1"],
    ["13", "13"],
    ["13-1", "13-1"],
    ["Sec. 13-1", "13-1"],
    ["S. 13", "13"],
    ["article 13 of the trade secrets act", "13"],
    ["Art.13", "13"],
    ["Article 13–1", "13-1"],
    ["§ 10", "10"],
    ["Trade Secrets Act Art. 10", "10"],
    ["Taiwan Trade Secrets Act, Article 12", "12"],
  ];
  for (const [input, want] of cases)
    expect([input, parseTwTradeSecretsCitation(input)]).toEqual([input, want]);
  for (const bad of ["", "Art.", "Patent Act 2", "13-1-2", "Art. 2(1)"])
    expect(() => parseTwTradeSecretsCitation(bad)).toThrow(CorpusError);
});

test("library get, search, sort, paging and status over the bundled text", async () => {
  const client = new TwTradeSecretsClient();
  try {
    const article = await client.getSection("Art. 13-1 Trade Secrets Act");
    expect(article).toMatchObject({
      section: "13-1",
      title: null,
      amended_date: "2020-01-15",
      corpus_version: "snapshot-2026-10-22",
      provenance: {
        source_url: TW_TRADE_SECRETS_SOURCE.source_url,
        cache_hit: true,
        corpus_synced_at: "2026-10-22T11:17:17.000Z",
      },
    });
    expect(article?.text).toContain("NT$1 million and NT$10 million");
    expect(await client.getSection("99")).toBeNull();

    // Porter stemming: 'damage' matches 'damages' in Articles 12 and 13.
    const damages = await client.search({ query: "damage" });
    expect(damages.hits.map((hit) => hit.section).sort()).toEqual(["12", "13"]);
    expect(damages.hits[0]?.snippet).toContain("<mark>damages</mark>");
    expect(damages.has_more).toBe(false);

    const outline = await client.search({
      query: "trade secret",
      sort: "outline",
      limit: 5,
    });
    expect(outline.hits.map((hit) => hit.section)).toEqual([
      "1",
      "2",
      "3",
      "4",
      "5",
    ]);
    expect(outline.has_more).toBe(true);
    const next = await client.search({
      query: "trade secret",
      sort: "outline",
      limit: 5,
      offset: 5,
    });
    expect(next.hits[0]?.section).toBe("6");
    // Statutory order, not Python's string order ("10" < "2").
    const all = await client.search({
      query: "trade secret",
      sort: "outline",
      limit: 100,
    });
    const order = all.hits.map((hit) => hit.section);
    expect(order.indexOf("2")).toBeLessThan(order.indexOf("10"));
    expect(order.indexOf("13")).toBeLessThan(order.indexOf("13-1"));
    expect(order.indexOf("13-3")).toBeLessThan(order.indexOf("14"));

    // Caller input is text: FTS5 operators neither run nor raise.
    expect((await client.search({ query: "NOT" })).hits.length).toBeGreaterThan(
      0,
    );
    // Python raises an FTS5 syntax error for a trailing AND; here it is a word.
    expect((await client.search({ query: "damages AND" })).hits.length).toBe(2);
    expect(
      (await client.search({ query: "imprisonment zzzz", syntax: "or" })).hits
        .length,
    ).toBeGreaterThan(0);
    expect(
      (await client.search({ query: "reasonable measures", syntax: "adj" }))
        .hits[0]?.section,
    ).toBe("2");
    expect((await client.search({ query: "  " })).hits).toEqual([]);

    expect(await client.getCorpusStatus()).toMatchObject({
      available: true,
      section_count: 25,
      corpus_version: "snapshot-2026-10-22",
      amended_date: "2020-01-15",
      bundled: true,
    });
    const controller = new AbortController();
    controller.abort();
    await expect(
      client.search({ query: "damages", signal: controller.signal }),
    ).rejects.toThrow("cancelled");
  } finally {
    client.close();
  }
});

async function connect(toolset: "full" | "curated") {
  const server = createServer({ toolset });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    async close() {
      await client.close();
      await server.close();
    },
  };
}

test("MCP tools return Python's envelopes, lean stubs and not_found", async () => {
  const { client, close } = await connect("full");
  try {
    const listed = await client.listTools();
    expect(
      listed
        .filter((tool) => tools.includes(tool.name))
        .map((tool) => tool.name)
        .sort(),
    ).toEqual([...tools].sort());
    const search = await client.callTool<Envelope>("search_tw_trade_secrets", {
      query: "damages",
    });
    expect(search.structuredContent?.summary).toBe(
      "TW Trade Secrets Act — `damages`: 2 hits (corpus snapshot-2026-10-22).",
    );
    expect(Object.keys(search.structuredContent?.items[0] ?? {})).toEqual([
      "section",
      "title",
      "snippet",
    ]);
    expect(search.structuredContent?.provenance).toMatchObject({
      corpus_version: "snapshot-2026-10-22",
      connector_version: "0.1.0",
    });
    const full = await client.callTool<Envelope>("search_tw_trade_secrets", {
      query: "trade secret",
      limit: 2,
      full: true,
      sort: "outline",
    });
    expect(full.structuredContent?.items[0]).toHaveProperty("rank");
    expect(full.structuredContent?.more_available).toBe(true);
    expect(full.structuredContent?.summary).toEndWith("(more available).");

    const one = await client.callTool<Envelope>(
      "get_tw_trade_secrets_section",
      { citation: "Art. 2 Trade Secrets Act" },
    );
    expect(one.structuredContent?.summary).toBe(
      "**Trade Secrets Act Art. 2**\nSource: Taiwan Trade Secrets Act corpus (snapshot-2026-10-22)",
    );
    expect(one.structuredContent?.items[0]?.text).toContain(
      "reasonable measures",
    );
    const many = await client.callTool<Envelope>(
      "get_tw_trade_secrets_section",
      { citation: ["Art. 13", "99", "nonsense", "13-1"] },
    );
    expect(many.structuredContent?.items.map((item) => item.section)).toEqual([
      "13",
      "13-1",
    ]);
    expect(many.structuredContent?.not_found).toEqual(["99", "nonsense"]);
    expect(many.structuredContent?.summary).toBe(
      "Fetched 2 of 4 Taiwan Trade Secrets Articles. Not found: 99, nonsense.",
    );
    await expect(
      client.callTool("get_tw_trade_secrets_section", { citation: "99" }),
    ).rejects.toThrow("not found");

    const content = (await client.readResource(TW_TRADE_SECRETS_STATUS_URI))[0];
    expect(
      JSON.parse(content && "text" in content ? content.text : "{}"),
    ).toMatchObject({ available: true, section_count: 25 });
  } finally {
    await close();
  }
});

test("the curated facade routes tw_trade_secrets with the statute default syntax", async () => {
  const { client, close } = await connect("curated");
  try {
    // Default syntax for a statute corpus is 'and'; Python sent 'adj'.
    const hits = await client.callTool<Envelope>("search_legal_reference", {
      corpus: "tw_trade_secrets",
      query: "secrecy reasonable",
    });
    expect(hits.structuredContent?.items[0]?.section).toBe("2");
    const phrase = await client.callTool<Envelope>("search_legal_reference", {
      corpus: "tw_trade_secrets",
      query: "secrecy reasonable",
      syntax: "adj",
    });
    expect(phrase.structuredContent?.items).toEqual([]);
    const article = await client.callTool<Envelope>("get_legal_reference", {
      corpus: "tw_trade_secrets",
      identifier: "Article 13-2",
    });
    expect(article.structuredContent?.items[0]?.text).toContain(
      "mainland China, Hong Kong, or Macau",
    );
    await expect(
      client.callTool("get_legal_reference", {
        corpus: "tw_trade_secrets",
        identifier: "Art. 99",
      }),
    ).rejects.toThrow("not found");
    await expect(
      client.callTool("search_legal_reference", {
        corpus: "tw_trade_secrets",
        query: "x",
        version: "2019",
      }),
    ).rejects.toThrow("only for uspto_mpep");
  } finally {
    await close();
  }
});

test("Bun HTTP serves the Taiwan tools only to tokens with tw:read", async () => {
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
  const server = createServer({
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
      auth: new BearerAuth(token("upc:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names.filter((name) => tools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_tw_trade_secrets", { query: "damages" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const tw = await Client.connect(url, {
      auth: new BearerAuth(token("tw:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const result = await tw.callTool<Envelope>("search_tw_trade_secrets", {
        query: "damages",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items.length).toBe(2);
    } finally {
      await tw.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

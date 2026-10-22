import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { LegifranceIpClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { LEGIFRANCE_IP_STATUS_URI } from "../packages/mcp/src/legifrance-ip.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "legifrance-ip",
  "legifrance_ip.db",
);
const tools = ["search_legifrance_ip", "get_legifrance_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};
const VERSION = "LEGI 20261021-213023";

async function connect() {
  const reader = new LegifranceIpClient({ corpusPath: fixture });
  const server = createServer({ legifranceIp: reader });
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

test("search_legifrance_ip keeps Python's parameters, lean hits and summary", async () => {
  const { client, call, close } = await connect();
  try {
    const listed = await client.listTools();
    const search = listed.find((tool) => tool.name === "search_legifrance_ip");
    expect(Object.keys(search?.inputSchema.properties ?? {}).sort()).toEqual([
      "limit",
      "offset",
      "query",
      "statute",
    ]);
    expect(
      listed
        .filter((tool) => tools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);
    const result = await call("search_legifrance_ip", {
      query: "brevetabilité",
    });
    expect(result.summary).toBe(
      `Légifrance IP (${VERSION}) — \`brevetabilité\`: ${result.items.length} hit${result.items.length === 1 ? "" : "s"}.`,
    );
    expect(Object.keys(result.items[0] ?? {}).sort()).toEqual([
      "section",
      "snippet",
      "statute",
      "title",
    ]);
    expect(result.provenance).toMatchObject({
      source_name:
        "Légifrance — French IP statutes (CPI + Code de commerce L.151 trade secrets)",
      corpus_version: VERSION,
      corpus_synced_at: "2026-10-21T00:00:00.000Z",
    });
    const filtered = await call("search_legifrance_ip", {
      query: "secret",
      statute: "Code de commerce",
    });
    expect(filtered.summary).toContain("[Code de commerce]");
    expect(
      filtered.items.every((item) => item.statute === "Code de commerce"),
    ).toBe(true);
    const none = await call("search_legifrance_ip", { query: "zzzzqqq" });
    expect(none.items).toEqual([]);
    expect(none.summary).toContain("0 hits.");
    await expect(
      client.callTool("search_legifrance_ip", {
        query: "x",
        statute: "Code civil",
      }),
    ).rejects.toThrow();
    const paged = await call("search_legifrance_ip", {
      query: "brevet",
      limit: 1,
    });
    expect(paged.more_available).toBe(true);
    expect(paged.summary).toEndWith("1 hit (more available).");
  } finally {
    await close();
  }
});

test("get_legifrance_section returns Python's envelope, order and not_found", async () => {
  const { client, call, close } = await connect();
  try {
    const one = await call("get_legifrance_section", {
      citation: "L. 611-10 CPI",
    });
    expect(one.summary).toBe(
      `**Légifrance IP ${VERSION} — CPI art. L611-10: Section 3 : Inventions brevetables**`,
    );
    expect(one.items[0]).toMatchObject({
      statute: "CPI",
      section: "L611-10",
      text: expect.stringContaining("Sont brevetables"),
      url: "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000019298703",
    });
    const many = await call("get_legifrance_section", {
      citation: ["L. 611-1 CPI", "L. 151-1 Code de commerce", "L. 711-1 CPI"],
    });
    expect(many.items.map((item) => `${item.statute} ${item.section}`)).toEqual(
      ["CPI L611-1", "Code de commerce L151-1", "CPI L711-1"],
    );
    expect(many.summary).toBe("Fetched 3 of 3 Légifrance IP articles.");
    const missing = await call("get_legifrance_section", {
      citation: ["L. 611-10 CPI", "L. 999-99 CPI"],
    });
    expect(missing.items).toHaveLength(1);
    expect(missing.not_found).toEqual(["L. 999-99 CPI"]);
    expect(missing.summary).toBe(
      "Fetched 1 of 2 Légifrance IP articles. Not found: L. 999-99 CPI.",
    );
    await expect(
      client.callTool("get_legifrance_section", { citation: ["nonsense"] }),
    ).rejects.toThrow("could not parse citation");
    await expect(
      client.callTool("get_legifrance_section", { citation: "L. 999-99 CPI" }),
    ).rejects.toThrow("could not find Légifrance article L999-99");
    const content = (await client.readResource(LEGIFRANCE_IP_STATUS_URI))[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    );
    expect(status).toMatchObject({
      available: true,
      section_count: 13,
      corpus_version: VERSION,
    });
  } finally {
    await close();
  }
});

test("Bun HTTP serves the Légifrance tools only to tokens with legifrance:read", async () => {
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
  const reader = new LegifranceIpClient({ corpusPath: fixture });
  const server = createServer({
    legifranceIp: reader,
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
      auth: new BearerAuth(token("inpibr:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names).toContain("search_inpi_br_statutes");
      expect(names.filter((name) => tools.includes(name))).toEqual([]);
    } finally {
      await other.close();
    }
    const allowed = await Client.connect(url, {
      auth: new BearerAuth(token("legifrance:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const result = await allowed.callTool<Envelope>(
        "get_legifrance_section",
        {
          citation: "L. 151-1 Code de commerce",
        },
      );
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.section).toBe("L151-1");
    } finally {
      await allowed.close();
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
    "a359db0dc77a366003f377ac3111af2d1cf3755712cdb1038d7adfc4c07c85cc",
  );
});

import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { InpiBrStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { INPI_BR_STATUTES_STATUS_URI } from "../packages/mcp/src/inpi-br-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "inpi-br-statutes",
  "inpi_br_statutes.db",
);
const tools = ["search_inpi_br_statutes", "get_inpi_br_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};
const VERSION = "consolidated through Lei nº 14.852, de 3/5/2024";

async function connect() {
  const reader = new InpiBrStatutesClient({ corpusPath: fixture });
  const server = createServer({ inpiBrStatutes: reader });
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

test("search_inpi_br_statutes keeps Python's parameters, lean stubs and summary", async () => {
  const { client, call, close } = await connect();
  try {
    const listed = await client.listTools();
    const search = listed.find(
      (tool) => tool.name === "search_inpi_br_statutes",
    );
    expect(Object.keys(search?.inputSchema.properties ?? {}).sort()).toEqual([
      "full",
      "limit",
      "offset",
      "query",
      "sort",
      "syntax",
    ]);
    expect(
      listed
        .filter((tool) => tools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);
    const lean = await call("search_inpi_br_statutes", {
      query: "concorrência desleal",
    });
    expect(lean.summary).toBe(
      `LPI (${VERSION}) — \`concorrência desleal\`: ${lean.items.length} hit${lean.items.length === 1 ? "" : "s"}.`,
    );
    expect(Object.keys(lean.items[0] ?? {}).sort()).toEqual([
      "article_number",
      "href",
      "snippet",
      "title",
    ]);
    expect(lean.items.map((item) => item.article_number)).toContain("Art. 195");
    expect(lean.provenance).toMatchObject({
      source_name: "INPI Brazil — LPI (Lei 9.279/1996)",
      source_url: expect.stringContaining("camara.leg.br"),
      corpus_version: VERSION,
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
    });
    const english = await call("search_inpi_br_statutes", {
      query: "unfair competition",
    });
    expect(english.items.map((item) => item.article_number)).toContain(
      "Art. 195",
    );
    const full = await call("search_inpi_br_statutes", {
      query: "patente",
      full: true,
      limit: 2,
    });
    expect(full.items[0]).toMatchObject({
      result_url: expect.stringContaining(
        "planalto.gov.br/ccivil_03/leis/l9279.htm#Art",
      ),
      path: expect.any(Array),
      rank: expect.any(Number),
    });
    expect(full.more_available).toBe(true);
    expect(full.summary).toEndWith("2 hits (more available).");
  } finally {
    await close();
  }
});

test("get_inpi_br_section returns Python's envelope, order and not_found", async () => {
  const { call, client, close } = await connect();
  try {
    const one = await call("get_inpi_br_section", { citation: "Art. 6" });
    expect(one.summary).toBe(
      `**LPI (${VERSION}) — Art. 6: Ao autor de invenção ou modelo de utilidade será assegurado o direito de obter a patente que lhe garanta a propriedade,…**\nSource: https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#Art6`,
    );
    expect(one.items).toHaveLength(1);
    expect(one.items[0]).toMatchObject({
      href: "art6",
      text_pt: expect.stringContaining("patente"),
      text_en: expect.stringContaining("patent"),
      html_pt: expect.stringContaining("<p>"),
      version: "current",
    });
    expect(one.not_found).toEqual([]);
    const many = await call("get_inpi_br_section", {
      citation: ["Art. 6", "Art. 125", "Art. 195(XI) LPI"],
    });
    expect(many.items.map((item) => item.href)).toEqual([
      "art6",
      "art125",
      "art195",
    ]);
    expect(many.summary).toBe("Fetched 3 of 3 LPI Articles.");
    const missing = await call("get_inpi_br_section", {
      citation: ["Art. 6", "Art. 9999"],
    });
    expect(missing.items).toHaveLength(1);
    expect(missing.not_found).toEqual(["Art. 9999"]);
    expect(missing.summary).toBe(
      "Fetched 1 of 2 LPI Articles. Not found: Art. 9999.",
    );
    const listOfOne = await call("get_inpi_br_section", {
      citation: ["Art. 9"],
    });
    expect(listOfOne.summary).toBe("LPI Article Art. 9 — not found.");
    await expect(
      client.callTool("get_inpi_br_section", { citation: "Art. 9999" }),
    ).rejects.toThrow("Could not find LPI section 'Art. 9999'.");
    const content = (await client.readResource(INPI_BR_STATUTES_STATUS_URI))[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    );
    expect(status).toMatchObject({
      available: true,
      section_count: 9,
      corpus_version: VERSION,
    });
  } finally {
    await close();
  }
});

test("Bun HTTP serves the LPI tools only to tokens with inpibr:read", async () => {
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
  const reader = new InpiBrStatutesClient({ corpusPath: fixture });
  const server = createServer({
    inpiBrStatutes: reader,
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
      expect(names.filter((name) => tools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_inpi_br_statutes", { query: "marca" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const allowed = await Client.connect(url, {
      auth: new BearerAuth(token("inpibr:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await allowed.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(tools),
      );
      const result = await allowed.callTool<Envelope>("get_inpi_br_section", {
        citation: "Art. 125",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.href).toBe("art125");
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
    "28b5b687cdace276bae4dbdd578bdb71ae63cb3e36df5303cb560506350a6d19",
  );
});

import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { InpiArStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { INPI_AR_STATUTES_STATUS_URI } from "../packages/mcp/src/inpi-ar-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "inpi-ar-statutes",
  "inpi_ar_statutes.db",
);
const arTools = ["search_inpi_ar_statutes", "get_inpi_ar_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const reader = new InpiArStatutesClient({ corpusPath: fixture });
  const server = createServer({ toolset, inpiArStatutes: reader });
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

test("search_inpi_ar_statutes lists its parameters, hits and summary", async () => {
  const { client, call, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(arTools),
    );
    const search = tools.find(
      (tool) => tool.name === "search_inpi_ar_statutes",
    );
    expect(Object.keys(search?.inputSchema.properties ?? {}).sort()).toEqual([
      "page",
      "per_page",
      "query",
      "sort",
      "statute",
      "syntax",
    ]);
    expect(search?.description).toContain("not official Boletín Oficial");
    expect(
      tools
        .filter((tool) => arTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const result = await call("search_inpi_ar_statutes", {
      query: "marca",
      statute: "Ley 22.362",
      per_page: 1,
    });
    expect(result.summary).toBe(
      "INPI Argentina statutes — `marca` (statute=Ley 22.362): 1 hit (page 1).",
    );
    expect(result.more_available).toBe(true);
    expect(result.items[0]).toMatchObject({
      statute: "trademarks",
      section_label: expect.stringMatching(/^Artículo \d+°? Ley 22\.362$/),
      snippet: expect.stringContaining("<mark>"),
      rank: expect.any(Number),
    });
    expect(result.provenance).toMatchObject({
      source_name: "INPI Argentina — Statutes (Infoleg)",
      source_url: "https://www.infoleg.gob.ar/",
      corpus_version: "Infoleg updated texts, 2026-10-26",
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
    });
    const all = await call("search_inpi_ar_statutes", {
      query: "informacion secreta",
    });
    expect(all.summary).toBe(
      "INPI Argentina statutes — `informacion secreta` (statute=all): 1 hit (page 1).",
    );
  } finally {
    await close();
  }
});

test("get_inpi_ar_section reads one citation or a list, reporting misses", async () => {
  const { call, client, close } = await connect("full");
  try {
    const single = await call("get_inpi_ar_section", {
      citation: "Artículo 4 Ley 24.481",
    });
    expect(single.summary).toBe(
      "**Artículo 4° Ley 24.481** — TITULO II — DE LAS PATENTES DE INVENCION / CAPITULO I — PATENTABILIDAD",
    );
    expect(single.items).toHaveLength(1);
    expect(single.items[0]).toMatchObject({
      statute: "patents",
      section_number: "4",
      text: expect.stringContaining("actividad inventiva"),
      source_url:
        "https://servicios.infoleg.gob.ar/infolegInternet/anexos/35000-39999/35001/texact.htm",
    });
    expect(single.items[0]).not.toHaveProperty("provenance");
    expect(single.not_found).toEqual([]);

    const untitled = await call("get_inpi_ar_section", {
      citation: "Art. 1 Ley 24.766",
    });
    expect(untitled.summary).toBe("**Artículo 1° Ley 24.766** — (sin título)");

    const many = await call("get_inpi_ar_section", {
      citation: [
        "Ley 22.362 art. 3",
        "Art. 5 bis Ley 11.723",
        "Artículo 999 Ley 24.481",
        "nonsense",
      ],
    });
    expect(many.summary).toBe(
      "Fetched 2 of 4 INPI Argentina articles. Not found: Artículo 999 Ley 24.481, nonsense.",
    );
    expect(many.items.map((item) => item.section_label)).toEqual([
      "Artículo 3° Ley 22.362",
      "Artículo 5° bis Ley 11.723",
    ]);
    expect(many.not_found).toEqual(["Artículo 999 Ley 24.481", "nonsense"]);

    const missing = await call("get_inpi_ar_section", {
      citation: "Artículo 999 Ley 24.481",
    });
    expect(missing.summary).toBe(
      "INPI Argentina article 'Artículo 999 Ley 24.481' — not found.",
    );
    expect(missing.items).toEqual([]);
    expect(missing.provenance.corpus_version).toBe(
      "Infoleg updated texts, 2026-10-26",
    );

    const content = (await client.readResource(INPI_AR_STATUTES_STATUS_URI))[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    ) as {
      available: boolean;
      notice: string;
      statutes: { statute: string; text_kind: string }[];
    };
    expect(status.available).toBe(true);
    expect(status.notice).toContain("not official Boletín Oficial");
    expect(
      status.statutes.map((item) => `${item.statute}:${item.text_kind}`),
    ).toEqual([
      "patents:texact",
      "trademarks:texact",
      "designs:texact",
      "copyright:texact",
      "trade_secrets:norma",
    ]);
  } finally {
    await close();
  }
});

test("the curated toolset does not expose the INPI Argentina statutes tools", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => arTools.includes(name))).toEqual([]);
  } finally {
    await close();
  }
});

test("Bun HTTP serves INPI Argentina statutes tools only to tokens with inpi_ar:read", async () => {
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
  const reader = new InpiArStatutesClient({ corpusPath: fixture });
  const server = createServer({
    inpiArStatutes: reader,
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
      expect(names.filter((name) => arTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_inpi_ar_statutes", { query: "patente" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const ar = await Client.connect(url, {
      auth: new BearerAuth(token("inpi_ar:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await ar.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(arTools),
      );
      const result = await ar.callTool<Envelope>("get_inpi_ar_section", {
        citation: "Ley 22.362 art. 23",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.statute).toBe("trademarks");
    } finally {
      await ar.close();
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
    "99cce888ab0ae667e39b98d99121c70328940a90c872e6e3480ea2835e86d63d",
  );
});

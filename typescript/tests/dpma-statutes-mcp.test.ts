import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { DpmaStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { DPMA_STATUTES_STATUS_URI } from "../packages/mcp/src/dpma-statutes.js";
import { createServer } from "../packages/mcp/src/index.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "dpma-statutes",
  "dpma_statutes.db",
);
const dpmaTools = ["search_dpma_statutes", "get_dpma_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

async function connect(toolset: "full" | "curated") {
  const reader = new DpmaStatutesClient({ corpusPath: fixture });
  const server = createServer({ toolset, dpmaStatutes: reader });
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

test("search_dpma_statutes keeps Python's parameters, lean stubs and summary", async () => {
  const { client, call, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(dpmaTools),
    );
    const search = tools.find((tool) => tool.name === "search_dpma_statutes");
    expect(Object.keys(search?.inputSchema.properties ?? {}).sort()).toEqual([
      "full",
      "limit",
      "offset",
      "query",
      "sort",
      "statute",
      "syntax",
    ]);
    expect(
      tools
        .filter((tool) => dpmaTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const lean = await call("search_dpma_statutes", {
      query: "Unterlassung",
      statute: "PatG",
    });
    expect(lean.summary).toBe(
      "DPMA Germany statutes (PatG) — `Unterlassung`: 1 hit (corpus snapshot-2026-10-22).",
    );
    expect(lean.items).toEqual([
      {
        statute: "PatG",
        section: "139",
        title: "Unterlassungs- und Schadensersatzanspruch",
        snippet: expect.stringContaining("<mark>Unterlassung</mark>"),
      },
    ]);
    expect(lean.provenance).toMatchObject({
      source_url: "https://www.gesetze-im-internet.de/",
      source_name: "DPMA Germany — IP statutes",
      corpus_version: "snapshot-2026-10-22",
      corpus_synced_at: "2026-10-22T00:00:00.000Z",
      cache_hit: true,
    });
    expect(lean.next_cursor).toBeNull();

    const full = await call("search_dpma_statutes", {
      query: "Gesetzes",
      limit: 1,
      full: true,
    });
    expect(full.summary).toBe(
      "DPMA Germany statutes — `Gesetzes`: 1 hit (corpus snapshot-2026-10-22) (more available).",
    );
    expect(full.more_available).toBe(true);
    expect(full.items[0]?.rank).toEqual(expect.any(Number));
    const next = await call("search_dpma_statutes", {
      query: "Gesetzes",
      limit: 1,
      offset: 1,
      full: true,
    });
    expect(next.items[0]).not.toEqual(full.items[0]);
  } finally {
    await close();
  }
});

test("get_dpma_section returns sections in order with not_found, as Python's FetchedList", async () => {
  const { client, call, close } = await connect("full");
  try {
    const one = await call("get_dpma_section", { citation: "§ 139 PatG" });
    expect(one.summary).toBe(
      "**§ 139 PatG** — Unterlassungs- und Schadensersatzanspruch\nSource: DPMA Germany statutes corpus (snapshot-2026-10-22)",
    );
    expect(one.items).toEqual([
      {
        statute: "PatG",
        section: "139",
        title: "Unterlassungs- und Schadensersatzanspruch",
        text: expect.stringContaining("(1) Wer entgegen"),
      },
    ]);
    expect(one.not_found).toEqual([]);

    const many = await call("get_dpma_section", {
      citation: ["§ 97 UrhG", "§ 4 PatG", "Section 14 MarkenG", "§ 1 BGB"],
    });
    expect(many.items.map((item) => `${item.statute} ${item.section}`)).toEqual(
      ["UrhG 97", "MarkenG 14"],
    );
    expect(many.not_found).toEqual(["§ 4 PatG", "§ 1 BGB"]);
    expect(many.summary).toBe(
      "Fetched 2 of 4 DPMA statute sections. Not found: § 4 PatG, § 1 BGB.",
    );

    // A single missing citation, a bare ambiguous number and an unparseable
    // citation fail the call, as in Python.
    await expect(
      client.callTool("get_dpma_section", { citation: "§ 4 PatG" }),
    ).rejects.toThrow("Section '4' not found in 'PatG'.");
    await expect(
      client.callTool("get_dpma_section", { citation: ["1", "§ 97 UrhG"] }),
    ).rejects.toThrow("ambiguous");
    await expect(
      client.callTool("get_dpma_section", { citation: "Article 54 EPC" }),
    ).rejects.toThrow("Could not parse citation");

    const content = (await client.readResource(DPMA_STATUTES_STATUS_URI))[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    );
    expect(status).toMatchObject({
      available: true,
      section_count: 12,
      corpus_version: "snapshot-2026-10-22",
      artifact_sha256: expect.stringMatching(/^[a-f\d]{64}$/),
    });
  } finally {
    await close();
  }
});

test("the curated facade routes corpus='dpma' with the statute filter and statute default syntax", async () => {
  const { client, call, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => dpmaTools.includes(name))).toEqual([]);

    // Omitted syntax is 'and' for statutes: both terms, anywhere in the section.
    const terms = await call("search_legal_reference", {
      corpus: "dpma",
      query: "Verletzten Unterlassung",
    });
    expect(terms.items.map((item) => item.section).sort()).toEqual([
      "139",
      "97",
    ]);
    expect(terms.next_cursor).toBeNull();
    // An explicit phrase still runs as a phrase.
    expect(
      (
        await call("search_legal_reference", {
          corpus: "dpma",
          query: "Verletzten Unterlassung",
          syntax: "adj",
        })
      ).items,
    ).toEqual([]);
    const filtered = await call("search_legal_reference", {
      corpus: "dpma",
      query: "Verletzten",
      statute: "UrhG",
      full: true,
    });
    expect(filtered.items).toEqual([
      expect.objectContaining({
        statute: "UrhG",
        section: "97",
        rank: expect.any(Number),
      }),
    ]);
    expect(filtered.summary).toContain("DPMA Germany statutes (UrhG)");

    const got = await call("get_legal_reference", {
      corpus: "dpma",
      identifier: "§ 3 PatG",
    });
    expect(got.items).toEqual([
      expect.objectContaining({
        statute: "PatG",
        section: "3",
        title: "Neuheit",
      }),
    ]);
    expect(got.not_found).toEqual([]);
    await expect(
      client.callTool("get_legal_reference", {
        corpus: "dpma",
        identifier: "§ 4 PatG",
      }),
    ).rejects.toThrow("not found");
    await expect(
      client.callTool("search_legal_reference", {
        corpus: "dpma",
        query: "x",
        version: "2020",
      }),
    ).rejects.toThrow("only for uspto_mpep");
  } finally {
    await close();
  }
});

test("Bun HTTP serves DPMA statutes tools only to tokens with dpma:read", async () => {
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
  const reader = new DpmaStatutesClient({ corpusPath: fixture });
  const server = createServer({
    dpmaStatutes: reader,
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
      auth: new BearerAuth(token("upc:read epo:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names).toContain("search_upc_statutes");
      expect(names.filter((name) => dpmaTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_dpma_statutes", { query: "Marke" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const dpma = await Client.connect(url, {
      auth: new BearerAuth(token("dpma:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await dpma.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(dpmaTools),
      );
      const result = await dpma.callTool<Envelope>("get_dpma_section", {
        citation: "§ 14 MarkenG",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.statute).toBe("MarkenG");
    } finally {
      await dpma.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
    reader.close();
  }
});

test("the fixture is the packaged Python build, byte for byte", async () => {
  const bytes = await readFile(fixture);
  expect(new Bun.CryptoHasher("sha256").update(bytes).digest("hex")).toBe(
    "6256d69d7d32325a05c3c8e30c619ed66b61043a4b7879927b700307dcec3b98",
  );
});

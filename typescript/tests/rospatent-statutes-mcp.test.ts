import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { RospatentStatutesClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { ROSPATENT_STATUTES_STATUS_URI } from "../packages/mcp/src/rospatent-statutes.js";

const fixture = join(
  import.meta.dir,
  "fixtures",
  "rospatent-statutes",
  "rospatent_statutes.db",
);
const rospatentTools = ["search_rospatent_statutes", "get_rospatent_section"];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};
const VERSION = "WIPO Lex 22547 English translation, amended up to 2024-03-22";

async function connect(toolset: "full" | "curated") {
  const reader = new RospatentStatutesClient({ corpusPath: fixture });
  const server = createServer({ toolset, rospatentStatutes: reader });
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

test("search_rospatent_statutes returns ranked hits with chapter and provenance", async () => {
  const { client, call, close } = await connect("full");
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(rospatentTools),
    );
    const search = tools.find(
      (tool) => tool.name === "search_rospatent_statutes",
    );
    expect(Object.keys(search?.inputSchema.properties ?? {}).sort()).toEqual([
      "chapter",
      "page",
      "per_page",
      "query",
      "sort",
      "syntax",
    ]);
    expect(
      tools
        .filter((tool) => rospatentTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const result = await call("search_rospatent_statutes", {
      query: "invention",
      chapter: 72,
      per_page: 1,
    });
    expect(result.summary).toBe(
      "Russian Civil Code, Part Four — `invention` (chapter=72): 1 hit (page 1).",
    );
    expect(result.more_available).toBe(true);
    expect(result.items[0]).toMatchObject({
      statute: "civil_code",
      section_label: expect.stringMatching(
        /^Article 1\d{3}(\.\d+)? Civil Code$/,
      ),
      chapter: "Chapter 72. The Patent Law",
      snippet: expect.stringContaining("<mark>"),
      rank: expect.any(Number),
    });
    expect(result.provenance).toMatchObject({
      source_name:
        "Russian Federation — Civil Code, Part Four (WIPO Lex English translation)",
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/22547",
      corpus_version: VERSION,
      corpus_synced_at: "2026-10-26T00:00:00.000Z",
    });
    const all = await call("search_rospatent_statutes", {
      query: "know-how",
      syntax: "exact",
    });
    expect(all.summary).toStartWith(
      "Russian Civil Code, Part Four — `know-how` (chapter=all):",
    );
  } finally {
    await close();
  }
});

test("get_rospatent_section reads one citation or a list, reporting misses", async () => {
  const { call, client, close } = await connect("full");
  try {
    const single = await call("get_rospatent_section", {
      citation: "Civil Code Art. 1350(1)",
    });
    expect(single.summary).toBe(
      "**Article 1350 Civil Code** — The Conditions for Patentability of an Invention",
    );
    expect(single.items).toHaveLength(1);
    expect(single.items[0]).toMatchObject({
      statute: "civil_code",
      section_number: "1350",
      chapter: "Chapter 72. The Patent Law",
      paragraph: "§ 1. Basic Provisions",
      repealed: false,
      text: expect.stringContaining("inventive step"),
      source_url: "https://www.wipo.int/wipolex/en/legislation/details/22547",
    });
    expect(single.items[0]).not.toHaveProperty("provenance");
    expect(single.not_found).toEqual([]);

    const repealed = await call("get_rospatent_section", {
      citation: "Article 1478",
    });
    expect(repealed.summary).toBe(
      "**Article 1478 Civil Code** — repealed (Invalid from June 29, 2023 - Federal Law No. 193-FZ of June 28, 2022)",
    );

    const many = await call("get_rospatent_section", {
      citation: [
        "Art. 1484 CC RF",
        "ст. 1231.1 ГК РФ",
        "Article 1999 Civil Code",
        "Article 6 Patents Law",
      ],
    });
    expect(many.summary).toBe(
      "Fetched 2 of 4 Civil Code articles. Not found: Article 1999 Civil Code, Article 6 Patents Law.",
    );
    expect(many.items.map((item) => item.section_label)).toEqual([
      "Article 1484 Civil Code",
      "Article 1231.1 Civil Code",
    ]);
    expect(many.not_found).toEqual([
      "Article 1999 Civil Code",
      "Article 6 Patents Law",
    ]);

    const missing = await call("get_rospatent_section", {
      citation: "Article 1999 Civil Code",
    });
    expect(missing.summary).toBe(
      "Russian Civil Code article 'Article 1999 Civil Code' — not found.",
    );
    expect(missing.items).toEqual([]);
    expect(missing.provenance.corpus_version).toBe(VERSION);

    const content = (
      await client.readResource(ROSPATENT_STATUTES_STATUS_URI)
    )[0];
    const status = JSON.parse(
      content && "text" in content ? content.text : "{}",
    ) as {
      available: boolean;
      translation_amended_up_to: string;
      russian_amended_up_to: string;
      version_note: string;
    };
    expect(status).toMatchObject({
      available: true,
      translation_amended_up_to: "2024-03-22",
      russian_amended_up_to: "2025-08-03",
    });
    expect(status.version_note).toContain("The Russian text controls.");
  } finally {
    await close();
  }
});

test("the curated toolset does not expose the Russian Civil Code tools", async () => {
  const { client, close } = await connect("curated");
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names.filter((name) => rospatentTools.includes(name))).toEqual([]);
  } finally {
    await close();
  }
});

test("Bun HTTP serves the Russian Civil Code tools only to tokens with rospatent:read", async () => {
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
  const reader = new RospatentStatutesClient({ corpusPath: fixture });
  const server = createServer({
    rospatentStatutes: reader,
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
      expect(names.filter((name) => rospatentTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_rospatent_statutes", { query: "patent" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const rospatent = await Client.connect(url, {
      auth: new BearerAuth(token("rospatent:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await rospatent.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(rospatentTools),
      );
      const result = await rospatent.callTool<Envelope>(
        "get_rospatent_section",
        { citation: "Article 1484 Civil Code" },
      );
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items[0]?.section_number).toBe("1484");
    } finally {
      await rospatent.close();
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
    "791ba534625e2a233ae17963e4a28c4e81a6f08cb9d61df4f0cd82bf4c0ab848",
  );
});

import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { join } from "node:path";
import {
  IposManualsClient,
  IposStatutesClient,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import {
  IPOS_MANUALS_STATUS_URI,
  IPOS_STATUTES_STATUS_URI,
} from "../packages/mcp/src/ipos.js";

const dir = join(import.meta.dir, "fixtures", "ipos");
const iposTools = [
  "search_ipos_statutes",
  "get_ipos_section",
  "list_ipos_statutes",
  "search_ipos_manuals",
  "get_ipos_manual_section",
  "list_ipos_manuals",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  next_cursor: string | null;
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

function readers() {
  return {
    iposStatutes: new IposStatutesClient({
      corpusPath: join(dir, "ipos_statutes.db"),
    }),
    iposManuals: new IposManualsClient({
      corpusPath: join(dir, "ipos_manuals.db"),
    }),
  };
}
async function connect() {
  const corpora = readers();
  const server = createServer({ toolset: "full", ...corpora });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    async close() {
      await client.close();
      await server.close();
      corpora.iposStatutes.close();
      corpora.iposManuals.close();
    },
  };
}

test("IPOS statutes MCP tools keep Python's envelopes, summaries and not_found", async () => {
  const { client, close } = await connect();
  try {
    const tools = await client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining(iposTools),
    );
    expect(
      tools
        .filter((tool) => iposTools.includes(tool.name))
        .every((tool) => tool.annotations?.readOnlyHint && tool.outputSchema),
    ).toBe(true);

    const search = await client.callTool<Envelope>("search_ipos_statutes", {
      query: "inventive step",
      statute: "Patents Act",
    });
    expect(search.structuredContent).toMatchObject({
      summary: expect.stringMatching(
        /^IPOS Singapore statutes — `inventive step` \(statute=Patents Act\): \d+ hits \(page 1\)\.$/,
      ),
      next_cursor: null,
      more_available: false,
      provenance: {
        source_url: "https://www.wipo.int/wipolex/en/members/profile/SG",
        source_name: "IPOS Singapore — IP statutes",
        corpus_version: "2020 Revised Edition, in force from 2025-03-09",
        corpus_synced_at: "2026-10-22T00:00:00.000Z",
        connector_version: "0.1.0",
      },
    });
    expect(
      Object.keys(search.structuredContent?.items[0] ?? {}).sort(),
    ).toEqual([
      "breadcrumb",
      "rank",
      "section_label",
      "short_name",
      "snippet",
      "statute",
      "title",
    ]);
    const paged = await client.callTool<Envelope>("search_ipos_statutes", {
      query: "the",
      per_page: 2,
    });
    expect(paged.structuredContent?.more_available).toBe(true);
    expect(paged.structuredContent?.summary).toEndWith(": 2 hits (page 1).");

    const one = await client.callTool<Envelope>("get_ipos_section", {
      citation: "Section 13 Patents Act",
    });
    expect(one.structuredContent).toMatchObject({
      summary: "**Patents Act § 13** — Patentable inventions",
      not_found: [],
      provenance: {
        source_url: "https://sso.agc.gov.sg/Act/PA1994?ProvIds=pr13-#pr13-",
      },
    });
    expect(one.structuredContent?.items[0]).toMatchObject({
      statute: "patents",
      section_label: "13",
      sso_url: "https://sso.agc.gov.sg/Act/PA1994?ProvIds=pr13-#pr13-",
      text: expect.stringContaining("it involves an inventive step"),
    });
    expect(one.structuredContent?.items[0]).not.toHaveProperty("provenance");

    const sub = await client.callTool<Envelope>("get_ipos_section", {
      citation: "s 27(1) Trade Marks Act",
    });
    expect(sub.structuredContent?.summary).toBe(
      "**Trade Marks Act § 27** — Acts amounting to infringement of registered trade mark\nCited (1) is within this section's text.",
    );

    // Python returns not-found for one citation instead of raising.
    const missing = await client.callTool<Envelope>("get_ipos_section", {
      citation: "Patents Act",
    });
    expect(missing.isError).toBe(false);
    expect(missing.structuredContent).toMatchObject({
      summary: "IPOS section `Patents Act` — not found.",
      items: [],
      not_found: ["Patents Act"],
    });
    const many = await client.callTool<Envelope>("get_ipos_section", {
      citation: [
        "Section 190 Copyright Act",
        "Section 999 Patents Act",
        "First Schedule Trade Marks Act",
      ],
    });
    expect(many.structuredContent).toMatchObject({
      summary:
        "Fetched 2 of 3 IPOS statute sections. Not found: Section 999 Patents Act.",
      not_found: ["Section 999 Patents Act"],
      provenance: {
        source_url: "https://www.wipo.int/wipolex/en/members/profile/SG",
      },
    });
    expect(
      many.structuredContent?.items.map((item) => item.section_label),
    ).toEqual(["190", "First Schedule"]);
    await expect(
      client.callTool("get_ipos_section", { citation: "Section 2" }),
    ).rejects.toThrow("is ambiguous");

    const list = await client.callTool<Envelope>("list_ipos_statutes", {});
    expect(list.structuredContent?.summary).toBe(
      "IPOS Singapore statutes — 4 Acts.",
    );
    expect(list.structuredContent?.items.map((item) => item.statute)).toEqual([
      "patents",
      "tm",
      "designs",
      "copyright",
    ]);

    const status = await client.readResource(IPOS_STATUTES_STATUS_URI);
    expect(
      JSON.parse(String((status[0] as { text?: string }).text)),
    ).toMatchObject({ available: true, section_count: 19 });
  } finally {
    await close();
  }
});

test("IPOS manuals MCP tools search, fetch and list", async () => {
  const { client, close } = await connect();
  try {
    const search = await client.callTool<Envelope>("search_ipos_manuals", {
      query: "visual similarity",
      manual: "tm",
    });
    expect(search.structuredContent).toMatchObject({
      summary: expect.stringMatching(
        /^IPOS manuals — `visual similarity` \(manual=tm\): \d+ hits \(page 1\)\.$/,
      ),
      provenance: {
        source_url: "https://www.ipos.gov.sg/about-ip/",
        source_name: "IPOS Singapore — examination manuals",
        corpus_version: "snapshot 2026-10-22",
      },
    });
    expect(search.structuredContent?.items[0]).toMatchObject({
      manual: "tm",
      section_label: "7.5.2.5.2",
    });

    const one = await client.callTool<Envelope>("get_ipos_manual_section", {
      citation: "IPOS PEG 8.12",
    });
    expect(one.structuredContent?.summary).toBe(
      "**IPOS PEG 8.12** — Discoveries",
    );
    expect(String(one.structuredContent?.provenance.source_url)).toEndWith(
      "examination-guidelines-for-patent-applications.pdf#page=294",
    );
    const many = await client.callTool<Envelope>("get_ipos_manual_section", {
      citation: ["TM Work Manual 17.3.1", "PEG 99.9", "Designs Guidelines 2.1"],
    });
    expect(many.structuredContent).toMatchObject({
      summary: "Fetched 2 of 3 IPOS manual sections. Not found: PEG 99.9.",
      not_found: ["PEG 99.9"],
    });

    const list = await client.callTool<Envelope>("list_ipos_manuals", {});
    expect(list.structuredContent?.summary).toBe(
      "IPOS Singapore manuals — 3 manuals.",
    );
    const status = await client.readResource(IPOS_MANUALS_STATUS_URI);
    expect(
      JSON.parse(String((status[0] as { text?: string }).text)),
    ).toMatchObject({ available: true, label: "IPOS manuals" });
  } finally {
    await close();
  }
});

test("Bun HTTP serves IPOS tools only to tokens with ipos:read", async () => {
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
  const corpora = readers();
  const server = createServer({
    ...corpora,
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
      auth: new BearerAuth(token("ipoin:read uspto:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names).toContain("search_ipo_in_statutes");
      expect(names.filter((name) => iposTools.includes(name))).toEqual([]);
      await expect(
        other.callTool("search_ipos_statutes", { query: "patent" }),
      ).rejects.toThrow();
    } finally {
      await other.close();
    }
    const singapore = await Client.connect(url, {
      auth: new BearerAuth(token("ipos:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await singapore.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(iposTools),
      );
      const result = await singapore.callTool<Envelope>("search_ipos_manuals", {
        query: "discovery",
      });
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items.length).toBeGreaterThan(0);
    } finally {
      await singapore.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
    corpora.iposStatutes.close();
    corpora.iposManuals.close();
  }
});

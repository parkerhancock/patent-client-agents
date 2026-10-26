import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import type {
  EuipoContentsNode,
  EuipoPage,
  EuipoPublication,
  EuipoSearchHit,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import {
  euipoGuidelinesCassette,
  euipoGuidelinesRecording,
  replayClient,
  samples,
  toolCalls,
} from "./euipo-guidelines-recordings.js";

type Search = {
  publication: EuipoPublication;
  hits: EuipoSearchHit[];
  total: number;
  more_available: boolean;
};
type Contents = { publication: EuipoPublication; nodes: EuipoContentsNode[] };
type Page = { publication: EuipoPublication; data: EuipoPage };

test("publications resolve to the latest edition, or a named one, per language", async () => {
  const all =
    await euipoGuidelinesRecording<EuipoPublication[]>("publications");
  expect(all).toHaveLength(357);
  expect(new Set(all.map((p) => p.guidelines))).toEqual(
    new Set(["trade_marks", "designs", "craft_gi"]),
  );
  const search = await euipoGuidelinesRecording<Search>("search");
  expect(search.publication).toMatchObject({
    publication_id: "2319054",
    edition: "2026",
    entry_into_force: "2026-07-01",
  });
  const older = await euipoGuidelinesRecording<Search>("search-edition");
  expect(older.publication).toMatchObject({
    publication_id: "2058424",
    guidelines: "designs",
    edition: "2023",
  });
  const german = await euipoGuidelinesRecording<Search>("search-german");
  expect(german.publication.title).toBe("Richtlinien zu Marken");
});

test("search ranks pages with highlighted snippets, filtered by part", async () => {
  const search = await euipoGuidelinesRecording<Search>("search");
  expect(search.total).toBe(57);
  expect(search.more_available).toBe(true);
  expect(search.hits[0]).toEqual({
    page_id: samples.leaf,
    title: "1.3.3 Factual monopoly",
    part: "B",
    chapter: "4",
    section: "4",
    snippet:
      "However, in this case the applicant will be more likely to succeed on acquired distinctiveness.",
    url: `https://guidelines.euipo.europa.eu/2319054/${samples.leaf}`,
  });
  const opposition = await euipoGuidelinesRecording<Search>("search-part");
  expect(opposition.total).toBe(2);
  expect(opposition.hits.every((hit) => hit.part === "C")).toBe(true);
  const designs = await euipoGuidelinesRecording<Search>("search-designs");
  expect(designs.hits.every((hit) => hit.part === "INV RCD")).toBe(true);
  // Titles come in the publication's language, not the English logical title.
  const german = await euipoGuidelinesRecording<Search>("search-german");
  expect(german.hits[0]?.title).toMatch(/^4\.5\.4 Kombi/);
  expect(german.hits[0]?.snippet).toContain("Unterscheidungskraft");
});

test("contents list parts and drill down by node id", async () => {
  const root = await euipoGuidelinesRecording<Contents>("contents");
  expect(root.nodes.map((node) => node.title)).toContain("Part C Opposition");
  expect(root.nodes.find((node) => node.node_id === "t1-k8")).toMatchObject({
    page_id: "2231876",
    title: "Part A General rules",
    has_children: true,
  });
  const partA = await euipoGuidelinesRecording<Contents>("contents-part");
  expect(partA.nodes[0]).toMatchObject({
    node_id: "t1-k9",
    page_id: samples.section,
  });
  const gi = await euipoGuidelinesRecording<Contents>("contents-gi");
  expect(gi.publication.guidelines).toBe("craft_gi");
  expect(gi.nodes[1]?.title).toBe(
    "Part A Geographical indications for craft and industrial products",
  );
});

test("pages come as text with their parent and children", async () => {
  const leaf = await euipoGuidelinesRecording<Page>("leaf");
  expect(leaf.data).toMatchObject({
    title: "1.3.3 Factual monopoly",
    parent: { page_id: "2068220", title: "1.3 Common misunderstandings" },
    children: [],
    entry_into_force: "2026-07-01",
  });
  // Source line breaks inside sentences are joined; the links are lifted out.
  expect(leaf.data.text).toBe(
    "1.3.3 Factual monopoly\n\nThe fact that the applicant is the only person offering the goods and services for which the mark is descriptive is not relevant for Article 7(1)(c) EUTMR. However, in this case the applicant will be more likely to succeed on acquired distinctiveness.",
  );
  const section = await euipoGuidelinesRecording<Page>("section");
  expect(section.data.text).toBe(section.data.title);
  expect(section.data.children.map((child) => child.page_id)).toEqual([
    "2347292",
    "2340973",
    "2396308",
    "2341103",
  ]);
  await expect(euipoGuidelinesRecording("missing")).rejects.toMatchObject({
    code: "NOT_FOUND",
  });
});

test("bad ids and parts reject before any request", async () => {
  const client = replayClient();
  await expect(client.getPage("12a")).rejects.toThrow("Not a page id");
  await expect(client.contents("root")).rejects.toThrow(
    "Not a contents node id",
  );
  await expect(client.search("use", { part: "B; drop" })).rejects.toThrow(
    "A part is a letter",
  );
  await expect(client.publication({ language: "english" })).rejects.toThrow(
    "Not a two-letter language code",
  );
});

async function replayed(name: string) {
  const call = toolCalls[name];
  if (!call) throw new Error(`Unknown tool call ${name}`);
  const server = createServer({ clients: { euipoGuidelines: replayClient() } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    return await euipoGuidelinesCassette(
      `mcp-${name}`,
      async () =>
        (await client.callTool(call[0], call[1])).structuredContent as Record<
          string,
          unknown
        >,
    );
  } finally {
    await client.close();
    await server.close();
  }
}

test("the tools search, browse and fetch pages", async () => {
  const search = (await replayed("search")) as {
    summary: string;
    items: EuipoSearchHit[];
    more_available: boolean;
  };
  expect(search.summary).toBe(
    "Trade mark guidelines (edition 2026, en) — 50 pages match `genuine use` in part C, returned hits 1-3.",
  );
  expect(search.items).toHaveLength(3);
  expect(search.more_available).toBe(true);
  const browse = (await replayed("browse")) as {
    summary: string;
    items: EuipoContentsNode[];
  };
  expect(browse.summary).toBe(
    "Designs guidelines (edition 2026, en) — 8 entries under t1.",
  );
  expect(browse.items.map((item) => item.title)).toContain(
    "Examination of design invalidity applications",
  );
  const page = (await replayed("page")) as {
    summary: string;
    details: Record<string, unknown>;
  };
  expect(page.summary).toBe(
    "**1.3.3 Factual monopoly** — Trade mark guidelines (edition 2026, en).",
  );
  expect(page.details).toMatchObject({
    page_id: samples.leaf,
    text_length: 275,
    publication: { publication_id: "2319054" },
  });
  expect(page.details.text).toEqual(
    expect.stringContaining("Factual monopoly"),
  );
});

test("Bun HTTP serves the Guidelines tools to tokens with euipo:read", async () => {
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
    clients: { euipoGuidelines: replayClient() },
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
  const tools = [
    "browse_euipo_guidelines",
    "get_euipo_guidelines_page",
    "search_euipo_guidelines",
  ];
  const names = async (scope: string) => {
    const client = await Client.connect(url, {
      auth: new BearerAuth(token(scope)),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      return (await client.listTools())
        .map((tool) => tool.name)
        .filter((n) => tools.includes(n));
    } finally {
      await client.close();
    }
  };
  try {
    expect(await names("eurlex:read")).toEqual([]);
    expect((await names("euipo:read")).sort()).toEqual(tools);
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

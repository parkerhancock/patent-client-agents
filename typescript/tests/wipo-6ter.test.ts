import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  WIPO_6TER_SEARCH_TYPES,
  Wipo6terClient,
  type Wipo6terPage,
  type Wipo6terSign,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { leanSign } from "../packages/mcp/src/wipo-6ter.js";
import {
  replayClient,
  samples,
  sixterCassette,
  sixterRecording,
  toolCalls,
} from "./wipo-6ter-recordings.js";

type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available: boolean;
};
const page = (name: string) => sixterRecording<Wipo6terPage>(name);

test("the archived OpenAPI file documents the four operations the client uses", async () => {
  const spec = Bun.YAML.parse(
    await readFile(
      resolve(
        import.meta.dir,
        "../references/wipo-6ter/Article6ter_API_v1_OpenAPI.yaml",
      ),
      "utf8",
    ),
  ) as { info: { version: string }; paths: Record<string, unknown> };
  expect(spec.info.version).toBe("1.2.0");
  expect(Object.keys(spec.paths).sort()).toEqual([
    "/last-updated",
    "/publication",
    "/signs",
    "/signs/{signId}",
  ]);
  // The spec's STARTS_WITH is rejected live, so the client leaves it out.
  expect(WIPO_6TER_SEARCH_TYPES).toEqual(["ANY", "ALL", "PHRASE"]);
});

test("searches return signs with their total, in every search mode", async () => {
  const unesco = await page("search-any");
  expect(unesco).toMatchObject({ count: 6, more_available: true });
  expect(unesco.signs[0]).toMatchObject({
    numberAlias: expect.stringMatching(/^QO\d{4}$/),
    communicatingParty: expect.objectContaining({ type: "ORG" }),
  });
  expect(unesco.provenance.source_url).toContain("keywords=UNESCO");
  expect((await page("search-phrase")).count).toBe(175);
  const hallmarks = await page("search-hallmark-relevance");
  expect(hallmarks).toMatchObject({ count: 1066, offset: 10 });
});

test("signs by alias; an unknown alias (HTTP 204) is NOT_FOUND", async () => {
  const unesco = await sixterRecording<{ data: Wipo6terSign }>("sign");
  expect(unesco.data).toMatchObject({
    numberAlias: samples.unesco,
    protectedSign: { text: "UNESCO", languageCode: "EN" },
  });
  await expect(sixterRecording("sign-missing")).rejects.toMatchObject({
    code: "NOT_FOUND",
  });
  expect(await sixterRecording("last-updated")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  const publication = await sixterRecording<{
    data: { zip: { url: string; size: number } };
  }>("publication");
  expect(publication.data.zip).toMatchObject({
    url: "https://6ter.wipo.int/files/6ter.zip",
    size: expect.any(Number),
  });
  await expect(new Wipo6terClient().getSign("88")).rejects.toThrow(
    "look like QO0088",
  );
  await expect(new Wipo6terClient().search({ keywords: " " })).rejects.toThrow(
    "keywords is required",
  );
});

async function replayed(name: string) {
  const call = toolCalls[name];
  if (!call) throw new Error(`Unknown tool call ${name}`);
  const server = createServer({ clients: { wipo6ter: replayClient() } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    return await sixterCassette(`mcp-${name}`, async () => {
      const result = await client.callTool<Envelope>(call[0], call[1]);
      return result.structuredContent as Envelope;
    });
  } finally {
    await client.close();
    await server.close();
  }
}

test("the tools search and fetch signs, lean by default", async () => {
  const health = await replayed("search");
  expect(health.summary).toBe(
    "WIPO Article 6ter — 13 signs match `world health`, returned signs 1-3.",
  );
  expect(
    health.items.every(
      (item) => !("metadata" in item) && !("fileName" in item),
    ),
  ).toBe(true);
  const signs = await replayed("get-signs");
  expect(signs.items.map((item) => item.numberAlias)).toEqual([
    samples.unesco,
    samples.maltaFlag,
  ]);
  expect(signs.not_found).toEqual([samples.missing]);
  expect(
    leanSign({
      metadata: {},
      indexedAt: "x",
      fileName: "y",
      numberAlias: "QO1",
    }),
  ).toEqual({
    numberAlias: "QO1",
  });
});

test("Bun HTTP serves the 6ter tools to tokens with wipo:read", async () => {
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
    clients: { wipo6ter: replayClient() },
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
  const names = async (scope: string) => {
    const client = await Client.connect(url, {
      auth: new BearerAuth(token(scope)),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      return (await client.listTools())
        .map((tool) => tool.name)
        .filter((n) => n.includes("6ter"));
    } finally {
      await client.close();
    }
  };
  try {
    expect(await names("prh:read")).toEqual([]);
    expect((await names("wipo:read")).sort()).toEqual([
      "get_wipo_6ter_sign",
      "search_wipo_6ter",
    ]);
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

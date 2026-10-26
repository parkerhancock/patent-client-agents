import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import type { PrhClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { leanPrhDossier, leanPrhPatent } from "../packages/mcp/src/prh.js";
import {
  prhCassette,
  replayClient,
  samples,
  toolCalls,
} from "./prh-recordings.js";

const PRH_TOOLS = [
  "search_prh_patents",
  "get_prh_patent",
  "search_prh_trademarks",
  "search_prh_well_known_trademarks",
  "search_prh_designs",
  "download_prh_trademark_image",
  "download_prh_design_image",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available: boolean;
  details?: Record<string, unknown>;
  file_path?: string;
  filename?: string;
  content_type?: string;
  provenance: Record<string, unknown>;
};

async function connect(prh: PrhClient) {
  const server = createServer({ clients: { prh } });
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
/** Replay one recorded tool call; `inspect` runs before the server closes and removes artifacts. */
async function replayed<T = Envelope>(
  name: string,
  inspect: (result: Envelope) => Promise<T> | T = (r) => r as T,
) {
  const call = toolCalls[name];
  if (!call) throw new Error(`Unknown tool call ${name}`);
  const session = await connect(replayClient());
  try {
    return await prhCassette(`mcp-${name}`, async () => {
      const result = await session.client.callTool<Envelope>(call[0], call[1]);
      return inspect(result.structuredContent as Envelope);
    });
  } finally {
    await session.close();
  }
}

test("PRH tools are always served, read-only", async () => {
  const session = await connect(replayClient());
  try {
    const tools = (await session.client.listTools()).filter((tool) =>
      PRH_TOOLS.includes(tool.name),
    );
    expect(tools.map((tool) => tool.name).sort()).toEqual(
      [...PRH_TOOLS].sort(),
    );
    expect(
      tools.every(
        (tool) => tool.annotations?.readOnlyHint && tool.outputSchema,
      ),
    ).toBe(true);
  } finally {
    await session.close();
  }
});

test("searches return a window of PRH's rows", async () => {
  const patents = await replayed("search-patents");
  expect(patents.summary).toBe(
    "PRH patents — 84 total hits for `Nokia`, returned rows 6-10.",
  );
  expect(patents.items).toHaveLength(5);
  expect(patents.more_available).toBe(true);
  expect(patents.items.every((item) => !("ordinal" in item))).toBe(true);
  const designs = await replayed("search-designs");
  expect(designs.items).toHaveLength(3);
  expect(designs.items.every((item) => !("thumbnailUrl" in item))).toBe(true);
});

test("get_prh_patent fans out and lists unknown numbers", async () => {
  const result = await replayed("get-patents");
  expect(result.items.map((item) => item.applicationNumber)).toEqual([
    samples.patent,
  ]);
  expect(result.not_found).toEqual([samples.missing]);
  expect(result.summary).toBe(
    `Fetched 1 of 2 PRH patent records. Not found: ${samples.missing}.`,
  );
  expect(result.items[0]).not.toHaveProperty("documents");
  expect(result.items[0]).not.toHaveProperty("paymentDetails");
});

test("trademark images arrive as artifacts", async () => {
  const bytes = await replayed("trademark-image", async (result) => {
    expect(result).toMatchObject({
      filename: `prh-tm-${samples.trademark.application}-${samples.trademark.registration}-thumbnail.jpg`,
      content_type: "image/jpeg",
    });
    return readFile(result.file_path as string);
  });
  expect([...bytes.subarray(0, 2)]).toEqual([0xff, 0xd8]);
});

test("lean projections match Python's", () => {
  expect(
    leanPrhDossier({
      a: 1,
      thumbnailUrl: "t",
      largeThumbnailUrl: "l",
      ordinal: 1,
    }),
  ).toEqual({ a: 1 });
  expect(
    leanPrhPatent({ a: 1, documents: {}, paymentDetails: {}, events: [] }),
  ).toEqual({ a: 1 });
});

test("Bun HTTP serves PRH tools only to tokens with prh:read", async () => {
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
    clients: { prh: replayClient() },
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
      return (await client.listTools()).map((tool) => tool.name);
    } finally {
      await client.close();
    }
  };
  try {
    expect(
      (await names("prv:read")).filter((n) => PRH_TOOLS.includes(n)),
    ).toEqual([]);
    expect(await names("prh:read")).toEqual(expect.arrayContaining(PRH_TOOLS));
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

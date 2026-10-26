import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { type PrvClient, PrvError } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { leanPrvDossier, leanPrvPatent } from "../packages/mcp/src/prv.js";
import {
  prvCassette,
  replayClient,
  samples,
  toolCalls,
} from "./prv-recordings.js";

const PRV_TOOLS = [
  "search_prv_patents",
  "get_prv_patent",
  "get_prv_trademark",
  "get_prv_design",
  "search_prv_trademarks",
  "search_prv_designs",
  "search_prv_spcs",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available: boolean;
  provenance: Record<string, unknown>;
};

async function connect(prv: PrvClient) {
  const server = createServer({ clients: { prv } });
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
async function replayed(name: string) {
  const call = toolCalls[name];
  if (!call) throw new Error(`Unknown tool call ${name}`);
  const session = await connect(replayClient());
  try {
    return await prvCassette(`mcp-${name}`, async () => {
      const result = await session.client.callTool<Envelope>(call[0], call[1]);
      return result.structuredContent as Envelope;
    });
  } finally {
    await session.close();
  }
}

test("PRV tools are always served, read-only", async () => {
  const session = await connect(replayClient());
  try {
    const tools = (await session.client.listTools()).filter((tool) =>
      PRV_TOOLS.includes(tool.name),
    );
    expect(tools.map((tool) => tool.name).sort()).toEqual(
      [...PRV_TOOLS].sort(),
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

test("searches keep Python's summaries", async () => {
  const patents = await replayed("search-patents");
  expect(patents.summary).toBe(
    "PRV patents — 3,604 total hits for `Volvo`, returned 2.",
  );
  expect(patents.more_available).toBe(true);
  const spcs = await replayed("search-spcs");
  expect(spcs.summary).toBe(
    "PRV SPCs — 4 total hits for `naproxen`, returned 2.",
  );
  const designs = await replayed("search-designs");
  expect(designs.items).toHaveLength(2);
});

test("get_prv_patent fans out, lists unknown numbers and drops drawing bytes", async () => {
  const result = await replayed("get-patents");
  expect(result.items.map((item) => item.applicationNumberFormatted)).toEqual([
    samples.patent,
  ]);
  expect(result.not_found).toEqual(["9999999-9"]);
  expect(result.summary).toBe(
    "Fetched 1 of 2 PRV patent records. Not found: 9999999-9.",
  );
  const drawing = result.items[0]?.firstDrawing as Record<string, unknown>;
  expect(drawing).not.toHaveProperty("data");
  expect(drawing).toHaveProperty("pageNumber");
  expect(result.provenance.source_url).toBe(
    "https://api.prv.se/patents/applications/",
  );
});

test("a single unknown number raises, as Python's fetch_many does", async () => {
  const missing = {
    getPatent: async () => {
      throw new PrvError("PRV found no record.", 404, "NOT_FOUND");
    },
  } as unknown as PrvClient;
  const session = await connect(missing);
  try {
    await expect(
      session.client.callTool("get_prv_patent", {
        application_number: "SE1234567-8",
      }),
    ).rejects.toThrow("PRV found no record");
  } finally {
    await session.close();
  }
});

test("lean records keep drawing metadata", () => {
  expect(
    leanPrvPatent({
      title: "t",
      firstDrawing: { pageNumber: 1, data: "AAAA" },
    }),
  ).toEqual({ title: "t", firstDrawing: { pageNumber: 1 } });
  expect(leanPrvPatent({ title: "t", firstDrawing: null })).toEqual({
    title: "t",
    firstDrawing: null,
  });
});

test("Bun HTTP serves PRV tools only to tokens with prv:read", async () => {
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
    clients: { prv: replayClient() },
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
      (await names("kipo:read")).filter((n) => PRV_TOOLS.includes(n)),
    ).toEqual([]);
    expect(await names("prv:read")).toEqual(expect.arrayContaining(PRV_TOOLS));
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

test("trademark and design tools return records without image bytes", async () => {
  const marks = await replayed("get-trademarks");
  expect(marks.items.map((item) => item.applicationNumber)).toEqual([
    samples.trademark,
  ]);
  expect(marks.not_found).toEqual(["1999-99999"]);
  const documents = marks.items[0]?.dvDocuments as Record<string, unknown>[];
  expect(documents.length).toBeGreaterThan(0);
  expect(documents.every((document) => !("data" in document))).toBe(true);
  expect(documents[0]).toHaveProperty("imageEndpointUrl");
  const designs = await replayed("get-designs");
  expect(designs.summary).toBe(
    `PRV design records — 1 record for ${samples.design}.`,
  );
  expect(
    leanPrvDossier({ dvDocuments: [{ data: "AAAA", documentId: 1 }], a: 1 }),
  ).toEqual({ dvDocuments: [{ documentId: 1 }], a: 1 });
});

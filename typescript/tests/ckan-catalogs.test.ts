import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import {
  type CkanDataset,
  CkanError,
  IlpoTmClient,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import {
  ckanCassette,
  ckanRecording,
  replayClients,
  samples,
  toolCalls,
} from "./ckan-recordings.js";

const CATALOG_TOOLS = [
  "list_ilpo_tm_releases",
  "download_ilpo_tm",
  "list_ipa_bulk_releases",
  "download_ipa_bulk",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  details: Record<string, unknown>;
  provenance: Record<string, unknown>;
};
const dataset = (name: string) =>
  ckanRecording<{ data: CkanDataset; provenance: { source_url: string } }>(
    name,
  );

test("the ILPO register is simaneymisahr; Python's trade-marks id does not exist", async () => {
  const register = await dataset("ilpo-register");
  expect(register.data.name).toBe("simaneymisahr");
  expect(register.data.resources).toHaveLength(7);
  expect(
    register.data.resources.find((r) => r.id === samples.ilpoRegister),
  ).toMatchObject({ format: "CSV", size: expect.any(Number) });
  expect(register.provenance.source_url).toBe(
    "https://data.gov.il/dataset/simaneymisahr",
  );
  expect((await dataset("ilpo-classifications")).data.resources.length).toBe(3);
  const python = await dataset("ilpo-python-default").catch((e) => e);
  expect(python).toBeInstanceOf(CkanError);
  expect(python).toMatchObject({ code: "NOT_FOUND", status: 404 });
});

test("IP RAPID lists its dictionary and weekly zip; unknown datasets are NOT_FOUND", async () => {
  const iprapid = await dataset("ipa-iprapid");
  expect(iprapid.data).toMatchObject({
    name: "iprapid",
    license_title: "Creative Commons Attribution 4.0 International",
  });
  expect(iprapid.data.resources.map((r) => r.format)).toEqual([".pdf", "ZIP"]);
  expect(iprapid.data.resources[1]?.size).toBeGreaterThan(1_000_000_000);
  expect(iprapid.provenance.source_url).toBe(
    "https://data.gov.au/data/dataset/iprapid",
  );
  // data.gov.au redirects an unknown id to an HTML page.
  await expect(dataset("ipa-missing")).rejects.toMatchObject({
    code: "NOT_FOUND",
  });
});

async function replayed(name: string) {
  const call = toolCalls[name];
  if (!call) throw new Error(`Unknown tool call ${name}`);
  const clients = replayClients();
  const server = createServer({
    clients: { ilpoTm: clients.ilpo, ipaBulk: clients.ipa },
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    return await ckanCassette(`mcp-${name}`, async () => {
      const result = await client.callTool<Envelope>(call[0], call[1]);
      return result.structuredContent as Envelope;
    });
  } finally {
    await client.close();
    await server.close();
  }
}

test("the tools keep Python's names, id keys and summaries", async () => {
  const ilpo = await replayed("list-ilpo");
  expect(ilpo.summary).toBe(
    "ILPO Israel TM feed — `simaneymisahr` (Other (Open)): 7 downloadable resource(s).",
  );
  expect(Object.keys(ilpo.items[0] ?? {})).toEqual([
    "resource_id",
    "name",
    "description",
    "format",
    "mimetype",
    "size_bytes",
    "last_modified",
    "download_url",
  ]);
  const ilpoFile = await replayed("download-ilpo");
  expect(ilpoFile.details).toMatchObject({
    resource_id: samples.ilpoRegister,
    dataset_id: "simaneymisahr",
    download_url: expect.stringMatching(/^https:\/\/e\.data\.gov\.il\//),
  });
  const ipa = await replayed("list-ipa");
  expect(ipa.items.map((item) => item.release_id)).toContain(samples.ipaZip);
  const zip = await replayed("download-ipa");
  expect(zip.summary).toContain("IPRAPID.zip (1,351.8 MB)");
  expect(zip.details).toMatchObject({
    release_id: samples.ipaZip,
    license: "Creative Commons Attribution 4.0 International",
    download_url: expect.stringMatching(
      /^https:\/\/data\.gov\.au\/.*iprapid\.zip$/,
    ),
  });
});

test("bad ids are refused before any request; a missing resource is NOT_FOUND", async () => {
  const client = new IlpoTmClient({
    retryLimit: 0,
    fetch: (async () =>
      Response.json({
        success: true,
        result: { id: "x", name: "simaneymisahr", resources: [{ id: "r1" }] },
      })) as unknown as typeof fetch,
  });
  await expect(client.getDataset("../etc")).rejects.toThrow(
    "Not a CKAN dataset id",
  );
  await expect(client.getResource("nope")).rejects.toMatchObject({
    code: "NOT_FOUND",
  });
  expect((await client.getResource("r1")).data.id).toBe("r1");
  const failed = new IlpoTmClient({
    retryLimit: 0,
    fetch: (async () =>
      Response.json({ success: false, error: {} })) as unknown as typeof fetch,
  });
  await expect(failed.getDataset()).rejects.toMatchObject({
    code: "NOT_FOUND",
  });
});

test("Bun HTTP scopes the catalogs to ilpo:read and ipaustralia:read", async () => {
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
  const clients = replayClients();
  const server = createServer({
    clients: { ilpoTm: clients.ilpo, ipaBulk: clients.ipa },
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
        .filter((name) => CATALOG_TOOLS.includes(name));
    } finally {
      await client.close();
    }
  };
  try {
    expect((await names("ilpo:read")).sort()).toEqual([
      "download_ilpo_tm",
      "list_ilpo_tm_releases",
    ]);
    expect((await names("ipaustralia:read")).sort()).toEqual([
      "download_ipa_bulk",
      "list_ipa_bulk_releases",
    ]);
    expect(await names("prh:read")).toEqual([]);
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

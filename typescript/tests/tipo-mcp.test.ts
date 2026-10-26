import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import type { TipoClient } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { leanTipo } from "../packages/mcp/src/tipo.js";
import {
  replayClient,
  samples,
  tipoCassette,
  toolCalls,
} from "./tipo-recordings.js";

const TIPO_TOOLS = [
  "search_tipo_patents",
  "get_tipo_patent",
  "get_tipo_patent_publication",
  "get_tipo_patent_rights",
  "get_tipo_patent_priority",
  "get_tipo_patent_annuity",
  "get_tipo_patent_twins",
  "get_tipo_patent_events",
  "search_tipo_trademarks",
  "get_tipo_trademark",
  "get_tipo_trademark_rights",
  "get_tipo_trademark_priority",
  "get_tipo_trademark_image_urls",
  "get_tipo_trademark_events",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available: boolean;
  attribution: string;
  provenance: Record<string, unknown>;
};

async function connect(tipo?: TipoClient) {
  const server = createServer(tipo ? { clients: { tipo } } : {});
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
/** Replay one recorded tool call. */
async function replayed(name: string) {
  const call = toolCalls[name];
  if (!call) throw new Error(`Unknown tool call ${name}`);
  const session = await connect(replayClient());
  try {
    return await tipoCassette(`mcp-${name}`, async () => {
      const result = await session.client.callTool<Envelope>(call[0], call[1]);
      return result.structuredContent as Envelope;
    });
  } finally {
    await session.close();
  }
}

test("TIPO tools appear only with a client or TIPO_API_KEY", async () => {
  const saved = process.env.TIPO_API_KEY;
  delete process.env.TIPO_API_KEY;
  try {
    const names = async () => {
      const session = await connect();
      try {
        return (await session.client.listTools()).map((tool) => tool.name);
      } finally {
        await session.close();
      }
    };
    expect((await names()).filter((n) => n.includes("tipo"))).toEqual([]);
    process.env.TIPO_API_KEY = "some-token";
    expect(await names()).toEqual(expect.arrayContaining(TIPO_TOOLS));
    const session = await connect(replayClient());
    try {
      const tools = (await session.client.listTools()).filter((tool) =>
        TIPO_TOOLS.includes(tool.name),
      );
      expect(tools).toHaveLength(TIPO_TOOLS.length);
      expect(
        tools.every(
          (tool) => tool.annotations?.readOnlyHint && tool.outputSchema,
        ),
      ).toBe(true);
    } finally {
      await session.close();
    }
  } finally {
    if (saved === undefined) delete process.env.TIPO_API_KEY;
    else process.env.TIPO_API_KEY = saved;
  }
});

test("patent searches use TIPO's documented filters", async () => {
  const titles = await replayed("search-patents");
  expect(titles.summary).toMatch(
    /^TIPO patents \(rights\) — 2 of \d+ hits for `加熱器` \(invention\)\.$/,
  );
  expect(titles.more_available).toBe(true);
  expect(titles.attribution).toContain("Taiwan Open Government Data License");
  expect(
    titles.items.every((item) =>
      String(
        (item["patent-title"] as Record<string, unknown>)[
          "patent-name-chinese"
        ],
      ).includes("加熱器"),
    ),
  ).toBe(true);
  expect(titles.provenance.source_url).toContain("patentname=");
  const filed = await replayed("search-patent-applications");
  expect(filed.items.map((item) => item["appl-date"])).toEqual([
    "2025-03-26",
    "2025-03-26",
    "2025-03-26",
  ]);
  const session = await connect(replayClient());
  try {
    await expect(
      session.client.callTool("search_tipo_patents", {
        register: "applications",
        q: "x",
      }),
    ).rejects.toThrow("no title or applicant filter");
    await expect(
      session.client.callTool("search_tipo_patents", {
        register: "publications",
        applclass: 2,
      }),
    ).rejects.toThrow("invention applications only");
  } finally {
    await session.close();
  }
});

test("lookups return the requested application and report not_found", async () => {
  const patents = await replayed("get-patent");
  expect(patents.items.map((item) => item["appl-no"])).toEqual([
    samples.patent,
  ]);
  expect(patents.not_found).toEqual([samples.missing]);
  expect(patents.summary).toBe(
    `Fetched 1 of 2 applications for TIPO patent applications. Not found: ${samples.missing}. 1 rows.`,
  );
  const rights = await replayed("get-patent-rights");
  expect(rights.summary).toBe(
    `TIPO patent rights — 1 rows for 1 application: ${samples.patent}.`,
  );
  // Lean output drops nulls and ftps:// pointers.
  expect(JSON.stringify(rights.items)).not.toMatch(/null|ftps:\/\//);
  const twins = await replayed("get-patent-twins");
  expect(twins.items.map((item) => item.list)).toEqual([
    "twins-announceds",
    "twins-approveds",
  ]);
  expect(twins.items[1]?.["twins-appl-no"]).toBe(samples.twinInvention);
  const trademark = await replayed("get-trademark");
  expect(trademark.items[0]).toMatchObject({ "appl-no": samples.trademark });
  expect(trademark.not_found).toEqual([]);
  const priority = await replayed("get-trademark-priority");
  expect(JSON.stringify(priority.items)).toContain(samples.trademark);
  const images = await replayed("get-trademark-images");
  expect(images.items[0]?.["tmark-image-url"]).toMatchObject({
    "image-data-1": expect.stringContaining("https://"),
  });
});

test("event tools merge their endpoints and tag each event", async () => {
  const patent = await replayed("get-patent-events");
  expect(patent.items.map((item) => [item.appl_no, item.event_type])).toEqual([
    [samples.divideParent, "divide"],
    [samples.alteration, "alteration"],
  ]);
  const trademark = await replayed("get-trademark-events");
  // Divided registrations keep the parent's application number, so one
  // number reaches the whole tree: 00981661 → 01443209/10 → 01463677-79 → 01514712/13.
  expect(
    trademark.items.map((item) => [
      item.appl_no,
      item.event_type,
      item["exam-no"],
      (item["origin-exam-no"] as Record<string, unknown> | undefined)?.[
        "origin-exam-no"
      ] ?? null,
    ]),
  ).toEqual([
    [samples.trademarkDivided, "divide", "00981661", null],
    [samples.trademarkDivided, "divide", "01443209", "00981661"],
    [samples.trademarkDivided, "divide", "01443210", "00981661"],
    [samples.trademarkDivided, "divide", "01463677", "01443210"],
    [samples.trademarkDivided, "divide", "01463678", "01443210"],
    [samples.trademarkDivided, "divide", "01463679", "01443210"],
    [samples.trademarkDivided, "divide", "01514712", "01463677"],
    [samples.trademarkDivided, "divide", "01514713", "01463677"],
    [samples.trademarkTransfer, "change", "01714282", null],
  ]);
});

test("trademark search maps the Nice class to goodclasscode", async () => {
  const result = await replayed("search-trademarks");
  expect(result.summary).toMatch(
    /^TIPO trademarks — 2 of 6 hits \(class 17\)\.$/,
  );
  expect(result.provenance.source_url).toContain("goodclasscode=017");
  expect(
    result.items.every((item) =>
      (item.goodsclasses as Record<string, unknown>[]).some(
        (g) => g["goodsclass-code"] === "017",
      ),
    ),
  ).toBe(true);
});

test("lean projection keeps everything but nulls, empty strings and ftps pointers", () => {
  expect(
    leanTipo({
      a: null,
      b: "",
      c: "ftps://ftp.tipo.gov.tw/x.xml",
      d: [{ e: null, f: 1 }],
      g: { h: "https://x" },
      i: [],
    }),
  ).toEqual({ d: [{ f: 1 }], g: { h: "https://x" }, i: [] });
});

test("Bun HTTP serves TIPO tools only to tokens with tipo:read", async () => {
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
    clients: { tipo: replayClient() },
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
      (await names("kipo:read")).filter((n) => TIPO_TOOLS.includes(n)),
    ).toEqual([]);
    expect(await names("tipo:read")).toEqual(
      expect.arrayContaining(TIPO_TOOLS),
    );
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

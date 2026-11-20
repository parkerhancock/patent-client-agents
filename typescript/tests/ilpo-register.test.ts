import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import {
  type IlpoPage,
  IlpoRegisterClient,
  type IlpoRow,
  ilpoPrefixQuery,
  ilpoRow,
  restorePunctuation,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { leanIlpoTrademark } from "../packages/mcp/src/ilpo-register.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  ilpoCassette,
  ilpoRecording,
  replayClient,
  samples,
  toolCalls,
} from "./ilpo-register-recordings.js";

const TOOLS = [
  "search_ilpo_trademarks",
  "get_ilpo_trademark",
  "search_ilpo_patents",
  "get_ilpo_patent",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available: boolean;
  provenance: Record<string, unknown>;
};
const page = (name: string) => ilpoRecording<IlpoPage>(name);

test("rows come back in English with ISO dates, flags and status translations", async () => {
  const marks = await page("trademarks-words");
  expect(marks.total).toBe(63);
  expect(marks.more_available).toBe(true);
  const first = marks.rows[0] as IlpoRow;
  expect(first).toMatchObject({
    mark_number: expect.any(Number),
    mark_text_en: expect.stringMatching(/coca/i),
    has_image: expect.any(Boolean),
    application_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    status_en: expect.any(String),
  });
  expect(Object.keys(first).some((key) => /[֐-׿]/.test(key))).toBe(false);
  expect(marks.provenance.source_url).toBe(
    "https://data.gov.il/dataset/simaneymisahr",
  );
  const byNumber = await page("trademarks-filter");
  expect(
    byNumber.rows.map((row) => row.mark_number as number).sort((a, b) => a - b),
  ).toEqual([9, samples.mark]);
});

test("Nice classes match whole tokens; English title words need prefix queries", async () => {
  const nice = await page("trademarks-nice-3");
  expect(
    nice.rows.every((row) =>
      String(row.nice_classes).split(/;\s*/).includes("3"),
    ),
  ).toBe(true);
  // Plain full-text search finds no English title words; the prefix query finds 90.
  expect((await page("patents-text")).total).toBe(90);
  expect((await page("patents-plain-english")).total).toBe(728);
  const ipc = await ilpoRecording<IlpoRow[]>("classifications-for");
  expect(ipc).toEqual([
    { application_number: samples.patent, ipc: "C12Q 1/6806", main: false },
    { application_number: samples.patent, ipc: "C12N 15/10", main: true },
  ]);
});

test("the export's placeholders are restored", () => {
  expect(restorePunctuation("טבע תעשיות פרמצבטיות בע~מ")).toBe(
    'טבע תעשיות פרמצבטיות בע"מ',
  );
  expect(restorePunctuation("Computer software~ computers")).toBe(
    "Computer software, computers",
  );
  expect(restorePunctuation("a~b")).toBe("a~b");
  expect(
    ilpoRow("patents", {
      "מספר בקשה": 1,
      "מספר פרסום בינלאומי": "/2013/119295",
      "תאריך פרסום שני": "01/01/1900",
      "תאריך מתן פטנט": "29/05/2019",
      "סטטוס בקשה/פטנט": "פקיעת תוקף",
    }),
  ).toMatchObject({
    pct_publication_number: "WO/2013/119295",
    second_publication_date: null,
    grant_date: "2019-05-29",
    status: "פקיעת תוקף",
    status_en: "lapsed",
  });
});

test("query building refuses unknown columns and strips query syntax", async () => {
  expect(ilpoPrefixQuery("coca-cola & (x)")).toBe("coca:* & cola:* & x:*");
  expect(() => ilpoPrefixQuery("&&&")).toThrow("no words");
  const urls: URL[] = [];
  const client = new IlpoRegisterClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) => {
      urls.push(new URL(String(input instanceof Request ? input.url : input)));
      return Response.json({
        success: true,
        result: { total: 0, records: [] },
      });
    }) as unknown as typeof fetch,
  });
  await expect(
    client.query("trademarks", { filters: { owner: "x" } }),
  ).rejects.toThrow('trademarks has no column "owner"');
  await expect(
    client.query("trademarks", { text: "a", words: { mark_text_en: "b" } }),
  ).rejects.toThrow("not both");
  await client.query("trademarks", {
    words: { owner_name_en: "Strauss Group" },
    tokens: { nice_classes: 30 },
    filters: { status: "רשום" },
    sort: "mark_number desc",
    limit: 5,
  });
  const params = Object.fromEntries(urls[0]?.searchParams ?? []);
  expect(JSON.parse(params.q ?? "{}")).toEqual({
    "שם בעל הסימן באנגלית": "Strauss:* & Group:*",
    "סוגי ניצה לבקשה": "30",
  });
  expect(params).toMatchObject({
    plain: "false",
    limit: "5",
    sort: '"מספר הסימן" desc',
  });
  expect(JSON.parse(params.filters ?? "{}")).toEqual({ מצב: "רשום" });
  const failed = new IlpoRegisterClient({
    retryLimit: 0,
    fetch: (async () =>
      Response.json({ success: false })) as unknown as typeof fetch,
  });
  await expect(failed.query("patents")).rejects.toMatchObject({
    code: "INVALID_RESPONSE",
  });
});

async function replayed(name: string) {
  const call = toolCalls[name];
  if (!call) throw new Error(`Unknown tool call ${name}`);
  const server = createServer({ clients: { ilpoRegister: replayClient() } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    return await ilpoCassette(`mcp-${name}`, async () => {
      const result = await client.callTool<Envelope>(call[0], call[1]);
      return result.structuredContent as Envelope;
    });
  } finally {
    await client.close();
    await server.close();
  }
}

test("trademark tools search, filter and join the related tables", async () => {
  const registered = await replayed("search-trademarks");
  expect(registered.summary).toBe(
    "ILPO trade marks — 40 matches for `coca cola`, returned rows 1-3.",
  );
  expect(
    registered.items.every((item) => item.status_en === "registered"),
  ).toBe(true);
  expect(registered.items[0]).not.toHaveProperty(
    "customs_representative_email",
  );
  const strauss = await replayed("search-trademarks-hebrew-owner");
  expect(
    strauss.items.every(
      (item) =>
        String(item.owner_name_he).includes("שטראוס") &&
        String(item.nice_classes).split(/;\s*/).includes("30"),
    ),
  ).toBe(true);
  const marks = await replayed("get-trademarks");
  expect(marks.items.map((item) => item.mark_number)).toEqual([
    samples.markWithPriority,
    samples.mark,
  ]);
  expect(marks.not_found).toEqual([String(samples.missingMark)]);
  const [pentium, coke] = marks.items as Record<string, unknown[]>[];
  expect(pentium?.priorities?.length).toBeGreaterThan(0);
  expect(coke?.parties).toEqual([
    expect.objectContaining({
      name_en: "The Coca-Cola Company",
      lead_party: true,
    }),
  ]);
  expect(coke?.events?.length).toBeGreaterThan(0);
});

test("patent tools search by title, applicant or IPC and join applicants and classes", async () => {
  const graphene = await replayed("search-patents");
  expect(graphene.items.every((item) => item.status_en === "granted")).toBe(
    true,
  );
  const teva = await replayed("search-patents-applicant");
  expect(teva.summary).toBe(
    "ILPO patent applicant rows — 771 matches for `Teva`, returned rows 1-3.",
  );
  expect(teva.items[0]).toMatchObject({
    match: expect.objectContaining({
      name_he: expect.stringContaining('בע"מ'),
    }),
    title_en: expect.any(String),
    pct_publication_number: expect.stringMatching(/^WO\//),
  });
  const ipc = await replayed("search-patents-ipc");
  expect(
    ipc.items.every((item) =>
      String((item.match as IlpoRow).ipc).startsWith("H01M 4"),
    ),
  ).toBe(true);
  const patents = await replayed("get-patents");
  expect(patents.items.map((item) => item.application_number)).toEqual([
    samples.grantedPatent,
    samples.patent,
  ]);
  expect(patents.not_found).toEqual([String(samples.missingPatent)]);
  expect(patents.items[1]).toMatchObject({
    applicants: [
      expect.objectContaining({ name_en: "EXOSOME DIAGNOSTICS, INC." }),
    ],
    classifications: expect.arrayContaining([
      { ipc: "C12N 15/10", main: true },
    ]),
  });
  const session = await (async () => {
    const server = createServer({ clients: { ilpoRegister: replayClient() } });
    return {
      server,
      client: await Client.connect(server, {
        versionNegotiation: { mode: "legacy" },
      }),
    };
  })();
  try {
    await expect(
      session.client.callTool("search_ilpo_patents", {
        applicant: "Teva",
        q: "x",
      }),
    ).rejects.toThrow("run applicant and IPC searches without them");
  } finally {
    await session.client.close();
    await session.server.close();
  }
});

test("lean trademark rows drop the customs contact columns", () => {
  expect(
    leanIlpoTrademark({
      mark_number: 1,
      customs_representative: "x",
      customs_address_start_date: "x",
      customs_representative_email: "x",
      customs_representative_phone: "x",
      extract_url: "x",
    }),
  ).toEqual({ mark_number: 1 });
});

test("Bun HTTP serves the register tools only to tokens with ilpo:read", async () => {
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
    clients: { ilpoRegister: replayClient() },
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
        .filter((n) => TOOLS.includes(n));
    } finally {
      await client.close();
    }
  };
  try {
    expect(await names("prh:read")).toEqual([]);
    expect((await names("ilpo:read")).sort()).toEqual([...TOOLS].sort());
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

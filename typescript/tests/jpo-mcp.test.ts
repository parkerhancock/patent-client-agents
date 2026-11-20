import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import type { JpoClient, JpoResult } from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { unzipSync } from "fflate";
import { createServer } from "../packages/mcp/src/index.js";
import { inCassette, pythonOutput, replayClient } from "./jpo-recordings.js";

const JPO_TOOLS = [
  "get_jpo_progress",
  "get_jpo_progress_simple",
  "get_jpo_priority_info",
  "get_jpo_registration_info",
  "get_jpo_number_reference",
  "get_jpo_jplatpat_url",
  "get_jpo_applicant",
  "get_jpo_patent_divisional_info",
  "get_jpo_patent_cited_documents",
  "get_jpo_pct_national_phase_number",
  "get_jpo_documents",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found: string[];
  details: Record<string, unknown>;
  provenance: Record<string, unknown>;
};

async function connect(jpo?: JpoClient) {
  const server = createServer(jpo ? { clients: { jpo } } : {});
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    call: async (name: string, args: Record<string, unknown>) =>
      (await client.callTool<Envelope>(name, args))
        .structuredContent as Envelope,
    async close() {
      await client.close();
      await server.close();
    },
  };
}
/** Call one tool while a cassette replays. */
async function replayed(
  cassette: string,
  name: string,
  args: Record<string, unknown>,
) {
  const session = await connect(replayClient());
  try {
    return await inCassette(cassette, () => session.call(name, args));
  } finally {
    await session.close();
  }
}

test("JPO tools appear only with a client or both JPO credentials", async () => {
  const saved = [process.env.JPO_API_USERNAME, process.env.JPO_API_PASSWORD];
  delete process.env.JPO_API_USERNAME;
  delete process.env.JPO_API_PASSWORD;
  try {
    const names = async () => {
      const session = await connect();
      try {
        return (await session.client.listTools()).map((tool) => tool.name);
      } finally {
        await session.close();
      }
    };
    expect((await names()).filter((n) => n.includes("jpo"))).toEqual([]);
    process.env.JPO_API_USERNAME = "someone";
    expect((await names()).filter((n) => n.includes("jpo"))).toEqual([]);
    process.env.JPO_API_PASSWORD = "secret";
    expect(await names()).toEqual(expect.arrayContaining(JPO_TOOLS));
    const session = await connect(replayClient());
    try {
      const tools = (await session.client.listTools()).filter((tool) =>
        JPO_TOOLS.includes(tool.name),
      );
      expect(tools).toHaveLength(JPO_TOOLS.length);
      expect(
        tools.every(
          (tool) => tool.annotations?.readOnlyHint && tool.outputSchema,
        ),
      ).toBe(true);
      const documents = tools.find((tool) => tool.name === "get_jpo_documents");
      expect(
        Object.keys(
          (documents?.inputSchema as { properties?: object } | undefined)
            ?.properties ?? {},
        ).sort(),
      ).toEqual(["application_number", "doc_kind", "ip_type", "parse"]);
    } finally {
      await session.close();
    }
  } finally {
    for (const [key, value] of [
      ["JPO_API_USERNAME", saved[0]],
      ["JPO_API_PASSWORD", saved[1]],
    ] as const)
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
  }
});

test("progress tools return Python's records in a list envelope with not_found", async () => {
  const patent = await replayed(
    "jpo-patent-app-progress-2020123456",
    "get_jpo_progress",
    { application_number: "2020123456" },
  );
  expect(patent.summary).toBe(
    "**JPO application 2020123456** — 立体配線構造体の製造方法\nFiled 20200720. Registration 7533889 (20240805).",
  );
  expect(patent.items).toEqual([
    pythonOutput["jpo-patent-app-progress-2020123456"] as Record<
      string,
      unknown
    >,
  ]);
  expect(patent.not_found).toEqual([]);
  expect(patent.provenance).toMatchObject({
    source_url:
      "https://ip-data.jpo.go.jp/api/patent/v1/app_progress/2020123456",
    source_name: "Japan Patent Office (JPO)",
    connector_version: "0.1.0",
  });
  // Python read camelCase keys its records never have, so these said "(no title)".
  const design = await replayed(
    "jpo-design-app-progress-2020015234",
    "get_jpo_progress",
    { application_number: "2020015234", ip_type: "design" },
  );
  expect(design.summary.split("\n")[0]).toBe(
    "**JPO application 2020015234** — 球体転がし用積み木",
  );
  const trademark = await replayed(
    "jpo-trademark-app-progress-2024123456",
    "get_jpo_progress",
    { application_number: "2024123456", ip_type: "trademark" },
  );
  expect(trademark.summary).not.toContain("(no title)");
  const missing = await replayed(
    "jpo-patent-app-progress-9999999999",
    "get_jpo_progress",
    { application_number: "9999999999" },
  );
  expect(missing).toMatchObject({
    summary: "**JPO application 9999999999** — no data on file.",
    items: [],
    not_found: ["9999999999"],
  });
  const simple = await replayed(
    "jpo-patent-app-progress-simple-2020123456",
    "get_jpo_progress_simple",
    { application_number: "2020123456" },
  );
  expect(simple.items[0]?.priority_right_information).toEqual([]);
});

/** A stand-in client for list fan-out: numbers starting with 9 have no data. */
function listClient(calls: string[]) {
  const result = <T>(data: T): JpoResult<T> => ({
    data,
    status_code: data ? "100" : "107",
    remaining_access_count: "1",
    provenance: {
      source_url: "https://ip-data.jpo.go.jp/api/x",
      source_name: "Japan Patent Office (JPO)",
      retrieved_at: new Date().toISOString(),
      cache_hit: false,
    },
  });
  return {
    async getProgress(ip: string, number: string) {
      calls.push(`${ip}:${number}`);
      return result(
        number.startsWith("9")
          ? null
          : {
              application_number: number,
              invention_title: "T",
              filing_date: "1",
            },
      );
    },
    async getRegistrationInfo(_ip: string, number: string) {
      calls.push(number);
      return result(
        number.startsWith("9") ? null : { registration_number: `R${number}` },
      );
    },
  } as unknown as JpoClient;
}

test("lists keep input order, report not_found and are capped before any request", async () => {
  const calls: string[] = [];
  const session = await connect(listClient(calls));
  try {
    const list = await session.call("get_jpo_progress", {
      application_number: ["2020000003", " 9000000000 ", "2020000001", ""],
      ip_type: "design",
    });
    expect(list.summary).toBe(
      "Fetched 2 of 3 JPO design progress records. Not found: 9000000000.",
    );
    expect(list.items.map((item) => item.application_number)).toEqual([
      "2020000003",
      "2020000001",
    ]);
    expect(list.not_found).toEqual(["9000000000"]);
    expect(list.provenance.source_url).toBe(
      "https://ip-data.jpo.go.jp/api/design/v1/app_progress",
    );
    expect(calls).toEqual([
      "design:2020000003",
      "design:9000000000",
      "design:2020000001",
    ]);
    const registrations = await session.call("get_jpo_registration_info", {
      application_number: ["2020000001", "9000000000"],
    });
    expect(registrations.summary).toBe(
      "Fetched 1 of 2 JPO patent registration records. Not found: 9000000000.",
    );
    calls.length = 0;
    await expect(
      session.client.callTool("get_jpo_progress", {
        application_number: Array.from(
          { length: 51 },
          (_, i) => `20200000${i}`,
        ),
      }),
    ).rejects.toThrow();
    expect(calls).toEqual([]);
  } finally {
    await session.close();
  }
});

test("lookup tools return detail envelopes from the recordings", async () => {
  const priority = await replayed(
    "jpo-patent-priority-right-app-info-2020123456",
    "get_jpo_priority_info",
    { application_number: "2020123456" },
  );
  expect(priority.summary).toBe(
    "**JPO application 2020123456** — 1 priority claim.",
  );
  expect(priority.items).toEqual(
    pythonOutput["jpo-patent-priority-right-app-info-2020123456"] as never,
  );
  const reference = await replayed(
    "jpo-patent-case-number-reference-publication-2020123456",
    "get_jpo_number_reference",
    { number: "2020123456", kind: "publication" },
  );
  expect(reference.summary).toBe(
    "**JPO publication 2020123456** — cross-reference resolved.",
  );
  expect(reference.details).toMatchObject({
    application_number: "2019013554",
    registration_number: "7193363",
  });
  const url = await replayed(
    "jpo-design-jpp-fixed-address-2020015234",
    "get_jpo_jplatpat_url",
    { application_number: "2020015234", ip_type: "design" },
  );
  expect(url.details.url).toBe(
    pythonOutput["jpo-design-jpp-fixed-address-2020015234"] as string,
  );
  const code = await replayed(
    "jpo-patent-applicant-attorney-cd-000003207",
    "get_jpo_applicant",
    { applicant: "000003207" },
  );
  expect(code).toMatchObject({
    summary: "**JPO applicant code 000003207** — トヨタ自動車株式会社",
    details: { name: "トヨタ自動車株式会社" },
  });
  const name = await replayed(
    "jpo-patent-applicant-attorney-name",
    "get_jpo_applicant",
    { applicant: "トヨタ自動車株式会社" },
  );
  expect(name.details.results).toEqual(
    pythonOutput["jpo-patent-applicant-attorney-name"] as never,
  );
  const divisional = await replayed(
    "jpo-patent-divisional-app-info-2020123456",
    "get_jpo_patent_divisional_info",
    { application_number: "2020123456" },
  );
  expect(divisional.details).toEqual(
    pythonOutput["jpo-patent-divisional-app-info-2020123456"] as never,
  );
  const cited = await replayed(
    "jpo-patent-cite-doc-info-2020123456",
    "get_jpo_patent_cited_documents",
    { application_number: "2020123456" },
  );
  expect(cited.summary).toBe(
    "**JPO patent 2020123456** — citation record resolved.",
  );
  const pct = await replayed(
    "jpo-patent-pct-national-phase-application-number-international-application-JP9999999999",
    "get_jpo_pct_national_phase_number",
    { number: "JP9999999999" },
  );
  expect(pct).toMatchObject({
    summary: "**PCT JP9999999999** — no JP national-phase record.",
    details: {},
  });
});

test("get_jpo_documents parses the bundle and delivers the raw ZIP as an artifact", async () => {
  const cassette = "jpo-patent-app-doc-cont-refusal-reason-decision-2020123456";
  // Artifacts are removed when the server closes, so read the file first.
  const open = await connect(replayClient());
  const parsed = await inCassette(cassette, () =>
    open.call("get_jpo_documents", { application_number: "2020123456" }),
  );
  expect(parsed.summary).toBe(
    "**JPO patent application 2020123456** — 2 mailed (JPO notices and decisions) documents: 拒絶理由通知書 (20240220), 特許査定 (20240704).",
  );
  const entries = parsed.details.entries as Record<string, unknown>[];
  expect(entries.map((entry) => entry.document_variant)).toEqual([
    "notice-of-rejection-a131-rn",
    "decision-of-registration-a01-rn",
  ]);
  const document = parsed.details.document as {
    file_path: string;
    filename: string;
    content_type: string;
  };
  expect(document).toMatchObject({
    filename: "jpo_patent_2020123456_mailed.zip",
    content_type: "application/zip",
  });
  expect(Object.keys(unzipSync(await readFile(document.file_path)))).toEqual([
    "06124084096-jpntce.xml",
    "06124327784-jpntce.xml",
  ]);
  await open.close();
  const raw = await replayed(cassette, "get_jpo_documents", {
    application_number: "2020123456",
    parse: false,
  });
  expect(raw.details).toMatchObject({
    application_number: "2020123456",
    ip_type: "patent",
    doc_kind: "mailed",
    entries: [],
    binary_attachments: [],
    document: { filename: "jpo_patent_2020123456_mailed.zip" },
  });
  const empty: JpoClient = {
    ...replayClient(),
    getDocuments: async () => ({
      data: {
        application_number: "1",
        ip_type: "patent",
        doc_kind: "refusal",
        entries: [],
        binary_attachments: [],
      },
      zip: null,
      provenance: {
        source_url:
          "https://ip-data.jpo.go.jp/api/patent/v1/app_doc_cont_refusal_reason/1",
        source_name: "Japan Patent Office (JPO)",
        retrieved_at: new Date().toISOString(),
        cache_hit: false,
      },
    }),
  } as unknown as JpoClient;
  const session = await connect(empty);
  try {
    expect(
      await session.call("get_jpo_documents", {
        application_number: "1",
        doc_kind: "refusal",
      }),
    ).toMatchObject({
      summary:
        "**JPO patent application 1** — no refusal (notices of reasons for refusal) documents on file.",
      details: {},
    });
  } finally {
    await session.close();
  }
});

test("Bun HTTP serves JPO tools only to tokens with jpo:read", async () => {
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
    clients: { jpo: replayClient() },
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
      (await names("kipo:read")).filter((n) => JPO_TOOLS.includes(n)),
    ).toEqual([]);
    expect(await names("jpo:read")).toEqual(expect.arrayContaining(JPO_TOOLS));
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import {
  celexNumber,
  documentText,
  EU_IP_LEGISLATION,
  type EurlexCase,
  type EurlexDocument,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import {
  eurlexCassette,
  eurlexRecording,
  replayClient,
  samples,
  toolCalls,
} from "./eurlex-recordings.js";

type Search = { cases: EurlexCase[]; total: number; more_available: boolean };
type Document = { data: EurlexDocument; provenance: { source_url: string } };

test("case-law search filters by subject, court, type, dates and title words", async () => {
  const patents = await eurlexRecording<Search>("search-patents-cj");
  expect(patents.total).toBe(59);
  expect(patents.more_available).toBe(true);
  expect(
    patents.cases.every(
      (c) => c.court === "court_of_justice" && c.document_type === "judgment",
    ),
  ).toBe(true);
  expect(patents.cases[0]).toMatchObject({
    celex: expect.stringMatching(/^6\d{4}CJ\d{4}$/),
    ecli: expect.stringMatching(/^ECLI:EU:C:/),
    heading: expect.stringMatching(/^Judgment of the Court/),
    parties: expect.any(String),
  });
  const spc = await eurlexRecording<Search>("search-words");
  expect(spc.total).toBe(66);
  expect(
    spc.cases.every((c) =>
      c.title?.toLowerCase().includes("supplementary protection certificate"),
    ),
  ).toBe(true);
  const designs = await eurlexRecording<Search>("search-dates");
  expect(
    designs.cases.every(
      (c) => c.date >= "2025-01-01" && c.date <= "2025-12-31",
    ),
  ).toBe(true);
});

test("documents come as text with CELLAR metadata, in the requested language", async () => {
  const intel = await eurlexRecording<Document>("judgment");
  expect(intel.data).toMatchObject({
    celex: samples.judgment,
    ecli: "ECLI:EU:C:2008:655",
    language: "en",
  });
  // Older judgments open with the summary, then the judgment.
  expect(intel.data.text).toMatch(/^Case C-252\/07\n/);
  expect(intel.data.text).toContain("JUDGMENT OF THE COURT");
  expect(intel.provenance.source_url).toBe(
    `https://publications.europa.eu/resource/celex/${samples.judgment}`,
  );
  const french = await eurlexRecording<Document>("judgment-french");
  expect(french.data.text).toMatch(/ARRÊT DE LA COUR/);
  const designs = await eurlexRecording<Document>("regulation");
  expect(designs.data).toMatchObject({
    title:
      "Council Regulation (EC) No 6/2002 of 12 December 2001 on Community designs",
    latest_consolidated: { celex: "02002R0006-20260701", date: "2026-07-01" },
  });
  const consolidated = await eurlexRecording<Document>("consolidated");
  expect(consolidated.data.text).toContain(
    "This text is meant purely as a documentation tool",
  );
  await expect(eurlexRecording("missing")).rejects.toMatchObject({
    code: "NOT_FOUND",
  });
});

test("the curated legislation resolves, each act to its own consolidation only", async () => {
  const { acts } = await eurlexRecording<{
    acts: ((typeof EU_IP_LEGISLATION)[number] & {
      latest_consolidated: string | null;
      title: string | null;
    })[];
  }>("legislation");
  expect(acts).toHaveLength(EU_IP_LEGISLATION.length);
  expect(acts.every((act) => act.title)).toBe(true);
  for (const act of acts)
    if (act.latest_consolidated)
      expect(
        act.latest_consolidated.startsWith(`0${act.celex.slice(1)}-`),
      ).toBe(true);
  // CELLAR also links 2023/2411 to the trade mark regulation it amends.
  expect(
    acts.find((act) => act.celex === "32023R2411")?.latest_consolidated,
  ).toBe("02023R2411-20231027");
});

test("CELEX numbers are validated and HTML becomes block text", () => {
  expect(celexNumber(" celex:32017r1001 ")).toBe("32017R1001");
  expect(celexNumber("02002R0006-20260701")).toBe("02002R0006-20260701");
  expect(() => celexNumber('32017R1001" } DROP')).toThrow("Not a CELEX number");
  expect(
    documentText(
      "<html><head><title>x</title><script>bad()</script></head><body><p>One&nbsp;two</p><table><tr><td>a</td><td>b</td></tr></table><div>Three</div></body></html>",
    ),
  ).toBe("One two\n\na b\nThree");
});

async function replayed(
  name: string,
  inspect?: (r: Record<string, unknown>) => Promise<unknown>,
) {
  const call = toolCalls[name];
  if (!call) throw new Error(`Unknown tool call ${name}`);
  const server = createServer({ clients: { eurlex: replayClient() } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    return await eurlexCassette(`mcp-${name}`, async () => {
      const result = (await client.callTool(call[0], call[1]))
        .structuredContent as Record<string, unknown>;
      return inspect ? inspect(result) : result;
    });
  } finally {
    await client.close();
    await server.close();
  }
}

test("the tools search, fetch inline or as an artifact, and list legislation", async () => {
  const search = (await replayed("search")) as {
    summary: string;
    items: Record<string, unknown>[];
  };
  expect(search.summary).toBe(
    "EU IP case law — 116 matches for `likelihood of confusion`, returned cases 1-3.",
  );
  expect(search.items[0]?.eurlex_url).toMatch(
    /^https:\/\/eur-lex\.europa\.eu\/legal-content\/EN\/TXT\/\?uri=CELEX:/,
  );
  // 34,902 characters: over the inline budget, so an artifact.
  const judgment = (await replayed("get-judgment", async (result) => {
    const details = result.details as Record<string, unknown>;
    const document = details.document as { file_path: string };
    return { details, text: await readFile(document.file_path, "utf8") };
  })) as { details: Record<string, unknown>; text: string };
  expect(judgment.details).toMatchObject({
    celex: samples.spcJudgment,
    text_length: judgment.text.length,
  });
  expect(judgment.details).not.toHaveProperty("text");
  const directive = (await replayed("get-regulation")) as {
    summary: string;
    details: Record<string, unknown>;
  };
  expect(directive.summary).toContain(
    "Latest consolidated version: 02016L0943-20160615.",
  );
  // Longer than the inline budget, so delivered as an artifact.
  expect(directive.details).toHaveProperty("document");
  expect(directive.details).not.toHaveProperty("text");
  const patents = (await replayed("list-patents")) as {
    items: Record<string, unknown>[];
  };
  expect(patents.items.map((item) => item.celex)).toEqual([
    "32012R1257",
    "32012R1260",
    "32009R0469",
    "31996R1610",
    "31998L0044",
  ]);
});

test("Bun HTTP serves the EUR-Lex tools to tokens with eurlex:read", async () => {
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
    clients: { eurlex: replayClient() },
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
    "get_eurlex_document",
    "list_eu_ip_legislation",
    "search_eu_ip_case_law",
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
    expect(await names("wipo:read")).toEqual([]);
    expect((await names("eurlex:read")).sort()).toEqual(tools);
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

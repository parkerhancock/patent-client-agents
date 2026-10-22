import { beforeAll, expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import {
  ApiError,
  assessDocketStatus,
  CanadaFederalCourtClient,
  type FederalCourtDocketEntry,
  parseCourtDate,
} from "../packages/client/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  type CanadaFederalCourtRecording,
  canadaFederalCourtRecording,
} from "./canada-federal-court-recordings.js";

let r: CanadaFederalCourtRecording;
beforeAll(async () => {
  r = await canadaFederalCourtRecording();
});

const TOOLS = [
  "search_canada_federal_court_patent_cases",
  "get_canada_federal_court_case",
  "list_canada_federal_court_docket_entries",
];
type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};

test("party search filters patent natures, dedupes files and sorts newest first", () => {
  const { patent, all } = r;
  // The recorded answer lists T-1467-20 twice among 28 rows.
  expect(patent.upstream_count).toBe(28);
  expect(all.filtered_count).toBe(27);
  expect(all.cases.filter((c) => c.court_number === "T-1467-20")).toHaveLength(
    1,
  );
  expect(patent.filtered_count).toBe(20);
  expect(patent.cases).toHaveLength(20);
  for (const c of patent.cases)
    expect(`${c.nature_en} ${c.nature_fr}`.toLowerCase()).toMatch(
      /patent|brevet/,
    );
  const dates = patent.cases.map((c) => c.filed_date ?? "");
  expect(dates).toEqual([...dates].sort().reverse());
  expect(patent.cases[0]).toMatchObject({
    court_number: "T-2962-24",
    style_of_cause: "PFIZER CANADA ULC ET AL. v. TARO PHARMACEUTICALS INC.",
    nature_en: "Patented Medicines (NOC) Regulations [Actions]",
    division: "T",
    filed_date: "2024-10-31",
    city_en: "Toronto",
  });
  expect(patent.provenance.source_name).toBe(
    "Federal Court of Canada — Court Files",
  );
  expect(
    all.cases.some((c) => /judicial review/i.test(c.nature_en ?? "")),
  ).toBe(true);
});

test("dated search uses the dated endpoint and names keep their periods", () => {
  expect(r.dated.cases.map((c) => c.court_number)).toEqual([
    "T-2962-24",
    "T-675-24",
  ]);
  for (const c of r.dated.cases) expect(c.filed_date).toStartWith("2024-");
  // Python sent "Apotex Incxxyxx", which the Registry matches to nothing.
  expect(r.dotted.upstream_count).toBe(2);
});

test("a case record carries parties, counsel and patent numbers", () => {
  const { record } = r;
  expect(record.case.court_number).toBe("T-2962-24");
  expect(record.parties[0]).toEqual({
    name: "PFIZER CANADA ULC",
    solicitor_firm: "Norton Rose Fulbright Canada",
    solicitor_contact: "JORGENSEN, PAUL",
  });
  expect(record.intellectual_property.map((ip) => ip.number)).toContain(
    "2688467",
  );
  expect(record.related_cases).toEqual([]);
  expect(r.missing).toBeInstanceOf(ApiError);
  expect((r.missing as ApiError).status).toBe(404);
});

test("evening filings keep the Registry's Eastern calendar date", () => {
  // Filed 2023-03-30 23:41 Eastern; Python's UTC conversion said March 31.
  expect(r.evening.case.filed_date).toBe("2023-03-30");
  expect(parseCourtDate("/Date(1680234093000)/")).toBe("2023-03-30");
  // A 1982 local midnight serialized with the current daylight rule.
  expect(parseCourtDate("/Date(387777600000)/")).toBe("1982-04-16");
  expect(parseCourtDate("/Date(1730406718000)/")).toBe("2024-10-31");
  expect(parseCourtDate("2024-11-21T00:00:00")).toBe("2024-11-21");
  expect(parseCourtDate(null)).toBeNull();
  expect(() => parseCourtDate("21-NOV-2024")).toThrow("Unsupported");
});

test("docket entries are newest first with a whitespace-tolerant status", () => {
  const { docket } = r;
  expect(docket.court_number).toBe("T-2962-24");
  expect(docket.total_count).toBe(10);
  expect(docket.entries.map((e) => e.entry_number)).toEqual([
    10, 9, 8, 7, 6, 5, 4, 3, 2, 1,
  ]);
  // "seeking  first case management conference" has a double space upstream.
  expect(docket.status).toEqual({
    assessment: "likely_pending",
    basis:
      "The latest recorded entry contains the prospective phrase 'seeking first case management conference'.",
    inferred: true,
  });
  const statement = docket.entries.find((e) => e.entry_number === 1);
  expect(statement?.summary).toStartWith("Statement of Claim filed");
  expect(statement?.can_download).toBe(true);
  expect(statement?.download_url).toBe(
    "https://www-u.fct-cf.gc.ca/CourtFilesAndDecisions/downloadFileFromAlfresco?foremostNum=8594362",
  );
  expect(
    docket.entries.filter((e) => e.download_url).map((e) => e.entry_number),
  ).toEqual([1]);
});

const entry = (summary: string, n = 1): FederalCourtDocketEntry => ({
  court_number: "T-1-26",
  style_of_cause: null,
  filing_date: null,
  nature_code: null,
  nature_en: null,
  track_en: null,
  office_en: null,
  document_number: null,
  entry_number: n,
  document_id: null,
  summary,
  document_date: null,
  registry_notes: null,
  command_phrase_en: null,
  command_phrase_fr: null,
  can_download: false,
  is_confidential: false,
  download_url: null,
});

test("status assessment follows Python's markers", () => {
  expect(assessDocketStatus([]).assessment).toBe("unknown");
  expect(
    assessDocketStatus([entry("Case management conference scheduled")])
      .assessment,
  ).toBe("likely_pending");
  expect(
    assessDocketStatus([
      entry("Notice of Discontinuance filed", 1),
      entry("Hearing scheduled", 2),
    ]).assessment,
  ).toBe("likely_closed");
  // Prospective language counts only on the latest entry.
  expect(
    assessDocketStatus([entry("Hearing scheduled", 1), entry("Letter", 2)])
      .assessment,
  ).toBe("unknown");
});

test("MCP helpers reproduce Python's envelopes over the recording", () => {
  const { mcpSearch, mcpGet, mcpDocket } = r;
  expect(
    mcpSearch.items.map((i) => [
      i.court_number,
      (i.status_assessment as { assessment: string }).assessment,
    ]),
  ).toEqual([
    ["T-2962-24", "likely_pending"],
    ["T-351-24", "unknown"],
    ["T-958-22", "likely_closed"],
    ["T-1467-20", "unknown"],
    ["T-671-20", "unknown"],
  ]);
  expect(Object.keys(mcpSearch.items[0] ?? {}).sort()).toEqual([
    "city_en",
    "court_number",
    "filed_date",
    "nature_en",
    "parties",
    "status_assessment",
    "style_of_cause",
  ]);
  expect(mcpSearch.more_available).toBe(true);
  expect(mcpSearch.provenance).toMatchObject({
    source_url:
      "https://www-u.fct-cf.gc.ca/en/court-files-and-decisions/court-files",
    as_of_status: "inferred per item",
    connector_version: "0.1.0",
  });
  expect(mcpSearch.summary).toContain(
    "5 returned from 20 patent-filtered hits",
  );

  expect(mcpGet.items).toHaveLength(1);
  expect(mcpGet.not_found).toEqual(["T-99999-99"]);
  expect(mcpGet.summary).toBe(
    "Fetched 1 of 2 Canadian Federal Court files. Not found: T-99999-99.",
  );
  expect(mcpGet.provenance.as_of_status).toBe("likely_pending");
  expect(mcpGet.items[0]).not.toHaveProperty("provenance");

  expect(mcpDocket.items).toHaveLength(5);
  expect(Object.keys(mcpDocket.items[0] ?? {}).sort()).toEqual([
    "document_date",
    "document_number",
    "download_url",
    "entry_number",
    "office_en",
    "summary",
  ]);
  expect(mcpDocket.more_available).toBe(true);
  expect(mcpDocket.provenance.source_url).toBe(
    "https://www-u.fct-cf.gc.ca/en/court-files-and-decisions/court-files?courtNumber=T-2962-24",
  );
});

/** A fake Registry: one patent file whose docket says it was discontinued. */
function fakeCourt(seen: URL[] = []) {
  const caseRow = {
    COURT_NO: "T-5-25",
    STYLE_OF_CAUSE: "A v. B",
    ENGLISH_NATURE_DESC: "Patent Infringement",
    FRENCH_NATURE_DESC: "Brevet - Contrefaçon",
    DIVISION: "T",
    FILE_DT: "/Date(1735707600000)/",
    Party: ["A", "B"],
  };
  return new CanadaFederalCourtClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(new Request(input, init).url);
      seen.push(url);
      const number = url.searchParams.get("courtnumber");
      const path = url.pathname.split("/").pop();
      if (number && number !== "T-5-25")
        return Response.json({ Count: 0, data: [] });
      if (path?.startsWith("ProceedingsQueriesPartyInfo"))
        return Response.json({ Count: 1, data: [caseRow] });
      if (path === "proceedingQueriesAddInfo")
        return Response.json({ Count: 1, data: [caseRow] });
      if (path === "proceedingQueriesRE")
        return Response.json({
          Count: 1,
          data: [
            {
              COURT_NO: "T-5-25",
              RE_NO: 1,
              RECORDED_ENTRY: "Notice of Discontinuance filed",
              CAN_PUBLISH_DOCUMENT: "N",
              IS_CONFIDENTIAL: "N",
            },
          ],
        });
      return Response.json({ Count: 0, data: [] });
    }) as typeof fetch,
  });
}

test("input validation and malformed responses fail loudly", async () => {
  const seen: URL[] = [];
  const client = fakeCourt(seen);
  await expect(
    client.searchPartyCases({ partyName: "Acme", filedFrom: "2024-01-01" }),
  ).rejects.toThrow("supplied together");
  await expect(
    client.searchPartyCases({
      partyName: "Acme",
      filedFrom: "2024-02-01",
      filedTo: "2024-01-01",
    }),
  ).rejects.toThrow("on or before");
  await expect(
    client.searchPartyCases({
      partyName: "Acme",
      filedFrom: "01-01-2024",
      filedTo: "2024-02-01",
    }),
  ).rejects.toThrow("YYYY-MM-DD");
  await expect(client.searchPartyCases({ partyName: " A " })).rejects.toThrow(
    "at least 2",
  );
  await expect(
    client.searchPartyCases({ partyName: "Acme", limit: 101 }),
  ).rejects.toThrow("between 1 and 100");
  await expect(
    client.listDocketEntries("T-5-25", { limit: 0 }),
  ).rejects.toThrow("between 1 and 500");
  expect(seen).toHaveLength(0);
  await client.searchPartyCases({
    partyName: "Acme Corp.",
    division: "b",
    filedFrom: "2024-01-02",
    filedTo: "2024-03-04",
  });
  expect(seen[0]?.pathname).toBe(
    "/CourtFilesAndDecisions/ProceedingsQueriesPartyInfoDates",
  );
  expect(Object.fromEntries(seen[0]?.searchParams ?? [])).toEqual({
    division: "b",
    name: "Acme Corp.",
    from: "01-02-2024",
    to: "03-04-2024",
  });
  const broken = new CanadaFederalCourtClient({
    retryLimit: 0,
    fetch: (async (_input: RequestInfo | URL) =>
      Response.json({ data: [{ COURT_NO: 5 }] })) as typeof fetch,
  });
  await expect(broken.searchPartyCases({ partyName: "Acme" })).rejects.toThrow(
    "Malformed",
  );
  const shapeless = new CanadaFederalCourtClient({
    retryLimit: 0,
    fetch: (async (_input: RequestInfo | URL) =>
      Response.json({ rows: [] })) as typeof fetch,
  });
  await expect(shapeless.getCase("T-1-25")).rejects.toThrow(
    "Unexpected Federal Court response shape",
  );
});

test("the full toolset serves the three tools and degrades failed status lookups", async () => {
  const server = createServer({
    clients: { canadaFederalCourt: fakeCourt() },
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names).toEqual(expect.arrayContaining(TOOLS));
    const search = (
      await client.callTool<Envelope>(
        "search_canada_federal_court_patent_cases",
        { party_name: "Acme", full: true },
      )
    ).structuredContent;
    expect(search?.items[0]).toMatchObject({
      court_number: "T-5-25",
      filed_date: "2025-01-01",
      nature_fr: "Brevet - Contrefaçon",
      status_assessment: { assessment: "likely_closed", inferred: true },
    });
    const single = (
      await client.callTool<Envelope>("get_canada_federal_court_case", {
        court_number: "t-5-25",
      })
    ).structuredContent;
    expect(single?.summary).toBe(
      "Fetched 1 Canadian Federal Court file(s): t-5-25.",
    );
    expect(single?.provenance.as_of_status).toBe("likely_closed");
    await expect(
      client.callTool("get_canada_federal_court_case", {
        court_number: "T-9-99",
      }),
    ).rejects.toThrow("not found");
    const docket = (
      await client.callTool<Envelope>(
        "list_canada_federal_court_docket_entries",
        { court_number: "T-5-25", full: true },
      )
    ).structuredContent;
    expect(docket?.items[0]).toMatchObject({
      entry_number: 1,
      can_download: false,
      download_url: null,
    });
    await expect(
      client.callTool("search_canada_federal_court_patent_cases", {
        party_name: "Acme",
        filed_from: "2024-01-01",
      }),
    ).rejects.toThrow("supplied together");
  } finally {
    await client.close();
    await server.close();
  }

  // A failing docket lookup leaves the case with an unknown status.
  let calls = 0;
  const flaky = new CanadaFederalCourtClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) => {
      calls++;
      if (String(input).includes("proceedingQueriesRE"))
        return new Response("down", { status: 404 });
      return Response.json({
        Count: 1,
        data: [
          {
            COURT_NO: "T-5-25",
            STYLE_OF_CAUSE: "A v. B",
            ENGLISH_NATURE_DESC: "Patent Infringement",
            DIVISION: "T",
          },
        ],
      });
    }) as typeof fetch,
  });
  const { searchCanadaFederalCourtPatentCases } = await import(
    "../packages/mcp/src/canada-federal-court.js"
  );
  const degraded = await searchCanadaFederalCourtPatentCases(flaky, {
    party_name: "Acme",
    division: "t",
    limit: 5,
    patent_only: true,
    assess_status: true,
    full: false,
  });
  expect(calls).toBe(2);
  expect(degraded.items[0]?.status_assessment).toEqual({
    assessment: "unknown",
    basis: "The docket status lookup failed; case metadata remains available.",
    inferred: true,
  });
});

test("Bun HTTP serves the tools only to tokens with fct:read", async () => {
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
    clients: { canadaFederalCourt: fakeCourt() },
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
      auth: new BearerAuth(token("cafc:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names.filter((name) => TOOLS.includes(name))).toEqual([]);
    } finally {
      await other.close();
    }
    const fct = await Client.connect(url, {
      auth: new BearerAuth(token("fct:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await fct.listTools()).map((tool) => tool.name);
      expect(names).toEqual(expect.arrayContaining(TOOLS));
      const result = await fct.callTool<Envelope>(
        "list_canada_federal_court_docket_entries",
        { court_number: "T-5-25" },
      );
      expect(result.structuredContent?.provenance.as_of_status).toBe(
        "likely_closed",
      );
    } finally {
      await fct.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

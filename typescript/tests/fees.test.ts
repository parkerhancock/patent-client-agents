import { expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import {
  EpoFeesClient,
  FeeItemSchema,
  FeeRouteError,
  FeeScheduleSchema,
  FeesClient,
  filterFees,
  parseEuroAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { feeRecording } from "./fees-recordings.js";

/** Article 2(1), item 1, Rules relating to Fees for Unitary Patent Protection, as transcribed in the Python package. */
const RFEES_UPP_ARTICLE_2: Record<number, string> = {
  2: "35.00",
  3: "105.00",
  4: "145.00",
  5: "315.00",
  6: "475.00",
  7: "630.00",
  8: "815.00",
  9: "990.00",
  10: "1175.00",
  11: "1460.00",
  12: "1775.00",
  13: "2105.00",
  14: "2455.00",
  15: "2830.00",
  16: "3240.00",
  17: "3640.00",
  18: "4055.00",
  19: "4455.00",
  20: "4855.00",
};
const cents = (amount: string) => Math.round(Number(amount) * 100);

test("real EPO feed: EPC schedule maps every code and keeps Unitary Patent fees out", async () => {
  const schedule = await feeRecording("epo-epc");
  expect(schedule.key).toBe("EP/EPO/patent");
  expect(schedule.unmapped_codes).toEqual([]);
  expect(schedule.effective_date).toBeNull();
  expect(schedule.provenance).toMatchObject({
    effective_date: null,
    as_of_status: "effective date not published by the office",
    source_name: "EPO Schedule of Fees",
  });
  expect(schedule.fees.some((fee) => /^7[0-7]\d$/.test(fee.code))).toBe(false);
  const fee = (code: string, label?: RegExp) =>
    schedule.fees.find(
      (item) => item.code === code && (!label || label.test(item.label)),
    );
  expect(fee("001", / - online$/)?.amount).toBe("135.00");
  expect(fee("002")?.category).toBe("search");
  expect(fee("015", /16th/)?.condition).toMatchObject({
    trigger: "claims_over",
    threshold: 15,
  });
  expect(fee("123")?.notes).toContain("50%");
  const renewals = filterFees(schedule.fees, { category: "renewal", year: 10 });
  expect(renewals.map((item) => [item.code, item.amount])).toEqual([
    ["040", "1865.00"],
  ]);
  // Late-payment fees 093-110 are 50% of renewals 033-050.
  for (let year = 3; year <= 20; year++) {
    const [renewal] = filterFees(schedule.fees, { category: "renewal", year });
    const [late] = filterFees(schedule.fees, { category: "late_fee", year });
    expect(cents(late?.amount ?? "0") * 2).toBe(cents(renewal?.amount ?? "-1"));
  }
  expect(schedule.recurring_fee_coverage.status).toBe("complete");
});

test("real EPO feed: Unitary Patent ladder matches RFeesUPP Article 2", async () => {
  const schedule = await feeRecording("epo-unitary");
  expect(schedule.key).toBe("UP/EPO-UP/patent");
  expect(schedule.unmapped_codes).toEqual([]);
  const ladder = Object.fromEntries(
    schedule.fees
      .filter((fee) => fee.category === "renewal")
      .map((fee) => [fee.year, fee.amount]),
  );
  expect(ladder).toEqual(RFEES_UPP_ARTICLE_2);
  for (const [year, amount] of Object.entries(RFEES_UPP_ARTICLE_2)) {
    const [late] = filterFees(schedule.fees, {
      category: "late_fee",
      year: Number(year),
    });
    expect(cents(late?.amount ?? "0") * 2).toBe(cents(amount));
  }
  expect(schedule.recurring_fee_coverage.status).toBe("complete");
});

test("euro amounts parse exactly or fail", () => {
  expect(parseEuroAmount("1.595,00")).toBe("1595.00");
  expect(parseEuroAmount("362,50")).toBe("362.50");
  expect(parseEuroAmount("17")).toBe("17.00");
  expect(parseEuroAmount("12.345.678,9")).toBe("12345678.90");
  for (const bad of ["1,595.00", "abc", "-5,00", "", "1.59,00"])
    expect(() => parseEuroAmount(bad)).toThrow();
});

function fakeFeed(body: unknown) {
  return new EpoFeesClient({
    retryLimit: 0,
    fetch: (async () => Response.json(body)) as unknown as typeof fetch,
  });
}
const node = (
  feeCode: string | null,
  feeDescription: string,
  amount: string | null,
  children: unknown[] = [],
) => ({
  key: 1,
  data: { feeCode, feeDescription, amount, validUntil: null },
  children,
});

test("feed drift is visible: unknown codes, missing years and shape changes", async () => {
  const schedule = await fakeFeed([
    node("033", "Renewal fee for the 3rd year", "725,00"),
    node("888", "Brand new fee", "10,00"),
  ]).getEpcSchedule();
  expect(schedule.unmapped_codes).toEqual(["888"]);
  expect(schedule.fees.find((fee) => fee.code === "888")?.category).toBe(
    "other",
  );
  expect(schedule.recurring_fee_coverage).toMatchObject({
    status: "partial",
    missing_years: [
      4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    ],
  });
  for (const body of [
    {},
    [],
    [{ data: { feeCode: "001" } }],
    [node("001", "Filing", "1,595.00")],
    [
      {
        ...node("001", "Filing", "1,00"),
        data: {
          ...node("001", "Filing", "1,00").data,
          validUntil: "2027-03-31",
        },
      },
    ],
  ])
    expect(
      await fakeFeed(body)
        .getEpcSchedule()
        .catch((error) => error.code),
    ).toBe("INVALID_RESPONSE");
});

test("schemas reject inconsistent fees and schedules", () => {
  const fee = {
    code: "033",
    label: "Renewal",
    category: "renewal",
    rights: ["patent"],
    amount: "725.00",
    currency: "eur",
  };
  expect(FeeItemSchema.safeParse(fee).success).toBe(false);
  expect(FeeItemSchema.parse({ ...fee, year: 3 }).currency).toBe("EUR");
  expect(
    FeeItemSchema.safeParse({ ...fee, year: 3, amount: 725 }).success,
  ).toBe(false);
  const schedule = {
    key: "EP/EPO/patent",
    jurisdiction: "EP",
    issuing_body: "EPO",
    office_code: "EPO",
    right: "patent",
    currency: "USD",
    effective_date: null,
    source_url: "https://www.epo.org/",
    statutory_basis: null,
    fees: [{ ...fee, year: 3 }],
    recurring_fee_coverage: { status: "complete" },
    notes: null,
    provenance: {
      source_url: "https://www.epo.org/",
      source_name: "x",
      retrieved_at: new Date().toISOString(),
      cache_hit: false,
      effective_date: null,
    },
  };
  expect(FeeScheduleSchema.safeParse(schedule).success).toBe(false);
  expect(
    FeeScheduleSchema.safeParse({ ...schedule, currency: "EUR" }).success,
  ).toBe(true);
  expect(
    FeeScheduleSchema.safeParse({
      ...schedule,
      currency: "EUR",
      recurring_fee_coverage: { status: "complete", missing_years: [4] },
    }).success,
  ).toBe(false);
});

test("jurisdiction resolution matches Python and separates unported offices", async () => {
  expect(resolveFeeJurisdiction("ep")).toEqual(["EP", "EPO"]);
  expect(resolveFeeJurisdiction("EP", "trademark")).toEqual(["EP", "EUIPO"]);
  expect(resolveFeeJurisdiction("Unitary Patent")).toEqual(["UP", "EPO-UP"]);
  expect(resolveFeeJurisdiction("WIPO", "design")).toEqual([
    "WO",
    "WIPO-HAGUE",
  ]);
  expect(() => resolveFeeJurisdiction("EPO", "trademark")).toThrow(
    FeeRouteError,
  );
  expect(() => resolveFeeJurisdiction("Narnia")).toThrow("Unknown");
  const client = new FeesClient();
  expect(client.supportedRoutes).toEqual(["EPO/patent", "EPO-UP/patent"]);
  expect(await client.getSchedule("DPMA").catch((error) => error.code)).toBe(
    "NOT_PORTED",
  );
  expect(
    await client.getSchedule("Germany", "design").catch((error) => error.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

function feesFromCassetteBody() {
  return [
    node("001", "Filing fee - EP direct", null, [
      node(null, "not online", "285,00"),
      node(null, "online", "135,00"),
    ]),
    ...Array.from({ length: 18 }, (_, i) =>
      node(
        String(33 + i).padStart(3, "0"),
        `Renewal fee for the ${i + 3}th year`,
        "1.000,00",
      ),
    ),
    ...Array.from({ length: 19 }, (_, i) =>
      node(String(732 + i), `Renewal fee for the ${i + 2}th year`, "100,00"),
    ),
  ];
}

test("fee MCP tools forward filters and report gaps and unported offices", async () => {
  const fees = new FeesClient({
    retryLimit: 0,
    fetch: (async () =>
      Response.json(feesFromCassetteBody())) as unknown as typeof fetch,
  });
  const server = createServer({ clients: { fees } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  type Envelope = {
    summary: string;
    items: Record<string, unknown>[];
    details?: Record<string, unknown>;
    provenance: Record<string, unknown>;
  };
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names).toEqual(
      expect.arrayContaining([
        "get_fee_schedule",
        "list_fee_jurisdictions",
        "lookup_fee",
      ]),
    );
    const schedule = await client.callTool<Envelope>("get_fee_schedule", {
      jurisdiction: "EPO",
    });
    expect(schedule.structuredContent?.summary).toContain(
      "effective date not published by the office",
    );
    expect(schedule.structuredContent?.provenance).toMatchObject({
      effective_date: null,
    });
    const renewal = await client.callTool<Envelope>("lookup_fee", {
      jurisdiction: "UP",
      category: "renewal",
      year: 10,
    });
    expect(renewal.structuredContent?.items).toEqual([
      expect.objectContaining({ code: "740", amount: "100.00", year: 10 }),
    ]);
    const none = await client.callTool<Envelope>("lookup_fee", {
      jurisdiction: "EPO",
      category: "renewal",
      year: 25,
    });
    expect(none.structuredContent?.items).toEqual([]);
    expect(none.structuredContent?.summary).toContain(
      "Recurring-fee coverage: complete",
    );
    const filing = await client.callTool<Envelope>("lookup_fee", {
      jurisdiction: "EP",
      category: "filing",
    });
    expect(filing.structuredContent?.items.map((item) => item.amount)).toEqual([
      "285.00",
      "135.00",
    ]);
    const list = await client.callTool<Envelope>("list_fee_jurisdictions", {});
    expect(list.structuredContent?.items.map((item) => item.key)).toEqual([
      "EP/EPO/patent",
      "UP/EPO-UP/patent",
    ]);
    await expect(
      client.callTool("get_fee_schedule", { jurisdiction: "JPO" }),
    ).rejects.toThrow("not yet ported");
  } finally {
    await client.close();
    await server.close();
  }
});

test("Bun HTTP serves fee tools only to tokens with fees:read", async () => {
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
  const fees = new FeesClient({
    retryLimit: 0,
    fetch: (async () =>
      Response.json(feesFromCassetteBody())) as unknown as typeof fetch,
  });
  const server = createServer({
    clients: { fees },
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
    const unsigned = `${encode({ alg: "RS256", kid: "test-key", typ: "JWT" })}.${encode({ iss: issuer, aud: audience, sub: "u", exp: Math.floor(Date.now() / 1000) + 120, scope })}`;
    return `${unsigned}.${sign("RSA-SHA256", Buffer.from(unsigned), privateKey).toString("base64url")}`;
  };
  try {
    const epo = await Client.connect(url, {
      auth: new BearerAuth(token("epo:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await epo.listTools()).map((tool) => tool.name)).not.toContain(
        "lookup_fee",
      );
    } finally {
      await epo.close();
    }
    const feesUser = await Client.connect(url, {
      auth: new BearerAuth(token("fees:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const result = await feesUser.callTool("lookup_fee", {
        jurisdiction: "EPO",
        category: "filing",
      });
      expect(result.isError).toBe(false);
    } finally {
      await feesUser.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
  }
});

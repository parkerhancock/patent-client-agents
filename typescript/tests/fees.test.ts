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
  parseUsdAmount,
  resolveFeeJurisdiction,
  UsptoFeesClient,
} from "@patent-client-agents/client";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import {
  feeRecording,
  feeRecordings,
  recordedFeeResponse,
  usptoFeePage,
} from "./fees-recordings.js";

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
  expect(client.supportedRoutes).toEqual(
    expect.arrayContaining([
      "USPTO/patent",
      "USPTO/trademark",
      "USPTO/design",
      "EPO/patent",
      "EPO-UP/patent",
    ]),
  );
  expect(resolveFeeJurisdiction("United States", "design")).toEqual([
    "US",
    "USPTO",
  ]);
  expect(await client.getSchedule("DPMA").catch((error) => error.code)).toBe(
    "NOT_PORTED",
  );
  expect(
    await client.getSchedule("Germany", "design").catch((error) => error.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

/** EPO feed fake plus every other recorded fee source, routed by URL. */
const feeFetch = (async (input: RequestInfo | URL) =>
  recordedFeeResponse(String(input instanceof Request ? input.url : input)) ??
  Response.json(feesFromCassetteBody())) as unknown as typeof fetch;
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
    fetch: feeFetch,
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
    expect(list.structuredContent?.items.map((item) => item.key)).toEqual(
      expect.arrayContaining([
        "US/USPTO/patent",
        "US/USPTO/trademark",
        "US/USPTO/design",
        "EP/EPO/patent",
        "UP/EPO-UP/patent",
      ]),
    );
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
    fetch: feeFetch,
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

/**
 * Independent check: 37 CFR as published in the eCFR (title 37 issue of
 * 2026-08-26, fetched 2026-10-21), [large, small, micro] in USD.
 */
const ECFR_PATENT: Record<string, [string, string, string]> = {
  "1.16(a) 1011": ["350.00", "140.00", "70.00"],
  "1.16(d) 1005": ["325.00", "130.00", "65.00"],
  "1.16(e) 1014": ["350.00", "140.00", "70.00"],
  "1.18(a) 1501": ["1290.00", "516.00", "258.00"],
  "1.20(e) 1551": ["2150.00", "860.00", "430.00"],
  "1.20(f) 1552": ["4040.00", "1616.00", "808.00"],
  "1.20(g) 1553": ["8280.00", "3312.00", "1656.00"],
};
const ECFR_DESIGN: Record<string, [string, string, string]> = {
  "1.16(b) 1012": ["300.00", "120.00", "60.00"],
  "1.18(b)(1) 1502": ["1300.00", "520.00", "260.00"],
};
/** 37 CFR 2.6(a)(1)(i), (a)(1)(iii), (a)(5)(i)-(ii). */
const ECFR_TRADEMARK: Record<string, string> = {
  "6001": "850.00",
  "7017": "350.00",
  "6201": "525.00",
  "7201": "325.00",
  "7931": "600.00",
};
const tierCodes = (base: string) =>
  [1, 2, 3].map((n) => `${n}${base.slice(1)}`);

test("real USPTO page: patent schedule maps every code by entity tier and matches the eCFR", async () => {
  const [schedule] = await feeRecordings("uspto");
  if (!schedule) throw new Error("missing schedule");
  expect(schedule.key).toBe("US/USPTO/patent");
  expect(schedule.effective_date).toBe("2025-01-19");
  expect(schedule.provenance).toMatchObject({
    effective_date: "2025-01-19",
    as_of_status: "effective 2025-01-19; page last revised 2026-08-14",
    source_name: "USPTO Fee Schedule",
  });
  expect(schedule.unmapped_codes).toEqual([]);
  const codes = new Set(schedule.fees.map((fee) => fee.code));
  for (const [key, amounts] of Object.entries(ECFR_PATENT)) {
    const base = key.split(" ")[1] as string;
    const rows = tierCodes(base).map((code) =>
      schedule.fees.find((fee) => fee.code === code),
    );
    expect(rows.map((row) => row?.amount)).toEqual(amounts);
    expect(rows.map((row) => row?.tier)).toEqual(["large", "small", "micro"]);
  }
  // Design (1012, 1502), plant (1013, 1503) and variable (1619) fees stay out.
  for (const code of ["1012", "1502", "1013", "1503", "1619", "9001"])
    expect(codes.has(code)).toBe(false);
  // Reissue search covers utility and design reissues (Python dropped it).
  expect(codes.has("1114")).toBe(true);
  const small = filterFees(schedule.fees, {
    category: "filing",
    tier: "small",
  });
  expect(
    small.filter((fee) => /^Basic filing fee - Utility/.test(fee.label)),
  ).toEqual([
    expect.objectContaining({ code: "2011", amount: "140.00", tier: "small" }),
    expect.objectContaining({ code: "4011", amount: "70.00", tier: "small" }),
  ]);
  expect(
    filterFees(schedule.fees, { category: "filing" }).some(
      (fee) => fee.code === "4011",
    ),
  ).toBe(false);
  expect(
    filterFees(schedule.fees, { category: "maintenance", year: 8 }),
  ).toEqual([
    expect.objectContaining({ code: "1552", amount: "4040.00", tier: "large" }),
  ]);
  expect(
    filterFees(schedule.fees, {
      category: "late_fee",
      year: 12,
      tier: "micro",
    }),
  ).toEqual([
    expect.objectContaining({
      code: "3556",
      amount: "108.00",
      condition: expect.objectContaining({ trigger: "late_days" }),
    }),
  ]);
  expect(schedule.fees.find((fee) => fee.code === "1201")?.condition).toEqual({
    trigger: "independent_claims_over",
    threshold: 3,
    per_unit: true,
    description: "Per independent claim over 3.",
  });
  expect(schedule.fees.find((fee) => fee.code === "1418")?.tier).toBe("none");
  expect(schedule.fees.find((fee) => fee.code === "1701")).toMatchObject({
    tier: "none",
    amount: "1542.00",
  });
  expect(schedule.fees.find((fee) => fee.code === "1818")?.amount).toBe(
    "195.00",
  );
  expect(schedule.fees.some((fee) => fee.code === "3818")).toBe(false);
  expect(schedule.fees.find((fee) => fee.code === "1833")).toMatchObject({
    amount: "500.00",
    notes: expect.stringContaining("previously paid"),
  });
  expect(schedule.fees.filter((fee) => fee.code === "1628")).toHaveLength(1);
  expect(
    schedule.fees.find((fee) => fee.code === "37 CFR 1.18(d)(1)"),
  ).toMatchObject({ category: "publication", amount: "0.00", tier: "none" });
  expect(schedule.recurring_fee_coverage.status).toBe("complete");
});

test("real USPTO page: design and trademark schedules", async () => {
  const [, design, trademark] = await feeRecordings("uspto");
  if (!design || !trademark) throw new Error("missing schedules");
  expect(design.key).toBe("US/USPTO/design");
  expect(design.fees.every((fee) => fee.rights[0] === "design")).toBe(true);
  for (const [key, amounts] of Object.entries(ECFR_DESIGN)) {
    const base = key.split(" ")[1] as string;
    expect(
      tierCodes(base).map(
        (code) => design.fees.find((fee) => fee.code === code)?.amount,
      ),
    ).toEqual(amounts);
  }
  expect(design.fees.some((fee) => fee.code === "1011")).toBe(false);
  expect(design.fees.some((fee) => fee.code === "1781")).toBe(true);
  expect(design.recurring_fee_coverage.status).toBe("not_applicable");

  expect(trademark.key).toBe("US/USPTO/trademark");
  expect(trademark.unmapped_codes).toEqual([]);
  for (const [code, amount] of Object.entries(ECFR_TRADEMARK))
    expect(trademark.fees.find((fee) => fee.code === code)?.amount).toBe(
      amount,
    );
  expect(trademark.fees.find((fee) => fee.code === "7017")?.condition).toEqual({
    trigger: "classes_over",
    threshold: 0,
    per_unit: true,
    description: "Per class, including the first.",
  });
  expect(
    trademark.fees.find((fee) => fee.code === "6001")?.condition?.trigger,
  ).toBe("paper_filing");
  expect(
    filterFees(trademark.fees, { category: "renewal", year: 10 }).map((fee) => [
      fee.code,
      fee.amount,
    ]),
  ).toEqual([
    ["7201", "325.00"],
    ["6201", "525.00"],
    ["7932", "325.00"],
    ["7201+7205", "650.00"],
    ["6201+6205", "950.00"],
  ]);
  // Grace-period renewal fees are late fees, not renewals (Python filed them as renewals).
  expect(trademark.fees.find((fee) => fee.code === "6203")).toMatchObject({
    category: "late_fee",
    year: 10,
    condition: expect.objectContaining({ trigger: "paper_filing" }),
  });
  // Service fees with one code for both filing methods appear once.
  expect(trademark.fees.filter((fee) => fee.code === "8501")).toHaveLength(1);
  for (const code of ["7951", "6991"])
    expect(trademark.fees.some((fee) => fee.code === code)).toBe(false);
  expect(trademark.recurring_fee_coverage.status).toBe("complete");
});

test("dollar amounts parse exactly or fail", () => {
  expect(parseUsdAmount("2,150.00")).toBe("2150.00");
  expect(parseUsdAmount("25.10")).toBe("25.10");
  expect(parseUsdAmount("11,290.00")).toBe("11290.00");
  expect(parseUsdAmount("n/a")).toBeNull();
  for (const bad of ["variable", "1.595,00", "$350", "350", "AT COST", ""])
    expect(() => parseUsdAmount(bad)).toThrow();
});

test("USPTO page drift fails or surfaces, and one fetch serves all schedules", async () => {
  const page = usptoFeePage();
  let calls = 0;
  const client = (html: string) =>
    new UsptoFeesClient({
      retryLimit: 0,
      fetch: (async () => {
        calls++;
        return new Response(html, { headers: { "content-type": "text/html" } });
      }) as unknown as typeof fetch,
    });
  const live = client(page);
  await Promise.all([
    live.getPatentSchedule(),
    live.getDesignSchedule(),
    live.getTrademarkSchedule(),
  ]);
  expect(calls).toBe(1);
  const drifted = await client(
    page.replace("<td>1806/2806/3806</td>", "<td>1999/2999/3999</td>"),
  ).getPatentSchedule();
  expect(drifted.unmapped_codes).toEqual(["1999", "2999", "3999"]);
  expect(drifted.fees.find((fee) => fee.code === "1999")?.category).toBe(
    "other",
  );
  for (const html of [
    page.replace(/Effective January 19, 2025/g, "Updated"),
    page.replace("</a>Patent search fees</h3>", "</a>Patent wizard fees</h3>"),
    page.replace("<span>2,150.00</span>", "<span>2.150,00</span>"),
    page.replace(
      "<th><strong>Small entity fee</strong></th>",
      "<th>Small</th>",
    ),
    page.replace("<td>1011/2011/3011</td>", "<td>1011-2011</td>"),
    "<html><body>Effective January 19, 2025</body></html>",
  ])
    expect(
      await client(html)
        .getPatentSchedule()
        .catch((error) => error.code),
    ).toBe("INVALID_RESPONSE");
});

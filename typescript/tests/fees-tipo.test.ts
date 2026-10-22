import { expect, test } from "bun:test";
import {
  type FeeItem,
  FeesClient,
  filterFees,
  normalizeForMatch,
  parseNtAmount,
  resolveFeeJurisdiction,
  TIPO_PATENT_FEES_URL,
  TipoFeesClient,
  trademarkEnforcedDate,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeFetch } from "./fees-recordings.js";

const recorded = feeRecordings("tipo");
const amounts = (fees: FeeItem[]) => fees.map((fee) => [fee.code, fee.amount]);

test("real TIPO patent table: rows, categories and annuity tiers", async () => {
  const [patent] = await recorded;
  expect(patent?.key).toBe("TW/TIPO/patent");
  const fees = patent?.fees ?? [];
  // 20 rows of procedural fees plus annuities for invention years 1-20,
  // utility model 1-10 and design 1-15, each at two tiers.
  expect(fees.length).toBe(110);
  expect(fees.filter((fee) => fee.category === "renewal").length).toBe(90);
  expect(patent?.effective_date).toBeNull();
  expect(patent?.provenance.as_of_status).toMatch(
    /^effective date not published by the office; page updated \d{4}-\d{2}-\d{2}$/,
  );
  expect(patent?.recurring_fee_coverage.status).toBe("complete");
  const fee = (code: string) => fees.find((item) => item.code === code);
  // Spot checks against https://www.tipo.gov.tw/en/tipo2/326.html.
  expect(fee("tipo-patent-1")).toMatchObject({
    amount: "3500.00",
    category: "filing",
    tier: "none",
  });
  expect(fee("tipo-patent-4")).toMatchObject({
    amount: "7000.00",
    category: "examination",
  });
  expect(fee("tipo-patent-5")).toMatchObject({
    amount: "800.00",
    category: "excess_claims",
    condition: { trigger: "claims_over", threshold: 10, per_unit: true },
  });
  expect(fee("tipo-patent-6")?.condition).toMatchObject({
    trigger: "pages_over",
    threshold: 50,
  });
  expect(fee("tipo-patent-11")?.category).toBe("other");
  expect(fee("tipo-patent-14")?.category).toBe("other");
  expect(fee("tipo-patent-15")).toMatchObject({
    amount: "100000.00",
    category: "petition",
  });
  expect(fee("tipo-patent-16")?.category).toBe("transfer");
  expect(fee("tipo-patent-33")?.category).toBe("other");
  // Rows 17-30 are annuities; the small tier is the reduced amount in years 1-6.
  const annuities = (year: number, tier: "large" | "small") =>
    amounts(filterFees(fees, { category: "renewal", year, tier }));
  expect(annuities(2, "large")).toEqual([
    ["tipo-annuity-invention-2-large", "2500.00"],
    ["tipo-annuity-utility-model-2-large", "2500.00"],
    ["tipo-annuity-design-2-large", "800.00"],
  ]);
  expect(annuities(2, "small")).toEqual([
    ["tipo-annuity-invention-2-small", "1700.00"],
    ["tipo-annuity-utility-model-2-small", "1700.00"],
    ["tipo-annuity-design-2-small", "0.00"],
  ]);
  expect(annuities(5, "small")).toEqual([
    ["tipo-annuity-invention-5-small", "3800.00"],
    ["tipo-annuity-utility-model-5-small", "2800.00"],
    ["tipo-annuity-design-5-small", "800.00"],
  ]);
  // No reduction from year 7: small entities pay the standard annuity.
  expect(annuities(8, "small")).toEqual([
    ["tipo-annuity-invention-8-small", "8000.00"],
    ["tipo-annuity-utility-model-8-small", "8000.00"],
    ["tipo-annuity-design-8-small", "3000.00"],
  ]);
  expect(annuities(12, "large")).toEqual([
    ["tipo-annuity-invention-12-large", "16000.00"],
    ["tipo-annuity-design-12-large", "3000.00"],
  ]);
  expect(annuities(20, "large")).toEqual([
    ["tipo-annuity-invention-20-large", "16000.00"],
  ]);
  expect(annuities(21, "large")).toEqual([]);
  for (const item of fees) expect(item.source_url).toBe(TIPO_PATENT_FEES_URL);
});

test("real TIPO trademark PDF: the catalog verifies against the bilingual text", async () => {
  const [, trademark] = await recorded;
  expect(trademark?.key).toBe("TW/TIPO/trademark");
  expect(trademark?.fees.length).toBe(30);
  expect(trademark?.effective_date).toBe("2024-05-01");
  expect(trademark?.provenance.source_url).toMatch(
    /^https:\/\/www\.tipo\.gov\.tw\/wSite\/public\/Attachment\/.+\.pdf$/,
  );
  const fees = trademark?.fees ?? [];
  const fee = (suffix: string) =>
    fees.find((item) => item.code === `tipo-tm-${suffix}`);
  expect(fee("app-class-1to34")).toMatchObject({
    amount: "3000.00",
    category: "filing",
    condition: { trigger: "classes_over", threshold: 0, per_unit: true },
  });
  expect(fee("app-class-1to34-over20-goods")).toMatchObject({
    amount: "200.00",
    condition: null,
  });
  expect(fee("app-accelerated")?.amount).toBe("6000.00");
  expect(fee("reg-trademark")).toMatchObject({
    amount: "2500.00",
    category: "grant",
  });
  expect(fee("app-efile-discount")).toMatchObject({
    category: "other",
    notes: expect.stringContaining("not a charge"),
  });
  expect(amounts(filterFees(fees, { category: "renewal", year: 10 }))).toEqual([
    ["tipo-tm-renewal-trademark", "4000.00"],
    ["tipo-tm-renewal-collective-cert-mark", "4000.00"],
  ]);
  expect(fee("invalidation")).toMatchObject({
    amount: "7000.00",
    category: "cancellation",
  });
  expect(fee("opposition")?.amount).toBe("4000.00");
});

test("TIPO parsers: amounts, normalization, enforcement date", () => {
  expect(parseNtAmount("NT$3,500")).toBe("3500.00");
  expect(parseNtAmount("NT$ 100,000")).toBe("100000.00");
  expect(parseNtAmount("NT$2,800`")).toBe("2800.00");
  expect(parseNtAmount("NT$0")).toBe("0.00");
  for (const bad of ["3,500", "NT$3.500", "NT$", "NT$1,00"])
    expect(() => parseNtAmount(bad)).toThrow();
  expect(normalizeForMatch("designate d good")).toBe("designatedgood");
  expect(normalizeForMatch("NT$6 ,0 00 每類")).toBe("nt6000");
  expect(trademarkEnforcedDate("( Enforced on May 1, 20 24 )")).toBe(
    "2024-05-01",
  );
  expect(trademarkEnforcedDate("no date")).toBeNull();
});

const replay = recordedFeeFetch();
/** Serve the recorded TIPO responses, with one page rewritten. */
function rewritten(path: string, edit: (body: string) => string) {
  return (async (input: RequestInfo | URL) => {
    const url = String(input instanceof Request ? input.url : input);
    const response = await replay(url);
    return url.endsWith(path)
      ? new Response(edit(await response.text()), { headers: response.headers })
      : response;
  }) as unknown as typeof fetch;
}

test("TIPO drift fails: reduction mismatch, header change, missing catalog entry", async () => {
  const mismatch = new TipoFeesClient({
    retryLimit: 0,
    fetch: rewritten("326.html", (body) =>
      body.replace(/(<td[^>]*>\s*)NT\$1,700(\s*<\/td>)/, "$1NT$1,600$2"),
    ),
  });
  expect(await mismatch.getPatentSchedule().catch((error) => error.code)).toBe(
    "INVALID_RESPONSE",
  );
  const header = new TipoFeesClient({
    retryLimit: 0,
    fetch: rewritten("326.html", (body) => body.replace(">Fee<", ">Amount<")),
  });
  expect(await header.getPatentSchedule().catch((error) => error.code)).toBe(
    "INVALID_RESPONSE",
  );
  const noPdf = new TipoFeesClient({
    retryLimit: 0,
    fetch: rewritten("342.html", (body) => body.replaceAll(".pdf", ".doc")),
  });
  expect(await noPdf.getTrademarkSchedule().catch((error) => error.code)).toBe(
    "INVALID_RESPONSE",
  );
});

test("TIPO routes resolve through FeesClient", async () => {
  for (const name of ["TIPO", "Taiwan", "TW", "ROC", "Chinese Taipei"])
    expect(resolveFeeJurisdiction(name, "trademark")).toEqual(["TW", "TIPO"]);
  const client = new FeesClient({
    retryLimit: 0,
    fetch: recordedFeeFetch(),
  });
  expect(client.supportedRoutes).toEqual(
    expect.arrayContaining(["TIPO/patent", "TIPO/trademark"]),
  );
  const { fees } = await client.lookupFees(
    "Taiwan",
    { category: "renewal", year: 10 },
    "trademark",
  );
  expect(fees.map((fee) => fee.amount)).toEqual(["4000.00", "4000.00"]);
  expect(
    await client.getSchedule("TW", "design").catch((error) => error.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

import { expect, test } from "bun:test";
import {
  designMultiAmounts,
  type FeeItem,
  FeesClient,
  filterFees,
  parseTryAmount,
  resolveFeeJurisdiction,
  TurkpatentFeesClient,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeResponseStrict } from "./fees-recordings.js";

const recorded = feeRecordings("turkpatent");
const pick = (fees: FeeItem[], code: string) =>
  fees.find((fee) => fee.code === code);

test("real TÜRKPATENT patent table: totals, annuities and reduced rates", async () => {
  const [patent] = await recorded;
  const fees = patent?.fees ?? [];
  expect(patent?.key).toBe("TR/TURKPATENT/patent");
  // 56 rows less three formula rows and the CHF row.
  expect(fees.length).toBe(52);
  expect(patent?.unmapped_codes).toEqual([]);
  expect(patent?.effective_date).toBeNull();
  expect(patent?.notes).toContain(
    "01.01.43 PCT receiving-office priority document (30 CHF)",
  );
  expect(fees.some((fee) => fee.amount === "0.00")).toBe(false);
  // Spot checks against https://www.turkpatent.gov.tr/patent-islem-ucretleri.
  expect(pick(fees, "tr-pat-01.01.01")).toMatchObject({
    amount: "620.00",
    category: "filing",
    notes: "Office fee TRY 81.42, VAT TRY 16.28, stamp duty TRY 522.30.",
  });
  expect(pick(fees, "tr-pat-01.01.04")?.category).toBe("publication");
  expect(pick(fees, "tr-pat-01.01.17")?.category).toBe("other");
  expect(pick(fees, "tr-pat-01.01.41")?.amount).toBe("16890.00");
  const ladder = Object.fromEntries(
    fees
      .filter((fee) => fee.category === "renewal")
      .map((fee) => [fee.year, fee.amount]),
  );
  expect(Object.keys(ladder).map(Number)).toEqual(
    Array.from({ length: 18 }, (_, i) => i + 3),
  );
  expect([ladder[3], ladder[10], ladder[20]]).toEqual([
    "3800.00",
    "10000.00",
    "26650.00",
  ]);
  expect(patent?.recurring_fee_coverage.status).toBe("complete");
  // Search and examination reports: standard (large) and reduced (small) rates.
  expect(
    filterFees(fees, { category: "search", tier: "large" }).map(
      (fee) => fee.code,
    ),
  ).toEqual(["tr-pat-01.01.49", "tr-pat-01.01.56", "tr-pat-01.01.64"]);
  expect(
    filterFees(fees, { category: "search", tier: "small" }).map((fee) => [
      fee.code,
      fee.amount,
    ]),
  ).toEqual([
    ["tr-pat-01.01.48", "2530.00"],
    ["tr-pat-01.01.56", "3130.00"],
    ["tr-pat-01.01.65", "7280.00"],
  ]);
});

test("real TÜRKPATENT trademark and design tables", async () => {
  const [, trademark, design] = await recorded;
  const tm = trademark?.fees ?? [];
  expect(trademark?.key).toBe("TR/TURKPATENT/trademark");
  expect(tm.length).toBe(29);
  expect(trademark?.effective_date).toBe("2026-01-01");
  expect(pick(tm, "tr-tm-02.01.01")?.amount).toBe("2820.00");
  expect(pick(tm, "tr-tm-02.01.02")?.condition).toMatchObject({
    trigger: "classes_over",
    threshold: 1,
    per_unit: false,
  });
  expect(pick(tm, "tr-tm-02.01.28")?.condition).toMatchObject({
    threshold: 2,
    per_unit: true,
  });
  expect(
    filterFees(tm, { category: "renewal", year: 10 }).map((fee) => fee.amount),
  ).toEqual(["8730.00"]);
  expect(pick(tm, "tr-tm-02.01.24")).toMatchObject({
    category: "late_fee",
    year: 10,
    amount: "15420.00",
  });
  expect(filterFees(tm, { category: "madrid" }).map((fee) => fee.code)).toEqual(
    ["tr-tm-02.01.19", "tr-tm-02.01.20", "tr-tm-02.01.21", "tr-tm-02.01.35"],
  );
  const ds = design?.fees ?? [];
  expect(design?.key).toBe("TR/TURKPATENT/design");
  expect(ds.length).toBe(30);
  expect(design?.effective_date).toBe("2026-01-01");
  expect(
    ds
      .filter((fee) => fee.code.startsWith("tr-des-04.01.02-"))
      .map((fee) => [fee.code, fee.amount, fee.condition?.threshold]),
  ).toEqual([
    ["tr-des-04.01.02-d2", "1674.90", 1],
    ["tr-des-04.01.02-d3to5", "318.70", 2],
    ["tr-des-04.01.02-d6plus", "760.00", 5],
  ]);
  for (const year of [5, 10, 15, 20])
    expect(
      filterFees(ds, { category: "renewal", year }).map((fee) => fee.amount),
    ).toEqual(["6340.00", "520.00"]);
  expect(
    filterFees(ds, { category: "late_fee", year: 5 }).map((fee) => fee.amount),
  ).toEqual(["11120.00", "940.00"]);
  expect(pick(ds, "tr-des-04.01.04")?.category).toBe("deferment");
});

test("TÜRKPATENT parsers and drift", async () => {
  expect(parseTryAmount("2.402,67")).toBe("2402.67");
  expect(parseTryAmount("9000")).toBe("9000.00");
  expect(parseTryAmount("522,3")).toBe("522.30");
  expect(parseTryAmount("6.066,67")).toBe("6066.67");
  expect(parseTryAmount("760,00 TL")).toBe("760.00");
  for (const bad of ["2,402.67", "30 CHF", "", "1.23"])
    expect(() => parseTryAmount(bad)).toThrow();
  expect(() =>
    designMultiAmounts("Başvurudaki 2. tasarım için: 10,00 TL"),
  ).toThrow();
  const fetch = (edit: (body: string) => string) =>
    (async (input: RequestInfo | URL) => {
      const response = recordedFeeResponseStrict(
        String(input instanceof Request ? input.url : input),
      );
      return new Response(edit(await response.text()), {
        headers: response.headers,
      });
    }) as unknown as typeof globalThis.fetch;
  // A total that no longer equals fee + VAT + stamp duty means the columns moved.
  const total = new TurkpatentFeesClient({
    retryLimit: 0,
    fetch: fetch((body) => body.replace(">620\n<", ">621\n<")),
  });
  expect(await total.getPatentSchedule().catch((error) => error.code)).toBe(
    "INVALID_RESPONSE",
  );
  const header = new TurkpatentFeesClient({
    retryLimit: 0,
    fetch: fetch((body) => body.replace("İŞLEM ÜCRETLERİ", "ÜCRETLER")),
  });
  expect(await header.getTrademarkSchedule().catch((error) => error.code)).toBe(
    "INVALID_RESPONSE",
  );
});

test("TÜRKPATENT routes resolve through FeesClient", async () => {
  for (const name of ["TURKPATENT", "TÜRKPATENT", "Türkiye", "Turkey", "TR"])
    expect(resolveFeeJurisdiction(name)).toEqual(["TR", "TURKPATENT"]);
  const client = new FeesClient({
    retryLimit: 0,
    fetch: ((input: RequestInfo | URL) =>
      Promise.resolve(
        recordedFeeResponseStrict(
          String(input instanceof Request ? input.url : input),
        ),
      )) as unknown as typeof fetch,
  });
  expect(client.supportedRoutes).toEqual(
    expect.arrayContaining([
      "TURKPATENT/patent",
      "TURKPATENT/trademark",
      "TURKPATENT/design",
    ]),
  );
  const { fees } = await client.lookupFees("Türkiye", {
    category: "renewal",
    year: 7,
  });
  expect(fees.map((fee) => fee.amount)).toEqual(["7730.00"]);
});

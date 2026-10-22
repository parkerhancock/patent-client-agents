import { expect, test } from "bun:test";
import {
  CnipaFeesClient,
  cnipaPatentFees,
  FeesClient,
  filterFees,
  parseYuanAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecording, recordedFeeFetch } from "./fees-recordings.js";

test("real CNIPA page: invention fees, PCT fees and annual fees by year", async () => {
  const schedule = await feeRecording("cnipa");
  expect(schedule.key).toBe("CN/CNIPA/patent");
  expect(schedule.currency).toBe("CNY");
  expect(schedule.effective_date).toBeNull();
  expect(schedule.unmapped_codes).toEqual([]);
  expect(schedule.fees).toHaveLength(48);
  const fee = (code: string) =>
    schedule.fees.find((item) => item.code === code);
  // Spot checks against the page.
  expect(fee("cn-i-1-invention")).toMatchObject({
    category: "filing",
    amount: "900.00",
  });
  expect(fee("cn-v-v-fee-for-substantive-examination-for-an")).toMatchObject({
    category: "examination",
    amount: "2500.00",
  });
  expect(fee("cn-vi-1-invention")).toMatchObject({
    category: "appeal",
    amount: "1000.00",
  });
  expect(fee("cn-xiii-1-invention")).toMatchObject({
    category: "cancellation",
    amount: "3000.00",
  });
  expect(
    fee("cn-ii-additional-fee-for-each-page-of-the-desc")?.condition,
  ).toMatchObject({ trigger: "pages_over", threshold: 300 });
  expect(
    fee("cn-ii-1-additional-fee-for-each-claim-exceeds-")?.condition,
  ).toMatchObject({ trigger: "claims_over", threshold: 10 });
  // PCT rows keep their own sections and categories.
  expect(fee("cn-pct-i-1-search-fee")).toMatchObject({
    category: "search",
    amount: "2100.00",
  });
  expect(fee("cn-pct-ii-1-surcharge-for-the-late-entry")).toMatchObject({
    category: "late_fee",
    amount: "1000.00",
  });
  // Utility model and design rows are excluded.
  expect(schedule.fees.some((item) => item.amount === "500.00")).toBe(false);
  const ladder = Object.fromEntries(
    schedule.fees
      .filter((item) => item.category === "renewal")
      .map((item) => [item.year, item.amount]),
  );
  expect(
    filterFees(schedule.fees, { category: "renewal", year: 20 }),
  ).toHaveLength(1);
  expect(ladder).toEqual({
    1: "900.00",
    2: "900.00",
    3: "900.00",
    4: "1200.00",
    5: "1200.00",
    6: "1200.00",
    7: "2000.00",
    8: "2000.00",
    9: "2000.00",
    10: "4000.00",
    11: "4000.00",
    12: "4000.00",
    13: "6000.00",
    14: "6000.00",
    15: "6000.00",
    16: "8000.00",
    17: "8000.00",
    18: "8000.00",
    19: "8000.00",
    20: "8000.00",
  });
  expect(schedule.recurring_fee_coverage.status).toBe("complete");
});

test("CNIPA amounts, unknown rows and aliases", async () => {
  expect(parseYuanAmount("2,500")).toBe("2500.00");
  expect(() => parseYuanAmount("2.500,00")).toThrow();
  const { fees, unmapped } = cnipaPatentFees([
    ["Patent Fees – Domestic", null],
    ["I.Filing Fee", null],
    ["1. Invention", "900"],
    ["2. Utility Model", "500"],
    ["VIII.Brand New Fee", "10"],
    ["VII.Annual Fee", null],
    ["1. Invention", null],
    ["1-3 Years (Each Year)", "900"],
  ]);
  expect(unmapped).toEqual(["VIII.Brand New Fee"]);
  expect(fees.map((fee) => [fee.code, fee.year])).toEqual([
    ["cn-i-1-invention", null],
    ["cn-vii-1-3-years-each-year-y1", 1],
    ["cn-vii-1-3-years-each-year-y2", 2],
    ["cn-vii-1-3-years-each-year-y3", 3],
  ]);
  expect(resolveFeeJurisdiction("China")).toEqual(["CN", "CNIPA"]);
  const client = new FeesClient({
    retryLimit: 0,
    fetch: recordedFeeFetch(),
  });
  expect((await client.getSchedule("CN")).key).toBe("CN/CNIPA/patent");
  expect(
    await client.getSchedule("CN", "design").catch((error) => error.code),
  ).toBe("UNSUPPORTED_RIGHT");
  const broken = new CnipaFeesClient({
    retryLimit: 0,
    fetch: (async () =>
      new Response("<html></html>")) as unknown as typeof fetch,
  });
  await expect(broken.getPatentSchedule()).rejects.toThrow("fee table");
});

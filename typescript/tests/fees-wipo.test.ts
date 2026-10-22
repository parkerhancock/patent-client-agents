import { expect, test } from "bun:test";
import {
  type FeeSchedule,
  FeesClient,
  filterFees,
  resolveFeeJurisdiction,
  WipoFeesClient,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeResponseByUrl } from "./fees-recordings.js";

/** The PCT, Madrid and Hague Schedules of Fees, recorded October 22, 2026. */
const recording = feeRecordings("wipo");
const schedule = async (office: string) => {
  const found = (await recording).find((item) => item.office_code === office);
  if (!found) throw new Error(`No ${office} schedule.`);
  return found;
};
const fee = (s: FeeSchedule, code: string) => {
  const found = s.fees.find((item) => item.code === code);
  if (!found) throw new Error(`No ${code} in ${s.key}.`);
  return found;
};

test("real WIPO pages: three schedules, in-force dates as the pages state them", async () => {
  const schedules = await recording;
  expect(
    schedules.map((s) => [s.key, s.fees.length, s.effective_date]),
  ).toEqual([
    ["WO/WIPO-PCT/patent", 7, null],
    ["WO/WIPO-MADRID/trademark", 30, "2023-02-01"],
    ["WO/WIPO-HAGUE/design", 32, "2026-07-01"],
  ]);
  for (const s of schedules) {
    expect(s.currency).toBe("CHF");
    expect(s.unmapped_codes).toEqual([]);
    expect(s.fees.every((item) => item.tier === "none")).toBe(true);
  }
  expect((await schedule("WIPO-PCT")).recurring_fee_coverage.status).toBe(
    "not_applicable",
  );
});

test("PCT: filing fee with its per-sheet fee, and reductions that are not charges", async () => {
  const pct = await schedule("WIPO-PCT");
  expect(
    pct.fees.map((item) => [item.code, item.amount, item.category]),
  ).toEqual([
    ["wo-pct-1", "1330.00", "filing"],
    ["wo-pct-1-sheet", "15.00", "excess_pages"],
    ["wo-pct-2", "200.00", "search"],
    ["wo-pct-3", "200.00", "examination"],
    ["wo-pct-4-a", "100.00", "other"],
    ["wo-pct-4-b", "200.00", "other"],
    ["wo-pct-4-c", "300.00", "other"],
  ]);
  expect(fee(pct, "wo-pct-1-sheet").condition).toMatchObject({
    trigger: "sheets_over",
    threshold: 30,
  });
  expect(fee(pct, "wo-pct-4-a").notes).toContain("not a charge");
});

test("Madrid: renewal at year 10 with the grace surcharge computed from item 6.1", async () => {
  const madrid = await schedule("WIPO-MADRID");
  expect(fee(madrid, "wo-madrid-2-1-1").amount).toBe("653.00");
  expect(fee(madrid, "wo-madrid-2-1-2").amount).toBe("903.00");
  expect(fee(madrid, "wo-madrid-2-2").condition).toMatchObject({
    trigger: "classes_over",
    threshold: 3,
  });
  expect(
    filterFees(madrid.fees, { category: "renewal", year: 10 }).map((item) => [
      item.code,
      item.amount,
    ]),
  ).toEqual([
    ["wo-madrid-6-1", "653.00"],
    ["wo-madrid-6-2", "100.00"],
    ["wo-madrid-6-3", "100.00"],
  ]);
  expect(fee(madrid, "wo-madrid-6-5")).toMatchObject({
    amount: "326.50",
    category: "late_fee",
    year: 10,
  });
  expect(fee(madrid, "wo-madrid-7-6").category).toBe("petition");
  expect(fee(madrid, "wo-madrid-4-1-term").amount).toBe("4.00");
  expect(fee(madrid, "wo-madrid-8-1-1").amount).toBe("155.00");
  expect(fee(madrid, "wo-madrid-8-1-2").amount).toBe("10.00");
  expect(madrid.recurring_fee_coverage.status).toBe("complete");
});

test("Hague: five-yearly renewals, recordals as recordals, 14bis kept", async () => {
  const hague = await schedule("WIPO-HAGUE");
  expect(fee(hague, "wo-hague-1-1")).toMatchObject({
    label: "Basic fee - For one design",
    amount: "397.00",
    category: "filing",
  });
  expect(fee(hague, "wo-hague-4-3-1").amount).toBe("90.00");
  expect(fee(hague, "wo-hague-4-3-2").condition).toMatchObject({
    trigger: "multi_design",
    threshold: 1,
  });
  expect(
    filterFees(hague.fees, { category: "renewal", year: 5 }).map((item) => [
      item.code,
      item.amount,
    ]),
  ).toEqual([
    ["wo-hague-7-1", "200.00"],
    ["wo-hague-7-2", "17.00"],
    ["wo-hague-8-1", "21.00"],
    ["wo-hague-8-2", "1.00"],
  ]);
  expect(fee(hague, "wo-hague-13").category).toBe("transfer");
  expect(fee(hague, "wo-hague-17").category).toBe("other");
  expect(fee(hague, "wo-hague-14bis-1").amount).toBe("144.00");
  expect(hague.recurring_fee_coverage.status).toBe("complete");
});

test("WIPO schedule drift fails instead of guessing an amount", async () => {
  const client = new WipoFeesClient({
    retryLimit: 0,
    fetch: (async () =>
      new Response(
        "<table><tbody><tr><td>2.1.1 where no representation</td><td>about 650</td></tr></tbody></table>",
      )) as unknown as typeof fetch,
  });
  for (const call of [
    client.getMadridSchedule(),
    client.getHagueSchedule(),
    client.getPctSchedule(),
  ])
    expect(await call.catch((error) => error.code)).toBe("INVALID_RESPONSE");
});

test("WIPO aliases route by right", async () => {
  expect(resolveFeeJurisdiction("Madrid Protocol", "trademark")).toEqual([
    "WO",
    "WIPO-MADRID",
  ]);
  const client = new FeesClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) =>
      recordedFeeResponseByUrl(
        String(input instanceof Request ? input.url : input),
      ) ?? new Response("missing", { status: 404 })) as typeof fetch,
  });
  expect((await client.getSchedule("WIPO")).key).toBe("WO/WIPO-PCT/patent");
  expect((await client.getSchedule("WO", "design")).key).toBe(
    "WO/WIPO-HAGUE/design",
  );
  expect((await client.getSchedule("Hague System", "design")).key).toBe(
    "WO/WIPO-HAGUE/design",
  );
  expect(
    await client.getSchedule("PCT", "trademark").catch((e) => e.code),
  ).toBe("UNSUPPORTED_RIGHT");
  expect(
    await client.getSchedule("WIPO", "utility_model").catch((e) => e.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

import { expect, test } from "bun:test";
import {
  type FeeSchedule,
  FeesClient,
  filterFees,
  IlpoFeesClient,
  parseShekelAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeFetch } from "./fees-recordings.js";

const offline = (async () => {
  throw new Error("unrecorded request");
}) as unknown as typeof fetch;
const amounts = (schedule: FeeSchedule) =>
  Object.fromEntries(schedule.fees.map((fee) => [fee.code, fee.amount]));

test("real ILPO notice: patent schedule, 2026 amounts", async () => {
  const [patent] = await feeRecordings("ilpo");
  if (!patent) throw new Error("no patent schedule");
  expect(patent.key).toBe("IL/ILPO/patent");
  expect(patent.currency).toBe("ILS");
  expect(patent.effective_date).toBe("2026-01-01");
  expect(patent.provenance.effective_date).toBe("2026-01-01");
  expect(patent.fees).toHaveLength(47);
  expect(patent.notes).toContain("Hebrew");
  // Spot checks against the Hebrew PDF.
  expect(amounts(patent)).toMatchObject({
    "il-pat-1": "2402.00",
    "il-pat-1-small": "1441.00",
    "il-pat-2": "616.00",
    "il-pat-3": "300.00",
    "il-pat-6": "2101.00",
    "il-pat-8-2": "11910.00",
    "il-pat-10": "841.00",
    "il-pat-10-small": "505.00",
    "il-pat-13": "2402.00",
    "il-pat-14": "4203.00",
    "il-pat-12-6": "14410.00",
    "il-pat-pte-ren-y4": "7223.00",
    "il-pat-pte-opposition": "2402.00",
    "il-pat-pte-cancel": "4804.00",
  });
  const filing = patent.fees.filter((fee) =>
    /^il-pat-1(?:-small)?$/.test(fee.code),
  );
  expect(filing.map((fee) => fee.tier)).toEqual(["large", "small"]);
  expect(
    patent.fees.find((fee) => fee.code === "il-pat-2")?.condition,
  ).toMatchObject({ trigger: "claims_over", threshold: 50, per_unit: true });
  expect(
    patent.fees.find((fee) => fee.code === "il-pat-3")?.condition,
  ).toMatchObject({ trigger: "pages_over", threshold: 100 });
});

test("real ILPO notice: patent renewals are period payments, extensions are years 21-25", async () => {
  const [patent] = await feeRecordings("ilpo");
  if (!patent) throw new Error("no patent schedule");
  const renewals = patent.fees
    .filter((fee) => fee.category === "renewal")
    .map((fee) => [fee.year, fee.amount]);
  expect(renewals).toEqual([
    [6, "961.00"],
    [10, "1921.00"],
    [14, "2882.00"],
    [18, "4803.00"],
    [20, "6725.00"],
    [21, "3484.00"],
    [22, "4180.00"],
    [23, "5016.00"],
    [24, "6019.00"],
    [25, "7223.00"],
  ]);
  // The whole-term payment is an alternative, not a year-20 renewal.
  expect(
    filterFees(patent.fees, { category: "renewal", year: 20 }).map(
      (fee) => fee.code,
    ),
  ).toEqual(["il-pat-12-5"]);
  expect(patent.fees.find((fee) => fee.code === "il-pat-12-6")?.category).toBe(
    "other",
  );
  expect(patent.recurring_fee_coverage.status).toBe("complete");
});

test("real ILPO notice: trade mark and design schedules", async () => {
  const [, trademark, design] = await feeRecordings("ilpo");
  if (!trademark || !design) throw new Error("missing schedules");
  expect(trademark.key).toBe("IL/ILPO/trademark");
  expect(trademark.fees).toHaveLength(19);
  expect(amounts(trademark)).toMatchObject({
    "il-tm-1": "1904.00",
    "il-tm-1-2": "1432.00",
    "il-tm-4": "3393.00",
    "il-tm-4-2": "2864.00",
    "il-tm-11": "573.00",
    "il-tm-13": "4.30",
  });
  expect(
    trademark.fees
      .filter((fee) => fee.category === "madrid")
      .map((fee) => fee.amount),
  ).toEqual(["626.00", "626.00", "626.00"]);
  expect(
    filterFees(trademark.fees, { category: "renewal", year: 10 })[0]?.code,
  ).toBe("il-tm-4");
  expect(trademark.fees.every((fee) => fee.tier === "none")).toBe(true);

  expect(design.key).toBe("IL/ILPO/design");
  expect(design.fees).toHaveLength(21);
  expect(amounts(design)).toMatchObject({
    "il-des-1": "471.00",
    "il-des-1-small": "283.00",
    "il-des-2": "707.00",
    "il-des-2-small": "424.00",
    "il-des-10": "1178.00",
  });
  expect(
    design.fees
      .filter((fee) => fee.category === "renewal")
      .map((fee) => [fee.year, fee.amount]),
  ).toEqual([
    [10, "589.00"],
    [15, "707.00"],
    [20, "825.00"],
    [25, "943.00"],
  ]);
  expect(design.fees.find((fee) => fee.code === "il-des-5-5")).toMatchObject({
    category: "other",
    amount: "3535.00",
  });
});

test("ILPO amounts, aliases, shared fetch and drift", async () => {
  expect(parseShekelAmount("2, 402")).toBe("2402.00");
  expect(parseShekelAmount("4.3")).toBe("4.30");
  expect(parseShekelAmount("0. 6 0")).toBe("0.60");
  for (const bad of ["2.402,00", "abc", ""])
    expect(() => parseShekelAmount(bad)).toThrow();
  expect(resolveFeeJurisdiction("Israel", "design")).toEqual(["IL", "ILPO"]);
  let calls = 0;
  const replay = recordedFeeFetch(["ilpo"], offline);
  const client = new IlpoFeesClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      calls++;
      return replay(input, init);
    }) as typeof fetch,
  });
  await Promise.all([
    client.getPatentSchedule(),
    client.getTrademarkSchedule(),
    client.getDesignSchedule(),
  ]);
  expect(calls).toBe(1);
  const fees = new FeesClient({ retryLimit: 0, fetch: replay });
  expect((await fees.getSchedule("ISRAEL", "trademark")).key).toBe(
    "IL/ILPO/trademark",
  );
  const broken = new IlpoFeesClient({
    retryLimit: 0,
    fetch: (async () =>
      new Response("<html>blocked</html>")) as unknown as typeof fetch,
  });
  await expect(broken.getPatentSchedule()).rejects.toThrow();
});

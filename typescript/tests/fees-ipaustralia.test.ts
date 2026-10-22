import { expect, test } from "bun:test";
import {
  FeesClient,
  filterFees,
  IpAustraliaFeesClient,
  ipaustraliaRenewalFees,
  parseAudAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecording, recordedFeeFetch } from "./fees-recordings.js";

test("real IP Australia pages: procedural fees and claim fees", async () => {
  const schedule = await feeRecording("ipaustralia");
  expect(schedule.key).toBe("AU/IPAU/patent");
  expect(schedule.currency).toBe("AUD");
  expect(schedule.effective_date).toBe("2024-10-01");
  expect(schedule.unmapped_codes).toEqual([]);
  expect(schedule.fees).toHaveLength(67);
  const fee = (code: string) =>
    schedule.fees.find((item) => item.code === code);
  // Spot checks against the timeframes-and-fees page.
  expect(fee("au-standard-patent-standard-patent-application")).toMatchObject({
    category: "filing",
    amount: "400.00",
  });
  expect(fee("au-provisional-pat-provisional-patent-application")?.amount).toBe(
    "100.00",
  );
  expect(fee("au-postal-applicat-standard-patent-application")).toMatchObject({
    amount: "600.00",
    condition: { trigger: "paper_filing" },
  });
  expect(fee("au-fees-examination-request")).toMatchObject({
    category: "examination",
    amount: "550.00",
  });
  expect(
    fee("au-fees-standard-patent-acceptance-mandatory-up-to-20-clai"),
  ).toMatchObject({ category: "grant", amount: "300.00" });
  expect(
    fee("au-voluntary-amend-examination-of-more-than-30-claims"),
  ).toMatchObject({
    amount: "250.00",
    condition: { trigger: "claims_over", threshold: 30, per_unit: true },
  });
  expect(
    fee("au-fees-if-the-specification-was-proposed-to-contain-31-or"),
  ).toMatchObject({ amount: "250.00", condition: { threshold: 30 } });
  expect(fee("au-re-examination--re-examination-request")?.amount).toBe(
    "800.00",
  );
  // The acceptance fee is listed in both claim-fee regimes but stored once.
  expect(
    schedule.fees.filter((item) => item.category === "grant"),
  ).toHaveLength(1);
});

test("real IP Australia renewal page: years 4-24, online and other payment", async () => {
  const schedule = await feeRecording("ipaustralia");
  const online = Object.fromEntries(
    schedule.fees
      .filter((item) =>
        item.code.startsWith("au-standard-patent-online-renewal"),
      )
      .map((item) => [item.year, item.amount]),
  );
  expect(online).toEqual({
    4: "300.00",
    5: "315.00",
    6: "345.00",
    7: "380.00",
    8: "420.00",
    9: "465.00",
    10: "540.00",
    11: "645.00",
    12: "780.00",
    13: "945.00",
    14: "1140.00",
    15: "1385.00",
    16: "1675.00",
    17: "2010.00",
    18: "2390.00",
    19: "2815.00",
    20: "4000.00",
    21: "5000.00",
    22: "6000.00",
    23: "7000.00",
    24: "8000.00",
  });
  const year10 = filterFees(schedule.fees, { category: "renewal", year: 10 });
  expect(year10.map((item) => [item.amount, item.condition?.trigger])).toEqual([
    ["540.00", undefined],
    ["590.00", "paper_filing"],
  ]);
  expect(
    schedule.fees.find(
      (item) => item.code === "au-patent-renewal-grace-period",
    ),
  ).toMatchObject({ category: "late_fee", amount: "100.00" });
  expect(schedule.recurring_fee_coverage.status).toBe("complete");
});

test("IP Australia amounts, aliases and drift", async () => {
  expect(parseAudAmount("$1100")).toBe("1100.00");
  expect(parseAudAmount("$1,100")).toBe("1100.00");
  expect(() => parseAudAmount("$1.100,00")).toThrow();
  expect(() => ipaustraliaRenewalFees("<main><p>moved</p></main>")).toThrow(
    "renewal table",
  );
  expect(resolveFeeJurisdiction("IP Australia")).toEqual(["AU", "IPAU"]);
  const client = new FeesClient({
    retryLimit: 0,
    fetch: recordedFeeFetch(),
  });
  expect((await client.getSchedule("Australia")).key).toBe("AU/IPAU/patent");
  const broken = new IpAustraliaFeesClient({
    retryLimit: 0,
    fetch: (async () =>
      new Response("<main></main>")) as unknown as typeof fetch,
  });
  await expect(broken.getPatentSchedule()).rejects.toThrow();
});

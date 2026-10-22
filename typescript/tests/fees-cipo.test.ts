import { expect, test } from "bun:test";
import {
  CipoFeesClient,
  cipoFees,
  cipoYears,
  FeesClient,
  filterFees,
  parseCadAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { recordedFeeFetch } from "./fees-recordings.js";

const replay = recordedFeeFetch();
const recording = () =>
  new CipoFeesClient({ retryLimit: 0, fetch: replay }).getPatentSchedule();

test("archived CIPO page: the current year's list with small and standard tiers", async () => {
  const schedule = await recording();
  expect(schedule.key).toBe("CA/CIPO/patent");
  expect(schedule.currency).toBe("CAD");
  expect(schedule.effective_date).toBe("2026-01-01");
  expect(schedule.notes).toContain("2027");
  expect(schedule.unmapped_codes).toEqual([]);
  expect(schedule.fees).toHaveLength(163);
  const fee = (code: string) =>
    schedule.fees.find((item) => item.code === code);
  // Spot checks against the 2026 list.
  expect(fee("application-fee-s")).toMatchObject({
    tier: "small",
    amount: "241.24",
  });
  expect(fee("application-fee-l")).toMatchObject({
    category: "filing",
    tier: "large",
    amount: "595.06",
  });
  expect(fee("request-for-examination-fee-fe-l-2")?.amount).toBe("1190.13");
  expect(fee("request-for-examination-fee-fe-l-3")).toMatchObject({
    category: "excess_claims",
    amount: "117.94",
    condition: { trigger: "claims_over", threshold: 20 },
  });
  expect(fee("final-fee-n")).toMatchObject({
    category: "excess_pages",
    amount: "8.58",
    condition: { trigger: "pages_over", threshold: 100 },
  });
  expect(fee("search-fee-n")).toMatchObject({
    category: "search",
    amount: "2380.26",
  });
  expect(fee("re-examination-fee-l")?.amount).toBe("2975.32");
  expect(fee("advanced-examination-fee-n")?.tier).toBe("none");
});

test("archived CIPO page: maintenance bands expand to every anniversary", async () => {
  const schedule = await recording();
  const expected: Record<number, [string, string]> = {
    2: ["60.26", "134.02"],
    4: ["60.26", "134.02"],
    5: ["107.22", "297.00"],
    9: ["107.22", "297.00"],
    10: ["134.02", "372.05"],
    14: ["134.02", "372.05"],
    15: ["271.26", "669.05"],
    19: ["271.26", "669.05"],
    20: ["410.80", "1027.00"],
  };
  for (const [year, [small, large]] of Object.entries(expected)) {
    const rows = (tier: "small" | "large") =>
      filterFees(schedule.fees, {
        category: "renewal",
        year: Number(year),
        tier,
      }).map((item) => item.amount);
    // One row for a pending application, one for a granted patent.
    expect(rows("small")).toEqual([small, small]);
    expect(rows("large")).toEqual([large, large]);
  }
  expect(schedule.recurring_fee_coverage.status).toBe("complete");
});

test("CIPO helpers, aliases and drift", async () => {
  expect(parseCadAmount("1,027.00")).toBe("1027.00");
  expect(parseCadAmount("See description")).toBeNull();
  expect(() => parseCadAmount("1.027,00")).toThrow();
  expect(
    cipoYears("each of the second, third and fourth anniversaries"),
  ).toEqual([2, 3, 4]);
  expect(cipoYears("each of the 10th, 11th, 12th, 13th and 14th")).toEqual([
    10, 11, 12, 13, 14,
  ]);
  expect(cipoYears("the 20th and each subsequent anniversary")).toEqual([20]);
  const { unmapped } = cipoFees({
    year: 2026,
    rows: [
      {
        caption: "Fees in respect of patents",
        feeType: "Brand new fee",
        description: "x",
        small: "1.00",
        standard: "2.00",
      },
    ],
  });
  expect(unmapped).toEqual(["Brand new fee"]);
  expect(resolveFeeJurisdiction("Canada")).toEqual(["CA", "CIPO"]);
  const client = new FeesClient({
    retryLimit: 0,
    fetch: replay,
  });
  expect((await client.getSchedule("CA")).key).toBe("CA/CIPO/patent");
  const broken = new CipoFeesClient({
    retryLimit: 0,
    fetch: (async () =>
      new Response(
        "<h2>2026 list of fees for patents</h2><table><caption>New</caption></table>",
      )) as unknown as typeof fetch,
  });
  await expect(broken.getPatentSchedule()).rejects.toThrow(
    "unrecognized table",
  );
});

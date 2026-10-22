import { expect, test } from "bun:test";
import {
  DpmaFeesClient,
  dpmaPatentFees,
  dpmaRows,
  FeesClient,
  filterFees,
  parseDpmaAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecording, recordedFeeFetch } from "./fees-recordings.js";

const fee = (
  schedule: Awaited<ReturnType<typeof feeRecording>>,
  code: string,
) => schedule.fees.find((item) => item.code === code);

test("real DPMA form A 9510.1: patent fees by fee number", async () => {
  const schedule = await feeRecording("dpma");
  expect(schedule.key).toBe("DE/DPMA/patent");
  expect(schedule.currency).toBe("EUR");
  expect(schedule.effective_date).toBeNull();
  expect(schedule.provenance.as_of_status).toContain("edition July 2026");
  expect(schedule.unmapped_codes).toEqual([]);
  expect(schedule.fees).toHaveLength(101);
  expect(schedule.fees.every((item) => item.code.startsWith("31"))).toBe(true);
  // Spot checks against the PDF (edition July 2026).
  expect(fee(schedule, "311 000")).toMatchObject({
    category: "filing",
    amount: "40.00",
  });
  expect(fee(schedule, "311 050")).toMatchObject({
    category: "excess_claims",
    amount: "20.00",
    condition: { trigger: "claims_over", threshold: 10, per_unit: true },
  });
  expect(fee(schedule, "311 050")?.label).toContain(
    "for each additional claim",
  );
  expect(fee(schedule, "311 100")).toMatchObject({
    amount: "60.00",
    condition: { trigger: "paper_filing" },
  });
  expect(fee(schedule, "311 200")).toMatchObject({
    category: "search",
    amount: "300.00",
  });
  expect(fee(schedule, "311 400")?.amount).toBe("350.00");
  // Rows whose text wraps across lines (missing from the Python scraper).
  expect(fee(schedule, "311 500")?.amount).toBe("300.00");
  expect(fee(schedule, "313 820")).toMatchObject({
    category: "translation",
    amount: "150.00",
  });
  expect(fee(schedule, "313 900")?.amount).toBe("90.00");
  expect(fee(schedule, "313 600")).toMatchObject({
    category: "opposition",
    amount: "200.00",
  });
});

test("real DPMA: annual fees for years 3-20 with licence-of-right and late rows", async () => {
  const schedule = await feeRecording("dpma");
  const ladder = Object.fromEntries(
    schedule.fees
      .filter((item) => item.category === "renewal" && /0$/.test(item.code))
      .map((item) => [item.year, item.amount]),
  );
  expect(ladder).toMatchObject({
    3: "70.00",
    4: "70.00",
    5: "100.00",
    10: "430.00",
    15: "1130.00",
    20: "2030.00",
  });
  for (let year = 3; year <= 20; year++) {
    const rows = filterFees(schedule.fees, { category: "renewal", year });
    const [standard, licence] = rows.map((item) => Number(item.amount));
    expect(rows).toHaveLength(2);
    expect(licence).toBe((standard ?? 0) / 2);
    expect(
      filterFees(schedule.fees, { category: "late_fee", year })[0]?.amount,
    ).toBe("50.00");
  }
  // Supplementary protection certificate years 1-6 are years 21-26.
  expect(fee(schedule, "312 210")).toMatchObject({
    category: "renewal",
    year: 21,
    amount: "2920.00",
  });
  expect(fee(schedule, "312 260")?.year).toBe(26);
  expect(fee(schedule, "312 205")).toMatchObject({
    category: "other",
    year: 3,
    amount: "210.00",
  });
  expect(schedule.recurring_fee_coverage.status).toBe("complete");
});

test("DPMA amounts and row continuation parse exactly", () => {
  expect(parseDpmaAmount("2 030")).toBe("2030.00");
  expect(parseDpmaAmount("70")).toBe("70.00");
  for (const bad of ["1.130", "1,130", "", "70 €"])
    expect(() => parseDpmaAmount(bad)).toThrow();
  const rows = dpmaRows([
    [
      "Application procedure for national applications",
      "311 000 - containing up to ten patent claims ........ 40",
      "311 500 Application procedure relating to a certificate (section 49a of",
      "the Patent Act)........................ 300",
      "312 030 for the 3rd year of the patent ........ 70",
      "312 999 an unknown fee ........ 5",
    ].join("\n"),
  ]);
  expect(rows.map((row) => [row.code, row.amount])).toEqual([
    ["311 000", "40.00"],
    ["311 500", "300.00"],
    ["312 030", "70.00"],
    ["312 999", "5.00"],
  ]);
  const { fees, unmapped } = dpmaPatentFees(rows);
  expect(unmapped).toEqual(["312 999"]);
  expect(fees[0]?.label).toBe(
    "Application procedure for national applications - containing up to ten patent claims",
  );
});

test("DPMA routes by alias and fails on an unrecognized PDF", async () => {
  expect(resolveFeeJurisdiction("Germany")).toEqual(["DE", "DPMA"]);
  const client = new FeesClient({
    retryLimit: 0,
    fetch: recordedFeeFetch(),
  });
  expect((await client.getSchedule("DE")).key).toBe("DE/DPMA/patent");
  const broken = new DpmaFeesClient({
    retryLimit: 0,
    fetch: (async () =>
      new Response("not a pdf", {
        headers: { "content-type": "application/pdf" },
      })) as unknown as typeof fetch,
  });
  await expect(broken.getPatentSchedule()).rejects.toThrow();
});

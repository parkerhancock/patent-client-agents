import { expect, test } from "bun:test";
import {
  type FeeSchedule,
  FeesClient,
  filterFees,
  PrvFeesClient,
  parsePrvAmount,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeResponse } from "./fees-recordings.js";

/** PRV's three fee pages, recorded October 22, 2026. */
const recording = feeRecordings("prv");
const schedule = async (right: "patent" | "trademark" | "design") => {
  const found = (await recording).find((item) => item.right === right);
  if (!found) throw new Error(`No PRV ${right} schedule.`);
  return found;
};
const fee = (s: FeeSchedule, code: string) => {
  const found = s.fees.find((item) => item.code === code);
  if (!found) throw new Error(`No ${code} in ${s.key}.`);
  return found;
};

test("real PRV pages: three schedules, no effective date, page edit dates kept apart", async () => {
  const schedules = await recording;
  expect(schedules.map((s) => [s.key, s.fees.length])).toEqual([
    ["SE/PRV/patent", 98],
    ["SE/PRV/trademark", 42],
    ["SE/PRV/design", 18],
  ]);
  const edited = ["2026-01-01", "2025-04-25", "2023-03-18"];
  schedules.forEach((s, i) => {
    expect(s.effective_date).toBeNull();
    expect(s.provenance.as_of_status).toBe(
      `effective date not published; page last edited ${edited[i]}`,
    );
    expect(s.unmapped_codes).toEqual([]);
    expect(s.recurring_fee_coverage.status).toBe("complete");
    expect(s.fees.every((item) => item.tier === "none")).toBe(true);
  });
});

test("PRV patent fees by ID, with the annuity ladder and its increased fees", async () => {
  const patent = await schedule("patent");
  expect(fee(patent, "se-pat-se-1")).toMatchObject({
    label: "SE-1: Filing fee",
    amount: "3000.00",
    category: "filing",
  });
  expect(fee(patent, "se-pat-se-1").notes).toContain("Search fee: 2500 SEK");
  expect(fee(patent, "se-pat-se-3")).toMatchObject({
    amount: "150.00",
    category: "excess_claims",
    condition: { trigger: "claims_over", threshold: 10, per_unit: true },
  });
  expect(fee(patent, "se-pat-se-8")).toMatchObject({
    amount: "3000.00",
    category: "grant",
  });
  for (let year = 1; year <= 20; year++) {
    const [renewal] = filterFees(patent.fees, { category: "renewal", year });
    expect(renewal?.code).toBe(`se-pat-n-${year}`);
  }
  expect(fee(patent, "se-pat-n-1").amount).toBe("0.00");
  expect(fee(patent, "se-pat-n-3").amount).toBe("1600.00");
  expect(fee(patent, "se-pat-n-3-increased")).toMatchObject({
    amount: "1920.00",
    category: "late_fee",
    year: 3,
  });
  expect(fee(patent, "se-pat-n-20").amount).toBe("8000.00");
  expect(fee(patent, "se-pat-n-20-increased").amount).toBe("9600.00");
  // The SPC annual fee is not the patent's year-2 annuity.
  expect(fee(patent, "se-pat-nt-2")).toMatchObject({
    amount: "20000.00",
    category: "other",
    year: null,
  });
  expect(fee(patent, "se-pat-pct-1").amount).toBe("15680.00");
  expect(fee(patent, "se-pat-pct-2")).toMatchObject({
    amount: "180.00",
    condition: { trigger: "sheets_over", threshold: 30 },
  });
  expect(fee(patent, "se-pat-pct-3").category).toBe("other");
  expect(fee(patent, "se-pat-pct-3").notes).toContain("reduction");
  expect(fee(patent, "se-pat-ep-1").category).toBe("translation");
  // Rows priced by quotation or formula are omitted, not listed at zero.
  const codes = patent.fees.map((item) => item.code);
  for (const code of ["se-pat-kt-6", "se-pat-pct-11", "se-pat-pct-5"])
    expect(codes).not.toContain(code);
  expect(patent.notes).toContain("KT-6");
});

test("PRV trademark fees: e-service and other-channel rates", async () => {
  const trademark = await schedule("trademark");
  const filing = filterFees(trademark.fees, { category: "filing" });
  expect(
    filing.map((item) => [item.amount, item.condition?.trigger ?? null]),
  ).toEqual([
    ["2700.00", null],
    ["3900.00", "paper_filing"],
    ["3000.00", null],
  ]);
  expect(
    filterFees(trademark.fees, { category: "renewal", year: 10 }).map(
      (item) => [item.code, item.amount],
    ),
  ).toEqual([
    [
      "se-tm-e-service-renewal-application-for-protection-in-one-class-i",
      "2700.00",
    ],
    ["se-tm-e-service-for-each-additional-class-2", "1000.00"],
    [
      "se-tm-paper-or-other-renewal-application-for-protection-in-one-class-i",
      "3900.00",
    ],
    ["se-tm-paper-or-other-for-each-additional-class-2", "1000.00"],
  ]);
  expect(
    filterFees(trademark.fees, { category: "late_fee", year: 10 }).map(
      (item) => item.amount,
    ),
  ).toEqual(["200.00", "200.00"]);
  expect(
    fee(trademark, "se-tm-e-service-for-each-additional-class").condition,
  ).toMatchObject({ trigger: "classes_over", threshold: 1 });
  expect(
    trademark.fees.filter((item) => item.category === "madrid").length,
  ).toBe(3);
});

test("PRV design fees: renewals per five-year period are year 5", async () => {
  const design = await schedule("design");
  expect(
    filterFees(design.fees, { category: "renewal", year: 5 }).map((item) => [
      item.amount,
      item.condition?.trigger ?? null,
    ]),
  ).toEqual([
    ["2500.00", null],
    ["3000.00", "paper_filing"],
  ]);
  expect(
    filterFees(design.fees, { category: "late_fee", year: 5 }).map(
      (item) => item.amount,
    ),
  ).toEqual(["500.00"]);
  expect(
    filterFees(design.fees, { category: "filing" }).map((item) => item.amount),
  ).toEqual(["2000.00", "2500.00", "2200.00", "1400.00"]);
});

test("SEK amounts parse with space separators and keep their units", () => {
  expect(parsePrvAmount("3 000 kr")).toEqual({
    kind: "amount",
    amount: "3000.00",
    unit: "",
  });
  expect(parsePrvAmount("15 680 SEK")).toMatchObject({
    amount: "15680.00",
  });
  expect(parsePrvAmount("180 kr per sheet")).toMatchObject({
    unit: "per sheet",
  });
  for (const none of ["By quotation", "As described", "50% addition", ""])
    expect(parsePrvAmount(none).kind).toBe("none");
});

test("PRV page drift fails instead of returning a partial schedule", async () => {
  const client = new PrvFeesClient({
    retryLimit: 0,
    fetch: (async () =>
      new Response("<main><h2>Fees</h2><p>Moved.</p></main>", {
        headers: { "content-type": "text/html" },
      })) as unknown as typeof fetch,
  });
  for (const call of [
    client.getPatentSchedule(),
    client.getTrademarkSchedule(),
    client.getDesignSchedule(),
  ])
    expect(await call.catch((error) => error.code)).toBe("INVALID_RESPONSE");
});

test("PRV routes resolve through the Python aliases", async () => {
  const client = new FeesClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) =>
      recordedFeeResponse(
        String(input instanceof Request ? input.url : input),
      ) ?? new Response("missing", { status: 404 })) as typeof fetch,
  });
  expect((await client.getSchedule("Sweden", "design")).key).toBe(
    "SE/PRV/design",
  );
  expect(
    (await client.getSchedule("Swedish Intellectual Property Office")).key,
  ).toBe("SE/PRV/patent");
  expect((await client.getSchedule("se", "trademark")).key).toBe(
    "SE/PRV/trademark",
  );
});

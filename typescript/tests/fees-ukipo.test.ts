import { expect, test } from "bun:test";
import {
  type FeeSchedule,
  FeesClient,
  filterFees,
  parseUkipoAmount,
  UkipoFeesClient,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeFetch } from "./fees-recordings.js";

/** The UK IPO guidance page and its patents and trade marks CSVs, recorded October 22, 2026. */
const recording = feeRecordings("ukipo");
const schedule = async (right: "patent" | "trademark") => {
  const found = (await recording).find((item) => item.right === right);
  if (!found) throw new Error(`No UKIPO ${right} schedule.`);
  return found;
};
const fee = (s: FeeSchedule, code: string) => {
  const found = s.fees.find((item) => item.code === code);
  if (!found) throw new Error(`No ${code} in ${s.key}.`);
  return found;
};

/** UKIPO's 2026 renewal ladder as transcribed in the Python package (ukipo._PATENT_RENEWAL_FEES). */
const PYTHON_LADDER: Record<number, string> = {
  5: "90.00",
  6: "120.00",
  7: "150.00",
  8: "170.00",
  9: "200.00",
  10: "230.00",
  11: "250.00",
  12: "290.00",
  13: "340.00",
  14: "400.00",
  15: "480.00",
  16: "560.00",
  17: "620.00",
  18: "690.00",
  19: "760.00",
  20: "810.00",
};

test("real UK IPO CSVs: both schedules, effective 1 April 2026", async () => {
  const schedules = await recording;
  expect(schedules.map((s) => [s.key, s.fees.length])).toEqual([
    ["GB/UKIPO/patent", 67],
    ["GB/UKIPO/trademark", 43],
  ]);
  for (const s of schedules) {
    expect(s.effective_date).toBe("2026-04-01");
    expect(s.unmapped_codes).toEqual([]);
    expect(s.recurring_fee_coverage.status).toBe("complete");
    expect(s.provenance.source_url).toStartWith(
      "https://assets.publishing.service.gov.uk/media/",
    );
    expect(new Set(s.fees.map((item) => item.code)).size).toBe(s.fees.length);
  }
});

test("UK patent renewal ladder from the CSV equals the Python transcription", async () => {
  const patent = await schedule("patent");
  const ladder = Object.fromEntries(
    patent.fees
      .filter((item) => item.category === "maintenance")
      .map((item) => [item.year, item.amount]),
  );
  expect(ladder).toEqual(PYTHON_LADDER);
  expect(fee(patent, "uk-patent-renewal-y5").code).toBe("uk-patent-renewal-y5");
  expect(fee(patent, "uk-patent-late-renewal-m6")).toMatchObject({
    amount: "160.00",
    category: "late_fee",
    condition: { trigger: "late_days" },
  });
  expect(patent.notes).toContain("Renewal License of Rights");
});

test("UK patent fees: search, examination, excess claims and SPC fees", async () => {
  const patent = await schedule("patent");
  const amount = (label: RegExp) =>
    patent.fees.find((item) => label.test(item.label))?.amount;
  expect(amount(/^Request a search \(UK application\)$/)).toBe("240.00");
  expect(amount(/^Request a search \(UK application online\)$/)).toBe("200.00");
  expect(amount(/substantive examination - online$/)).toBe("130.00");
  expect(amount(/^Application fee \(if paid on filing online\)$/)).toBe(
    "75.00",
  );
  expect(fee(patent, "uk-patent-form-17")).toMatchObject({
    amount: "250.00",
    category: "petition",
  });
  const claims = filterFees(patent.fees, { category: "excess_claims" });
  expect(
    claims.map((item) => [item.amount, item.condition?.threshold]),
  ).toEqual([
    ["27.00", 25],
    ["27.00", 25],
  ]);
  expect(fee(patent, "uk-patent-spc-y3")).toMatchObject({
    amount: "1070.00",
    category: "other",
    year: 3,
  });
  expect(fee(patent, "uk-patent-spc-late-y5").amount).toBe("665.00");
  // SPC annual fees are not patent renewals.
  expect(filterFees(patent.fees, { category: "maintenance", year: 5 })).toEqual(
    [expect.objectContaining({ code: "uk-patent-renewal-y5" })],
  );
});

test("UK trade mark fees: one class included, class fees per additional class", async () => {
  const trademark = await schedule("trademark");
  expect(
    filterFees(trademark.fees, { category: "filing" }).map((item) => [
      item.label,
      item.amount,
    ]),
  ).toEqual([
    ["Apply for a trade mark (paper application)", "250.00"],
    ["Apply for a trade mark (online application)", "205.00"],
    ["Right Start Application - Stage 1", "125.00"],
    ["Right Start Application - Stage 2", "125.00"],
  ]);
  expect(
    fee(
      trademark,
      "uk-tm-form-e-tm3-apply-for-a-trade-mark-online-application-class-fee",
    ).condition,
  ).toMatchObject({ trigger: "classes_over", threshold: 1, per_unit: true });
  expect(
    filterFees(trademark.fees, { category: "renewal", year: 10 }).map(
      (item) => item.amount,
    ),
  ).toEqual(["245.00", "245.00", "60.00", "60.00"]);
  expect(fee(trademark, "uk-tm-form-tm13").category).toBe("late_fee");
  expect(
    fee(trademark, "uk-tm-form-e-tm3-request-for-expedited-examination"),
  ).toMatchObject({ amount: "370.00", category: "examination" });
  expect(fee(trademark, "uk-tm-form-mm2")).toMatchObject({
    amount: "50.00",
    category: "madrid",
  });
});

test("UK IPO amounts: pound sign optional, Windows-1252 CSVs decoded", async () => {
  expect(parseUkipoAmount("£1,070.00")).toBe("1070.00");
  expect(parseUkipoAmount("�250.00")).toBe("250.00");
  expect(parseUkipoAmount("50% of renewal fee")).toBeNull();
  expect(parseUkipoAmount("£250")).toBeNull();
  const guidance = `<p>The new fees will take effect on 1 April 2026.</p><a href="https://www.gov.uk/csv-preview/abc123/tm.csv">Trade marks fees table</a>`;
  const csv = new Uint8Array([
    ...new TextEncoder().encode(
      "Trade Marks - Domestic,Form,Current Fee,New Fee\r\nRenew trade mark registration (online),TM11,",
    ),
    0xa3,
    ...new TextEncoder().encode("200.00,"),
    0xa3,
    ...new TextEncoder().encode("245.00\r\n"),
  ]);
  const client = new UkipoFeesClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) =>
      String(input instanceof Request ? input.url : input).endsWith(".csv")
        ? new Response(csv)
        : new Response(guidance)) as unknown as typeof fetch,
  });
  const schedule = await client.getTrademarkSchedule();
  expect(schedule.fees.map((item) => [item.amount, item.year])).toEqual([
    ["245.00", 10],
  ]);
});

test("UK IPO guidance drift fails clearly", async () => {
  const client = new UkipoFeesClient({
    retryLimit: 0,
    fetch: (async () =>
      new Response(
        "<p>The new fees will take effect on 1 April 2026.</p>",
      )) as unknown as typeof fetch,
  });
  expect(await client.getPatentSchedule().catch((error) => error.code)).toBe(
    "INVALID_RESPONSE",
  );
});

test("UKIPO routes resolve through the Python aliases; no design route", async () => {
  const client = new FeesClient({
    retryLimit: 0,
    fetch: recordedFeeFetch(),
  });
  expect((await client.getSchedule("Britain", "trademark")).key).toBe(
    "GB/UKIPO/trademark",
  );
  const { fees } = await client.lookupFees("UK", {
    category: "maintenance",
    year: 20,
  });
  expect(fees.map((item) => item.amount)).toEqual(["810.00"]);
  expect(await client.getSchedule("UK", "design").catch((e) => e.code)).toBe(
    "UNSUPPORTED_RIGHT",
  );
});

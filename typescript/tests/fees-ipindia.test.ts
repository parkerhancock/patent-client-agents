import { expect, test } from "bun:test";
import {
  type FeeSchedule,
  FeesClient,
  filterFees,
  IPINDIA_FEES_PDF_URL,
  IpIndiaFeesClient,
  parseRateCell,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecording, recordedFeeResponse } from "./fees-recordings.js";

const byCode = (schedule: FeeSchedule, code: string) =>
  schedule.fees.find((fee) => fee.code === code);
/** [small e-filing, large e-filing, small physical, large physical], the PDF's column order. */
const rates = (schedule: FeeSchedule, base: string) =>
  ["small-efile", "large-efile", "small-paper", "large-paper"].map(
    (suffix) => byCode(schedule, `${base}-${suffix}`)?.amount,
  );

test("real First Schedule PDF: counts, provenance and column order", async () => {
  const schedule = await feeRecording("ipindia");
  expect(schedule.key).toBe("IN/IPIN/patent");
  expect(schedule.fees).toHaveLength(330);
  expect(schedule.unmapped_codes).toEqual([]);
  expect(schedule.effective_date).toBeNull();
  expect(schedule.provenance).toMatchObject({
    effective_date: null,
    as_of_status: "effective date not published by the office",
    source_url: IPINDIA_FEES_PDF_URL,
  });
  // Amounts as printed in the PDF. Python read the middle two columns
  // swapped, filing 8000 as the small-entity paper rate.
  expect(rates(schedule, "in-1")).toEqual(["1600", "8000", "1750", "8800"]);
  expect(byCode(schedule, "in-1-small-paper")).toMatchObject({
    tier: "small",
    category: "filing",
    condition: { trigger: "paper_filing" },
  });
  expect(byCode(schedule, "in-1-large-efile")?.tier).toBe("large");
  expect(rates(schedule, "in-28-i")).toEqual([
    "4000",
    "20000",
    "4400",
    "22000",
  ]);
  expect(byCode(schedule, "in-28-i-small-efile")?.category).toBe("examination");
  expect(rates(schedule, "in-4-i")).toEqual(["480", "2400", "530", "2600"]);
  expect(rates(schedule, "in-21")).toEqual(["2400", "12000", "2650", "13200"]);
  expect(byCode(schedule, "in-21-small-efile")?.category).toBe("petition");
  expect(rates(schedule, "in-31")).toEqual(["2400", "12000", "2650", "13200"]);
  expect(byCode(schedule, "in-31-small-efile")?.category).toBe("cancellation");
});

test("real First Schedule PDF: renewal fees for years 3-20 by tier and filing mode", async () => {
  const schedule = await feeRecording("ipindia");
  const ladder: Record<number, string[]> = {
    3: ["800", "4000", "880", "4400"],
    6: ["800", "4000", "880", "4400"],
    7: ["2400", "12000", "2650", "13200"],
    10: ["2400", "12000", "2650", "13200"],
    11: ["4800", "24000", "5300", "26400"],
    15: ["4800", "24000", "5300", "26400"],
    16: ["8000", "40000", "8800", "44000"],
    20: ["8000", "40000", "8800", "44000"],
  };
  for (const [year, amounts] of Object.entries(ladder))
    expect(rates(schedule, `in-18-y${year}`)).toEqual(amounts);
  expect(
    filterFees(schedule.fees, {
      category: "renewal",
      year: 7,
      tier: "small",
    }).map((fee) => [fee.code, fee.amount]),
  ).toEqual([
    ["in-18-y7-small-efile", "2400"],
    ["in-18-y7-small-paper", "2650"],
  ]);
  expect(byCode(schedule, "in-18-y3-small-efile")?.notes).toContain(
    "entry 18(i).",
  );
  expect(schedule.fees.some((fee) => fee.category === "maintenance")).toBe(
    false,
  );
  expect(schedule.recurring_fee_coverage.status).toBe("complete");
});

test("real First Schedule PDF: sub-item surcharges, absences and omitted entries", async () => {
  const schedule = await feeRecording("ipindia");
  expect(byCode(schedule, "in-1-ii-small-efile")).toMatchObject({
    category: "excess_claims",
    amount: "320",
    condition: { trigger: "claims_over", threshold: 10, per_unit: true },
  });
  expect(byCode(schedule, "in-1-i-large-efile")).toMatchObject({
    category: "excess_pages",
    amount: "800",
    condition: { trigger: "pages_over", threshold: 30 },
  });
  expect(byCode(schedule, "in-1-iii-small-efile")?.notes).toContain(
    "subject to a maximum of 24000",
  );
  // Sequence-listing pages and oppositions cannot be filed on paper.
  expect(byCode(schedule, "in-1-iii-small-paper")).toBeUndefined();
  expect(rates(schedule, "in-9-i")).toEqual([
    "8000",
    "40000",
    undefined,
    undefined,
  ]);
  expect(byCode(schedule, "in-9-i-small-efile")?.notes).toContain(
    "Physical filing for natural persons, startups, small entities and educational institutions: not allowed.",
  );
  // "No fee" entries are zero-amount fees, not gaps.
  expect(byCode(schedule, "in-2-small-efile")).toMatchObject({
    amount: "0",
    notes: expect.stringContaining("No fee."),
  });
  expect(rates(schedule, "in-11-2")).toEqual(["800", "4000", "880", "4400"]);
  expect(rates(schedule, "in-12")).toEqual([
    "900",
    undefined,
    "1000",
    undefined,
  ]);
  // Patent-agent register fees (34-38) and the "as applicable" entry 58 are omitted.
  for (const entry of [34, 35, 36, 37, 38, 58])
    expect(
      schedule.fees.some((fee) => fee.code.startsWith(`in-${entry}-`)),
    ).toBe(false);
  expect(schedule.notes).toContain("entry 58");
});

test("rate cells parse exactly or fail", () => {
  expect(parseRateCell("(ii) 1600")).toEqual({
    kind: "fee",
    amount: "1600",
    extra: "",
  });
  expect(parseRateCell("8,000 (In respect of each patent)")).toEqual({
    kind: "fee",
    amount: "8000",
    extra: "(In respect of each patent)",
  });
  expect(parseRateCell("No fee")).toEqual({ kind: "no_fee" });
  expect(parseRateCell("Not allowed")).toEqual({ kind: "not_allowed" });
  expect(parseRateCell("Not applicable")).toEqual({ kind: "not_applicable" });
  for (const bad of ["Rs. 1600", "", "free"])
    expect(() => parseRateCell(bad)).toThrow();
});

test("a non-PDF response fails; the recorded PDF parses from a fake fetch", async () => {
  const pdf = new Uint8Array(
    await recordedFeeResponse("ipindia", IPINDIA_FEES_PDF_URL).arrayBuffer(),
  );
  const client = (body: Uint8Array) =>
    new IpIndiaFeesClient({
      retryLimit: 0,
      fetch: (async () =>
        new Response(body as Uint8Array<ArrayBuffer>, {
          headers: { "content-type": "application/pdf" },
        })) as unknown as typeof fetch,
    });
  expect(
    await client(new TextEncoder().encode("<html>maintenance</html>"))
      .getPatentSchedule()
      .catch((error) => error.code),
  ).toBe("INVALID_RESPONSE");
  expect((await client(pdf).getPatentSchedule()).fees).toHaveLength(330);
});

test("India aliases resolve and route through FeesClient", async () => {
  for (const name of [
    "IPIN",
    "IN",
    "india",
    "IPO India",
    "CGPDTM",
    "Indian Patent Office",
  ])
    expect(resolveFeeJurisdiction(name)).toEqual(["IN", "IPIN"]);
  const fees = new FeesClient({
    retryLimit: 0,
    fetch: (async () =>
      recordedFeeResponse(
        "ipindia",
        IPINDIA_FEES_PDF_URL,
      )) as unknown as typeof fetch,
  });
  expect((await fees.getSchedule("India")).key).toBe("IN/IPIN/patent");
  expect(
    await fees.getSchedule("India", "trademark").catch((error) => error.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

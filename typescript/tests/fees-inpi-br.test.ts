import { expect, test } from "bun:test";
import {
  type FeeItem,
  FeesClient,
  filterFees,
  INPI_BR_PATENT_PDF_URL,
  parseBrlAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeFetch } from "./fees-recordings.js";

const recorded = feeRecordings("inpi-br");
const pick = (fees: FeeItem[], code: string) =>
  fees.find((fee) => fee.code === code);

test("real INPI Brazil patent table: codes, tiers, bands and claim surcharges", async () => {
  const [patent] = await recorded;
  const fees = patent?.fees ?? [];
  expect(patent?.key).toBe("BR/INPI-BR/patent");
  expect(patent?.provenance.source_url).toBe(INPI_BR_PATENT_PDF_URL);
  expect(fees.length).toBe(346);
  expect(patent?.unmapped_codes).toEqual([]);
  expect(patent?.effective_date).toBeNull();
  expect(patent?.notes).toContain('"Variable" are omitted (287, 293, 800)');
  expect(new Set(fees.map((fee) => fee.code)).size).toBe(fees.length);
  // Spot checks against the April 2021 English patent table.
  const pair = (code: string) => [
    pick(fees, `inpi-br-${code}-l`)?.amount,
    pick(fees, `inpi-br-${code}-s`)?.amount,
  ];
  expect(pair("200")).toEqual(["175.00", "70.00"]);
  expect([
    pick(fees, "inpi-br-200-l-paper")?.amount,
    pick(fees, "inpi-br-200-s-paper")?.condition?.trigger,
  ]).toEqual(["260.00", "paper_filing"]);
  expect(pick(fees, "inpi-br-203-l")).toMatchObject({
    amount: "590.00",
    category: "examination",
  });
  expect(
    fees
      .filter(
        (fee) =>
          fee.code.startsWith("inpi-br-203-") &&
          fee.category === "excess_claims",
      )
      .map((fee) => [fee.tier, fee.amount, fee.condition?.threshold]),
  ).toEqual([
    ["large", "100.00", 10],
    ["small", "40.00", 10],
    ["large", "200.00", 15],
    ["small", "80.00", 15],
    ["large", "500.00", 30],
    ["small", "200.00", 30],
  ]);
  expect(pair("212")).toEqual(["235.00", "94.00"]);
  expect(pick(fees, "inpi-br-213-l")?.category).toBe("late_fee");
  expect(pick(fees, "inpi-br-256-n")).toMatchObject({
    amount: "90.00",
    tier: "none",
    category: "extension",
  });
  expect(pick(fees, "inpi-br-263-n")).toMatchObject({
    amount: "0.00",
    notes: expect.stringContaining("No charge."),
  });
  expect(pick(fees, "inpi-br-271-n-paper")?.amount).toBe("135.00");
  // Annual fees: invention bands 3-6, 7-10, 11-15, 16-20.
  const annual = (year: number, tier: "large" | "small") =>
    filterFees(fees, { category: "renewal", year, tier }).map((fee) => [
      fee.code,
      fee.amount,
    ]);
  expect(annual(5, "large")).toEqual([
    ["inpi-br-222-l-y5", "780.00"],
    ["inpi-br-232-l-y5", "235.00"],
    ["inpi-br-242-l-y5", "405.00"],
  ]);
  expect(annual(20, "small")).toEqual([
    ["inpi-br-228-s-y20", "802.00"],
    ["inpi-br-238-s-y20", "242.00"],
  ]);
  expect(annual(15, "large").map(([code]) => code)).toEqual([
    "inpi-br-226-l-y15",
    "inpi-br-236-l-y15",
    "inpi-br-246-l-y15",
  ]);
  expect(annual(2, "large")).toEqual([]);
  expect(
    filterFees(fees, { category: "late_fee", year: 5 }).map(
      (fee) => fee.amount,
    ),
  ).toEqual(["1565.00", "475.00", "805.00"]);
  expect(patent?.recurring_fee_coverage.status).toBe("complete");
});

test("real INPI Brazil trademark table: per-class fees, renewals and repeats", async () => {
  const [, trademark] = await recorded;
  const fees = trademark?.fees ?? [];
  expect(trademark?.key).toBe("BR/INPI-BR/trademark");
  expect(fees.length).toBe(76);
  expect(trademark?.unmapped_codes).toEqual([]);
  expect(pick(fees, "inpi-br-tm-389-l")).toMatchObject({
    amount: "355.00",
    category: "filing",
    condition: { trigger: "classes_over", threshold: 0, per_unit: true },
  });
  expect(pick(fees, "inpi-br-tm-389-s")?.amount).toBe("142.00");
  expect(
    filterFees(fees, { category: "renewal", year: 10, tier: "small" }).map(
      (fee) => [fee.code, fee.amount],
    ),
  ).toEqual([["inpi-br-tm-374-s", "426.00"]]);
  expect(pick(fees, "inpi-br-tm-375-l")).toMatchObject({
    category: "late_fee",
    year: 10,
    amount: "1610.00",
  });
  expect(pick(fees, "inpi-br-tm-3003-n-additional-class")).toMatchObject({
    amount: "475.00",
    category: "excess_classes",
  });
  expect(pick(fees, "inpi-br-tm-349-n-additional-process-as")?.amount).toBe(
    "85.00",
  );
  expect(pick(fees, "inpi-br-tm-393-n")?.amount).toBe("37575.00");
  expect(pick(fees, "inpi-br-tm-3010-n")?.amount).toBe("0.00");
  expect(pick(fees, "inpi-br-tm-3013-n")).toMatchObject({
    category: "madrid",
    amount: "1065.00",
  });
  // Codes repeated in several sections of the table appear once.
  expect(
    fees.filter((fee) => fee.code.startsWith("inpi-br-tm-382-")).length,
  ).toBe(1);
  expect(pick(fees, "inpi-br-tm-358-n")?.label).toBe(
    "INPI BR code 358: Classification enquiries to the Figurative Elements Classification Committee",
  );
  expect(pick(fees, "inpi-br-tm-3007-n")?.label).toContain(
    "Validation and transmittal of the request for transfer of International Application",
  );
});

test("INPI Brazil amounts parse exactly or fail", () => {
  expect(parseBrlAmount("1.595,00")).toBe("1595.00");
  expect(parseBrlAmount("2,80")).toBe("2.80");
  expect(parseBrlAmount("37.575,00")).toBe("37575.00");
  for (const bad of ["1,595.00", "175", "", "No charge"])
    expect(() => parseBrlAmount(bad)).toThrow();
});

test("INPI Brazil routes resolve through FeesClient", async () => {
  for (const name of ["INPI-BR", "Brazil", "BR", "INPI Brasil"])
    expect(resolveFeeJurisdiction(name, "trademark")).toEqual([
      "BR",
      "INPI-BR",
    ]);
  const client = new FeesClient({
    retryLimit: 0,
    fetch: recordedFeeFetch(),
  });
  expect(client.supportedRoutes).toEqual(
    expect.arrayContaining(["INPI-BR/patent", "INPI-BR/trademark"]),
  );
  const { fees } = await client.lookupFees("Brazil", {
    category: "filing",
    tier: "small",
  });
  expect(fees.map((fee) => [fee.code, fee.amount])).toEqual([
    ["inpi-br-200-s", "70.00"],
    ["inpi-br-200-s-paper", "104.00"],
    ["inpi-br-201-s", "70.00"],
    ["inpi-br-201-s-paper", "104.00"],
  ]);
  expect(
    await client.getSchedule("BR", "design").catch((error) => error.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

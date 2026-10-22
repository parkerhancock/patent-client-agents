import { expect, test } from "bun:test";
import {
  type FeeSchedule,
  FeesClient,
  filterFees,
  KIPO_PATENT_FEES_URL,
  KIPO_TRADEMARK_DESIGN_FEES_URL,
  KipoFeesClient,
  parseKrwAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeResponse } from "./fees-recordings.js";

const byCode = (schedule: FeeSchedule, code: string) =>
  schedule.fees.find((fee) => fee.code === code);

test("real KIPO patent page: counts, effective date and spot-checked fees", async () => {
  const [patent] = await feeRecordings("kipo");
  if (!patent) throw new Error("missing schedule");
  expect(patent.key).toBe("KR/KIPO/patent");
  expect(patent.fees).toHaveLength(66);
  expect(patent.unmapped_codes).toEqual([]);
  expect(patent.effective_date).toBe("2023-08-01");
  expect(patent.provenance.as_of_status).toBe(
    "in effect since 2023-08-01; page last updated 2026-02-10",
  );
  expect(patent.fees.every((fee) => fee.tier === "none")).toBe(true);
  // Amounts as published on the KIPO page (Description | Fee(KRW)).
  for (const [code, amount] of [
    ["kr-patent-application-electronic", "46000"],
    ["kr-patent-application-paper", "66000"],
    ["kr-patent-term-extension", "300000"],
    ["kr-substantive-examination", "166000"],
    ["kr-substantive-examination-per-claim", "51000"],
    ["kr-reexamination", "100000"],
    ["kr-reexamination-per-claim", "10000"],
    ["kr-preferential-examination", "200000"],
    ["kr-priority-claim-paper", "20000"],
  ])
    expect(byCode(patent, code as string)?.amount).toBe(amount);
  expect(byCode(patent, "kr-patent-application-paper-page-fee")).toMatchObject({
    category: "excess_pages",
    amount: "1000",
    condition: { trigger: "pages_over", threshold: 20, per_unit: true },
  });
  expect(byCode(patent, "kr-substantive-examination")?.category).toBe(
    "examination",
  );
  expect(
    byCode(patent, "kr-substantive-examination-per-claim")?.condition,
  ).toMatchObject({
    trigger: "claims_over",
    threshold: 0,
  });
});

test("real KIPO patent page: annual fees are renewals by year with a per-claim part", async () => {
  const [patent] = await feeRecordings("kipo");
  if (!patent) throw new Error("missing schedule");
  const ladder: Record<number, [string, string]> = {
    1: ["13000", "12000"],
    3: ["13000", "12000"],
    4: ["36000", "20000"],
    7: ["90000", "34000"],
    10: ["216000", "49000"],
    13: ["324000", "49000"],
    16: ["324000", "49000"],
    25: ["324000", "49000"],
  };
  for (const [year, [basic, claim]] of Object.entries(ladder)) {
    expect(
      filterFees(patent.fees, { category: "renewal", year: Number(year) }).map(
        (fee) => fee.amount,
      ),
    ).toEqual([basic]);
    expect(
      filterFees(patent.fees, {
        category: "excess_claims",
        year: Number(year),
      }).map((fee) => fee.amount),
    ).toEqual([claim]);
  }
  expect(patent.fees.some((fee) => fee.category === "maintenance")).toBe(false);
  expect(patent.recurring_fee_coverage.status).toBe("complete");
});

test("real KIPO trademark page: per-class fees, installments and renewal year 10", async () => {
  const [, trademark] = await feeRecordings("kipo");
  if (!trademark) throw new Error("missing schedule");
  expect(trademark.key).toBe("KR/KIPO/trademark");
  expect(trademark.fees).toHaveLength(24);
  expect(trademark.unmapped_codes).toEqual([]);
  expect(trademark.source_url).toBe(KIPO_TRADEMARK_DESIGN_FEES_URL);
  expect(byCode(trademark, "kr-tm-application-electronic")).toMatchObject({
    amount: "52000",
    condition: { trigger: "classes_over", threshold: 0 },
  });
  expect(byCode(trademark, "kr-tm-application-paper")).toMatchObject({
    amount: "62000",
    condition: { trigger: "paper_filing" },
  });
  expect(byCode(trademark, "kr-tm-registration")?.amount).toBe("201000");
  expect(byCode(trademark, "kr-tm-registration-installment")?.amount).toBe(
    "122000",
  );
  expect(
    filterFees(trademark.fees, { category: "renewal", year: 10 }).map((fee) => [
      fee.code,
      fee.amount,
    ]),
  ).toEqual([
    ["kr-tm-renewal", "300000"],
    ["kr-tm-renewal-installment", "184000"],
  ]);
  expect(byCode(trademark, "kr-tm-late-renewal")).toMatchObject({
    category: "late_fee",
    year: 10,
    amount: "330000",
  });
  // Goods beyond 10 in a class: no condition, since no trigger counts goods.
  const goods = byCode(trademark, "kr-tm-renewal-excess-goods");
  expect(goods).toMatchObject({
    category: "excess_classes",
    amount: "2000",
    year: 10,
    condition: null,
  });
  expect(byCode(trademark, "kr-tm-opposition")?.amount).toBe("50000");
  expect(trademark.recurring_fee_coverage.status).toBe("complete");
});

test("real KIPO design page: application tracks, annual-fee tracks and divisions", async () => {
  const [, , design] = await feeRecordings("kipo");
  if (!design) throw new Error("missing schedule");
  expect(design.key).toBe("KR/KIPO/design");
  expect(design.fees).toHaveLength(60);
  expect(design.unmapped_codes).toEqual([]);
  for (const [code, amount] of [
    ["kr-des-application-substantive-electronic", "94000"],
    ["kr-des-application-substantive-paper", "104000"],
    ["kr-des-application-partial-substantive-electronic", "45000"],
    ["kr-des-application-partial-substantive-paper", "55000"],
    ["kr-des-reexamination-paper", "40000"],
    ["kr-des-opposition", "50000"],
    // Python dropped the second division rate on this row.
    ["kr-des-division-to-substantive-electronic", "59000"],
    ["kr-des-division-to-substantive-paper", "69000"],
  ])
    expect(byCode(design, code as string)?.amount).toBe(amount);
  const track = (prefix: string) =>
    Object.fromEntries(
      design.fees
        .filter((fee) => fee.code.startsWith(prefix))
        .map((fee) => [fee.year, fee.amount]),
    );
  const substantive = track("kr-des-annuity-substantive-y");
  expect(Object.keys(substantive)).toHaveLength(20);
  expect([1, 4, 7, 10, 13, 20].map((year) => substantive[year])).toEqual([
    "25000",
    "35000",
    "70000",
    "140000",
    "210000",
    "210000",
  ]);
  const partial = track("kr-des-annuity-partial-substantive-y");
  expect(Object.keys(partial)).toHaveLength(20);
  expect([1, 3, 4, 20].map((year) => partial[year])).toEqual([
    "25000",
    "25000",
    "34000",
    "34000",
  ]);
  expect(
    filterFees(design.fees, { category: "renewal", year: 1 }),
  ).toHaveLength(2);
  expect(design.recurring_fee_coverage.status).toBe("complete");
});

const kipoFetch = (patentPage: string, tmPage: string) => {
  let calls = 0;
  const fetch = (async (input: RequestInfo | URL) => {
    calls++;
    const url = String(input instanceof Request ? input.url : input);
    return new Response(url.includes("92004") ? patentPage : tmPage, {
      headers: { "content-type": "text/html" },
    });
  }) as unknown as typeof globalThis.fetch;
  return { fetch, calls: () => calls };
};
const pages = async () => ({
  patent: await recordedFeeResponse("kipo", KIPO_PATENT_FEES_URL).text(),
  tm: await recordedFeeResponse("kipo", KIPO_TRADEMARK_DESIGN_FEES_URL).text(),
});

test("KIPO page drift fails or surfaces, and one fetch serves both schedules on a page", async () => {
  const { patent, tm } = await pages();
  const shared = kipoFetch(patent, tm);
  const client = new KipoFeesClient({ retryLimit: 0, fetch: shared.fetch });
  await Promise.all([
    client.getTrademarkSchedule(),
    client.getDesignSchedule(),
  ]);
  expect(shared.calls()).toBe(1);

  const renamed = await new KipoFeesClient({
    retryLimit: 0,
    fetch: kipoFetch(
      patent.replace(
        "Request for a preferential examination",
        "Request for a brand new service",
      ),
      tm,
    ).fetch,
  })
    .getPatentSchedule()
    .catch((error) => error.code);
  // A renamed known row is both unrecognized and missing: fail rather than guess.
  expect(renamed).toBe("INVALID_RESPONSE");

  for (const html of [
    patent.replace("The fees have been in effect since", "Fees apply from"),
    patent.replace("166,000", "166.000"),
    patent.replace(">51,000<", "><"),
    patent.replace(/<caption class="hidden">\s*Patent fees/, "<caption>Fees"),
  ])
    expect(
      await new KipoFeesClient({
        retryLimit: 0,
        fetch: kipoFetch(html, tm).fetch,
      })
        .getPatentSchedule()
        .catch((error) => error.code),
    ).toBe("INVALID_RESPONSE");
});

test("KIPO amounts parse exactly or fail", () => {
  expect(parseKrwAmount("1,200,000")).toBe("1200000");
  expect(parseKrwAmount("46,000")).toBe("46000");
  for (const bad of ["46.000", "46,00", "₩46,000", ""])
    expect(() => parseKrwAmount(bad)).toThrow();
});

test("KIPO aliases resolve and route through FeesClient", async () => {
  for (const name of [
    "KIPO",
    "KR",
    "korea",
    "South Korea",
    "Korean Intellectual Property Office",
  ])
    expect(resolveFeeJurisdiction(name, "design")).toEqual(["KR", "KIPO"]);
  const { patent, tm } = await pages();
  const fees = new FeesClient({
    retryLimit: 0,
    fetch: kipoFetch(patent, tm).fetch,
  });
  expect((await fees.getSchedule("South Korea", "trademark")).key).toBe(
    "KR/KIPO/trademark",
  );
  expect(
    await fees.getSchedule("KR", "utility_model").catch((error) => error.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

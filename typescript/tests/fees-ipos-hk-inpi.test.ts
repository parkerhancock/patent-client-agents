import { expect, test } from "bun:test";
import {
  type FeeItem,
  FeesClient,
  filterFees,
  HkIpdFeesClient,
  InpiFrFeesClient,
  IposFeesClient,
  iposRenewalYears,
  parseEurAmount,
  parseHkdAmount,
  parseSgdAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeFetch } from "./fees-recordings.js";

const byCode = (fees: FeeItem[], code: string) => {
  const fee = fees.find((item) => item.code === code);
  if (!fee) throw new Error(`missing ${code}`);
  return fee;
};
/** Renewal amounts by year for one entity tier (untiered rows included). */
const ladder = (fees: FeeItem[], tier: "large" | "small" = "large") =>
  Object.fromEntries(
    fees
      .filter(
        (fee) =>
          fee.category === "renewal" &&
          (fee.tier === "none" || fee.tier === tier),
      )
      .map((fee) => [fee.year, fee.amount]),
  );
const replay = recordedFeeFetch();
/** Serve recorded pages, optionally rewritten, from a fake fetch. */
const recordedFetch = (
  rewrite: (url: string, body: string) => string = (_, body) => body,
) =>
  (async (input: RequestInfo | URL) => {
    const url = String(input instanceof Request ? input.url : input);
    const response = await replay(url);
    if (url.includes("download-document")) return response;
    return new Response(rewrite(url, await response.text()));
  }) as unknown as typeof fetch;
const code = (promise: Promise<unknown>) =>
  promise.then(
    () => "ok",
    (error) => error.code,
  );

test("amount parsers are exact", () => {
  expect(parseSgdAmount("1,750")).toBe("1750.00");
  expect(parseSgdAmount("1800.00")).toBe("1800.00");
  expect(parseHkdAmount("$1,080")).toBe("1080.00");
  expect(parseHkdAmount("Nil")).toBe("0.00");
  expect(parseHkdAmount("$6 per page")).toBe("6.00");
  expect(parseHkdAmount("No fee")).toBeNull();
  expect(parseEurAmount("190")).toBe("190.00");
  expect(parseEurAmount("0.75")).toBe("0.75");
  expect(parseEurAmount("0,75")).toBe("0.75");
  expect(() => parseEurAmount("1.595,00")).toThrow();
  expect(
    iposRenewalYears(
      "For each year of renewal in respect of the 5th, 6th or 7th year of the patent",
    ),
  ).toEqual([5, 6, 7]);
  expect(
    iposRenewalYears("(f) For renewal of the 20th year of the patent"),
  ).toEqual([20]);
  expect(
    iposRenewalYears(
      "(g) For each year of renewal after the 20th year of the patent",
    ),
  ).toEqual([21]);
});

test("offices resolve by name and route through FeesClient", async () => {
  expect(resolveFeeJurisdiction("Singapore", "design")).toEqual(["SG", "IPOS"]);
  expect(resolveFeeJurisdiction("hong kong", "trademark")).toEqual([
    "HK",
    "HKIPD",
  ]);
  expect(resolveFeeJurisdiction("INPI France")).toEqual(["FR", "INPI-FR"]);
  const fees = new FeesClient({ retryLimit: 0, fetch: recordedFetch() });
  expect(fees.supportedRoutes).toEqual(
    expect.arrayContaining([
      "IPOS/patent",
      "IPOS/trademark",
      "IPOS/design",
      "HKIPD/patent",
      "HKIPD/trademark",
      "HKIPD/design",
      "INPI-FR/patent",
      "INPI-FR/trademark",
      "INPI-FR/design",
    ]),
  );
  expect((await fees.getSchedule("HK", "trademark")).key).toBe(
    "HK/HKIPD/trademark",
  );
  const { fees: annuity } = await fees.lookupFees("France", {
    category: "renewal",
    year: 5,
    tier: "small",
  });
  expect(annuity.map((fee) => [fee.code, fee.amount])).toEqual([
    ["inpi-fr-annuity-y05-s", "19.00"],
  ]);
  expect(await code(fees.getSchedule("SG", "utility_model"))).toBe(
    "UNSUPPORTED_RIGHT",
  );
});

test("real IPOS pages: patent schedule", async () => {
  const [patent] = await feeRecordings("ipos");
  if (!patent) throw new Error("missing schedule");
  expect(patent.key).toBe("SG/IPOS/patent");
  expect(patent.fees).toHaveLength(124);
  expect(patent.unmapped_codes).toEqual([]);
  expect(patent.effective_date).toBe("2026-04-01");
  expect(patent.provenance.as_of_status).toBe(
    "effective 2026-04-01 (second tranche of the 2025 fee reform); page last updated 2026-10-09",
  );
  const fees = patent.fees;
  expect(
    byCode(fees, "sg-pat-pf1-request-for-the-grant-of-a-patent"),
  ).toMatchObject({
    amount: "170.00",
    category: "filing",
    currency: "SGD",
    tier: "none",
  });
  expect(
    byCode(fees, "sg-pat-pf11-request-for-search-and-examination-repor"),
  ).toMatchObject({ amount: "1750.00", category: "search" });
  expect(byCode(fees, "sg-pat-pf11-excess-claims")).toMatchObject({
    amount: "80.00",
    category: "excess_claims",
    condition: { trigger: "claims_over", threshold: 15, per_unit: true },
  });
  expect(
    byCode(fees, "sg-pat-pf12-acceleration-sg-patents-fast-4").amount,
  ).toBe("1200.00");
  expect(
    byCode(fees, "sg-pat-pf11-acceleration-sg-patents-fast-8").amount,
  ).toBe("900.00");
  expect(
    byCode(fees, "sg-pat-pf12-request-for-examination-reportsave-on-of"),
  ).toMatchObject({
    amount: "1420.00",
    label: "PF12: Request for Examination Report",
  });
  // Per-claim surcharges are not also emitted as base search or grant fees (Python did).
  expect(
    fees.filter(
      (fee) =>
        ["search", "examination", "grant"].includes(fee.category) &&
        ["80.00", "40.00"].includes(fee.amount),
    ),
  ).toEqual([]);
  // PF15 bands, one fee per year; "after the 20th year" is year 21.
  expect(ladder(fees)).toEqual({
    5: "176.00",
    6: "176.00",
    7: "176.00",
    8: "460.00",
    9: "460.00",
    10: "460.00",
    11: "640.00",
    12: "640.00",
    13: "640.00",
    14: "830.00",
    15: "830.00",
    16: "830.00",
    17: "1010.00",
    18: "1010.00",
    19: "1010.00",
    20: "1200.00",
    21: "1470.00",
  });
  // Licence-of-right and restoration renewals do not compete with the standard fee.
  expect(
    filterFees(fees, { category: "renewal", year: 5 }).map((fee) => fee.code),
  ).toEqual(["sg-pat-pf15-y-5"]);
  expect(byCode(fees, "sg-pat-pf15-lor-y-5")).toMatchObject({
    amount: "88.00",
    category: "other",
    year: 5,
  });
  expect(byCode(fees, "sg-pat-pf20-y-20")).toMatchObject({
    amount: "1200.00",
    category: "late_fee",
  });
  expect(
    byCode(fees, "sg-pat-pf20-payment-of-additional-fee-and-renewal-fe"),
  ).toMatchObject({ amount: "300.00", category: "late_fee", year: null });
  expect(
    filterFees(fees, { category: "late_fee" }).map((fee) => fee.amount),
  ).toEqual(expect.arrayContaining(["50.00", "100.00", "300.00"]));
  expect(byCode(fees, "sg-pat-pf14-excess-claims")).toMatchObject({
    amount: "40.00",
    condition: { threshold: 20 },
  });
  expect(
    byCode(fees, "sg-pat-pf13a-response-to-written-opinion-or-a-respons"),
  ).toMatchObject({
    category: "excess_claims",
    condition: { trigger: "claims_over", threshold: null },
  });
  expect(
    byCode(fees, "sg-pat-pf58-b-to-an-amendment-of-a-specification-a").category,
  ).toBe("opposition");
  expect(patent.recurring_fee_coverage.status).toBe("complete");
});

test("real IPOS pages: trademark and design schedules", async () => {
  const [, trademark, design] = await feeRecordings("ipos");
  if (!trademark || !design) throw new Error("missing schedules");
  expect(trademark.fees).toHaveLength(35);
  expect(trademark.unmapped_codes).toEqual([]);
  const tm = trademark.fees;
  expect(byCode(tm, "sg-tm-tm4-preapproved")).toMatchObject({
    amount: "280.00",
    category: "filing",
    condition: { trigger: "classes_over", threshold: 0 },
  });
  expect(byCode(tm, "sg-tm-tm4-custom").amount).toBe("410.00");
  expect(byCode(tm, "sg-tm-tm4-acceleration-preapproved").amount).toBe(
    "200.00",
  );
  expect(byCode(tm, "sg-tm-tm4-acceleration-custom").amount).toBe("250.00");
  // Late renewal and restoration are late fees, not renewals.
  expect(
    filterFees(tm, { category: "renewal", year: 10 }).map((fee) => fee.amount),
  ).toEqual(["480.00"]);
  expect(
    filterFees(tm, { category: "late_fee", year: 10 }).map((fee) => fee.amount),
  ).toEqual(["700.00", "770.00"]);
  // TM27 lists 50 and "From 1 April 2026" 60; only the current amount stays.
  const tm27 = tm.filter((fee) => fee.code.startsWith("sg-tm-tm27-"));
  expect(tm27.map((fee) => [fee.code.slice(-2), fee.amount])).toEqual([
    ["v2", "60.00"],
    ["v4", "60.00"],
    ["v6", "60.00"],
  ]);
  expect(byCode(tm, "sg-tm-hc1-hearing-and-decision")).toMatchObject({
    amount: "1000.00",
    condition: null,
  });
  expect(byCode(tm, "sg-tm-hc1-hearing-and-decision-v2")).toMatchObject({
    amount: "800.00",
    condition: { trigger: "classes_over", threshold: 1 },
  });
  expect(
    byCode(tm, "sg-tm-mm2-e-application-for-international-registrati"),
  ).toMatchObject({ amount: "250.00", category: "madrid" });
  expect(
    byCode(tm, "sg-tm-cm5-request-for-extension-of-time-v3").label,
  ).toContain("Third and subsequent requests");
  expect(trademark.recurring_fee_coverage.status).toBe("complete");

  expect(design.fees).toHaveLength(26);
  const ds = design.fees;
  expect(
    byCode(ds, "sg-des-d3-application-for-registration-of-a-design"),
  ).toMatchObject({ amount: "200.00", category: "filing" });
  expect(
    byCode(ds, "sg-des-d3-application-for-registration-of-a-design-v2"),
  ).toMatchObject({ amount: "40.00", category: "deferment" });
  expect(ladder(ds)).toEqual({
    10: "220.00",
    15: "330.00",
    20: "440.00",
    25: "550.00",
  });
  expect(
    byCode(ds, "sg-des-d8-application-for-restoration-of-registrat").category,
  ).toBe("petition");
  expect(
    byCode(ds, "sg-des-d13-application-for-revocation-of-registrati").category,
  ).toBe("cancellation");
  expect(design.recurring_fee_coverage.status).toBe("complete");
});

test("IPOS drift: unknown forms surface, a lost table header fails", async () => {
  const client = (rewrite: (url: string, body: string) => string) =>
    new IposFeesClient({ retryLimit: 0, fetch: recordedFetch(rewrite) });
  const drifted = await client((_, body) =>
    body.replace(">PF54<", ">PF99<"),
  ).getPatentSchedule();
  expect(drifted.unmapped_codes).toEqual(["PF99"]);
  expect(
    await code(
      client((_, body) =>
        body.replaceAll(">Description<", ">Details<"),
      ).getDesignSchedule(),
    ),
  ).toBe("INVALID_RESPONSE");
});

test("real HK IPD pages: patent schedule", async () => {
  const [patent] = await feeRecordings("hk-ipd");
  if (!patent) throw new Error("missing schedule");
  expect(patent.key).toBe("HK/HKIPD/patent");
  expect(patent.fees).toHaveLength(75);
  expect(patent.unmapped_codes).toEqual([]);
  expect(patent.effective_date).toBeNull();
  expect(patent.provenance.as_of_status).toBe(
    "effective date not published by the office; page last revised 2026-08-03",
  );
  const fees = patent.fees;
  expect(
    byCode(fees, "hk-pat-ogp-request-for-grant-of-a-standard-patent-o"),
  ).toMatchObject({
    amount: "345.00",
    category: "filing",
    currency: "HKD",
    condition: null,
  });
  expect(
    byCode(fees, "hk-pat-ogp-request-for-grant-of-a-standard-patent-o-paper"),
  ).toMatchObject({
    amount: "480.00",
    condition: { trigger: "paper_filing" },
  });
  expect(
    byCode(fees, "hk-pat-rr-request-for-registration-of-a-designated").category,
  ).toBe("grant");
  expect(
    fees.filter((fee) => fee.code.startsWith("hk-pat-gen-advertisement-fee")),
  ).toHaveLength(1);
  expect(
    byCode(fees, "hk-pat-ogp-request-for-substantive-examination-of-a"),
  ).toMatchObject({ amount: "4000.00", category: "examination" });
  const standard = Object.fromEntries(
    fees
      .filter((fee) => fee.code.startsWith("hk-pat-gen-renewal-"))
      .map((fee) => [fee.year, fee.amount]),
  );
  expect(Object.keys(standard).map(Number)).toEqual(
    Array.from({ length: 17 }, (_, i) => i + 4),
  );
  expect([
    standard[4],
    standard[10],
    standard[11],
    standard[15],
    standard[16],
    standard[20],
  ]).toEqual(["450.00", "450.00", "620.00", "620.00", "850.00", "850.00"]);
  // A short-term patent renews once, for years 5-8 (Python stored years 4 and 8).
  expect(
    filterFees(fees, { category: "renewal", year: 5 }).map((fee) => [
      fee.code,
      fee.amount,
    ]),
  ).toEqual([
    ["hk-pat-gen-renewal-y5", "450.00"],
    ["hk-pat-stp-renewal-y5", "1080.00"],
  ]);
  expect(filterFees(fees, { category: "renewal", year: 8 })).toHaveLength(1);
  expect(
    byCode(fees, "hk-pat-gen-request-for-a-copy-of-document"),
  ).toMatchObject({
    amount: "6.00",
    condition: { trigger: "pages_over", threshold: 0, per_unit: true },
  });
  expect(
    byCode(fees, "hk-pat-gen-application-to-restore-a-lapsed-standard")
      .category,
  ).toBe("petition");
  expect(patent.recurring_fee_coverage.status).toBe("complete");
});

test("real HK IPD pages: trademark and design schedules", async () => {
  const [, trademark, design] = await feeRecordings("hk-ipd");
  if (!trademark || !design) throw new Error("missing schedules");
  expect(trademark.fees).toHaveLength(42);
  const tm = trademark.fees;
  expect(
    byCode(tm, "hk-tm-application-for-registration-of-a-trade-"),
  ).toMatchObject({ amount: "2000.00", category: "filing" });
  expect(
    byCode(tm, "hk-tm-application-for-registration-of-a-trade--addl-class"),
  ).toMatchObject({
    amount: "1000.00",
    category: "excess_classes",
    condition: { trigger: "classes_over", threshold: 1 },
  });
  // Rows sharing a rowspan fee cell keep it (Python dropped them).
  expect(
    byCode(tm, "hk-tm-application-for-revocation-declaration-o"),
  ).toMatchObject({ amount: "800.00", category: "cancellation" });
  expect(
    byCode(tm, "hk-tm-search-of-records-preliminary-advice-on--addl-class")
      .amount,
  ).toBe("200.00");
  expect(
    filterFees(tm, { category: "renewal", year: 10 }).map((fee) => fee.amount),
  ).toEqual(["2670.00"]);
  expect(byCode(tm, "hk-tm-late-renewal-charge")).toMatchObject({
    amount: "500.00",
    category: "late_fee",
    year: 10,
  });
  expect(
    byCode(tm, "hk-tm-request-for-restoration-and-renewal-of-a"),
  ).toMatchObject({ amount: "4000.00", category: "late_fee" });
  expect(
    byCode(
      tm,
      "hk-tm-request-to-divide-application-for-regist-addl-application",
    ).amount,
  ).toBe("2000.00");
  expect(
    byCode(tm, "hk-tm-request-to-divide-application-for-regist-addl-class")
      .amount,
  ).toBe("1000.00");
  expect(trademark.recurring_fee_coverage.status).toBe("complete");

  expect(design.fees).toHaveLength(37);
  const ds = design.fees;
  expect(byCode(ds, "hk-des-1-design-for-1-set-of-articles")).toMatchObject({
    amount: "470.00",
    category: "filing",
  });
  expect(byCode(ds, "hk-des-1-design-for-1-set-of-articles-paper").amount).toBe(
    "630.00",
  );
  expect(
    byCode(ds, "hk-des-2-or-more-designs-for-articles-not-formi-2"),
  ).toMatchObject({
    amount: "175.00",
    condition: { trigger: "multi_design", per_unit: true },
  });
  expect(ladder(ds)).toEqual({
    10: "475.00",
    15: "835.00",
    20: "1410.00",
    25: "2420.00",
  });
  expect(design.recurring_fee_coverage.status).toBe("complete");
});

test("HK IPD drift: unknown forms surface, a lost header fails", async () => {
  const client = (rewrite: (url: string, body: string) => string) =>
    new HkIpdFeesClient({ retryLimit: 0, fetch: recordedFetch(rewrite) });
  const drifted = await client((_, body) =>
    body.replace("Form D6<br", "Form D99<br"),
  ).getDesignSchedule();
  expect(drifted.unmapped_codes).toEqual(["D99"]);
  expect(
    await code(
      client((_, body) =>
        body.replaceAll("Descriptions", "Items"),
      ).getPatentSchedule(),
    ),
  ).toBe("INVALID_RESPONSE");
});

test("real INPI PDF: patent annuities, reduced rates and effective date", async () => {
  const [patent] = await feeRecordings("inpi-fr");
  if (!patent) throw new Error("missing schedule");
  expect(patent.key).toBe("FR/INPI-FR/patent");
  expect(patent.fees).toHaveLength(51);
  expect(patent.unmapped_codes).toEqual([]);
  expect(patent.effective_date).toBe("2026-07-02");
  expect(patent.provenance).toMatchObject({
    effective_date: "2026-07-02",
    source_url: "https://www.inpi.fr/inpi-block/download-document?id=20516",
  });
  const fees = patent.fees;
  expect(
    [
      "patent-filing",
      "patent-search",
      "patent-grant",
      "patent-claim-over-11",
    ].map((stem) => [
      byCode(fees, `inpi-fr-${stem}-l`).amount,
      byCode(fees, `inpi-fr-${stem}-s`).amount,
    ]),
  ).toEqual([
    ["26.00", "13.00"],
    ["520.00", "260.00"],
    ["90.00", "45.00"],
    ["42.00", "21.00"],
  ]);
  expect(
    byCode(fees, "inpi-fr-patent-claim-over-11-l").condition,
  ).toMatchObject({
    trigger: "claims_over",
    threshold: 10,
  });
  expect(ladder(fees)).toEqual({
    2: "38.00",
    3: "38.00",
    4: "38.00",
    5: "38.00",
    6: "76.00",
    7: "96.00",
    8: "136.00",
    9: "180.00",
    10: "220.00",
    11: "260.00",
    12: "300.00",
    13: "350.00",
    14: "400.00",
    15: "460.00",
    16: "520.00",
    17: "580.00",
    18: "650.00",
    19: "730.00",
    20: "800.00",
    21: "950.00",
  });
  expect(ladder(fees, "small")).toMatchObject({
    2: "19.00",
    6: "57.00",
    7: "72.00",
    8: "136.00",
  });
  // The PDF has no reduced rate from the 8th annuity; those rows have no tier.
  expect(byCode(fees, "inpi-fr-annuity-y08-l").tier).toBe("none");
  expect(fees.some((fee) => fee.code === "inpi-fr-annuity-y08-s")).toBe(false);
  expect(byCode(fees, "inpi-fr-annuity-y07-s").notes).toContain(
    "fewer than 250 employees",
  );
  expect(byCode(fees, "inpi-fr-ep-transmission-per-page-l")).toMatchObject({
    amount: "0.75",
    condition: { trigger: "pages_over" },
  });
  expect(patent.recurring_fee_coverage.status).toBe("complete");
});

test("real INPI PDF: trademark and design schedules", async () => {
  const [, trademark, design] = await feeRecordings("inpi-fr");
  if (!trademark || !design) throw new Error("missing schedules");
  expect(trademark.fees).toHaveLength(14);
  const tm = trademark.fees;
  expect(byCode(tm, "inpi-fr-tm-filing-1class-l")).toMatchObject({
    amount: "190.00",
    category: "filing",
    condition: null,
  });
  expect(byCode(tm, "inpi-fr-tm-class-additional-l")).toMatchObject({
    amount: "40.00",
    condition: { trigger: "classes_over", threshold: 1 },
  });
  expect(
    filterFees(tm, { category: "renewal", year: 10 }).map((fee) => fee.amount),
  ).toEqual(["290.00", "450.00"]);
  expect(byCode(tm, "inpi-fr-tm-renewal-class-additional-l").amount).toBe(
    "40.00",
  );
  expect(byCode(tm, "inpi-fr-tm-opposition-additional-right-l").amount).toBe(
    "150.00",
  );
  expect(byCode(tm, "inpi-fr-tm-relevé-déchéance-l").amount).toBe("156.00");
  expect(byCode(tm, "inpi-fr-tm-international-registration-l")).toMatchObject({
    amount: "62.00",
    category: "madrid",
  });

  expect(design.fees).toHaveLength(8);
  expect(byCode(design.fees, "inpi-fr-design-filing-l").amount).toBe("39.00");
  expect(ladder(design.fees)).toEqual({
    10: "52.00",
    15: "52.00",
    20: "52.00",
    25: "52.00",
  });
  expect(design.recurring_fee_coverage.status).toBe("complete");
});

test("INPI: the PDF is found through the Tarifs page, with Python's fallback", async () => {
  let pdfPath = "";
  const fallback = new InpiFrFeesClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) => {
      const url = String(input instanceof Request ? input.url : input);
      if (url.includes("download-document")) {
        pdfPath = new URL(url).search;
        return replay(url);
      }
      return new Response("<html><body>Tarifs</body></html>");
    }) as unknown as typeof fetch,
  });
  const schedule = await fallback.getDesignSchedule();
  expect(pdfPath).toBe("?id=20516");
  expect(schedule.provenance.as_of_status).toContain("not linked");
  const broken = new InpiFrFeesClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL) =>
      String(input instanceof Request ? input.url : input).includes(
        "download-document",
      )
        ? new Response(new Uint8Array([37, 80, 68, 70]))
        : new Response("<html></html>")) as unknown as typeof fetch,
  });
  expect(await code(broken.getPatentSchedule())).not.toBe("ok");
});

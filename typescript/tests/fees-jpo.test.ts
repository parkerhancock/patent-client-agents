import { expect, test } from "bun:test";
import {
  type FeeSchedule,
  FeesClient,
  filterFees,
  JPO_FEES_URL,
  JpoFeesClient,
  parseYenCell,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { recordedFeeFetch } from "./fees-recordings.js";

/** The JPO page cannot be recorded with plain requests (HTTP 403), so these tests serve the Python fixture. */
const page = await (await recordedFeeFetch()(JPO_FEES_URL)).text();
const jpo = (html = page, status = 200) => {
  let calls = 0;
  const client = new JpoFeesClient({
    retryLimit: 0,
    fetch: (async () => {
      calls++;
      return new Response(html, {
        status,
        headers: { "content-type": "text/html" },
      });
    }) as unknown as typeof fetch,
  });
  return { client, calls: () => calls };
};
const all = async () => {
  const { client, calls } = jpo();
  const schedules = await Promise.all([
    client.getPatentSchedule(),
    client.getTrademarkSchedule(),
    client.getDesignSchedule(),
  ]);
  return { schedules, calls: calls() };
};
const byCode = (schedule: FeeSchedule, code: string) =>
  schedule.fees.find((fee) => fee.code === code);

test("JPO fixture: patent schedule, examination cohorts and the per-claim split", async () => {
  const {
    schedules: [patent],
    calls,
  } = await all();
  if (!patent) throw new Error("missing schedule");
  expect(calls).toBe(1);
  expect(patent.key).toBe("JP/JPO/patent");
  expect(patent.fees).toHaveLength(253);
  expect(patent.unmapped_codes).toEqual([]);
  expect(patent.effective_date).toBe("2022-04-01");
  expect(patent.provenance.as_of_status).toBe(
    "schedule of fees on or after 2022-04-01; page last updated 2022-04-01",
  );
  // Amounts as published on the JPO page.
  for (const [code, amount] of [
    ["jp-application", "14000"],
    ["jp-application-foreign-language", "22000"],
    ["jp-pct-national-phase", "14000"],
    ["jp-examination", "138000"],
    ["jp-examination-per-claim", "4000"],
    // Python dropped this row: its first 60 characters match the JPO-ISR row.
    ["jp-examination-pct-other-isr", "124000"],
    ["jp-examination-pct-other-isr-per-claim", "3600"],
    ["jp-examination-pre-2019", "118000"],
    ["jp-opposition", "16500"],
    ["jp-opposition-per-claim", "2400"],
    ["jp-trial-term-extension", "55000"],
    ["jp-extension-article-50-late", "51000"],
    ["jp-transfer-of-right", "15000"],
  ])
    expect(byCode(patent, code as string)?.amount).toBe(amount);
  expect(byCode(patent, "jp-examination-pct-jpo-isr")?.category).toBe(
    "examination",
  );
  expect(byCode(patent, "jp-examination-per-claim")).toMatchObject({
    category: "excess_claims",
    condition: { trigger: "claims_over", threshold: 0, per_unit: true },
  });
  expect(byCode(patent, "jp-trial")?.category).toBe("trial");
  expect(byCode(patent, "jp-term-extension")?.category).toBe("other");
  // Other rights' transfer fees and the design-only Article 50 extension stay out.
  for (const code of [
    "jp-tm-transfer-of-right",
    "jp-des-extension-article-50-late",
  ])
    expect(byCode(patent, code)).toBeUndefined();
  expect(
    patent.fees.filter((fee) => fee.code === "jp-correction"),
  ).toHaveLength(1);
  expect(byCode(patent, "jp-extension-of-period")).toMatchObject({
    amount: "2100",
    rights: ["patent", "utility_model", "design", "trademark"],
  });
  expect(
    byCode(patent, "jp-request-for-other-certificates-on-line")?.amount,
  ).toBe("1100");
  expect(byCode(patent, "jp-electronic-conversion-per-sheet")).toMatchObject({
    amount: "800",
    condition: { trigger: "sheets_over" },
  });
});

test("JPO fixture: patent annual fees are renewals for years 1-25 in four cohorts", async () => {
  const {
    schedules: [patent],
  } = await all();
  if (!patent) throw new Error("missing schedule");
  const current = (year: number) =>
    [
      byCode(patent, `jp-annual-fee-y${year}`),
      byCode(patent, `jp-annual-fee-y${year}-per-claim`),
    ].map((fee) => fee?.amount);
  expect(current(1)).toEqual(["4300", "300"]);
  expect(current(5)).toEqual(["10300", "800"]);
  expect(current(9)).toEqual(["24800", "1900"]);
  expect(current(10)).toEqual(["59400", "4600"]);
  expect(current(25)).toEqual(["59400", "4600"]);
  expect(
    filterFees(patent.fees, { category: "renewal", year: 10 }).map((fee) => [
      fee.code,
      fee.amount,
    ]),
  ).toEqual([
    ["jp-annual-fee-y10", "59400"],
    ["jp-annual-fee-exam-pre-2004-y10", "64400"],
    ["jp-annual-fee-filed-pre-1988-y10", "47500"],
    ["jp-annual-fee-filed-pre-1988-exam-pre-2004-y10", "47500"],
  ]);
  expect(byCode(patent, "jp-annual-fee-y26")).toBeUndefined();
  expect(patent.fees.some((fee) => fee.category === "maintenance")).toBe(false);
  expect(patent.recurring_fee_coverage.status).toBe("complete");
});

test("JPO fixture: trademark and design schedules", async () => {
  const {
    schedules: [, trademark, design],
  } = await all();
  if (!trademark || !design) throw new Error("missing schedules");
  expect(trademark.fees).toHaveLength(38);
  expect(trademark.unmapped_codes).toEqual([]);
  expect(byCode(trademark, "jp-tm-application")?.amount).toBe("3400");
  expect(byCode(trademark, "jp-tm-application-per-class")).toMatchObject({
    category: "excess_classes",
    amount: "8600",
    condition: { trigger: "classes_over", threshold: 0 },
  });
  expect(
    filterFees(trademark.fees, { category: "renewal", year: 10 }).map((fee) => [
      fee.code,
      fee.amount,
    ]),
  ).toEqual([
    ["jp-tm-renewal", "43600"],
    ["jp-tm-renewal-installment", "22800"],
    ["jp-tm-defensive-mark-renewal", "37500"],
  ]);
  expect(byCode(trademark, "jp-tm-registration")).toMatchObject({
    category: "grant",
    amount: "32900",
    condition: { trigger: "classes_over" },
  });
  expect(byCode(trademark, "jp-tm-transfer-of-right")?.amount).toBe("30000");
  expect(byCode(trademark, "jp-transfer-of-right")).toBeUndefined();
  expect(trademark.recurring_fee_coverage.status).toBe("complete");

  expect(design.fees).toHaveLength(52);
  expect(design.unmapped_codes).toEqual([]);
  expect(byCode(design, "jp-des-application")).toMatchObject({
    label: "Design application",
    amount: "16000",
  });
  expect(byCode(design, "jp-des-secret-design")?.amount).toBe("5100");
  const ladder = Object.fromEntries(
    design.fees
      .filter((fee) => fee.category === "renewal")
      .map((fee) => [fee.year, fee.amount]),
  );
  expect(Object.keys(ladder)).toHaveLength(25);
  expect([1, 3, 4, 15, 16, 20, 21, 25].map((year) => ladder[year])).toEqual([
    "8500",
    "8500",
    "16900",
    "16900",
    "16900",
    "16900",
    "16900",
    "16900",
  ]);
  expect(byCode(design, "jp-des-annual-fee-y21")?.notes).toContain(
    "April 1, 2020",
  );
  expect(byCode(design, "jp-des-extension-article-50-late")?.amount).toBe(
    "7200",
  );
  expect(byCode(design, "jp-des-transfer-of-right")?.amount).toBe("9000");
  expect(design.recurring_fee_coverage.status).toBe("complete");
});

test("yen cells parse exactly or fail", () => {
  expect(parseYenCell("¥14,000")).toEqual({
    base: "14000",
    per: null,
    unit: null,
  });
  expect(parseYenCell("¥118,000 +¥4,000 per claim")).toEqual({
    base: "118000",
    per: "4000",
    unit: "claim",
  });
  expect(parseYenCell("¥32,900 per classification")).toEqual({
    base: null,
    per: "32900",
    unit: "classification",
  });
  for (const bad of ["14,000 yen", "¥14.000", "¥1,000 per page", ""])
    expect(() => parseYenCell(bad)).toThrow();
});

test("JPO page drift fails or surfaces; a blocked page is an HTTP error", async () => {
  const unknown = await jpo(
    page.replace(
      "Request for inspection of documents (paper)",
      "Request for a brand new service",
    ),
  ).client.getPatentSchedule();
  expect(unknown.unmapped_codes).toEqual([
    "jp-request-for-a-brand-new-service",
  ]);
  expect(byCode(unknown, "jp-request-for-a-brand-new-service")?.category).toBe(
    "other",
  );
  for (const html of [
    page.replace("(on or after April 1, 2022)", "(current)"),
    page.replace("&yen;22,000", "22,000 yen"),
    page.replace("<h2>5. Others</h2>", "<h2>Others</h2>"),
  ])
    expect(
      await jpo(html)
        .client.getPatentSchedule()
        .catch((error) => error.code),
    ).toBe("INVALID_RESPONSE");
  expect(
    await jpo("Forbidden", 403)
      .client.getDesignSchedule()
      .catch((error) => error.status),
  ).toBe(403);
});

test("JPO aliases resolve and route through FeesClient", async () => {
  for (const name of ["JPO", "JP", "japan", "Japan Patent Office"])
    expect(resolveFeeJurisdiction(name, "trademark")).toEqual(["JP", "JPO"]);
  const fees = new FeesClient({
    retryLimit: 0,
    fetch: recordedFeeFetch(),
  });
  expect((await fees.getSchedule("Japan", "design")).key).toBe("JP/JPO/design");
  expect(
    await fees.getSchedule("JP", "utility_model").catch((error) => error.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

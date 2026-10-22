import { expect, test } from "bun:test";
import {
  type FeeSchedule,
  FeesClient,
  filterFees,
  parseOepmAmount,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeFetch } from "./fees-recordings.js";

/** The OEPM PDF recorded October 22, 2026 ("desde el 1 de abril de 2026"). */
const recording = feeRecordings("oepm");
const schedule = async (right: "patent" | "trademark" | "design") => {
  const found = (await recording).find((item) => item.right === right);
  if (!found) throw new Error(`No OEPM ${right} schedule.`);
  return found;
};
const fee = (s: FeeSchedule, code: string) => {
  const found = s.fees.find((item) => item.code === `oepm-${code}`);
  if (!found) throw new Error(`No ${code} in ${s.key}.`);
  return found;
};
const codes = (s: FeeSchedule) => new Set(s.fees.map((item) => item.code));

test("real OEPM PDF: three schedules, every code mapped, effective date from page 1", async () => {
  const schedules = await recording;
  expect(schedules.map((s) => [s.key, s.fees.length])).toEqual([
    ["ES/OEPM/patent", 369],
    ["ES/OEPM/trademark", 71],
    ["ES/OEPM/design", 92],
  ]);
  for (const s of schedules) {
    expect(s.effective_date).toBe("2026-04-01");
    expect(s.provenance.effective_date).toBe("2026-04-01");
    expect(s.currency).toBe("EUR");
    expect(s.unmapped_codes).toEqual([]);
    expect(s.recurring_fee_coverage.status).toBe("complete");
    // Agent registration fees (BB01, BB02) are not IP-right fees.
    expect(codes(s).has("oepm-BB01")).toBe(false);
  }
});

test("OEPM patent fees: three applicant tiers and paper versus electronic rows", async () => {
  const patent = await schedule("patent");
  expect(fee(patent, "IT01")).toMatchObject({
    amount: "102.39",
    category: "filing",
    tier: "large",
    condition: { trigger: "paper_filing" },
  });
  expect(fee(patent, "IE01")).toMatchObject({
    amount: "87.03",
    tier: "large",
    condition: null,
  });
  expect(fee(patent, "YT01")).toMatchObject({ amount: "51.20", tier: "small" });
  expect(fee(patent, "UT02")).toMatchObject({ amount: "5.25", tier: "small" });
  expect(fee(patent, "IT04")).toMatchObject({
    amount: "698.42",
    category: "search",
  });
  expect(fee(patent, "IE22")).toMatchObject({
    amount: "337.96",
    category: "examination",
  });
  expect(fee(patent, "I702")).toMatchObject({
    amount: "44.93",
    category: "appeal",
    tier: "small",
  });
  expect(fee(patent, "I304-page")).toMatchObject({
    amount: "1.15",
    condition: { trigger: "pages_over", threshold: 10 },
  });
  expect(fee(patent, "ET03")).toMatchObject({
    amount: "327.38",
    category: "translation",
  });
  expect(fee(patent, "ET04-page")).toMatchObject({
    amount: "11.19",
    condition: { trigger: "pages_over", threshold: 22 },
  });
  expect(fee(patent, "PCT1")).toMatchObject({
    amount: "1885.00",
    category: "search",
  });
  expect(fee(patent, "pct-international-filing").amount).toBe("1428.00");
  expect(fee(patent, "pct-reduction-pdf").category).toBe("other");
  // Procedural fees for trademarks and designs stay out of the patent schedule.
  expect(codes(patent).has("oepm-CM01")).toBe(false);
});

test("OEPM annual fees: years 3-20 per tier with surcharges, and SPC fees are not annuities", async () => {
  const patent = await schedule("patent");
  const ladder = (prefix: string) =>
    patent.fees
      .filter((item) =>
        new RegExp(`^oepm-${prefix}(?!00)\\d\\d$`).test(item.code),
      )
      .map((item) => item.year);
  const years = Array.from({ length: 18 }, (_, i) => i + 3);
  for (const prefix of ["IP", "2P", "5P", "YP", "UP", "IR"])
    expect(ladder(prefix)).toEqual(years);
  expect(
    filterFees(patent.fees, { category: "renewal", year: 10 }).map((item) => [
      item.code,
      item.amount,
    ]),
  ).toEqual([["oepm-IP10", "220.40"]]);
  expect(
    filterFees(patent.fees, { category: "renewal", year: 6, tier: "small" })
      .map((item) => [item.code, item.amount])
      .sort(),
  ).toEqual([
    ["oepm-UP06", "33.21"],
    ["oepm-YP06", "66.41"],
  ]);
  expect(fee(patent, "IP03").amount).toBe("18.85");
  expect(fee(patent, "IP20").amount).toBe("499.85");
  expect(fee(patent, "2P10")).toMatchObject({
    amount: "275.51",
    category: "late_fee",
    year: 10,
  });
  expect(fee(patent, "IR10")).toMatchObject({
    amount: "110.20",
    category: "other",
    year: 10,
  });
  // SPC maintenance fees are set by SPC term, not by year.
  expect(fee(patent, "CP03")).toMatchObject({
    amount: "2714.54",
    category: "other",
    year: null,
  });
  expect(fee(patent, "CP53").category).toBe("late_fee");
  expect(
    patent.fees.filter(
      (item) => item.category === "renewal" && item.code.startsWith("oepm-CP"),
    ),
  ).toEqual([]);
});

test("OEPM trademark codes carry the meanings the PDF prints next to them", async () => {
  const trademark = await schedule("trademark");
  expect(fee(trademark, "MT01")).toMatchObject({
    amount: "150.45",
    category: "filing",
  });
  expect(fee(trademark, "MT01-class")).toMatchObject({
    amount: "97.48",
    category: "excess_classes",
    condition: { trigger: "classes_over", threshold: 1 },
  });
  expect(fee(trademark, "ME02").amount).toBe("255.74");
  expect(fee(trademark, "MT17")).toMatchObject({
    amount: "97.48",
    category: "late_fee",
  });
  expect(fee(trademark, "MT17").label).toContain("not paid");
  expect(fee(trademark, "MT07").category).toBe("petition");
  expect(fee(trademark, "MT08").label).toContain("priority");
  expect(fee(trademark, "MT15")).toMatchObject({
    amount: "35.12",
    category: "transfer",
  });
  expect(fee(trademark, "MT03").category).toBe("madrid");
  expect(fee(trademark, "CM07").category).toBe("other");
  expect(
    filterFees(trademark.fees, { category: "renewal", year: 10 }).map(
      (item) => [item.code, item.amount],
    ),
  ).toEqual([
    ["oepm-MT11", "174.18"],
    ["oepm-MT11-class", "116.95"],
    ["oepm-ME04", "148.06"],
    ["oepm-ME04-class", "99.39"],
    ["oepm-MT12", "349.87"],
    ["oepm-MT12-class", "233.90"],
    ["oepm-ME05", "297.40"],
    ["oepm-ME05-class", "198.81"],
  ]);
  expect(fee(trademark, "EC50")).toMatchObject({
    amount: "222.09",
    category: "late_fee",
    year: 10,
  });
  const all = codes(trademark);
  for (const code of ["oepm-I301", "oepm-IT01", "oepm-PCT1", "oepm-DT40"])
    expect(all.has(code)).toBe(false);
});

test("OEPM design fees: per-design bands for filing, opposition and renewal", async () => {
  const design = await schedule("design");
  expect(
    design.fees
      .filter((item) => item.code.startsWith("oepm-DT40"))
      .map((item) => [item.code, item.amount, item.condition?.threshold]),
  ).toEqual([
    ["oepm-DT40", "77.96", 0],
    ["oepm-DT40-11-20", "68.23", 10],
    ["oepm-DT40-21-30", "56.66", 20],
    ["oepm-DT40-31-40", "45.34", 30],
    ["oepm-DT40-41-50", "36.30", 40],
  ]);
  expect(fee(design, "DE45").amount).toBe("37.90");
  expect(fee(design, "DT41")).toMatchObject({
    amount: "100.64",
    category: "renewal",
    year: 5,
  });
  expect(fee(design, "DE43-41-50")).toMatchObject({
    amount: "52.54",
    category: "late_fee",
    year: 5,
  });
  expect(fee(design, "DQR1-50").amount).toBe("129.80");
  expect(fee(design, "DT35").category).toBe("other");
  expect(fee(design, "CM08").category).toBe("opposition");
  expect(codes(design).has("oepm-MT01")).toBe(false);
});

test("Spanish amounts parse exactly or fail", () => {
  expect(parseOepmAmount("7.329,17")).toBe("7329.17");
  expect(parseOepmAmount("3,64")).toBe("3.64");
  for (const bad of ["7,329.17", "100", "", "1.23,45"])
    expect(() => parseOepmAmount(bad)).toThrow();
});

test("OEPM routes resolve through the Python aliases", async () => {
  const client = new FeesClient({
    retryLimit: 0,
    fetch: recordedFeeFetch(),
  });
  expect((await client.getSchedule("Spain", "trademark")).key).toBe(
    "ES/OEPM/trademark",
  );
  expect((await client.getSchedule("ES", "design")).key).toBe("ES/OEPM/design");
  const { fees } = await client.lookupFees(
    "Oficina Española de Patentes y Marcas",
    { category: "filing", tier: "small" },
  );
  expect(fees.map((item) => item.code)).toContain("oepm-YE01");
  expect(
    await client.getSchedule("OEPM", "utility_model").catch((e) => e.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

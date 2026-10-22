import { expect, test } from "bun:test";
import {
  type FeeSchedule,
  FeesClient,
  filterFees,
  ImpiFeesClient,
  impiFees,
  impiReducible,
  impiRows,
  parsePesoAmount,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeFetch } from "./fees-recordings.js";

const offline = (async () => {
  throw new Error("unrecorded request");
}) as unknown as typeof fetch;
const find = (schedule: FeeSchedule, code: string, tier = "large") =>
  schedule.fees.find((fee) => fee.code === code && fee.tier === tier);

test("real IMPI tariff: patent schedule with Cuarta tiers and annuities by year", async () => {
  const [patent] = await feeRecordings("impi");
  if (!patent) throw new Error("no patent schedule");
  expect(patent.key).toBe("MX/IMPI/patent");
  expect(patent.currency).toBe("MXN");
  expect(patent.effective_date).toBe("2023-05-12");
  expect(patent.unmapped_codes).toEqual([]);
  expect(patent.fees).toHaveLength(109);
  // Spot checks against the Acuerdo PDF.
  expect(find(patent, "impi-1-a")).toMatchObject({
    category: "filing",
    amount: "4550.00",
  });
  expect(find(patent, "impi-1-a-small", "small")?.amount).toBe("2275.00");
  expect(find(patent, "impi-1-a-bis")).toMatchObject({
    category: "excess_pages",
    amount: "61.00",
    condition: { trigger: "pages_over", threshold: 30 },
  });
  expect(find(patent, "impi-1-e")).toMatchObject({
    category: "grant",
    amount: "3099.84",
  });
  // 1 g is outside Disposición Cuarta: one untiered row.
  expect(patent.fees.filter((fee) => fee.code.startsWith("impi-1-g"))).toEqual([
    expect.objectContaining({ tier: "none", amount: "27770.70" }),
  ]);
  for (const [year, amount] of [
    [1, "1161.90"],
    [5, "1161.90"],
    [6, "1360.69"],
    [10, "1360.69"],
    [11, "1536.99"],
    [20, "1536.99"],
  ] as const) {
    const [large] = filterFees(patent.fees, { category: "renewal", year });
    const [small] = filterFees(patent.fees, {
      category: "renewal",
      year,
      tier: "small",
    });
    expect(large?.amount).toBe(amount);
    expect(small?.amount).toBe(
      { "1161.90": "580.95", "1360.69": "680.34", "1536.99": "768.50" }[amount],
    );
  }
  expect(patent.recurring_fee_coverage.status).toBe("complete");
  // The Madrid MXN rows and utility models are not patent fees.
  expect(patent.fees.some((fee) => /^impi-(9|10|36)-/.test(fee.code))).toBe(
    false,
  );
  expect(find(patent, "impi-32", "none")?.category).toBe("transfer");
});

test("real IMPI tariff: utility model, design and trade mark schedules", async () => {
  const [, utility, design, trademark] = await feeRecordings("impi");
  if (!utility || !design || !trademark) throw new Error("missing schedules");
  expect(utility.key).toBe("MX/IMPI/utility_model");
  expect(utility.fees).toHaveLength(83);
  expect(find(utility, "impi-9-a")?.amount).toBe("2000.00");
  // 9 e has no "$" in the PDF and was missing from the Python scraper.
  expect(find(utility, "impi-9-e")?.amount).toBe("1044.91");
  expect(
    filterFees(utility.fees, { category: "renewal", year: 15 })[0]?.amount,
  ).toBe("1290.36");
  expect(utility.recurring_fee_coverage.status).toBe("complete");

  expect(design.key).toBe("MX/IMPI/design");
  expect(design.fees).toHaveLength(44);
  expect(find(design, "impi-9-f")).toMatchObject({
    category: "filing",
    amount: "2000.00",
  });
  expect(find(design, "impi-9-g")?.amount).toBe("5770.45");
  expect(
    design.fees
      .filter((fee) => fee.category === "renewal" && fee.tier === "large")
      .map((fee) => [fee.year, fee.amount]),
  ).toEqual([
    [5, "5926.75"],
    [10, "5926.75"],
    [15, "5926.75"],
    [20, "5926.75"],
  ]);
  expect(find(design, "impi-37-iii", "none")?.amount).toBe("2500.00");

  expect(trademark.key).toBe("MX/IMPI/trademark");
  expect(trademark.fees).toHaveLength(34);
  expect(trademark.fees.every((fee) => fee.tier === "none")).toBe(true);
  const tm = (code: string) => find(trademark, code, "none");
  expect(tm("impi-14-a")).toMatchObject({
    category: "filing",
    amount: "2695.18",
  });
  // "14b", "14f" and "14g" lack a space in the PDF; Python dropped them.
  expect(tm("impi-14-b")).toMatchObject({
    category: "opposition",
    amount: "3704.09",
  });
  expect(tm("impi-14-f")?.amount).toBe("2521.09");
  expect(tm("impi-14-g")?.amount).toBe("975.34");
  expect(tm("impi-14-c")).toMatchObject({
    category: "renewal",
    year: 10,
    amount: "2597.77",
  });
  expect(
    trademark.fees
      .filter((fee) => fee.category === "madrid")
      .map((fee) => fee.amount),
  ).toEqual(["1195.21", "801.24", "2292.24", "542.81"]);
  expect(tm("impi-13")).toBeUndefined();
});

test("IMPI parsing helpers", () => {
  expect(parsePesoAmount("$4,550.00")).toBe("4550.00");
  expect(parsePesoAmount("$ 1,099.39")).toBe("1099.39");
  expect(parsePesoAmount("$1,348. 51")).toBe("1348.51");
  expect(parsePesoAmount("2,500")).toBe("2500.00");
  for (const bad of ["4.550,00", "abc", ""])
    expect(() => parsePesoAmount(bad)).toThrow();
  expect(impiReducible("1 f")).toBe(true);
  expect(impiReducible("1 g")).toBe(false);
  expect(impiReducible("13")).toBe(true);
  expect(impiReducible("14 a")).toBe(false);
  expect(impiReducible("26 bis")).toBe(true);
  expect(impiReducible("27 a")).toBe(false);
  const { rows, lastReform } = impiRows([
    [
      "Última reforma publicada DOF: 12 - 0 5 - 202 3",
      "1 a Por la presentación de una solicitud de patente y sus anexos de hasta 30",
      "hojas; $4,550.00",
      "1b Por la entrada a la fase nacional; $3,147.00",
      "3",
      "Incidente de daños y perjuicios.",
      "quáter $1,349.22",
      "99 Something unknown $1.00",
      "4 Nuevo concepto $5.00",
    ].join("\n"),
  ]);
  expect(lastReform).toBe("2023-05-12");
  expect(rows.map((row) => [row.code, row.amount])).toEqual([
    ["1 a", "4550.00"],
    ["1 b", "3147.00"],
    ["3 quáter", "1349.22"],
    ["4", "5.00"],
  ]);
  expect(
    impiFees([{ code: "17 z", description: "x", amount: "1.00" }], "patent")
      .unmapped,
  ).toEqual(["17 z"]);
});

test("IMPI routes by alias, shares one fetch and offers utility models", async () => {
  expect(resolveFeeJurisdiction("México", "trademark")).toEqual(["MX", "IMPI"]);
  let calls = 0;
  const replay = recordedFeeFetch(["impi"], offline);
  const client = new ImpiFeesClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      calls++;
      return replay(input, init);
    }) as typeof fetch,
  });
  await Promise.all([
    client.getPatentSchedule(),
    client.getUtilityModelSchedule(),
    client.getDesignSchedule(),
    client.getTrademarkSchedule(),
  ]);
  expect(calls).toBe(1);
  const fees = new FeesClient({ retryLimit: 0, fetch: replay });
  expect((await fees.getSchedule("MX", "utility_model")).key).toBe(
    "MX/IMPI/utility_model",
  );
});

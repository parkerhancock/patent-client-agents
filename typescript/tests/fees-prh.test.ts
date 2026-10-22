import { expect, test } from "bun:test";
import {
  type FeeItem,
  FeesClient,
  filterFees,
  PRH_FEES_PDF_URL,
  PrhFeesClient,
  parsePrhAmount,
  prhEffectiveDate,
  prhRows,
  resolveFeeJurisdiction,
} from "@patent-client-agents/client";
import { feeRecordings, recordedFeeFetch } from "./fees-recordings.js";

const recorded = feeRecordings("prh");
const pick = (fees: FeeItem[], code: string) =>
  fees.find((fee) => fee.code === code);

test("real PRH regulation: patent schedule bundles sections 1-5", async () => {
  const [patent] = await recorded;
  expect(patent?.key).toBe("FI/PRH/patent");
  expect(patent?.fees.length).toBe(98);
  expect(patent?.effective_date).toBe("2026-04-01");
  expect(patent?.provenance).toMatchObject({
    source_url: PRH_FEES_PDF_URL,
    as_of_status:
      "in force from 2026-04-01 per the regulation; regulation 171/2026",
  });
  expect(patent?.statutory_basis).toContain(
    "1216/2025, as amended by 171/2026",
  );
  expect(patent?.recurring_fee_coverage.status).toBe("complete");
  const fees = patent?.fees ?? [];
  // Spot checks against Maksuasetus 171/2026, section 1.
  expect(
    pick(fees, "fi-prh-pat-hakemusmaksu-sahkoista-jarjestelmaa-kayttaen"),
  ).toMatchObject({ amount: "450.00", category: "filing", condition: null });
  expect(
    pick(
      fees,
      "fi-prh-pat-hakemusmaksu-muuta-kuin-sahkoista-jarjestelmaa-kayttaen",
    ),
  ).toMatchObject({
    amount: "580.00",
    condition: { trigger: "paper_filing" },
  });
  const ladder = Object.fromEntries(
    fees
      .filter(
        (fee) =>
          fee.code.startsWith("fi-prh-pat-") && fee.category === "renewal",
      )
      .map((fee) => [fee.year, fee.amount]),
  );
  expect(Object.keys(ladder).length).toBe(20);
  expect([ladder[1], ladder[2], ladder[10], ladder[20]]).toEqual([
    "0.00",
    "80.00",
    "450.00",
    "1010.00",
  ]);
  const excess = filterFees(fees, { category: "excess_claims" });
  expect(
    excess.map((fee) => [fee.amount, fee.condition?.threshold ?? null]),
  ).toEqual([
    ["60.00", 15],
    ["60.00", null],
    ["30.00", 5],
  ]);
  // Section 2 utility model renewals fall due at years 4 and 8; their surcharges are late fees.
  expect(
    fees
      .filter((fee) => fee.code.startsWith("fi-prh-um-") && fee.year !== null)
      .map((fee) => [fee.category, fee.year, fee.amount]),
  ).toEqual([
    ["renewal", 4, "330.00"],
    ["late_fee", 4, "70.00"],
    ["renewal", 8, "280.00"],
    ["late_fee", 8, "70.00"],
  ]);
  expect(
    fees
      .filter(
        (fee) =>
          fee.code.startsWith("fi-prh-spc-") && fee.category === "renewal",
      )
      .map((fee) => [fee.year, fee.amount]),
  ).toEqual([
    [1, "1060.00"],
    [2, "1160.00"],
    [3, "1260.00"],
    [4, "1360.00"],
    [5, "1460.00"],
    [6, "1560.00"],
  ]);
  const refund = fees.find((fee) => fee.code.startsWith("fi-prh-pct-palautus"));
  expect(refund).toMatchObject({ category: "other", amount: "300.00" });
  expect(refund?.notes).toContain("refund");
  expect(
    pick(
      fees,
      "fi-prh-pct-lisamaksu-uutuustutkimuksesta-pct-saannon-40-2-a-mukaan",
    )?.category,
  ).toBe("search");
  expect(pick(fees, "fi-prh-spc-ensimmainen-kerta")?.label).toBe(
    "Maksu uudelleenkäsiteltäväksi ottamisesta, ensimmäinen kerta",
  );
  expect(pick(fees, "fi-prh-pat-oikeaksi-todistaminen")?.notes).toBe(
    "Unit: 15 € + 1 €/sivu.",
  );
  expect(
    pick(fees, "fi-prh-pct-kopiot-sivu-pct-saannon-94-1ter-ja-94-2-mukaan")
      ?.amount,
  ).toBe("0.60");
});

test("real PRH regulation: trademark channels and late renewals", async () => {
  const [, trademark] = await recorded;
  const fees = trademark?.fees ?? [];
  expect(trademark?.key).toBe("FI/PRH/trademark");
  expect(fees.length).toBe(35);
  expect(
    pick(fees, "fi-prh-tm-electronic-tavaramerkin-rekisteroinnin-hakemusmaksu")
      ?.amount,
  ).toBe("250.00");
  expect(
    pick(fees, "fi-prh-tm-paper-tavaramerkin-rekisteroinnin-hakemusmaksu"),
  ).toMatchObject({ amount: "300.00", condition: { trigger: "paper_filing" } });
  // Renewal lookup: individual and collective marks, electronic and paper; late renewals are separate.
  expect(
    filterFees(fees, { category: "renewal", year: 10 }).map(
      (fee) => fee.amount,
    ),
  ).toEqual(["250.00", "340.00", "300.00", "390.00"]);
  expect(
    filterFees(fees, { category: "late_fee", year: 10 }).map(
      (fee) => fee.amount,
    ),
  ).toEqual(["320.00", "410.00", "370.00", "460.00"]);
  for (const fee of filterFees(fees, { category: "excess_classes" }))
    expect(fee).toMatchObject({
      amount: "100.00",
      condition: { trigger: "classes_over", threshold: 1, per_unit: true },
    });
  expect(
    pick(
      fees,
      "fi-prh-tm-electronic-maksu-vaitteen-tekemisesta-rekisterointia-vastaan",
    )?.category,
  ).toBe("opposition");
  expect(
    pick(
      fees,
      "fi-prh-tm-electronic-hallinnollinen-menettamis-ja-mitatointihakemusmaksu",
    )?.category,
  ).toBe("cancellation");
  // The Madrid transmittal fee and certificates follow the paper block but apply to both channels.
  expect(
    pick(
      fees,
      "fi-prh-tm-kansainvalisen-tavaramerkkihakemuksen-vastaanottomaksu",
    ),
  ).toMatchObject({ amount: "170.00", category: "madrid", condition: null });
});

test("real PRH regulation: design renewals every five years", async () => {
  const [, , design] = await recorded;
  const fees = design?.fees ?? [];
  expect(design?.key).toBe("FI/PRH/design");
  expect(fees.length).toBe(22);
  expect(
    filterFees(fees, { category: "filing" }).map((fee) => [
      fee.amount,
      fee.condition?.trigger ?? null,
    ]),
  ).toEqual([
    ["250.00", null],
    ["300.00", "paper_filing"],
    ["130.00", "multi_design"],
  ]);
  for (const year of [5, 10, 15, 20])
    expect(
      filterFees(fees, { category: "renewal", year }).map((fee) => fee.amount),
    ).toEqual(["380.00"]);
  expect(filterFees(fees, { category: "renewal", year: 25 })).toEqual([]);
  expect(design?.recurring_fee_coverage.status).toBe("complete");
  expect(
    fees.find((fee) => fee.code.startsWith("fi-prh-des-jos-uudistamismaksu"))
      ?.category,
  ).toBe("late_fee");
  expect(
    pick(fees, "fi-prh-des-sailytysmaksu-jokaiselta-mallikappaleelta")
      ?.category,
  ).toBe("other");
});

test("PRH parsers: amounts, dates and drift", () => {
  expect(parsePrhAmount("1 010")).toBe("1010.00");
  expect(parsePrhAmount("1 885")).toBe("1885.00");
  expect(parsePrhAmount("0,60")).toBe("0.60");
  for (const bad of ["1.010", "1,010.00", "abc", "10 10"])
    expect(() => parsePrhAmount(bad)).toThrow();
  expect(
    prhEffectiveDate("Tämä asetus tulee voimaan 1 päivänä huhtikuuta 2026."),
  ).toBe("2026-04-01");
  expect(prhEffectiveDate("Tämä asetus tulee voimaan pian.")).toBeNull();
  // A regulation missing the design section is rejected rather than parsed short.
  expect(() =>
    prhRows(["1. Kansalliset patenttiasiat", "Hakemusmaksu 450 €"]),
  ).toThrow("sections 1-9");
  expect(
    prhRows([
      "8. Tavaramerkkiasiat",
      "Maksut muuta kuin sähköistä järjestelmää käyttäen",
      "Tavaramerkin rekisteröinnin hakemusmaksu 300 €",
      "9. Mallioikeusasiat",
      "Maksu uudelleenkäsiteltäväksi ottamisesta",
      "ensimmäinen kerta 110 €",
      "Oikeaksi todistaminen 15 € +",
      "1 €/sivu",
      "10. Kaupparekisteriasiat",
    ]).map((row) => [row.channel, row.label, row.amount, row.unit]),
  ).toEqual([
    ["paper", "Tavaramerkin rekisteröinnin hakemusmaksu", "300.00", null],
    [
      "default",
      "Maksu uudelleenkäsiteltäväksi ottamisesta, ensimmäinen kerta",
      "110.00",
      null,
    ],
    ["default", "Oikeaksi todistaminen", "15.00", "+ 1 €/sivu"],
  ]);
});

test("PRH routes resolve through FeesClient and share one PDF fetch", async () => {
  for (const name of ["PRH", "Finland", "FI", "Patentti- ja rekisterihallitus"])
    expect(resolveFeeJurisdiction(name, "design")).toEqual(["FI", "PRH"]);
  let fetches = 0;
  const replay = recordedFeeFetch();
  const fetch = ((input: RequestInfo | URL) => {
    fetches++;
    return replay(input);
  }) as unknown as typeof globalThis.fetch;
  const prh = new PrhFeesClient({ retryLimit: 0, fetch });
  await Promise.all([
    prh.getPatentSchedule(),
    prh.getTrademarkSchedule(),
    prh.getDesignSchedule(),
  ]);
  expect(fetches).toBe(1);
  const client = new FeesClient({ retryLimit: 0, fetch });
  expect(client.supportedRoutes).toEqual(
    expect.arrayContaining(["PRH/patent", "PRH/trademark", "PRH/design"]),
  );
  const { fees } = await client.lookupFees("Finland", {
    category: "renewal",
    year: 20,
  });
  expect(fees.map((fee) => fee.amount)).toEqual(["1010.00"]);
  expect(
    await client
      .getSchedule("FI", "utility_model")
      .catch((error) => error.code),
  ).toBe("UNSUPPORTED_RIGHT");
});

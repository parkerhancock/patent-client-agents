import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import {
  PrvClient,
  PrvError,
  type PrvPage,
  type PrvRow,
  prvApplicationNumber,
} from "../packages/client/src/index.js";
import { cassettePath, prvRecording, samples } from "./prv-recordings.js";

const page = (name: string) => prvRecording<PrvPage>(name);
const record = (name: string) =>
  prvRecording<{ data: PrvRow; provenance: { source_url: string } }>(name);
/** The JSON body a cassette's (only) request sent. */
async function sentBody(name: string) {
  const text = await readFile(cassettePath(name), "utf8");
  const match =
    /body:\s*\n\s*type: json\s*\n\s*content:\s*\n([\s\S]*?)\n\s{2}response:/.exec(
      text,
    );
  return match?.[1] ?? text;
}

test("searches return PRV's rows with honest paging", async () => {
  const first = await page("patents-search");
  expect(first.rows).toHaveLength(2);
  expect(first).toMatchObject({
    total_hits: 3604,
    total_pages: 1802,
    page: 0,
    more_available: true,
  });
  expect(first.rows[0]).toMatchObject({
    applicationNumberFormatted: expect.stringMatching(/^SE\d{7}-\d$/),
    applicationType: "NAT",
  });
  expect(first.provenance.source_url).toBe(
    "https://patents-search-api.prv.se/searchpatent/patentsimplesearch/",
  );
  const second = await page("patents-search-page-1");
  expect(second.page).toBe(1);
  expect(second.rows[0]?.idPatent).not.toBe(first.rows[0]?.idPatent);
  const trademarks = await page("trademarks-search");
  expect(trademarks.rows[0]).toMatchObject({
    dossierTypeEn: expect.any(String),
    classes: expect.any(Array),
  });
  const designs = await page("designs-search");
  expect(designs.rows[0]).toMatchObject({
    designNumber: expect.any(Number),
    designsTotal: expect.any(Number),
  });
});

test("SPC filters use the keys PRV's app sends", async () => {
  // Python sent substanceProduct, which PRV ignores: every substance search found nothing.
  const substance = await page("spcs-substance");
  expect(substance.total_hits).toBe(4);
  expect(await sentBody("spcs-substance")).toContain("substance:");
  expect(await sentBody("spcs-substance")).not.toContain("substanceProduct");
  expect(
    substance.rows.every((row) => String(row.substance).includes("naproxen")),
  ).toBe(true);
  const base = await page("spcs-base-patent");
  expect(base.rows.map((row) => row.applicationNumberFormatted)).toEqual([
    samples.epPatent,
  ]);
  // A CONTAINS search on a number field gets HTTP 406.
  expect(await sentBody("spcs-base-patent")).toContain("STARTS_WITH");
  // totalPages is a last index: 0 here, for one hit.
  expect(base).toMatchObject({
    total_hits: 1,
    total_pages: 1,
    more_available: false,
  });
  expect(
    (await page("spcs-number")).rows[0]?.applicationNumberSpcFormatted,
  ).toBe("1190011-5");
  expect(
    (await page("spcs-marketing-authorization")).total_hits,
  ).toBeGreaterThan(1000);
  expect((await page("spcs-applicant")).total_hits).toBe(32);
});

test("patent records resolve formatted, compact and EP numbers; unknown ones are NOT_FOUND", async () => {
  const formatted = await record("patent-record");
  expect(formatted.data).toMatchObject({
    applicationNumberFormatted: samples.patent,
    statusDisplayTextEn: expect.any(String),
    registryEntriesEn: expect.any(Array),
  });
  // PRV answers HTTP 400 for the compact form; the client adds the SE prefix.
  const compact = await record("patent-record-compact");
  expect(compact.provenance.source_url).toBe(
    `https://api.prv.se/patents/applications/${samples.patent}`,
  );
  expect(compact.data.applicationNumberFormatted).toBe(samples.patent);
  const ep = await record("patent-record-ep");
  expect(ep.data).toMatchObject({ applicationType: "EP" });
  const missing = await record("patent-missing").catch((e) => e);
  expect(missing).toBeInstanceOf(PrvError);
  expect(missing).toMatchObject({ code: "NOT_FOUND", status: 404 });
  expect(missing.message).toContain("99999999");
});

test("application numbers normalize to the register's form", () => {
  expect(prvApplicationNumber("26155556")).toBe("SE2615555-6");
  expect(prvApplicationNumber(" 2615555-6 ")).toBe("SE2615555-6");
  expect(prvApplicationNumber("se2615555-6")).toBe("SE2615555-6");
  expect(prvApplicationNumber("EP001084805")).toBe("EP00108480.5");
  expect(prvApplicationNumber("EP00108480.5")).toBe("EP00108480.5");
  expect(prvApplicationNumber("PCT/SE2020/050001")).toBe("PCT/SE2020/050001");
  expect(() => prvApplicationNumber(" ")).toThrow("required");
});

// ── Synthetic edge cases ─────────────────────────────────────────────

function fake(
  respond: (body: Record<string, unknown>) => unknown,
  status = 200,
) {
  const bodies: Record<string, unknown>[] = [];
  const client = new PrvClient({
    retryLimit: 0,
    fetch: (async (input, init) => {
      const request = new Request(input, init);
      const body = request.method === "POST" ? await request.json() : {};
      bodies.push(body as Record<string, unknown>);
      return Response.json(respond(body as Record<string, unknown>), {
        status,
      });
    }) as typeof fetch,
  });
  return { client, bodies };
}
const empty = {
  totalHits: 0,
  totalPages: -1,
  hits: 0,
  page: 0,
  searchSpcDTOS: [],
};

test("SPC searches need a filter and fall back to a match type each field accepts", async () => {
  const { client, bodies } = fake(() => empty);
  await expect(client.searchSpcs()).rejects.toThrow("at least one filter");
  await expect(
    client.searchSpcs({ announcement: "Alla" as never }),
  ).rejects.toThrow("Unknown SPC announcement type");
  const result = await client.searchSpcs({
    substance: "x",
    basePatentNumber: "EP1",
    marketingAuthorizationNumber: "EU/1",
    announcement: "Meddelade tilläggsskydd",
    matchType: "STARTS_WITH",
    pageSize: 1000,
  });
  expect(bodies[0]).toEqual({
    page: 0,
    pageSize: 100,
    sortColumn: "",
    sortOrder: "ASC",
    substance: { value: "x", searchType: "STARTS_WITH" },
    applicationNumber: { value: "EP1", searchType: "STARTS_WITH" },
    firstMarketingAuthorization: { value: "EU/1", searchType: "CONTAINS" },
    announcement: { value: "Meddelade tilläggsskydd", searchType: "EXACT" },
  });
  expect(result).toMatchObject({
    rows: [],
    total_pages: 0,
    more_available: false,
  });
});

test("simple searches send PRV's body and page by hits", async () => {
  const { client, bodies } = fake((body) => ({
    totalHits: 5,
    totalPages: 1,
    hits: 2,
    page: body.page,
    trademarks: [{ a: 1 }, { a: 2 }],
  }));
  const second = await client.searchTrademarks({
    text: " IKEA ",
    page: 1,
    pageSize: 2,
    extra: { classes: null, dossierType: "x" },
  });
  expect(bodies[0]).toEqual({
    page: 1,
    pageSize: 2,
    sortColumn: "filingDate",
    sortOrder: "DESC",
    simpleSearchText: "IKEA",
    dossierType: "x",
  });
  // Python's page + 1 < totalPages said false here, with a third page still to come.
  expect(second).toMatchObject({ total_pages: 3, more_available: true });
  // Only the request matters here; the fake answers with trademark rows.
  await client
    .searchDesigns({ sortColumn: null, sortOrder: null })
    .catch(() => undefined);
  expect(bodies[1]).toEqual({ page: 0, pageSize: 10 });
});

test("malformed responses and server errors are errors", async () => {
  await expect(
    fake(() => ({ unexpected: true })).client.searchPatents(),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  await expect(
    fake(() => ({
      totalHits: 1,
      totalPages: 0,
      page: 0,
      searchPatentDTOS: ["x"],
    })).client.searchPatents(),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  await expect(
    fake(() => ({ message: "Unknown applicationType." }), 400).client.getPatent(
      "SE1",
    ),
  ).rejects.toMatchObject({ code: "INVALID_REQUEST", status: 400 });
  await expect(
    fake(() => ({}), 500).client.searchPatents(),
  ).rejects.toMatchObject({ code: "UPSTREAM_ERROR", status: 500 });
});

test("trademark and design records, as PRV's app reads them", async () => {
  const mark = await prvRecording<{
    data: PrvRow;
    provenance: { source_url: string };
  }>("trademark-record");
  expect(mark.data).toMatchObject({
    applicationNumber: samples.trademark,
    statusEn: expect.any(String),
    classNumbers: expect.any(Array),
  });
  expect(mark.provenance.source_url).toBe(
    `https://api.prv.se/trademarks/applications/${samples.trademark}`,
  );
  const design = await prvRecording<{ data: PrvRow }>("design-record");
  expect(design.data).toMatchObject({
    applicationNumber: samples.design,
    designsEn: expect.any(Array),
  });
  const missing = (await prvRecording("trademark-missing").catch(
    (e) => e,
  )) as Error;
  expect(missing).toMatchObject({ code: "NOT_FOUND", status: 404 });
  expect(missing.message).toBe(
    "PRV found no record: There is no trademark with number 1999-99999.",
  );
  await expect(new PrvClient().getDesign("SE1234")).rejects.toThrow(
    "look like 2025-05038",
  );
});

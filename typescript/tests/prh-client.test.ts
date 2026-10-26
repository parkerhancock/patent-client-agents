import { expect, test } from "bun:test";
import {
  PRH_PATENT_STATUSES,
  PRH_PATENT_TYPES,
  PRH_PUBLICATION_TYPES,
  PrhClient,
  PrhError,
  type PrhRow,
  type PrhSearch,
  prhApplicationNumber,
} from "../packages/client/src/index.js";
import { prhRecording, pythonLists, samples } from "./prh-recordings.js";

const search = (name: string) => prhRecording<PrhSearch>(name);

test("the app's inclusion lists find every match; Python's found a tenth", async () => {
  expect(PRH_PATENT_STATUSES).toHaveLength(117);
  expect(PRH_PATENT_TYPES).toEqual([
    "PatentDossier",
    "PatentDossierUtilityModel",
    "PatentEurope",
    "Spc",
  ]);
  expect(PRH_PUBLICATION_TYPES).toHaveLength(42);
  const full = await search("patents-search");
  const python = await search("patents-search-python-lists");
  expect(full.total_results).toBe(84);
  expect(python.total_results).toBe(8);
  expect(
    pythonLists.dossierStatus.filter(
      (s) => !(PRH_PATENT_STATUSES as readonly string[]).includes(s),
    ),
  ).toEqual([
    "Lapsed",
    "Revoked",
    "Refused",
    "Reinstated",
    "Withdrawn",
    "Granted",
    "Application_pending",
    "Pending",
  ]);
  expect(
    full.rows.every((row) =>
      row.applicationDate?.toString().startsWith("2024-02"),
    ),
  ).toBe(true);
  expect(full).toMatchObject({ capped: false });
  expect(full.provenance.source_url).toBe(
    "https://patenttitietopalvelu.prh.fi/nis-api-gateway-pat/patent",
  );
});

test("trademark, well-known and design searches return PRH's dossier rows", async () => {
  const trademarks = await search("trademarks-search");
  expect(trademarks.total_results).toBe(68);
  expect(trademarks.rows[0]).toMatchObject({
    applicationNumber: expect.any(String),
    trademarkWord: expect.stringMatching(/sisu/i),
    imageUrl: expect.stringMatching(/^\/opendata\/trademark\/image\//),
  });
  const wellKnown = await search("well-known-search");
  expect(wellKnown.rows[0]).toMatchObject({
    trademarkWord: expect.stringContaining("TAFFEL"),
    targetGroup: expect.any(String),
  });
  const designs = await search("designs-search");
  expect(designs.total_results).toBe(7);
  expect(
    designs.rows.every((row) => String(row.applicationDate) >= "2015-01-01"),
  ).toBe(true);
  expect((designs.rows[0]?.designs as PrhRow[] | undefined)?.[0]).toMatchObject(
    {
      dominantViewImageUrl: expect.stringMatching(
        /^\/opendata\/design\/image\//,
      ),
    },
  );
});

test("patent records; an FI prefix is dropped; unknown numbers are NOT_FOUND", async () => {
  const record = await prhRecording<{ data: PrhRow }>("patent-record");
  expect(record.data).toMatchObject({
    applicationNumber: samples.patent,
    registrationNumber: "131976",
    patentTitle: expect.any(Array),
  });
  const prefixed = await prhRecording<{
    data: PrhRow;
    provenance: { source_url: string };
  }>("patent-record-fi-prefix");
  expect(prefixed.provenance.source_url).toBe(
    `https://patenttitietopalvelu.prh.fi/nis-api-gateway-pat/patent/${samples.patent}`,
  );
  const missing = await prhRecording("patent-missing").catch((e) => e);
  expect(missing).toBeInstanceOf(PrhError);
  expect(missing).toMatchObject({ code: "NOT_FOUND", status: 404 });
  expect(prhApplicationNumber(" fi20245203 ")).toBe("20245203");
  expect(() => prhApplicationNumber(" ")).toThrow("required");
});

test("images come back as bytes with their content type", async () => {
  const mark = await prhRecording<{ data: Uint8Array; content_type: string }>(
    "trademark-thumbnail",
  );
  expect(mark.content_type).toBe("image/jpeg");
  expect([...mark.data.slice(0, 2)]).toEqual([0xff, 0xd8]);
  const design = await prhRecording<{ data: Uint8Array; content_type: string }>(
    "design-thumbnail",
  );
  expect(design.content_type).toMatch(/^image\//);
  expect(design.data.byteLength).toBeGreaterThan(100);
});

// ── Synthetic edge cases ─────────────────────────────────────────────

function fake(respond: (request: Request) => Response) {
  const requests: { url: string; body: Record<string, unknown> }[] = [];
  const client = new PrhClient({
    retryLimit: 0,
    fetch: (async (input, init) => {
      const request = new Request(input, init);
      const body =
        request.method === "POST"
          ? ((await request.clone().json()) as Record<string, unknown>)
          : {};
      requests.push({ url: request.url, body });
      return respond(request);
    }) as typeof fetch,
  });
  return { client, requests };
}
const page = (rows: unknown[], total = rows.length) =>
  Response.json({ totalResults: total, results: rows });

test("search bodies carry every field, check dates and refuse unknown fields", async () => {
  const { client, requests } = fake(() => page([{ a: 1 }], 3500));
  const result = await client.searchPatents({
    applicant: " Kone ",
    filingStartDate: "2024-01-01",
  });
  const body = requests[0]?.body ?? {};
  expect(Object.keys(body)).toHaveLength(30);
  expect(body).toMatchObject({
    applicant: "Kone",
    filingStartDate: "2024-01-01",
    basicSearch: "",
    dossierStatus: [...PRH_PATENT_STATUSES],
    patentTypes: [...PRH_PATENT_TYPES],
    publicationTypes: [...PRH_PUBLICATION_TYPES],
  });
  expect(result).toMatchObject({ total_results: 3500, capped: true });
  await expect(client.searchPatents({ patentTypes: [] })).rejects.toThrow(
    "matches nothing",
  );
  await expect(
    client.searchTrademarks({ trademark: "x" } as never),
  ).rejects.toThrow('PRH has no search field "trademark"');
  await expect(
    client.searchDesigns({ applicationStartDate: "01.01.2020" }),
  ).rejects.toThrow("YYYY-MM-DD");
  await client.searchWellKnownTrademarks();
  expect(requests.at(-1)?.url).toBe(
    "https://tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/tmr",
  );
  expect(Object.keys(requests.at(-1)?.body ?? {})).toHaveLength(21);
});

test("malformed responses and non-image bodies are errors", async () => {
  await expect(
    fake(() => Response.json({ results: "x" })).client.searchDesigns(),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  await expect(
    fake(
      () =>
        new Response("<html>", { headers: { "content-type": "text/html" } }),
    ).client.downloadDesignImage("M1.1.1"),
  ).rejects.toThrow("instead of an image");
  await expect(
    fake(() => new Response("", { status: 400 })).client.getPatent("FI1"),
  ).rejects.toMatchObject({ code: "INVALID_REQUEST" });
  await expect(
    new PrhClient().downloadTrademarkImage("T1", null, "huge" as never),
  ).rejects.toThrow();
});

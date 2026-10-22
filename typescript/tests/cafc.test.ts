import { beforeAll, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Client } from "@prefecthq/fastmcp-ts/client";
import {
  CafcClient,
  classifyPatentCase,
  normalizeAppealNumber,
  officialPdfUrl,
} from "../packages/client/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";
import { type CafcRecording, cafcRecording } from "./cafc-recordings.js";

let recording: CafcRecording;
beforeAll(async () => {
  recording = await cafcRecording();
});

test("patent-origin search pages through the recorded date range", () => {
  const { patentOpinions } = recording;
  expect(patentOpinions.total).toBe(253);
  expect(patentOpinions.data).toHaveLength(150);
  for (const opinion of patentOpinions.data) {
    expect(["PTO", "DCT", "ITC", "CFC"]).toContain(opinion.origin);
    expect(opinion.release_date).toMatch(/^2026-0[6-9]-\d{2}$/);
    expect(opinion.pdf_url).toStartWith(
      "https://www.cafc.uscourts.gov/opinions-orders/",
    );
    expect(opinion.case_name_short).not.toContain("[");
  }
  const dates = patentOpinions.data.map((o) => o.release_date ?? "");
  expect(dates).toEqual([...dates].sort().reverse());
  expect(patentOpinions.provenance.source_name).toBe(
    "U.S. Court of Appeals for the Federal Circuit",
  );
});

test("free-text search and a four-digit-year appeal number find the opinion", () => {
  expect(recording.query.data[0]).toMatchObject({
    appeal_number: "24-1945",
    case_name: "GOOGLE LLC v. VALTRUS INNOVATIONS LTD. [OPINION]",
    case_name_short: "GOOGLE LLC v. VALTRUS INNOVATIONS LTD.",
    origin: "PTO",
    document_type: "OPINION",
    precedential_status: "Precedential",
    release_date: "2026-10-19",
  });
  expect(recording.appeal.data.map((o) => o.pdf_url)).toEqual([
    "https://www.cafc.uscourts.gov/opinions-orders/24-1945.OPINION.10-19-2026_2772810.pdf",
  ]);
  expect(recording.pdf.filename).toBe("24-1945.OPINION.10-19-2026_2772810.pdf");
  expect(new TextDecoder().decode(recording.pdf.data.subarray(0, 5))).toBe(
    "%PDF-",
  );
});

test("the classifier matches Python's PatentClassifier exactly", () => {
  const cases = JSON.parse(
    readFileSync(
      join(import.meta.dir, "fixtures", "cafc", "classifier-parity.json"),
      "utf8",
    ),
  ) as {
    case_name: string;
    is_patent_case: boolean;
    confidence: number;
    keywords: string[];
  }[];
  const mismatches = cases.filter((expected) => {
    const actual = classifyPatentCase(expected.case_name);
    return (
      actual.isPatentCase !== expected.is_patent_case ||
      actual.confidence !== expected.confidence ||
      JSON.stringify([...actual.keywords].sort()) !==
        JSON.stringify(expected.keywords)
    );
  });
  expect(mismatches).toEqual([]);
  expect(cases.filter((c) => c.is_patent_case).length).toBeGreaterThan(20);
});

test("appeal numbers normalize to the index's two-digit-year form", () => {
  expect(normalizeAppealNumber("2024-1945")).toBe("24-1945");
  expect(normalizeAppealNumber(" 24-1945 ")).toBe("24-1945");
  expect(normalizeAppealNumber("valtrus")).toBe("valtrus");
});

test("only official opinions-orders PDF URLs are downloadable", () => {
  const good =
    "https://www.cafc.uscourts.gov/opinions-orders/24-1945.OPINION.10-19-2026_2772810.pdf";
  expect(officialPdfUrl(good)?.pathname).toStartWith("/opinions-orders/");
  for (const bad of [
    good.replace("https:", "http:"),
    good.replace("www.", ""),
    `${good}?x=1`,
    good.replace("/opinions-orders/", "/wp-content/"),
    good.replace(".pdf", ".html"),
    "https://user:pw@www.cafc.uscourts.gov/opinions-orders/a.pdf",
    "not a url",
  ])
    expect(officialPdfUrl(bad)).toBeNull();
});

const PAGE = `<html><input type="hidden" id="wdtNonceFrontendServerSide_1" value="0123456789" /></html>`;
const row = (appeal: string) => [
  "10/19/2026",
  appeal,
  "PTO",
  "OPINION",
  `<a sort="A &amp; B v. C [OPINION]" href="/x">A</a>`,
  "Precedential",
  `opinions-orders/${appeal}.pdf`,
];
function fakeSite(respond: (form: URLSearchParams, call: number) => unknown): {
  client: CafcClient;
  pages: () => number;
} {
  let pages = 0;
  let calls = 0;
  const client = new CafcClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = new Request(input, init);
      if (request.method === "GET") {
        pages++;
        return new Response(PAGE, { headers: { "content-type": "text/html" } });
      }
      const form = new URLSearchParams(await request.text());
      return Response.json(respond(form, calls++));
    }) as typeof fetch,
  });
  return { client, pages: () => pages };
}

test("an expired nonce is refreshed once and entities in case names decode", async () => {
  const site = fakeSite((_form, call) =>
    call === 0
      ? -1
      : { recordsFiltered: "1", recordsTotal: "9", data: [row("24-1")] },
  );
  const result = await site.client.search({ maxResults: 5 });
  expect(site.pages()).toBe(2);
  expect(result.data[0]?.case_name_short).toBe("A & B v. C");
});

test("the request carries the date range, origins and query the index expects", async () => {
  let seen: URLSearchParams | undefined;
  const site = fakeSite((form) => {
    seen = form;
    return { recordsFiltered: 0, data: [] };
  });
  await site.client.searchPatentOpinions({
    dateFrom: "2026-01-02",
    dateTo: "2026-03-04",
    maxResults: 10,
  });
  expect(seen?.get("columns[0][search][value]")).toBe("01/02/2026|03/04/2026");
  expect(seen?.get("columns[2][search][value]")).toBe("PTO|DCT|ITC|CFC");
  expect(seen?.get("wdtNonce")).toBe("0123456789");
  expect(seen?.get("length")).toBe("10");
});

test("bad input and inconsistent pages are rejected", async () => {
  const site = fakeSite(() => ({ recordsFiltered: 0, data: [] }));
  await expect(
    site.client.search({ dateTo: "2026-01-01", maxResults: 1 }),
  ).rejects.toThrow("date_to requires date_from");
  await expect(
    site.client.search({
      dateFrom: "2026-02-01",
      dateTo: "2026-01-01",
      maxResults: 1,
    }),
  ).rejects.toThrow("date_from must not be later");
  await expect(
    site.client.search({ dateFrom: "01/02/2026", maxResults: 1 }),
  ).rejects.toThrow("YYYY-MM-DD");
  await expect(site.client.search({ maxResults: 0 })).rejects.toThrow(
    "maxResults",
  );
  const contradictory = fakeSite(() => ({
    recordsFiltered: "1",
    data: [row("24-1"), row("24-2")],
  }));
  await expect(contradictory.client.search({ maxResults: 5 })).rejects.toThrow(
    "contradicts its total count",
  );
  const malformed = fakeSite(() => ({ recordsFiltered: "1", data: [["x"]] }));
  await expect(malformed.client.search({ maxResults: 5 })).rejects.toThrow(
    "malformed",
  );
  await expect(
    site.client.downloadPdf("https://example.com/opinions-orders/a.pdf"),
  ).rejects.toThrow("official CAFC");
});

test("the full toolset serves the CAFC connector tools", async () => {
  const site = fakeSite((form) => {
    const rows = [row("24-1"), row("24-2")].filter((r) =>
      r[1]?.includes(form.get("search[value]") ?? ""),
    );
    const start = Number(form.get("start"));
    return {
      recordsFiltered: String(rows.length),
      data: rows.slice(start, start + Number(form.get("length"))),
    };
  });
  const server = createServer({ clients: { cafc: site.client } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    for (const name of [
      "search_cafc_opinions",
      "search_cafc_patent_opinions",
      "download_cafc_pdf",
    ])
      expect(names).toContain(name);
    const page = (
      await client.callTool<{ items: unknown[]; next_cursor: string | null }>(
        "search_cafc_opinions",
        { limit: 1 },
      )
    ).structuredContent;
    expect(page?.items).toHaveLength(1);
    expect(page?.next_cursor).toBeString();
    await expect(
      client.callTool("download_cafc_pdf", {
        appeal_number: "24-1",
        document_url: "https://www.cafc.uscourts.gov/wp-admin/x.pdf",
      }),
    ).rejects.toThrow("official CAFC");
  } finally {
    await client.close();
    await server.close();
  }
});

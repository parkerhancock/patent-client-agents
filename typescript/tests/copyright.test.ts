import { beforeAll, expect, test } from "bun:test";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { CopyrightClient } from "../packages/client/src/index.js";
import { stubCopyright } from "../packages/mcp/src/copyright.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  type CopyrightRecording,
  copyrightRecording,
  RECORDED_IDS,
} from "./copyright-recordings.js";

let recording: CopyrightRecording;
beforeAll(async () => {
  recording = await copyrightRecording();
});

test("card-catalog hits keep the Python record fields", () => {
  const { keyword } = recording;
  expect(keyword.metadata).toMatchObject({
    hit_count: 11150,
    hit_count_capped: false,
    query: "Mickey Mouse",
  });
  expect(keyword.records).toHaveLength(10);
  expect(keyword.histogram.system_of_origin).toEqual({
    voyager: 8345,
    card_catalog: 2805,
  });
  expect(stubCopyright(keyword.records[0] as never)).toEqual({
    public_records_id: "card_catalog_CC19381945B_394000-395999.1200",
    title: "Mickey Mouse Magazine",
    registration_number: "B 395200",
    registration_class: "newspaper_or_periodical",
    type_of_record: "registration",
    type_of_work: "periodical",
    claimant: "K. K. Publications, Inc.",
    representative_date: "1938-11-12",
  });
  expect(keyword.provenance.source_name).toBe(
    "U.S. Copyright Office — Public Records",
  );
});

test("post-1978 registrations and recordations fill title, number and claimant", () => {
  const families = new Set(
    recording.title.records.map(
      (r) => `${r.system_of_origin}/${r.type_of_record}`,
    ),
  );
  expect([...families].sort()).toEqual([
    "siebel/registration",
    "voyager/recordation",
    "voyager/registration",
  ]);
  for (const record of recording.title.records) {
    expect(record.title_of_work.length).toBeGreaterThan(0);
    expect(record.copyright_number_for_display).not.toBe("");
    if (record.type_of_record === "registration") {
      expect(record.claimant.length).toBeGreaterThan(0);
      expect(record.registration_class.length).toBe(1);
    }
  }
  const voyager = recording.voyager.record;
  expect(voyager).toMatchObject({
    public_records_id: RECORDED_IDS.voyager,
    title_of_work: ["Steamboat Willie Fotonovel."],
    registration_number: ["TX0009411109"],
    registration_class: ["TX"],
    claimants: [{ claimant_full_name: "Steven Joseph Abramson," }],
    first_published_date: ["2024-05-24"],
    all_type_of_work: ["text"],
    // Upstream fields outside the Python model are kept.
    registration_date: "2024-06-24",
  });
});

test("recordations report the capped hit count and get matches ids exactly", () => {
  expect(recording.name.metadata).toMatchObject({
    hit_count: 50000,
    hit_count_capped: true,
  });
  expect(recording.name.records.map((r) => r.type_of_record)).toEqual([
    "recordation",
    "recordation",
  ]);
  expect(recording.name.records[0]?.party_1).toEqual([
    { names: "WALT DISNEY EMEA PRODUCTIONS LIMITED" },
  ]);
  expect(recording.card.record?.link_to_image_url).toHaveLength(2);
  expect(recording.card.record?.public_records_id).toBe(RECORDED_IDS.card);
  expect(recording.missing.record).toBeNull();
});

function fakeApi(respond: (url: URL) => Response = () => emptyPage()) {
  const urls: URL[] = [];
  const client = new CopyrightClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(new Request(input, init).url);
      urls.push(url);
      return respond(url);
    }) as typeof fetch,
  });
  return { client, urls };
}
const emptyPage = () =>
  Response.json({ metadata: { hit_count: 0, histogram: {} }, data: [] });
const hit = (id: string) => ({
  score: 1,
  hit: {
    public_records_id: id,
    title_concatenated: `Title ${id}`,
    registration_number: `TX${id}`,
    registration_class: "TX",
    type_of_record: "registration",
    claimants_list: [{ claimant_full_name: "Someone" }],
  },
});

test("requests carry the Python parameters and bad input never reaches the API", async () => {
  const api = fakeApi();
  await api.client.search({
    query: " Mickey ",
    field: "name",
    page: 3,
    pageSize: 25,
  });
  expect(Object.fromEntries(api.urls[0]?.searchParams ?? [])).toEqual({
    query: "Mickey",
    field_type: "name",
    page_number: "3",
    records_per_page: "25",
    sort_order: "asc",
    model: "",
  });
  for (const [search, message] of [
    [{ query: " " }, "query"],
    [{ query: "x", field: "author" }, "field"],
    [{ query: "x", page: 0 }, "page"],
    [{ query: "x", pageSize: 0 }, "page_size"],
    [{ query: "x", pageSize: 501 }, "page_size"],
    [{ query: "x", page: 5001, pageSize: 10 }, "50000"],
  ] as const)
    await expect(api.client.search(search as never)).rejects.toThrow(message);
  expect(api.urls).toHaveLength(1);
  const malformed = fakeApi(() => Response.json({ data: [] }));
  await expect(malformed.client.search({ query: "x" })).rejects.toThrow(
    "coverage is unknown",
  );
});

test("the full toolset serves search_copyright and get_copyright_record", async () => {
  const api = fakeApi((url) => {
    const query = url.searchParams.get("query") ?? "";
    const rows = ["1", "2"].map(hit);
    return Response.json({
      metadata: { hit_count: 2 },
      data:
        query === "x"
          ? rows.slice(0, Number(url.searchParams.get("records_per_page")))
          : rows.filter((r) => r.hit.public_records_id === query),
    });
  });
  const server = createServer({ clients: { copyright: api.client } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names).toContain("search_copyright");
    expect(names).toContain("get_copyright_record");
    const search = (
      await client.callTool<{
        items: Record<string, unknown>[];
        more_available: boolean;
      }>("search_copyright", { query: "x", page_size: 1 })
    ).structuredContent;
    expect(search?.items[0]).toEqual({
      public_records_id: "1",
      title: "Title 1",
      registration_number: "TX1",
      registration_class: "TX",
      type_of_record: "registration",
      type_of_work: null,
      claimant: "Someone",
      representative_date: null,
    });
    expect(search?.more_available).toBe(true);
    const got = (
      await client.callTool<{ items: unknown[]; not_found: string[] }>(
        "get_copyright_record",
        { public_records_id: ["2", "3"] },
      )
    ).structuredContent;
    expect(got?.items).toHaveLength(1);
    expect(got?.not_found).toEqual(["3"]);
  } finally {
    await client.close();
    await server.close();
  }
});

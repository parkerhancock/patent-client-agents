import { afterAll, beforeAll, expect, test } from "bun:test";
import { CopyrightClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { createServer } from "../packages/mcp/src/index.js";

/** Synthetic public records API: never touches the network. */
const requests: URL[] = [];
const record = (id: string, extra: Record<string, unknown> = {}) => ({
  score: 2.5,
  hit: {
    public_records_id: id,
    title_of_work: [`Work ${id}`],
    registration_number: [`A ${id}`],
    copyright_number_for_display: `A ${id}`,
    type_of_record: "registration",
    registration_status: "published",
    registration_class: ["book"],
    claimant: ["Claimant Co."],
    claimants: [{ claimant_full_name: "Claimant Co." }],
    cc_type_of_work: "book",
    system_of_origin: "card_catalog",
    representative_date: "1938-10-11",
    drawer_name: "upstream-only",
    ...extra,
  },
});
const copyright = new CopyrightClient({
  retryLimit: 0,
  fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(new Request(input, init).url);
    requests.push(url);
    const query = url.searchParams.get("query");
    const rows =
      query === "mickey"
        ? [record("card_1"), record("card_2")]
        : query === "card_1" || query === "card_2"
          ? [record("card_1"), record("card_2")]
          : [];
    return Response.json({
      metadata: { hit_count: query === "mickey" ? 25 : rows.length },
      data: rows,
    });
  }) as typeof fetch,
});

type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  more_available: boolean;
  not_found?: string[];
};
let server: FastMCP;
let client: Client;
const call = async (args: Record<string, unknown>) =>
  (await client.callTool<Envelope>("copyright", args))
    .structuredContent as Envelope;

beforeAll(async () => {
  server = createServer({ toolset: "curated", clients: { copyright } });
  client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
});
afterAll(async () => {
  await client.close();
  await server.close();
});

test("copyright(mode='search') returns lean stubs, or Python fields with full", async () => {
  const lean = await call({
    mode: "search",
    query: "mickey",
    field: "title",
    page: 2,
  });
  expect(requests.at(-1)?.searchParams.get("field_type")).toBe("title");
  expect(requests.at(-1)?.searchParams.get("page_number")).toBe("2");
  expect(lean.summary).toBe(
    "U.S. Copyright Office — `mickey` (by title): 2 of 25 hits.",
  );
  expect(lean.more_available).toBe(true);
  expect(lean.items[0]).toEqual({
    public_records_id: "card_1",
    title: "Work card_1",
    registration_number: "A card_1",
    registration_class: "book",
    type_of_record: "registration",
    type_of_work: "book",
    claimant: "Claimant Co.",
    representative_date: "1938-10-11",
  });
  const full = await call({ mode: "search", query: "mickey", full: true });
  expect(full.items[0]).toMatchObject({
    score: 2.5,
    claimant: ["Claimant Co."],
  });
  expect(full.items[0]).not.toHaveProperty("drawer_name");
});

test("copyright(mode='get') fetches full records and names missing ids", async () => {
  const one = await call({ mode: "get", public_records_id: "card_2" });
  expect(one.items).toHaveLength(1);
  expect(one.items[0]).toMatchObject({
    public_records_id: "card_2",
    drawer_name: "upstream-only",
  });
  expect(one.summary).toStartWith("**U.S. Copyright registration card_2**");
  const many = await call({
    mode: "get",
    public_records_id: ["card_1", "nope"],
  });
  expect(many.items.map((item) => item.public_records_id)).toEqual(["card_1"]);
  expect(many.not_found).toEqual(["nope"]);
  expect(many.summary).toBe(
    "Fetched 1 of 2 U.S. Copyright records. Not found: nope.",
  );
  const missing = await call({ mode: "get", public_records_id: "nope" });
  expect(missing.items).toEqual([]);
  expect(missing.summary).toBe("U.S. Copyright record nope — not found.");
});

test("copyright rejects missing routing keys and bad fields before any request", async () => {
  const before = requests.length;
  await expect(
    client.callTool("copyright", { mode: "search" }),
  ).rejects.toThrow("requires query");
  await expect(client.callTool("copyright", { mode: "get" })).rejects.toThrow(
    "requires public_records_id",
  );
  await expect(
    client.callTool("copyright", {
      mode: "search",
      query: "x",
      field: "author",
    }),
  ).rejects.toThrow("Invalid field");
  expect(requests.length).toBe(before);
});

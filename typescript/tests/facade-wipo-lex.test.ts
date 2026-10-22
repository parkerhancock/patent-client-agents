import { afterAll, beforeAll, expect, test } from "bun:test";
import { Client } from "@prefecthq/fastmcp-ts/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { createServer } from "../packages/mcp/src/index.js";
import { fixtureSite } from "./wipo-lex-recordings.js";

type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found?: string[];
  provenance: { source_name: string; source_url: string };
};
let server: FastMCP;
let client: Client;
let site: ReturnType<typeof fixtureSite>;
const call = async (name: string, args: Record<string, unknown>) =>
  (await client.callTool<Envelope>(name, args)).structuredContent as Envelope;

beforeAll(async () => {
  site = fixtureSite();
  server = createServer({
    toolset: "curated",
    clients: { wipoLex: site.client },
  });
  client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
});
afterAll(async () => {
  await client.close();
  await server.close();
});

test("search_wipo_lex_legislation forwards every filter and returns lean stubs", async () => {
  site.requests.length = 0;
  const lean = await call("search_wipo_lex_legislation", {
    country_codes: ["CA"],
    subject_matter: [1],
    type_of_text: [205],
    keywords: "patent",
    include_historical: true,
  });
  expect(site.requests[0]?.search).toBe(
    "?countryOrgs=CA&subjectMatter=1&typeOfText=205&keywords=patent&last=false",
  );
  expect(lean.summary).toBe(
    "WIPO Lex legislation — `patent` countries=CA subjects=1 types=205: 11 hits. Includes historical and supplemental texts.",
  );
  expect(lean.items[0]).toEqual({
    legislation_id: "23293",
    title: "Patent Act, (R.S.C., 1985, c. P-4, amended January 1, 2025)",
    url: "https://www.wipo.int/wipolex/en/legislation/details/23293",
  });
  expect(lean.provenance.source_name).toBe("WIPO Lex");
  const full = await call("search_wipo_lex_legislation", {
    subject_matter: [9],
    start_date: "2020-01-01",
    end_date: "2020-12-31",
    full: true,
  });
  expect(site.requests[1]?.search).toBe(
    "?subjectMatter=9&sDate=01%2F01%2F2020&eDate=31%2F12%2F2020&last=true",
  );
  expect(full.items).toHaveLength(11);
  const empty = await call("search_wipo_lex_legislation", {
    keywords: "nothing",
  });
  expect(empty.items).toEqual([]);
  await expect(
    client.callTool("search_wipo_lex_legislation", {
      country_codes: ["CA"],
      start_date: "2020-01-01",
    }),
  ).rejects.toThrow("ignores start_date/end_date");
});

test("get_wipo_lex_legislation takes one ID or a list", async () => {
  const one = await call("get_wipo_lex_legislation", {
    legislation_id: "23766",
  });
  expect(one.summary).toBe(
    "**WIPO Lex 23766** — Patents Ordinance\nJurisdiction: Hong Kong, China. 2 attachment(s).",
  );
  expect(one.items[0]).toMatchObject({
    legislation_id: "23766",
    url: "https://www.wipo.int/wipolex/en/legislation/details/23766",
  });
  expect(one.not_found).toEqual([]);
  const many = await call("get_wipo_lex_legislation", {
    legislation_id: ["23293", " 1 ", "23766"],
  });
  expect(many.items.map((i) => i.legislation_id)).toEqual(["23293", "23766"]);
  expect(many.not_found).toEqual(["1"]);
  expect(many.summary).toBe(
    "Fetched 2 of 3 WIPO Lex legislation entries. Not found: 1.",
  );
  await expect(
    client.callTool("get_wipo_lex_legislation", { legislation_id: "1" }),
  ).rejects.toThrow("no legislation entry 1");
});

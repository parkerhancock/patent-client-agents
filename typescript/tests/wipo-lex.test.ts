import { beforeAll, expect, test } from "bun:test";
import { Client } from "@prefecthq/fastmcp-ts/client";
import {
  parseWipoLexLegislation,
  parseWipoLexSearch,
} from "../packages/client/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  fixtureSite,
  type WipoLexRecording,
  wipoLexFixture,
  wipoLexRecording,
} from "./wipo-lex-recordings.js";

let recording: WipoLexRecording;
beforeAll(async () => {
  recording = await wipoLexRecording();
});

test("the recorded searches return latest versions by default and every version on request", () => {
  expect(recording.latest.total).toBe(1);
  expect(recording.latest.data).toEqual([
    {
      legislation_id: "23293",
      title: "Patent Act, (R.S.C., 1985, c. P-4, amended January 1, 2025)",
      url: "https://www.wipo.int/wipolex/en/legislation/details/23293",
    },
  ]);
  expect(recording.latest.query_url).toEndWith(
    "?countryOrgs=CA&subjectMatter=1&typeOfText=205&last=true",
  );
  expect(recording.historical.total).toBe(11);
  expect(recording.historical.data).toHaveLength(11);
  expect(recording.historical.data.map((h) => h.legislation_id)).toContain(
    "23293",
  );
  expect(recording.historical.query_url).toEndWith("&last=false");
  expect(recording.dated.total).toBe(13);
  expect(recording.dated.query_url).toContain(
    "sDate=01%2F01%2F2020&eDate=31%2F12%2F2020",
  );
  expect(recording.latest.provenance.source_name).toBe("WIPO Lex");
});

test("the recorded detail page and a missing ID", () => {
  const { files, ...detail } = recording.patentAct;
  expect(detail).toEqual({
    legislation_id: "23293",
    title: "Patent Act",
    jurisdiction: "Canada",
    summary:
      "Canada - Year of Version: 2025 -  Assented: January 1, 1985 - Main IP Laws - Patents (Inventions)",
    url: "https://www.wipo.int/wipolex/en/legislation/details/23293",
  });
  expect(files.map((f) => [f.label, f.mime_type])).toEqual([
    ["Patent Act", "application/pdf"],
    ["Loi sur les brevets", "application/pdf"],
  ]);
  for (const file of files) {
    expect(file.url).toStartWith(
      "https://wipolex-res.wipo.int/edocs/lexdocs/laws/",
    );
    expect(file.expires_at).toMatch(/^2026-10-22T/);
  }
  expect(recording.missing).toEqual({ code: "NOT_FOUND", status: 404 });
});

test("archived result pages: laws only, treaties only and empty", () => {
  const all = parseWipoLexSearch(
    wipoLexFixture("search-ca-patents-historical"),
  );
  expect(all.total).toBe(11);
  expect(new Set(all.hits.map((h) => h.legislation_id)).size).toBe(11);
  // Treaty and judgment rows on the same page are not legislation.
  for (const hit of all.hits)
    expect(hit.url).toMatch(/\/wipolex\/en\/legislation\/details\/\d+$/);
  expect(parseWipoLexSearch(wipoLexFixture("search-treaties-only"))).toEqual({
    hits: [],
    total: 0,
  });
  expect(parseWipoLexSearch(wipoLexFixture("search-empty"))).toEqual({
    hits: [],
    total: 0,
  });
});

test("a jurisdiction with a comma stays whole", () => {
  const detail = parseWipoLexLegislation(
    wipoLexFixture("details-23766"),
    "23766",
  );
  // Python's rsplit gives title "Patents Ordinance, Hong Kong" and jurisdiction "China".
  expect(detail.title).toBe("Patents Ordinance");
  expect(detail.jurisdiction).toBe("Hong Kong, China");
  expect(detail.files.map((f) => f.label)).toEqual([
    "Patents Ordinance",
    "專利條例",
  ]);
});

test("unreadable or inconsistent pages fail loudly", () => {
  const page = wipoLexFixture("search-ca-patents-historical");
  expect(() =>
    parseWipoLexSearch("<html><body>Maintenance</body></html>"),
  ).toThrow("without a legislation count");
  const dropped = page.replace(
    /<a href="\/wipolex\/en\/legislation\/details\/23293">[\s\S]*?<\/a>/,
    "",
  );
  expect(() => parseWipoLexSearch(dropped)).toThrow("reports 11 laws but 10");
  expect(() =>
    parseWipoLexLegislation("<html><head></head></html>", "1"),
  ).toThrow("has no title");
});

test("requests carry the form's parameters and bad input is rejected first", async () => {
  const site = fixtureSite();
  await site.client.search({
    countryCodes: ["ca", "EU"],
    subjectMatter: [1, 9],
    typeOfText: [205],
    keywords: '"trade secret"',
  });
  await site.client.search({
    subjectMatter: [9],
    startDate: "2020-01-01",
    includeHistorical: true,
  });
  expect(site.requests.map((u) => u.search)).toEqual([
    "?countryOrgs=CA&countryOrgs=EU&subjectMatter=1&subjectMatter=9&typeOfText=205&keywords=%22trade+secret%22&last=true",
    "?subjectMatter=9&sDate=01%2F01%2F2020&last=false",
  ]);
  const rejects = async (promise: Promise<unknown>, message: string) =>
    expect(promise).rejects.toThrow(message);
  await rejects(site.client.search({}), "at least one WIPO Lex filter");
  await rejects(site.client.search({ subjectMatter: [99] }), "subject_matter");
  await rejects(site.client.search({ typeOfText: [1] }), "type_of_text");
  await rejects(site.client.search({ countryCodes: ["C-A"] }), "jurisdiction");
  await rejects(
    site.client.search({ countryCodes: ["CA"], startDate: "2020-01-01" }),
    "ignores start_date/end_date",
  );
  await rejects(
    site.client.search({ subjectMatter: [1], startDate: "2020-1-1" }),
    "YYYY-MM-DD",
  );
  await rejects(
    site.client.search({
      subjectMatter: [1],
      startDate: "2021-01-01",
      endDate: "2020-01-01",
    }),
    "not be later",
  );
  await rejects(site.client.get("../x"), "numeric");
  expect(site.requests).toHaveLength(2);
});

test("the full toolset serves the WIPO Lex tools", async () => {
  const site = fixtureSite();
  const server = createServer({ clients: { wipoLex: site.client } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names).toContain("search_wipo_lex_legislation");
    expect(names).toContain("get_wipo_lex_legislation");
    const search = (
      await client.callTool<{ items: Record<string, unknown>[] }>(
        "search_wipo_lex_legislation",
        { country_codes: ["CA"], subject_matter: [1] },
      )
    ).structuredContent;
    expect(search?.items).toHaveLength(11);
    expect(Object.keys(search?.items[0] ?? {})).toEqual([
      "legislation_id",
      "title",
      "url",
    ]);
    const get = (
      await client.callTool<{
        items: Record<string, unknown>[];
        not_found: string[];
      }>("get_wipo_lex_legislation", {
        legislation_id: ["23293", "404404"],
      })
    ).structuredContent;
    expect(get?.items.map((i) => i.jurisdiction)).toEqual(["Canada"]);
    expect(get?.not_found).toEqual(["404404"]);
  } finally {
    await client.close();
    await server.close();
  }
});

import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { parseDocument } from "../packages/client/src/google-patents/dom.js";
import {
  buildGoogleQuery,
  extractClaims,
  type GooglePatent,
  GooglePatentsClient,
  GooglePatentsError,
  GooglePatentsRateLimiter,
  normalizeGooglePatentNumber,
  parseGoogleSearch,
  resolveExpiration,
} from "../packages/client/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";
import { googleRecording } from "./google-patents-recordings.js";

const fixture = async (name: string) =>
  gunzipSync(
    await readFile(join(import.meta.dir, "fixtures", "google-patents", name)),
  ).toString();
type Result<T> = { data: T; provenance: { source_url: string } };

test("real US page: metadata, claims, citations, family, events and figures", async () => {
  const { data, provenance } =
    await googleRecording<Result<GooglePatent>>("patent-us");
  expect(provenance.source_url).toBe(
    "https://patents.google.com/patent/US7654321B2/en",
  );
  expect(data).toMatchObject({
    patent_number: "US7654321B2",
    current_assignee: "Schlumberger Technology Corp",
    priority_date: "2006-12-27",
    grant_date: "2010-02-02",
    expiration_date: "2026-12-27",
    expiration_estimated: false,
    source_language: null,
  });
  expect(data.title).toStartWith("Formation fluid sampling apparatus");
  expect(data.claims).toHaveLength(26);
  expect(
    data.claims.filter((c) => c.type === "independent").map((c) => c.number),
  ).toEqual(["1", "13", "14", "15", "21", "24"]);
  expect(data.claims[1]).toMatchObject({
    number: "2",
    depends_on: "1",
    type: "dependent",
  });
  expect(data.structured_limitations["1"]?.[0]).toEndWith("comprising:");
  expect(data.cited_patents).toHaveLength(30);
  expect(data.citing_patents).toHaveLength(42);
  expect(data.legal_events.length).toBeGreaterThan(10);
  expect(data.figures).toHaveLength(9);
  expect(data.figures[0]?.full_image_url).toStartWith(
    "https://patentimages.storage.googleapis.com/",
  );
  expect(data.description_markdown?.length).toBeGreaterThan(10_000);
});

test("real JP page: translation, original text and estimated expiration", async () => {
  const { data } = await googleRecording<Result<GooglePatent>>("patent-jp");
  expect(data.source_language).toBe("ja");
  expect(data.expiration_estimated).toBe(true);
  expect(data.expiration_date).toBe("2035-09-29");
  const first = data.claims[0];
  expect(first?.text).toStartWith("A cell culture device");
  expect(first?.original_text).toMatch(/[぀-ヿ一-龯]/);
  // Limitations hold the translation only; the original stays separate.
  expect(data.structured_limitations["1"]?.join(" ")).not.toMatch(/[぀-ヿ]/);
  expect(data.original_limitations["1"]?.[0]).toMatch(/[぀-ヿ一-龯]/);
  expect(data.claims.find((c) => c.number === "3")?.depends_on).toBe("2");
});

test("a real Google 503 becomes RATE_LIMITED with a retry-after hint", async () => {
  expect(await googleRecording("throttled")).toEqual({
    error: "RATE_LIMITED",
    retryAfter: 90,
  });
});

test("recordings and fixtures carry no embedded Google API keys", async () => {
  const { readdir } = await import("node:fs/promises");
  const cassettes = join(import.meta.dir, "cassettes");
  for (const name of (await readdir(cassettes)).filter((n) =>
    n.startsWith("google-patents-"),
  ))
    expect(await readFile(join(cassettes, name), "utf8")).not.toMatch(
      /AIza[0-9A-Za-z_-]{35}/,
    );
  const fixtures = join(import.meta.dir, "fixtures", "google-patents");
  for (const name of (await readdir(fixtures)).filter((n) => n.endsWith(".gz")))
    expect(await fixture(name)).not.toMatch(/AIza[0-9A-Za-z_-]{35}/);
});

test("missing publications are NOT_FOUND, not retried or empty", async () => {
  expect(await googleRecording<{ error: string }>("not-found")).toEqual({
    error: "NOT_FOUND",
  });
});

test("archived pages parse without network", async () => {
  const ep = GooglePatentsClient.parsePatent(
    await fixture("EP3456789A1.html.gz"),
    "EP3456789A1",
  );
  // EP multiple dependency ("one or more of the preceding claims") counts as dependent.
  expect(
    ep.claims.filter((c) => c.type === "independent").map((c) => c.number),
  ).toEqual(["1"]);
  const wo = GooglePatentsClient.parsePatent(
    await fixture("WO2020123456A1.html.gz"),
    "WO2020123456A1",
  );
  expect(wo.grant_date).toBe("");
  expect(wo.claims).toHaveLength(19);
  const cn = GooglePatentsClient.parsePatent(
    await fixture("CN110000000A.html.gz"),
    "CN110000000A",
  );
  expect(cn.claims.slice(1, 4).map((c) => c.depends_on)).toEqual([
    "1",
    "1",
    "1",
  ]);
  expect(() =>
    GooglePatentsClient.parsePatent("<html><body></body></html>", "US1A"),
  ).toThrow(GooglePatentsError);
});

test("search parsing matches the archived response", async () => {
  const payload = JSON.parse(await fixture("search-lithium.json.gz"));
  const parsed = parseGoogleSearch(payload, "q=lithium");
  expect(parsed.total_results).toBe(123810);
  expect(parsed.results).toHaveLength(10);
  expect(parsed.results[0]).toMatchObject({ result_type: "patent" });
  expect(parsed.results[0]?.publication_number).toMatch(/^US/);
  expect(parsed.results[0]?.detail_url).toStartWith(
    "https://patents.google.com/patent/",
  );
  expect(() => parseGoogleSearch({ nope: true }, "q")).toThrow(
    GooglePatentsError,
  );
});

test("number normalization and query building", () => {
  expect(normalizeGooglePatentNumber(" us 7,654,321 b2 ")).toBe("US7654321B2");
  expect(normalizeGooglePatentNumber("7654321")).toBe("US7654321");
  expect(normalizeGooglePatentNumber("US2023012345A1")).toBe("US20230012345A1");
  // Pre-2004 two-digit-year WO numbers: WO 00/12345 and WO 99/12345.
  expect(normalizeGooglePatentNumber("WO0012345A1")).toBe("WO2000012345A1");
  expect(normalizeGooglePatentNumber("WO9912345A1")).toBe("WO1999012345A1");
  expect(() => normalizeGooglePatentNumber("../etc")).toThrow();
  expect(
    buildGoogleQuery({
      keywords: ["fuel cell", "a&b"],
      cpcCodes: ["H01M8/04"],
      countries: ["us"],
      after: "2015-01-31",
      before: "2020-01-01",
      dateType: "filing",
      pageSize: 25,
      page: 3,
      sort: "new",
    }),
  ).toBe(
    "q=fuel+cell&q=a%26b&cpc=H01M8%2f04&country=US&after=filing:20150131&before=filing:20200101&num=25&sort=new&page=2",
  );
  expect(() => buildGoogleQuery({})).toThrow("at least one search term");
  expect(() =>
    buildGoogleQuery({ keywords: ["x"], after: "2020/01/01" }),
  ).toThrow();
});

test("expiration fallback estimates priority + 20 years, clamping Feb 29", () => {
  expect(resolveExpiration("2030-01-01", "2010-01-01")).toEqual({
    expiration_date: "2030-01-01",
    expiration_estimated: false,
  });
  expect(resolveExpiration("", "2012-02-29")).toEqual({
    expiration_date: "2032-02-29",
    expiration_estimated: true,
  });
  expect(resolveExpiration("", "2016-02-29").expiration_date).toBe(
    "2036-02-29",
  );
  expect(resolveExpiration("", "2004-02-29").expiration_date).toBe(
    "2024-02-29",
  );
  expect(resolveExpiration("", "2001-03-01").expiration_date).toBe(
    "2021-03-01",
  );
  expect(resolveExpiration("", "1999-02-28").expiration_date).toBe(
    "2019-02-28",
  );
  expect(resolveExpiration("", null)).toEqual({
    expiration_date: "",
    expiration_estimated: false,
  });
});

test("the limiter spaces requests and fails fast during a cooldown", async () => {
  const limiter = new GooglePatentsRateLimiter(40, 5_000);
  const started = Date.now();
  await limiter.acquire();
  await limiter.acquire();
  await limiter.acquire();
  expect(Date.now() - started).toBeGreaterThanOrEqual(75);
  limiter.cooldown();
  const error = await limiter.acquire().catch((e) => e);
  expect(error).toMatchObject({ code: "RATE_LIMITED" });
  expect(error.retryAfterSeconds).toBeGreaterThan(0);
});

test("503s and HTML search bodies start the cooldown; later calls fail without a request", async () => {
  let requests = 0;
  const client = new GooglePatentsClient({
    rateLimiter: new GooglePatentsRateLimiter(0, 60_000),
    fetch: (async () => {
      requests++;
      return new Response("busy", { status: 503 });
    }) as unknown as typeof fetch,
  });
  expect(await client.getPatent("US1A").catch((e) => e.code)).toBe(
    "RATE_LIMITED",
  );
  expect(await client.getPatent("US2A").catch((e) => e.code)).toBe(
    "RATE_LIMITED",
  );
  expect(requests).toBe(1);
  const html = new GooglePatentsClient({
    rateLimiter: new GooglePatentsRateLimiter(0, 60_000),
    fetch: (async () =>
      new Response("<html>sorry</html>")) as unknown as typeof fetch,
  });
  expect(await html.search({ keywords: ["x"] }).catch((e) => e.code)).toBe(
    "RATE_LIMITED",
  );
});

test("PDFs come only from Google's image host and must be PDFs", async () => {
  const page = (pdf: string) =>
    `<html><head><meta name="DC.title" content="T"></head><body><a itemprop="pdfLink" href="${pdf}">PDF</a></body></html>`;
  const make = (pdf: string, body: string) =>
    new GooglePatentsClient({
      rateLimiter: new GooglePatentsRateLimiter(0, 1),
      fetch: (async (input: RequestInfo | URL, init?: RequestInit) =>
        new URL(new Request(input, init).url).hostname === "patents.google.com"
          ? new Response(page(pdf))
          : new Response(body)) as unknown as typeof fetch,
    });
  expect(
    await make("https://evil.example/x.pdf", "%PDF-1.4")
      .downloadPdf("US1A")
      .catch((e) => e.code),
  ).toBe("INVALID_RESPONSE");
  expect(
    await make("https://patentimages.storage.googleapis.com/x.pdf", "<html>")
      .downloadPdf("US1A")
      .catch((e) => e.code),
  ).toBe("INVALID_RESPONSE");
  const ok = await make(
    "https://patentimages.storage.googleapis.com/x.pdf",
    "%PDF-1.4 x",
  ).downloadPdf("US1A");
  expect(new TextDecoder().decode(ok.data.slice(0, 5))).toBe("%PDF-");
});

test("claim-text elements do not repeat nested limitations", () => {
  const document = parseDocument(
    `<section itemprop="claims"><claim num="00001"><claim-text>1. A device comprising:<claim-text>a part; and</claim-text><claim-text>a second part.</claim-text></claim-text></claim></section>`,
  );
  expect(extractClaims(document).structured_limitations["1"]).toEqual([
    "A device comprising:",
    "a part; and",
    "a second part.",
  ]);
});

test("Google Patents MCP tools project views and report missing batch members", async () => {
  const html = await fixture("US7654321B2.html.gz");
  const googlePatents = new GooglePatentsClient({
    rateLimiter: new GooglePatentsRateLimiter(0, 1),
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) =>
      new URL(new Request(input, init).url).pathname.includes("US404")
        ? new Response("", { status: 404 })
        : new Response(html)) as unknown as typeof fetch,
  });
  const server = createServer({ clients: { googlePatents } });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  type Envelope = { items: Record<string, unknown>[]; not_found?: string[] };
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names).toEqual(
      expect.arrayContaining([
        "search_google_patents",
        "get_google_patent",
        "download_google_patent_pdf",
      ]),
    );
    const summary = await client.callTool<Envelope>("get_google_patent", {
      patent_numbers: ["US7654321B2", "US404B1"],
    });
    expect(summary.structuredContent?.items[0]).toMatchObject({
      patent_number: "US7654321B2",
      grant_date: "2010-02-02",
    });
    expect(summary.structuredContent?.items[0]).not.toHaveProperty("claims");
    expect(summary.structuredContent?.not_found).toEqual(["US404B1"]);
    const claims = await client.callTool<Envelope>("get_google_patent", {
      patent_numbers: "US7654321B2",
      view: "claims",
    });
    expect(
      Object.keys(claims.structuredContent?.items[0] ?? {}).sort(),
    ).toEqual([
      "claims",
      "original_limitations",
      "patent_number",
      "structured_limitations",
    ]);
    await expect(
      client.callTool("get_google_patent", { patent_numbers: "US404B1" }),
    ).rejects.toThrow("not found");
  } finally {
    await client.close();
    await server.close();
  }
});

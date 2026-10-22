// Runs the compiled client (packages/client/dist) under Node, outside Bun.
// Usage: bun run build && node scripts/smoke-node.mjs
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { gunzipSync, zstdCompressSync } from "node:zlib";
import {
  DpmaStatutesClient,
  EpcClient,
  EpoFeesClient,
  EpoOpsClient,
  GooglePatentsClient,
  MoppClient,
  MpepClient,
  TmepClient,
  TwTradeSecretsClient,
  UpcStatutesClient,
} from "@patent-client-agents/client";

const fixture = (path) => new URL(`../tests/fixtures/${path}`, import.meta.url);
const results = {};

// Corpus by path (server file adapter) and by bytes (the browser route).
const epcByPath = new EpcClient({
  corpusPath: fixture("epo-legal/epc.db").pathname,
});
const article = await epcByPath.getSection("Article 54");
assert.match(article.html, /<main/);
results.epc_path = article.citation ?? article.href;
const epcBytes = new EpcClient({
  source: new Uint8Array(await readFile(fixture("epo-legal/epc.db"))),
});
results.epc_bytes_hits = (
  await epcBytes.search({ query: "patent", limit: 2 })
).hits.length;
assert.ok(results.epc_bytes_hits > 0);

// Dictionary-compressed cells, then a whole-file Zstandard artifact passed as bytes.
const mpep = new MpepClient({
  corpusPath: fixture("mpep/compressed.db").pathname,
});
const first = (await mpep.search({ query: "patent", limit: 1 })).hits[0];
assert.ok(first);
results.mpep_dictionary_cell =
  (await mpep.getSection(first.href)).html.length > 0;
const zst = new MpepClient({
  source: new Uint8Array(
    zstdCompressSync(await readFile(fixture("mpep/plain.db"))),
  ),
});
const zstStatus = await zst.getCorpusStatus();
assert.equal(zstStatus.available, true);
results.mpep_whole_file = zstStatus.compression;
const upc = new UpcStatutesClient({
  source: new Uint8Array(
    zstdCompressSync(await readFile(fixture("upc-statutes/upc_statutes.db"))),
  ),
});
results.upc_instrument = (await upc.getInstrument("statute")).instrument;
assert.equal(results.upc_instrument, "upca");
const dpma = new DpmaStatutesClient({
  source: new Uint8Array(
    zstdCompressSync(await readFile(fixture("dpma-statutes/dpma_statutes.db"))),
  ),
});
results.dpma_section = (
  await dpma.getSectionByCitation("§ 14 MarkenG")
).statute;
assert.equal(results.dpma_section, "MarkenG");
const tmep = new TmepClient({
  source: new Uint8Array(await readFile(fixture("tmep/tmep.db"))),
});
results.tmep_section = (await tmep.getSection("1207.01")).href;
assert.equal(results.tmep_section, "TMEP-1200d1e5044.html");
const mopp = new MoppClient({
  source: new Uint8Array(await readFile(fixture("ukipo-mopp/mopp.db"))),
});
results.mopp_section = (await mopp.getSection("4a")).href;
assert.equal(
  results.mopp_section,
  "-section-4a-methods-of-treatment-or-diagnosis",
);
// Bundled text indexed into in-memory SQLite; no artifact.
const tw = new TwTradeSecretsClient();
results.tw_hits = (await tw.search({ query: "damage" })).hits
  .map((hit) => hit.section)
  .join(",");
assert.equal(results.tw_hits, "12,13");

// Network clients with synthetic upstreams.
const fees = new EpoFeesClient({
  fetch: async () =>
    Response.json([
      {
        data: { feeCode: "001", feeDescription: "Filing", amount: "1.595,00" },
        children: [],
      },
    ]),
});
results.fee = (await fees.getEpcSchedule()).fees[0].amount;
assert.equal(results.fee, "1595.00");
const ops = new EpoOpsClient({
  apiKey: "k",
  apiSecret: "s",
  fetch: async (input, init) => {
    const url = new URL(new Request(input, init).url);
    if (url.pathname.endsWith("accesstoken"))
      return Response.json({ access_token: "t", expires_in: 1200 });
    return new Response(
      '<ops:world-patent-data xmlns:ops="http://ops.epo.org"><ops:biblio-search total-result-count="0"/></ops:world-patent-data>',
    );
  },
});
results.ops_total = (await ops.search("ta=x")).data.total_results;

const google = GooglePatentsClient.parsePatent(
  gunzipSync(
    await readFile(fixture("google-patents/US7654321B2.html.gz")),
  ).toString(),
  "US7654321B2",
);
assert.equal(google.claims.length, 26);
results.google_claims = google.claims.length;

for (const client of [
  epcByPath,
  epcBytes,
  mpep,
  zst,
  upc,
  tmep,
  mopp,
  dpma,
  tw,
])
  client.close();
console.log(JSON.stringify({ runtime: `node ${process.version}`, ...results }));

// Runs the compiled client (packages/client/dist) under Node, outside Bun.
// Usage: bun run build && node scripts/smoke-node.mjs
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gunzipSync, zstdCompressSync } from "node:zlib";
import {
  ApiError,
  DpmaStatutesClient,
  downloadPatentPdfClean,
  EpcClient,
  EpoFeesClient,
  EpoOpsClient,
  GooglePatentsClient,
  getPatentClaims,
  IlpoStatutesClient,
  IpoInStatutesClient,
  IposStatutesClient,
  MoppClient,
  MpepClient,
  parseHearingNotice,
  parseJapanIpHighCourtWorkbook,
  TmepClient,
  TwTradeSecretsClient,
  UpcStatutesClient,
} from "@patent-client-agents/client";
import { verifyCorpusFile } from "@patent-client-agents/client/corpus-bootstrap";

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
const jpCourt = parseJapanIpHighCourtWorkbook(
  new Uint8Array(
    gunzipSync(
      await readFile(fixture("japan-ip-high-court/jikenitiran.xls.gz")),
    ),
  ),
);
results.jp_court = `${jpCourt.pending_count}/${jpCourt.closed_count}`;
assert.equal(results.jp_court, "34/219");
const ilpo = new IlpoStatutesClient({
  source: new Uint8Array(
    zstdCompressSync(await readFile(fixture("ilpo-statutes/ilpo_statutes.db"))),
  ),
});
results.ilpo_section = (
  await ilpo.getSectionByCitation("Section 6 Commercial Torts Law")
)?.title;
assert.equal(
  results.ilpo_section,
  "Prohibition against misappropriation of a trade secret",
);
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
const india = new IpoInStatutesClient({
  source: new Uint8Array(
    zstdCompressSync(await readFile(fixture("ipo-in/ipo_in_statutes.db"))),
  ),
});
results.ipo_in_section = (
  await india.getSectionByCitation("Section 3(d) Patents Act")
).section_number;
assert.equal(results.ipo_in_section, "3");
const singapore = new IposStatutesClient({
  source: new Uint8Array(
    zstdCompressSync(await readFile(fixture("ipos/ipos_statutes.db"))),
  ),
});
results.ipos_section = (
  await singapore.getByCitation("Section 13 Patents Act")
).section_label;
assert.equal(results.ipos_section, "13");

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

const googleHtml = gunzipSync(
  await readFile(fixture("google-patents/US7654321B2.html.gz")),
).toString();
const google = GooglePatentsClient.parsePatent(googleHtml, "US7654321B2");
assert.equal(google.claims.length, 26);
results.google_claims = google.claims.length;

const spc = JSON.parse(
  await readFile(fixture("china-spc-ip-court/notices.json"), "utf8"),
).notices["6106"];
const spcNotice = parseHearingNotice(spc.html, {
  noticeUrl: "https://ipc.court.gov.cn/zh-cn/news/view-6106.html",
});
assert.equal(spcNotice.parties[2].role_en, "first_instance_third_party");
results.spc_dispute = spcNotice.dispute_type;

// Fused helpers with stand-in sources: an ODP miss falls back to Google,
// and a PPUBS miss falls through to EPO.
const fused = await getPatentClaims(
  {
    applications: {
      getGrantedClaims: async () => ({ claims: null, provenance: null }),
    },
    googlePatents: {
      getPatentHtml: async (number) => ({
        html: googleHtml,
        patentNumber: number,
        provenance: null,
      }),
    },
  },
  "US7654321B2",
);
assert.equal(fused.claims.length, 26);
assert.ok(fused.claims[0].limitations.some((item) => item.depth > 0));
results.unified_claims = `${fused.source}:${fused.claims.length}`;
const fusedPdf = await downloadPatentPdfClean(
  {
    publications: {
      resolveDocumentByPublicationNumber: async () => {
        throw new ApiError("missing", 404, "NOT_FOUND");
      },
      downloadPdf: async () => assert.fail("PPUBS had no document"),
    },
    epoOps: {
      downloadPdf: async (number) => ({
        data: new TextEncoder().encode("%PDF-"),
        pages: 1,
        publicationNumber: number,
        provenance: null,
      }),
    },
  },
  "US1234567B1",
);
assert.equal(fusedPdf.filename, "US1234567B1.pdf");
results.unified_pdf = fusedPdf.source;
assert.equal(results.unified_pdf, "epo");

// The server-only bootstrap subpath: stream-verify a packaged artifact under Node.
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const scratch = await mkdtemp(join(tmpdir(), "pca-smoke-"));
try {
  const decoded = await readFile(fixture("epo-legal/epc.db"));
  const packed = zstdCompressSync(decoded);
  const packedPath = join(scratch, "epc.db.zst");
  await writeFile(packedPath, packed);
  const pins = {
    file_sha256: sha(packed),
    file_bytes: packed.length,
    decoded_sha256: sha(decoded),
    decoded_bytes: decoded.length,
  };
  assert.equal(await verifyCorpusFile(packedPath, pins), null);
  assert.match(
    await verifyCorpusFile(packedPath, {
      ...pins,
      decoded_sha256: "0".repeat(64),
    }),
    /decoded sha256/,
  );
  results.bootstrap_verify = "ok";
} finally {
  await rm(scratch, { recursive: true });
}

for (const client of [
  epcByPath,
  epcBytes,
  mpep,
  zst,
  upc,
  tmep,
  mopp,
  dpma,
  ilpo,
  tw,
])
  client.close();
console.log(JSON.stringify({ runtime: `node ${process.version}`, ...results }));

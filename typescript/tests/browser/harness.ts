// Bundled for the browser by scripts/smoke-browser.ts. Exercises the client
// with no Node or Bun APIs available and reports results on window.
import {
  configureWasm,
  createRelayFetch,
  EpcClient,
  EpoFeesClient,
  EpoOpsClient,
  GooglePatentsClient,
  MpepClient,
} from "../../packages/client/src/index.js";

configureWasm({ sqlite: "/wasm/sqlite3.wasm", zstd: "/wasm/zstd.wasm" });
const bytes = async (path: string) =>
  new Uint8Array(await (await fetch(path)).arrayBuffer());
const report = (value: unknown) => {
  (window as unknown as { smoke: unknown }).smoke = value;
  document.body.textContent = JSON.stringify(value);
};

try {
  const results: Record<string, unknown> = { userAgent: navigator.userAgent };
  const epc = new EpcClient({
    source: () => bytes("/fixtures/epo-legal/epc.db"),
  });
  results.epc_article = (await epc.getSection("Article 54")).citation;
  results.epc_hits = (
    await epc.search({ query: "patent", limit: 2 })
  ).hits.length;
  const mpep = new MpepClient({
    source: () => bytes("/fixtures/mpep/compressed.db"),
  });
  const hit = (await mpep.search({ query: "patent", limit: 1 })).hits[0];
  results.mpep_dictionary_cell = hit
    ? (await mpep.getSection(hit.href)).html.length > 0
    : false;
  const zst = new MpepClient({ source: () => bytes("/fixtures/plain.db.zst") });
  results.mpep_whole_file = (await zst.getCorpusStatus()).compression;
  const pathOnly = new MpepClient({ corpusPath: "/nowhere/mpep.db" });
  results.path_in_browser = (await pathOnly.getCorpusStatus()).error?.code;
  results.fee = (
    await new EpoFeesClient({
      fetch: (async () =>
        Response.json([
          {
            data: {
              feeCode: "001",
              feeDescription: "Filing",
              amount: "1.595,00",
            },
            children: [],
          },
        ])) as unknown as typeof fetch,
    }).getEpcSchedule()
  ).fees[0]?.amount;
  results.ops_total = (
    await new EpoOpsClient({
      apiKey: "k",
      apiSecret: "s",
      fetch: (async (input: RequestInfo | URL, init?: RequestInit) =>
        new URL(new Request(input, init).url).pathname.endsWith("accesstoken")
          ? Response.json({ access_token: "t", expires_in: 1200 })
          : new Response(
              '<ops:world-patent-data xmlns:ops="http://ops.epo.org"><ops:biblio-search total-result-count="3"/></ops:world-patent-data>',
            )) as unknown as typeof fetch,
    }).search("ta=x")
  ).data.total_results;
  const google = GooglePatentsClient.parsePatent(
    await (await fetch("/fixtures/google-patents/US7654321B2.html")).text(),
    "US7654321B2",
  );
  results.google_claims = google.claims.length;
  results.google_markdown = (google.description_markdown?.length ?? 0) > 10_000;
  // Cross-origin leg: the page's origin differs from the relay and the upstream.
  const relay = JSON.parse(
    decodeURIComponent(location.hash.slice(1)) || "null",
  ) as {
    relayUrl: string;
    token: string;
    upstreamUrl: string;
  } | null;
  if (relay) {
    results.direct_cross_origin = await fetch(relay.upstreamUrl)
      .then(() => "allowed")
      .catch(() => "blocked by CORS");
    results.relay_fee = (
      await new EpoFeesClient({
        retryLimit: 0,
        fetch: createRelayFetch({ url: relay.relayUrl, token: relay.token }),
      }).getEpcSchedule()
    ).fees[0]?.amount;
  }
  report({ ok: true, ...results });
} catch (error) {
  report({ ok: false, error: String(error), stack: (error as Error).stack });
}

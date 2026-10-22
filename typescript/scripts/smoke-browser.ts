// Bundles tests/browser/harness.ts for the browser and runs it in headless
// Chromium. Usage: bun run smoke:browser
import { generateKeyPairSync, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { gunzipSync, zstdCompressSync } from "node:zlib";
import { chromium } from "playwright";
import { createServer } from "../packages/mcp/src/index.js";

const root = join(import.meta.dir, "..");
const build = await Bun.build({
  entrypoints: [join(root, "tests/browser/harness.ts")],
  target: "browser",
  format: "esm",
  naming: { asset: "[name].[ext]" },
});
if (!build.success)
  throw new AggregateError(build.logs, "Browser bundle failed.");
const files = new Map<string, { body: Uint8Array; type: string }>();
for (const output of build.outputs)
  files.set(`/${output.path.replace(/^\.\//, "")}`, {
    body: new Uint8Array(await output.arrayBuffer()),
    type: output.type,
  });
const entry = build.outputs.find((output) => output.kind === "entry-point");
const fixtures = join(root, "tests/fixtures");
const served: string[] = [];
const server = Bun.serve({
  hostname: "127.0.0.1",
  port: 0,
  async fetch(request) {
    const path = new URL(request.url).pathname;
    served.push(path);
    if (path === "/")
      return new Response(
        `<!doctype html><meta charset="utf-8"><script type="module" src="/${entry?.path.replace(/^\.\//, "")}"></script>`,
        { headers: { "content-type": "text/html" } },
      );
    // Stand-in for the asset copy step a production build performs.
    if (path === "/wasm/sqlite3.wasm" || path === "/wasm/zstd.wasm")
      return new Response(
        await readFile(
          path.endsWith("sqlite3.wasm")
            ? Bun.resolveSync(
                "@sqlite.org/sqlite-wasm/sqlite3.wasm",
                join(root, "packages/client"),
              )
            : join(
                Bun.resolveSync(
                  "@bokuweb/zstd-wasm",
                  join(root, "packages/client"),
                ),
                "../../web/zstd.wasm",
              ),
        ),
        { headers: { "content-type": "application/wasm" } },
      );
    if (path === "/fixtures/google-patents/US7654321B2.html")
      return new Response(
        gunzipSync(
          await readFile(join(fixtures, "google-patents/US7654321B2.html.gz")),
        ),
        { headers: { "content-type": "text/html" } },
      );
    if (path === "/fixtures/japan-ip-high-court/jikenitiran.xls")
      return new Response(
        gunzipSync(
          await readFile(
            join(fixtures, "japan-ip-high-court/jikenitiran.xls.gz"),
          ),
        ),
        { headers: { "content-type": "application/vnd.ms-excel" } },
      );
    if (path === "/fixtures/plain.db.zst")
      return new Response(
        zstdCompressSync(await readFile(join(fixtures, "mpep/plain.db"))),
      );
    if (path.startsWith("/fixtures/") && !path.includes(".."))
      return new Response(await readFile(join(fixtures, path.slice(10))));
    const file = files.get(path);
    return file
      ? new Response(new Blob([new Uint8Array(file.body)]), {
          headers: { "content-type": file.type },
        })
      : new Response("Not found", { status: 404 });
  },
});
// A fake EPO fee feed with no CORS headers, an identity provider and the
// relay, each on its own origin, to exercise real browser CORS enforcement.
const feed = Bun.serve({
  hostname: "127.0.0.1",
  port: 0,
  fetch: () =>
    Response.json([
      {
        data: { feeCode: "001", feeDescription: "Filing", amount: "135,00" },
        children: [],
      },
    ]),
});
const { privateKey, publicKey } = generateKeyPairSync("rsa", {
  modulusLength: 2048,
});
const identity = Bun.serve({
  hostname: "127.0.0.1",
  port: 0,
  fetch: () =>
    Response.json({
      keys: [
        {
          ...publicKey.export({ format: "jwk" }),
          kid: "k",
          alg: "RS256",
          use: "sig",
        },
      ],
    }),
});
const issuer = "https://identity.test";
const audience = "patent-client-agents";
const pageOrigin = `http://127.0.0.1:${server.port}`;
const relayServer = createServer({
  auth: { jwksUri: `http://127.0.0.1:${identity.port}/jwks`, issuer, audience },
  relay: {
    origins: [pageOrigin],
    credentials: {},
    upstreams: { "fees.apps.epo.org": `http://127.0.0.1:${feed.port}/` },
  },
});
await relayServer.run({
  transport: "http",
  host: "127.0.0.1",
  port: 0,
  stateless: true,
});
const encode = (value: object) =>
  Buffer.from(JSON.stringify(value)).toString("base64url");
const unsigned = `${encode({ alg: "RS256", kid: "k", typ: "JWT" })}.${encode({ iss: issuer, aud: audience, sub: "smoke", exp: Math.floor(Date.now() / 1000) + 300, scope: "relay:use" })}`;
const relayConfig = {
  relayUrl: `http://127.0.0.1:${relayServer.address?.port}/relay`,
  token: `${unsigned}.${sign("RSA-SHA256", Buffer.from(unsigned), privateKey).toString("base64url")}`,
  upstreamUrl: `http://127.0.0.1:${feed.port}/prod/bff/api/fees`,
};
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(
    `${pageOrigin}/#${encodeURIComponent(JSON.stringify(relayConfig))}`,
  );
  await page.waitForFunction(() => "smoke" in window, null, {
    timeout: 60_000,
  });
  const result = await page.evaluate(
    () => (window as unknown as { smoke: unknown }).smoke,
  );
  console.log(
    JSON.stringify({
      result,
      pageErrors: errors,
      notFound: served.filter(
        (p) =>
          !files.has(p) &&
          p !== "/" &&
          !p.startsWith("/fixtures/") &&
          !p.startsWith("/wasm/"),
      ),
    }),
  );
  const checked = result as {
    ok?: boolean;
    google_claims?: number;
    unified_claims?: string;
    direct_cross_origin?: string;
    relay_fee?: string;
    upc_instrument?: string;
    dpma_section?: string;
    inpi_br_hits?: string;
    legifrance_section?: string;
    tw_hits?: string;
    ipo_in_mppp?: string;
    jp_court?: string;
    ilpo_section?: string;
    ipos_manual?: string;
  };
  if (
    !checked.ok ||
    checked.google_claims !== 26 ||
    checked.unified_claims !== "google_patents:26" ||
    checked.direct_cross_origin !== "blocked by CORS" ||
    checked.relay_fee !== "135.00" ||
    checked.upc_instrument !== "upca" ||
    checked.dpma_section !== "139" ||
    !checked.inpi_br_hits?.split(",").includes("art195") ||
    checked.legifrance_section !== "L611-10" ||
    checked.tw_hits !== "12,13" ||
    checked.jp_court !== "34/219:令和7年（行ケ）第10084号" ||
    checked.ipo_in_mppp !== "09.03.05.04" ||
    checked.ilpo_section !== "Section 13 Commercial Torts Law" ||
    checked.ipos_manual !== "Discoveries"
  )
    process.exitCode = 1;
} finally {
  await browser.close();
  server.stop(true);
  await relayServer.close();
  feed.stop(true);
  identity.stop(true);
}

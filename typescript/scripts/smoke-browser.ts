// Bundles tests/browser/harness.ts for the browser and runs it in headless
// Chromium. Usage: bun run smoke:browser
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { zstdCompressSync } from "node:zlib";
import { chromium } from "playwright";

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
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.port}/`);
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
  if (!(result as { ok?: boolean }).ok) process.exitCode = 1;
} finally {
  await browser.close();
  server.stop(true);
}

// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { resolve } from "node:path";
import { BulkDataClient } from "@patent-client-agents/client";
import { Cassette, RecordMode } from "cassetter";

if (!Bun.argv.includes("--record"))
  throw new Error("Explicit --record is required.");
const product = Bun.argv
  .find((value) => value.startsWith("--product="))
  ?.slice(10);
const file = Bun.argv.find((value) => value.startsWith("--file="))?.slice(7);
if (!product || !file)
  throw new Error(
    "Supply --product=<id> and --file=<filename> for a small official bulk file.",
  );
const path = resolve(import.meta.dir, "../tests/cassettes/odp-bulk-file.yaml");
const cassette = new Cassette(path, {
  recordMode: RecordMode.ALL,
  matchConfig: { matchOn: ["method", "uri", "json_body"] },
  securityConfig: {
    filterHeaders: ["x-api-key", "authorization", "cookie", "set-cookie"],
    filterQueryParameters: ["Expires", "Signature", "Key-Pair-Id"],
  },
});
cassette.load();
const headerMap = (h: Headers) =>
  Object.fromEntries(Array.from(h, ([k, v]) => [k, [v]]));
async function boundedCopy(response: Response): Promise<Buffer> {
  const reader = response.clone().body?.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  if (reader)
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > 1024 * 1024) {
          await reader.cancel();
          throw new Error("Bulk cassette recording is limited to 1 MiB.");
        }
        chunks.push(value);
      }
    } finally {
      reader.releaseLock();
    }
  return Buffer.concat(chunks);
}
const client = new BulkDataClient({
  retryLimit: 0,
  maxResponseBytes: 1024 * 1024,
  fetch: (async (input, init) => {
    const request = new Request(input, init);
    const response = await fetch(input, init);
    const headers = new Headers(response.headers);
    const location = headers.get("location");
    if (location) {
      const url = new URL(location);
      for (const key of ["Expires", "Signature", "Key-Pair-Id"])
        if (url.searchParams.has(key)) url.searchParams.set(key, "[FILTERED]");
      headers.set("location", url.href);
    }
    cassette.record(
      request.method,
      request.url,
      headerMap(request.headers),
      null,
      response.status,
      headerMap(headers),
      response.status === 302
        ? Buffer.from(
            (await boundedCopy(response))
              .toString("utf8")
              .replace(
                /(Expires|Signature|Key-Pair-Id)=[^&\s"<>]+/g,
                "$1=[FILTERED]",
              ),
          )
        : await boundedCopy(response),
    );
    return response;
  }) as typeof fetch,
});
const result = await client.downloadFile(product, file);
cassette.save();
console.log(
  JSON.stringify({
    bytes: result.data.length,
    zip: result.data[0] === 80 && result.data[1] === 75,
    interactions: cassette.interactions.length,
  }),
);

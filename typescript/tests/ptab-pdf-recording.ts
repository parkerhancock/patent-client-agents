import { resolve } from "node:path";
import { bodyToBuffer, Cassette, RecordMode } from "cassetter";
import { PtabTrialsClient } from "../packages/client/src/ptab.js";

const signedKeys = ["Expires", "Signature", "Key-Pair-Id"];
const headerMap = (headers: Headers) =>
  Object.fromEntries(Array.from(headers, ([key, value]) => [key, [value]]));
export async function ptabPdfRecording(mode: "all" | "none") {
  const cassette = new Cassette(
    resolve(import.meta.dir, "cassettes/odp-features-ptab-pdf.yaml"),
    {
      recordMode: mode === "all" ? RecordMode.ALL : RecordMode.NONE,
      matchConfig: { matchOn: ["method", "uri", "json_body"] },
      securityConfig: {
        filterHeaders: [
          "uspto-api-key",
          "x-api-key",
          "authorization",
          "cookie",
          "set-cookie",
        ],
        filterQueryParameters: signedKeys,
      },
    },
  );
  cassette.load();
  const requests: { host: string; authenticated: boolean }[] = [];
  const api = new PtabTrialsClient({
    ...(mode === "none" ? { apiKey: "replay-placeholder" } : {}),
    retryLimit: 0,
    maxResponseBytes: 4 * 1024 * 1024,
    fetch: (async (input, init) => {
      const request = new Request(input, init);
      requests.push({
        host: new URL(request.url).hostname,
        authenticated: request.headers.has("x-api-key"),
      });
      if (mode === "none") {
        const response = cassette.play(
          request.method,
          request.url,
          headerMap(request.headers),
          null,
        );
        return new Response(new Uint8Array(bodyToBuffer(response.body)), {
          status: response.status,
          headers: Object.fromEntries(
            Object.entries(response.headers).map(([key, values]) => [
              key,
              values.join(", "),
            ]),
          ),
        });
      }
      await Bun.sleep(1000);
      const response = await fetch(request);
      const headers = new Headers(response.headers);
      const location = headers.get("location");
      if (location) {
        const url = new URL(location, request.url);
        for (const key of url.searchParams.keys()) {
          if (!signedKeys.includes(key))
            throw new Error(
              "Review the new redirect query parameter before recording.",
            );
          url.searchParams.set(key, "[FILTERED]");
        }
        headers.set("location", url.href);
      }
      headers.delete("content-encoding");
      headers.delete("content-length");
      let body = Buffer.alloc(0);
      // Redirect bodies are unused by the client and may echo signed URLs.
      if (response.status < 300 || response.status >= 400) {
        const reader = response.clone().body?.getReader();
        const chunks: Uint8Array[] = [];
        let length = 0;
        if (reader)
          try {
            for (;;) {
              const { done, value } = await reader.read();
              if (done) break;
              length += value.byteLength;
              if (length > 4 * 1024 * 1024) {
                await reader.cancel();
                throw new Error("PTAB PDF recording exceeds 4 MiB.");
              }
              chunks.push(value);
            }
          } finally {
            reader.releaseLock();
          }
        body = Buffer.concat(chunks);
      }
      cassette.record(
        request.method,
        request.url,
        headerMap(request.headers),
        null,
        response.status,
        headerMap(headers),
        body,
      );
      return response;
    }) as typeof fetch,
  });
  const result = await api.downloadDocumentPdf("171376473", {
    signal: AbortSignal.timeout(20000),
  });
  if (mode === "all") cassette.save();
  return { ...result, interactions: cassette.interactions.length, requests };
}

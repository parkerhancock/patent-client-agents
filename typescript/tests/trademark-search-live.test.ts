import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { bodyToBuffer, Cassette, RecordMode } from "cassetter";
import {
  TrademarkSearchClient,
  WAF_USER_AGENT,
} from "../packages/client/src/trademark-search.js";

test("real Trademark Search response replays with native client normalization", async () => {
  const path = resolve(import.meta.dir, "cassettes/trademark-search-live.yaml");
  const serialized = await readFile(path, "utf8");
  for (const name of [
    "cookie",
    "set-cookie",
    "authorization",
    "x-access-token",
  ])
    expect(serialized.toLowerCase()).not.toMatch(
      new RegExp(`^\\s*${name}:`, "m"),
    );
  const cassette = new Cassette(path, {
    recordMode: RecordMode.NONE,
    matchConfig: { matchOn: ["method", "uri", "body"] },
  });
  cassette.load();
  let calls = 0;
  const fetcher = Object.assign(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = new Request(input, init);
      calls++;
      expect(request.headers.get("user-agent")).toBe(WAF_USER_AGENT);
      const response = cassette.play(
        request.method,
        request.url,
        {},
        Buffer.from(await request.text()),
      );
      return new Response(new Uint8Array(bodyToBuffer(response.body)), {
        status: response.status,
        headers: Object.fromEntries(
          Object.entries(response.headers).map(([k, v]) => [k, v.join(", ")]),
        ),
      });
    },
    { preconnect: fetch.preconnect },
  ) as typeof fetch;
  const result = await new TrademarkSearchClient({
    token: { token: "replay-placeholder", expires: Date.now() / 1000 + 86400 },
    fetch: fetcher,
    retryLimit: 0,
  }).searchQuery({ match: { wordmark: "APPLE" } }, { size: 1 });
  expect(calls).toBe(1);
  expect(result.count).toBe(1);
  expect(result.total).toBeGreaterThan(0);
  expect(result.results[0]?.serial_number).toMatch(/^\d{8}$/);
  expect(result.results[0]?.wordmark).toBeString();
  expect(result.results[0]?.status_live).toBeBoolean();
});

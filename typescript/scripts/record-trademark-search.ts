// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { resolve } from "node:path";
import { Cassette, RecordMode } from "cassetter";
import {
  TrademarkSearchClient,
  WAF_USER_AGENT,
  type WafToken,
} from "../packages/client/src/trademark-search.js";

// The deployed refresh job imports Python WafTokenManager, which mints this UA.
// Never print child output, cookies, response bodies, or raw caught errors.
const limit = 4 * 1024 * 1024;
const filtered = [
  "authorization",
  "proxy-authorization",
  "cookie",
  "set-cookie",
  "x-access-token",
  "x-api-key",
  "api_key",
  "apikey",
];
let session: WafToken | undefined;
let status: number | undefined;
try {
  if (!Bun.argv.includes("--deployed-secret"))
    throw new Error("Explicit deployed-secret selection is required.");
  const child = Bun.spawn(
    [
      "gcloud",
      "secrets",
      "versions",
      "access",
      "latest",
      "--secret=pca-waf-token-json",
      "--project=patentclient-mcp",
      "--account=parker.d.hancock@gmail.com",
    ],
    { stdout: "pipe", stderr: "pipe" },
  );
  const [payload, , exit] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  if (exit !== 0 || payload.length > 32768)
    throw new Error("Secret access failed.");
  const parsed = JSON.parse(payload) as WafToken;
  if (
    typeof parsed.token !== "string" ||
    !parsed.token ||
    !Number.isFinite(parsed.expires) ||
    parsed.expires * 1000 <= Date.now() ||
    (parsed.userAgent !== undefined && parsed.userAgent !== WAF_USER_AGENT)
  )
    throw new Error("Deployed session does not match its source contract.");
  session = {
    token: parsed.token,
    expires: parsed.expires,
    userAgent: WAF_USER_AGENT,
  };
  const cassette = new Cassette(
    resolve(import.meta.dir, "../tests/cassettes/trademark-search-live.yaml"),
    {
      recordMode: RecordMode.ALL,
      matchConfig: { matchOn: ["method", "uri", "body"] },
      securityConfig: { filterHeaders: filtered },
    },
  );
  let calls = 0;
  const fetcher = Object.assign(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = new Request(input, init);
      if (
        ++calls > 1 ||
        request.method !== "POST" ||
        request.url !== "https://tmsearch.uspto.gov/prod-stage-v1-0-0/tmsearch"
      )
        throw new Error("Bounded search route rejected.");
      const requestBody = await request.clone().text();
      const response = await fetch(request, { redirect: "manual" });
      status = response.status;
      const reader = response.body?.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      try {
        if (reader)
          for (;;) {
            const chunk = await reader.read();
            if (chunk.done) break;
            size += chunk.value.byteLength;
            if (size > limit) {
              await reader.cancel();
              throw new Error("Size limit exceeded.");
            }
            chunks.push(chunk.value);
          }
      } finally {
        reader?.releaseLock();
      }
      const body = Buffer.concat(chunks);
      if (body.includes(Buffer.from(parsed.token)))
        throw new Error("Credential reflection rejected.");
      // Whitelist public representation metadata; no upstream auth/session headers persist.
      const safeHeaders = {
        "content-type": [
          response.headers.get("content-type") ?? "application/json",
        ],
      };
      if (response.status === 200)
        cassette.record(
          "POST",
          request.url,
          { "user-agent": [WAF_USER_AGENT] },
          Buffer.from(requestBody),
          response.status,
          safeHeaders,
          body,
        );
      return new Response(body, {
        status: response.status,
        headers: {
          "content-type": safeHeaders["content-type"][0] ?? "application/json",
        },
      });
    },
    { preconnect: fetch.preconnect },
  ) as typeof fetch;
  const result = await new TrademarkSearchClient({
    token: session,
    fetch: fetcher,
    retryLimit: 0,
    timeoutMs: 20_000,
    maxResponseBytes: limit,
  }).searchQuery(
    { match: { wordmark: "APPLE" } },
    { size: 1, signal: AbortSignal.timeout(20_000) },
  );
  const yaml = cassette.toYaml();
  if (yaml.includes(parsed.token))
    throw new Error("Credential persistence rejected.");
  cassette.save();
  console.log(
    JSON.stringify({
      verified: true,
      status,
      count: result.count,
      total: result.total,
      calls,
    }),
  );
} catch {
  console.log(
    JSON.stringify({
      verified: false,
      ...(status === undefined ? {} : { status }),
      reason:
        status === 202 || status === 401 || status === 403
          ? "Deployed WAF session rejected by native Bun request; no retry or recording."
          : "Bounded session verification stopped; no secret or raw error emitted.",
    }),
  );
  process.exitCode = 1;
} finally {
  session = undefined;
}

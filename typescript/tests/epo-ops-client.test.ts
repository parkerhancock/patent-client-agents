import { expect, test } from "bun:test";
import {
  ConfigurationError,
  EpoOpsClient,
  EpoOpsError,
  opsNumber,
} from "../packages/client/src/index.js";

const wpd = (body: string) =>
  `<?xml version="1.0"?><ops:world-patent-data xmlns="http://www.epo.org/exchange" xmlns:ops="http://ops.epo.org">${body}</ops:world-patent-data>`;
const biblio = wpd(
  `<exchange-documents><exchange-document country="EP" doc-number="1" kind="A1" family-id="7"><bibliographic-data><publication-reference><document-id document-id-type="docdb"><country>EP</country><doc-number>1</doc-number><kind>A1</kind></document-id></publication-reference><invention-title lang="de">Titel</invention-title><invention-title lang="en">Title</invention-title></bibliographic-data></exchange-document></exchange-documents>`,
);
const fault = (code: string, message: string) =>
  `<?xml version="1.0"?><fault xmlns="http://ops.epo.org"><code>${code}</code><message>${message}</message></fault>`;

/** Synthetic OPS: token endpoint plus a scripted queue of data responses. */
function fakeOps(responses: (() => Response)[]) {
  const calls: { path: string; authorization: string | null }[] = [];
  let tokens = 0;
  const fetcher = (async (input, init) => {
    const request = new Request(input, init);
    const url = new URL(request.url);
    calls.push({
      path: url.pathname + url.search,
      authorization: request.headers.get("authorization"),
    });
    if (url.pathname === "/3.2/auth/accesstoken") {
      tokens++;
      await Bun.sleep(5);
      return Response.json({
        access_token: `token-${tokens}`,
        expires_in: "1199",
        issued_at: "0",
      });
    }
    const next = responses.shift();
    return next ? next() : new Response(biblio);
  }) as typeof fetch;
  const client = new EpoOpsClient({
    apiKey: "key",
    apiSecret: "secret",
    retryLimit: 0,
    fetch: fetcher,
  });
  return { client, calls, tokens: () => tokens };
}

test("requires both credentials", () => {
  const saved = { ...process.env };
  for (const name of [
    "EPO_OPS_API_KEY",
    "EPO_OPS_API_SECRET",
    "EPO_API_KEY",
    "EPO_API_SECRET",
  ])
    delete process.env[name];
  try {
    expect(() => new EpoOpsClient({ apiKey: "key" })).toThrow(
      ConfigurationError,
    );
  } finally {
    Object.assign(process.env, saved);
  }
});

test("concurrent requests share one token and send it only to OPS", async () => {
  const ops = fakeOps([]);
  const results = await Promise.all(
    Array.from({ length: 5 }, () => ops.client.getBiblio("EP1A1")),
  );
  expect(ops.tokens()).toBe(1);
  expect(results[0]?.data.documents[0]?.title).toBe("Title");
  const tokenCall = ops.calls.find((call) => call.path.includes("accesstoken"));
  expect(tokenCall?.authorization).toBe(
    `Basic ${Buffer.from("key:secret").toString("base64")}`,
  );
  for (const call of ops.calls.filter((c) => !c.path.includes("accesstoken")))
    expect(call.authorization).toBe("Bearer token-1");
  expect(results[0]?.provenance.source_url).not.toContain("token");
});

test("refreshes once on an invalid token and retries the request", async () => {
  const ops = fakeOps([
    () => new Response("invalid_access_token", { status: 400 }),
  ]);
  const result = await ops.client.getBiblio("EP1A1");
  expect(result.data.documents).toHaveLength(1);
  expect(ops.tokens()).toBe(2);
  expect(ops.calls.at(-1)?.authorization).toBe("Bearer token-2");
});

test("a token rejected after refresh fails without looping", async () => {
  const ops = fakeOps([
    () => new Response("", { status: 401 }),
    () => new Response("", { status: 401 }),
  ]);
  const error = await ops.client.getBiblio("EP1A1").catch((e) => e);
  expect(error).toBeInstanceOf(EpoOpsError);
  expect(error.code).toBe("AUTHENTICATION_FAILED");
  expect(ops.tokens()).toBe(2);
});

test("rejected credentials are an authentication failure", async () => {
  const fetcher = (async () =>
    new Response("bad credentials", {
      status: 401,
    })) as unknown as typeof fetch;
  const client = new EpoOpsClient({
    apiKey: "key",
    apiSecret: "secret",
    retryLimit: 0,
    fetch: fetcher,
  });
  const error = await client.getBiblio("EP1A1").catch((e) => e);
  expect(error).toMatchObject({ code: "AUTHENTICATION_FAILED", status: 401 });
  expect(String(error.message)).not.toContain("secret");
});

test("403 reports throttling headers as a retryable rate limit", async () => {
  const ops = fakeOps([
    () =>
      new Response(fault("CLIENT.RobotDetected", "Robot"), {
        status: 403,
        headers: {
          "X-Rejection-Reason": "IndividualQuotaPerHour",
          "X-Throttling-Control": "overloaded (search=red:0)",
        },
      }),
  ]);
  const error = await ops.client.getBiblio("EP1A1").catch((e) => e);
  expect(error).toMatchObject({ code: "RATE_LIMITED", retryable: true });
  expect(error.message).toContain("reason=IndividualQuotaPerHour");
  expect(error.message).toContain("throttling=overloaded");
});

test("404 faults map to not found; only no-results becomes an empty search", async () => {
  const ops = fakeOps([
    () =>
      new Response(fault("SERVER.EntityNotFound", "No results found"), {
        status: 404,
      }),
    () =>
      new Response(fault("SERVER.EntityNotFound", "Not found"), {
        status: 404,
      }),
    () =>
      new Response(fault("SERVER.EntityNotFound", "No results found"), {
        status: 404,
      }),
  ]);
  const empty = await ops.client.search("ta=nothing");
  expect(empty.data).toMatchObject({ total_results: 0, results: [] });
  const missing = await ops.client.getBiblio("EP9A1").catch((e) => e);
  expect(missing).toMatchObject({
    code: "NOT_FOUND",
    faultCode: "SERVER.EntityNotFound",
  });
  const fulltext = await ops.client.getFullText("US1A").catch((e) => e);
  expect(fulltext.message).toContain("no claims full text");
});

test("malformed or unexpected XML is never an empty record", async () => {
  const ops = fakeOps([
    () => new Response("<not-xml"),
    () => new Response("<other/>"),
    () => new Response(`<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>`),
  ]);
  for (let i = 0; i < 3; i++)
    expect(await ops.client.getBiblio("EP1A1").catch((e) => e.code)).toBe(
      "INVALID_RESPONSE",
    );
});

test("search, family, register and CPC requests use the documented routes", async () => {
  const ops = fakeOps([
    () => new Response(wpd(`<ops:biblio-search total-result-count="0"/>`)),
    () => new Response(wpd(`<ops:patent-family/>`)),
    () => new Response(wpd(`<ops:register-search/>`)),
    () =>
      new Response(wpd(`<ops:classification-search total-result-count="0"/>`)),
    () => new Response(""),
  ]);
  await ops.client.search("ta=x", { rangeBegin: 26, rangeEnd: 50 });
  await ops.client.getFamily("us 2005 0262543 a1", { constituents: "legal" });
  await ops.client.getUnitaryPatentPackage("ep4108782");
  await ops.client.searchCpc("battery", { rangeBegin: 1, rangeEnd: 5 });
  const mapping = await ops.client.mapClassification("cpc", "h04l9/32", "ipc");
  expect(mapping.data.mappings).toEqual([]);
  expect(
    ops.calls.filter((c) => !c.path.includes("accesstoken")).map((c) => c.path),
  ).toEqual([
    "/3.2/rest-services/published-data/search?q=ta%3Dx&Range=26-50",
    "/3.2/rest-services/family/publication/docdb/US2005262543A1/legal",
    "/3.2/rest-services/register/publication/epodoc/EP4108782/upp",
    "/3.2/rest-services/classification/cpc/search?q=battery",
    "/3.2/rest-services/classification/map/cpc/H04L9/32/ipc",
  ]);
});

test("identifier and range validation happen before any request", async () => {
  const ops = fakeOps([]);
  // Validation may throw synchronously, as in the other connectors.
  const fails = (run: () => unknown) =>
    expect(Promise.resolve().then(run)).rejects.toThrow();
  await fails(() => ops.client.retrieveCpc("../../auth"));
  await fails(() => ops.client.getCpcMedia("../x"));
  await fails(() => ops.client.search("ta=x", { rangeEnd: 500 }));
  await fails(() => ops.client.search(" "));
  expect(ops.calls).toHaveLength(0);
  expect(opsNumber("US20050262543A1")).toBe("US2005262543A1");
  expect(opsNumber("US20050262543A1", "publication", "original")).toBe(
    "US20050262543A1",
  );
  expect(opsNumber(" ep 1000000 a1 ")).toBe("EP1000000A1");
});

test("family evidence records per-view failures and skips the register outside EP", async () => {
  const ops = fakeOps([
    () => new Response(wpd(`<ops:patent-family total-result-count="0"/>`)),
    () =>
      new Response(fault("SERVER.EntityNotFound", "Not found"), {
        status: 404,
      }),
    () => new Response(biblio),
    () => new Response("", { status: 503 }),
  ]);
  const evidence = await ops.client.getFamilyEvidence("US6000000A");
  expect(evidence.inpadoc_family.outcome).toBe("empty");
  expect(evidence.register_biblio.outcome).toBe("not_applicable");
  const outcomes = [
    evidence.simple_family_equivalents,
    evidence.backward_citations,
    evidence.worldwide_legal_events,
  ].map((view) => view.outcome);
  expect(outcomes.sort()).toEqual(["empty", "error", "not_found"]);
  const failed = [
    evidence.simple_family_equivalents,
    evidence.backward_citations,
    evidence.worldwide_legal_events,
  ].find((view) => view.outcome === "error");
  expect(failed && "failure" in failed && failed.failure).toMatchObject({
    code: "upstream_server_error",
    retryable: true,
  });
});

test("family evidence fails when every attempted view fails", async () => {
  const ops = fakeOps(
    Array.from({ length: 4 }, () => () => new Response("", { status: 500 })),
  );
  const error = await ops.client
    .getFamilyEvidence("US6000000A")
    .catch((e) => e);
  expect(error).toBeInstanceOf(EpoOpsError);
});

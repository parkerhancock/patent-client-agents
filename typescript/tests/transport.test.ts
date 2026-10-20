import { expect, test } from "bun:test";
import {
  GenericHttpTransport,
  OdpTransport,
} from "../packages/client/src/transport.js";

function mock(
  handler: (request: Request) => Response | Promise<Response>,
): typeof fetch {
  return (async (input, init) =>
    handler(new Request(input, init))) as typeof fetch;
}
test("approved public download redirects strip all configured and per-call credentials", async () => {
  const calls: Request[] = [];
  const api = new OdpTransport({
    apiKey: "synthetic-api-secret",
    retryLimit: 0,
    fetch: mock((request) => {
      calls.push(request);
      if (new URL(request.url).hostname === "api.uspto.gov")
        return Response.redirect("https://downloads.uspto.gov/file.pdf", 302);
      expect(request.headers.get("x-api-key")).toBeNull();
      expect(request.headers.get("authorization")).toBeNull();
      expect(request.headers.get("cookie")).toBeNull();
      return new Response("PDF");
    }),
  });
  const result = await api.bytes("GET", "/file", {
    headers: {
      Authorization: "Bearer synthetic-secret",
      Cookie: "session=synthetic",
    },
    allowedHosts: ["downloads.uspto.gov"],
  });
  expect(new TextDecoder().decode(result.data)).toBe("PDF");
  expect(calls).toHaveLength(2);
  expect(calls[0]?.headers.get("x-api-key")).toBe("synthetic-api-secret");
});
test("unapproved redirects fail without contacting their destination", async () => {
  let calls = 0;
  const api = new OdpTransport({
    apiKey: "synthetic",
    retryLimit: 0,
    fetch: mock(() => {
      calls++;
      return Response.redirect("https://attacker.example/file", 302);
    }),
  });
  await expect(
    api.bytes("GET", "/file", { allowedHosts: ["downloads.uspto.gov"] }),
  ).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  expect(calls).toBe(1);
});
test("generic transport encodes forms and primitive JSON without losing metadata", async () => {
  const api = new GenericHttpTransport({
    baseUrl: "https://developer.uspto.gov",
    sourceName: "USPTO analytics",
    retryLimit: 0,
    fetch: mock(async (request) => {
      if (request.url.endsWith("form")) {
        expect(request.headers.get("content-type")).toContain(
          "application/x-www-form-urlencoded",
        );
        expect(await request.text()).toBe("criteria=a%26b");
        return new Response("text", { headers: { "x-receipt": "receipt" } });
      }
      expect(await request.json()).toBe(-1);
      return Response.json({ ok: true });
    }),
  });
  const form = await api.text("POST", "/form", { form: { criteria: "a&b" } });
  expect(form.data).toBe("text");
  expect(form.headers.get("x-receipt")).toBe("receipt");
  expect(form.provenance.source_name).toBe("USPTO analytics");
  expect((await api.json("POST", "/json", { body: -1 })).data).toEqual({
    ok: true,
  });
});

test("response limits reject declared and streamed oversize bodies before buffering them", async () => {
  for (const declared of [false, true]) {
    let cancelled = false;
    const api = new GenericHttpTransport({
      baseUrl: "https://api.uspto.gov",
      sourceName: "USPTO",
      maxResponseBytes: 4,
      retryLimit: 0,
      fetch: mock(
        () =>
          new Response(
            new ReadableStream({
              start(controller) {
                controller.enqueue(new Uint8Array(5));
              },
              cancel() {
                cancelled = true;
              },
            }),
            { headers: declared ? { "content-length": "1000000000" } : {} },
          ),
      ),
    });
    await expect(api.bytes("GET", "/file")).rejects.toMatchObject({
      code: "RESPONSE_TOO_LARGE",
    });
    expect(cancelled).toBe(true);
  }
});
test("provenance identifies the original API resource without signed redirect credentials", async () => {
  const api = new GenericHttpTransport({
    baseUrl: "https://api.uspto.gov",
    sourceName: "USPTO",
    retryLimit: 0,
    fetch: mock((request) =>
      new URL(request.url).hostname === "api.uspto.gov"
        ? Response.redirect(
            "https://data.uspto.gov/file?Signature=synthetic-signed-secret&Expires=123&Key-Pair-Id=synthetic-key",
            302,
          )
        : new Response("PDF"),
    ),
  });
  const result = await api.bytes("GET", "/file?apiKey=synthetic-secret", {
    allowedHosts: ["data.uspto.gov"],
  });
  expect(result.provenance.source_url).toBe("https://api.uspto.gov/file");
});

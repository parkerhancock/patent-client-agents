import { describe, expect, test } from "bun:test";
import { createHmac } from "node:crypto";
import type { MiddlewareContext } from "@prefecthq/fastmcp-ts/server";
import {
  actorId,
  MemoryRateLimitStore,
  MemoryUsageSink,
  previewArgs,
  RateLimiter,
  rateLimitMiddleware,
  resultBytes,
  usageMiddleware,
  virtualRefill,
} from "../packages/hosted/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";

const MB = 1024 * 1024;
const limits = {
  adminEmails: new Set(["admin@example.com"]),
  mbPerMinute: 1,
  mbPerDay: 3,
  adminMbPerMinute: 10,
  adminMbPerDay: 30,
  minChargeBytes: 1024,
};

function context(
  email: string | undefined,
  name = "get_fees",
  args: unknown = {},
) {
  return {
    method: "tools/call",
    request: { name, arguments: args },
    mcpContext: email
      ? { auth: { token: "t", scopes: [], claims: { email } } }
      : { auth: undefined },
  } as unknown as MiddlewareContext;
}

describe("byte-bucket refill (ported from the Python tests)", () => {
  const at = new Date(Date.UTC(2026, 3, 23, 12, 0, 30));
  const bucket = (tokens: number, last: Date) => ({
    tokens,
    last_refill: last,
    capacity: 1000,
    window_seconds: 60,
  });
  test("a fresh bucket reads as full", () => {
    expect(virtualRefill(undefined, 1000, 60, at)).toBe(1000);
  });
  test("refill is linear over the window", () => {
    expect(
      virtualRefill(bucket(0, new Date(at.getTime() - 30_000)), 1000, 60, at),
    ).toBeCloseTo(500, 0);
  });
  test("refill caps at capacity", () => {
    expect(
      virtualRefill(bucket(500, new Date(at.getTime() - 864e6)), 1000, 60, at),
    ).toBe(1000);
  });
  test("negative tokens refill toward zero", () => {
    expect(
      virtualRefill(
        bucket(-500, new Date(at.getTime() - 30_000)),
        1000,
        60,
        at,
      ),
    ).toBeCloseTo(0, 0);
  });
  test("a future last_refill never refills backwards", () => {
    expect(
      virtualRefill(bucket(100, new Date(at.getTime() + 30_000)), 1000, 60, at),
    ).toBe(100);
  });
});

describe("RateLimiter", () => {
  test("rejects after the minute bucket is spent and recovers as it refills", async () => {
    let clock = Date.UTC(2026, 9, 22);
    const limiter = new RateLimiter(
      new MemoryRateLimitStore(),
      limits,
      () => clock,
    );
    expect((await limiter.check("a", "u@example.com")).allowed).toBe(true);
    await limiter.debit("a", "u@example.com", 1.5 * MB);
    const refused = await limiter.check("a", "u@example.com");
    expect(refused).toMatchObject({ allowed: false, bucket: "minute" });
    // 0.5 MB deficit at 1 MB/min refills in 30 s, plus the 1 s margin.
    expect(refused.retryAfterSeconds).toBeCloseTo(31, 0);
    clock += 31_000;
    expect((await limiter.check("a", "u@example.com")).allowed).toBe(true);
  });

  test("the day bucket caps sustained use", async () => {
    let clock = Date.UTC(2026, 9, 22);
    const limiter = new RateLimiter(
      new MemoryRateLimitStore(),
      limits,
      () => clock,
    );
    for (let index = 0; index < 3; index++) {
      await limiter.debit("a", "u@example.com", 1.2 * MB);
      clock += 120_000;
    }
    expect(await limiter.check("a", "u@example.com")).toMatchObject({
      allowed: false,
      bucket: "day",
    });
  });

  test("admins get the admin limits", async () => {
    const limiter = new RateLimiter(
      new MemoryRateLimitStore(),
      limits,
      () => 0,
    );
    await limiter.debit("b", "Admin@Example.com", 5 * MB);
    expect((await limiter.check("b", "admin@example.com")).allowed).toBe(true);
  });
});

describe("rate-limit middleware", () => {
  const key = "actor-hash-test-key";
  test("unauthenticated callers pass through untouched", async () => {
    const store = new MemoryRateLimitStore();
    const middleware = rateLimitMiddleware({
      limiter: new RateLimiter(store, limits),
      actorHashKey: key,
      minChargeBytes: 1024,
      write: () => {},
    });
    expect(
      await middleware.onCallTool?.(context(undefined), async () => "ok"),
    ).toBe("ok");
    expect(store.buckets.size).toBe(0);
  });

  test("debits max(result bytes, minimum) under the pseudonymous actor", async () => {
    const store = new MemoryRateLimitStore();
    const middleware = rateLimitMiddleware({
      limiter: new RateLimiter(store, limits, () => Date.UTC(2026, 0, 1)),
      actorHashKey: key,
      minChargeBytes: 1024,
      write: () => {},
    });
    await middleware.onCallTool?.(context("u@example.com"), async () => ({
      small: true,
    }));
    const actor = (await actorId("u@example.com", key)) ?? "";
    expect([...store.buckets.keys()]).toEqual([actor]);
    expect(store.buckets.get(actor)?.minute?.tokens).toBe(MB - 1024);
    const big = { text: "x".repeat(4096) };
    await middleware.onCallTool?.(context("u@example.com"), async () => big);
    expect(store.buckets.get(actor)?.minute?.tokens).toBe(
      MB - 1024 - resultBytes(big),
    );
  });

  test("a spent bucket raises a retryable tool error and logs rate_limited", async () => {
    const events: Record<string, unknown>[] = [];
    const store = new MemoryRateLimitStore();
    const middleware = rateLimitMiddleware({
      limiter: new RateLimiter(store, limits, () => Date.UTC(2026, 0, 1)),
      actorHashKey: key,
      minChargeBytes: 2 * MB,
      write: (line) => events.push(JSON.parse(line)),
    });
    await middleware.onCallTool?.(context("u@example.com"), async () => ({}));
    let ran = false;
    await expect(
      middleware.onCallTool?.(context("u@example.com"), async () => {
        ran = true;
        return {};
      }) ?? Promise.resolve(),
    ).rejects.toThrow(
      /^\[retryable\] Rate limit exceeded on minute bucket\. Retry in ~\d+s\.$/,
    );
    expect(ran).toBe(false);
    expect(events.at(-1)).toMatchObject({
      event: "rate_limited",
      bucket: "minute",
      severity: "INFO",
    });
    expect(JSON.stringify(events)).not.toContain("example.com");
  });
});

describe("usage log", () => {
  test("actor ids match the Python HMAC pseudonym", async () => {
    const expected = createHmac("sha256", "demo-key")
      .update("user@example.com")
      .digest("hex")
      .slice(0, 32);
    expect(await actorId(" User@Example.COM ", "demo-key")).toBe(expected);
    expect(await actorId("user@example.com", "other-key")).not.toBe(expected);
    expect(await actorId("unauthenticated", "demo-key")).toBeUndefined();
    expect(await actorId("user@example.com", "")).toBeUndefined();
  });

  test("argument previews truncate long strings", () => {
    const preview = previewArgs({ q: "x".repeat(500), n: 42 });
    expect(preview.n).toBe(42);
    expect(String(preview.q)).toStartWith("x".repeat(200));
    expect(String(preview.q)).toEndWith("...[500 total]");
    expect(previewArgs(null)).toEqual({});
    expect(previewArgs("text")).toEqual({});
  });

  test("records successes, thrown errors and error results", async () => {
    const sink = new MemoryUsageSink();
    const events: Record<string, unknown>[] = [];
    const middleware = usageMiddleware({
      sink,
      actorHashKey: "k".repeat(20),
      write: (line) => events.push(JSON.parse(line)),
    });
    await middleware.onCallTool?.(
      context("u@example.com", "get_patent"),
      async () => ({ ok: 1 }),
    );
    await expect(
      middleware.onCallTool?.(
        context("u@example.com", "get_patent"),
        async () => {
          throw new TypeError("bad input");
        },
      ) ?? Promise.resolve(),
    ).rejects.toThrow("bad input");
    await middleware.onCallTool?.(
      context("u@example.com", "search_epo"),
      async () => ({
        isError: true,
        content: [{ type: "text", text: "EPO OPS is not configured." }],
      }),
    );
    expect(
      sink.records.map((record) => [record.tool, record.ok, record.error]),
    ).toEqual([
      ["get_patent", true, null],
      ["get_patent", false, "TypeError: bad input"],
      ["search_epo", false, "EPO OPS is not configured."],
    ]);
    for (const record of sink.records) {
      expect(Object.keys(record).sort()).toEqual(
        ["actor_id", "duration_ms", "error", "ok", "tool", "ts"].sort(),
      );
      expect(record.ts).toBeInstanceOf(Date);
    }
    expect(events.map((event) => event.event)).toEqual([
      "tool_call",
      "tool_call",
      "tool_call",
    ]);
    expect(events[0]).toMatchObject({
      severity: "INFO",
      tool: "get_patent",
      ok: true,
    });
    expect(JSON.stringify(events)).not.toContain("example.com");
  });

  test("unauthenticated calls are logged to stdout only; sink failures do not fail calls", async () => {
    const sink = new MemoryUsageSink();
    const events: Record<string, unknown>[] = [];
    await usageMiddleware({
      sink,
      actorHashKey: "k".repeat(20),
      write: (l) => events.push(JSON.parse(l)),
    }).onCallTool?.(context(undefined), async () => "ok");
    expect(sink.records).toEqual([]);
    expect(events[0]).toMatchObject({ event: "tool_call", actor_id: null });
    const broken = usageMiddleware({
      sink: { record: async () => Promise.reject(new Error("firestore down")) },
      actorHashKey: "k".repeat(20),
      write: (l) => events.push(JSON.parse(l)),
    });
    expect(
      await broken.onCallTool?.(context("u@example.com"), async () => "fine"),
    ).toBe("fine");
    expect(events.at(-1)).toMatchObject({
      event: "usage_write_failed",
      severity: "WARNING",
    });
  });
});

describe("middleware in a FastMCP server", () => {
  test("a rate-limited call becomes an error result and still reaches the usage log", async () => {
    const server = createServer({ toolset: "curated" });
    const sink = new MemoryUsageSink();
    const key = "k".repeat(20);
    server.use(usageMiddleware({ sink, actorHashKey: key, write: () => {} }));
    server.use(
      rateLimitMiddleware({
        limiter: new RateLimiter(new MemoryRateLimitStore(), limits),
        actorHashKey: key,
        minChargeBytes: 2 * MB,
        write: () => {},
      }),
    );
    const call = async () => {
      const response = await server.fetch(
        new Request("http://localhost/mcp", {
          method: "POST",
          headers: {
            "content-type": "application/json",
            accept: "application/json, text/event-stream",
          },
          body: JSON.stringify({
            jsonrpc: "2.0",
            id: 1,
            method: "tools/call",
            params: { name: "patent_client_status", arguments: {} },
          }),
        }),
        {
          authInfo: {
            token: "verified",
            clientId: "client",
            scopes: [],
            extra: { email: "u@example.com", sub: "s" },
          },
        },
      );
      const text = await response.text();
      const data = text.split("\n").find((line) => line.startsWith("data: "));
      return JSON.parse(data ? data.slice(6) : text).result as {
        isError?: boolean;
        content: { text: string }[];
      };
    };
    try {
      expect((await call()).isError).not.toBe(true);
      const limited = await call();
      expect(limited.isError).toBe(true);
      expect(limited.content[0]?.text).toStartWith(
        "[retryable] Rate limit exceeded",
      );
      expect(sink.records.map((record) => record.ok)).toEqual([true, false]);
    } finally {
      await server.close();
    }
  });
});

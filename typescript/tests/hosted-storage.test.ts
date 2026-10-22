import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import {
  decodeValue,
  encodeValue,
  FirestoreClient,
  FirestoreOAuthStore,
  FirestoreRateLimitStore,
  FirestoreUsageSink,
  MemoryOAuthStore,
  MemoryRateLimitStore,
  type OAuthStore,
  type RateLimitStore,
} from "../packages/hosted/src/index.js";

/**
 * One contract for every storage implementation: in-memory, Firestore REST
 * against a fake Firestore server, and the Firestore emulator when
 * FIRESTORE_EMULATOR_HOST is set (`gcloud emulators firestore start`).
 */

interface StoredDocument {
  fields: Record<string, unknown>;
  createTime: string;
  updateTime: string;
}

/** The slice of the Firestore v1 REST API the hosted stores use. */
function startFakeFirestore() {
  const documents = new Map<string, StoredDocument>();
  const requests: {
    method: string;
    path: string;
    authorization: string | null;
  }[] = [];
  let tick = 0;
  const stamp = () =>
    new Date(Date.UTC(2026, 0, 1) + ++tick).toISOString().replace("Z", "000Z");
  const error = (status: number, code: string) =>
    Response.json(
      { error: { code: status, status: code, message: code } },
      { status },
    );
  const server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      const url = new URL(request.url);
      const path = decodeURIComponent(url.pathname.replace(/^\/v1\//, ""));
      requests.push({
        method: request.method,
        path,
        authorization: request.headers.get("authorization"),
      });
      if (request.method === "GET") {
        const document = documents.get(path);
        return document
          ? Response.json({ name: path, ...document })
          : error(404, "NOT_FOUND");
      }
      if (request.method === "POST" && path.endsWith("/documents:commit")) {
        const { writes } = (await request.json()) as {
          writes: {
            update?: { name: string; fields: Record<string, unknown> };
            delete?: string;
            currentDocument?: { exists?: boolean; updateTime?: string };
          }[];
        };
        // Check every precondition first: commits are all or nothing.
        for (const write of writes) {
          const current = documents.get(
            write.update?.name ?? write.delete ?? "",
          );
          const condition = write.currentDocument;
          if (condition?.exists === false && current)
            return error(409, "ALREADY_EXISTS");
          if (condition?.exists === true && !current)
            return error(404, "NOT_FOUND");
          if (
            condition?.updateTime !== undefined &&
            current?.updateTime !== condition.updateTime
          )
            return error(400, "FAILED_PRECONDITION");
        }
        for (const write of writes) {
          if (write.delete) documents.delete(write.delete);
          if (write.update) {
            const time = stamp();
            documents.set(write.update.name, {
              fields: write.update.fields,
              createTime: documents.get(write.update.name)?.createTime ?? time,
              updateTime: time,
            });
          }
        }
        return Response.json({ commitTime: stamp() });
      }
      return error(400, "INVALID_ARGUMENT");
    },
  });
  return {
    host: `127.0.0.1:${server.port}`,
    url: `http://127.0.0.1:${server.port}`,
    documents,
    requests,
    stop: () => server.stop(true),
  };
}

let fake: ReturnType<typeof startFakeFirestore>;
let clock = Date.UTC(2026, 9, 22);
const now = () => clock;

beforeAll(() => {
  fake = startFakeFirestore();
});
afterAll(() => fake.stop());

const credentials = {
  token: async () => "test-access-token",
  projectId: async () => "test-project",
  headers: async () => ({ "x-goog-user-project": "quota-project" }),
};

function fakeClient() {
  return new FirestoreClient({
    projectId: "test-project",
    credentials,
    fetch: (input, init) =>
      fetch(
        String(input).replace("https://firestore.googleapis.com", fake.url),
        init,
      ),
  });
}

const emulator = process.env.FIRESTORE_EMULATOR_HOST;
function emulatorClient() {
  return new FirestoreClient({
    projectId: `pca-hosted-test-${Date.now()}`,
    emulatorHost: emulator ?? "",
  });
}

const backends: [
  string,
  () => { oauth: OAuthStore; limits: RateLimitStore },
  boolean,
][] = [
  [
    "memory",
    () => ({
      oauth: new MemoryOAuthStore(now),
      limits: new MemoryRateLimitStore(),
    }),
    true,
  ],
  [
    "firestore (fake REST server)",
    () => {
      const client = fakeClient();
      return {
        oauth: new FirestoreOAuthStore(client, undefined, now),
        limits: new FirestoreRateLimitStore(client),
      };
    },
    true,
  ],
  [
    "firestore (emulator)",
    () => {
      const client = emulatorClient();
      return {
        oauth: new FirestoreOAuthStore(client, undefined, now),
        limits: new FirestoreRateLimitStore(client),
      };
    },
    Boolean(emulator),
  ],
];

for (const [name, make, enabled] of backends)
  describe.if(enabled)(`storage contract: ${name}`, () => {
    test("put, get and delete round-trip JSON records", async () => {
      const { oauth } = make();
      const value = {
        client_id: "abc",
        redirect_uris: ["http://localhost:1/cb", "https://claude.ai/x"],
        nested: { count: 3, ratio: 0.5, ok: true, nothing: null, empty: [] },
      };
      await oauth.put("clients", "abc", value);
      expect(await oauth.get("clients", "abc")).toEqual(value);
      expect(await oauth.get("clients", "missing")).toBeUndefined();
      await oauth.delete("clients", "abc");
      expect(await oauth.get("clients", "abc")).toBeUndefined();
    });

    test("records expire after their TTL", async () => {
      const { oauth } = make();
      await oauth.put("codes", "short", { a: 1 }, 60);
      expect(await oauth.get("codes", "short")).toEqual({ a: 1 });
      clock += 61_000;
      expect(await oauth.get("codes", "short")).toBeUndefined();
      expect(await oauth.take("codes", "short")).toBeUndefined();
    });

    test("take is atomic: one of many concurrent callers wins", async () => {
      const { oauth } = make();
      await oauth.put("codes", "once", { v: "x" }, 300);
      const results = await Promise.all(
        Array.from({ length: 6 }, () =>
          oauth.take<{ v: string }>("codes", "once"),
        ),
      );
      expect(results.filter((result) => result?.v === "x")).toHaveLength(1);
      expect(await oauth.get("codes", "once")).toBeUndefined();
    });

    test("rate-limit updates are read-modify-write without lost updates", async () => {
      const { limits } = make();
      const actor = `actor${Math.floor(Math.random() * 1e9)}`;
      const at = new Date(Date.UTC(2026, 9, 22));
      await Promise.all(
        Array.from({ length: 4 }, () =>
          limits.update(actor, (current) => ({
            minute: {
              tokens: (current?.minute?.tokens ?? 0) + 1,
              last_refill: at,
              capacity: 10,
              window_seconds: 60,
            },
          })),
        ),
      );
      const state = await limits.read(actor);
      expect(state?.minute?.tokens).toBe(4);
      expect(new Date(state?.minute?.last_refill ?? 0).getTime()).toBe(
        at.getTime(),
      );
    });
  });

describe("Firestore REST details", () => {
  test("documents live in ts-mcp- collections with credentials and quota project", async () => {
    fake.requests.length = 0;
    const client = fakeClient();
    await new FirestoreOAuthStore(client).put(
      "refresh_tokens",
      "rt1",
      { x: 1 },
      60,
    );
    await new FirestoreUsageSink(client).record({
      actor_id: "a".repeat(32),
      tool: "get_fees",
      ts: new Date("2026-10-22T00:00:00Z"),
      duration_ms: 12.5,
      ok: true,
      error: null,
    });
    const names = [...fake.documents.keys()];
    expect(names).toContain(
      "projects/test-project/databases/(default)/documents/ts-mcp-oauth-refresh-tokens/rt1",
    );
    const usage = names.find((name) => name.includes("/ts-mcp-usage/"));
    expect(usage).toBeDefined();
    const fields = fake.documents.get(usage ?? "")?.fields as Record<
      string,
      unknown
    >;
    expect(fields.ts).toEqual({ timestampValue: "2026-10-22T00:00:00.000Z" });
    expect(fields.duration_ms).toEqual({ doubleValue: 12.5 });
    expect(Object.keys(fields).sort()).toEqual(
      ["actor_id", "duration_ms", "error", "ok", "tool", "ts"].sort(),
    );
    expect(
      fake.requests.every(
        (request) => request.authorization === "Bearer test-access-token",
      ),
    ).toBe(true);
    const ttl = fake.documents.get(
      "projects/test-project/databases/(default)/documents/ts-mcp-oauth-refresh-tokens/rt1",
    )?.fields.expires_at as { timestampValue?: string };
    expect(ttl.timestampValue).toBeString();
  });

  test("values round-trip through Firestore encoding", () => {
    const value = {
      text: "x",
      count: 42,
      big: 2 ** 60,
      ratio: 1.25,
      flag: false,
      none: null,
      when: new Date("2026-01-02T03:04:05.000Z"),
      list: [1, "two", { three: 3 }],
    };
    const decoded = decodeValue(encodeValue(value)) as Record<string, unknown>;
    expect(decoded).toEqual({ ...value });
    expect(encodeValue(42)).toEqual({ integerValue: "42" });
  });

  test("record ids are restricted to URL-safe characters", async () => {
    const store = new FirestoreOAuthStore(fakeClient());
    await expect(store.get("clients", "../../other/doc")).rejects.toThrow(
      "Invalid",
    );
  });

  test("server errors are not mistaken for missing documents", async () => {
    const client = new FirestoreClient({
      projectId: "p",
      credentials,
      fetch: async () => new Response("boom", { status: 500 }),
    });
    await expect(client.get("c/d")).rejects.toThrow("HTTP 500");
    await expect(client.commit([{ delete: "c/d" }])).rejects.toThrow(
      "HTTP 500",
    );
  });
});

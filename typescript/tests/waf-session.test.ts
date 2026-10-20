import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import {
  chmod,
  lstat,
  mkdir,
  readdir,
  readFile,
  rmdir,
  symlink,
  unlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { crc32c } from "../packages/waf-session/src/crc32c.js";
import {
  createFileWafSessionStore,
  createGoogleWafSessionStore,
  createWafSessionProvider,
  parseWafSession,
  WAF_USER_AGENT,
  type WafSession,
  WafSessionError,
} from "../packages/waf-session/src/index.js";

const session = (token = "synthetic-session-a"): WafSession => ({
  token,
  acquired: Date.now() / 1000 - 10,
  expires: Date.now() / 1000 + 86400,
  userAgent: WAF_USER_AGENT,
});
const fakeFetch = (
  handler: (request: Request) => Response | Promise<Response>,
) =>
  Object.assign(
    async (input: RequestInfo | URL, init?: RequestInit) =>
      handler(new Request(input, init)),
    { preconnect: fetch.preconnect },
  ) as typeof fetch;

async function directory(run: (path: string) => Promise<void>) {
  const path = join(tmpdir(), `pca-waf-session-${randomUUID()}`);
  await mkdir(path, { mode: 0o700 });
  try {
    await run(path);
  } finally {
    for (const name of await readdir(path)) await unlink(join(path, name));
    await rmdir(path);
  }
}
test("session parsing supports deployed JSON and rejects unsafe headers, times and oversized payloads without leaking input", () => {
  const { userAgent: _, ...legacy } = session();
  expect(parseWafSession(legacy).userAgent).toBe(WAF_USER_AGENT);
  const iso = new Date(legacy.acquired * 1000).toISOString();
  expect(parseWafSession({ ...legacy, acquired: iso }).acquired).toBe(
    Date.parse(iso) / 1000,
  );
  expect(
    parseWafSession({ ...legacy, acquired: iso.replace("Z", "+00:00") })
      .userAgent,
  ).toBe(WAF_USER_AGENT);
  for (const value of [
    null,
    { ...session(), token: "private-token\r\nX: secret" },
    { ...session(), userAgent: "private-UA\nsecret" },
    { ...session(), expires: 0 },
    { ...session(), acquired: Date.now() / 1000 + 1000 },
    { ...session(), token: "a".repeat(16385) },
  ]) {
    try {
      parseWafSession(value);
      throw new Error("Expected rejection");
    } catch (error) {
      expect(error).toBeInstanceOf(WafSessionError);
      expect(String(error)).not.toContain("private-");
      expect(error).not.toHaveProperty("cause");
    }
  }
});
test("file store publishes atomically with0600 permissions and reloads rotated sessions", async () => {
  await directory(async (directory) => {
    const path = join(directory, "session.json");
    const store = createFileWafSessionStore(path);
    await store.write(session());
    expect((await lstat(path)).mode & 0o777).toBe(0o600);
    expect(await readdir(directory)).toEqual(["session.json"]);
    expect((await store.read()).token).toBe("synthetic-session-a");
    await store.write(session("synthetic-session-b"));
    expect((await store.read()).token).toBe("synthetic-session-b");
    const wire = JSON.parse(await readFile(path, "utf8"));
    expect(wire.userAgent).toBe(WAF_USER_AGENT);
    expect(typeof wire.acquired).toBe("string");
    expect((await store.read()).acquired).toBe(
      Date.parse(wire.acquired) / 1000,
    );
  });
});
test("file store refuses readable permissions, symlinks and oversized bytes with sanitized errors", async () => {
  await directory(async (directory) => {
    const path = join(directory, "session.json");
    const store = createFileWafSessionStore(path);
    await store.write(session());
    await chmod(path, 0o644);
    await expect(store.read()).rejects.toBeInstanceOf(WafSessionError);
    await chmod(path, 0o600);
    const link = join(directory, "link.json");
    await symlink(path, link);
    await expect(createFileWafSessionStore(link).read()).rejects.toBeInstanceOf(
      WafSessionError,
    );
    await expect(
      createFileWafSessionStore(link).write(session()),
    ).rejects.toBeInstanceOf(WafSessionError);
    await writeFile(path, "private-value".repeat(4000), { mode: 0o600 });
    await expect(store.read()).rejects.toThrow(
      "protected current WAF session file",
    );
  });
});
test("provider sees warm-process rotation and forces new source reads after rejection", async () => {
  let next = session();
  let reads = 0;
  const provider = createWafSessionProvider(
    {
      read: async () => {
        reads++;
        return next;
      },
    },
    { pollIntervalMs: 5 },
  );
  const first = await provider.load({ forceRefresh: false });
  next = session("synthetic-session-b");
  expect((await provider.load({ forceRefresh: false })).token).toBe(
    first.token,
  );
  await Bun.sleep(10);
  expect((await provider.load({ forceRefresh: false })).token).toBe(next.token);
  const latest = session("synthetic-session-c");
  next = latest;
  expect(
    (
      await provider.load({
        forceRefresh: true,
        rejectedToken: session("synthetic-session-b"),
      })
    ).token,
  ).toBe(latest.token);
  expect(reads).toBe(3);
});
test("provider coalesces simultaneous reads and fails unchanged rejected cookies despite new timestamps", async () => {
  let reads = 0;
  let next = session();
  const provider = createWafSessionProvider({
    read: async () => {
      reads++;
      await Bun.sleep(5);
      return next;
    },
  });
  const results = await Promise.all(
    Array.from({ length: 8 }, () => provider.load({ forceRefresh: false })),
  );
  expect(reads).toBe(1);
  const rejectedToken = results[0];
  if (!rejectedToken) throw new Error("Missing coalesced session");
  next = { ...next, acquired: next.acquired + 1, expires: next.expires + 1 };
  await expect(
    provider.load({ forceRefresh: true, rejectedToken }),
  ).rejects.toThrow("fresh trusted WAF session");
  await expect(provider.load({ forceRefresh: false })).rejects.toBeInstanceOf(
    WafSessionError,
  );
  next = session("synthetic-rotated");
  expect((await provider.load({ forceRefresh: false })).token).toBe(
    "synthetic-rotated",
  );
});
test("provider bounds hanging reads and never caches late results after timeout", async () => {
  let resolve: ((value: WafSession) => void) | undefined;
  let reads = 0;
  const provider = createWafSessionProvider(
    {
      read: () => {
        reads++;
        return reads === 1
          ? new Promise<WafSession>((done) => {
              resolve = done;
            })
          : Promise.resolve(session("new"));
      },
    },
    { timeoutMs: 10 },
  );
  await expect(provider.load({ forceRefresh: false })).rejects.toThrow(
    "fresh trusted WAF session",
  );
  resolve?.(session("stale"));
  await Bun.sleep(1);
  expect((await provider.load({ forceRefresh: false })).token).toBe("new");
  expect(reads).toBe(2);
});
test("Google store confines identity token to exact Secret Manager origin and roundtrips session payload", async () => {
  const requests: Request[] = [];
  let persisted = session();
  const store = createGoogleWafSessionStore(
    "projects/test-project/secrets/waf-token",
    {
      fetch: fakeFetch(async (request) => {
        requests.push(request);
        if (request.url.startsWith("http://metadata.google.internal/")) {
          expect(request.headers.get("authorization")).toBeNull();
          expect(request.headers.get("metadata-flavor")).toBe("Google");
          return Response.json(
            { access_token: "synthetic-identity", token_type: "Bearer" },
            { headers: { "Metadata-Flavor": "Google" } },
          );
        }
        expect(new URL(request.url).origin).toBe(
          "https://secretmanager.googleapis.com",
        );
        expect(request.headers.get("authorization")).toBe(
          "Bearer synthetic-identity",
        );
        expect(request.redirect).toBe("error");
        if (request.method === "POST") {
          const body = (await request.json()) as {
            payload: { data: string; dataCrc32c: string };
          };
          expect(body.payload.dataCrc32c).toBe(
            String(crc32c(Buffer.from(body.payload.data, "base64"))),
          );
          persisted = JSON.parse(
            Buffer.from(body.payload.data, "base64").toString(),
          );
          expect(typeof persisted.acquired).toBe("string");
          return Response.json({
            name: "projects/test-project/secrets/waf-token/versions/2",
          });
        }
        return Response.json({
          payload: {
            data: Buffer.from(JSON.stringify(persisted)).toString("base64"),
            dataCrc32c: String(crc32c(Buffer.from(JSON.stringify(persisted)))),
          },
        });
      }),
    },
  );
  await store.write(session("new-value"));
  expect((await store.read()).token).toBe("new-value");
  expect(requests.map((r) => r.url)).toEqual([
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
    "https://secretmanager.googleapis.com/v1/projects/test-project/secrets/waf-token:addVersion",
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
    "https://secretmanager.googleapis.com/v1/projects/test-project/secrets/waf-token/versions/latest:access",
  ]);
});
test("Google store rejects redirects, invalid metadata, oversized bodies and stalled identity without leaking errors", async () => {
  for (const response of [
    new Response("private-response", {
      status: 302,
      headers: { location: "https://untrusted.test" },
    }),
    Response.json({ access_token: "private-identity", token_type: "Bearer" }),
    new Response("x".repeat(65537), {
      headers: { "Metadata-Flavor": "Google" },
    }),
  ]) {
    const store = createGoogleWafSessionStore("projects/test/secrets/waf", {
      fetch: fakeFetch(() => response.clone()),
    });
    try {
      await store.read();
      throw new Error("Expected failure");
    } catch (error) {
      expect(error).toBeInstanceOf(WafSessionError);
      expect(String(error)).not.toContain("private-");
      expect(error).not.toHaveProperty("cause");
    }
  }
  const store = createGoogleWafSessionStore("projects/test/secrets/waf", {
    timeoutMs: 10,
    fetch: fakeFetch(() => new Promise<Response>(() => {})),
  });
  await expect(store.read()).rejects.toBeInstanceOf(WafSessionError);
  expect(() =>
    createGoogleWafSessionStore("projects/test/secrets/waf/../../evil"),
  ).toThrow(WafSessionError);
});

test("force rejection invalidates an ordinary read already in flight without caching its result", async () => {
  let release: ((value: WafSession) => void) | undefined;
  const rejectedToken = session();
  let reads = 0;
  const provider = createWafSessionProvider({
    read: () => {
      reads++;
      return reads === 1
        ? new Promise<WafSession>((done) => {
            release = done;
          })
        : Promise.resolve(session("new-version"));
    },
  });
  const ordinary = provider.load({ forceRefresh: false });
  const forced = provider.load({ forceRefresh: true, rejectedToken });
  const outcomes = Promise.allSettled([ordinary, forced]);
  release?.(rejectedToken);
  expect((await outcomes).map((result) => result.status)).toEqual([
    "rejected",
    "rejected",
  ]);
  expect((await provider.load({ forceRefresh: false })).token).toBe(
    "new-version",
  );
  expect(reads).toBe(2);
});

test("Google timeout cannot publish after a late identity response and rejected secret data stays private", async () => {
  let release: ((value: Response) => void) | undefined;
  let calls = 0;
  const store = createGoogleWafSessionStore("projects/test/secrets/waf", {
    timeoutMs: 10,
    fetch: fakeFetch(() => {
      calls++;
      return new Promise<Response>((done) => {
        release = done;
      });
    }),
  });
  await expect(store.write(session())).rejects.toBeInstanceOf(WafSessionError);
  release?.(
    Response.json(
      { access_token: "synthetic-late-identity", token_type: "Bearer" },
      { headers: { "Metadata-Flavor": "Google" } },
    ),
  );
  await Bun.sleep(1);
  expect(calls).toBe(1);
  const badStore = createGoogleWafSessionStore("projects/test/secrets/waf", {
    fetch: fakeFetch((request) =>
      request.url.startsWith("http:")
        ? Response.json(
            { access_token: "synthetic-identity", token_type: "Bearer" },
            { headers: { "Metadata-Flavor": "Google" } },
          )
        : Response.json({
            payload: {
              data: Buffer.from(
                JSON.stringify({ ...session("private-cookie"), expires: 0 }),
              ).toString("base64"),
            },
          }),
    ),
  });
  try {
    await badStore.read();
    throw new Error("Expected invalid session");
  } catch (error) {
    expect(error).toBeInstanceOf(WafSessionError);
    expect(String(error)).not.toContain("private-cookie");
  }
});

test("Secret Manager CRC32C verifies the Castagnoli vector and rejects corrupted or malformed checksums", async () => {
  expect(crc32c(Buffer.from("123456789"))).toBe(0xe3069283);
  expect(crc32c(new Uint8Array())).toBe(0);
  const original = Buffer.from(JSON.stringify(session("private-cookie")));
  for (const checksum of [
    String((crc32c(original) + 1) >>> 0),
    "-1",
    "private-invalid-checksum",
  ]) {
    const store = createGoogleWafSessionStore("projects/test/secrets/waf", {
      fetch: fakeFetch((request) =>
        request.url.startsWith("http:")
          ? Response.json(
              { access_token: "synthetic-identity", token_type: "Bearer" },
              { headers: { "Metadata-Flavor": "Google" } },
            )
          : Response.json({
              payload: {
                data: original.toString("base64"),
                dataCrc32c: checksum,
              },
            }),
      ),
    });
    try {
      await store.read();
      throw new Error("Expected integrity rejection");
    } catch (error) {
      expect(error).toBeInstanceOf(WafSessionError);
      expect(String(error)).not.toContain("private-");
    }
  }
});

test("cancelled file publication preserves the previous session and cleans temporary files", async () => {
  await directory(async (directory) => {
    const path = join(directory, "session.json");
    const store = createFileWafSessionStore(path);
    await store.write(session("previous"));
    const cancelled = new AbortController();
    const write = store.write(session("unpublished"), {
      signal: cancelled.signal,
    });
    cancelled.abort("private-abort-reason");
    await expect(write).rejects.toThrow(
      "publish the protected WAF session file",
    );
    expect((await store.read()).token).toBe("previous");
    expect(await readdir(directory)).toEqual(["session.json"]);
    await expect(
      store.write(session("unpublished"), { signal: cancelled.signal }),
    ).rejects.toBeInstanceOf(WafSessionError);
    expect((await store.read()).token).toBe("previous");
  });
});

test("cancelled Google publication never starts after pre-abort or late identity completion", async () => {
  let calls = 0;
  let release: ((response: Response) => void) | undefined;
  const store = createGoogleWafSessionStore("projects/test/secrets/waf", {
    fetch: fakeFetch(() => {
      calls++;
      return new Promise<Response>((done) => {
        release = done;
      });
    }),
  });
  const controller = new AbortController();
  controller.abort("private-abort-reason");
  await expect(
    store.write(session(), { signal: controller.signal }),
  ).rejects.toBeInstanceOf(WafSessionError);
  expect(calls).toBe(0);
  const later = new AbortController();
  const write = store.write(session(), { signal: later.signal });
  later.abort("private-abort-reason");
  await expect(write).rejects.toThrow("publish the Google WAF session secret");
  release?.(
    Response.json(
      { access_token: "synthetic-identity", token_type: "Bearer" },
      { headers: { "Metadata-Flavor": "Google" } },
    ),
  );
  await Bun.sleep(1);
  expect(calls).toBe(1);
});

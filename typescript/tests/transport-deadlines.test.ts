import { expect, test } from "bun:test";
import { GenericHttpTransport } from "../packages/client/src/transport.js";

test("total time budget includes detached response body reads", async () => {
  let cancelled = false;
  let timer: ReturnType<typeof setTimeout>;
  const api = new GenericHttpTransport({
    baseUrl: "https://api.uspto.gov",
    sourceName: "USPTO",
    timeoutMs: 10,
    retryLimit: 0,
    fetch: (async () =>
      new Response(
        new ReadableStream({
          start(controller) {
            timer = setTimeout(() => {
              controller.enqueue(new TextEncoder().encode("late"));
              controller.close();
            }, 80);
          },
          cancel() {
            cancelled = true;
            clearTimeout(timer);
          },
        }),
      )) as unknown as typeof fetch,
  });
  await expect(api.text("GET", "/slow")).rejects.toMatchObject({
    code: "TIMEOUT",
  });
  expect(cancelled).toBe(true);
});

test("caller cancellation interrupts a detached response body read", async () => {
  let cancelled = false;
  let timer: ReturnType<typeof setTimeout>;
  const controller = new AbortController();
  const api = new GenericHttpTransport({
    baseUrl: "https://api.uspto.gov",
    sourceName: "USPTO",
    timeoutMs: 1000,
    retryLimit: 0,
    fetch: (async () =>
      new Response(
        new ReadableStream({
          start(stream) {
            timer = setTimeout(() => {
              stream.enqueue(new TextEncoder().encode("late"));
              stream.close();
            }, 80);
          },
          cancel() {
            cancelled = true;
            clearTimeout(timer);
          },
        }),
      )) as unknown as typeof fetch,
  });
  const request = api.text("GET", "/slow", { signal: controller.signal });
  setTimeout(() => controller.abort(), 10);
  await expect(request).rejects.toMatchObject({ code: "ABORTED" });
  expect(cancelled).toBe(true);
});

test("invalid configured credential headers do not escape in configuration errors", () => {
  try {
    new GenericHttpTransport({
      baseUrl: "https://api.uspto.gov",
      sourceName: "USPTO",
      headers: { Authorization: "synthetic-private\nsecret" },
    });
    throw new Error("Expected header validation failure");
  } catch (error) {
    expect(error).toMatchObject({ name: "ConfigurationError" });
    expect(String(error)).not.toContain("synthetic-private");
    expect(error).not.toHaveProperty("cause");
  }
});

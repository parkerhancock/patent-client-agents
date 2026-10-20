import { expect, test } from "bun:test";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ApplicationsClient } from "@patent-client-agents/client";
import { createServer } from "@patent-client-agents/mcp";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { useCassette } from "cassetter";
import ky from "ky";
import {
  applicationNumber,
  applicationRecordings,
  recorded,
} from "./cassettes.js";

test("Ky and Cassetter record real local HTTP, replay offline, reject mismatches, and scrub secrets", async () => {
  const directory = await mkdtemp(join(tmpdir(), "odp-cassette-"));
  const path = join(directory, "compatibility.yaml");
  const server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch: () =>
      Response.json(
        { count: 1 },
        { headers: { "Set-Cookie": "test-cookie-secret=value" } },
      ),
  });
  const url = `http://127.0.0.1:${server.port}/search`;
  const request = () =>
    ky
      .post(url, {
        headers: { "X-API-KEY": "test-key-secret" },
        json: { q: "test" },
        retry: 0,
      })
      .json();
  const matchOn = ["method", "uri", "json_body"] as (
    | "method"
    | "uri"
    | "json_body"
  )[];
  try {
    await useCassette(path, { recordMode: "all", matchOn }, async () => {
      expect(await request()).toEqual({ count: 1 });
    });
  } finally {
    await server.stop(true);
  }
  await useCassette(path, { recordMode: "none", matchOn }, async () => {
    expect(await request()).toEqual({ count: 1 });
    await expect(
      ky.post(url, { json: { q: "different" }, retry: 0 }),
    ).rejects.toThrow();
    await expect(fetch(`${url}/missing`)).rejects.toThrow();
  });
  const bytes = await readFile(path, "utf8");
  expect(bytes).not.toContain("test-key-secret");
  expect(bytes).not.toContain("test-cookie-secret");
});

test("recorded real ODP unauthenticated response replays without an API key", async () => {
  const response = await recorded("unauthenticated", () =>
    fetch(
      `https://api.uspto.gov/api/v1/patent/applications/${applicationNumber}`,
      {
        headers: { Accept: "application/json" },
        redirect: "error",
      },
    ),
  );
  expect([401, 403]).toContain(response.status);
  expect(response.headers.get("content-type")).toContain("application/json");
});

test("successful real ODP application cassettes replay without credentials or network access", async () => {
  const results = await applicationRecordings("none");
  expect(results.search.count).toBeGreaterThan(0);
  expect(results.application.patentBag[0]?.applicationNumberText).toBe(
    applicationNumber,
  );
  expect(Array.isArray(results.documents.documents)).toBe(true);
});

test("MCP application tools return real ODP records through the library and cassette transport", async () => {
  const server = createServer({
    client: new ApplicationsClient({
      apiKey: "replay-placeholder",
      retryLimit: 0,
    }),
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const search = await recorded("search", () =>
      client.callTool<{ items: { applicationNumberText: string }[] }>(
        "search_applications",
        {
          query: `applicationNumberText:${applicationNumber}`,
          limit: 1,
        },
      ),
    );
    expect(search.structuredContent?.items[0]?.applicationNumberText).toBe(
      applicationNumber,
    );
    const application = await recorded("application", () =>
      client.callTool<{ items: { applicationNumberText: string }[] }>(
        "get_application",
        {
          application_numbers: applicationNumber,
        },
      ),
    );
    expect(application.structuredContent?.items[0]?.applicationNumberText).toBe(
      applicationNumber,
    );
    const history = await recorded("documents", () =>
      client.callTool<{ items: unknown[]; more_available: boolean }>(
        "list_file_history",
        {
          application_number: applicationNumber,
          limit: 10,
        },
      ),
    );
    expect(history.structuredContent?.items).toHaveLength(10);
    expect(history.structuredContent?.more_available).toBe(true);
  } finally {
    await client.close();
    await server.close();
  }
});

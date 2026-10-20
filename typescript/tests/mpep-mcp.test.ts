import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import {
  CorpusError,
  MPEP_RELEASE_CHECK,
  type MpepClient,
} from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { FastMCP } from "@prefecthq/fastmcp-ts/server";
import {
  DownloadStore,
  downloadContext,
} from "../packages/mcp/src/downloads.js";
import {
  MPEP_CORPUS_STATUS_URI,
  registerMpepTools,
} from "../packages/mcp/src/mpep.js";

async function fixture(denied = false) {
  const status: Awaited<ReturnType<MpepClient["getCorpusStatus"]>> = {
    available: true,
    source_version: "unknown",
    corpus_version: "unknown",
    schema_version: 2,
    section_count: 2,
    snapshot_date: null,
    corpus_synced_at: null,
    edition: null,
    revision: null,
    publication_date: null,
    substantive_cutoff_date: null,
    build_id: "build-one",
    interim_updates_coverage: "not_included",
    artifact_sha256: "a".repeat(64),
    file_sha256: "a".repeat(64),
    compression: "none",
    metadata: { source_version: "current" },
    source_url: "https://mpep.uspto.gov",
    release_check: { ...MPEP_RELEASE_CHECK, comparison: "unknown" },
  };
  const provenance = {
    source_url: "https://mpep.uspto.gov/RDMS/MPEP/result",
    source_name: "USPTO MPEP",
    retrieved_at: null,
    accessed_at: "2026-10-20T12:00:00.000Z",
    cache_hit: true as const,
    corpus_synced_at: null,
    corpus_version: "unknown",
  };
  const calls: unknown[] = [];
  let active = 0;
  let peak = 0;
  const corpus: Pick<MpepClient, "search" | "getSection" | "getCorpusStatus"> =
    {
      async getCorpusStatus() {
        return { ...status };
      },
      async search(options) {
        calls.push(options);
        const offset = options.offset ?? 0;
        return {
          hits: [
            {
              title: `${offset ? "2143" : "2106"} - Synthetic section`,
              section_number: offset ? "2143" : "2106",
              href: `section-${offset}.html`,
              path: ["Chapter 2100"],
              result_url:
                "https://mpep.uspto.gov/RDMS/MPEP/result?href=test.html",
              snippet: "s".repeat(600),
            },
          ],
          has_more: offset === 0,
          offset,
          limit: options.limit ?? 25,
          provenance,
          corpus: { ...status },
        };
      },
      async getSection(ref, options) {
        calls.push({ ref, ...options });
        active++;
        peak = Math.max(active, peak);
        await Bun.sleep(1);
        active--;
        if (ref === "missing")
          throw new CorpusError("SECTION_NOT_FOUND", "Missing section");
        if (ref === "corrupt")
          throw new CorpusError("INVALID_CORPUS", "Invalid corpus");
        return {
          href: `${ref}.html`,
          section_number: ref,
          title: "Synthetic section",
          html: "<p>Synthetic full section</p>",
          text:
            ref === "large"
              ? "x".repeat(32001)
              : ref === "medium"
                ? "m".repeat(20000)
                : "Synthetic full section",
          version: "unknown",
          source_url: "https://mpep.uspto.gov/RDMS/MPEP/result?href=test.html",
          content_sha256: "b".repeat(64),
          section_revision: null,
          corpus_metadata: { source_version: "current" },
          provenance,
        };
      },
    };
  const server = new FastMCP({ name: "mpep-tools-test", version: "1" });
  const store = new DownloadStore();
  server.use({
    onCallTool: (_context, next) => downloadContext.run({ store }, next),
  });
  registerMpepTools(
    server,
    corpus,
    denied
      ? () => {
          throw new Error("Access denied");
        }
      : undefined,
  );
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    status,
    calls,
    peak: () => peak,
    client,
    async close() {
      await client.close();
      await server.close();
      await store.close();
    },
  };
}

test("MPEP actual MCP search preserves corpus provenance and binds query/options/snapshot cursors", async () => {
  const api = await fixture();
  try {
    const tools = await api.client.listTools();
    expect(tools.map((tool) => tool.name)).toEqual([
      "search_mpep",
      "get_mpep_section",
    ]);
    expect(tools.every((tool) => tool.annotations?.readOnlyHint)).toBe(true);
    const first = await api.client.callTool<{
      next_cursor: string;
      items: { snippet: string; result_url?: string }[];
      provenance: Record<string, unknown>;
      summary: string;
    }>("search_mpep", {
      query: "patent",
      limit: 1,
      syntax: "and",
      sort: "outline",
      version: "current",
    });
    expect(api.calls[0]).toEqual({
      query: "patent",
      limit: 1,
      offset: 0,
      syntax: "and",
      sort: "outline",
      version: "current",
    });
    expect(first.structuredContent?.items[0]?.snippet.length).toBe(400);
    expect(first.structuredContent?.items[0]?.result_url).toBeUndefined();
    expect(first.structuredContent?.provenance).toMatchObject({
      cache_hit: true,
      retrieved_at: null,
      accessed_at: "2026-10-20T12:00:00.000Z",
      corpus_synced_at: null,
      corpus_version: "unknown",
      connector_version: "0.1.0",
    });
    expect(first.structuredContent?.summary).toContain("not_included");
    expect(first.structuredContent?.summary).toContain(
      "not a live currency check",
    );
    expect(first.structuredContent?.summary).toContain(
      "Release comparison unknown",
    );
    const cursor = first.structuredContent?.next_cursor;
    const parameters = {
      query: "patent",
      limit: 1,
      syntax: "and",
      sort: "outline",
      cursor,
    };
    // Lossless repackaging changes the file, but preserves decoded snapshot identity.
    api.status.file_sha256 = "c".repeat(64);
    api.status.compression = "zstd";
    const next = await api.client.callTool<{ more_available: boolean }>(
      "search_mpep",
      parameters,
    );
    expect(api.calls[1]).toMatchObject({ offset: 1 });
    expect(next.structuredContent?.more_available).toBe(false);
    for (const changed of [
      { query: "changed" },
      { limit: 2 },
      { version: "different" },
      { sort: "relevance" },
    ])
      await expect(
        api.client.callTool("search_mpep", { ...parameters, ...changed }),
      ).rejects.toThrow("different query or corpus");
    api.status.build_id = "build-two";
    await expect(
      api.client.callTool("search_mpep", parameters),
    ).rejects.toThrow("different query or corpus");
    await expect(
      api.client.callTool("search_mpep", { query: "patent", cursor: "bad" }),
    ).rejects.toThrow("Invalid pagination cursor");
    const full = await api.client.callTool<{ items: { result_url: string }[] }>(
      "search_mpep",
      { query: "patent", full: true },
    );
    expect(full.structuredContent?.items[0]?.result_url).toStartWith("https:");
  } finally {
    await api.close();
  }
});

test("MPEP actual MCP gets ordered sections and delivers HTML or large text as private artifacts", async () => {
  const api = await fixture();
  try {
    const response = await api.client.callTool<{
      items: { section_number: string; text: string; html?: string }[];
    }>("get_mpep_section", { section: ["2143", "2106"] });
    expect(
      response.structuredContent?.items.map((item) => item.section_number),
    ).toEqual(["2143", "2106"]);
    expect(response.structuredContent?.items[0]?.text).toBe(
      "Synthetic full section",
    );
    expect(response.structuredContent?.items[0]?.html).toBeUndefined();
    for (const [section, format, content] of [
      ["2106", "html", "<p>Synthetic full section</p>"],
      ["large", "text", "x".repeat(32001)],
    ]) {
      const result = await api.client.callTool<{
        items: {
          document: { file_path: string; provenance: Record<string, unknown> };
          text?: string;
          html?: string;
        }[];
      }>("get_mpep_section", { section, format });
      const item = result.structuredContent?.items[0];
      expect(await readFile(item?.document.file_path ?? "", "utf8")).toBe(
        content ?? "",
      );
      expect(item?.text).toBeUndefined();
      expect(item?.html).toBeUndefined();
      expect(item?.document.provenance).toMatchObject({
        corpus_version: "unknown",
        corpus_synced_at: null,
      });
    }
    const resource = await api.client.readResource(MPEP_CORPUS_STATUS_URI);
    const content = resource[0];
    expect(
      JSON.parse(content && "text" in content ? content.text : "{}"),
    ).toMatchObject({
      source_version: "unknown",
      interim_updates_coverage: "not_included",
      available: true,
    });
  } finally {
    await api.close();
  }
});

test("MPEP portfolio fetch retains ordered not-found records but propagates corpus errors", async () => {
  const api = await fixture();
  try {
    const result = await api.client.callTool<{
      items: { section_number?: string; error?: { code: string } }[];
    }>("get_mpep_section", { section: ["missing", "2106", "missing"] });
    expect(result.structuredContent?.items).toMatchObject([
      { error: { code: "NOT_FOUND" } },
      { section_number: "2106" },
      { error: { code: "NOT_FOUND" } },
    ]);
    await expect(
      api.client.callTool("get_mpep_section", { section: "missing" }),
    ).rejects.toThrow("Missing section");
    await expect(
      api.client.callTool("get_mpep_section", {
        section: ["missing", "missing"],
      }),
    ).rejects.toThrow("Missing section");
    await expect(
      api.client.callTool("get_mpep_section", { section: ["2106", "corrupt"] }),
    ).rejects.toThrow("Invalid corpus");
  } finally {
    await api.close();
  }
});

test("MPEP portfolios bound fetch concurrency and total inline text", async () => {
  const api = await fixture();
  try {
    await api.client.callTool("get_mpep_section", {
      section: Array.from({ length: 12 }, (_, index) => String(2100 + index)),
    });
    expect(api.peak()).toBe(4);
    const result = await api.client.callTool<{
      items: { text?: string; document?: { file_path: string } }[];
    }>("get_mpep_section", { section: ["medium", "medium"] });
    expect(result.structuredContent?.items[0]?.text).toHaveLength(20000);
    expect(result.structuredContent?.items[1]?.text).toBeUndefined();
    expect(
      await readFile(
        result.structuredContent?.items[1]?.document?.file_path ?? "",
        "utf8",
      ),
    ).toHaveLength(20000);
  } finally {
    await api.close();
  }
});

test("MPEP actual MCP applies the same authorization to tools and corpus status", async () => {
  const api = await fixture(true);
  try {
    expect(await api.client.listTools()).toHaveLength(0);
    expect(await api.client.listResources()).toHaveLength(0);
    await expect(
      api.client.callTool("search_mpep", { query: "patent" }),
    ).rejects.toThrow();
    await expect(
      api.client.callTool("get_mpep_section", { section: "2106" }),
    ).rejects.toThrow();
    await expect(
      api.client.readResource(MPEP_CORPUS_STATUS_URI),
    ).rejects.toThrow();
    expect(api.calls).toHaveLength(0);
  } finally {
    await api.close();
  }
});

import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import {
  AssignmentCenterClient,
  TrademarkAssignmentClient,
  TsdrClient,
} from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { FastMCP } from "@prefecthq/fastmcp-ts/server";
import {
  DownloadStore,
  downloadContext,
} from "../packages/mcp/src/downloads.js";
import { registerRegisterTools } from "../packages/mcp/src/registers.js";

async function fixture() {
  const requests: URL[] = [];
  const fetcher = (async (input, init) => {
    const url = new URL(new Request(input, init).url);
    requests.push(url);
    if (url.pathname.includes("caseMultiStatus"))
      return Response.json({
        transactionList: (url.searchParams.get("ids") ?? "")
          .split(",")
          .map((id) => ({
            searchId: id,
            trademarks: [{ status: { markElement: "SYNTHETIC" } }],
          })),
      });
    if (url.pathname.endsWith("bundle.xml"))
      return new Response("<Bundle>synthetic</Bundle>");
    if (url.pathname.includes("bundle."))
      return new Response("synthetic bundle bytes");
    return Response.json({
      trademarks: [{ status: { markElement: "SYNTHETIC" } }],
    });
  }) as typeof fetch;
  const store = new DownloadStore();
  const server = new FastMCP({ name: "tsdr-options-test", version: "1" });
  server.use({
    onCallTool: (_context, next) => downloadContext.run({ store }, next),
  });
  registerRegisterTools(server, {
    assignments: new AssignmentCenterClient({ fetch: fetcher }),
    trademarkAssignments: new TrademarkAssignmentClient({ fetch: fetcher }),
    tsdr: new TsdrClient({
      apiKey: "synthetic",
      retryLimit: 0,
      fetch: fetcher,
    }),
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  return {
    client,
    requests,
    async close() {
      await client.close();
      await server.close();
      await store.close();
    },
  };
}

test("actual MCP batches preserve identifier types, infer prefixes and forward status ranges", async () => {
  const api = await fixture();
  try {
    for (const type of ["sn", "rn", "ir", "ref"]) {
      const id = type === "ref" ? "Z1231384" : "12345";
      const response = await api.client.callTool<{
        items: { markText: string }[];
      }>("get_trademark", {
        serial_number: [id],
        identifier_type: type,
        from: "1",
        to: "2",
      });
      expect(response.structuredContent?.items[0]?.markText).toBe("SYNTHETIC");
      expect(api.requests.at(-1)?.pathname).toBe(
        `/ts/cd/caseMultiStatus/${type}`,
      );
      expect(api.requests.at(-1)?.searchParams.get("ids")).toBe(id);
      expect(api.requests.at(-1)?.searchParams.get("from")).toBe("1");
      expect(api.requests.at(-1)?.searchParams.get("to")).toBe("2");
      await api.client.callTool("get_trademark", {
        serial_number: [`${type}${id}`],
      });
      expect(api.requests.at(-1)?.pathname).toBe(
        `/ts/cd/caseMultiStatus/${type}`,
      );
    }
    await api.client.callTool("get_trademark", { serial_number: "rn12345" });
    expect(api.requests.at(-1)?.pathname).toBe(
      "/ts/cd/casestatus/rn12345/info",
    );
  } finally {
    await api.close();
  }
});

test("actual MCP exposes filtered multicase XML and binary bundles as artifacts", async () => {
  const api = await fixture();
  const filters = {
    date: "2026-10-20",
    from_date: "2026-10-01",
    to_date: "2026-10-20",
    type: "NOTICE",
    category: "INCOMING",
    sort: "asc",
  };
  try {
    for (const format of ["xml", "pdf", "zip"]) {
      const response = await api.client.callTool<{
        file_path?: string;
        items?: { file_path: string }[];
      }>(format === "xml" ? "get_trademark" : "download_trademark_documents", {
        serial_number: ["refZ1231384"],
        bundle_filters: filters,
        ...(format === "xml" ? { view: "bundle_xml" } : { format }),
      });
      const url = api.requests.at(-1);
      expect(url?.pathname).toBe(`/ts/cd/casedocs/bundle.${format}`);
      expect(Object.fromEntries(url?.searchParams ?? [])).toEqual({
        ref: "Z1231384",
        date: filters.date,
        fromDate: filters.from_date,
        toDate: filters.to_date,
        type: filters.type,
        category: filters.category,
        sort: filters.sort,
      });
      const path =
        response.structuredContent?.file_path ??
        response.structuredContent?.items?.[0]?.file_path;
      expect(path).toBeString();
      expect(await readFile(path ?? "", "utf8")).toBe(
        format === "xml"
          ? "<Bundle>synthetic</Bundle>"
          : "synthetic bundle bytes",
      );
      expect(JSON.stringify(response.structuredContent)).not.toContain(
        "synthetic bundle bytes",
      );
    }
    for (const type of ["sn", "rn", "ir", "ref"]) {
      const id = type === "ref" ? "Z1231384" : "12345";
      await api.client.callTool("download_trademark_documents", {
        serial_number: [id],
        identifier_type: type,
        format: "zip",
      });
      expect(
        Object.fromEntries(api.requests.at(-1)?.searchParams ?? []),
      ).toEqual({
        [type]: id,
      });
    }
  } finally {
    await api.close();
  }
});

test("invalid or incompatible MCP batch options fail before HTTP", async () => {
  const api = await fixture();
  try {
    for (const [name, input] of [
      ["get_trademark", { serial_number: ["rn12345", "sn67890"] }],
      ["get_trademark", { serial_number: ["rn12345"], identifier_type: "ir" }],
      ["get_trademark", { serial_number: "rn12345", identifier_type: "rn" }],
      ["get_trademark", { serial_number: "12345", from: "1" }],
      ["get_trademark", { serial_number: "12345", bundle_filters: {} }],
      ["get_trademark", { serial_number: ["not-a-numeric-identifier"] }],
      ["get_trademark", { serial_number: ["12345"], bundle_filters: {} }],
      [
        "get_trademark",
        { serial_number: ["12345"], view: "bundle_xml", from: "1" },
      ],
      ["get_trademark", { serial_number: ["12345"], view: "xml" }],
      [
        "download_trademark_documents",
        { serial_number: ["rn12345", "ir67890"] },
      ],
      [
        "download_trademark_documents",
        { serial_number: ["rn12345"], identifier_type: "sn" },
      ],
      [
        "download_trademark_documents",
        { serial_number: "12345", bundle_filters: {} },
      ],
      [
        "download_trademark_documents",
        { serial_number: ["12345"], target: "status" },
      ],
      [
        "download_trademark_documents",
        { serial_number: ["12345"], bundle_filters: { from_date: "" } },
      ],
      [
        "download_trademark_documents",
        { serial_number: ["12345"], bundle_filters: { ref: "different" } },
      ],
    ] as const)
      await expect(api.client.callTool(name, input)).rejects.toThrow();
    expect(api.requests).toHaveLength(0);
  } finally {
    await api.close();
  }
});

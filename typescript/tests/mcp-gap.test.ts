import { expect, test } from "bun:test";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";
import {
  detailEnvelopeSchema,
  listEnvelopeSchema,
} from "../packages/mcp/src/shared.js";

const provenance = {
  source_url: "https://api.uspto.gov/test",
  source_name: "USPTO Open Data Portal",
  retrieved_at: new Date().toISOString(),
  cache_hit: false,
  connector_version: "0.1.0",
} as const;
test("detail output schemas cannot swallow list envelopes or incomplete artifacts", () => {
  const list = {
    summary: "One record",
    items: [{ id: "1" }],
    next_cursor: null,
    more_available: false,
    provenance,
  };
  expect(detailEnvelopeSchema.safeParse(list).success).toBe(false);
  expect(
    z.union([detailEnvelopeSchema, listEnvelopeSchema]).parse(list),
  ).toEqual(list);
  expect(detailEnvelopeSchema.safeParse({ provenance }).success).toBe(false);
  expect(
    detailEnvelopeSchema.safeParse({ summary: "Detail", provenance }).success,
  ).toBe(false);
  expect(
    detailEnvelopeSchema.parse({
      summary: "Detail",
      details: { id: "1" },
      provenance,
    }),
  ).toHaveProperty("details");
});
test("application MCP retains requested facets and forwards source document-date filters", async () => {
  const facets = { applicationType: ["Utility"] };
  let seenDates: unknown;
  const server = createServer({
    client: {
      search: async (options) => {
        expect(options?.facets).toEqual(["applicationType"]);
        return {
          count: 1,
          patentBag: [{ applicationNumberText: "14412875" }],
          facetResults: facets,
          provenance,
        };
      },
      get: async () => ({ count: 0, patentBag: [], provenance }),
      getDocuments: async (_number, options) => {
        seenDates = options;
        return { documents: [], provenance };
      },
    },
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const search = await client.callTool<{ facets: unknown }>(
      "search_applications",
      { facets: ["applicationType"] },
    );
    expect(search.structuredContent?.facets).toEqual(facets);
    await client.callTool("list_file_history", {
      application_number: "14412875",
      official_date_from: "2020-01-01",
      official_date_to: "2021-01-01",
    });
    expect(seenDates).toMatchObject({
      officialDateFrom: "2020-01-01",
      officialDateTo: "2021-01-01",
      includeAssociated: false,
    });
  } finally {
    await client.close();
    await server.close();
  }
});

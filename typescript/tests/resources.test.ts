import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { FastMCP } from "@prefecthq/fastmcp-ts/server";
import {
  BULKDATA_PRODUCT_GUIDE_RESOURCE_URI,
  CURRENT_ODP_SWAGGER_RESOURCE_URI,
  getBulkdataResponseSchema,
  getCurrentOdpSwaggerSpec,
  getOdpSwaggerSpec,
  getPatentDataSchema,
  getPetitionDecisionSchema,
  getProductGuide,
  getSearchableIndexesResource,
  getSearchGuide,
  ODP_FIELD_CATALOG,
  ODP_SEARCH_GUIDE,
  ODP_STATUS_CODES,
  ODP_SWAGGER_RESOURCE_URI,
  USPTO_DOCUMENTATION_RESOURCES,
} from "../packages/client/src/uspto-resources.js";
import { registerUsptoResources } from "../packages/mcp/src/resources.js";

const source = (path: string) =>
  readFileSync(
    new URL(`../../src/patent_client_agents/${path}`, import.meta.url),
    "utf8",
  );

test("resources preserve copied Python reference content with explicit historical labels", () => {
  expect(getSearchGuide()).toContain(
    source("uspto_publications/docs/search_guide.md"),
  );
  expect(getSearchableIndexesResource()).toContain(
    source("uspto_publications/docs/searchable_indexes.md"),
  );
  expect(ODP_STATUS_CODES).toContain(source("uspto_odp/data/status_codes.md"));
  for (const text of [
    getSearchGuide(),
    getSearchableIndexesResource(),
    ODP_STATUS_CODES,
    ODP_FIELD_CATALOG,
    ODP_SEARCH_GUIDE,
  ]) {
    expect(text).toContain("Historical Python-package snapshot");
    expect(text).toContain("original content date is unverified");
  }
  expect(getProductGuide()).toContain(
    source("uspto_bulkdata/data/2025_bulkdata_product_guide.md"),
  );
  expect(getProductGuide()).toContain("not a current product catalog");
});

test("bundled JSON schemas retain valid original schema bytes and freshness metadata", () => {
  for (const [name, read] of [
    ["bulkdata-response-schema.json", getBulkdataResponseSchema],
    ["patent-data-schema.json", getPatentDataSchema],
    ["petition-decision-schema.json", getPetitionDecisionSchema],
  ] as const) {
    expect(read()).toBe(source(`uspto_bulkdata/data/${name}`));
    expect(JSON.parse(read())).toBeObject();
  }
  expect(
    USPTO_DOCUMENTATION_RESOURCES.filter(
      (r) => r.mimeType === "application/schema+json",
    ).every((r) => r.description.includes("Historical")),
  ).toBe(true);
});

test("current main index and historical Swagger are separate and explicitly labeled", () => {
  expect(getOdpSwaggerSpec()).toContain(
    source("uspto_odp/data/odp_swagger.yaml"),
  );
  expect(getOdpSwaggerSpec()).toContain(
    "Historical Python-package OpenAPI snapshot",
  );
  expect(getCurrentOdpSwaggerSpec()).toContain("INCOMPLETE BUNDLE");
  expect(getCurrentOdpSwaggerSpec()).toContain("2026-10-20");
  expect(getCurrentOdpSwaggerSpec()).toContain("./odp-common-base.yaml");
  expect(ODP_SWAGGER_RESOURCE_URI).not.toBe(CURRENT_ODP_SWAGGER_RESOURCE_URI);
});

test("MCP advertises all ten parity URIs plus current index and reads library content", async () => {
  const server = new FastMCP({ name: "resource-test", version: "0.1.0" });
  registerUsptoResources(server);
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const resources = await client.listResources();
    expect(resources).toHaveLength(11);
    expect(new Set(resources.map((r) => r.uri)).size).toBe(11);
    expect(resources.map((r) => r.uri)).toContain(
      BULKDATA_PRODUCT_GUIDE_RESOURCE_URI,
    );
    for (const resource of USPTO_DOCUMENTATION_RESOURCES) {
      const content = await client.readResource(resource.uri);
      expect(content).toHaveLength(1);
      expect(content[0]).toMatchObject({
        uri: resource.uri,
        mimeType: resource.mimeType,
        text: resource.read(),
      });
    }
  } finally {
    await client.close();
  }
});

test("MCP resource authorization denies direct reads and hides resources", async () => {
  const server = new FastMCP({ name: "resource-auth-test", version: "0.1.0" });
  registerUsptoResources(server, () => {
    throw new Error("Resource access denied");
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    expect(await client.listResources()).toHaveLength(0);
    await expect(
      client.readResource(ODP_SWAGGER_RESOURCE_URI),
    ).rejects.toThrow();
  } finally {
    await client.close();
  }
});

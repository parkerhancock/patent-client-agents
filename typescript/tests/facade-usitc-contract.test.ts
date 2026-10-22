import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { EdisClient } from "../packages/client/src/index.js";
import { UNPORTED_FACADE_TOOLS } from "../packages/mcp/src/facade/index.js";
import { createServer } from "../packages/mcp/src/index.js";

/**
 * The Python facade exported with a placeholder USITC_EDIS_TOKEN (EDIS
 * enabled) is the contract for a server that has an EDIS token: the
 * EDIS-less tools plus search_usitc_investigations, search_usitc_documents
 * and list_usitc_attachments, forum='usitc' on get_litigation and the
 * usitc_* sources on download_document.
 */
type JsonSchema = {
  properties?: Record<string, JsonSchema>;
  required?: string[];
  enum?: unknown[];
  anyOf?: JsonSchema[];
};
const load = (name: string) =>
  JSON.parse(
    readFileSync(join(import.meta.dir, "fixtures", "facade", name), "utf8"),
  ) as { name: string; inputSchema: JsonSchema }[];
const edisContract = new Map(
  load("python-facade-tools-edis.json").map((tool) => [
    tool.name,
    tool.inputSchema,
  ]),
);
const plainContract = new Map(
  load("python-facade-tools.json").map((tool) => [tool.name, tool.inputSchema]),
);
function enums(schema: JsonSchema | undefined): string[] {
  if (!schema) return [];
  return [
    ...(schema.enum ?? []).map(String),
    ...(schema.anyOf ?? []).flatMap(enums),
  ].sort();
}

async function curatedTools(edis: boolean) {
  const server = createServer({
    toolset: "curated",
    clients: edis ? { edis: new EdisClient({ token: "placeholder" }) } : {},
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    return await client.listTools();
  } finally {
    await client.close();
    await server.close();
  }
}

function mismatches(
  tools: Awaited<ReturnType<typeof curatedTools>>,
  contract: Map<string, JsonSchema>,
) {
  const problems: string[] = [];
  const served = new Set(tools.map((tool) => tool.name));
  const unported = new Set<string>(UNPORTED_FACADE_TOOLS);
  for (const name of contract.keys())
    if (!served.has(name) && !unported.has(name))
      problems.push(`${name}: not served`);
  for (const tool of tools) {
    const expected = contract.get(tool.name);
    if (!expected) {
      problems.push(`${tool.name}: not in the Python contract`);
      continue;
    }
    const actual = tool.inputSchema as JsonSchema;
    const names = (schema: JsonSchema) =>
      Object.keys(schema.properties ?? {}).sort();
    if (JSON.stringify(names(actual)) !== JSON.stringify(names(expected)))
      problems.push(`${tool.name}: parameters ${names(actual)}`);
    const required = (schema: JsonSchema) =>
      [...(schema.required ?? [])].sort();
    if (JSON.stringify(required(actual)) !== JSON.stringify(required(expected)))
      problems.push(`${tool.name}: required ${required(actual)}`);
    for (const [parameter, schema] of Object.entries(
      expected.properties ?? {},
    )) {
      const want = enums(schema);
      const got = enums(actual.properties?.[parameter]);
      if (want.length && JSON.stringify(got) !== JSON.stringify(want))
        problems.push(`${tool.name}.${parameter}: enum ${got} != ${want}`);
    }
  }
  return problems;
}

test("with an EDIS client the curated surface matches the EDIS-enabled Python facade", async () => {
  const tools = await curatedTools(true);
  expect(mismatches(tools, edisContract)).toEqual([]);
  const names = tools.map((tool) => tool.name);
  for (const name of [
    "search_usitc_investigations",
    "search_usitc_documents",
    "list_usitc_attachments",
  ])
    expect(names).toContain(name);
});

test("without an EDIS client the surface stays the EDIS-less contract", async () => {
  const tools = await curatedTools(false);
  expect(mismatches(tools, plainContract)).toEqual([]);
  expect(tools.map((tool) => tool.name).join(" ")).not.toContain("usitc");
});

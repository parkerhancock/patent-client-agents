import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { DpmaStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged DPMA statutes artifact through the library and the default MCP and facade wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error(
    "Usage: bun scripts/verify-dpma-statutes.ts --file FILE.db.zst",
  );
  process.exit(2);
}
const corpusPath = resolve(args[1]);
const manifest = manifestSchema.parse(
  JSON.parse(await readFile(`${corpusPath}.manifest.json`, "utf8")),
);
process.env.DPMA_STATUTES_CORPUS_PATH = corpusPath;
process.env.DPMA_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.DPMA_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new DpmaStatutesClient();
const report: Record<string, unknown> = {};
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error("DPMA statutes: artifact status or pins did not verify.");
  const section = await library.getSectionByCitation("§ 139 PatG");
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    statutes: await library.listStatutes(),
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    patg_139_title: section.title,
  });
} finally {
  library.close();
}

type Envelope = {
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available: boolean;
};
const cases = {
  // Default server wiring reads the configured path; no reader is injected.
  full: [
    ["search_dpma_statutes", { query: "Unterlassung" }],
    [
      "get_dpma_section",
      { citation: ["§ 1 PatG", "§ 14 MarkenG", "§ 97 UrhG", "§ 4 PatG"] },
    ],
  ],
  curated: [
    ["search_legal_reference", { corpus: "dpma", query: "Unterlassung" }],
    ["get_legal_reference", { corpus: "dpma", identifier: "§ 2 GeschGehG" }],
  ],
} as const;
for (const toolset of ["full", "curated"] as const) {
  const server = createServer({ toolset });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const [search, get] = cases[toolset];
    const hits = await client.callTool<Envelope>(search[0], { ...search[1] });
    const sections = await client.callTool<Envelope>(get[0], { ...get[1] });
    const items = sections.structuredContent?.items ?? [];
    if (!hits.structuredContent?.items.length || !items.length)
      throw new Error(`DPMA statutes (${toolset}): MCP search or get failed.`);
    report[`mcp_${toolset}`] = {
      unterlassung_hits: hits.structuredContent.items.map(
        (item) => `${item.statute} ${item.section}`,
      ),
      sections: items.map((item) => `${item.statute} ${item.section}`),
      not_found: sections.structuredContent?.not_found,
    };
  } finally {
    await client.close();
    await server.close();
  }
}
console.log(JSON.stringify(report, null, 2));

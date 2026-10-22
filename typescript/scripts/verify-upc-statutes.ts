import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { UpcStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged UPC statutes artifact through the library and the default MCP and facade wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error("Usage: bun scripts/verify-upc-statutes.ts --file FILE.db.zst");
  process.exit(2);
}
const corpusPath = resolve(args[1]);
const manifest = manifestSchema.parse(
  JSON.parse(await readFile(`${corpusPath}.manifest.json`, "utf8")),
);
process.env.UPC_STATUTES_CORPUS_PATH = corpusPath;
process.env.UPC_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.UPC_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new UpcStatutesClient();
const report: Record<string, unknown> = {};
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error("UPC statutes: artifact status or pins did not verify.");
  const instruments = (await library.listInstruments()).instruments;
  const rop = await library.getInstrument("rules of procedure", {
    language: "de",
  });
  if (!rop) throw new Error("UPC statutes: RoP (de) is missing.");
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    instrument_count: status.instrument_count,
    instruments: instruments.map(
      (item) => `${item.instrument}/${item.language}`,
    ),
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    rop_de_characters: rop.text.length,
    rop_de_sha256: rop.content_sha256,
  });
} finally {
  library.close();
}

type Envelope = {
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available: boolean;
};
for (const toolset of ["full", "curated"] as const) {
  // Default server wiring reads the configured path; no reader is injected.
  const server = createServer({ toolset });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const search = await client.callTool<Envelope>("search_upc_statutes", {
      query: "opt-out withdrawal",
      instrument: "rop",
    });
    const article = await client.callTool<Envelope>("search_upc_statutes", {
      query: "Article 33",
      per_page: 3,
    });
    const sections = await client.callTool<Envelope>("get_upc_section", {
      instrument: ["upca", "rop", "fees", "coc"],
    });
    const items = sections.structuredContent?.items ?? [];
    if (
      !search.structuredContent?.items.length ||
      !article.structuredContent?.items.length ||
      items.length !== 3
    )
      throw new Error(`UPC statutes (${toolset}): MCP search or get failed.`);
    report[`mcp_${toolset}`] = {
      opt_out_rop_hits: search.structuredContent.items.length,
      article_33_first: article.structuredContent.items[0]?.instrument,
      article_33_more: article.structuredContent.more_available,
      sections: items.map((item) =>
        item.text === undefined
          ? `${item.instrument}: artifact`
          : `${item.instrument}: inline`,
      ),
      not_found: sections.structuredContent?.not_found,
    };
  } finally {
    await client.close();
    await server.close();
  }
}
console.log(JSON.stringify(report, null, 2));

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { InpiBrStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged INPI Brazil LPI artifact through the library and the default MCP wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error(
    "Usage: bun scripts/verify-inpi-br-statutes.ts --file FILE.db.zst",
  );
  process.exit(2);
}
const corpusPath = resolve(args[1]);
const manifest = manifestSchema.parse(
  JSON.parse(await readFile(`${corpusPath}.manifest.json`, "utf8")),
);
process.env.INPI_BR_STATUTES_CORPUS_PATH = corpusPath;
process.env.INPI_BR_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.INPI_BR_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new InpiBrStatutesClient();
const report: Record<string, unknown> = {};
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error(
      "INPI Brazil statutes: artifact status or pins did not verify.",
    );
  if (status.section_count !== 248 || !status.latest_amendment)
    throw new Error("INPI Brazil statutes: unexpected row count or metadata.");
  const art195 = await library.getSection("Art. 195(XI) LPI");
  const lettered = await library.getSection("Art. 229-C");
  const hits = await library.search({ query: "dados confidenciais" });
  const english = await library.search({ query: "unfair competition" });
  if (
    !art195.text_pt.includes("XI - divulga") ||
    !art195.text_en?.includes("XI. divulges") ||
    lettered.text_en !== null ||
    !hits.hits.length ||
    !english.hits.some((hit) => hit.href === "art195")
  )
    throw new Error("INPI Brazil statutes: library reads did not verify.");
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    latest_amendment: status.latest_amendment,
    english_version: status.english_version,
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    versions: await library.listVersions(),
    art195: `${art195.title_section}; ${art195.text_pt.split("\n").length} PT lines, ${art195.text_en?.split("\n").length} EN lines`,
    art229c: lettered.text_pt,
    dados_confidenciais: hits.hits.map((hit) => hit.article_number),
  });
} finally {
  library.close();
}

type Envelope = {
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available: boolean;
};
// Default server wiring reads the configured path; no reader is injected.
const server = createServer();
const client = await Client.connect(server, {
  versionNegotiation: { mode: "legacy" },
});
try {
  const hits = await client.callTool<Envelope>("search_inpi_br_statutes", {
    query: "concorrência desleal",
  });
  const sections = await client.callTool<Envelope>("get_inpi_br_section", {
    citation: ["Art. 6", "Art. 125", "Art. 195", "Art. 999"],
  });
  const items = sections.structuredContent?.items ?? [];
  if (!hits.structuredContent?.items.length || items.length !== 3)
    throw new Error("INPI Brazil statutes: MCP search or get failed.");
  report.mcp_full = {
    concorrencia_desleal_hits: hits.structuredContent.items.map(
      (item) => item.article_number,
    ),
    sections: items.map((item) => item.article_number),
    not_found: sections.structuredContent?.not_found,
  };
} finally {
  await client.close();
  await server.close();
}
console.log(JSON.stringify(report, null, 2));

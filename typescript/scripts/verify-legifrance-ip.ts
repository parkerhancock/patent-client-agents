import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { LegifranceIpClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged Légifrance IP artifact through the library and the default MCP wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error(
    "Usage: bun scripts/verify-legifrance-ip.ts --file FILE.db.zst",
  );
  process.exit(2);
}
const corpusPath = resolve(args[1]);
const manifest = manifestSchema.parse(
  JSON.parse(await readFile(`${corpusPath}.manifest.json`, "utf8")),
);
process.env.LEGIFRANCE_IP_CORPUS_PATH = corpusPath;
process.env.LEGIFRANCE_IP_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.LEGIFRANCE_IP_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new LegifranceIpClient();
const report: Record<string, unknown> = {};
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error("Légifrance IP: artifact status or pins did not verify.");
  if (
    status.codes?.length !== 2 ||
    status.codes.reduce((sum, code) => sum + code.articles, 0) !==
      status.section_count
  )
    throw new Error("Légifrance IP: per-code metadata is missing or off.");
  const patentability = await library.getSection("L. 611-10 CPI");
  const secret = await library.getSection("Art. L. 151-1 Code de commerce");
  const bare = await library.getSection("L. 613-3");
  const hits = await library.search({
    query: "brevetabilite",
    statute: "CPI",
  });
  const secrets = await library.search({
    query: "secret des affaires",
    statute: "Code de commerce",
  });
  if (
    !patentability.text.includes("inventions nouvelles") ||
    !secret.text.includes("secret des affaires") ||
    bare.statute !== "CPI" ||
    !hits.hits.length ||
    !secrets.hits.length
  )
    throw new Error("Légifrance IP: library reads did not verify.");
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    codes: status.codes.map((code) => `${code.statute}: ${code.articles}`),
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    l611_10: `${patentability.title} (in force since ${patentability.in_force_since}, ${patentability.url})`,
    l151_1: `${secret.breadcrumb}`,
    brevetabilite: hits.hits.map((hit) => hit.section),
    secret_des_affaires: secrets.hits.map((hit) => hit.section),
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
  const hits = await client.callTool<Envelope>("search_legifrance_ip", {
    query: "contrefaçon",
  });
  const sections = await client.callTool<Envelope>("get_legifrance_section", {
    citation: [
      "L. 611-1 CPI",
      "L. 711-1 CPI",
      "L. 151-1 Code de commerce",
      "L. 999-99 CPI",
    ],
  });
  const items = sections.structuredContent?.items ?? [];
  if (!hits.structuredContent?.items.length || items.length !== 3)
    throw new Error("Légifrance IP: MCP search or get failed.");
  report.mcp_full = {
    contrefacon_hits: hits.structuredContent.items.map(
      (item) => `${item.statute} ${item.section}`,
    ),
    sections: items.map((item) => `${item.statute} ${item.section}`),
    not_found: sections.structuredContent?.not_found,
  };
} finally {
  await client.close();
  await server.close();
}
console.log(JSON.stringify(report, null, 2));

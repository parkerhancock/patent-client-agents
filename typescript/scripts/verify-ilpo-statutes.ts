import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { IlpoStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged ILPO statutes artifact through the library and the default full MCP wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const sourcesSchema = z.object({
  statutes: z.array(
    z.object({
      statute: z.string(),
      pdf_sha256: z.string(),
      section_count: z.number(),
    }),
  ),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error(
    "Usage: bun scripts/verify-ilpo-statutes.ts --file FILE.db.zst",
  );
  process.exit(2);
}
const corpusPath = resolve(args[1]);
const manifest = manifestSchema.parse(
  JSON.parse(await readFile(`${corpusPath}.manifest.json`, "utf8")),
);
const sources = sourcesSchema.parse(
  JSON.parse(
    await readFile(
      resolve(import.meta.dir, "ilpo-statutes-sources.json"),
      "utf8",
    ),
  ),
);
process.env.ILPO_STATUTES_CORPUS_PATH = corpusPath;
process.env.ILPO_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.ILPO_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new IlpoStatutesClient();
const report: Record<string, unknown> = {};
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error("ILPO statutes: artifact status or pins did not verify.");
  const statutes = await library.listStatutes();
  for (const source of sources.statutes) {
    const found = statutes.find((item) => item.statute === source.statute);
    if (
      found?.section_count !== source.section_count ||
      found.pdf_sha256 !== source.pdf_sha256
    )
      throw new Error(
        `ILPO statutes: ${source.statute} does not match the source manifest.`,
      );
  }
  const checks = {
    "Section 3 Patents Law": "What constitutes a patentable invention",
    "Section 46A Trade Marks Ordinance":
      "Exclusive use of a well known trademark",
    "Section 6 Designs Law": "Novel design",
    "Section 19 Copyright Act": "Fair Use",
    "Section 6 Commercial Torts Law":
      "Prohibition against misappropriation of a trade secret",
    "Section 13 Commercial Torts Law": "Statutory damages",
  };
  for (const [citation, title] of Object.entries(checks)) {
    const section = await library.getSectionByCitation(citation);
    if (section?.title !== title)
      throw new Error(`ILPO statutes: ${citation} is '${section?.title}'.`);
  }
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    statutes: statutes.map(
      (item) =>
        `${item.statute}: ${item.section_count} sections (${item.version})`,
    ),
    titles_checked: Object.keys(checks).length,
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
const server = createServer({ toolset: "full" });
const client = await Client.connect(server, {
  versionNegotiation: { mode: "legacy" },
});
try {
  const hits = await client.callTool<Envelope>("search_ilpo_statutes", {
    query: "trade secret",
    statute: "commercial_torts",
  });
  const sections = await client.callTool<Envelope>("get_ilpo_section", {
    citation: [
      "Section 6 Commercial Torts Law",
      "Patents Law §3",
      "Section 999 Patents Law",
    ],
  });
  const items = sections.structuredContent?.items ?? [];
  if (!hits.structuredContent?.items.length || items.length !== 2)
    throw new Error("ILPO statutes: MCP search or get failed.");
  report.mcp_full = {
    trade_secret_hits: hits.structuredContent.items.map(
      (item) => item.section_label,
    ),
    sections: items.map((item) => item.section_label),
    not_found: sections.structuredContent?.not_found,
  };
} finally {
  await client.close();
  await server.close();
}
console.log(JSON.stringify(report, null, 2));

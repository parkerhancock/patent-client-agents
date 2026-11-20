import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { ThaiDipStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged Thailand IP statutes artifact through the library and the default full MCP wiring. */
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
    "Usage: bun scripts/verify-thai-dip-statutes.ts --file FILE.db.zst",
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
      resolve(import.meta.dir, "thai-dip-statutes-sources.json"),
      "utf8",
    ),
  ),
);
process.env.THAI_DIP_STATUTES_CORPUS_PATH = corpusPath;
process.env.THAI_DIP_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.THAI_DIP_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new ThaiDipStatutesClient();
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
      "Thailand IP statutes: artifact status or pins did not verify.",
    );
  const statutes = await library.listStatutes();
  for (const source of sources.statutes) {
    const found = statutes.find((item) => item.statute === source.statute);
    if (
      found?.section_count !== source.section_count ||
      found.pdf_sha256 !== source.pdf_sha256
    )
      throw new Error(
        `Thailand IP statutes: ${source.statute} does not match the source manifest.`,
      );
  }
  // The acts print no headings, so each check is a phrase from the section's text.
  const checks = {
    "Section 5 Patent Act": "the invention is new",
    "Section 36 bis Patent Act": "shall be determined by the claims",
    "Section 65decies Patent Act": "concerning petty patents",
    "Section 6 Trademark Act": "be distinctive",
    "Section 109/1 Trademark Act": "packagings or utensils",
    "Section 32/1 Copyright Act": "lawfully acquires the right of ownership",
    "Section 3 Trade Secrets Act": "trade information not yet publicly known",
    "Trade Secrets Act s. 6": "contrary to honest trade practices",
  };
  for (const [citation, phrase] of Object.entries(checks)) {
    const section = await library.getSectionByCitation(citation);
    if (!section?.text.includes(phrase) || !section.authority)
      throw new Error(`Thailand IP statutes: ${citation} lacks '${phrase}'.`);
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
    sections_checked: Object.keys(checks).length,
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
  const hits = await client.callTool<Envelope>("search_thai_dip_statutes", {
    query: "petty patent",
    statute: "patent",
  });
  const sections = await client.callTool<Envelope>("get_thai_dip_section", {
    citation: [
      "Section 6 Trade Secrets Act",
      "Patent Act s. 36",
      "Section 999 Patent Act",
    ],
  });
  const items = sections.structuredContent?.items ?? [];
  if (!hits.structuredContent?.items.length || items.length !== 2)
    throw new Error("Thailand IP statutes: MCP search or get failed.");
  report.mcp_full = {
    petty_patent_hits: hits.structuredContent.items.map(
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

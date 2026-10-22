import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { TmepClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged TMEP artifact through the library and the default MCP and facade wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error("Usage: bun scripts/verify-tmep.ts --file FILE.db.zst");
  process.exit(2);
}
const corpusPath = resolve(args[1]);
const manifest = manifestSchema.parse(
  JSON.parse(await readFile(`${corpusPath}.manifest.json`, "utf8")),
);
process.env.TMEP_CORPUS_PATH = corpusPath;
process.env.TMEP_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.TMEP_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new TmepClient();
const report: Record<string, unknown> = {};
let sectionHash: string;
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error("TMEP: artifact status or pins did not verify.");
  const hits = await library.search({
    query: "likelihood of confusion",
    limit: 5,
  });
  const byHref = await library.getSection("TMEP-1200d1e8145.html");
  const section = await library.getSection("1207.01");
  if (!hits.hits.length || byHref.section_number !== "1209.03(u)")
    throw new Error("TMEP: library search or href lookup failed.");
  sectionHash = section.content_sha256;
  Object.assign(report, {
    corpus_version: status.corpus_version,
    snapshot_date: status.snapshot_date,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    likelihood_of_confusion_top: hits.hits.map((hit) => hit.section_number),
    section_1207_01_text_characters: section.text.length,
    section_1207_01_html_sha256: section.content_sha256,
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
    if (toolset === "full") {
      const search = await client.callTool<Envelope>("search_tmep", {
        query: "specimen of use",
      });
      const sections = await client.callTool<Envelope>("get_tmep_section", {
        section: ["1207", "1209.03(u)", "1402", "9999.99"],
      });
      const html = await client.callTool<{
        items: { document: { file_path: string } }[];
      }>("get_tmep_section", { section: "1207.01", format: "html" });
      const artifact = html.structuredContent?.items[0]?.document.file_path;
      const artifactHash = artifact
        ? createHash("sha256")
            .update(await readFile(artifact))
            .digest("hex")
        : null;
      if (
        !search.structuredContent?.items.length ||
        sections.structuredContent?.items.length !== 3 ||
        artifactHash !== sectionHash
      )
        throw new Error("TMEP (full): MCP search or get failed.");
      report.mcp_full = {
        specimen_hits: search.structuredContent.items.length,
        specimen_more: search.structuredContent.more_available,
        sections: sections.structuredContent.items.map(
          (item) => item.section_number,
        ),
        not_found: sections.structuredContent.not_found,
        html_artifact_matches_library: true,
      };
    } else {
      const search = await client.callTool<Envelope>("search_legal_reference", {
        corpus: "uspto_tmep",
        query: "acquired distinctiveness",
        limit: 3,
      });
      const section = await client.callTool<Envelope>("get_legal_reference", {
        corpus: "uspto_tmep",
        identifier: "1212",
      });
      const item = section.structuredContent?.items[0];
      if (!search.structuredContent?.items.length || !item)
        throw new Error("TMEP (curated): facade search or get failed.");
      report.mcp_curated = {
        acquired_distinctiveness_top: search.structuredContent.items.map(
          (hit) => hit.section_number,
        ),
        section_1212: `${item.section_number}: ${item.title} (${item.text === undefined ? "artifact" : "inline"})`,
      };
    }
  } finally {
    await client.close();
    await server.close();
  }
}
console.log(JSON.stringify(report, null, 2));

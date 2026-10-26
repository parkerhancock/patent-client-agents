import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { IpophlStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged IPOPHL statutes artifact through the library and the default full MCP wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const sourcesSchema = z.object({
  acts: z.array(
    z.object({
      statute: z.string(),
      sha256: z.string(),
      section_count: z.number(),
    }),
  ),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error(
    "Usage: bun scripts/verify-ipophl-statutes.ts --file FILE.db.zst",
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
      resolve(import.meta.dir, "ipophl-statutes-sources.json"),
      "utf8",
    ),
  ),
);
process.env.IPOPHL_STATUTES_CORPUS_PATH = corpusPath;
process.env.IPOPHL_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.IPOPHL_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new IpophlStatutesClient();
const report: Record<string, unknown> = {};
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error("IPOPHL statutes: artifact status or pins did not verify.");
  const statutes = await library.listStatutes();
  for (const source of sources.acts) {
    const found = statutes.find((item) => item.statute === source.statute);
    if (
      found?.section_count !== source.section_count ||
      found.page_sha256 !== source.sha256
    )
      throw new Error(
        `IPOPHL statutes: ${source.statute} does not match the source manifest.`,
      );
  }
  const checks = {
    "Section 21 IP Code": "Patentable Inventions",
    "Section 22 RA 8293": "Non-Patentable Inventions",
    "Sec. 123.1(d) RA 8293": "Registrability",
    "Section 185 IP Code": "Fair Use of a Copyrighted Work",
    "Section 241 RA 8293": "Effectivity",
    "Section 3 RA 9150": "Applicability",
    "Section 1 RA 9502": "Short Title",
    "Section 29 RA 10372": "Implementing Rules and Regulations",
  };
  for (const [citation, title] of Object.entries(checks)) {
    const section = await library.getSectionByCitation(citation);
    if (section?.title !== title)
      throw new Error(`IPOPHL statutes: ${citation} is '${section?.title}'.`);
  }
  const amended = await library.getSectionByCitation("Section 22 IP Code");
  if (amended?.amended_by.join() !== "Section 5 RA 9502")
    throw new Error("IPOPHL statutes: Section 22 amendment pointer is wrong.");
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    statutes: statutes.map(
      (item) =>
        `${item.statute}: ${item.section_count} sections (approved ${item.approved}${item.missing_sections.length ? `; missing ${item.missing_sections.join(", ")}` : ""})`,
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
  const hits = await client.callTool<Envelope>("search_ipophl_statutes", {
    query: "compulsory licensing",
  });
  const sections = await client.callTool<Envelope>("get_ipophl_section", {
    citation: [
      "Section 22 IP Code",
      "Section 5 RA 9502",
      "Section 999 IP Code",
    ],
  });
  const items = sections.structuredContent?.items ?? [];
  if (!hits.structuredContent?.items.length || items.length !== 2)
    throw new Error("IPOPHL statutes: MCP search or get failed.");
  report.mcp_full = {
    compulsory_licensing_hits: hits.structuredContent.items.map(
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

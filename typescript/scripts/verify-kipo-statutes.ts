import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { KipoStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged KIPO statutes artifact through the library and the default full MCP wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const sourcesSchema = z.object({
  statutes: z.array(
    z.object({
      statute: z.string(),
      version: z.string(),
      sha256: z.string(),
      section_count: z.number(),
    }),
  ),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error(
    "Usage: bun scripts/verify-kipo-statutes.ts --file FILE.db.zst",
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
      resolve(import.meta.dir, "kipo-statutes-sources.json"),
      "utf8",
    ),
  ),
);
process.env.KIPO_STATUTES_CORPUS_PATH = corpusPath;
process.env.KIPO_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.KIPO_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new KipoStatutesClient();
const report: Record<string, unknown> = {};
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error("KIPO statutes: artifact status or pins did not verify.");
  const statutes = await library.listStatutes();
  for (const source of sources.statutes) {
    const found = statutes.find((item) => item.statute === source.statute);
    if (
      found?.section_count !== source.section_count ||
      found.sha256 !== source.sha256 ||
      found.version !== source.version
    )
      throw new Error(
        `KIPO statutes: ${source.statute} does not match the source manifest.`,
      );
  }
  const checks = {
    "Article 29 Patent Act": "Requirements for Patent Registration",
    "Article 29-2 Patent Act": null,
    "Article 7-2 Patent Act":
      "Ratification of Acts of Persons Lacking Capacity to Act",
    "Article 4 Utility Model Act": "Requirements for utility model",
    "Article 33 Design Protection Act": "Requirements for Design Registration",
    "Article 34 Trademark Act":
      "Trademarks Ineligible for Trademark Registration",
    "Article 2 Unfair Competition Prevention and Trade Secret Protection Act":
      "Definitions",
    "Article 10 Invention Promotion Act": "Service invention",
    "Article 35-5 Copyright Act": "Fair use of works",
  };
  for (const [citation, title] of Object.entries(checks)) {
    const section = await library.getSectionByCitation(citation);
    // Article 29-2 does not exist in the Patent Act; it must not resolve.
    if (title === null ? section !== null : section?.title !== title)
      throw new Error(`KIPO statutes: ${citation} is '${section?.title}'.`);
  }
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    statutes: statutes.map(
      (item) =>
        `${item.statute}: ${item.section_count} articles (${item.version})`,
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
  const hits = await client.callTool<Envelope>("search_kipo_statutes", {
    query: "trade secret",
    statute: "unfair_competition",
  });
  const sections = await client.callTool<Envelope>("get_kipo_section", {
    citation: [
      "Patent Act Art. 29(1)",
      "특허법 제94조",
      "Article 999 Patent Act",
    ],
  });
  const items = sections.structuredContent?.items ?? [];
  if (!hits.structuredContent?.items.length || items.length !== 2)
    throw new Error("KIPO statutes: MCP search or get failed.");
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

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { CnipaStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged CNIPA statutes artifact through the library and the default full MCP wiring. */
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
    "Usage: bun scripts/verify-cnipa-statutes.ts --file FILE.db.zst",
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
      resolve(import.meta.dir, "cnipa-statutes-sources.json"),
      "utf8",
    ),
  ),
);
process.env.CNIPA_STATUTES_CORPUS_PATH = corpusPath;
process.env.CNIPA_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.CNIPA_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new CnipaStatutesClient();
const report: Record<string, unknown> = {};
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error("CNIPA statutes: artifact status or pins did not verify.");
  const statutes = await library.listStatutes();
  for (const source of sources.statutes) {
    const found = statutes.find((item) => item.statute === source.statute);
    if (
      found?.section_count !== source.section_count ||
      found.pdf_sha256 !== source.pdf_sha256
    )
      throw new Error(
        `CNIPA statutes: ${source.statute} does not match the source manifest.`,
      );
  }
  // Provision -> a phrase from the English PDF and the chapter it sits in.
  const checks: Record<string, [string, string]> = {
    "Article 22 Patent Law": [
      "prominent substantive features",
      "Chapter II Requirements for Granting Patent Rights",
    ],
    "Rule 20 Implementing Regulations": [
      "The claims shall have an independent claim",
      "Chapter 2 Application for a Patent",
    ],
    "Article 13 Trademark Law": [
      "well-known trademark",
      "Chapter I General Provisions",
    ],
    "Article 3 Trademark Implementing Regulations": [
      "well-known trademark",
      "Chapter I General Provisions",
    ],
    "Article 9 Anti-Unfair Competition Law": [
      "“a trade secret” means",
      "Chapter II Acts of Unfair Competition",
    ],
    "Article 24 Copyright Law": [
      "dyslexics",
      "Chapter II Copyright, Section 4 Limitations on Rights",
    ],
  };
  for (const [citation, [phrase, title]] of Object.entries(checks)) {
    const section = await library.getSectionByCitation(citation);
    if (section?.title !== title || !section.text.includes(phrase))
      throw new Error(`CNIPA statutes: ${citation} is '${section?.title}'.`);
  }
  if (!status.notice.includes("the Chinese text controls"))
    throw new Error(
      "CNIPA statutes: the status lacks the controlling-text notice.",
    );
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    notice: status.notice,
    statutes: statutes.map(
      (item) =>
        `${item.statute}: ${item.section_count} ${item.unit === "Rule" ? "Rules" : "Articles"} (${item.translation_version})`,
    ),
    provisions_checked: Object.keys(checks).length,
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
  const hits = await client.callTool<Envelope>("search_cnipa_statutes", {
    query: "trade secret",
    statute: "anti_unfair_competition",
  });
  const sections = await client.callTool<Envelope>("get_cnipa_section", {
    citation: [
      "Article 9 AUCL",
      "Patent Law Art. 22(3)",
      "Article 999 Patent Law",
    ],
  });
  const items = sections.structuredContent?.items ?? [];
  if (!hits.structuredContent?.items.length || items.length !== 2)
    throw new Error("CNIPA statutes: MCP search or get failed.");
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

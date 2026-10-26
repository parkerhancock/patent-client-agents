import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { RospatentStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged Russian Civil Code Part Four artifact through the library and the default full MCP wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const sourcesSchema = z.object({
  legislation: z.object({
    pdf_sha256: z.string(),
    article_count: z.number(),
    repealed_article_count: z.number(),
  }),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error(
    "Usage: bun scripts/verify-rospatent-statutes.ts --file FILE.db.zst",
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
      resolve(import.meta.dir, "rospatent-statutes-sources.json"),
      "utf8",
    ),
  ),
);
process.env.ROSPATENT_STATUTES_CORPUS_PATH = corpusPath;
process.env.ROSPATENT_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.ROSPATENT_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new RospatentStatutesClient();
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
      "Rospatent statutes: artifact status or pins did not verify.",
    );
  if (
    status.section_count !== sources.legislation.article_count ||
    status.legislation?.pdf_sha256 !== sources.legislation.pdf_sha256
  )
    throw new Error(
      "Rospatent statutes: the corpus does not match the source manifest.",
    );
  const checks = {
    "Article 1225 Civil Code":
      "Protected Results of Intellectual Activities and Means of Individualisation",
    "Article 1231.1":
      "Objects Including Official Symbols, Denominations and Distinctive Marks",
    "Civil Code Art. 1350(1)":
      "The Conditions for Patentability of an Invention",
    "Art. 1484 CC RF": "The Exclusive Right to a Trademark",
    "Article 1465": "A Production Secret (Know-How)",
    "Article 1541":
      "The Relationship of the Right to a Commercial Name with the Rights to a Company Name and to a Trademark",
  };
  for (const [citation, title] of Object.entries(checks)) {
    const article = await library.getArticleByCitation(citation);
    if (article?.title !== title)
      throw new Error(
        `Rospatent statutes: ${citation} is '${article?.title}'.`,
      );
  }
  const repealed = await library.getArticle("1478");
  if (!repealed?.repealed || repealed.title !== null)
    throw new Error("Rospatent statutes: Article 1478 is not marked repealed.");
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    translation_amended_up_to: status.translation_amended_up_to,
    russian_amended_up_to: status.russian_amended_up_to,
    repealed_chapters: status.repealed_chapters,
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
  const hits = await client.callTool<Envelope>("search_rospatent_statutes", {
    query: "inventive step",
    chapter: 72,
  });
  const articles = await client.callTool<Envelope>("get_rospatent_section", {
    citation: ["Article 1350 Civil Code", "ст. 1484 ГК РФ", "Article 1999"],
  });
  const items = articles.structuredContent?.items ?? [];
  if (!hits.structuredContent?.items.length || items.length !== 2)
    throw new Error("Rospatent statutes: MCP search or get failed.");
  report.mcp_full = {
    inventive_step_hits: hits.structuredContent.items.map(
      (item) => item.section_label,
    ),
    articles: items.map((item) => item.section_label),
    not_found: articles.structuredContent?.not_found,
  };
} finally {
  await client.close();
  await server.close();
}
console.log(JSON.stringify(report, null, 2));

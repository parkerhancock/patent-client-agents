import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { InpiArStatutesClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify a packaged INPI Argentina statutes artifact through the library and the default full MCP wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const sourcesSchema = z.object({
  statutes: z.array(
    z.object({
      statute: z.string(),
      text_sha256: z.string(),
      text_kind: z.enum(["texact", "norma"]),
      section_count: z.number(),
    }),
  ),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error(
    "Usage: bun scripts/verify-inpi-ar-statutes.ts --file FILE.db.zst",
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
      resolve(import.meta.dir, "inpi-ar-statutes-sources.json"),
      "utf8",
    ),
  ),
);
process.env.INPI_AR_STATUTES_CORPUS_PATH = corpusPath;
process.env.INPI_AR_STATUTES_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.INPI_AR_STATUTES_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new InpiArStatutesClient();
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
      "INPI Argentina statutes: artifact status or pins did not verify.",
    );
  const statutes = await library.listStatutes();
  for (const source of sources.statutes) {
    const found = statutes.find((item) => item.statute === source.statute);
    if (
      found?.section_count !== source.section_count ||
      found.text_sha256 !== source.text_sha256 ||
      found.text_kind !== source.text_kind
    )
      throw new Error(
        `INPI Argentina statutes: ${source.statute} does not match the source manifest.`,
      );
  }
  // Opening words of articles read against the Infoleg pages.
  const checks = {
    "Artículo 4 Ley 24.481": "Serán patentables las invenciones",
    "Ley 22.362 art. 3": "No pueden ser registrados:",
    "Art. 6 Decreto-Ley 6673/63":
      "No podrán gozar de los beneficios que otorgue este decreto-ley:",
    "Art. 5 bis Ley 11.723":
      "La propiedad intelectual sobre sus interpretaciones o ejecuciones",
    "Artículo 1 Ley 24.766": "Las personas físicas o jurídicas podrán impedir",
    "art. 19 ley 22362": "(Artículo derogado por art. 69 de la Ley N° 27.444",
  };
  for (const [citation, opening] of Object.entries(checks)) {
    const section = await library.getSectionByCitation(citation);
    if (!section?.text.startsWith(opening))
      throw new Error(
        `INPI Argentina statutes: ${citation} starts '${section?.text.slice(0, 60)}'.`,
      );
  }
  Object.assign(report, {
    corpus_version: status.corpus_version,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    notice: status.notice,
    statutes: statutes.map(
      (item) =>
        `${item.statute}: ${item.section_count} articles (${item.version})`,
    ),
    openings_checked: Object.keys(checks).length,
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
  const hits = await client.callTool<Envelope>("search_inpi_ar_statutes", {
    query: "informacion secreta",
    statute: "trade secrets",
  });
  const sections = await client.callTool<Envelope>("get_inpi_ar_section", {
    citation: [
      "Artículo 4 Ley 24.481",
      "Ley 22.362 art. 3",
      "Artículo 999 Ley 24.481",
    ],
  });
  const items = sections.structuredContent?.items ?? [];
  if (!hits.structuredContent?.items.length || items.length !== 2)
    throw new Error("INPI Argentina statutes: MCP search or get failed.");
  report.mcp_full = {
    informacion_secreta_hits: hits.structuredContent.items.map(
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

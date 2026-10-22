import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { MoppClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/**
 * Verify a packaged MoPP artifact through the library and the default MCP and
 * facade wiring, against values Python's MoppClient (patent-client-agents
 * 0.30.0) returned for the same deployed snapshot on October 22, 2026.
 */
const PYTHON = {
  sections: {
    "1": {
      href: "section-1-patentability",
      html_sha256:
        "f0ab78642694b794745e4157a0a697b3d95b672a1450936699084b9e0d6c061d",
      text_chars: 133_767,
    },
    "4A": {
      href: "-section-4a-methods-of-treatment-or-diagnosis",
      html_sha256:
        "a56dcb83cc730fd7efd863acede527b753f5d4a1d9b75241a71e5e96fd0edad4",
      text_chars: 52_724,
    },
    "14": {
      href: "section-14-the-application",
      html_sha256:
        "4b57b87ff12ce5b0d6d35f992599c6f8082ba7b137d06c396eddb32e6f827da1",
      text_chars: 228_599,
    },
    "glossary-of-terms-and-abbreviations-used-in-this-manual": {
      href: "glossary-of-terms-and-abbreviations-used-in-this-manual",
      html_sha256:
        "c95b8ca9dda76bc432e190e356413d37d4d193ac1bfd21748be12cb94964ae36",
      text_chars: 6_595,
    },
  },
  search: {
    "inventive step": [
      "section-3-inventive-step",
      "section-89b-adaptation-of-provisions-in-relation-to-international-application",
      "section-17-search",
      "section-74a-opinions-on-matters-prescribed-in-the-rules",
      "section-24-publication-and-certificate-of-grant",
    ],
    "methods of treatment": [
      "-section-4a-methods-of-treatment-or-diagnosis",
      "section-4-industrial-application",
      "section-89b-adaptation-of-provisions-in-relation-to-international-application",
      "section-76-amendments-of-applications-and-patents-not-to-include-added-matter",
      "section-2-novelty",
    ],
    "industrial application": [
      "section-4-industrial-application",
      "section-89b-adaptation-of-provisions-in-relation-to-international-application",
      "section-89-effect-of-international-application-for-patent",
      "section-76a-biotechnological-inventions",
      "-section-4a-methods-of-treatment-or-diagnosis",
    ],
    sufficiency: [
      "section-14-the-application",
      "section-68-effect-of-non-registration-on-infringement-proceedings",
      "section-111-unauthorised-claim-that-patent-has-been-applied-for",
      "section-110-unauthorised-claim-of-patent-rights",
      "section-89b-adaptation-of-provisions-in-relation-to-international-application",
    ],
  },
} as const;
// References Python reports as not found, and the page each should reach.
const FIXED = {
  "4a": "-section-4a-methods-of-treatment-or-diagnosis",
  "102a":
    "section-102a-right-of-audience-etc-in-proceedings-on-appeal-from-the-comptroller-repealed",
  "11": "sections-11-effect-of-transfer-of-application-under-s-8-or-10",
  "1.07": "section-1-patentability",
  "https://www.gov.uk/guidance/manual-of-patent-practice-mopp/section-14-the-application#ref14-01":
    "section-14-the-application",
} as const;

const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--file" || !args[1]) {
  console.error("Usage: bun scripts/verify-ukipo-mopp.ts --file FILE.db.zst");
  process.exit(2);
}
const corpusPath = resolve(args[1]);
const manifest = manifestSchema.parse(
  JSON.parse(await readFile(`${corpusPath}.manifest.json`, "utf8")),
);
process.env.MOPP_CORPUS_PATH = corpusPath;
process.env.MOPP_CORPUS_SHA256 = manifest.decoded_sha256;
process.env.MOPP_CORPUS_FILE_SHA256 = manifest.file_sha256;

const library = new MoppClient();
const report: Record<string, unknown> = {};
try {
  const status = await library.getCorpusStatus();
  if (
    !status.available ||
    status.compression !== "zstd" ||
    status.artifact_sha256 !== manifest.decoded_sha256 ||
    status.file_sha256 !== manifest.file_sha256
  )
    throw new Error("MoPP: artifact status or pins did not verify.");
  for (const [ref, expected] of Object.entries(PYTHON.sections)) {
    const section = await library.getSection(ref);
    if (
      section.href !== expected.href ||
      section.content_sha256 !== expected.html_sha256 ||
      section.text.length !== expected.text_chars
    )
      throw new Error(`MoPP: section ${ref} differs from Python.`);
  }
  for (const [query, expected] of Object.entries(PYTHON.search)) {
    const hits = (await library.search({ query, limit: 5 })).hits.map(
      (hit) => hit.href,
    );
    if (JSON.stringify(hits) !== JSON.stringify(expected))
      throw new Error(`MoPP: search '${query}' differs from Python: ${hits}`);
  }
  for (const [ref, href] of Object.entries(FIXED))
    if ((await library.getSection(ref)).href !== href)
      throw new Error(`MoPP: reference '${ref}' did not resolve to ${href}.`);
  Object.assign(report, {
    corpus_version: status.corpus_version,
    snapshot_date: status.snapshot_date,
    corpus_synced_at: status.corpus_synced_at,
    section_count: status.section_count,
    decoded_sha256: status.artifact_sha256,
    file_sha256: status.file_sha256,
    python_sections_match: Object.keys(PYTHON.sections),
    python_search_top5_match: Object.keys(PYTHON.search),
    python_not_found_now_resolved: FIXED,
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
      const search = await client.callTool<Envelope>("search_mopp", {
        query: "inventive step",
      });
      const sections = await client.callTool<Envelope>("get_mopp_section", {
        section: ["1", "4A", "11", "9999"],
      });
      const html = await client.callTool<{
        items: { document: { file_path: string } }[];
      }>("get_mopp_section", { section: "4A", format: "html" });
      const artifact = html.structuredContent?.items[0]?.document.file_path;
      const artifactHash = artifact
        ? createHash("sha256")
            .update(await readFile(artifact))
            .digest("hex")
        : null;
      if (
        !search.structuredContent?.items.length ||
        sections.structuredContent?.items.length !== 3 ||
        artifactHash !== PYTHON.sections["4A"].html_sha256
      )
        throw new Error("MoPP (full): MCP search or get failed.");
      report.mcp_full = {
        inventive_step_hits: search.structuredContent.items.length,
        inventive_step_more: search.structuredContent.more_available,
        sections: sections.structuredContent.items.map(
          (item) => item.section_number,
        ),
        not_found: sections.structuredContent.not_found,
        html_artifact_matches_python: true,
      };
    } else {
      const search = await client.callTool<Envelope>("search_legal_reference", {
        corpus: "ukipo_mopp",
        query: "industrial application",
        limit: 3,
      });
      const section = await client.callTool<Envelope>("get_legal_reference", {
        corpus: "ukipo_mopp",
        identifier: "4A",
      });
      const item = section.structuredContent?.items[0];
      if (!search.structuredContent?.items.length || !item)
        throw new Error("MoPP (curated): facade search or get failed.");
      report.mcp_curated = {
        industrial_application_top: search.structuredContent.items.map(
          (hit) => hit.section_number,
        ),
        section_4A: `${item.section_number}: ${item.title} (${item.text === undefined ? "artifact" : "inline"})`,
      };
    }
  } finally {
    await client.close();
    await server.close();
  }
}
console.log(JSON.stringify(report, null, 2));

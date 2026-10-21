import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import {
  EPC_BOOK,
  EPO_CASE_LAW_BOOK,
  EPO_GUIDELINES_BOOK,
  EPO_PCT_GUIDELINES_BOOK,
  EPO_UP_GUIDELINES_BOOK,
  type EpoLegalBook,
  EpoLegalCorpusClient,
} from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/** Verify packaged EPO legal artifacts through the library and default MCP wiring. */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const books: [
  EpoLegalBook<unknown>,
  string,
  { search: string; get: string; query: string; section: string },
][] = [
  [
    EPC_BOOK,
    "epc",
    {
      search: "search_epc",
      get: "get_epc_section",
      query: "inventive step",
      section: "Article 56",
    },
  ],
  [
    EPO_CASE_LAW_BOOK,
    "caselaw",
    {
      search: "search_epo_case_law",
      get: "get_epo_case_law_section",
      query: "problem solution approach",
      section: "I.D.2",
    },
  ],
  [
    EPO_GUIDELINES_BOOK,
    "guidelines",
    {
      search: "search_epo_guidelines",
      get: "get_epo_guidelines_section",
      query: "inventive step",
      section: "G-VII, 5",
    },
  ],
  [
    EPO_PCT_GUIDELINES_BOOK,
    "pct_guidelines",
    {
      search: "search_epo_pct_guidelines",
      get: "get_epo_pct_guidelines_section",
      query: "international search",
      section: "B-III, 2",
    },
  ],
  [
    EPO_UP_GUIDELINES_BOOK,
    "up_guidelines",
    {
      search: "search_epo_up_guidelines",
      get: "get_epo_up_guidelines_section",
      query: "unitary effect",
      section: "2.4",
    },
  ],
];

const args = Bun.argv.slice(2);
if (args.length !== 2 || args[0] !== "--dir" || !args[1]) {
  console.error("Usage: bun scripts/verify-epo-legal.ts --dir DIRECTORY");
  process.exit(2);
}
const directory = resolve(args[1]);
const report: Record<string, unknown>[] = [];
for (const [book, name] of books) {
  const corpusPath = join(directory, `${name}.db.zst`);
  const manifest = manifestSchema.parse(
    JSON.parse(await readFile(`${corpusPath}.manifest.json`, "utf8")),
  );
  process.env[`${book.envPrefix}_CORPUS_PATH`] = corpusPath;
  process.env[`${book.envPrefix}_CORPUS_SHA256`] = manifest.decoded_sha256;
  process.env[`${book.envPrefix}_CORPUS_FILE_SHA256`] = manifest.file_sha256;
  const library = new EpoLegalCorpusClient(book);
  try {
    const status = await library.getCorpusStatus();
    if (
      !status.available ||
      status.compression !== "zstd" ||
      status.artifact_sha256 !== manifest.decoded_sha256 ||
      status.file_sha256 !== manifest.file_sha256
    )
      throw new Error(`${book.label}: artifact status or pins did not verify.`);
    report.push({
      book: book.label,
      edition: status.edition,
      snapshot_date: status.snapshot_date,
      section_count: status.section_count,
      decoded_sha256: status.artifact_sha256,
      file_sha256: status.file_sha256,
    });
  } finally {
    library.close();
  }
}
// Exercise default server wiring rather than injected corpus clients.
const server = createServer();
const client = await Client.connect(server, {
  versionNegotiation: { mode: "legacy" },
});
try {
  for (const [index, [book, , tools]] of books.entries()) {
    const search = await client.callTool<{ items: unknown[] }>(tools.search, {
      query: tools.query,
      limit: 3,
    });
    const section = await client.callTool<{
      items: { href?: string; text?: string }[];
    }>(tools.get, { section: tools.section });
    const item = section.structuredContent?.items[0];
    if (!search.structuredContent?.items.length || !item?.text)
      throw new Error(`${book.label}: MCP search or section fetch failed.`);
    Object.assign(report[index] ?? {}, {
      mcp_search_hits: search.structuredContent.items.length,
      mcp_section: `${tools.section} -> ${item.href}`,
    });
  }
} finally {
  await client.close();
  await server.close();
}
console.log(JSON.stringify(report, null, 2));

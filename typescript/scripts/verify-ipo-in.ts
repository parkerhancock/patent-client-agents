import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  IpoInMpppClient,
  IpoInStatutesClient,
} from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";

/**
 * Verify packaged IPO India statutes and MPPP artifacts: pins, every row
 * against the Python seed the builder ingested, search and get parity with
 * the Python clients over the same databases, and the default full and
 * curated MCP wiring.
 *
 * Usage: bun scripts/verify-ipo-in.ts --statutes S.db.zst --mppp M.db.zst
 * The prepared .db files (the .zst paths without the suffix) are what the
 * Python clients read.
 */
const manifestSchema = z.object({
  decoded_sha256: z.string().regex(/^[a-f\d]{64}$/),
  file_sha256: z.string().regex(/^[a-f\d]{64}$/),
});
const args = Bun.argv.slice(2);
const flag = (name: string) => {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : undefined;
};
const statutesFile = flag("--statutes");
const mpppFile = flag("--mppp");
if (!statutesFile || !mpppFile) {
  console.error(
    "Usage: bun scripts/verify-ipo-in.ts --statutes FILE.db.zst --mppp FILE.db.zst",
  );
  process.exit(2);
}
const root = resolve(import.meta.dir, "..", "..");
const sha = (text: string) => createHash("sha256").update(text).digest("hex");
const report: Record<string, unknown> = {};

async function configure(prefix: string, file: string) {
  const path = resolve(file);
  const manifest = manifestSchema.parse(
    JSON.parse(await readFile(`${path}.manifest.json`, "utf8")),
  );
  process.env[`${prefix}_CORPUS_PATH`] = path;
  process.env[`${prefix}_CORPUS_SHA256`] = manifest.decoded_sha256;
  process.env[`${prefix}_CORPUS_FILE_SHA256`] = manifest.file_sha256;
  return { path, manifest };
}
const statutes = await configure("IPO_IN_STATUTES", statutesFile);
const mppp = await configure("IPO_IN_MPPP", mpppFile);

async function seed(name: string) {
  const text = await readFile(
    resolve(root, "src/patent_client_agents", name, "data/seed.jsonl"),
    "utf8",
  );
  return text
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as Record<string, string>);
}

const STATUTE_QUERIES = [
  ["efficacy", null],
  ["compulsory licensing", "Patents Act"],
  ["well-known mark", null],
  ["fair dealing", null],
  ["opposition", null],
  ["registered", "trade marks"],
  ["term", null],
] as const;
const MPPP_QUERIES = [
  "first examination report",
  "opposition",
  "Form 27",
  "national phase",
  "efficacy",
] as const;

/** Python client results for the same queries over the prepared databases. */
function python() {
  const script = `
import asyncio, json, os, sys
from patent_client_agents.ipo_in_statutes import IpoInStatutesClient
from patent_client_agents.ipo_in_mppp import MpppClient
args = json.loads(sys.argv[1])
async def main():
    out = {"statutes": [], "mppp": [], "sections": {}, "mppp_sections": {}}
    async with IpoInStatutesClient(corpus_path=args["statutes"]) as c:
        for q, statute in args["statute_queries"]:
            r = await c.search(q, statute_name=statute, per_page=50)
            out["statutes"].append([[h.statute_name, h.section_number, h.snippet] for h in r.hits])
        for cite in args["citations"]:
            s = await c.get_section_by_citation(cite)
            out["sections"][cite] = [s.statute_name, s.section_number, s.title, s.text, s.source_url]
    async with MpppClient(corpus_path=args["mppp"]) as c:
        for q in args["mppp_queries"]:
            r = await c.search(q, per_page=50)
            out["mppp"].append([[h.section_number, h.snippet] for h in r.hits])
        for ref in args["mppp_refs"]:
            s = await c.get_section(ref)
            out["mppp_sections"][ref] = [s.section_number, s.chapter, s.title, s.text, s.source_url]
    print(json.dumps(out))
asyncio.run(main())
`;
  const result = Bun.spawnSync(
    [
      "uv",
      "run",
      "--project",
      root,
      "--frozen",
      "--no-sync",
      "python",
      "-c",
      script,
      JSON.stringify({
        statutes: statutes.path.replace(/\.zst$/, ""),
        mppp: mppp.path.replace(/\.zst$/, ""),
        statute_queries: STATUTE_QUERIES,
        citations: CITATIONS,
        mppp_queries: MPPP_QUERIES,
        mppp_refs: MPPP_REFS,
      }),
    ],
    { stderr: "pipe" },
  );
  if (result.exitCode !== 0)
    throw new Error(`Python parity run failed: ${result.stderr.toString()}`);
  return JSON.parse(result.stdout.toString()) as {
    statutes: string[][][];
    mppp: string[][][];
    sections: Record<string, (string | null)[]>;
    mppp_sections: Record<string, (string | null)[]>;
  };
}
const CITATIONS = [
  "Section 3(d) Patents Act",
  "Section 25(2) of the Patents Act",
  "Rule 71 Patent Rules",
  "S. 84",
  "Section 9 Trade Marks Act",
  "Section 52 Copyright Act",
  "Section 2(d) Designs Act",
];
const MPPP_REFS = ["04.05.01", "Chapter 05.04", "MPPP Chapter 07.02"];

const mismatches: string[] = [];
const statuteClient = new IpoInStatutesClient();
const mpppClient = new IpoInMpppClient();
try {
  for (const [client, manifest, name] of [
    [statuteClient, statutes.manifest, "statutes"],
    [mpppClient, mppp.manifest, "mppp"],
  ] as const) {
    const status = await client.getCorpusStatus();
    if (
      !status.available ||
      status.compression !== "zstd" ||
      status.artifact_sha256 !== manifest.decoded_sha256 ||
      status.file_sha256 !== manifest.file_sha256
    )
      throw new Error(`IPO India ${name}: artifact status or pins failed.`);
    report[name] = {
      corpus_version: status.corpus_version,
      corpus_synced_at: status.corpus_synced_at,
      section_count: status.section_count,
      decoded_sha256: status.artifact_sha256,
      file_sha256: status.file_sha256,
    };
  }

  // Every seed row comes back unchanged through the TypeScript reader.
  const statuteSeed = await seed("ipo_in_statutes");
  for (const row of statuteSeed) {
    const section = await statuteClient.getSection(
      row.section_number as string,
      { statute: row.statute_name as string },
    );
    if (
      section.content_sha256 !== sha(row.text as string) ||
      section.title !== (row.title ?? null) ||
      section.source_url !== (row.source_url ?? null)
    )
      mismatches.push(
        `statutes seed ${row.statute_name} ${row.section_number}`,
      );
  }
  const mpppSeed = await seed("ipo_in_mppp");
  for (const row of mpppSeed) {
    const section = await mpppClient.getSection(row.section_number as string);
    if (
      section.content_sha256 !== sha(row.text as string) ||
      section.chapter !== (row.chapter ?? null) ||
      section.title !== (row.title ?? null)
    )
      mismatches.push(`mppp seed ${row.section_number}`);
  }

  // Python parity over queries without FTS5 operator words.
  const py = python();
  for (const [index, [query, statute]] of STATUTE_QUERIES.entries()) {
    const hits = (
      await statuteClient.search({ query, statute, limit: 50 })
    ).hits.map((h) => [h.statute_name, h.section_number, h.snippet]);
    if (JSON.stringify(hits) !== JSON.stringify(py.statutes[index]))
      mismatches.push(`statutes search '${query}'`);
  }
  for (const [index, query] of MPPP_QUERIES.entries()) {
    const hits = (await mpppClient.search({ query, limit: 50 })).hits.map(
      (h) => [h.section_number, h.snippet],
    );
    if (JSON.stringify(hits) !== JSON.stringify(py.mppp[index]))
      mismatches.push(`mppp search '${query}'`);
  }
  for (const citation of CITATIONS) {
    const s = await statuteClient.getSectionByCitation(citation);
    const row = [
      s.statute_name,
      s.section_number,
      s.title,
      s.text,
      s.source_url,
    ];
    if (JSON.stringify(row) !== JSON.stringify(py.sections[citation]))
      mismatches.push(`statutes get '${citation}'`);
  }
  for (const ref of MPPP_REFS) {
    const s = await mpppClient.getSection(ref);
    const row = [s.section_number, s.chapter, s.title, s.text, s.source_url];
    if (JSON.stringify(row) !== JSON.stringify(py.mppp_sections[ref]))
      mismatches.push(`mppp get '${ref}'`);
  }
  report.parity = {
    seed_rows_checked: statuteSeed.length + mpppSeed.length,
    python_searches: STATUTE_QUERIES.length + MPPP_QUERIES.length,
    python_gets: CITATIONS.length + MPPP_REFS.length,
    mismatches,
  };
} finally {
  statuteClient.close();
  mpppClient.close();
}

type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found?: string[];
  more_available: boolean;
};
const server = createServer({ toolset: "full" });
const full = await Client.connect(server, {
  versionNegotiation: { mode: "legacy" },
});
try {
  const search = await full.callTool<Envelope>("search_ipo_in_statutes", {
    query: "compulsory licensing",
    statute: "patents act 1970",
  });
  const get = await full.callTool<Envelope>("get_ipo_in_section", {
    citation: ["Section 3(d) Patents Act", "Section 999 Patents Act"],
  });
  const mpppSearch = await full.callTool<Envelope>("search_ipo_in_mppp", {
    query: "opposition",
  });
  const mpppGet = await full.callTool<Envelope>("get_ipo_in_mppp_section", {
    citation: "MPPP Chapter 4.5.1",
  });
  if (
    !search.structuredContent?.items.length ||
    get.structuredContent?.items.length !== 1 ||
    !mpppSearch.structuredContent?.items.length ||
    mpppGet.structuredContent?.items.length !== 1
  )
    throw new Error("IPO India (full): MCP search or get failed.");
  report.mcp_full = {
    statutes_search: search.structuredContent.summary,
    statutes_get_not_found: get.structuredContent.not_found,
    mppp_search: mpppSearch.structuredContent.summary,
    mppp_get: mpppGet.structuredContent.summary,
  };
} finally {
  await full.close();
  await server.close();
}
const curatedServer = createServer({ toolset: "curated" });
const curated = await Client.connect(curatedServer, {
  versionNegotiation: { mode: "legacy" },
});
try {
  const search = await curated.callTool<Envelope>("search_legal_reference", {
    corpus: "india_statutes",
    query: "well-known mark",
    statute: "Trade Marks Act",
  });
  const get = await curated.callTool<Envelope>("get_legal_reference", {
    corpus: "india_statutes",
    identifier: "Section 3 Patents Act",
  });
  const mpppSearch = await curated.callTool<Envelope>(
    "search_legal_reference",
    { corpus: "india_mppp", query: "Form 27" },
  );
  const mpppGet = await curated.callTool<Envelope>("get_legal_reference", {
    corpus: "india_mppp",
    identifier: "04.05.02",
  });
  if (
    !search.structuredContent?.items.length ||
    get.structuredContent?.items.length !== 1 ||
    !mpppSearch.structuredContent?.items.length ||
    mpppGet.structuredContent?.items.length !== 1
  )
    throw new Error("IPO India (curated): facade search or get failed.");
  report.mcp_curated = {
    statutes_search: search.structuredContent.summary,
    statutes_get: get.structuredContent.summary,
    mppp_search: mpppSearch.structuredContent.summary,
    mppp_get: mpppGet.structuredContent.summary,
  };
} finally {
  await curated.close();
  await curatedServer.close();
}
console.log(JSON.stringify(report, null, 2));
if (mismatches.length) process.exit(1);

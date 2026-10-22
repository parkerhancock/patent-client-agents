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
import { build } from "./build-ipo-in-corpora.js";

/**
 * Verify packaged IPO India statutes and MPPP artifacts: pins, every row
 * against a fresh parse of the archived official sources
 * (references/ipo-in/sources.json), spot checks of known provisions, and the
 * default full and curated MCP wiring.
 *
 * Usage: bun scripts/verify-ipo-in.ts --statutes S.db.zst --mppp M.db.zst
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
const sources = JSON.parse(
  await readFile(
    resolve(import.meta.dir, "../references/ipo-in/sources.json"),
    "utf8",
  ),
);
const expected = await build(sources);

/** Provisions checked against wording read from the source documents. */
const STATUTE_SPOT_CHECKS: [string, string, string, string[]][] = [
  [
    "Section 3(d) Patents Act",
    "Patents Act",
    "3",
    [
      "the mere discovery of a new form of a known substance which does not result in the enhancement of the known efficacy of that substance",
      "salts, esters, ethers, polymorphs, metabolites, pure form, particle size",
      "(p) an invention which, in effect, is traditional knowledge",
    ],
  ],
  [
    "Section 25 Patents Act",
    "Patents Act",
    "25",
    [
      "Opposition to the patent.",
      "(1) Where an application for a patent has been published but a patent has not been granted, any person may, in writing, represent by way of opposition to the Controller",
      "(2) At any time after the grant of patent but before the expiry of a period of one year from the date of publication of grant of a patent",
    ],
  ],
  [
    "§107A",
    "Patents Act",
    "107A",
    [
      "Certain acts not to be considered as infringement.",
      "a patented invention solely for uses reasonably related to the development and submission of information required under any law",
    ],
  ],
  [
    "Rule 13",
    "Patent Rules",
    "13",
    [
      "(1) Every specification, whether provisional or complete, shall be made in Form 2.",
      "(7) (a) The abstract as specified under clause (d) of sub-section (4) of section 10",
    ],
  ],
  [
    "Section 9 Trade Marks Act",
    "Trade Marks Act",
    "9",
    [
      "Absolute grounds for refusal of registration.",
      "(1) The trade marks— (a) which are devoid of any distinctive character",
      "(3) A mark shall not be registered as a trade mark if it consists exclusively of",
    ],
  ],
];
const MPPP_SPOT_CHECKS: [string, string, string, string[]][] = [
  [
    "MPPP 09.03",
    "09.03",
    "Examination of application",
    ["Chapter 09: Examination and Grant"],
  ],
  [
    "07.02",
    "07.02",
    "International Application under PCT",
    ["Chapter 07: Convention Application, International Application and"],
  ],
];

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
  const statutesCount = (await statuteClient.getCorpusStatus()).section_count;
  const mpppCount = (await mpppClient.getCorpusStatus()).section_count;
  if (statutesCount !== expected.statutes.length)
    mismatches.push(
      `statutes rows ${statutesCount} != ${expected.statutes.length}`,
    );
  if (mpppCount !== expected.mppp.length)
    mismatches.push(`mppp rows ${mpppCount} != ${expected.mppp.length}`);

  // Every row matches a fresh parse of the archived official sources.
  for (const row of expected.statutes) {
    const section = await statuteClient.getSection(row.section_number, {
      statute: row.statute_name,
    });
    if (
      section.content_sha256 !== sha(row.text) ||
      section.title !== row.title ||
      section.source_url !== row.source_url ||
      section.section_number !== row.section_number
    )
      mismatches.push(`statutes ${row.statute_name} ${row.section_number}`);
  }
  for (const row of expected.mppp) {
    const section = await mpppClient.getSection(row.section_number);
    if (
      section.content_sha256 !== sha(row.text) ||
      section.chapter !== row.chapter ||
      section.title !== row.title
    )
      mismatches.push(`mppp ${row.section_number}`);
  }
  const counts: Record<string, number> = {};
  for (const row of expected.statutes)
    counts[row.statute_name] = (counts[row.statute_name] ?? 0) + 1;

  const spot: Record<string, unknown> = {};
  for (const [citation, statute, number, phrases] of STATUTE_SPOT_CHECKS) {
    const section = await statuteClient.getSectionByCitation(citation);
    const flat = section.text.replace(/\s+/g, " ");
    const missing = phrases.filter(
      (phrase) => !`${section.title}. ${flat}`.includes(phrase),
    );
    if (
      section.statute_name !== statute ||
      section.section_number !== number ||
      missing.length
    )
      mismatches.push(`spot ${citation}: ${missing.join(" | ")}`);
    spot[citation] = {
      section: `${section.statute_name} ${section.section_number}`,
      subdivision: section.subdivision ?? null,
      title: section.title,
      chars: section.text.length,
      source_url: section.source_url,
    };
  }
  for (const [reference, number, title, chapter] of MPPP_SPOT_CHECKS) {
    const section = await mpppClient.getSection(reference);
    if (
      section.section_number !== number ||
      !section.title?.startsWith(title) ||
      !chapter.every((value) => section.chapter?.startsWith(value))
    )
      mismatches.push(`spot ${reference}: ${section.title}`);
    spot[reference] = {
      section: section.section_number,
      chapter: section.chapter,
      title: section.title,
      chars: section.text.length,
      source_url: section.source_url,
    };
  }
  report.rows = {
    statutes: counts,
    statutes_total: expected.statutes.length,
    mppp: expected.mppp.length,
    mismatches,
  };
  report.spot_checks = spot;
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
    query: "compulsory licence",
    statute: "patents act 1970",
  });
  const get = await full.callTool<Envelope>("get_ipo_in_section", {
    citation: ["Section 3(d) Patents Act", "Section 999 Patents Act"],
  });
  const mpppSearch = await full.callTool<Envelope>("search_ipo_in_mppp", {
    query: "pre-grant opposition",
  });
  const mpppGet = await full.callTool<Envelope>("get_ipo_in_mppp_section", {
    citation: "MPPP 9.3.5.4",
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
    query: "well-known trade mark",
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
    identifier: "09.03",
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

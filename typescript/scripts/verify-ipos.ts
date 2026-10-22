import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  IposManualsClient,
  IposStatutesClient,
} from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { z } from "zod";
import { createServer } from "../packages/mcp/src/index.js";
import { build, type SourceManifest } from "./build-ipos-corpora.js";

/**
 * Verify packaged IPOS statutes and manuals artifacts: pins, every row
 * against a fresh parse of the archived official sources
 * (references/ipos/sources.json), spot checks of known provisions, and the
 * default MCP wiring.
 *
 * Usage: bun scripts/verify-ipos.ts --statutes S.db.zst --manuals M.db.zst
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
const manualsFile = flag("--manuals");
if (!statutesFile || !manualsFile) {
  console.error(
    "Usage: bun scripts/verify-ipos.ts --statutes FILE.db.zst --manuals FILE.db.zst",
  );
  process.exit(2);
}
const report: Record<string, unknown> = {};

async function configure(prefix: string, file: string) {
  const path = resolve(file);
  const manifest = manifestSchema.parse(
    JSON.parse(await readFile(`${path}.manifest.json`, "utf8")),
  );
  process.env[`${prefix}_CORPUS_PATH`] = path;
  process.env[`${prefix}_CORPUS_SHA256`] = manifest.decoded_sha256;
  process.env[`${prefix}_CORPUS_FILE_SHA256`] = manifest.file_sha256;
  return manifest;
}
const statutesPins = await configure("IPOS_STATUTES", statutesFile);
const manualsPins = await configure("IPOS_MANUALS", manualsFile);
const sources = JSON.parse(
  await readFile(
    resolve(import.meta.dir, "../references/ipos/sources.json"),
    "utf8",
  ),
) as SourceManifest;
const expected = await build(sources);

/** Provisions checked against wording read from the source documents. */
const STATUTE_SPOT_CHECKS: [string, string, string, string[]][] = [
  [
    "Section 13 Patents Act",
    "patents",
    "13",
    [
      "(b) it involves an inventive step; and",
      "(c) it is capable of industrial application.",
    ],
  ],
  [
    "Patents Act s. 15",
    "patents",
    "15",
    [
      "An invention is taken to involve an inventive step if it is not obvious to a person skilled in the art",
    ],
  ],
  [
    "s 8(2) Trade Marks Act",
    "tm",
    "8",
    ["there exists a likelihood of confusion on the part of the public"],
  ],
  [
    "Section 190 Copyright Act 2021",
    "copyright",
    "190",
    ["It is a permitted use of a work to make a fair use of the work."],
  ],
  [
    "Section 5 Registered Designs Act",
    "designs",
    "5",
    [
      "a design which is new may, upon application by the person claiming to be the owner, be registered",
    ],
  ],
  [
    "First Schedule Trade Marks Act",
    "tm",
    "First Schedule",
    ["COLLECTIVE MARKS"],
  ],
];
const MANUAL_SPOT_CHECKS: [string, string, string, string][] = [
  ["IPOS PEG 8.12", "peg", "8.12", "would represent a discovery"],
  ["PEG 4.1", "peg", "4.1", "involves an inventive step"],
  [
    "TM Work Manual 7.5.2.5.2",
    "tm",
    "7.5.2.5.2",
    "Visual similarity deals with the appearance of the marks",
  ],
  ["TM Work Manual 17.3.1", "tm", "17.3.1", "10 years"],
  ["Designs Guidelines 2.1", "designs", "2.1", "should not be tangible"],
];

const mismatches: string[] = [];
const statutes = new IposStatutesClient();
const manuals = new IposManualsClient();
try {
  for (const [client, pins, name] of [
    [statutes, statutesPins, "statutes"],
    [manuals, manualsPins, "manuals"],
  ] as const) {
    const status = await client.getCorpusStatus();
    if (
      !status.available ||
      status.compression !== "zstd" ||
      status.artifact_sha256 !== pins.decoded_sha256 ||
      status.file_sha256 !== pins.file_sha256
    )
      throw new Error(`IPOS ${name}: artifact status or pins failed.`);
    report[name] = {
      corpus_version: status.corpus_version,
      corpus_synced_at: status.corpus_synced_at,
      section_count: status.section_count,
      decoded_sha256: status.artifact_sha256,
      file_sha256: status.file_sha256,
    };
  }
  if (
    (await statutes.getCorpusStatus()).section_count !==
    expected.statutes.length
  )
    mismatches.push(`statutes rows != ${expected.statutes.length}`);
  if (
    (await manuals.getCorpusStatus()).section_count !== expected.manuals.length
  )
    mismatches.push(`manuals rows != ${expected.manuals.length}`);

  // Every row matches a fresh parse of the archived official sources.
  for (const row of expected.statutes) {
    const section = await statutes.getSection(row.section_label, {
      statute: row.statute,
    });
    if (
      section.text !== row.text ||
      section.title !== row.title ||
      section.breadcrumb !== row.breadcrumb ||
      section.sso_url !== row.sso_url
    )
      mismatches.push(`statutes ${row.statute} ${row.section_label}`);
  }
  for (const row of expected.manuals) {
    const section = await manuals.getSection(row.manual, row.section_label);
    if (
      section.text !== row.text ||
      section.title !== row.title ||
      section.source_url !== row.source_url ||
      section.source_version !== row.source_version
    )
      mismatches.push(`manuals ${row.manual} ${row.section_label}`);
  }

  const spot: Record<string, unknown> = {};
  for (const [citation, statute, label, phrases] of STATUTE_SPOT_CHECKS) {
    const section = await statutes.getByCitation(citation);
    const missing = phrases.filter((phrase) => !section.text.includes(phrase));
    if (
      section.statute !== statute ||
      section.section_label !== label ||
      missing.length
    )
      mismatches.push(`spot ${citation}: ${missing.join(" | ")}`);
    spot[citation] = {
      section: `${section.short_name} ${section.section_label}`,
      title: section.title,
      chars: section.text.length,
      sso_url: section.sso_url,
    };
  }
  for (const [citation, manual, label, phrase] of MANUAL_SPOT_CHECKS) {
    const section = await manuals.getByCitation(citation);
    if (
      section.manual !== manual ||
      section.section_label !== label ||
      !section.text.includes(phrase)
    )
      mismatches.push(`spot ${citation}`);
    spot[citation] = {
      title: section.title,
      chars: section.text.length,
      source_url: section.source_url,
      source_version: section.source_version,
    };
  }
  const tally = (values: string[]) =>
    values.reduce<Record<string, number>>((acc, value) => {
      acc[value] = (acc[value] ?? 0) + 1;
      return acc;
    }, {});
  report.rows = {
    statutes: tally(expected.statutes.map((row) => row.statute)),
    manuals: tally(expected.manuals.map((row) => row.manual)),
    tm_headings_not_found: expected.missing,
    mismatches,
  };
  report.spot_checks = spot;
} finally {
  statutes.close();
  manuals.close();
}

type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  not_found?: string[];
};
const server = createServer({ toolset: "full" });
const client = await Client.connect(server, {
  versionNegotiation: { mode: "legacy" },
});
try {
  const search = await client.callTool<Envelope>("search_ipos_statutes", {
    query: "inventive step",
  });
  const get = await client.callTool<Envelope>("get_ipos_section", {
    citation: ["Section 13 Patents Act", "Section 999 Patents Act"],
  });
  const list = await client.callTool<Envelope>("list_ipos_statutes", {});
  const manualSearch = await client.callTool<Envelope>("search_ipos_manuals", {
    query: "likelihood of confusion",
  });
  const manualGet = await client.callTool<Envelope>("get_ipos_manual_section", {
    citation: "IPOS PEG 8.12",
  });
  const manualList = await client.callTool<Envelope>("list_ipos_manuals", {});
  if (
    !search.structuredContent?.items.length ||
    get.structuredContent?.items.length !== 1 ||
    list.structuredContent?.items.length !== 4 ||
    !manualSearch.structuredContent?.items.length ||
    manualGet.structuredContent?.items.length !== 1 ||
    manualList.structuredContent?.items.length !== 3
  )
    throw new Error("IPOS: MCP search, get or list failed.");
  report.mcp = {
    statutes_search: search.structuredContent.summary,
    statutes_get_not_found: get.structuredContent.not_found,
    statutes_list: list.structuredContent.summary,
    manuals_search: manualSearch.structuredContent.summary,
    manuals_get: manualGet.structuredContent.summary,
    manuals_list: manualList.structuredContent.summary,
  };
} finally {
  await client.close();
  await server.close();
}
console.log(JSON.stringify(report, null, 2));
if (mismatches.length) process.exit(1);

import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { EurlexClient } from "../packages/client/src/eurlex.js";

/** Live samples recorded October 27, 2026. CELLAR needs no credentials. */
export const samples = {
  judgment: "62007CJ0252",
  spcJudgment: "62017CJ0650",
  regulation: "32017R1001",
  designs: "32002R0006",
  consolidatedDirective: "01996L0009-20190606",
  directive: "32016L0943",
  missing: "32099R9999",
} as const;

type Run = (client: EurlexClient) => Promise<unknown>;
/** Library operations, one cassette each. SPARQL queries are POSTs, matched by body. */
export const operations: Record<string, Run> = {
  "search-patents-cj": (c) =>
    c.searchCaseLaw({
      subjects: ["patents"],
      court: "court_of_justice",
      documentType: "judgment",
      limit: 3,
    }),
  "search-words": (c) =>
    c.searchCaseLaw({
      words: "supplementary protection certificate",
      limit: 2,
    }),
  "search-dates": (c) =>
    c.searchCaseLaw({
      subjects: ["designs"],
      dateFrom: "2025-01-01",
      dateTo: "2025-12-31",
      limit: 2,
    }),
  judgment: (c) => c.getDocument(samples.judgment),
  "judgment-french": (c) => c.getDocument(samples.spcJudgment, "fr"),
  regulation: (c) => c.getDocument(samples.designs),
  consolidated: (c) => c.getDocument(samples.consolidatedDirective),
  missing: (c) => c.getDocument(samples.missing),
  legislation: (c) => c.listLegislation(),
};
/** MCP tool calls, one cassette each. */
export const toolCalls: Record<string, [string, Record<string, unknown>]> = {
  search: [
    "search_eu_ip_case_law",
    { words: "likelihood of confusion", court: "court_of_justice", limit: 3 },
  ],
  "get-judgment": ["get_eurlex_document", { celex: samples.spcJudgment }],
  "get-regulation": ["get_eurlex_document", { celex: samples.directive }],
  "list-patents": ["list_eu_ip_legislation", { topic: "patents" }],
};

export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `eurlex-${name}.yaml`);
export const replayClient = () => new EurlexClient({ retryLimit: 0 });

/** Replay (default) or record `run` against cassette `name`. */
export async function eurlexCassette<T>(
  name: string,
  run: () => Promise<T>,
  record = false,
): Promise<T> {
  if (!record && !existsSync(cassettePath(name)))
    throw new Error(`Missing EUR-Lex cassette: ${name}`);
  let result: T | undefined;
  await useCassette(
    cassettePath(name),
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri", "body"],
      filterHeaders: ["set-cookie"],
    },
    async () => {
      result = await run();
    },
  );
  return result as T;
}
export function eurlexRecording<T = unknown>(name: string): Promise<T> {
  const run = operations[name];
  if (!run) throw new Error(`Unknown EUR-Lex operation: ${name}`);
  return eurlexCassette(name, () => run(replayClient()) as Promise<T>);
}

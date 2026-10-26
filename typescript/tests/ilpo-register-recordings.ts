import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { IlpoRegisterClient } from "../packages/client/src/ilpo-register.js";

/** Live samples recorded October 27, 2026. data.gov.il needs no credentials. */
export const samples = {
  mark: 55359,
  markWithPriority: 120208,
  missingMark: 9_999_999,
  patent: 250000,
  grantedPatent: 232667,
  missingPatent: 9_999_999,
} as const;

type Run = (client: IlpoRegisterClient) => Promise<unknown>;
/** Library operations, one cassette each. */
export const operations: Record<string, Run> = {
  "trademarks-words": (c) =>
    c.query("trademarks", {
      words: { mark_text_en: "coca cola" },
      limit: 3,
      sort: "mark_number desc",
    }),
  "trademarks-nice-3": (c) =>
    c.query("trademarks", {
      tokens: { nice_classes: 3 },
      limit: 3,
      sort: "mark_number desc",
    }),
  "trademarks-filter": (c) =>
    c.query("trademarks", { filters: { mark_number: [samples.mark, 9] } }),
  "patents-text": (c) => c.query("patents", { text: "graphene", limit: 2 }),
  "patents-plain-english": (c) =>
    c.query("patents", { words: { title_en: "battery" }, limit: 2 }),
  "classifications-for": (c) =>
    c.rowsFor("patentClassifications", [samples.patent]),
};
/** MCP tool calls, one cassette each. */
export const toolCalls: Record<string, [string, Record<string, unknown>]> = {
  "search-trademarks": [
    "search_ilpo_trademarks",
    { q: "coca cola", status: "registered", limit: 3 },
  ],
  "search-trademarks-hebrew-owner": [
    "search_ilpo_trademarks",
    { owner: "שטראוס", nice_class: 30, limit: 3 },
  ],
  "get-trademarks": [
    "get_ilpo_trademark",
    {
      mark_number: [
        samples.markWithPriority,
        samples.mark,
        samples.missingMark,
      ],
    },
  ],
  "search-patents": [
    "search_ilpo_patents",
    { q: "graphene", status: "granted", limit: 3 },
  ],
  "search-patents-applicant": [
    "search_ilpo_patents",
    { applicant: "Teva", limit: 3 },
  ],
  "search-patents-ipc": ["search_ilpo_patents", { ipc: "H01M 4", limit: 3 }],
  "get-patents": [
    "get_ilpo_patent",
    {
      application_number: [
        samples.grantedPatent,
        samples.patent,
        samples.missingPatent,
      ],
    },
  ],
};

export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `ilpo-register-${name}.yaml`);
export const replayClient = () => new IlpoRegisterClient({ retryLimit: 0 });

/** Replay (default) or record `run` against cassette `name`. */
export async function ilpoCassette<T>(
  name: string,
  run: () => Promise<T>,
  record = false,
): Promise<T> {
  if (!record && !existsSync(cassettePath(name)))
    throw new Error(`Missing ILPO register cassette: ${name}`);
  let result: T | undefined;
  await useCassette(
    cassettePath(name),
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
      filterHeaders: ["set-cookie"],
    },
    async () => {
      result = await run();
    },
  );
  return result as T;
}
export function ilpoRecording<T = unknown>(name: string): Promise<T> {
  const run = operations[name];
  if (!run) throw new Error(`Unknown ILPO register operation: ${name}`);
  return ilpoCassette(name, () => run(replayClient()) as Promise<T>);
}

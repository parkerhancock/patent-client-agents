import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { PrvClient } from "../packages/client/src/prv.js";

/** Live PRV samples recorded October 27, 2026. PRV needs no credentials. */
export const samples = {
  patent: "SE2616246-1",
  patentCompact: "26162461",
  epPatent: "EP00108480.5",
  missing: "SE9999999-9",
  trademark: "2000-00010",
  design: "1970-1175",
} as const;

type Run = (client: PrvClient) => Promise<unknown>;
/** Library operations, one cassette each. */
export const operations: Record<string, Run> = {
  "patents-search": (c) => c.searchPatents({ text: "Volvo", pageSize: 2 }),
  "patents-search-page-1": (c) =>
    c.searchPatents({ text: "Volvo", pageSize: 2, page: 1 }),
  "trademarks-search": (c) => c.searchTrademarks({ text: "IKEA", pageSize: 2 }),
  "designs-search": (c) => c.searchDesigns({ text: "stol", pageSize: 2 }),
  "spcs-applicant": (c) =>
    c.searchSpcs({ applicants: "AstraZeneca", pageSize: 2 }),
  "spcs-substance": (c) => c.searchSpcs({ substance: "naproxen", pageSize: 2 }),
  "spcs-base-patent": (c) =>
    c.searchSpcs({ basePatentNumber: samples.epPatent }),
  "spcs-marketing-authorization": (c) =>
    c.searchSpcs({ marketingAuthorizationNumber: "EU/1", pageSize: 2 }),
  "spcs-number": (c) => c.searchSpcs({ applicationNumberSpc: "1190011-5" }),
  "patent-record": (c) => c.getPatent(samples.patent),
  "patent-record-compact": (c) => c.getPatent(samples.patentCompact),
  "patent-record-ep": (c) => c.getPatent(samples.epPatent),
  "patent-missing": (c) => c.getPatent(samples.missing),
  "trademark-record": (c) => c.getTrademark(samples.trademark),
  "trademark-missing": (c) => c.getTrademark("1999-99999"),
  "design-record": (c) => c.getDesign(samples.design),
};
/** MCP tool calls, one cassette each. */
export const toolCalls: Record<string, [string, Record<string, unknown>]> = {
  "search-patents": ["search_prv_patents", { text: "Volvo", page_size: 2 }],
  "get-patents": [
    "get_prv_patent",
    { application_number: [samples.patent, "9999999-9"] },
  ],
  "search-spcs": [
    "search_prv_spcs",
    { substance_product: "naproxen", page_size: 2 },
  ],
  "get-trademarks": [
    "get_prv_trademark",
    { application_number: [samples.trademark, "1999-99999"] },
  ],
  "get-designs": ["get_prv_design", { application_number: samples.design }],
  "search-designs": ["search_prv_designs", { text: "stol", page_size: 2 }],
};

export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `prv-${name}.yaml`);
export const replayClient = () => new PrvClient({ retryLimit: 0 });

/** Replay (default) or record `run` against cassette `name`. */
export async function prvCassette<T>(
  name: string,
  run: () => Promise<T>,
  record = false,
): Promise<T> {
  if (!record && !existsSync(cassettePath(name)))
    throw new Error(`Missing PRV cassette: ${name}`);
  let result: T | undefined;
  await useCassette(
    cassettePath(name),
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri", "json_body"],
      filterHeaders: ["set-cookie"],
    },
    async () => {
      result = await run();
    },
  );
  return result as T;
}
export function prvRecording<T = unknown>(name: string): Promise<T> {
  const run = operations[name];
  if (!run) throw new Error(`Unknown PRV operation: ${name}`);
  return prvCassette(name, () => run(replayClient()) as Promise<T>);
}

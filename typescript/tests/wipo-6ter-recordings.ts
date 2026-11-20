import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { Wipo6terClient } from "../packages/client/src/wipo-6ter.js";

/** Live samples recorded October 27, 2026. Article 6ter needs no credentials. */
export const samples = {
  unesco: "QO0088",
  maltaFlag: "MT0013",
  missing: "XX9999",
} as const;

type Run = (client: Wipo6terClient) => Promise<unknown>;
/** Library operations, one cassette each. */
export const operations: Record<string, Run> = {
  "search-any": (c) => c.search({ keywords: "UNESCO", limit: 3 }),
  "search-phrase": (c) =>
    c.search({ keywords: "united nations", searchType: "PHRASE", limit: 2 }),
  "search-hallmark-relevance": (c) =>
    c.search({ keywords: "hallmark", sortBy: "REL", limit: 2, offset: 10 }),
  sign: (c) => c.getSign(samples.unesco),
  "sign-missing": (c) => c.getSign(samples.missing),
  "last-updated": (c) => c.lastUpdated(),
  publication: (c) => c.publication(),
};
/** MCP tool calls, one cassette each. */
export const toolCalls: Record<string, [string, Record<string, unknown>]> = {
  search: [
    "search_wipo_6ter",
    { keywords: "world health", search_type: "ALL", limit: 3 },
  ],
  "get-signs": [
    "get_wipo_6ter_sign",
    { sign_id: [samples.unesco, "mt0013", samples.missing] },
  ],
};

export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `wipo-6ter-${name}.yaml`);
export const replayClient = () => new Wipo6terClient({ retryLimit: 0 });

/** Replay (default) or record `run` against cassette `name`. */
export async function sixterCassette<T>(
  name: string,
  run: () => Promise<T>,
  record = false,
): Promise<T> {
  if (!record && !existsSync(cassettePath(name)))
    throw new Error(`Missing WIPO 6ter cassette: ${name}`);
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
export function sixterRecording<T = unknown>(name: string): Promise<T> {
  const run = operations[name];
  if (!run) throw new Error(`Unknown WIPO 6ter operation: ${name}`);
  return sixterCassette(name, () => run(replayClient()) as Promise<T>);
}

import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { EuipoGuidelinesClient } from "../packages/client/src/euipo-guidelines.js";

/** Live samples recorded October 27, 2026. The Guidelines API needs no credentials. */
export const samples = {
  leaf: "2068232",
  section: "2231981",
  missing: "99999999",
} as const;

type Run = (client: EuipoGuidelinesClient) => Promise<unknown>;
/** Library operations, one cassette each. Searches are POSTs, matched by JSON body. */
export const operations: Record<string, Run> = {
  publications: (c) => c.listPublications(),
  search: (c) => c.search("acquired distinctiveness", { limit: 3 }),
  "search-part": (c) =>
    c.search("acquired distinctiveness", { part: "C", limit: 5 }),
  "search-designs": (c) =>
    c.search("visibility", { guidelines: "designs", part: "INV RCD" }),
  "search-german": (c) =>
    c.search("Unterscheidungskraft", { language: "de", limit: 2 }),
  "search-edition": (c) =>
    c.search("visibility", {
      guidelines: "designs",
      edition: "2023",
      limit: 2,
    }),
  contents: (c) => c.contents(),
  "contents-part": (c) => c.contents("t1-k8"),
  "contents-gi": (c) => c.contents("t1", { guidelines: "craft_gi" }),
  leaf: (c) => c.getPage(samples.leaf),
  section: (c) => c.getPage(samples.section),
  missing: (c) => c.getPage(samples.missing),
};
/** MCP tool calls, one cassette each. */
export const toolCalls: Record<string, [string, Record<string, unknown>]> = {
  search: [
    "search_euipo_guidelines",
    { query: "genuine use", part: "C", limit: 3 },
  ],
  browse: ["browse_euipo_guidelines", { guidelines: "designs" }],
  page: ["get_euipo_guidelines_page", { page_id: samples.leaf }],
};

export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `euipo-guidelines-${name}.yaml`);
export const replayClient = () => new EuipoGuidelinesClient({ retryLimit: 0 });

/** Replay (default) or record `run` against cassette `name`. */
export async function euipoGuidelinesCassette<T>(
  name: string,
  run: () => Promise<T>,
  record = false,
): Promise<T> {
  if (!record && !existsSync(cassettePath(name)))
    throw new Error(`Missing EUIPO Guidelines cassette: ${name}`);
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
export function euipoGuidelinesRecording<T = unknown>(
  name: string,
): Promise<T> {
  const run = operations[name];
  if (!run) throw new Error(`Unknown EUIPO Guidelines operation: ${name}`);
  return euipoGuidelinesCassette(name, () => run(replayClient()) as Promise<T>);
}

/** The search metadata the client reads; the rest is publishing bookkeeping (GUIDs, baselines). */
const SEARCH_META = [
  "FTITLE.logical.value",
  "rawlanguagetitle.generated.value",
  "part.scope.generated.value",
  "chapter.scope.generated.value",
  "section.scope.generated.value",
];

/**
 * Trim a recording to what the client reads. The publication list (357
 * editions and languages, 240 KB) is kept whole only in the `publications`
 * cassette; elsewhere only the English and German entries, all the other
 * cassettes resolve. Search hits keep the metadata in SEARCH_META.
 */
export async function trimRecording(name: string) {
  const path = cassettePath(name);
  const cassette = Bun.YAML.parse(await Bun.file(path).text()) as {
    interactions: {
      request: { uri: string };
      response: { body: { type: string; content?: unknown } };
    }[];
  };
  for (const { request, response } of cassette.interactions) {
    const content = response.body.content;
    if (
      name !== "publications" &&
      request.uri.endsWith("/api/publications") &&
      Array.isArray(content)
    )
      response.body.content = (content as { Language: string }[]).filter(
        (p) => p.Language === "en" || p.Language === "de",
      );
    if (request.uri.endsWith("/api/search") && content)
      for (const hit of (content as { QueryResults?: { Meta?: object }[] })
        .QueryResults ?? [])
        if (hit.Meta)
          hit.Meta = Object.fromEntries(
            Object.entries(hit.Meta).filter(([key]) =>
              SEARCH_META.includes(key),
            ),
          );
  }
  await Bun.write(path, Bun.YAML.stringify(cassette, null, 2));
}

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { gunzipSync } from "node:zlib";
import { useCassette } from "cassetter";
import {
  WipoLexClient,
  type WipoLexLegislation,
  type WipoLexSearchResult,
} from "../packages/client/src/index.js";

export const wipoLexCassette = resolve(
  import.meta.dir,
  "cassettes",
  "wipo-lex.yaml",
);
export interface WipoLexRecording {
  /** Canada, patents, main IP laws: latest versions only. */
  latest: WipoLexSearchResult;
  /** The same filters with historical and supplemental texts. */
  historical: WipoLexSearchResult;
  /** Trade secrets texts dated 2020, with no jurisdiction filter. */
  dated: WipoLexSearchResult;
  /** The Canadian Patent Act. */
  patentAct: WipoLexLegislation;
  /** A nonexistent ID: the site's 404. */
  missing: { code: string; status: number };
}

/** WIPO signs attachment links for five minutes; keep the signatures out of the repository anyway. */
export function scrubSignatures(text: string): string {
  return text.replace(/(Signature(?:&#x3D;|=))[A-Za-z0-9~_-]+/g, "$1REDACTED");
}

/** Replay (default) or record one session against the public WIPO Lex site. */
export async function wipoLexRecording(
  record = false,
): Promise<WipoLexRecording> {
  if (!record && !existsSync(wipoLexCassette))
    throw new Error("Missing WIPO Lex cassette.");
  let result: WipoLexRecording | undefined;
  await useCassette(
    wipoLexCassette,
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
      filterHeaders: ["set-cookie", "cookie"],
    },
    async () => {
      const client = new WipoLexClient({ retryLimit: 0 });
      const filters = {
        countryCodes: ["CA"],
        subjectMatter: [1],
        typeOfText: [205],
      };
      const latest = await client.search(filters);
      const historical = await client.search({
        ...filters,
        includeHistorical: true,
      });
      const dated = await client.search({
        subjectMatter: [9],
        startDate: "2020-01-01",
        endDate: "2020-12-31",
      });
      const patentAct = (await client.get("23293")).data;
      const missing = await client.get("99999999").then(
        () => ({ code: "FOUND", status: 200 }),
        (error) => ({ code: error.code, status: error.status }),
      );
      result = { latest, historical, dated, patentAct, missing };
    },
  );
  if (record)
    writeFileSync(
      wipoLexCassette,
      scrubSignatures(readFileSync(wipoLexCassette, "utf8")),
    );
  return result as WipoLexRecording;
}

export const wipoLexFixture = (name: string) =>
  gunzipSync(
    readFileSync(
      join(import.meta.dir, "fixtures", "wipo-lex", `${name}.html.gz`),
    ),
  ).toString("utf8");

/** A WipoLexClient over a synthetic site that serves the archived pages. */
export function fixtureSite() {
  const requests: URL[] = [];
  const fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(new Request(input, init).url);
    requests.push(url);
    const page = (name: string) =>
      new Response(wipoLexFixture(name), {
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    const detail = /\/legislation\/details\/(\d+)$/.exec(url.pathname)?.[1];
    if (detail === "23293" || detail === "23766")
      return page(`details-${detail}`);
    if (url.pathname.endsWith("/legislation/results"))
      return page(
        url.searchParams.get("keywords") === "nothing"
          ? "search-empty"
          : "search-ca-patents-historical",
      );
    return new Response("Page Not Found", { status: 404 });
  }) as typeof globalThis.fetch;
  return { requests, client: new WipoLexClient({ fetch, retryLimit: 0 }) };
}

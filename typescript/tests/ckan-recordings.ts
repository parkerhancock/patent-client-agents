import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  type CkanCatalogClient,
  IlpoTmClient,
  IpAustraliaBulkClient,
} from "../packages/client/src/ckan.js";

/** Live samples recorded October 27, 2026. Neither portal needs credentials. */
export const samples = {
  ilpoRegister: "6284d4a9-fdd4-45c9-a1d6-58143c7d8127",
  ipaZip: "c79b3af6-3720-44ac-9e39-6a68f5635924",
} as const;

type Run = (clients: {
  ilpo: CkanCatalogClient;
  ipa: CkanCatalogClient;
}) => Promise<unknown>;
/** Library operations, one cassette each. */
export const operations: Record<string, Run> = {
  "ilpo-register": ({ ilpo }) => ilpo.getDataset(),
  "ilpo-classifications": ({ ilpo }) => ilpo.getDataset("trademarks_nice"),
  // Python's default id.
  "ilpo-python-default": ({ ilpo }) => ilpo.getDataset("trade-marks"),
  "ipa-iprapid": ({ ipa }) => ipa.getDataset(),
  "ipa-missing": ({ ipa }) => ipa.getDataset("no-such-dataset-zz"),
};
/** MCP tool calls, one cassette each. */
export const toolCalls: Record<string, [string, Record<string, unknown>]> = {
  "list-ilpo": ["list_ilpo_tm_releases", {}],
  "download-ilpo": ["download_ilpo_tm", { resource_id: samples.ilpoRegister }],
  "list-ipa": ["list_ipa_bulk_releases", {}],
  "download-ipa": ["download_ipa_bulk", { release_id: samples.ipaZip }],
};

export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `ckan-${name}.yaml`);
export const replayClients = () => ({
  ilpo: new IlpoTmClient({ retryLimit: 0 }),
  ipa: new IpAustraliaBulkClient({ retryLimit: 0 }),
});

/** Replay (default) or record `run` against cassette `name`. */
export async function ckanCassette<T>(
  name: string,
  run: () => Promise<T>,
  record = false,
): Promise<T> {
  if (!record && !existsSync(cassettePath(name)))
    throw new Error(`Missing CKAN cassette: ${name}`);
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
export function ckanRecording<T = unknown>(name: string): Promise<T> {
  const run = operations[name];
  if (!run) throw new Error(`Unknown CKAN operation: ${name}`);
  return ckanCassette(name, () => run(replayClients()) as Promise<T>);
}

/**
 * The portals' HTML pages (data.gov.au's unknown-dataset page) carry
 * third-party widget keys and add nothing a test reads, so recordings keep
 * their status and headers and replace the HTML body.
 */
export async function omitHtmlBodies(name: string) {
  const path = cassettePath(name);
  const cassette = Bun.YAML.parse(await Bun.file(path).text()) as {
    interactions: {
      response: {
        headers: Record<string, string[]>;
        body: { type: string; content?: string };
      };
    }[];
  };
  let changed = false;
  for (const { response } of cassette.interactions)
    if (
      response.headers["content-type"]?.some((value) =>
        value.includes("text/html"),
      )
    ) {
      response.body = {
        type: "text",
        content: "<!-- HTML page omitted from the recording -->",
      };
      changed = true;
    }
  if (changed) await Bun.write(path, Bun.YAML.stringify(cassette, null, 2));
}
